"""
The two playlist services side by side in the interface, and the colors and names of history events.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from playlist_tracker.core.config import market
from playlist_tracker.core.i18n import t
from playlist_tracker.playlists import history, spotify, youtube
from playlist_tracker.ui.theme import P

EVENTS = (history.EVENT_ADDED, history.EVENT_REMOVED, history.EVENT_UNPLAYABLE, history.EVENT_PLAYABLE,
          history.EVENT_INITIAL)
EVENT_COLOR_KEYS = {
    history.EVENT_ADDED: "added",
    history.EVENT_REMOVED: "removed",
    history.EVENT_UNPLAYABLE: "unplayable",
    history.EVENT_PLAYABLE: "playable",
    history.EVENT_INITIAL: "initial",
}


def event_label(event: str) -> str:
    return t(f"event.{event}") if event in EVENTS else event


def event_color(event: str) -> str:
    return getattr(P, EVENT_COLOR_KEYS[event])


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
    unavailable_label: Callable[[], str]
    account: str
    accent: str
    accent_active: str

    @property
    def key(self) -> str:
        return self.name.lower()

    @property
    def tint(self) -> str:
        return getattr(P, f"{self.key}_tint")


SPOTIFY = Service(
    name="Spotify", db_path=spotify.DB_PATH, connect=spotify.connect, parse_playlist_id=spotify.parse_playlist_id,
    playlist_url="https://open.spotify.com/playlist/{}", items="tracks", login_required=spotify.LoginRequired,
    has_credentials=lambda c: bool(c.get("CLIENT_ID") and c.get("CLIENT_SECRET")),
    session_user=lambda c: c.get("USER", "") if c.get("REFRESH_TOKEN") else None,
    unavailable_label=lambda: t("unavailable.spotify", market=market()),
    account="Spotify",
    accent="#1aa34a", accent_active="#168a3f",
)
YOUTUBE = Service(
    name="YouTube", db_path=youtube.DB_PATH, connect=youtube.connect, parse_playlist_id=youtube.parse_playlist_id,
    playlist_url=youtube.PLAYLIST_URL, items="videos", login_required=youtube.LoginRequired,
    has_credentials=youtube.has_credentials,
    session_user=lambda c: c.get("YOUTUBE_USER", "") if c.get("YOUTUBE_REFRESH_TOKEN") else None,
    unavailable_label=lambda: t("unavailable.youtube"),
    account="Google",
    accent="#e62117", accent_active="#c41b12",
)
SERVICES = (SPOTIFY, YOUTUBE)
