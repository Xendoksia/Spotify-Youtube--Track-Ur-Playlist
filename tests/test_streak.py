from datetime import date

from playlist_tracker.music import listening
from tests.test_listening import ListeningTestCase


class StreakTest(ListeningTestCase):
    def on(self, *days: int):
        # Noon UTC stays on the same local day in Turkey and most places
        for day in days:
            self.play("A", f"Song {day}", f"2026-11-{day:02d} 12:00")

    def streak(self) -> dict:
        return listening.streak(date(2026, 11, 21), db_path=self.db)

    def test_runs_back_from_today_or_from_yesterday_while_today_has_no_play(self):
        self.on(18, 19, 20, 21)
        streak = self.streak()
        self.assertEqual((streak["current"], streak["today"], streak["start"]), (4, True, date(2026, 11, 18)))
        self.assertEqual(streak["recent"], [False] * 10 + [True] * 4)

    def test_yesterday_keeps_the_streak_until_the_day_ends(self):
        self.on(19, 20)
        streak = self.streak()
        self.assertEqual((streak["current"], streak["today"]), (2, False))
        self.assertIsNone(listening.streak_special(streak))

    def test_marked_only_on_a_new_title_or_the_day_a_record_is_first_beaten(self):
        self.on(1, 2, 3, 19, 20, 21)
        self.assertEqual(listening.streak_special(self.streak()), "level_up")
        self.on(18)
        self.assertEqual(listening.streak_special(self.streak()), "record")
        self.on(17)
        self.assertIsNone(listening.streak_special(self.streak()))

    def test_titles_come_at_3_7_14_21_30_50_100_and_365_days(self):
        self.assertEqual([listening.streak_level(d) for d in (0, 2, 3, 7, 13, 21, 49, 100, 364, 365, 400)],
                         [0, 0, 1, 2, 2, 4, 5, 7, 7, 8, 8])
        self.assertEqual([listening.streak_next_level(d) for d in (0, 3, 13, 50, 365)], [3, 7, 14, 100, None])
        self.assertAlmostEqual(listening.streak_place(10), 1 + 3 / 7)
        self.assertEqual((listening.streak_place(0), listening.streak_place(400)), (0.0, 7.0))
