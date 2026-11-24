"""
Artists and songs to discover (music/recommend.py) for the window's Discover section. They are worked out once a
day and saved. When Deezer still had something to look up, it is looked up on a background thread, at most once
an hour, after which arrived() lets the window ask again.
"""

from __future__ import annotations

import threading
import time
from typing import Callable
from urllib.parse import quote

from playlist_tracker.api.overview import artist_url, cover_url
from playlist_tracker.core.i18n import number, t
from playlist_tracker.music import listening, recommend

LIMIT = 12
SONG_LIMIT = 10
# An incomplete answer (Deezer unreachable) is tried again after this long, not on every visit
LOOKUP_RETRY_SECONDS = 3600

_lookup: threading.Thread | None = None
_lookup_lock = threading.Lock()
_looked_up_at = 0.0


def because_text(names: list[str], songs: bool = False) -> str:
    """Why an artist or song is suggested: the artists or songs played that led to it, at most two by name."""
    if len(names) == 1:
        return t("recommend.because_one", first=names[0])
    if len(names) == 2:
        return t("recommend.because_two", first=names[0], second=names[1])
    return t("recommend.because_more_songs" if songs else "recommend.because_more",
             first=names[0], second=names[1], count=number(len(names) - 2))


def spotify_search(*words: str) -> str:
    return "https://open.spotify.com/search/" + quote(" ".join(w for w in words if w))


def _look_up(arrived: Callable[[], None]) -> None:
    global _lookup
    try:
        recommend.discover(LIMIT, SONG_LIMIT, fetch=True, force=True)
    finally:
        with _lookup_lock:
            _lookup = None
    arrived()


def _song(song: dict, played_artist: bool) -> dict:
    first = listening._credit_parts(song["artist"])[0]
    return {
        "title": song["name"], "subtitle": song["artist"], "because": because_text(song["because"], songs=True),
        "image": cover_url(song["artist"], "", song["name"]),
        "link": spotify_search(song["artist"], song["name"]),
        # A song of an artist played opens that artist's page
        "artist_key": listening.key(first) if played_artist else None,
    }


def recommendations(arrived: Callable[[], None]) -> dict:
    """{title, artists, new_songs, known_songs, loading, empty}: the suggested artists with the reason and their
    top tracks, and the suggested songs by new artists and by artists played."""
    global _lookup, _looked_up_at
    found = recommend.discover(LIMIT, SONG_LIMIT)
    looking = False
    if not found["complete"]:
        with _lookup_lock:
            if _lookup is None and time.time() - _looked_up_at >= LOOKUP_RETRY_SECONDS:
                _looked_up_at = time.time()
                _lookup = threading.Thread(target=_look_up, args=(arrived,), name="recommend", daemon=True)
                _lookup.start()
            looking = _lookup is not None
    songs = found
    return {
        "title": t("recommend.title"), "empty": t("recommend.none"), "loading": looking,
        "artists": [{
            "title": a["name"], "subtitle": because_text(a["because"]), "because": a["because"],
            "image": artist_url(a["name"]), "round": True, "link": spotify_search(a["name"]),
            "tracks": [{"title": tr["title"], "subtitle": tr["artist"],
                        "image": cover_url(tr["artist"], tr["album"], tr["title"]),
                        "link": spotify_search(tr["artist"], tr["title"]), "deezer": tr["link"]}
                       for tr in a["tracks"]],
        } for a in found["artists"]],
        "new_songs": [_song(s, False) for s in songs["new"]],
        "known_songs": [_song(s, True) for s in songs["known"]],
    }
