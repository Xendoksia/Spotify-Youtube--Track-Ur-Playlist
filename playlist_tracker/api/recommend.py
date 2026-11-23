"""
Artists and tracks to discover (music/recommend.py) for the window. The answer comes from what is cached at once,
and what is missing is looked up on a background thread, after which arrived() lets the window ask again.
"""

from __future__ import annotations

import threading
from typing import Callable
from urllib.parse import quote

from playlist_tracker.api.overview import artist_url, cover_url
from playlist_tracker.core.i18n import number, t
from playlist_tracker.music import recommend

LIMIT = 12

_lookup: threading.Thread | None = None
_lookup_lock = threading.Lock()


def because_text(names: list[str]) -> str:
    """Why an artist is suggested: the artists played that led to it, at most two by name."""
    if len(names) == 1:
        return t("recommend.because_one", first=names[0])
    if len(names) == 2:
        return t("recommend.because_two", first=names[0], second=names[1])
    return t("recommend.because_more", first=names[0], second=names[1], count=number(len(names) - 2))


def spotify_search(*words: str) -> str:
    return "https://open.spotify.com/search/" + quote(" ".join(w for w in words if w))


def _look_up(arrived: Callable[[], None]) -> None:
    global _lookup
    try:
        recommend.suggestions(LIMIT, fetch=True)
    finally:
        with _lookup_lock:
            _lookup = None
    arrived()


def recommendations(arrived: Callable[[], None]) -> dict:
    """{title, artists, loading, empty}: the suggested artists with the reason and their top tracks."""
    global _lookup
    found = recommend.suggestions(LIMIT, fetch=False)
    if not found["complete"]:
        with _lookup_lock:
            if _lookup is None:
                _lookup = threading.Thread(target=_look_up, args=(arrived,), name="recommend", daemon=True)
                _lookup.start()
    return {
        "title": t("recommend.title"), "empty": t("recommend.none"), "loading": not found["complete"],
        "artists": [{
            "title": a["name"], "subtitle": because_text(a["because"]), "because": a["because"],
            "image": artist_url(a["name"]), "round": True, "link": spotify_search(a["name"]),
            "tracks": [{"title": tr["title"], "subtitle": tr["artist"],
                        "image": cover_url(tr["artist"], tr["album"], tr["title"]),
                        "link": spotify_search(tr["artist"], tr["title"]), "deezer": tr["link"]}
                       for tr in a["tracks"]],
        } for a in found["artists"]],
    }
