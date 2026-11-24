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
        for name in ("DISCOVER_PATH", "HISTORY_PATH"):
            patcher = mock.patch.object(recommend, name, Path(self._folder.name) / f"{name}.json")
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

    def write_model(self, kind: str, items: list[dict], neighbours: list[list[int]], width: int = 3,
                    rp3: list[list[int]] | None = None):
        with gzip.open(self.models / f"{kind}s.json.gz", "wt", encoding="utf-8") as f:
            json.dump(items, f)
        for name, table in (("neighbours", neighbours), ("neighbours_rp3", rp3)):
            if table is None:
                continue
            ids = array("i", [j for row in table for j in (row + [-1] * width)[:width]])
            with gzip.open(self.models / f"{kind}_{name}.i32.gz", "wb") as f:
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

    def test_a_song_spelt_with_other_punctuation_counts_as_played(self):
        songs = [{"artist": "Linkin Park", "title": "Numb", "key": "linkin park|numb", "listeners": 90},
                 {"artist": "Linkin Park", "title": "What I’ve Done", "key": "linkin park|what i’ve done",
                  "listeners": 80},
                 {"artist": "Linkin Park", "title": "What I've Done", "key": "linkin park|what i've done",
                  "listeners": 70},
                 {"artist": "Linkin Park", "title": "Faint", "key": "linkin park|faint", "listeners": 60}]
        self.write_model("song", songs, [[1, 2, 3], [0], [0], [0]])
        self.play("Linkin Park", "Numb", "2026-11-19 10:00")
        self.play("Linkin Park", "What I've Done", "2026-11-19 10:10")
        songs = recommend.song_suggestions(now=NOW, db_path=self.db)
        self.assertEqual([s["name"] for s in songs["known"]], ["Faint"])

    def test_suggested_artists_are_left_out_of_the_new_songs(self):
        self.play("Metallica", "One", "2026-11-19 10:00")
        songs = recommend.song_suggestions(now=NOW, db_path=self.db, skip_artists={"megadeth"})
        self.assertEqual(songs["new"], [])


    def test_the_second_song_table_is_fused_by_reciprocal_rank(self):
        songs = json.loads(gzip.decompress((self.models / "songs.json.gz").read_bytes()))
        # RP3beta finds Fade to Black, Raining Blood and Symphony of Destruction alike to One, in that order
        self.write_model("song", songs, [[1, 2, 3], [0], [0], [0], [1]], rp3=[[2, 4, 1], [0], [0], [0], [1]])
        self.play("Metallica", "One", "2026-11-19 10:00")
        self.play("Metallica", "Enter Sandman", "2026-11-19 10:10")
        found = recommend.song_suggestions(now=NOW, db_path=self.db)
        # Symphony: 1/61 + 1/63, Raining Blood: 1/62 from RP3beta alone
        self.assertEqual([s["name"] for s in found["new"]], ["Symphony of Destruction", "Raining Blood"])
        self.assertEqual([s["name"] for s in found["known"]], ["Fade to Black"])

    def test_fusing_puts_a_song_high_in_both_lists_first_and_breaks_ties_by_listeners(self):
        a = [{"key": "x", "fans": 1, "because": ["S"]}, {"key": "y", "fans": 9, "because": ["S"]}]
        b = [{"key": "y", "fans": 9, "because": ["T"]}, {"key": "x", "fans": 1, "because": ["S"]},
             {"key": "z", "fans": 5, "because": ["T"]}]
        fused = recommend.fuse(a, b)
        self.assertEqual([s["key"] for s in fused], ["y", "x", "z"])
        self.assertEqual(fused[0]["because"], ["S", "T"])

    def test_songs_below_the_fused_top_follow_it(self):
        top = [{"key": f"t{i}", "fans": 1, "because": []} for i in range(recommend.RRF_TOP)]
        low = [{"key": "low", "fans": 1, "because": []}]
        fused = recommend.fuse(top + low, top + low)
        self.assertEqual(fused[-1]["key"], "low")
        self.assertEqual(len(fused), recommend.RRF_TOP + 1)


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

    def test_suggestions_saved_with_an_older_model_are_worked_out_again(self):
        self.play("Metallica", "One", "2026-11-19 10:00")
        recommend.discover(now=NOW, db_path=self.db)
        saved = json.loads(recommend.DISCOVER_PATH.read_text(encoding="utf-8"))
        recommend.DISCOVER_PATH.write_text(json.dumps({**saved, "model": 1}), encoding="utf-8")
        with mock.patch.object(recommend, "suggestions", wraps=recommend.suggestions) as worked_out:
            recommend.discover(now=NOW, db_path=self.db)
        worked_out.assert_called_once()

    def test_a_day_later_it_is_worked_out_again(self):
        self.play("Metallica", "One", "2026-11-19 10:00")
        recommend.discover(now=NOW, db_path=self.db)
        day_later = recommend.time.time() + recommend.DISCOVER_SECONDS
        with mock.patch.object(recommend.time, "time", return_value=day_later),                 mock.patch.object(recommend, "suggestions", wraps=recommend.suggestions) as worked_out:
            recommend.discover(now=NOW, db_path=self.db)
        worked_out.assert_called_once()


class ReportTest(ModelTest):
    def test_suggested_artists_are_favorites_listened_or_untried_from_the_day_they_were_suggested(self):
        self.play("Metallica", "One", "2026-11-18 10:00")
        recommend.discover(now=NOW, db_path=self.db)  # Megadeth and Slayer, on 20 November
        self.assertEqual(recommend._read_history(), {"2026-11-20": ["Megadeth", "Slayer"]})
        self.play("Slayer", "Raining Blood", "2026-11-19 09:00")  # before it was suggested: does not count
        self.play("Megadeth", "Symphony of Destruction", "2026-11-21 10:00")
        found = recommend.report(now=NOW + timedelta(days=2), db_path=self.db)
        self.assertEqual([(r["name"], r["state"], r["plays"]) for r in found["rows"]],
                         [("Megadeth", "favorite", 1), ("Slayer", "untried", 0)])
        self.assertEqual((found["suggested"], found["listened"], found["favorites"]), (2, 1, 1))
        self.assertEqual(found["days"], [{"day": "2026-11-20", "names": ["Megadeth", "Slayer"]}])

    def test_the_history_keeps_sixty_days_and_one_list_a_day(self):
        recommend._remember(["Old"], NOW - timedelta(days=61))
        recommend._remember(["Morning"], NOW)
        recommend._remember(["Evening"], NOW)
        self.assertEqual(recommend._read_history(), {"2026-11-20": ["Evening"]})


class AlikeTest(ModelTest):
    def test_alike_songs_say_which_are_played_and_open_their_page(self):
        self.play("Metallica", "One", "2026-11-19 10:00")
        self.play("Metallica", "Enter Sandman", "2026-11-19 10:10")
        found = recommend.alike_songs("Metallica", "One - Remastered", db_path=self.db)
        # Two of Metallica's own, then the alike artists' most listened unplayed songs (Slayer's, as Megadeth's
        # one is in already)
        self.assertEqual([(s["title"], s["track_key"]) for s in found],
                         [("Symphony of Destruction", None), ("Fade to Black", None),
                          ("Enter Sandman", "metallica|enter sandman"), ("Raining Blood", None)])

    def test_alike_artists_and_an_unknown_one(self):
        self.play("Slayer", "Raining Blood", "2026-11-19 10:00")
        self.assertEqual(recommend.alike_artists("Metallica", db_path=self.db),
                         [{"name": "Megadeth", "artist_key": None}, {"name": "Slayer", "artist_key": "slayer"}])
        self.assertEqual(recommend.alike_artists("Nobody", db_path=self.db), [])


class DeezerErrorTest(RecommendTestCase):
    def test_an_error_answer_is_not_kept_as_no_tracks(self):
        error = lambda url: {"error": {"type": "Exception", "message": "Quota limit exceeded", "code": 4}}
        with self.assertRaises(LookupError):
            recommend.top_tracks(12875, error)
        self.assertNotIn("12875", recommend._load()["tracks"])

    def test_an_empty_top_list_is_looked_up_again_soon(self):
        recommend._load()["tracks"]["7"] = {"at": recommend.time.time() - recommend.EMPTY_RETRY_SECONDS, "tracks": []}
        self.assertIsNone(recommend.top_tracks(7, fetch=False))


class BecauseTextTest(RecommendTestCase):
    def setUp(self):
        super().setUp()
        i18n.set_language("tr")
        self.addCleanup(i18n.set_language, None)

    def test_reasons_name_at_most_two_artists(self):
        self.assertEqual(recommend_api.because_text(["Skillet"]), "Skillet dinlediğin için")
        self.assertEqual(recommend_api.because_text(["Skillet", "Seether"]), "Skillet ve Seether dinlediğin için")
        self.assertEqual(recommend_api.because_text(["A", "B", "C", "D"]), "A, B ve 2 sanatçı daha dinlediğin için")

    def test_a_suggestion_opens_its_own_spotify_track_and_falls_back_to_a_search(self):
        class FakeSpotify:
            def get(self, url):
                return {"tracks": {"items": [{"uri": "spotify:track:other", "artists": [{"name": "Someone"}]},
                                             {"uri": "spotify:track:right", "artists": [{"name": "Stone Sour"}]}]}}
        recommend_api._uris.clear()
        with mock.patch("playlist_tracker.playlists.spotify.connect", return_value=FakeSpotify()):
            self.assertEqual(recommend_api.spotify_uri("Stone Sour", "Through Glass"), "spotify:track:right")
        with mock.patch("playlist_tracker.playlists.spotify.connect", side_effect=RuntimeError("no account")):
            self.assertEqual(recommend_api.spotify_uri("Pop Evil", "Trenches"), "spotify:search:Pop%20Evil%20Trenches")
        recommend_api._uris.clear()

    def test_spotify_search_link(self):
        self.assertEqual(recommend_api.spotify_search("Papa Roach", "Last Resort"),
                         "https://open.spotify.com/search/Papa%20Roach%20Last%20Resort")
