import re
import unittest
from datetime import datetime
from pathlib import Path

from playlist_tracker.core import i18n
from playlist_tracker.core.text import format_date, format_length, track_label
from playlist_tracker.playlists import auto_check
from playlist_tracker.ui.stats import text as stats_text

PACKAGE = Path(__file__).resolve().parents[1] / "playlist_tracker"


class LanguageTestCase(unittest.TestCase):
    def setUp(self):
        i18n.set_language("en")
        self.addCleanup(i18n.set_language, None)


class TranslationTest(unittest.TestCase):
    def test_both_languages_have_the_same_texts(self):
        self.assertEqual(set(i18n.STRINGS["en"]) - set(i18n.STRINGS["tr"]), set())
        self.assertEqual(set(i18n.STRINGS["tr"]) - set(i18n.STRINGS["en"]), set())

    def test_every_text_the_code_asks_for_exists(self):
        missing = set()
        for path in PACKAGE.rglob("*.py"):
            if path.name == "i18n.py":
                continue
            for key in re.findall(r"""\bt\(\s*["']([a-z_]+\.[a-z_.]+)["']""", path.read_text(encoding="utf-8")):
                if key not in i18n.STRINGS["en"]:
                    missing.add(f"{path.name}: {key}")
        self.assertEqual(missing, set())

    def test_placeholders_match_between_languages(self):
        # English needs "a" or "an" in front of a word; Turkish has nothing like it
        english_only = {"article"}
        for key, english in i18n.STRINGS["en"].items():
            in_english = set(re.findall(r"{(\w+)", english))
            in_turkish = set(re.findall(r"{(\w+)", i18n.STRINGS["tr"][key]))
            self.assertEqual(in_english - english_only, in_turkish, key)

    def test_turkish_thousands_separator(self):
        i18n.set_language("tr")
        try:
            self.assertEqual(i18n.number(12345), "12.345")
        finally:
            i18n.set_language(None)
        i18n.set_language("en")
        self.assertEqual(i18n.number(12345), "12,345")
        i18n.set_language(None)


class TextTest(LanguageTestCase):
    def test_lengths(self):
        self.assertEqual(format_length(210_000), "3:30")
        self.assertEqual(format_length(59_999), "0:59")
        self.assertEqual(format_length(None), "")
        self.assertEqual(format_length(0), "")

    def test_track_label(self):
        self.assertEqual(track_label({"artist": "Slipknot", "name": "Snuff"}), "Slipknot - Snuff")
        self.assertEqual(track_label({"artist": "", "name": "Deleted video"}), "Deleted video")

    def test_dates(self):
        self.assertEqual(format_date(None), "")
        self.assertEqual(format_date("not a date"), "not a date")
        self.assertRegex(format_date("2026-11-04T12:00:00Z"), r"^2026-11-04 \d\d:00$")

    def test_durations_and_plays(self):
        self.assertEqual(stats_text.duration_text(45), "45 min")
        self.assertIn("2", stats_text.duration_text(125))
        self.assertNotEqual(stats_text.plays_text(1), stats_text.plays_text(2))
        # No listening time recorded: "0 min" is left out
        self.assertEqual(stats_text.summary_text("3 plays", minutes=0), "3 plays")

    def test_period_titles(self):
        week = stats_text.period_title("week", datetime(2026, 11, 2), datetime(2026, 11, 9))
        self.assertEqual(week, "2 – 8 November 2026")
        across = stats_text.period_title("week", datetime(2026, 12, 28), datetime(2027, 1, 4))
        self.assertIn("2026", across)
        self.assertIn("2027", across)
        self.assertEqual(stats_text.period_title("year", datetime(2026, 1, 1), datetime(2027, 1, 1)), "2026")

    def test_hour_buckets(self):
        buckets = stats_text.hour_buckets([0] * 23 + [4])
        self.assertEqual((len(buckets), buckets[23]["label"], buckets[23]["value"]), (24, "23", 4))


class SettingsTest(unittest.TestCase):
    def test_auto_check_interval(self):
        self.assertEqual(auto_check.interval_hours({}), 24)
        self.assertEqual(auto_check.interval_hours({"AUTO_CHECK": "6h"}), 6)
        self.assertEqual(auto_check.interval_hours({"AUTO_CHECK": "off"}), 0)
        self.assertEqual(auto_check.interval_hours({"AUTO_CHECK": "nonsense"}), 24)


if __name__ == "__main__":
    unittest.main()
