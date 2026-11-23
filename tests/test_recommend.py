from datetime import timedelta
from pathlib import Path
from unittest import mock

from playlist_tracker.api import recommend as recommend_api
from playlist_tracker.core import i18n
from playlist_tracker.music import recommend
from tests.test_listening import ListeningTestCase, utc

NOW = utc("2026-11-20 12:00")


class FakeDeezer:
    """Answers the Deezer addresses recommend.py asks for from a small catalog, counting the requests."""

    def __init__(self, artists: dict[str, tuple[int, int]], related: dict[int, list[tuple[int, str]]]):
        self.artists = artists  # name → (id, fans)
        self.related = related  # id → [(id, name)]
        self.requests = 0

    def __call__(self, url: str) -> dict:
        self.requests += 1
        if "/search/artist?" in url:
            return {"data": [{"id": artist_id, "name": name, "nb_fan": fans}
                             for name, (artist_id, fans) in self.artists.items()]}
        artist_id = int(url.split("/artist/")[1].split("/")[0])
        if "/related" in url:
            return {"data": [{"id": i, "name": n, "nb_fan": 100} for i, n in self.related.get(artist_id, [])]}
        return {"data": [{"title": f"Song {artist_id}", "artist": {"name": f"Artist {artist_id}"},
                          "album": {"title": "Album"}, "link": f"https://www.deezer.com/track/{artist_id}"}]}


class RecommendTestCase(ListeningTestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(recommend, "CACHE_PATH", Path(self._folder.name) / "related.json")
        patcher.start()
        self.addCleanup(patcher.stop)
        recommend._cache = None
        self.addCleanup(setattr, recommend, "_cache", None)

    def plays(self, artist: str, count: int, days_ago: int):
        for n in range(count):
            moment = NOW - timedelta(days=days_ago, minutes=n * 5)
            self.play(artist, f"Track {n}", moment.strftime("%Y-%m-%d %H:%M"))


class SeedsTest(RecommendTestCase):
    def test_recent_plays_weigh_more(self):
        self.plays("Metallica", 4, days_ago=60)
        self.plays("Skillet", 2, days_ago=0)
        seeds = recommend.seeds(NOW, db_path=self.db)
        self.assertEqual([s["name"] for s in seeds], ["Skillet", "Metallica"])
        self.assertAlmostEqual(seeds[1]["weight"], 1.0, places=2)  # four plays two half lives ago

    def test_a_collaboration_counts_for_each_known_artist(self):
        self.plays("Şanışer", 1, days_ago=0)
        self.plays("Şanışer, Sena Şener", 1, days_ago=0)
        self.plays("Sena Şener", 1, days_ago=0)
        names = {s["name"]: s["weight"] for s in recommend.seeds(NOW, db_path=self.db)}
        self.assertEqual(set(names), {"Şanışer", "Sena Şener"})
        self.assertAlmostEqual(names["Şanışer"], 2.0, places=2)


class ScoreTest(RecommendTestCase):
    def test_an_artist_related_to_several_seeds_wins_and_played_ones_are_left_out(self):
        seeds = [{"key": "a", "name": "A", "weight": 2.0}, {"key": "b", "name": "B", "weight": 1.0}]
        related = {"a": [{"id": 1, "name": "Played", "fans": 9}, {"id": 2, "name": "Only A", "fans": 9},
                         {"id": 3, "name": "Both", "fans": 9}],
                   "b": [{"id": 3, "name": "Both", "fans": 9}]}
        ranked = recommend.score(seeds, related, {"played"})
        self.assertEqual([r["name"] for r in ranked], ["Both", "Only A"])
        self.assertEqual(ranked[0]["because"], ["A", "B"])

    def test_a_much_played_seed_does_not_fill_every_place(self):
        seeds = [{"key": "a", "name": "A", "weight": 3.0}, {"key": "b", "name": "B", "weight": 1.0}]
        related = {"a": [{"id": i, "name": f"A{i}", "fans": 9} for i in range(1, 4)],
                   "b": [{"id": 9, "name": "B9", "fans": 9}]}
        ranked = [r["name"] for r in recommend.score(seeds, related, set())]
        # A's second pick is worth 3 × 0.95 × 0.5 = 1.4 and its third 3 × 0.9 × 0.25 = 0.7, below B's 1.0
        self.assertEqual(ranked, ["A1", "A2", "B9", "A3"])

    def test_names_match_without_accents_or_turkish_letters(self):
        self.assertEqual(recommend.fold("Göksel"), recommend.fold("Goksel"))
        self.assertEqual(recommend.fold("IŞIL"), "isil")


class SuggestionsTest(RecommendTestCase):
    def deezer(self):
        return FakeDeezer({"Goksel": (10, 5000), "Göksel": (11, 3)}, {10: [(20, "Sertab Erener"), (21, "Göksel")]})

    def test_suggestions_use_the_most_followed_same_named_artist_and_skip_the_played_one(self):
        self.plays("Göksel", 3, days_ago=1)
        deezer = self.deezer()
        found = recommend.suggestions(fetch=True, get=deezer, now=NOW, db_path=self.db)
        self.assertTrue(found["complete"])
        [artist] = found["artists"]
        self.assertEqual(artist["name"], "Sertab Erener")
        self.assertEqual(artist["because"], ["Göksel"])
        self.assertEqual(artist["tracks"][0]["title"], "Song 20")

    def test_lookups_are_cached(self):
        self.plays("Göksel", 3, days_ago=1)
        deezer = self.deezer()
        recommend.suggestions(fetch=True, get=deezer, now=NOW, db_path=self.db)
        asked = deezer.requests
        recommend._cache = None  # read back from the file
        found = recommend.suggestions(fetch=False, get=deezer, now=NOW, db_path=self.db)
        self.assertEqual(deezer.requests, asked)
        self.assertTrue(found["complete"])
        self.assertEqual(found["artists"][0]["name"], "Sertab Erener")

    def test_without_fetch_nothing_is_asked_and_it_is_incomplete(self):
        self.plays("Göksel", 3, days_ago=1)
        deezer = self.deezer()
        found = recommend.suggestions(fetch=False, get=deezer, now=NOW, db_path=self.db)
        self.assertEqual((deezer.requests, found["artists"], found["complete"]), (0, [], False))

    def test_an_unknown_artist_is_remembered_as_missing(self):
        self.plays("Nobody", 2, days_ago=1)
        deezer = FakeDeezer({}, {})
        found = recommend.suggestions(fetch=True, get=deezer, now=NOW, db_path=self.db)
        self.assertEqual((found["artists"], found["complete"]), ([], True))
        self.assertTrue(recommend._load()["artists"]["nobody"]["missing"])


class BecauseTextTest(RecommendTestCase):
    def setUp(self):
        super().setUp()
        i18n.set_language("tr")
        self.addCleanup(i18n.set_language, None)

    def test_reasons_name_at_most_two_artists(self):
        self.assertEqual(recommend_api.because_text(["Skillet"]), "Skillet dinlediğin için")
        self.assertEqual(recommend_api.because_text(["Skillet", "Seether"]), "Skillet ve Seether dinlediğin için")
        self.assertEqual(recommend_api.because_text(["A", "B", "C", "D"]), "A, B ve 2 sanatçı daha dinlediğin için")

    def test_spotify_search_link(self):
        self.assertEqual(recommend_api.spotify_search("Papa Roach", "Last Resort"),
                         "https://open.spotify.com/search/Papa%20Roach%20Last%20Resort")
