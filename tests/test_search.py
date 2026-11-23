import unittest

from playlist_tracker.api import search


class FoldTest(unittest.TestCase):
    def test_turkish_letters_and_accents_match_plain_ones(self):
        self.assertEqual(search.fold("Göksel"), "goksel")
        self.assertEqual(search.fold("  IŞIL  Ayman "), "isil ayman")
        self.assertEqual(search.fold("Beyoncé"), "beyonce")

    def test_every_word_must_match_and_a_start_ranks_first(self):
        words = ["linkin", "numb"]
        self.assertIsNone(search._score("linkin numb", words, "In The End", "Linkin Park"))
        self.assertEqual(search._score("numb", ["numb"], "Numb", "Linkin Park"), 0)
        self.assertEqual(search._score("end", ["end"], "In The End", "Linkin Park"), 1)
        self.assertEqual(search._score("park", ["park"], "Numb", "Linkin Park"), 2)

    def test_short_queries_find_nothing(self):
        self.assertEqual(search.search("a")["tracks"], [])
