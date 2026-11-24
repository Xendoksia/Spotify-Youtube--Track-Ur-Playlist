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
# The artists suggested each day, kept for the discovery report: which of them were played afterwards
HISTORY_PATH = ART_DIR / "discover_history.json"
HISTORY_DAYS = 60
REPORT_DAYS = 30
# A suggested artist among this many most played of the report's days has become a favorite
FAVORITE_TOP = 10
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
    return [{"name": model.artists.items[j]["name"], "fans": model.artists.items[j]["listeners"]}
            for j in model.artists.neighbours(index)[:MODEL_RELATED]]


def _data(get: Callable, url: str) -> list[dict]:
    """A Deezer list. Deezer answers an error such as its rate limit with an "error" field, which is raised rather
    than kept as an empty list."""
    answer = get(url)
    if "error" in answer:
        raise LookupError(answer["error"])
    return answer.get("data") or []


def _find_id(name: str, get: Callable) -> int | None:
    """The Deezer id of an artist: of the results with the same name, apart from accents, the one with most fans,
    as Deezer may also hold a same named artist with a handful of fans."""
    results = _data(get, f"{SEARCH_URL}/search/artist?" + urlencode({"q": name, "limit": 10}))
    same = [r for r in results if fold(r.get("name", "")) == fold(name)]
    return max(same, key=lambda r: r.get("nb_fan") or 0)["id"] if same else None


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


def _artist_id(name: str, get: Callable, fetch: bool) -> int | None:
    """The Deezer id of an artist the model suggested, for its top tracks. Raises LookupError when not looked up
    yet and fetch is off."""
    with _lock:
        entry = _load()["ids"].get(fold(name))
    if not _fresh(entry):
        if not fetch:
            raise LookupError(name)
        entry = {"at": time.time(), "id": _find_id(name, get)}
        if not entry["id"]:
            entry["missing"] = True
        with _lock:
            _load()["ids"][fold(name)] = entry
            _save()
    return entry["id"]


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
    the seeds that suggested it, most first."""
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
        ranked.append({**{k: v for k, v in best.items() if k != "shares"}, "score": round(value(best), 3),
                       "because": because})
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


def song_suggestions(limit: int = 12, now: datetime | None = None, db_path: Path = DB_PATH,
                     skip_artists: set[str] = frozenset()) -> dict:
    """{new, known}: songs not played yet, from the song model alone, so offline. new are by artists not played at
    all, leaving out skip_artists (folded, the artists suggested already), known by artists played. At most
    SONG_PER_ARTIST of one artist in each."""
    if not model.songs.available():
        return {"new": [], "known": []}
    seed_list = song_seeds(now, db_path=db_path)
    related_of = {}
    for seed in seed_list:
        alike = model.songs.neighbours(model.songs.find(seed["key"]))[:MODEL_RELATED]
        related_of[seed["key"]] = [{"key": model.songs.items[j]["key"], "name": model.songs.items[j]["title"],
                                    "artist": model.songs.items[j]["artist"],
                                    "fans": model.songs.items[j]["listeners"]} for j in alike]
    played_artists = heard(db_path)
    lists: dict[str, list[dict]] = {"new": [], "known": []}
    per_artist: dict[str, int] = {}
    for song in score(seed_list, related_of, heard_songs(db_path), MODEL_SEED_DECAY, MODEL_RELATED):
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
    if saved is None or time.time() - saved["at"] >= DISCOVER_SECONDS:
        found = suggestions(limit, fetch, get, now, db_path)
        songs = song_suggestions(song_limit, now, db_path, skip_artists={a["key"] for a in found["artists"]})
        saved = {"at": time.time(), "complete": found["complete"], "artists": found["artists"], **songs}
        _write_discover(saved)
        _remember([a["name"] for a in found["artists"]], now)
    else:
        # An artist saved without songs, as Deezer could not be reached, takes them once they are found
        filled = False
        for artist in saved["artists"]:
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
            _remember([a["name"] for a in saved["artists"][:limit]], datetime.fromtimestamp(saved["at"], timezone.utc))
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
    days = [{"day": day, "names": history[day]} for day in sorted(history, reverse=True)
            if date.fromisoformat(day) >= start]
    return {"suggested": len(found), "listened": sum(r["state"] != "untried" for r in found),
            "favorites": sum(r["state"] == "favorite" for r in found), "rows": found, "days": days}
