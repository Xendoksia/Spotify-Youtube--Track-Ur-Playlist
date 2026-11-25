"""
Artists and songs to discover (music/recommend.py) for the window's Discover section. They are worked out once a
day and saved. When Deezer still had something to look up, it is looked up on a background thread, at most once
an hour, after which arrived() lets the window ask again.
"""

from __future__ import annotations

import os
import threading
import time
import webbrowser
from typing import Callable
from urllib.parse import quote, urlencode

from playlist_tracker.api.overview import artist_url, cover_url
from playlist_tracker.core.i18n import number, t
from datetime import date

from playlist_tracker.music import listening, recommend
from playlist_tracker.music.text import month_name
from playlist_tracker.music.model import loose

# The closest artist and two rows of five tiles
LIMIT = 11
SONG_LIMIT = 10
# A preview's address is signed for a while, so it is kept this long
PREVIEW_SECONDS = 30 * 60
# An incomplete answer (Deezer unreachable) is tried again after this long, not on every visit
LOOKUP_RETRY_SECONDS = 3600

_lookup: threading.Thread | None = None
_lookup_lock = threading.Lock()
_looked_up_at = 0.0
_previews: dict[tuple[str, str], tuple[str | None, float]] = {}


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


# What a suggestion opened in Spotify, (artist, title) → spotify: address, for the run of the program
_uris: dict[tuple[str, str], str] = {}


def _spotify_app() -> bool:
    """Whether the Spotify desktop app is installed: it opens spotify: addresses. Only what it plays is recorded
    (music/nowplaying.py), so a suggestion played in the browser would not count."""
    try:
        import winreg
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "spotify"))
        return True
    except OSError:
        return False


def spotify_uri(artist: str, title: str = "") -> str:
    """The suggestion's own spotify:track: or spotify:artist: address, found with the Spotify account the playlists
    use, or a spotify:search: address without one."""
    if (artist, title) in _uris:
        return _uris[(artist, title)]
    from playlist_tracker.playlists import spotify
    kind = "track" if title else "artist"
    query = f'track:"{title}" artist:"{artist}"' if title else f'artist:"{artist}"'
    found = f"spotify:search:{quote(' '.join(w for w in (artist, title) if w))}"
    try:
        answer = spotify.connect().get("/search?" + urlencode({"q": query, "type": kind, "limit": 5}))
        items = answer[f"{kind}s"]["items"]
        wanted = loose(recommend.fold(listening._credit_parts(artist)[0]))
        names = lambda item: item.get("artists") or [item]
        same = [i for i in items if any(loose(recommend.fold(a.get("name", ""))) == wanted for a in names(i))]
        if same:
            found = same[0]["uri"]
    except Exception:  # no Spotify account, or offline: Spotify's own search is opened
        pass
    _uris[(artist, title)] = found
    return found


def open_spotify(artist: str, title: str = "") -> dict:
    """Open a suggested artist or song in the Spotify app, where playing it is recorded, or in the browser when
    the app is not installed."""
    uri = spotify_uri(artist, title)
    if _spotify_app():
        os.startfile(uri)
        return {"opened": "app"}
    kind, _, rest = uri.removeprefix("spotify:").partition(":")
    webbrowser.open(f"https://open.spotify.com/{kind}/{rest}")
    return {"opened": "browser"}


def preview(artist: str, title: str) -> dict:
    """The address of a suggested song's 30 second preview on Deezer, played in the window, or None."""
    now = time.monotonic()
    url, at = _previews.get((artist, title), (None, -PREVIEW_SECONDS))
    if now - at >= PREVIEW_SECONDS:
        from playlist_tracker.music import artwork
        try:
            url = artwork.find_preview(artist, title)
        except Exception:  # offline or Deezer's rate limit: asked again on the next click
            return {"url": None}
        _previews[(artist, title)] = (url, now)
    return {"url": url}


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
        "artist_image": artist_url(first),
        "link": spotify_search(song["artist"], song["name"]),
        # A song of an artist played opens that artist's page
        "artist_key": listening.key(first) if played_artist else None,
    }


def _day(day: str) -> str:
    moment = date.fromisoformat(day)
    return f"{moment.day} {month_name(moment.month, short=True)}"


def discovery_report() -> dict | None:
    """The discovery report for the page: which suggested artists were played since, None before any."""
    found = recommend.report()
    if not found["suggested"]:
        return None
    summary = t("discover.report.summary", listened=number(found["listened"]), suggested=number(found["suggested"]))
    if found["favorites"]:
        summary += t("discover.report.favorites", count=number(found["favorites"]))
    return {
        "title": t("discover.report.title"), "summary": summary,
        "suggested": found["suggested"], "listened": found["listened"], "favorites": found["favorites"],
        "rows": [{
            "title": r["name"], "image": artist_url(r["name"]), "state": r["state"],
            "state_text": t(f"discover.report.{r['state']}"),
            "detail": t("discover.report.plays", count=number(r["plays"])) if r["plays"] else
            t("discover.report.since", day=_day(r["day"])),
            "artist_key": listening.key(r["name"]) if r["plays"] else None,
        } for r in found["rows"]],
        "days_title": t("discover.report.days"),
        "days": [{"label": _day(d["day"]), "artists": [{"title": n, "image": artist_url(n)} for n in d["names"]]}
                 for d in found["days"][:7]],
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
        } for a in found["artists"][:LIMIT]],
        "new_songs": [_song(s, False) for s in songs["new"]],
        "known_songs": [_song(s, True) for s in songs["known"]],
        "report": discovery_report(),
    }
