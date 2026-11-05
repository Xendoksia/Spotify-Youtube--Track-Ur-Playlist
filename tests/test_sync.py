import sqlite3
import unittest
from unittest import mock

from playlist_tracker.core import sync
from playlist_tracker.music import listening
from tests.test_listening import ListeningTestCase, utc


def remote(uid: str, at: str, ms: int = 200_000, device: str = "phone", name: str = "Song") -> dict:
    return {"uid": uid, "device": device, "played_at": listening.to_utc(utc(at)), "source": "local",
            "artist": "A", "name": name, "album": "Album", "ms_played": ms}


class SyncStorageTest(ListeningTestCase):
    def test_new_plays_wait_to_be_sent_until_marked(self):
        self.play("A", "Song", "2026-11-02 10:00")
        [play] = listening.unsynced(10, self.db)
        self.assertTrue(play["uid"])
        self.assertIsNone(play["device"])
        listening.mark_synced([play], self.db)
        self.assertEqual(listening.unsynced(10, self.db), [])

    def test_a_longer_listening_time_is_sent_again(self):
        play_id = listening.record_local({"artist": "A", "name": "Song", "album": "",
                                          "played_at": listening.to_utc(utc("2026-11-02 10:00")), "ms": 30_000},
                                         self.db)
        [sent] = listening.unsynced(10, self.db)
        # The song keeps playing while it is being sent
        listening.update_local(play_id, 90_000, self.db)
        listening.mark_synced([sent], self.db)
        [again] = listening.unsynced(10, self.db)
        self.assertEqual(again["ms_played"], 90_000)

    def test_plays_of_other_devices_are_stored_once_and_not_sent_back(self):
        plays = [remote("u1", "2026-11-02 10:00"), remote("u2", "2026-11-02 11:00", name="Other")]
        self.assertEqual(listening.merge_remote(plays, self.db), 2)
        self.assertEqual(listening.merge_remote(plays, self.db), 0)
        self.assertEqual(len(listening.recent_plays(db_path=self.db)), 2)
        self.assertEqual(listening.unsynced(10, self.db), [])

    def test_a_fetched_play_keeps_the_longest_listening_time(self):
        listening.merge_remote([remote("u1", "2026-11-02 10:00", ms=60_000)], self.db)
        listening.merge_remote([remote("u1", "2026-11-02 10:00", ms=180_000)], self.db)
        listening.merge_remote([remote("u1", "2026-11-02 10:00", ms=90_000)], self.db)
        [stored] = listening.recent_plays(db_path=self.db)
        self.assertEqual(stored["ms_played"], 180_000)

    def test_plays_stored_before_syncing_get_an_id(self):
        with sqlite3.connect(self.db) as db:
            db.execute("CREATE TABLE listens (id INTEGER PRIMARY KEY AUTOINCREMENT, played_at TEXT NOT NULL, "
                       "source TEXT NOT NULL, artist TEXT, name TEXT, album TEXT, artist_key TEXT NOT NULL, "
                       "track_key TEXT NOT NULL, ms_played INTEGER, UNIQUE (source, played_at, track_key))")
            db.executemany("INSERT INTO listens (played_at, source, artist, name, album, artist_key, track_key, "
                           "ms_played) VALUES (?, 'local', 'A', ?, '', 'a', ?, 1000)",
                           [("2026-11-02T10:00:00Z", "One", "a|one"), ("2026-11-02T11:00:00Z", "Two", "a|two")])
        db.close()
        plays = listening.unsynced(10, self.db)
        self.assertEqual(len(plays), 2)
        self.assertEqual(len({p["uid"] for p in plays}), 2)

    def test_after_logging_out_everything_goes_to_the_next_account(self):
        self.play("A", "Song", "2026-11-02 10:00")
        listening.mark_synced(listening.unsynced(10, self.db), self.db)
        listening.mark_all_unsynced(self.db)
        self.assertEqual(len(listening.unsynced(10, self.db)), 1)


class FakeClient:
    """Answers like PostgREST from a list of rows."""

    def __init__(self, rows=None):
        self.rows = rows or []
        self.sent = []

    def rest(self, method, path, payload=None, prefer=None):
        if method == "POST":
            self.sent.extend(payload)
            return None
        offset = int(path.rsplit("offset=", 1)[1])
        return self.rows[offset:offset + sync.BATCH]


class SyncTest(ListeningTestCase):
    def setUp(self):
        super().setUp()
        self.config = {"DEVICE_ID": "pc"}
        db_path = self.db
        for target, value in (("load_config", lambda: dict(self.config)),
                              ("save_config", lambda config: self.config.update(config))):
            patcher = mock.patch.object(sync, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for name in ("unsynced", "mark_synced", "merge_remote"):
            original = getattr(listening, name)
            patcher = mock.patch.object(sync.listening, name,
                                        lambda *args, original=original: original(*args, db_path=db_path))
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_push_sends_own_plays_with_this_device(self):
        self.play("A", "Song", "2026-11-02 10:00")
        client = FakeClient()
        self.assertEqual(sync.push(client, "user"), 1)
        [row] = client.sent
        self.assertEqual((row["user_id"], row["device_id"]), ("user", "pc"))
        self.assertIn("device_name", row)
        self.assertEqual(sync.push(client, "user"), 0)

    def test_pull_pages_through_and_remembers_where_it_stopped(self):
        rows = [{**remote(f"u{i}", "2026-11-02 10:00", name=f"Song {i}"), "device_id": "phone",
                 "updated_at": f"2026-11-05T10:00:{i % 60:02d}.000000+00:00"} for i in range(sync.BATCH + 3)]
        client = FakeClient(rows)
        self.assertEqual(sync.pull(client), sync.BATCH + 3)
        self.assertEqual(self.config["SYNC_PULLED"], rows[-1]["updated_at"])


if __name__ == "__main__":
    unittest.main()
