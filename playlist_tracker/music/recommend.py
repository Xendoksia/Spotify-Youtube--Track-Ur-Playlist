"""
Artists and songs to discover, found from what is played most lately. The artist model (music/model.py) lists
the artists alike to each of the artists played, and an artist alike to several of them, or high in their lists,
comes first. An artist the model does not know is looked up in Deezer's public API instead (RECOMMEND_SOURCE:
"hybrid", or "model" or "deezer" alone). The song model does the same from the songs played most. Artists and
songs already played are left out, while an unplayed song of an artist played is kept. Deezer needs no account and
only artist names and Deezer ids are sent. Its lookups are cached in artwork/related.json.
"""

from __future__ import annotations

import json
import math
import threading
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode

from playlist_tracker.core.config import load_config
from playlist_tracker.music import listening, model
from playlist_tracker.music.model import loose
from playlist_tracker.music.artwork import ART_DIR, RETRY_SECONDS, SEARCH_URL, _get, _plain_title
from playlist_tracker.music.listening import DB_PATH, key

CACHE_PATH = ART_DIR / "related.json"
# The Discover section's suggestions, worked out at most once a day: between two, what is played since is only
# taken out of them
DISCOVER_PATH = ART_DIR / "discover.json"
DISCOVER_SECONDS = 24 * 3600
# Raised when the models in models/ change, so the saved suggestions are worked out again with them at once
MODEL_VERSION = 4
# The artists suggested each day, kept for the discovery report: which of them were played afterwards
HISTORY_PATH = ART_DIR / "discover_history.json"
HISTORY_DAYS = 60
REPORT_DAYS = 30
# A suggested artist among this many most played of the report's days has become a favorite
FAVORITE_TOP = 10
# The report is about this many of the artists suggested, the favorites and the played ones first
REPORT_ROWS = 5
# The artists the suggestions start from, by their recent plays
SEEDS = 10
# A play counts half as much after this many days, so the suggestions follow what is played lately
HALF_LIFE_DAYS = 30
# Related artists read for each seed, best first
RELATED = 20
TOP_TRACKS = 3
# Deezer's top list may hold the same song twice (single and album), so more are read than shown
TOP_TRACKS_READ = 8
# Each time a seed's suggestion is picked, what the seed adds to the rest is multiplied by this, so a few
# much played artists do not fill every place and the others get theirs
SEED_DECAY = 0.5
# The model's settings, which did best in its tests (models/README.md): more seeds and more of each one's list
MODEL_SEEDS = 30
MODEL_RELATED = 50
MODEL_SEED_DECAY = 0.75
SONG_SEEDS = 30
# At most this many suggested songs of one artist in a list, so a few artists do not fill it
SONG_PER_ARTIST = 2
# An artist whose top list came back empty is asked again after this long
EMPTY_RETRY_SECONDS = 3600
# Related artists and top tracks change slowly, so they are looked up again after this long
REFRESH_SECONDS = 30 * 24 * 3600

# More artists and songs are worked out than shown, so one hidden or moved down by the fame setting gives its
# place to the next
ARTIST_POOL = 30
SONG_POOL = 20
# The fame setting (DISCOVER_FAME) ranks by the square root of an artist's score, so the model's first few do not
# always stay on top, times ten for each power of ten it is better known (or lesser known) than the middle of the
# suggestions, at most FAME_LIMIT times either way
FAME_DIRECTION = {"known": 1, "balanced": 0, "lesser": -1}
FAME_LIMIT = 5.0
# ListenBrainz's listener counts, in the model, are about a hundredth of Deezer's fan counts, and low for many
# artists Deezer knows well (Turkish ones above all), so the larger of the two on one scale is taken
LISTENERS_SCALE = 2.0

_lock = threading.Lock()
_cache: dict | None = None


def fold(text: str) -> str:
    """A name without case, accents or Turkish letters: Deezer spells Göksel as "Goksel"."""
    text = (text or "").replace("ı", "i").replace("İ", "i")
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return " ".join("".join(c for c in decomposed if not unicodedata.combining(c)).split())


def _load() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _cache = {}
        _cache.setdefault("artists", {})
        _cache.setdefault("tracks", {})
        _cache.setdefault("ids", {})
    return _cache


def _save() -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = CACHE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(_cache, ensure_ascii=False), encoding="utf-8")
    temporary.replace(CACHE_PATH)


def _fresh(entry: dict | None) -> bool:
    if not entry:
        return False
    return time.time() - entry["at"] < (RETRY_SECONDS if entry.get("missing") else REFRESH_SECONDS)


def seeds(now: datetime | None = None, limit: int = SEEDS, db_path: Path = DB_PATH) -> list[dict]:
    """The artists played most lately, {key, name, weight}: each play weighs half as much every HALF_LIFE_DAYS
    days, and a collaboration counts for the artists it credits."""
    now = now or datetime.now(timezone.utc)
    with listening.open_db(db_path) as db:
        rows = db.execute("SELECT artist, played_at FROM listens").fetchall()
    solo = listening.known_artists(row[0] for row in rows)
    artists: dict[str, dict] = {}
    for artist, played_at in rows:
        age = max(0.0, (now - listening.from_utc(played_at)).total_seconds() / 86400)
        for part in listening.credited(artist, solo):
            entry = artists.setdefault(key(part), {"key": key(part), "name": part, "weight": 0.0})
            entry["weight"] += 0.5 ** (age / HALF_LIFE_DAYS)
    ordered = sorted(artists.values(), key=lambda a: -a["weight"])[:limit]
    return [{**a, "weight": round(a["weight"], 3)} for a in ordered]


def heard(db_path: Path = DB_PATH) -> set[str]:
    """Every artist name in the plays, each artist of a collaboration too, folded and without punctuation for
    matching the model's and Deezer's names."""
    with listening.open_db(db_path) as db:
        names = [row[0] for row in db.execute("SELECT DISTINCT artist FROM listens")]
    return {loose(fold(part)) for name in names for part in listening._credit_parts(name)}


def song_key(artist: str, title: str) -> str:
    """A song as the song model keys it: its first artist and its title without version notes, folded."""
    return loose(fold(listening._credit_parts(artist)[0]) + "|" + fold(_plain_title(title)))


def heard_songs(db_path: Path = DB_PATH) -> set[str]:
    """Every song in the plays as song_key, so a single and its album version count as one."""
    with listening.open_db(db_path) as db:
        return {song_key(artist, name) for artist, name in db.execute("SELECT DISTINCT artist, name FROM listens")}


def source() -> str:
    """Where the related artists come from: "hybrid" (the model, Deezer for an artist it does not know), "model"
    or "deezer". Deezer alone when the model's files are missing."""
    chosen = load_config().get("RECOMMEND_SOURCE", "hybrid")
    chosen = chosen if chosen in ("hybrid", "model", "deezer") else "hybrid"
    return chosen if chosen == "deezer" or model.artists.available() else "deezer"


def model_related(name: str) -> list[dict] | None:
    """The model's artists alike to an artist, best first, [{name, fans}], or None when it does not know it."""
    index = model.artists.find(fold(name))
    if index is None:
        return None
    return [{"name": model.artists.items[j]["name"], "fans": model.artists.items[j]["listeners"],
             "listeners": model.artists.items[j]["listeners"]}
            for j in model.artists.neighbours(index)[:MODEL_RELATED]]


def _data(get: Callable, url: str) -> list[dict]:
    """A Deezer list. Deezer answers an error such as its rate limit with an "error" field, which is raised rather
    than kept as an empty list."""
    answer = get(url)
    if "error" in answer:
        raise LookupError(answer["error"])
    return answer.get("data") or []


def _find(name: str, get: Callable) -> dict | None:
    """An artist on Deezer: of the results with the same name, apart from accents, the one with most fans, as
    Deezer may also hold a same named artist with a handful of fans."""
    results = _data(get, f"{SEARCH_URL}/search/artist?" + urlencode({"q": name, "limit": 10}))
    same = [r for r in results if fold(r.get("name", "")) == fold(name)]
    return max(same, key=lambda r: r.get("nb_fan") or 0) if same else None


def _find_id(name: str, get: Callable) -> int | None:
    found = _find(name, get)
    return found["id"] if found else None


def related(name: str, get: Callable = _get, fetch: bool = True) -> list[dict] | None:
    """Deezer's related artists of an artist, best first, [{id, name, fans}]. [] when Deezer does not know it,
    None when not looked up yet and fetch is off."""
    with _lock:
        entry = _load()["artists"].get(key(name))
    if not _fresh(entry):
        if not fetch:
            return None
        artist_id = _find_id(name, get)
        found = _data(get, f"{SEARCH_URL}/artist/{artist_id}/related?limit={RELATED}") if artist_id else []
        entry = {"at": time.time(), "id": artist_id,
                 "related": [{"id": a["id"], "name": a["name"], "fans": a.get("nb_fan") or 0} for a in found]}
        if not artist_id:
            entry["missing"] = True
        with _lock:
            _load()["artists"][key(name)] = entry
            _save()
    return entry["related"]


def _artist_entry(name: str, get: Callable, fetch: bool) -> dict:
    """{id, fans} of a suggested artist on Deezer, for its top tracks and how well known it is. Raises LookupError
    when not looked up yet and fetch is off."""
    with _lock:
        entry = _load()["ids"].get(fold(name))
    # Ids kept before the fans were are looked up again
    if not _fresh(entry) or "fans" not in entry:
        if not fetch:
            raise LookupError(name)
        found = _find(name, get)
        entry = {"at": time.time(), "id": found["id"] if found else None,
                 "fans": (found.get("nb_fan") or 0) if found else 0}
        if not entry["id"]:
            entry["missing"] = True
        with _lock:
            _load()["ids"][fold(name)] = entry
            _save()
    return entry


def _artist_id(name: str, get: Callable, fetch: bool) -> int | None:
    """The Deezer id of an artist the model suggested, for its top tracks. Raises LookupError when not looked up
    yet and fetch is off."""
    return _artist_entry(name, get, fetch)["id"]


def fame(listeners: int, fans: int) -> float:
    """How well known an artist is, about 2 to 7: the larger of its Deezer fans and its ListenBrainz listeners
    on the same scale, in powers of ten."""
    return max(math.log10(1 + fans), math.log10(1 + listeners) + LISTENERS_SCALE)


def pick_artists(artists: list[dict], limit: int, hidden: set[str] = frozenset(), setting: str = "balanced") \
        -> list[dict]:
    """The suggested artists to show: without the hidden ones (by key), in the model's order for the balanced
    setting, else with their scores weighed toward the better or the lesser known."""
    left = [a for a in artists if loose(fold(a["name"])) not in hidden]
    direction = FAME_DIRECTION.get(setting, 0)
    if direction and left:
        known = {id(a): fame(a.get("listeners", 0), a.get("deezer_fans", 0)) for a in left}
        middle = sorted(known.values())[len(known) // 2]
        factor = lambda a: min(FAME_LIMIT, max(1 / FAME_LIMIT, 10 ** (direction * (known[id(a)] - middle))))
        left = sorted(left, key=lambda a: -math.sqrt(max(0.0, a.get("score", 0))) * factor(a))
    return left[:limit]


def hidden_keys(kind: str) -> set[str]:
    """The keys of the artists or songs hidden from the suggestions (DISCOVER_HIDDEN)."""
    return {h["key"] for h in load_config().get("DISCOVER_HIDDEN") or [] if h.get("kind") == kind}


def top_tracks(artist_id: int, get: Callable = _get, fetch: bool = True) -> list[dict] | None:
    """An artist's most played tracks on Deezer, [{title, artist, album, link}], or None when not looked up yet and
    fetch is off. Previews are not kept: their addresses expire."""
    with _lock:
        entry = _load()["tracks"].get(str(artist_id))
    # None found, or an error kept before errors were told apart: asked again soon
    empty = entry is not None and not entry["tracks"]
    if not (time.time() - entry["at"] < EMPTY_RETRY_SECONDS if empty else _fresh(entry)):
        if not fetch:
            return None
        found = _data(get, f"{SEARCH_URL}/artist/{artist_id}/top?limit={TOP_TRACKS_READ}")
        tracks: dict[str, dict] = {}
        for t in found:
            title = t.get("title_short") or t["title"]
            tracks.setdefault(fold(_plain_title(title)), {
                "title": title, "artist": (t.get("artist") or {}).get("name", ""),
                "album": (t.get("album") or {}).get("title", ""), "link": t.get("link", "")})
        entry = {"at": time.time(), "tracks": list(tracks.values())[:TOP_TRACKS]}
        with _lock:
            _load()["tracks"][str(artist_id)] = entry
            _save()
    return entry["tracks"]


def model_tracks(name: str, played: set[str]) -> list[dict]:
    """An artist's most listened songs in the song model that are not played yet, [{title, artist, album, link}]."""
    tracks, seen = [], set(played)
    for index in model.songs_of(fold(name)):
        song = model.songs.items[index]
        # The same song may be in the model twice, spelt with different punctuation
        if loose(song["key"]) not in seen:
            seen.add(loose(song["key"]))
            tracks.append({"title": song["title"], "artist": song["artist"], "album": "", "link": ""})
        if len(tracks) == TOP_TRACKS:
            break
    return tracks


def score(seed_list: list[dict], related_of: dict[str, list[dict]], played: set[str], decay: float = SEED_DECAY,
          size: int = RELATED, limit: int | None = None) -> list[dict]:
    """Rank the related artists (or songs, by their "key") not played yet: each seed adds its weight, scaled down
    the lower the item is in its list, so one close to several of the seeds wins. Picked one at a time, and each
    pick lowers what its seeds add to the rest (decay), so the suggestions reach beyond the most played. Each gets
    the seeds that suggested it, most first, and what each added to its score (shares, [name, share])."""
    shares: dict[str, dict] = {}
    for seed in seed_list:
        candidates = related_of.get(seed["key"]) or []
        for place, item in enumerate(candidates):
            item_key = loose(item.get("key") or fold(item["name"]))
            if item_key in played:
                continue
            entry = shares.setdefault(item_key, {**item, "key": item_key, "shares": {}})
            # The same artist from the model and from Deezer: Deezer's id is kept for its top tracks
            if entry.get("id") is None and item.get("id") is not None:
                entry["id"] = item["id"]
            share = seed["weight"] * (1 - place / max(len(candidates), size))
            entry["shares"][seed["name"]] = entry["shares"].get(seed["name"], 0.0) + share
    used = {seed["name"]: 0 for seed in seed_list}
    ranked = []
    while shares and (limit is None or len(ranked) < limit):
        value = lambda a: sum(share * decay ** used[name] for name, share in a["shares"].items())
        best = max(shares.values(), key=lambda a: (value(a), a.get("fans", 0)))
        del shares[best["key"]]
        because = sorted(best["shares"], key=lambda n: -best["shares"][n])
        added = [[name, round(best["shares"][name] * decay ** used[name], 3)] for name in because]
        ranked.append({**{k: v for k, v in best.items() if k != "shares"}, "score": round(value(best), 3),
                       "because": because, "shares": sorted(added, key=lambda s: -s[1])})
        for name in best["shares"]:
            used[name] += 1
    return ranked


def suggestions(limit: int = 12, fetch: bool = True, get: Callable = _get, now: datetime | None = None,
                db_path: Path = DB_PATH) -> dict:
    """{artists, complete}: the artists to discover with their top tracks not played yet, best first. Without fetch
    only what is cached is used, and complete says whether anything is still to be looked up."""
    chosen = source()
    use_model = chosen != "deezer"
    seed_list = seeds(now, MODEL_SEEDS if use_model else SEEDS, db_path)
    complete = True
    related_of: dict[str, list[dict]] = {}
    for seed in seed_list:
        found = model_related(seed["name"]) if use_model else None
        if found is None and chosen != "model":
            try:
                found = related(seed["name"], get, fetch)
            except Exception:  # offline or Deezer unavailable: tried again next time
                found = None
            if found is None:
                complete = False
        related_of[seed["key"]] = found or []
    played_songs = heard_songs(db_path)
    artists = score(seed_list, related_of, heard(db_path), MODEL_SEED_DECAY if use_model else SEED_DECAY,
                    MODEL_RELATED if use_model else RELATED, limit)
    for artist in artists:
        if "listeners" not in artist and use_model:
            index = model.artists.find(fold(artist["name"]))
            artist["listeners"] = model.artists.items[index]["listeners"] if index is not None else 0
        if "listeners" not in artist:
            # A Deezer related artist's fans are Deezer's own
            artist["deezer_fans"] = artist.get("fans", 0)
        elif chosen != "model":
            try:
                artist["deezer_fans"] = _artist_entry(artist["name"], get, fetch)["fans"]
            except Exception:  # not looked up yet, offline or Deezer unavailable: tried again next time
                complete = False
        tracks = model_tracks(artist["name"], played_songs) if use_model else []
        if not tracks and chosen != "model":
            try:
                artist_id = artist.get("id") or _artist_id(artist["name"], get, fetch)
                tracks = top_tracks(artist_id, get, fetch) if artist_id else []
            except Exception:
                tracks = None
            if tracks is None:
                complete = False
            tracks = [t for t in tracks or [] if song_key(t["artist"], t["title"]) not in played_songs]
        artist["tracks"] = tracks or []
    return {"artists": artists, "complete": complete}


def song_seeds(now: datetime | None = None, limit: int = SONG_SEEDS, db_path: Path = DB_PATH) -> list[dict]:
    """The songs played most lately that the song model knows, {key, name, weight}, weighed as seeds() does."""
    now = now or datetime.now(timezone.utc)
    with listening.open_db(db_path) as db:
        rows = db.execute("SELECT artist, name, played_at FROM listens").fetchall()
    found: dict[str, dict] = {}
    for artist, name, played_at in rows:
        age = max(0.0, (now - listening.from_utc(played_at)).total_seconds() / 86400)
        entry = found.setdefault(song_key(artist, name), {"key": song_key(artist, name), "name": _plain_title(name),
                                                          "weight": 0.0})
        entry["weight"] += 0.5 ** (age / HALF_LIFE_DAYS)
    known = [s for s in found.values() if model.songs.find(s["key"]) is not None]
    return sorted(known, key=lambda s: -s["weight"])[:limit]


# The song model's version 2 ranks with its two tables and fuses the two lists' first RRF_TOP by reciprocal rank
RRF_K = 60
RRF_TOP = 50


def fuse(*lists: list[dict]) -> list[dict]:
    """The ranked lists fused: each song gets 1 / (RRF_K + place + 1) from each list's first RRF_TOP it is in, most
    first, the more listened first on a tie. The songs further down follow, fused the same way over the whole lists,
    as the new and known songs need more than the first ones once the played artists' are split off. A song keeps
    the first list's entry, with the seeds of both."""
    found: dict[str, dict] = {}
    for ranking in lists:
        for place, item in enumerate(ranking):
            entry = found.setdefault(item["key"], {**item, "top": 0.0, "score": 0.0, "because": []})
            if place < RRF_TOP:
                entry["top"] += 1 / (RRF_K + place + 1)
            entry["score"] += 1 / (RRF_K + place + 1)
            entry["because"] += [name for name in item["because"] if name not in entry["because"]]
    fused = sorted(found.values(), key=lambda s: (s["top"] == 0, -(s["top"] or s["score"]), -s.get("fans", 0)))
    return [{**{k: v for k, v in song.items() if k != "top"}, "score": round(song["top"] or song["score"], 5)}
            for song in fused]


def song_suggestions(limit: int = 12, now: datetime | None = None, db_path: Path = DB_PATH,
                     skip_artists: set[str] = frozenset()) -> dict:
    """{new, known}: songs not played yet, from the song model alone, so offline. new are by artists not played at
    all, leaving out skip_artists (folded, the artists suggested already), known by artists played. At most
    SONG_PER_ARTIST of one artist in each."""
    if not model.songs.available():
        return {"new": [], "known": []}
    seed_list = song_seeds(now, db_path=db_path)
    played_songs = heard_songs(db_path)

    def ranked(table: Callable[[int], list[int] | None]) -> list[dict] | None:
        related_of = {}
        for seed in seed_list:
            alike = table(model.songs.find(seed["key"]))
            if alike is None:
                return None
            related_of[seed["key"]] = [{"key": model.songs.items[j]["key"], "name": model.songs.items[j]["title"],
                                        "artist": model.songs.items[j]["artist"],
                                        "fans": model.songs.items[j]["listeners"]} for j in alike[:MODEL_RELATED]]
        return score(seed_list, related_of, played_songs, MODEL_SEED_DECAY, MODEL_RELATED)

    knn = ranked(model.songs.neighbours)
    rp3 = ranked(model.songs.neighbours_rp3)
    played_artists = heard(db_path)
    lists: dict[str, list[dict]] = {"new": [], "known": []}
    per_artist: dict[str, int] = {}
    for song in fuse(knn, rp3) if rp3 is not None else knn:
        artists = [loose(fold(part)) for part in listening._credit_parts(song["artist"])]
        target = lists["known" if any(a in played_artists for a in artists) else "new"]
        if len(target) >= limit or per_artist.get(artists[0], 0) >= SONG_PER_ARTIST or (
                target is lists["new"] and artists[0] in skip_artists):
            continue
        per_artist[artists[0]] = per_artist.get(artists[0], 0) + 1
        target.append(song)
        if all(len(songs) >= limit for songs in lists.values()):
            break
    return lists


def _read_discover() -> dict | None:
    try:
        saved = json.loads(DISCOVER_PATH.read_text(encoding="utf-8"))
        return saved if {"at", "complete", "artists", "new", "known"} <= saved.keys() else None
    except (OSError, ValueError):
        return None


def _write_discover(found: dict) -> None:
    DISCOVER_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = DISCOVER_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(found, ensure_ascii=False), encoding="utf-8")
    temporary.replace(DISCOVER_PATH)


def discover(limit: int = 12, song_limit: int = 10, fetch: bool = False, force: bool = False, get: Callable = _get,
             now: datetime | None = None, db_path: Path = DB_PATH) -> dict:
    """{at, complete, artists, new, known}: the suggested artists and songs. They are worked out again only once
    DISCOVER_SECONDS have passed (or with force, when an incomplete answer is completed), otherwise the saved ones
    are used. Either way the artists and songs played since are left out."""
    saved = None if force else _read_discover()
    if saved is None or time.time() - saved["at"] >= DISCOVER_SECONDS or saved.get("model") != MODEL_VERSION:
        found = suggestions(max(limit, ARTIST_POOL), fetch, get, now, db_path)
        shown = pick_artists(found["artists"], limit, hidden_keys("artist"),
                             load_config().get("DISCOVER_FAME") or "balanced")
        songs = song_suggestions(max(song_limit, SONG_POOL), now, db_path, skip_artists={a["key"] for a in shown})
        saved = {"at": time.time(), "model": MODEL_VERSION, "complete": found["complete"], "artists": found["artists"],
                 **songs}
        _write_discover(saved)
        _remember([a["name"] for a in shown], now)
    else:
        # An artist saved without songs or fans, as Deezer could not be reached, takes them once they are found
        filled = False
        for artist in saved["artists"]:
            if "deezer_fans" not in artist and source() == "hybrid":
                try:
                    artist["deezer_fans"], filled = _artist_entry(artist["name"], get, fetch=False)["fans"], True
                except LookupError:
                    saved["complete"] = False
            if not artist["tracks"] and artist.get("id"):
                tracks = top_tracks(artist["id"], get, fetch=False)
                if tracks:
                    artist["tracks"], filled = tracks, True
                elif tracks is None:
                    saved["complete"] = False
        if filled:
            _write_discover(saved)
        # Suggestions saved before the history was kept start it, on the day they were worked out
        if not _read_history():
            _remember([a["name"] for a in pick_artists(saved["artists"], limit)],
                      datetime.fromtimestamp(saved["at"], timezone.utc))
    played_artists, played_songs = heard(db_path), heard_songs(db_path)
    artists = [{**a, "tracks": [t for t in a["tracks"] if song_key(t["artist"], t["title"]) not in played_songs]}
               for a in saved["artists"] if loose(fold(a["name"])) not in played_artists]
    left = lambda songs: [s for s in songs if loose(s["key"]) not in played_songs]
    return {**saved, "artists": artists, "new": left(saved["new"]), "known": left(saved["known"])}


def _read_history() -> dict[str, list[str]]:
    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _remember(names: list[str], now: datetime | None = None) -> None:
    """Keep the day's suggested artists (local date → names), the last HISTORY_DAYS days of them. Worked out again
    the same day, the day keeps the newer ones."""
    today = (now or datetime.now(timezone.utc)).astimezone().date()
    history = {day: kept for day, kept in _read_history().items()
               if date.fromisoformat(day) > today - timedelta(days=HISTORY_DAYS)}
    history[today.isoformat()] = names
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False), encoding="utf-8")


def report(now: datetime | None = None, db_path: Path = DB_PATH) -> dict:
    """The discovery report of the last REPORT_DAYS days: {suggested, listened, favorites, rows, days}. Each artist
    suggested in them, from the first day it was, is a favorite (among the FAVORITE_TOP most played of the days,
    collaborations counted for the artists they credit), listened (played at least once) or untried. rows are
    {name, day, plays, state} with favorites first, days the suggestions by day, newest first."""
    now = now or datetime.now(timezone.utc)
    start = now.astimezone().date() - timedelta(days=REPORT_DAYS - 1)
    first: dict[str, tuple[str, str]] = {}
    history = _read_history()
    for day in sorted(history):
        if date.fromisoformat(day) >= start:
            for name in history[day]:
                first.setdefault(loose(fold(name)), (day, name))
    day_start = lambda day: datetime.combine(date.fromisoformat(day), datetime.min.time()).astimezone()
    with listening.open_db(db_path) as db:
        solo = listening.known_artists(row[0] for row in db.execute("SELECT DISTINCT artist FROM listens"))
        rows = db.execute("SELECT artist, played_at FROM listens WHERE played_at >= ?",
                          (listening.to_utc(day_start(start.isoformat())),)).fetchall()
    counts: dict[str, int] = {}
    plays: dict[str, list[datetime]] = {}
    for artist, played_at in rows:
        for part in listening.credited(artist, solo):
            counts[loose(fold(part))] = counts.get(loose(fold(part)), 0) + 1
            plays.setdefault(loose(fold(part)), []).append(listening.from_utc(played_at))
    top = set(sorted(counts, key=lambda k: -counts[k])[:FAVORITE_TOP])
    found = []
    for key, (day, name) in first.items():
        after = sum(1 for moment in plays.get(key, []) if moment >= day_start(day))
        state = "favorite" if after and key in top else "listened" if after else "untried"
        found.append({"name": name, "day": day, "plays": after, "state": state})
    order = {"favorite": 0, "listened": 1, "untried": 2}
    found.sort(key=lambda r: (order[r["state"]], -r["plays"], r["day"]))
    found = found[:REPORT_ROWS]
    days = [{"day": day, "names": history[day]} for day in sorted(history, reverse=True)
            if date.fromisoformat(day) >= start]
    return {"suggested": len(found), "listened": sum(r["state"] != "untried" for r in found),
            "favorites": sum(r["state"] == "favorite" for r in found), "rows": found, "days": days}


ALIKE = 12


# The song model finds mostly the same artist's songs alike, so a song's page takes at most this many of its own
# artist's and of any other, and the rest from the artists most alike to its artist
ALIKE_SAME_ARTIST = 2
ALIKE_PER_ARTIST = 2


def alike_songs(artist: str, name: str, limit: int = ALIKE, db_path: Path = DB_PATH) -> list[dict]:
    """The songs most alike to a song, best first: {artist, title, track_key}, track_key the played song's own key
    or None for one not played. First the song model's (ALIKE_SAME_ARTIST of the song's own artist and
    ALIKE_PER_ARTIST of each other), then one song of each artist the artist model finds most alike to its artist,
    the most listened one not played yet. [] when neither model knows the song."""
    index = model.songs.find(song_key(artist, name)) if model.songs.available() else None
    own = loose(fold(listening._credit_parts(artist)[0]))
    with listening.open_db(db_path) as db:
        played = {song_key(a, n): k for a, n, k in db.execute("SELECT DISTINCT artist, name, track_key FROM listens")}
    found, seen, per = [], {song_key(artist, name)}, {}

    def add(j: int) -> bool:
        song = model.songs.items[j]
        by = loose(song["key"].split("|")[0])
        # The same song may be in the model twice, spelt with different punctuation
        if loose(song["key"]) in seen or per.get(by, 0) >= (ALIKE_SAME_ARTIST if by == own else ALIKE_PER_ARTIST):
            return False
        seen.add(loose(song["key"]))
        per[by] = per.get(by, 0) + 1
        found.append({"artist": song["artist"], "title": song["title"], "track_key": played.get(loose(song["key"]))})
        return True

    for j in model.songs.neighbours(index) if index is not None else []:
        if len(found) == limit:
            return found
        add(j)
    for other in alike_artists(artist, limit=50, db_path=db_path):
        if len(found) == limit:
            break
        songs = model.songs_of(fold(other["name"]))
        if per.get(loose(fold(other["name"]))) or not songs:
            continue
        unplayed = [j for j in songs if loose(model.songs.items[j]["key"]) not in played]
        add((unplayed or songs)[0])
    return found


def alike_artists(name: str, limit: int = ALIKE, db_path: Path = DB_PATH) -> list[dict]:
    """The artists the artist model finds most alike to an artist, best first: {name, artist_key}, artist_key the
    page of one played or None. [] when the model does not know the artist."""
    if not model.artists.available() or (index := model.artists.find(fold(name))) is None:
        return []
    with listening.open_db(db_path) as db:
        names = [row[0] for row in db.execute("SELECT DISTINCT artist FROM listens")]
    played = {loose(fold(part)): key(part) for n in names for part in listening._credit_parts(n)}
    return [{"name": model.artists.items[j]["name"],
             "artist_key": played.get(loose(fold(model.artists.items[j]["name"])))}
            for j in model.artists.neighbours(index)[:limit]]
