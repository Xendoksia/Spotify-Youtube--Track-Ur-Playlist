"""
Album covers and artist photos for the listening statistics, cached in the artwork folder.

Covers are saved from Windows' media controls while a song plays (see nowplaying.py).
Missing covers and artist photos are looked up once on Deezer's public search, which needs
no account; only the artist and track names are sent. Images need the Pillow package;
without it the statistics show placeholders.
"""

from __future__ import annotations

import colorsys
import hashlib
import io
import json
import re
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

import listening
from listening import key
from tracker import BASE_DIR

try:
    from PIL import Image, ImageDraw, ImageTk
except ImportError:
    Image = None

ART_DIR = BASE_DIR / "artwork"
SEARCH_URL = "https://api.deezer.com"
SAVED_SIZE = 300
# A lookup that found nothing is tried again after this long
RETRY_SECONDS = 7 * 24 * 3600
# Deezer returns this placeholder path for artists without a photo
EMPTY_PICTURE = "/images/artist//"

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
    return marker.exists() and time.time() - marker.stat().st_mtime < RETRY_SECONDS


def _get(url: str, as_json: bool = True):
    request = urllib.request.Request(url, headers={"User-Agent": "PlaylistTracker/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response) if as_json else response.read()


def _search(path: str, query: str) -> list[dict]:
    return _get(f"{SEARCH_URL}{path}?" + urllib.parse.urlencode({"q": query, "limit": 5})).get("data") or []


def _plain_title(name: str) -> str:
    """Drop version notes such as " - Remastered 2026" or " (Deluxe)" that other catalogs spell differently."""
    return re.sub(r"\s*(\(.*?\)|\[.*?\])", "", name.split(" - ")[0]).strip() or name


def _find_cover(artist: str, name: str) -> str | None:
    for title in dict.fromkeys((name, _plain_title(name))):
        results = _search("/search", f'artist:"{artist}" track:"{title}"') or _search("/search", f"{artist} {title}")
        for result in results:
            if key((result.get("artist") or {}).get("name", "")) == key(artist):
                return (result.get("album") or {}).get("cover_big")
    return None


def _find_artist_photo(artist: str) -> str | None:
    for result in _search("/search/artist", artist):
        picture = result.get("picture_big") or ""
        if key(result.get("name", "")) == key(artist) and EMPTY_PICTURE not in picture:
            return picture
    return None


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
    if entry is None or (entry.get("missing") and time.time() - entry["missing"] > RETRY_SECONDS):
        return None
    return entry.get("tracks", [])


def fetch_tracklist(artist: str, album: str) -> None:
    """Look up the tracks of an album on Deezer (title and length, in album order) and cache them."""
    tracks = None
    for title in dict.fromkeys((album, _plain_title(album))):
        results = (_search("/search/album", f'artist:"{artist}" album:"{title}"')
                   or _search("/search/album", f"{artist} {title}"))
        for result in results:
            if (key((result.get("artist") or {}).get("name", "")) == key(artist)
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


class Fetcher:
    """Downloads missing images in the background and reports back on the Tk thread."""

    def __init__(self, widget):
        self.widget = widget
        self._pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="artwork")
        self._pending: set[Path] = set()
        self._lock = threading.Lock()

    def cover(self, artist: str, album: str, name: str, done: Callable[[], None]) -> Path | None:
        path = cover_path(artist, album, name)
        return self._get_or_fetch(path, lambda: _find_cover(artist, name), done)

    def artist(self, artist: str, done: Callable[[], None]) -> Path | None:
        path = artist_path(artist)
        return self._get_or_fetch(path, lambda: _find_artist_photo(artist), done)

    def _get_or_fetch(self, path: Path, find: Callable[[], str | None], done) -> Path | None:
        if path.exists():
            return path
        if not available or _recently_missed(path):
            return None
        with self._lock:
            if path in self._pending:
                return None
            self._pending.add(path)
        self._pool.submit(self._fetch, path, find, done)
        return None

    def _fetch(self, path: Path, find, done):
        try:
            url = find()
            if url and save_image(_get(url, as_json=False), path):
                self.widget.after(0, done)
                return
            path.parent.mkdir(parents=True, exist_ok=True)
            _missing_marker(path).touch()
        except Exception:  # offline or Deezer unavailable: try again next time
            pass
        finally:
            with self._lock:
                self._pending.discard(path)


def photo(path: Path | None, size: int, background: str, round_: bool = False, radius: int = 6):
    """Return a Tk image of the file cropped to a square with rounded corners or a circle, or None."""
    result = picture(path, size, background, round_, radius)
    return ImageTk.PhotoImage(result) if result is not None else None


def picture(path: Path | None, size: int, background: str | None, round_: bool = False, radius: int = 6):
    """Like photo(), as a Pillow image; with no background the corners are transparent."""
    if not available or not path or not path.exists():
        return None
    try:
        image = Image.open(path).convert("RGB")
    except OSError:
        return None
    side = min(image.size)
    left, top = (image.width - side) // 2, (image.height - side) // 2
    image = image.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS)
    # The mask is drawn larger and scaled down so the edges are smooth
    scale = 4
    mask = Image.new("L", (size * scale, size * scale), 0)
    draw = ImageDraw.Draw(mask)
    if round_:
        draw.ellipse((0, 0, size * scale - 1, size * scale - 1), fill=255)
    else:
        draw.rounded_rectangle((0, 0, size * scale - 1, size * scale - 1), radius=radius * scale, fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)
    if background is None:
        image.putalpha(mask)
        return image
    result = Image.new("RGB", (size, size), background)
    result.paste(image, (0, 0), mask)
    return result


_colors: dict = {}


def colors(path: Path | None) -> tuple[tuple[int, int, int], tuple[int, int, int]] | None:
    """The two main colors of a picture as RGB, the more vivid and frequent first, or None."""
    if not available or not path or not path.exists():
        return None
    cache_key = (path, path.stat().st_mtime)
    if cache_key not in _colors:
        try:
            image = Image.open(path).convert("RGB").resize((48, 48))
        except OSError:
            return None
        quantized = image.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
        palette = quantized.getpalette()
        candidates = []
        for count, index in quantized.getcolors():
            rgb = tuple(palette[index * 3:index * 3 + 3])
            hue, saturation, value = colorsys.rgb_to_hsv(*(channel / 255 for channel in rgb))
            # Near black and near white say little about a cover; vivid colors say the most
            weight = 0.25 if value < 0.12 or (saturation < 0.08 and value > 0.92) else 1
            candidates.append((count * (0.15 + saturation) * weight, rgb))
        candidates.sort(reverse=True)
        first = candidates[0][1]
        # The second is the next one that clearly differs from the first, else a darker shade of it
        second = next((rgb for _, rgb in candidates[1:] if sum(abs(a - b) for a, b in zip(rgb, first)) > 90),
                      tuple(int(channel * 0.55) for channel in first))
        _colors[cache_key] = (first, second)
    return _colors[cache_key]
