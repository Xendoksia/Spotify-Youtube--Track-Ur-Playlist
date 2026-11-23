"""
Artists and tracks to discover, found from the artists played most lately: Deezer's public API lists the artists
related to each of them, and an artist related to several of them, or high in their lists, comes first. Artists
already played are left out. Deezer needs no account and only artist names and Deezer ids are sent. Lookups are
cached in artwork/related.json.
"""

from __future__ import annotations

import json
import threading
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode

from playlist_tracker.music import listening
from playlist_tracker.music.artwork import ART_DIR, RETRY_SECONDS, SEARCH_URL, _get, _plain_title
from playlist_tracker.music.listening import DB_PATH, key

CACHE_PATH = ART_DIR / "related.json"
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
    """Every artist name in the plays, each artist of a collaboration too, folded for matching Deezer's names."""
    with listening.open_db(db_path) as db:
        names = [row[0] for row in db.execute("SELECT DISTINCT artist FROM listens")]
    return {fold(part) for name in names for part in listening._credit_parts(name)}


def _find_id(name: str, get: Callable) -> int | None:
    """The Deezer id of an artist: of the results with the same name, apart from accents, the one with most fans,
    as Deezer may also hold a same named artist with a handful of fans."""
    results = get(f"{SEARCH_URL}/search/artist?" + urlencode({"q": name, "limit": 10})).get("data") or []
    same = [r for r in results if fold(r.get("name", "")) == fold(name)]
    return max(same, key=lambda r: r.get("nb_fan") or 0)["id"] if same else None


def related(name: str, get: Callable = _get, fetch: bool = True) -> list[dict] | None:
    """Deezer's related artists of an artist, best first, [{id, name, fans}]; [] when Deezer does not know it,
    None when not looked up yet and fetch is off."""
    with _lock:
        entry = _load()["artists"].get(key(name))
    if not _fresh(entry):
        if not fetch:
            return None
        artist_id = _find_id(name, get)
        found = (get(f"{SEARCH_URL}/artist/{artist_id}/related?limit={RELATED}").get("data") or []) if artist_id else []
        entry = {"at": time.time(), "id": artist_id,
                 "related": [{"id": a["id"], "name": a["name"], "fans": a.get("nb_fan") or 0} for a in found]}
        if not artist_id:
            entry["missing"] = True
        with _lock:
            _load()["artists"][key(name)] = entry
            _save()
    return entry["related"]


def top_tracks(artist_id: int, get: Callable = _get, fetch: bool = True) -> list[dict] | None:
    """An artist's most played tracks on Deezer, [{title, artist, album, link}], or None when not looked up yet and
    fetch is off. Previews are not kept: their addresses expire."""
    with _lock:
        entry = _load()["tracks"].get(str(artist_id))
    if not _fresh(entry):
        if not fetch:
            return None
        found = get(f"{SEARCH_URL}/artist/{artist_id}/top?limit={TOP_TRACKS_READ}").get("data") or []
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


def score(seed_list: list[dict], related_of: dict[str, list[dict]], played: set[str]) -> list[dict]:
    """Rank the related artists not played yet: each seed adds its weight, scaled down the lower the artist is in
    its list, so an artist close to several of the seeds wins. Picked one at a time, and each pick lowers what its
    seeds add to the rest (SEED_DECAY), so the suggestions reach beyond the most played artists. Each gets the
    seeds that suggested it, most first."""
    shares: dict[int, dict] = {}
    for seed in seed_list:
        candidates = related_of.get(seed["key"]) or []
        for place, artist in enumerate(candidates):
            if fold(artist["name"]) in played:
                continue
            entry = shares.setdefault(artist["id"], {**artist, "shares": {}})
            share = seed["weight"] * (1 - place / max(len(candidates), RELATED))
            entry["shares"][seed["name"]] = entry["shares"].get(seed["name"], 0.0) + share
    used = {seed["name"]: 0 for seed in seed_list}
    ranked = []
    while shares:
        value = lambda a: sum(share * SEED_DECAY ** used[name] for name, share in a["shares"].items())
        best = max(shares.values(), key=lambda a: (value(a), a["fans"]))
        del shares[best["id"]]
        because = sorted(best["shares"], key=lambda n: -best["shares"][n])
        ranked.append({"id": best["id"], "name": best["name"], "fans": best["fans"], "score": round(value(best), 3),
                       "because": because})
        for name in best["shares"]:
            used[name] += 1
    return ranked


def suggestions(limit: int = 12, fetch: bool = True, get: Callable = _get, now: datetime | None = None,
                db_path: Path = DB_PATH) -> dict:
    """{artists, complete}: the artists to discover with their top tracks, best first. Without fetch only what is
    cached is used, and complete says whether anything is still to be looked up."""
    seed_list = seeds(now, db_path=db_path)
    complete = True
    related_of: dict[str, list[dict]] = {}
    for seed in seed_list:
        try:
            found = related(seed["name"], get, fetch)
        except Exception:  # offline or Deezer unavailable: tried again next time
            found = None
        if found is None:
            complete = False
        related_of[seed["key"]] = found or []
    artists = score(seed_list, related_of, heard(db_path))[:limit]
    for artist in artists:
        try:
            tracks = top_tracks(artist["id"], get, fetch)
        except Exception:
            tracks = None
        if tracks is None:
            complete = False
        artist["tracks"] = tracks or []
    return {"artists": artists, "complete": complete}
