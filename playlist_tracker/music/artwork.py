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
import math
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


def fetch_video_thumbnail(video_id: str) -> Path | None:
    """A YouTube video's thumbnail, from YouTube's public image address (no account or key)."""
    if not re.fullmatch(r"[\w-]{6,20}", video_id or ""):
        return None
    return _fetch_now(_path("videos", video_id), lambda: f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg")


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


# The colors of a picture: the hue its vivid parts share most, as OKLCH so the window can set the lightness
_MOOD_BINS = 24


def _oklch(r: int, g: int, b: int) -> tuple[float, float, float]:
    def linear(c: int) -> float:
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = linear(r), linear(g), linear(b)
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    lightness = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    b = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return lightness, (a * a + b * b) ** 0.5, math.degrees(math.atan2(b, a)) % 360


# A second color of a picture: a hue at least this many bins from the first, with this share of its weight
_SECOND_APART = 3
_SECOND_SHARE = 0.15
# Without such a hue, its greys and whites are its second color when they cover this much of it
_NEUTRAL_SHARE = 0.2
_NEUTRAL_CHROMA = 0.015
# A mostly grey picture still lends its few colored pixels (a logo, a title) to the curves from this share
_ACCENT_SHARE = 0.01
_analyses: dict[tuple[Path, float], dict | None] = {}


def _group_hue(group: list[list]) -> float:
    return math.degrees(math.atan2(sum(s[1] for s in group), sum(s[2] for s in group))) % 360


def _analyse(path: Path | None) -> dict | None:
    """The picture's vivid pixels per hue (weight, sin and cos of the hue, highest chroma, pixels), its light
    enough grey and white pixels and all its pixels, or None for a missing picture."""
    if not available or path is None or not path.exists():
        return None
    cache_key = (path, path.stat().st_mtime)
    if cache_key in _analyses:
        return _analyses[cache_key]
    bins = [[0.0, 0.0, 0.0, 0.0, 0] for _ in range(_MOOD_BINS)]
    try:
        with Image.open(path) as image:
            pixels = image.convert("RGB").resize((40, 40)).getdata()
    except OSError:
        return None
    total = neutral = 0
    for r, g, b in pixels:
        lightness, chroma, hue = _oklch(r, g, b)
        total += 1
        # Near black, white or grey pixels say little about the picture's color
        if chroma < 0.04 or not 0.2 < lightness < 0.92:
            # Greys and whites can still be its second color; near black would vanish on the dark page
            if lightness > 0.35:
                neutral += 1
            continue
        slot = bins[int(hue / 360 * _MOOD_BINS) % _MOOD_BINS]
        slot[0] += chroma
        slot[1] += chroma * math.sin(math.radians(hue))
        slot[2] += chroma * math.cos(math.radians(hue))
        slot[3] = max(slot[3], chroma)
        slot[4] += 1
    _analyses[cache_key] = result = {"bins": bins, "neutral": neutral, "total": total}
    return result


def _colors(analysis: dict, least_share: float) -> dict | None:
    """{hue, chroma, hue2, chroma2, lift}: the most common vivid hue and the second color (another hue, or the
    greys as a faintly tinted grey, or None when the window should turn the first a little), or None when the
    first covers less than least_share of the picture."""
    bins, total = analysis["bins"], analysis["total"]
    weight = lambda i: sum(bins[(i + d) % _MOOD_BINS][0] for d in (-1, 0, 1))
    # A hue and its two neighbours together, so a color split over two bins still wins
    best = max(range(_MOOD_BINS), key=weight)
    group = [bins[(best + d) % _MOOD_BINS] for d in (-1, 0, 1)]
    if not total or sum(slot[4] for slot in group) / total <= least_share:
        return None
    hue = _group_hue(group)
    colors = {"hue": round(hue, 1), "chroma": round(min(0.16, max(s[3] for s in group)), 3),
              "hue2": None, "chroma2": None, "lift": _lift(hue)}
    apart = [i for i in range(_MOOD_BINS)
             if min((i - best) % _MOOD_BINS, (best - i) % _MOOD_BINS) >= _SECOND_APART]
    second = max(apart, key=weight)
    if weight(second) >= weight(best) * _SECOND_SHARE:
        second_group = [bins[(second + d) % _MOOD_BINS] for d in (-1, 0, 1)]
        colors.update(hue2=round(_group_hue(second_group), 1),
                      chroma2=round(min(0.16, max(s[3] for s in second_group)), 3))
    elif analysis["neutral"] / total >= _NEUTRAL_SHARE:
        colors.update(hue2=colors["hue"], chroma2=_NEUTRAL_CHROMA)
    return colors


def _lift(hue: float) -> float:
    """How much lighter a yellow or olive hue is shown than the others: at the window's even lightness they turn
    to mustard and mud, most of all on the dark page."""
    return round(0.14 * max(0.0, 1 - abs(hue - 95) / 55), 3)


def mood(path: Path | None) -> dict | None:
    """The picture's colors as _colors gives them, or None for a grey or missing picture: a few colored pixels
    in a grey picture are not its color."""
    analysis = _analyse(path)
    return _colors(analysis, 0.06) if analysis else None


def palette(path: Path | None) -> dict | None:
    """The two colors of a page's curves: as mood(), but a mostly grey picture's few colored pixels count, with
    its greys as the second color. None for a picture without any color."""
    analysis = _analyse(path)
    return _colors(analysis, _ACCENT_SHARE) if analysis else None
