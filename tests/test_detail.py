import unittest

from playlist_tracker.api import detail
from playlist_tracker.core import i18n


def hours(**counts: int) -> list[int]:
    """24 hours of plays from counts like h18=4."""
    return [counts.get(f"h{hour}", 0) for hour in range(24)]


class DayCurveTest(unittest.TestCase):
    def setUp(self):
        i18n.set_language("en")
        self.addCleanup(i18n.set_language, None)

    def test_no_plays_say_nothing(self):
        self.assertEqual(detail.day_curve([0] * 24), {"peak": None, "peak_text": "", "summary": ""})

    def test_the_peak_and_the_part_of_the_day_with_most_plays(self):
        curve = detail.day_curve(hours(h18=5, h20=3, h9=1))
        self.assertEqual((curve["peak"], curve["peak_text"]), (18, "Most around 18:00"))
        self.assertEqual(curve["summary"], "You play it mostly in the evening")

    def test_the_night_runs_from_midnight_to_six(self):
        self.assertEqual(detail.day_part(hours(h0=2, h5=2, h6=1)), "night")

    def test_an_even_spread_is_not_called_mostly(self):
        self.assertIsNone(detail.day_part(hours(h1=1, h7=1, h13=1, h19=1)))
        self.assertEqual(detail.day_curve(hours(h1=1, h7=1, h13=1, h19=1))["summary"],
                         "You play it all through the day")


if __name__ == "__main__":
    unittest.main()
