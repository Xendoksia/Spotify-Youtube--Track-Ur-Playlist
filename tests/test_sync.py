import re
import sqlite3
import unittest
from pathlib import Path
from unittest import mock

from playlist_tracker.core import sync
from playlist_tracker.music import listening
from playlist_tracker.playlists import history
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
        offset = re.search(r"offset=(\d+)", path)
        if not offset:
            return self.rows
        offset = int(offset.group(1))
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
        for name in ("unsynced", "mark_synced", "merge_remote", "all_uids", "mark_unsynced"):
            original = getattr(listening, name)
            patcher = mock.patch.object(sync.listening, name,
                                        lambda *args, original=original: original(*args, db_path=db_path))
            patcher.start()
            self.addCleanup(patcher.stop)
        self.spotify_db = Path(self._folder.name) / "history.db"
        patcher = mock.patch.object(sync, "PLAYLIST_DATABASES", {"spotify": self.spotify_db})
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

    def test_check_sends_what_the_cloud_lacks_and_fetches_what_is_missing_here(self):
        # Here: a (in the cloud too) and b (marked sent but lost in the cloud)
        for uid in ("a", "b"):
            listening.merge_remote([remote(uid, f"2026-11-02 1{ord(uid) - 97}:00", device=None, name=uid)])
        listening.mark_synced(listening.unsynced(10))
        # The cloud: a, c (a phone play not fetched yet) and d (the phone's copy of a, kept here once)
        cloud = [{**remote("a", "2026-11-02 10:00", name="a"), "device_id": None},
                 {**remote("c", "2026-11-03 10:00", name="c"), "device_id": "phone", "source": "android"},
                 {**remote("d", "2026-11-02 10:01", name="a"), "device_id": "phone", "source": "android"}]
        client = FakeClient(cloud)
        result = sync.check(client, "user")
        self.assertEqual([row["uid"] for row in client.sent], ["b"])
        self.assertEqual((result["cloud"], result["here"], result["sent"], result["fetched"], result["twice"]),
                         (3, 3, 1, 1, 1))
        self.assertEqual(self.config["SYNC_CHECK"]["twice"], 1)
        self.assertFalse(sync.check_due())

    def test_pull_pages_through_and_remembers_where_it_stopped(self):
        rows = [{**remote(f"u{i}", "2026-11-02 10:00", name=f"Song {i}"), "device_id": "phone",
                 "updated_at": f"2026-11-05T10:00:{i % 60:02d}.000000+00:00"} for i in range(sync.BATCH + 3)]
        client = FakeClient(rows)
        self.assertEqual(sync.pull(client), sync.BATCH + 3)
        self.assertEqual(self.config["SYNC_PULLED"], rows[-1]["updated_at"])


    def test_tracking_changes_are_sent_once(self):
        history.set_tracked("p1", "Mix", True, self.spotify_db)
        client = FakeClient()
        self.assertEqual(sync.push_playlists(client, "user"), 1)
        [row] = client.sent
        self.assertEqual((row["service"], row["playlist_id"], row["tracked"]), ("spotify", "p1", True))
        self.assertEqual(sync.push_playlists(client, "user"), 0)

    def test_a_newer_change_from_another_device_wins(self):
        history.set_tracked("p1", "Mix", True, self.spotify_db)
        rows = [{"service": "spotify", "playlist_id": "p1", "name": "Mix", "tracked": False,
                 "changed_at": "2999-01-01T00:00:00.000000Z", "updated_at": "2026-11-05T10:00:00+00:00"},
                {"service": "spotify", "playlist_id": "p2", "name": "New", "tracked": True,
                 "changed_at": "2999-01-01T00:00:00.000000Z", "updated_at": "2026-11-05T10:00:01+00:00"}]
        self.assertEqual(sync.pull_playlists(FakeClient(rows)), 2)
        self.assertEqual([p["playlist_id"] for p in history.tracked_playlists(self.spotify_db)], ["p2"])
        # Taken over, so not sent back
        self.assertEqual(history.unsynced_playlists(self.spotify_db), [])

    def test_an_older_change_from_another_device_is_ignored(self):
        history.set_tracked("p1", "Mix", True, self.spotify_db)
        rows = [{"service": "spotify", "playlist_id": "p1", "name": "Mix", "tracked": False,
                 "changed_at": "2000-01-01T00:00:00.000000Z", "updated_at": "2026-11-05T10:00:00+00:00"}]
        self.assertEqual(sync.pull_playlists(FakeClient(rows)), 0)
        self.assertEqual(len(history.tracked_playlists(self.spotify_db)), 1)

    def test_playlists_tracked_before_syncing_lose_to_any_change(self):
        with history.open_db(self.spotify_db) as db:
            db.execute("INSERT INTO playlists (playlist_id, name, tracked) VALUES ('p1', 'Old', 1)")
        [playlist] = history.unsynced_playlists(self.spotify_db)
        self.assertEqual(playlist["changed_at"], history.NEVER)
        history.mark_playlists_synced([playlist], self.spotify_db)
        self.assertEqual(history.unsynced_playlists(self.spotify_db), [])

    def remote_event(self, uid, event, checked_at, uri="track:1", added_at="2026-01-01T00:00:00Z"):
        return {"uid": uid, "device_id": "phone", "service": "spotify", "playlist_id": "p1",
                "checked_at": checked_at, "event": event, "uri": uri, "name": "Song", "artist": "A",
                "album": "", "added_at": added_at, "updated_at": f"2026-11-07T10:00:00.{uid[-1]}+00:00"}

    def test_events_found_here_are_sent_once_with_this_device(self):
        with history.open_db(self.spotify_db) as db:
            history._write_event(db, "p1", "2026-11-07T10:00:00+03:00", history.EVENT_REMOVED,
                                 {"uri": "track:1", "name": "Song", "added_at": "2026-01-01T00:00:00Z"})
        client = FakeClient()
        self.assertEqual(sync.push_events(client, "user"), 1)
        [row] = client.sent
        self.assertEqual((row["service"], row["device_id"], row["event"]), ("spotify", "pc", "REMOVED"))
        self.assertNotIn("device", row)
        self.assertEqual(sync.push_events(client, "user"), 0)

    def test_events_of_other_devices_are_stored_once_and_not_sent_back(self):
        rows = [self.remote_event("e1", history.EVENT_REMOVED, "2026-11-07T10:00:00+03:00")]
        self.assertEqual(sync.pull_events(FakeClient(rows)), 1)
        self.assertEqual(sync.pull_events(FakeClient(rows)), 0)
        self.assertEqual(len(history.get_events(None, self.spotify_db)), 1)
        self.assertEqual(history.unsynced_events(10, self.spotify_db), [])
        self.assertEqual(self.config["SYNC_EVENTS_PULLED"], rows[-1]["updated_at"])

    def test_a_change_two_devices_found_is_stored_once(self):
        with history.open_db(self.spotify_db) as db:
            history._write_event(db, "p1", "2026-11-07T12:00:00+03:00", history.EVENT_UNPLAYABLE,
                                 {"uri": "track:1", "added_at": "2026-01-01T00:00:00Z"})
        # Found earlier on the phone, and again here
        rows = [self.remote_event("e1", history.EVENT_UNPLAYABLE, "2026-11-07T10:00:00+03:00")]
        self.assertEqual(sync.pull_events(FakeClient(rows)), 0)
        # A later change of the same track is not the same one
        rows = [self.remote_event("e2", history.EVENT_PLAYABLE, "2026-11-07T13:00:00+03:00")]
        self.assertEqual(sync.pull_events(FakeClient(rows)), 1)
        with history.open_db(self.spotify_db) as db:
            self.assertFalse(history._write_event(db, "p1", "2026-11-07T14:00:00+03:00", history.EVENT_PLAYABLE,
                                                  {"uri": "track:1", "added_at": "2026-01-01T00:00:00Z"}))
            self.assertTrue(history._write_event(db, "p1", "2026-11-07T15:00:00+03:00", history.EVENT_UNPLAYABLE,
                                                 {"uri": "track:1", "added_at": "2026-01-01T00:00:00Z"}))

    def test_a_check_does_not_report_what_another_device_found(self):
        class Client:
            def __init__(self, tracks):
                self.tracks = tracks

            def playlist_name(self, playlist_id):
                return "Mix"

            def playlist_tracks(self, playlist_id):
                return [dict(track) for track in self.tracks]

        track = {"key": "k1", "uri": "track:1", "name": "Song", "artist": "A", "album": "",
                 "added_at": "2026-01-01T00:00:00Z", "added_by": "", "playable": True}
        other = {**track, "key": "k2", "uri": "track:2", "name": "Other"}
        history.check_playlist(Client([track, other]), "p1", self.spotify_db)
        sync.pull_events(FakeClient([self.remote_event("e1", history.EVENT_REMOVED, "2000-01-01T00:00:00Z")]))
        result = history.check_playlist(Client([other]), "p1", self.spotify_db)
        self.assertEqual(result["removed"], [])

    def test_settings_changed_here_are_sent_once(self):
        self.config.update(LANGUAGE="tr", THEME="dark", CLOSE_TO_TRAY=True)
        sync.settings_changed(self.config)
        client = FakeClient()
        self.assertTrue(sync.push_settings(client, "user"))
        [row] = client.sent
        self.assertEqual(row["data"], {"LANGUAGE": "tr", "THEME": "dark"})
        self.assertFalse(sync.push_settings(client, "user"))

    def test_settings_changed_later_elsewhere_are_taken(self):
        self.config.update(LANGUAGE="tr", THEME="dark", SETTINGS_CHANGED_AT="2026-11-07T10:00:00.000000Z")
        older = [{"data": {"LANGUAGE": "en"}, "changed_at": "2026-11-06T10:00:00.000000Z"}]
        self.assertFalse(sync.pull_settings(FakeClient(older)))
        self.assertEqual(self.config["LANGUAGE"], "tr")
        newer = [{"data": {"LANGUAGE": "en", "THEME": "dark"}, "changed_at": "2026-11-07T11:00:00.000000Z"}]
        self.assertTrue(sync.pull_settings(FakeClient(newer)))
        self.assertEqual((self.config["LANGUAGE"], self.config["THEME"]), ("en", "dark"))
        self.assertFalse(sync.push_settings(FakeClient(), "user"))


if __name__ == "__main__":
    unittest.main()
