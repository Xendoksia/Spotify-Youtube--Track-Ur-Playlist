"""
The styles of a track from Discogs, where every album and single carries them ("Metalcore", "Thrash"), finer
than its genres ("Rock"). Tracks have none of their own, so a track takes the styles of its album, or of a single
of its name when the album is not found. Regional names of pop ("Europop", "K-Pop") count as pop.

Discogs' search needs no account (25 requests a minute). Only the artist's name and the album or track title are
sent. Found styles are cached in artwork/styles.json, keyed by artist and album (or track when there is no album).
"""

from __future__ import annotations

import json
import queue
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

from playlist_tracker.music import artist_info
from playlist_tracker.music.artwork import ART_DIR, RETRY_SECONDS, SSL_CONTEXT
from playlist_tracker.music.listening import key, name_variants

CACHE_PATH = ART_DIR / "styles.json"
SEARCH_URL = "https://api.discogs.com/database/search"
USER_AGENT = "SpotifyPlaylistTracker/1.0 +https://github.com/Xendoksia/Spotify-Youtube--Track-Ur-Playlist"
# Discogs allows 25 requests a minute without an account
REQUEST_GAP = 2.5
# Shown on a track's and an album's page
SHOWN = 2
REGIONAL_POP = re.compile(r"(euro|j|k|c|italo|latin|turkish|arabic|french|thai|indo|canto|mando)[- ]?pop")

_lock = threading.Lock()
_cache: dict | None = None
_queue: queue.Queue = queue.Queue()
_waiting: dict[str, list[Callable[[], None]]] = {}
_worker: threading.Thread | None = None
_last_request = 0.0


def plain(style: str) -> str:
    """A style as the genre share counts it: regional names of pop are pop."""
    return "Pop" if REGIONAL_POP.fullmatch(style.strip().lower()) else style


def styles_of(found: list[str]) -> list[str]:
    """Styles in Discogs' order, plain and without repeats."""
    result: list[str] = []
    for style in map(plain, found):
        if all(key(style) != key(other) for other in result):
            result.append(style)
    return result


def release_key(artist_key: str, album: str | None, name: str) -> str:
    return f"{artist_key}|{key(_title(album or name))}"


def _title(title: str) -> str:
    """A title without version notes such as " - Remastered" or " (Deluxe Edition)", as Discogs names it."""
    return re.sub(r"\s*(\(.*?\)|\[.*?\])", "", (title or "").split(" - ")[0]).strip()


def _same(found: str, wanted: str) -> bool:
    """Names compared without punctuation ("..." and "…") and Discogs' number for a same named artist ("(2)")."""
    def loose(text: str) -> str:
        return re.sub(r"\W+", "", key(re.sub(r"\s*\(\d+\)$", "", text.strip().rstrip("*"))))
    return loose(found) == loose(wanted)


def _load() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _cache = {}
    return _cache


def _save() -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = CACHE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(_cache, ensure_ascii=False), encoding="utf-8")
    temporary.replace(CACHE_PATH)


def _search(**params) -> list[dict]:
    global _last_request
    url = f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"
    for attempt in range(3):
        wait = _last_request + REQUEST_GAP - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=20, context=SSL_CONTEXT) as response:
                return json.load(response).get("results") or []
        except urllib.error.HTTPError as error:
            # 429 means too many requests in the last minute
            if error.code != 429 or attempt == 2:
                raise
            time.sleep(REQUEST_GAP * 4 * (attempt + 1))
        finally:
            _last_request = time.monotonic()
    return []


def _look_up(artist: str, album: str | None, name: str) -> dict:
    """The styles of the album, else of a single named as the track; results of another artist are skipped."""
    searches = [(album, "master"), (album, "release")] if album else []
    searches.append((name, "release"))
    for title, kind in searches:
        title = _title(title)
        if not title:
            continue
        for artist_name in name_variants(artist):
            for result in _search(artist=artist_name, release_title=title, type=kind, per_page=5):
                found_artist, _, found_title = (result.get("title") or "").partition(" - ")
                if _same(found_artist, artist_name) and _same(_title(found_title), title) and result.get("style"):
                    return {"styles": styles_of(result["style"])}
    return {"missing": time.time()}


def _work():
    while True:
        release, artist, album, name = _queue.get()
        try:
            found = _look_up(artist, album, name)
        except Exception:  # offline or Discogs unavailable: asked again next time
            found = None
        with _lock:
            if found is not None:
                _load()[release] = found
                _save()
            callbacks = _waiting.pop(release, [])
        if found is not None:
            for done in callbacks:
                try:
                    done()
                except Exception:  # one listener's failure must not stop the others or the lookups
                    pass


def cached(artist_key: str, album: str | None, name: str) -> list[str] | None:
    """The styles already found; None while unknown or not found."""
    with _lock:
        found = _load().get(release_key(artist_key, album, name))
    return found["styles"] if found and "styles" in found else None


def waiting(artist_key: str, album: str | None, name: str) -> bool:
    with _lock:
        return release_key(artist_key, album, name) in _waiting


def request(artist: str, artist_key: str, album: str | None, name: str, done: Callable[[], None]) -> list[str] | None:
    """Return the cached styles, or look them up in the background and call done on the lookup thread."""
    global _worker
    release = release_key(artist_key, album, name)
    with _lock:
        found = _load().get(release)
        if found is not None and ("missing" not in found or time.time() - found["missing"] < RETRY_SECONDS):
            return found.get("styles")
        callbacks = _waiting.setdefault(release, [])
        if not callbacks:
            _queue.put((release, artist, album, name))
        if done not in callbacks:
            callbacks.append(done)
        if _worker is None:
            _worker = threading.Thread(target=_work, name="styles", daemon=True)
            _worker.start()
    return None


def genre(release: dict, arrived: Callable[[], None] | None = None) -> tuple[str | None, bool]:
    """The main genre of a release_plays row (an album's or a track's plays): its first style, else its artist's
    main genre from MusicBrainz. With arrived, unknown ones are looked up in the background and (None, True)
    tells one is still being looked up. Without it, only what is known counts."""
    album = release["album"] or None
    if arrived:
        found = request(release["artist"], release["artist_key"], album, release["name"], arrived)
        if found is None and waiting(release["artist_key"], album, release["name"]):
            return None, True
        if found:
            return found[0], False
        facts = artist_info.request(release["artist"], release["artist_key"], arrived, priority=artist_info.LATER)
        if facts is None and artist_info.waiting(release["artist_key"]):
            return None, True
    else:
        found = cached(release["artist_key"], album, release["name"])
        if found:
            return found[0], False
        facts = artist_info.cached(release["artist_key"])
    return (facts["genres"][0] if facts and facts["genres"] else None), False
