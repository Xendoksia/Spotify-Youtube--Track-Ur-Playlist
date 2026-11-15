import unittest
from datetime import datetime

from playlist_tracker.api import sections
from playlist_tracker.core import i18n


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


if __name__ == "__main__":
    unittest.main()
