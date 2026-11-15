"""
The two playlist services side by side, and the names of history events. The window picks their colors.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from playlist_tracker.core.i18n import t
from playlist_tracker.playlists import history, spotify, youtube

EVENTS = (history.EVENT_ADDED, history.EVENT_REMOVED, history.EVENT_UNPLAYABLE, history.EVENT_PLAYABLE,
          history.EVENT_INITIAL)


def event_label(event: str) -> str:
    return t(f"event.{event}") if event in EVENTS else event


@dataclass
class Service:
    name: str
    db_path: Path
    connect: Callable
    parse_playlist_id: Callable[[str], str]
    playlist_url: str
    items: str
    login_required: type
    has_credentials: Callable[[dict], bool]
    session_user: Callable[[dict], "str | None"]
    account: str

    @property
    def key(self) -> str:
        return self.name.lower()


SPOTIFY = Service(
    name="Spotify", db_path=spotify.DB_PATH, connect=spotify.connect, parse_playlist_id=spotify.parse_playlist_id,
    playlist_url="https://open.spotify.com/playlist/{}", items="tracks", login_required=spotify.LoginRequired,
    has_credentials=lambda c: bool(c.get("CLIENT_ID") and c.get("CLIENT_SECRET")),
    session_user=lambda c: c.get("USER", "") if c.get("REFRESH_TOKEN") else None,
    account="Spotify",
)
YOUTUBE = Service(
    name="YouTube", db_path=youtube.DB_PATH, connect=youtube.connect, parse_playlist_id=youtube.parse_playlist_id,
    playlist_url=youtube.PLAYLIST_URL, items="videos", login_required=youtube.LoginRequired,
    has_credentials=youtube.has_credentials,
    session_user=lambda c: c.get("YOUTUBE_USER", "") if c.get("YOUTUBE_REFRESH_TOKEN") else None,
    account="Google",
)
SERVICES = (SPOTIFY, YOUTUBE)
