import unittest
from unittest import mock

from playlist_tracker.music import artist_info, styles


class StylesTest(unittest.TestCase):
    def test_regional_pop_is_pop_and_repeats_go(self):
        self.assertEqual(styles.styles_of(["Europop", "Ballad", "K-Pop", "Euro House"]),
                         ["Pop", "Ballad", "Euro House"])
        self.assertEqual(styles.plain("Synth-pop"), "Synth-pop")

    def test_the_album_first_then_a_single_of_the_track(self):
        calls = []

        def search(**params):
            calls.append((params["release_title"], params["type"]))
            if params["release_title"] == "Somebody Told Me" and params["type"] == "release":
                return [{"title": "Other Band - Somebody Told Me", "style": ["Indie Rock"]},
                        {"title": "Motionless In White - Somebody Told Me", "style": ["Metalcore"]}]
            return []

        with mock.patch.object(styles, "_search", search):
            found = styles._look_up("Motionless In White", "Somebody Told Me (Single)", "Somebody Told Me")
        self.assertEqual(found, {"styles": ["Metalcore"]})
        self.assertEqual(calls, [("Somebody Told Me", "master"), ("Somebody Told Me", "release")])

    def test_version_notes_are_left_out_of_the_album(self):
        seen = []

        def search(**params):
            seen.append(params["release_title"])
            return [{"title": "Metallica - ...And Justice For All", "style": ["Thrash", "Heavy Metal"]}]

        with mock.patch.object(styles, "_search", search):
            found = styles._look_up("Metallica", "...And Justice For All (Remastered Deluxe Box Set)", "One - Remastered")
        self.assertEqual(seen, ["...And Justice For All"])
        self.assertEqual(found["styles"], ["Thrash", "Heavy Metal"])

    def test_discogs_numbers_and_punctuation(self):
        with mock.patch.object(styles, "_search", return_value=[
                {"title": "Seether (2) - ...And Justice", "style": ["Post-Grunge"]}]):
            self.assertEqual(styles._look_up("Seether", "…And Justice", "Song"), {"styles": ["Post-Grunge"]})


class GenreTest(unittest.TestCase):
    release = {"artist": "Band", "artist_key": "band", "album": "Album", "name": "Song", "plays": 3}

    def test_the_first_style_wins_over_the_artist(self):
        with mock.patch.object(styles, "cached", return_value=["Metalcore", "Goth Rock"]), \
             mock.patch.object(artist_info, "cached", return_value={"genres": ["rock"]}):
            self.assertEqual(styles.genre(self.release), ("Metalcore", False))

    def test_without_styles_the_artist_genre(self):
        with mock.patch.object(styles, "cached", return_value=None), \
             mock.patch.object(artist_info, "cached", return_value={"genres": ["pop"]}):
            self.assertEqual(styles.genre(self.release), ("pop", False))

    def test_still_looking_up(self):
        with mock.patch.object(styles, "request", return_value=None), \
             mock.patch.object(styles, "waiting", return_value=True):
            self.assertEqual(styles.genre(self.release, lambda: None), (None, True))


if __name__ == "__main__":
    unittest.main()
