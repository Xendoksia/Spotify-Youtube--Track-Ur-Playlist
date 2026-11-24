import gzip
import json
from array import array
from datetime import timedelta
from pathlib import Path
from unittest import mock

from playlist_tracker.api import recommend as recommend_api
from playlist_tracker.core import i18n
from playlist_tracker.music import model, recommend
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
        patcher = mock.patch.object(recommend, "DISCOVER_PATH", Path(self._folder.name) / "discover.json")
        patcher.start()
        self.addCleanup(patcher.stop)
        # No model unless a test writes one, so the suggestions come from the fake Deezer
        self.models = Path(self._folder.name) / "models"
        self.models.mkdir()
        for kind in ("artist", "song"):
            patcher = mock.patch.object(model, f"{kind}s", model.Model(kind, self.models))
            patcher.start()
            self.addCleanup(patcher.stop)
        model._songs_of = None
        self.addCleanup(setattr, model, "_songs_of", None)

    def write_model(self, kind: str, items: list[dict], neighbours: list[list[int]], width: int = 3):
        with gzip.open(self.models / f"{kind}s.json.gz", "wt", encoding="utf-8") as f:
            json.dump(items, f)
        ids = array("i", [j for row in neighbours for j in (row + [-1] * width)[:width]])
        with gzip.open(self.models / f"{kind}_neighbours.i32.gz", "wb") as f:
            f.write(ids.tobytes())

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


class ModelTest(RecommendTestCase):
    """The models: Metallica is alike to Megadeth and Slayer, Göksel to Sertab Erener. Their songs: One is alike to
    Megadeth's Symphony of Destruction, Metallica's Fade to Black and the played Enter Sandman."""

    def setUp(self):
        super().setUp()
        artists = [{"name": "Metallica", "key": "metallica", "listeners": 900},
                   {"name": "Megadeth", "key": "megadeth", "listeners": 500},
                   {"name": "Slayer", "key": "slayer", "listeners": 400},
                   {"name": "Göksel", "key": "goksel", "listeners": 300},
                   {"name": "Sertab Erener", "key": "sertab erener", "listeners": 200}]
        self.write_model("artist", artists, [[1, 2], [0], [0], [4], [3]])
        songs = [{"artist": "Metallica", "title": "One", "key": "metallica|one", "listeners": 90},
                 {"artist": "Megadeth", "title": "Symphony of Destruction",
                  "key": "megadeth|symphony of destruction", "listeners": 50},
                 {"artist": "Metallica", "title": "Fade to Black", "key": "metallica|fade to black", "listeners": 70},
                 {"artist": "Metallica", "title": "Enter Sandman", "key": "metallica|enter sandman", "listeners": 95},
                 {"artist": "Slayer", "title": "Raining Blood", "key": "slayer|raining blood", "listeners": 40}]
        self.write_model("song", songs, [[1, 2, 3], [0], [0], [0], [1]])

    def test_the_model_suggests_unplayed_artists_with_their_unplayed_songs_and_asks_deezer_nothing(self):
        self.play("Metallica", "One - Remastered", "2026-11-19 10:00")
        deezer = FakeDeezer({}, {})
        found = recommend.suggestions(fetch=True, get=deezer, now=NOW, db_path=self.db)
        self.assertEqual([a["name"] for a in found["artists"]], ["Megadeth", "Slayer"])
        self.assertEqual(found["artists"][1]["tracks"][0]["title"], "Raining Blood")
        self.assertEqual((deezer.requests, found["complete"]), (0, True))

    def test_an_artist_the_model_does_not_know_falls_back_to_deezer(self):
        self.play("Kenan Doğulu", "Tutamıyorum Zamanı", "2026-11-19 10:00")
        deezer = FakeDeezer({"Kenan Dogulu": (10, 50)}, {10: [(20, "Tarkan")]})
        found = recommend.suggestions(fetch=True, get=deezer, now=NOW, db_path=self.db)
        self.assertEqual([a["name"] for a in found["artists"]], ["Tarkan"])
        self.assertEqual(found["artists"][0]["tracks"][0]["title"], "Song 20")

    def test_songs_leave_out_played_ones_and_split_new_and_known_artists(self):
        self.play("Metallica", "One - Remastered", "2026-11-19 10:00")
        self.play("Metallica", "Enter Sandman", "2026-11-19 10:10")
        songs = recommend.song_suggestions(now=NOW, db_path=self.db)
        self.assertEqual([s["name"] for s in songs["new"]], ["Symphony of Destruction"])
        self.assertEqual([s["name"] for s in songs["known"]], ["Fade to Black"])
        self.assertEqual(songs["known"][0]["because"], ["One"])

    def test_suggested_artists_are_left_out_of_the_new_songs(self):
        self.play("Metallica", "One", "2026-11-19 10:00")
        songs = recommend.song_suggestions(now=NOW, db_path=self.db, skip_artists={"megadeth"})
        self.assertEqual(songs["new"], [])


class DiscoverTest(ModelTest):
    def test_worked_out_once_a_day_and_what_is_played_since_is_left_out(self):
        self.play("Metallica", "One", "2026-11-19 10:00")
        first = recommend.discover(now=NOW, db_path=self.db)
        self.assertEqual([a["name"] for a in first["artists"]], ["Megadeth", "Slayer"])
        self.assertEqual([s["name"] for s in first["known"]], ["Fade to Black", "Enter Sandman"])
        self.play("Slayer", "South of Heaven", "2026-11-19 11:00")
        self.play("Metallica", "Fade to Black", "2026-11-19 11:10")
        with mock.patch.object(recommend, "suggestions", side_effect=AssertionError("worked out again")):
            later = recommend.discover(now=NOW, db_path=self.db)
        self.assertEqual([a["name"] for a in later["artists"]], ["Megadeth"])
        self.assertEqual([s["name"] for s in later["known"]], ["Enter Sandman"])

    def test_a_day_later_it_is_worked_out_again(self):
        self.play("Metallica", "One", "2026-11-19 10:00")
        recommend.discover(now=NOW, db_path=self.db)
        day_later = recommend.time.time() + recommend.DISCOVER_SECONDS
        with mock.patch.object(recommend.time, "time", return_value=day_later),                 mock.patch.object(recommend, "suggestions", wraps=recommend.suggestions) as worked_out:
            recommend.discover(now=NOW, db_path=self.db)
        worked_out.assert_called_once()


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
