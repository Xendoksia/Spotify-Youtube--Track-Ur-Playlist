"""
Album covers and artist photos for the listening statistics, cached in the artwork folder.

Covers are saved from Windows' media controls while a song plays (see nowplaying.py).
Missing covers and artist photos are looked up once on Deezer's public search, which needs
no account; only the artist and track names are sent. Images need the Pillow package;
without it the statistics show placeholders.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import ssl
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from playlist_tracker.core.config import BASE_DIR
from playlist_tracker.music import listening
from playlist_tracker.music.listening import key, name_variants

try:
    from PIL import Image
except ImportError:
    Image = None

ART_DIR = BASE_DIR / "artwork"
SEARCH_URL = "https://api.deezer.com"
SAVED_SIZE = 300
# A lookup that found nothing is tried again after this long
RETRY_SECONDS = 7 * 24 * 3600
# Deezer returns this placeholder path for artists without a photo
EMPTY_PICTURE = "/images/artist//"
# Misses from before collaborations were also searched by their main artist (2026-11-12) are tried again
MAIN_ARTIST_SEARCH = 1794486975

# One context for every download: building it reads the whole certificate store each time.
# Some Windows certificate stores still hold an expired root that Wikidata's chain runs into,
# so certifi's up to date list is used when it is installed
try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()

available = Image is not None


def _path(kind: str, name: str) -> Path:
    return ART_DIR / kind / (hashlib.sha1(name.encode("utf-8")).hexdigest()[:24] + ".jpg")


def cover_path(artist: str, album: str, name: str) -> Path:
    # Tracks of one album share its cover, so it is stored once per album
    return _path("covers", f"{key(artist)}|{key(album)}" if album else f"{key(artist)}||{key(name)}")


def artist_path(artist: str) -> Path:
    return _path("artists", key(artist))


def save_image(data: bytes, path: Path) -> bool:
    if not available:
        return False
    try:
        image = Image.open(io.BytesIO(data)).convert("RGB")
    except OSError:
        return False
    image.thumbnail((SAVED_SIZE, SAVED_SIZE))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=88)
    return True


def _missing_marker(path: Path) -> Path:
    return path.with_suffix(".none")


def _recently_missed(path: Path) -> bool:
    marker = _missing_marker(path)
    if not marker.exists():
        return False
    missed = marker.stat().st_mtime
    return missed >= MAIN_ARTIST_SEARCH and time.time() - missed < RETRY_SECONDS


def _get(url: str, as_json: bool = True):
    request = urllib.request.Request(url, headers={"User-Agent": "PlaylistTracker/1.0"})
    with urllib.request.urlopen(request, timeout=20, context=SSL_CONTEXT) as response:
        return json.load(response) if as_json else response.read()


def _search(path: str, query: str) -> list[dict]:
    return _get(f"{SEARCH_URL}{path}?" + urllib.parse.urlencode({"q": query, "limit": 5})).get("data") or []


def _plain_title(name: str) -> str:
    """Drop version notes such as " - Remastered 2026" or " (Deluxe)" that other catalogs spell differently."""
    return re.sub(r"\s*(\(.*?\)|\[.*?\])", "", name.split(" - ")[0]).strip() or name


def _find_cover(artist: str, name: str) -> str | None:
    # A collaboration such as "Pera, Işıl Ayman" is under its main artist at Deezer, so that is searched second
    for who in name_variants(artist):
        for title in dict.fromkeys((name, _plain_title(name))):
            results = _search("/search", f'artist:"{who}" track:"{title}"') or _search("/search", f"{who} {title}")
            for result in results:
                if key((result.get("artist") or {}).get("name", "")) == key(who):
                    return (result.get("album") or {}).get("cover_big")
    return None


def _find_artist_photo(artist: str) -> str | None:
    # A collaboration gets its main artist's photo
    for who in name_variants(artist):
        for result in _search("/search/artist", who):
            picture = result.get("picture_big") or ""
            if key(result.get("name", "")) == key(who) and EMPTY_PICTURE not in picture:
                return picture
    return None


_fetch_locks: dict[Path, threading.Lock] = {}
_fetch_locks_lock = threading.Lock()


def _fetch_now(path: Path, find: Callable[[], str | None]) -> Path | None:
    """The cached image, or downloaded now on the calling thread; None when there is none (also recently)."""
    with _fetch_locks_lock:
        lock = _fetch_locks.setdefault(path, threading.Lock())
    # One download per image when several requests ask for it at once
    with lock:
        if path.exists():
            return path
        if not available or _recently_missed(path):
            return None
        try:
            url = find()
            if url and save_image(_get(url, as_json=False), path):
                return path
            path.parent.mkdir(parents=True, exist_ok=True)
            _missing_marker(path).touch()
        except Exception:  # offline or Deezer unavailable: try again next time
            pass
        return None


def fetch_cover(artist: str, album: str, name: str) -> Path | None:
    return _fetch_now(cover_path(artist, album, name), lambda: _find_cover(artist, name))


def fetch_artist(artist: str) -> Path | None:
    return _fetch_now(artist_path(artist), lambda: _find_artist_photo(artist))


TRACKLISTS_PATH = ART_DIR / "tracklists.json"
_tracklists: dict | None = None
_tracklists_lock = threading.Lock()


def _load_tracklists() -> dict:
    global _tracklists
    if _tracklists is None:
        try:
            _tracklists = json.loads(TRACKLISTS_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _tracklists = {}
    return _tracklists


def cached_tracklist(artist: str, album: str) -> list[dict] | None:
    """The tracks of an album looked up before ([] when Deezer did not have it), or None when not yet."""
    with _tracklists_lock:
        entry = _load_tracklists().get(f"{key(artist)}|{key(album)}")
    missing = entry and entry.get("missing")
    if entry is None or (missing and (missing < MAIN_ARTIST_SEARCH or time.time() - missing > RETRY_SECONDS)):
        return None
    return entry.get("tracks", [])


def fetch_tracklist(artist: str, album: str) -> None:
    """Look up the tracks of an album on Deezer (title and length, in album order) and cache them."""
    tracks = None
    for who, title in ((who, title) for who in name_variants(artist)
                       for title in dict.fromkeys((album, _plain_title(album)))):
        results = (_search("/search/album", f'artist:"{who}" album:"{title}"')
                   or _search("/search/album", f"{who} {title}"))
        for result in results:
            if (key((result.get("artist") or {}).get("name", "")) == key(who)
                    and key(_plain_title(result.get("title", ""))) == key(_plain_title(album))):
                data = _get(f"{SEARCH_URL}/album/{result['id']}/tracks?limit=200").get("data") or []
                tracks = [{"title": t["title"], "ms": (t.get("duration") or 0) * 1000} for t in data]
                break
        if tracks:
            break
    entry = {"tracks": tracks} if tracks else {"missing": time.time()}
    with _tracklists_lock:
        _load_tracklists()[f"{key(artist)}|{key(album)}"] = entry
        TRACKLISTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        TRACKLISTS_PATH.write_text(json.dumps(_tracklists, ensure_ascii=False), encoding="utf-8")


def same_title(a: str, b: str) -> bool:
    """Whether two track titles are the same song, apart from version notes."""
    return key(_plain_title(a)) == key(_plain_title(b))


def find_length(artist: str, name: str) -> int | None:
    """The length of a track in milliseconds from Deezer, or None."""
    for title in dict.fromkeys((name, _plain_title(name))):
        results = _search("/search", f'artist:"{artist}" track:"{title}"') or _search("/search", f"{artist} {title}")
        for result in results:
            # Only the same track: same artist and the same title apart from version notes
            if (key((result.get("artist") or {}).get("name", "")) == key(artist) and result.get("duration")
                    and key(_plain_title(result.get("title", ""))) == key(_plain_title(name))):
                return result["duration"] * 1000
    return None


def fill_missing_lengths(done: Callable[[], None]) -> None:
    """Give plays stored without a listening time (by an earlier version) their track's length, so they
    count in the listening time; the longest time recorded for the track is used when Deezer has none.
    Runs once on a background thread; done is called when something changed."""
    changed = False
    for track in listening.plays_without_length():
        try:
            length = find_length(track["artist"], track["name"])
        except Exception:  # offline: tried again next start
            continue
        listening.set_missing_length(track["key"], length or track["known_ms"] or 0)
        changed = True
    if changed:
        done()
