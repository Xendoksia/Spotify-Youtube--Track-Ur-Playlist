import tempfile
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from playlist_tracker.core import i18n
from playlist_tracker.core.errors import TrackerError
from playlist_tracker.playlists import auto_check, history, spotify, youtube


def track(key: str, playable: bool = True, name: str | None = None) -> dict:
    return {"key": key, "uri": f"uri:{key}", "name": name or key.upper(), "artist": "Artist", "album": "Album",
            "added_at": "2026-10-01T10:00:00Z", "added_by": "", "playable": int(playable)}


class FakeClient:
    """A playlist service whose playlist holds whatever the test puts in tracks."""

    def __init__(self):
        self.tracks: list[dict] = []

    def playlist_name(self, playlist_id):
        return "My list"

    def playlist_tracks(self, playlist_id):
        return [dict(t) for t in self.tracks]


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.addCleanup(self._folder.cleanup)
        self.db = Path(self._folder.name) / "history.db"
        self.client = FakeClient()

    def check(self):
        return history.check_playlist(self.client, "p1", self.db)


class CheckPlaylistTest(DatabaseTestCase):
    def test_first_check_records_a_snapshot_only(self):
        self.client.tracks = [track("a"), track("b", playable=False)]
        result = self.check()
        self.assertTrue(result["first_check"])
        self.assertEqual((result["added"], result["removed"]), ([], []))
        self.assertEqual([t["key"] for t in result["unavailable"]], ["b"])
        [event] = history.get_events(None, self.db)
        self.assertEqual(event["event"], history.EVENT_INITIAL)

    def test_changes_between_checks(self):
        self.client.tracks = [track("a"), track("b"), track("c", playable=False)]
        self.check()
        self.client.tracks = [track("a", playable=False), track("c"), track("d")]
        result = self.check()
        self.assertFalse(result["first_check"])
        self.assertEqual([t["key"] for t in result["added"]], ["d"])
        self.assertEqual([t["key"] for t in result["removed"]], ["b"])
        self.assertEqual([t["key"] for t in result["unplayable"]], ["a"])
        self.assertEqual([t["key"] for t in result["playable_again"]], ["c"])
        events = {(e["event"], e["name"]) for e in history.get_events(None, self.db)}
        self.assertTrue({(history.EVENT_ADDED, "D"), (history.EVENT_REMOVED, "B"),
                         (history.EVENT_UNPLAYABLE, "A"), (history.EVENT_PLAYABLE, "C")} <= events)

    def test_no_changes(self):
        self.client.tracks = [track("a")]
        self.check()
        result = self.check()
        self.assertFalse(any(result[k] for k in ("added", "removed", "unplayable", "playable_again")))

    def test_an_unplayable_track_keeps_its_last_known_name(self):
        # YouTube replaces the title of a deleted video with "Deleted video"
        self.client.tracks = [track("a", name="Real title")]
        self.check()
        self.client.tracks = [track("a", playable=False, name="Deleted video")]
        result = self.check()
        self.assertEqual(result["unplayable"][0]["name"], "Real title")

    def test_tracking_and_summaries(self):
        history.set_tracked("p1", "My list", True, self.db)
        history.set_tracked("p2", "Other", False, self.db)
        self.assertEqual([p["playlist_id"] for p in history.tracked_playlists(self.db)], ["p1"])
        self.client.tracks = [track("a"), track("b")]
        self.check()
        self.client.tracks = [track("a")]
        self.check()
        summary = history.playlist_summaries(self.db)["p1"]
        self.assertEqual(summary["tracks"], 1)
        self.assertEqual(summary["changes"], {history.EVENT_REMOVED: 1})

    def test_export_csv(self):
        self.client.tracks = [track("a")]
        self.check()
        self.client.tracks = []
        self.check()
        path = Path(self._folder.name) / "history.csv"
        self.assertEqual(history.export_csv(str(path), self.db), 2)
        self.assertIn("URI", path.read_text(encoding="utf-8-sig").splitlines()[0])


class PlaylistLinkTest(unittest.TestCase):
    def test_spotify_links(self):
        playlist_id = "37i9dQZF1DXcBWIGoYBM5M"
        for link in (f"https://open.spotify.com/playlist/{playlist_id}?si=abc", f"spotify:playlist:{playlist_id}",
                     playlist_id):
            self.assertEqual(spotify.parse_playlist_id(link), playlist_id)
        with self.assertRaises(TrackerError):
            spotify.parse_playlist_id("https://open.spotify.com/album/xyz")

    def test_youtube_links(self):
        playlist_id = "PLMNGvg2CMabcdefghijklmnop"
        self.assertEqual(youtube.parse_playlist_id(f"https://www.youtube.com/playlist?list={playlist_id}"),
                         playlist_id)
        self.assertEqual(youtube.parse_playlist_id(f"https://www.youtube.com/watch?v=x&list={playlist_id}"),
                         playlist_id)
        with self.assertRaises(TrackerError):
            youtube.parse_playlist_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")


class AutoCheckTest(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        i18n.set_language("en")
        self.addCleanup(i18n.set_language, None)

        class LoginRequired(TrackerError):
            pass

        self.service = types.SimpleNamespace(__name__="tests.spotify", DB_PATH=self.db, connect=lambda: self.client,
                                             LoginRequired=LoginRequired)
        self.notes: list[str] = []
        self.checked: list[tuple] = []
        patches = [mock.patch.object(auto_check, "SERVICES", (self.service,)),
                   mock.patch.object(auto_check, "load_config", lambda: {"AUTO_CHECK": "24h"})]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.checker = auto_check.AutoChecker(self.notes.append, lambda s, r: self.checked.append((s, r)))
        history.set_tracked("p1", "My list", True, self.db)

    def make_due(self):
        long_ago = (datetime.now().astimezone() - timedelta(days=2)).isoformat(timespec="seconds")
        with history.open_db(self.db) as db:
            db.execute("UPDATE playlists SET last_checked = ?", (long_ago,))

    def test_never_checked_playlist_is_checked_without_a_notification(self):
        self.client.tracks = [track("a")]
        self.checker.look()
        self.assertEqual(len(self.checked), 1)
        self.assertEqual(self.notes, [], "a first snapshot is nothing to report")

    def test_not_checked_again_before_the_interval(self):
        self.client.tracks = [track("a")]
        self.checker.look()
        self.checker.look()
        self.assertEqual(len(self.checked), 1)

    def test_removed_and_unplayable_tracks_are_reported(self):
        self.client.tracks = [track("a"), track("b"), track("c")]
        self.checker.look()
        self.make_due()
        self.client.tracks = [track("a", playable=False), track("c"), track("d")]
        self.checker.look()
        self.assertEqual(self.notes, ["Spotify\nMy list: 1 removed, 1 became unplayable"])

    def test_added_tracks_alone_are_not_reported(self):
        self.client.tracks = [track("a")]
        self.checker.look()
        self.make_due()
        self.client.tracks = [track("a"), track("b")]
        self.checker.look()
        self.assertEqual(self.notes, [])
        self.assertEqual(len(self.checked), 2)

    def test_logged_out_service_waits_and_stays_quiet(self):
        def logged_out():
            raise self.service.LoginRequired("log in")
        self.client.playlist_name = lambda playlist_id: logged_out()
        wait = self.checker.look()
        self.assertEqual((self.notes, self.checked), ([], []))
        self.assertGreater(wait, 0)
        self.assertIn("spotify", self.checker._failed)

    def test_turned_off(self):
        with mock.patch.object(auto_check, "load_config", lambda: {"AUTO_CHECK": "off"}):
            self.checker.look()
        self.assertEqual(self.checked, [])

    def test_long_notifications_are_shortened(self):
        results = [{"name": f"List {i}", "first_check": False, "removed": [{}], "unplayable": [],
                    "playable_again": []} for i in range(6)]
        lines = auto_check.notification("Spotify", results).splitlines()
        self.assertEqual(lines[0], "Spotify")
        self.assertEqual(len(lines), 1 + auto_check.NOTIFY_PLAYLISTS)
        self.assertEqual(lines[-1], "and 3 more playlists")


if __name__ == "__main__":
    unittest.main()


class PlaylistCardsTest(DatabaseTestCase):
    """The playlists page of the desktop app (api/playlists.py)."""

    def setUp(self):
        super().setUp()
        import dataclasses
        from playlist_tracker.api import playlists as api
        from playlist_tracker.playlists.services import SPOTIFY
        service = dataclasses.replace(SPOTIFY, db_path=self.db)
        for patch in (mock.patch.object(api, "SERVICES", (service,)), mock.patch.object(api, "load_config", dict)):
            patch.start()
            self.addCleanup(patch.stop)
        self.api = api

    def test_a_playlist_added_by_link_keeps_its_card_untracked_after_a_restart(self):
        history.set_tracked("p1", "My list", True, self.db)
        # A new run has loaded nothing from the account: the playlist is known only from the database
        page = self.api.Playlists(lambda *args, **kwargs: None).toggle("Spotify", "p1")
        self.assertEqual([(card["id"], card["tracked"]) for card in page["playlists"]], [("p1", False)])
        page = self.api.Playlists(lambda *args, **kwargs: None).toggle("Spotify", "p1")
        self.assertEqual([(card["id"], card["tracked"]) for card in page["playlists"]], [("p1", True)])
