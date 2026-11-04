import unittest
from datetime import datetime

from playlist_tracker.core import i18n
from playlist_tracker.ui.stats.sections import GenreShift, share


class GenreShiftBucketTest(unittest.TestCase):
    def setUp(self):
        i18n.set_language("en")
        self.addCleanup(i18n.set_language, None)
        # The bucketing needs no window
        self.shift = GenreShift.__new__(GenreShift)
        self.shift._yearly = False

    def keys(self, period, start, end):
        return self.shift._bucket_keys(period, start.astimezone(), end.astimezone(), [])

    def test_a_past_week_has_a_bucket_per_day(self):
        keys = self.keys("week", datetime(2026, 10, 26), datetime(2026, 11, 2))
        self.assertEqual([self.shift._label("week", k) for k in keys], "Mon,Tue,Wed,Thu,Fri,Sat,Sun".split(","))

    def test_weeks_of_a_month_start_on_monday_or_the_1st(self):
        keys = self.keys("month", datetime(2026, 10, 1), datetime(2026, 11, 1))
        self.assertEqual([self.shift._label("month", k) for k in keys],
                         ["1 Oct", "5 Oct", "12 Oct", "19 Oct", "26 Oct"])

    def test_a_year_has_a_bucket_per_month(self):
        keys = self.keys("year", datetime(2025, 1, 1), datetime(2026, 1, 1))
        self.assertEqual(len(keys), 12)
        self.assertEqual(self.shift._label("year", keys[0]), "Jan")

    def test_all_time_past_three_years_goes_by_year(self):
        self.shift._yearly = True
        self.assertEqual(self.shift._bucket("all", "2024-05-17"), "2024")
        self.assertEqual(self.shift._label("all", "2024"), "2024")

    def test_a_column_splits_into_the_top_genres_and_other(self):
        column = self.shift._column("year", "2026-11", {"metalcore": 3, "rock": 1, "jazz": 1}, ["metalcore", "rock"],
                                    {"metalcore": "#111111", "rock": "#222222"}, "#999999")
        self.assertEqual(column["segments"], [(0.6, "#111111"), (0.2, "#222222"), (0.2, "#999999")])
        self.assertIn("Metalcore: 60%", column["tooltip"])
        self.assertIn("Other: 20%", column["tooltip"])

    def test_an_empty_bucket_has_no_segments(self):
        self.assertEqual(self.shift._column("year", "2026-10", {}, [], {}, "#999999")["segments"], [])

    def test_share(self):
        self.assertEqual((share(1, 3), share(0, 0)), (33, 0))


if __name__ == "__main__":
    unittest.main()
