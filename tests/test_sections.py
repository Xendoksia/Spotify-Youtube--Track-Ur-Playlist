import unittest
from datetime import datetime, timedelta

from playlist_tracker.api import sections
from playlist_tracker.core import i18n
from playlist_tracker.music import listening
from tests.test_listening import ListeningTestCase


class GenreShiftBucketTest(unittest.TestCase):
    def setUp(self):
        i18n.set_language("en")
        self.addCleanup(i18n.set_language, None)

    def labels(self, period, start, end):
        keys = sections.shift_buckets(period, start.astimezone(), end.astimezone(), None, False)
        return [sections.shift_label(period, key, False) for key in keys]

    def test_a_past_week_has_a_bucket_per_day(self):
        self.assertEqual(self.labels("week", datetime(2026, 10, 26), datetime(2026, 11, 2)),
                         "Mon,Tue,Wed,Thu,Fri,Sat,Sun".split(","))

    def test_weeks_of_a_month_start_on_monday_or_the_1st(self):
        self.assertEqual(self.labels("month", datetime(2026, 10, 1), datetime(2026, 11, 1)),
                         ["1 Oct", "5 Oct", "12 Oct", "19 Oct", "26 Oct"])

    def test_a_year_has_a_bucket_per_month(self):
        labels = self.labels("year", datetime(2025, 1, 1), datetime(2026, 1, 1))
        self.assertEqual(len(labels), 12)
        self.assertEqual(labels[0], "Jan")

    def test_all_time_past_three_years_goes_by_year(self):
        self.assertEqual(sections.shift_bucket("all", "2024-05-17", True), "2024")
        self.assertEqual(sections.shift_label("all", "2024", True), "2024")

    def test_a_column_splits_into_the_top_genres_and_other(self):
        column = sections.shift_column("2026", {"metalcore": 3, "rock": 1, "jazz": 1}, ["metalcore", "rock"])
        self.assertEqual(column["segments"], [{"series": 0, "share": 0.6}, {"series": 1, "share": 0.2},
                                              {"series": "other", "share": 0.2}])
        self.assertIn("Metalcore: 60%", column["tooltip"])
        self.assertIn("Other: 20%", column["tooltip"])

    def test_an_empty_bucket_has_no_segments(self):
        self.assertEqual(sections.shift_column("Oct", {}, [])["segments"], [])

    def test_share(self):
        self.assertEqual((sections.share(1, 3), sections.share(0, 0)), (33, 0))


class YearAgoTodayTest(ListeningTestCase):
    def setUp(self):
        super().setUp()
        i18n.set_language("en")
        self.addCleanup(i18n.set_language, None)

    def store(self, name, at: datetime):
        played = {"artist": "A", "name": name, "album": "Album", "played_at": listening.to_utc(at), "ms_played": 200_000}
        with listening.open_db(self.db) as db:
            listening._insert(db, played, "local")

    def test_nothing_shows_without_plays_on_that_day(self):
        now = datetime(2026, 11, 22, 15).astimezone()
        self.store("Song", now - timedelta(days=1))
        self.store("Song", datetime(2025, 11, 21, 23, 59).astimezone())
        self.store("Song", datetime(2025, 11, 23, 0, 1).astimezone())
        self.assertIsNone(sections.year_ago_today(now, self.db))

    def test_the_same_day_a_year_back_with_its_top_tracks(self):
        now = datetime(2026, 11, 22, 9).astimezone()
        self.store("Song", datetime(2025, 11, 22, 8).astimezone())
        self.store("Song", datetime(2025, 11, 22, 21).astimezone())
        self.store("Other", datetime(2025, 11, 22, 23, 50).astimezone())
        card = sections.year_ago_today(now, self.db)
        self.assertEqual(card["summary"], "22 November 2025  ·  3 plays  ·  10 min")
        self.assertEqual([track["title"] for track in card["tracks"]], ["Song  ·  A", "Other  ·  A"])
        self.assertEqual(card["tracks"][0]["plays"], "2 plays")


if __name__ == "__main__":
    unittest.main()
