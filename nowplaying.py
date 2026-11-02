"""
Records what the Spotify desktop app plays on this computer, without the Spotify API.

The current track is read from Windows' media controls (the same info as the media
overlay shown by the volume keys). When the winrt package is not installed, the title of
the Spotify window ("Artist - Song") is used instead. A track counts as played once it has
been listening for 30 seconds, like on Spotify, and the time actually listened is stored.
"""

from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import listening

POLL_SECONDS = 3
# Recorded listening time of a running play is written at most this often
SAVE_EVERY_MS = 30_000
# A tick longer than this means the computer slept, so the gap is not counted as listening
MAX_TICK_MS = POLL_SECONDS * 3 * 1000
# Window titles Spotify shows when nothing is playing (paused, ads)
IDLE_TITLES = {"spotify", "spotify free", "spotify premium", "advertisement", "spotify advertisement"}


@dataclass
class Snapshot:
    artist: str
    title: str
    album: str
    playing: bool
    position_ms: int | None = None

    @property
    def key(self) -> str:
        return listening.key(self.artist) + "|" + listening.key(self.title)


try:
    import asyncio

    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as SessionManager
    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status
except ImportError:
    SessionManager = None


async def _read_media_session() -> Snapshot | None:
    manager = await SessionManager.request_async()
    for session in manager.get_sessions():
        if "spotify" not in (session.source_app_user_model_id or "").lower():
            continue
        props = await session.try_get_media_properties_async()
        playing = session.get_playback_info().playback_status == Status.PLAYING
        timeline = session.get_timeline_properties()
        position = timeline.position.total_seconds() * 1000
        if playing:
            # Windows only updates the position on events, so add the time since the last update
            position += (datetime.now(timezone.utc) - timeline.last_updated_time).total_seconds() * 1000
        return Snapshot(props.artist or "", props.title or "", props.album_title or "", playing, int(position))
    return None


def _read_window_title() -> Snapshot | None:
    import ctypes
    from ctypes import wintypes

    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    titles = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        length = user32.GetWindowTextLengthW(hwnd)
        if not length or not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
        if process:
            path = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(path))
            if kernel32.QueryFullProcessImageNameW(process, 0, path, ctypes.byref(size)) \
                    and path.value.lower().endswith("spotify.exe"):
                text = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, text, length + 1)
                titles.append(text.value)
            kernel32.CloseHandle(process)
        return True

    user32.EnumWindows(visit, 0)
    for text in titles:
        artist, separator, title = text.partition(" - ")
        if separator and text.lower() not in IDLE_TITLES:
            return Snapshot(artist.strip(), title.strip(), "", True)
    # Spotify is open but shows its own name: paused or an ad
    return Snapshot("", "", "", False) if titles else None


def read() -> Snapshot | None:
    """Return what Spotify plays right now, or None when Spotify is not running."""
    if SessionManager is not None:
        return asyncio.run(_read_media_session())
    if sys.platform == "win32":
        return _read_window_title()
    return None


class LocalTracker:
    """Polls Spotify on a background thread and records plays in listening.db."""

    def __init__(self):
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._play: dict | None = None
        self._last_tick = 0.0
        self.state = "off"
        self.error: str | None = None
        # Increases whenever a play is stored, so the interface knows when to reload its list
        self.version = 0

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self.state = "idle"
        self._last_tick = time.monotonic()
        self._thread = threading.Thread(target=self._run, name="local-tracker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop polling and save the listening time of the current play."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=POLL_SECONDS * 2)
        with self._lock:
            self._finish()
        self.state = "off"

    def status(self) -> dict:
        with self._lock:
            play = dict(self._play) if self._play else None
        return {"state": self.state, "play": play, "error": self.error}

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                snapshot = read()
                self.error = None
            except Exception as error:  # a broken media session must not stop tracking for good
                snapshot, self.error = None, repr(error)
            with self._lock:
                self._tick(snapshot)
            self._stop.wait(POLL_SECONDS)

    def _tick(self, snapshot: Snapshot | None) -> None:
        now = time.monotonic()
        elapsed_ms = int((now - self._last_tick) * 1000)
        self._last_tick = now
        play = self._play

        if snapshot is None:
            self._finish()
            self.state = "idle"
            return
        if not snapshot.title or not snapshot.artist:
            # Paused or an ad: keep the current play so resuming continues it
            self.state = "paused" if play else "idle"
            return

        restarted = (play and play["key"] == snapshot.key and play["ms"] >= listening.MIN_PLAY_MS
                     and snapshot.position_ms is not None and play["position"] is not None
                     and snapshot.position_ms + 5000 < play["position"] and snapshot.position_ms < 15000)
        if play and (play["key"] != snapshot.key or restarted):
            self._finish()
            play = None
        if play is None:
            started = datetime.now(timezone.utc)
            if snapshot.position_ms is not None and snapshot.position_ms < 15 * 60 * 1000:
                started -= timedelta(milliseconds=snapshot.position_ms)
            play = self._play = {
                "key": snapshot.key, "artist": snapshot.artist, "name": snapshot.title,
                "album": snapshot.album, "played_at": listening.to_utc(started),
                "ms": 0, "saved_ms": 0, "id": None, "position": snapshot.position_ms,
            }
            elapsed_ms = 0

        if snapshot.playing:
            play["ms"] += min(elapsed_ms, MAX_TICK_MS)
        play["position"] = snapshot.position_ms
        if not play["album"] and snapshot.album:
            play["album"] = snapshot.album
        self.state = "playing" if snapshot.playing else "paused"

        if play["ms"] >= listening.MIN_PLAY_MS and play["id"] is None:
            play["id"] = listening.record_local(play) or 0  # 0: already known from the data export
            play["saved_ms"] = play["ms"]
            self.version += 1
        elif play["id"] and play["ms"] - play["saved_ms"] >= SAVE_EVERY_MS:
            self._save(play)

    def _save(self, play: dict) -> None:
        if play["id"]:
            listening.update_local(play["id"], play["ms"])
            play["saved_ms"] = play["ms"]
            self.version += 1

    def _finish(self) -> None:
        if self._play:
            self._save(self._play)
            self._play = None
