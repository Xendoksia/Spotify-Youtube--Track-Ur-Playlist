import unittest

from playlist_tracker.api.wrapped import genre_family, genre_message


class GenreWordsTest(unittest.TestCase):
    def test_families_follow_the_words_in_the_names(self):
        self.assertEqual(genre_family("Metalcore"), "metal")
        self.assertEqual(genre_family("post-grunge"), "rock")
        self.assertEqual(genre_family("synth-pop"), "electronic")
        self.assertEqual(genre_family("Turkish rock"), "turkish")
        self.assertEqual(genre_family("polka"), "other")

    def test_the_two_biggest_genres_get_a_word_of_their_own(self):
        self.assertEqual(genre_message("Metalcore", "Nu metal"), "wrapped.genre.combo.metalcore_numetal")
        self.assertEqual(genre_message("nu metal", "metalcore"), "wrapped.genre.combo.metalcore_numetal")
        self.assertEqual(genre_message("Hard rock", "Pop"), "wrapped.genre.combo.pop_rock")
        self.assertEqual(genre_message("deathcore", "thrash metal"), "wrapped.genre.combo.metal_metal")
        self.assertEqual(genre_message("jazz", "folk"), "wrapped.genre.say.jazz")
        self.assertEqual(genre_message("Pop", None), "wrapped.genre.say.pop")


if __name__ == "__main__":
    unittest.main()
