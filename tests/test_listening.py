import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playlist_tracker.music import listening


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


class ListeningTestCase(unittest.TestCase):
    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.db = Path(self._folder.name) / "listening.db"

    def tearDown(self):
        self._folder.cleanup()

    def play(self, artist: str, name: str, at: str, ms: int = 200_000, album: str = "Album", source: str = "local"):
        """Store a play at a UTC time ("2026-11-02 10:00")."""
        played = {"artist": artist, "name": name, "album": album, "played_at": listening.to_utc(utc(at)),
                  "ms_played": ms}
        with listening.open_db(self.db) as db:
            return listening._insert(db, played, source)


class StorageTest(ListeningTestCase):
    def test_record_and_update_local(self):
        play_id = listening.record_local({"artist": "Slipknot", "name": "Snuff", "album": "All Hope Is Gone",
                                          "played_at": listening.to_utc(utc("2026-11-02 10:00")), "ms": 30_000},
                                         self.db)
        self.assertIsNotNone(play_id)
        listening.update_local(play_id, 270_000, self.db)
        [stored] = listening.recent_plays(db_path=self.db)
        self.assertEqual(stored["ms_played"], 270_000)
        self.assertEqual(stored["track_key"], "slipknot|snuff")
        self.assertEqual(stored["source"], "local")

    def test_same_play_twice_from_one_source_is_kept_once(self):
        self.assertTrue(self.play("A", "Song", "2026-11-02 10:00"))
        self.assertFalse(self.play("A", "Song", "2026-11-02 10:00"))

    def test_same_play_from_another_source_is_not_counted_again(self):
        self.assertTrue(self.play("A", "Song", "2026-11-02 10:00", source="local"))
        # Within the song's length plus three minutes: the same listen seen by another source
        self.assertFalse(self.play("A", "Song", "2026-11-02 10:04", source="spotify"))
        # Much later it is a new listen
        self.assertTrue(self.play("A", "Song", "2026-11-02 12:00", source="spotify"))

    def test_keys_ignore_case_and_spaces(self):
        self.assertEqual(listening.key("  Three  Days GRACE "), "three days grace")

    def test_utc_round_trip(self):
        moment = utc("2026-11-02 10:30")
        self.assertEqual(listening.from_utc(listening.to_utc(moment)), moment)


class PeriodTest(unittest.TestCase):
    def test_week_starts_on_monday(self):
        start, end = listening.period_range("week", now=datetime(2026, 11, 5, 15, 0))  # a Thursday
        self.assertEqual((start.year, start.month, start.day, start.hour), (2026, 11, 2, 0))
        self.assertEqual(end - start, timedelta(weeks=1))

    def test_previous_week(self):
        start, _ = listening.period_range("week", 1, now=datetime(2026, 11, 5, 15, 0))
        self.assertEqual((start.month, start.day), (10, 26))

    def test_month_offset_crosses_the_year(self):
        start, end = listening.period_range("month", 1, now=datetime(2026, 1, 15))
        self.assertEqual((start.year, start.month, start.day), (2025, 12, 1))
        self.assertEqual((end.year, end.month, end.day), (2026, 1, 1))

    def test_december_ends_in_january(self):
        start, end = listening.period_range("month", now=datetime(2026, 12, 31, 23, 0))
        self.assertEqual((start.month, end.year, end.month), (12, 2027, 1))

    def test_year(self):
        start, end = listening.period_range("year", 2, now=datetime(2026, 6, 1))
        self.assertEqual((start.year, start.month, start.day, end.year), (2024, 1, 1, 2025))

    def test_all_time_reaches_past_now(self):
        now = datetime(2026, 11, 5, 15, 0)
        start, end = listening.period_range("all", now=now)
        self.assertLess(start.year, 2001)
        self.assertGreater(end, now.astimezone())


class StatisticsTest(ListeningTestCase):
    def setUp(self):
        super().setUp()
        self.start, self.end = utc("2026-11-02 00:00"), utc("2026-11-09 00:00")
        # Before the period: one play of Snuff and Bad Omens heard first
        self.play("Slipknot", "Snuff", "2026-10-20 10:00")
        self.play("Bad Omens", "Specter", "2026-10-21 10:00")
        # In the period
        for day in (2, 3, 4):
            self.play("Slipknot", "Snuff", f"2026-11-0{day} 10:00", ms=270_000, album="All Hope Is Gone")
        self.play("Slipknot", "Psychosocial", "2026-11-03 11:00", ms=240_000, album="All Hope Is Gone")
        self.play("Evanescence", "Lithium", "2026-11-04 12:00", ms=220_000, album="The Open Door")
        self.play("Evanescence", "Lithium", "2026-11-05 12:00", ms=220_000, album="The Open Door")

    def test_summary(self):
        totals = listening.summary(self.start, self.end, self.db)
        self.assertEqual(totals["plays"], 6)
        self.assertEqual(totals["tracks"], 3)
        self.assertEqual(totals["artists"], 2)
        self.assertEqual(totals["minutes"], (3 * 270_000 + 240_000 + 2 * 220_000) // 60_000)

    def test_summary_by_day(self):
        days = listening.summary_by(self.start, self.end, "day", self.db)
        # Plays at 10:00-12:00 UTC fall on the same local day in any zone within ±10 hours
        self.assertEqual(sum(day["plays"] for day in days.values()), 6)
        third = days["2026-11-03"]
        self.assertEqual((third["plays"], third["tracks"], third["artists"]), (2, 2, 1))
        self.assertEqual(listening.summary_by(self.start, self.end, "month", self.db)["2026-11"]["tracks"], 3)

    def test_top_tracks_and_artists(self):
        tracks = listening.top_tracks(self.start, self.end, db_path=self.db)
        self.assertEqual([t["key"] for t in tracks], ["slipknot|snuff", "evanescence|lithium", "slipknot|psychosocial"])
        self.assertEqual(tracks[0]["plays"], 3)
        artists = listening.top_artists(self.start, self.end, db_path=self.db)
        self.assertEqual([(a["key"], a["plays"], a["tracks"]) for a in artists],
                         [("slipknot", 4, 2), ("evanescence", 2, 1)])

    def test_equal_plays_go_to_the_longer_listened(self):
        self.play("Linkin Park", "Short", "2026-11-05 13:00", ms=90_000)
        self.play("Linkin Park", "Short", "2026-11-05 14:00", ms=90_000)
        tracks = listening.top_tracks(self.start, self.end, db_path=self.db)
        self.assertEqual([t["key"] for t in tracks][1:3], ["evanescence|lithium", "linkin park|short"])
        ranks = listening.ranks(self.start, self.end, "track_key", self.db)
        self.assertLess(ranks["evanescence|lithium"], ranks["linkin park|short"])

    def test_top_tracks_of_one_artist_and_album(self):
        only = listening.top_tracks(self.start, self.end, artist_key="evanescence", db_path=self.db)
        self.assertEqual([t["key"] for t in only], ["evanescence|lithium"])
        album = listening.album_key("slipknot", "all hope is gone")
        on_album = listening.top_tracks(self.start, self.end, album=album, db_path=self.db)
        self.assertEqual({t["key"] for t in on_album}, {"slipknot|snuff", "slipknot|psychosocial"})

    def test_top_albums_leave_out_plays_without_album(self):
        self.play("Nobody", "Single", "2026-11-06 09:00", album="")
        albums = listening.top_albums(self.start, self.end, db_path=self.db)
        self.assertEqual([(a["album_lower"], a["plays"]) for a in albums],
                         [("all hope is gone", 4), ("the open door", 2)])

    def test_ranks(self):
        ranks = listening.ranks(self.start, self.end, "artist_key", self.db)
        self.assertEqual(ranks, {"slipknot": 1, "evanescence": 2})
        with self.assertRaises(ValueError):
            listening.ranks(self.start, self.end, "name; DROP TABLE listens", self.db)

    def test_new_tracks_and_artists_are_first_heard_in_the_period(self):
        self.assertEqual({t["key"] for t in listening.new_tracks(self.start, self.end, self.db)},
                         {"slipknot|psychosocial", "evanescence|lithium"})
        self.assertEqual({a["key"] for a in listening.new_artists(self.start, self.end, self.db)}, {"evanescence"})

    def test_heard_before(self):
        self.assertEqual(listening.heard_before(self.start, "track_key", self.db),
                         {"slipknot|snuff", "bad omens|specter"})

    def test_forgotten(self):
        # Played three times, last on 4 November: forgotten 30 days later, not before
        self.assertEqual(listening.forgotten(now=utc("2026-11-20 00:00"), db_path=self.db), [])
        forgotten = listening.forgotten(now=utc("2026-12-10 00:00"), db_path=self.db)
        self.assertEqual([t["key"] for t in forgotten], ["slipknot|snuff"])

    def test_detail_of_a_track_artist_and_album(self):
        track = listening.detail("track_key", "slipknot|snuff", self.db)
        self.assertEqual((track["plays"], track["name"]), (4, "Snuff"))
        artist = listening.detail("artist_key", "slipknot", self.db)
        self.assertEqual((artist["plays"], artist["tracks"]), (5, 2))
        album = listening.detail(listening.ALBUM, listening.album_key("evanescence", "the open door"), self.db)
        self.assertEqual(album["plays"], 2)
        self.assertIsNone(listening.detail("track_key", "nobody|nothing", self.db))

    def test_timeline_and_hours_add_up(self):
        days = listening.timeline(self.start, self.end, "day", db_path=self.db)
        self.assertEqual(sum(days.values()), 6)
        months = listening.timeline(utc("2026-10-01 00:00"), self.end, "month", db_path=self.db)
        self.assertEqual(sum(months.values()), 8)
        hours = listening.hours(self.start, self.end, db_path=self.db)
        self.assertEqual((len(hours), sum(hours)), (24, 6))
        one_track = listening.hours(self.start, self.end, "track_key", "evanescence|lithium", self.db)
        self.assertEqual(sum(one_track), 2)

    def test_diversity(self):
        result = listening.diversity(self.start, self.end, self.db)
        self.assertEqual((result["plays"], result["tracks"], result["artists"]), (6, 3, 2))
        self.assertEqual(result["top5"], 6, "only two artists, so the top five hold every play")
        # Snuff was heard before the period; Psychosocial and both Lithium plays are new
        self.assertEqual(result["new"], 3)

    def test_milestones(self):
        for day in range(1, 11):
            self.play("Bad Omens", "Specter", f"2026-11-{day + 10:02d} 09:00")
        found = listening.milestones(self.db)
        kinds = [(m["kind"], m.get("key"), m["count"]) for m in found]
        # Ten more plays of Specter (eleven in all with the one in October): its 10th play and the artist's
        self.assertIn(("track", "bad omens|specter", 10), kinds)
        self.assertIn(("artist", "bad omens", 10), kinds)
        # Bad Omens now has eleven plays, so the day it was first heard counts
        met = next(m for m in found if m["kind"] == "met")
        self.assertEqual((met["key"], met["at"]), ("bad omens", listening.to_utc(utc("2026-10-21 10:00"))))
        self.assertEqual(found[-1]["kind"], "start")
        self.assertEqual([m["at"] for m in found], sorted((m["at"] for m in found), reverse=True))
        # Nothing new: the same list from the cache; a new play: worked out again
        self.assertIs(listening.milestones(self.db), found)
        self.play("Bad Omens", "Specter", "2026-11-25 09:00")
        self.assertIsNot(listening.milestones(self.db), found)

    def test_next_total_step(self):
        self.assertEqual(listening.next_total_step(self.db), (100, 92))

    def test_plays_without_length_are_filled(self):
        self.play("Old", "Song", "2026-11-01 08:00", ms=None)
        self.play("Old", "Song", "2026-11-01 18:00", ms=180_000)
        [missing] = listening.plays_without_length(self.db)
        self.assertEqual((missing["key"], missing["known_ms"]), ("old|song", 180_000))
        listening.set_missing_length("old|song", 180_000, self.db)
        self.assertEqual(listening.plays_without_length(self.db), [])


if __name__ == "__main__":
    unittest.main()


class RankHistoryTest(ListeningTestCase):
    def test_a_track_climbs_as_it_is_played(self):
        self.play("Slipknot", "Snuff", "2026-11-02 10:00")
        self.play("Slipknot", "Snuff", "2026-11-02 11:00")
        self.play("Evanescence", "Lithium", "2026-11-03 10:00")
        self.play("Evanescence", "Lithium", "2026-11-04 10:00")
        self.play("Evanescence", "Lithium", "2026-11-04 11:00")
        ends = [utc("2026-11-03 00:00"), utc("2026-11-04 00:00"), utc("2026-11-05 00:00")]
        places = listening.rank_history("evanescence|lithium", ends, db_path=self.db)
        # Not played yet, then behind Snuff, then ahead of it
        self.assertEqual(places, [None, (2, 2, 1), (1, 2, 3)])
