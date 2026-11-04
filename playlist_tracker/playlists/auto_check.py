"""
Checks the tracked playlists by itself while the app runs (also in the tray), once their last check is
older than the interval chosen in the settings (AUTO_CHECK), and reports removed and unplayable tracks
in a notification. Tracks added to a playlist are not reported, as those are usually the user's own.

The thread sleeps between looks, so it costs nothing while waiting.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Callable

from playlist_tracker.core.config import load_config
from playlist_tracker.core.errors import TrackerError
from playlist_tracker.core.i18n import t
from playlist_tracker.playlists import history, spotify, youtube

# Hours between checks of a playlist; 0 turns the automatic check off
INTERVALS = {"off": 0, "6h": 6, "12h": 12, "24h": 24}
DEFAULT_INTERVAL = "24h"
SERVICES = (spotify, youtube)
# Service names as the window shows them, by module name
TITLES = {"spotify": "Spotify", "youtube": "YouTube"}
# Not right at startup, while the app and Windows are still busy starting
FIRST_LOOK_SECONDS = 120
# Looked again at least this often, for a changed setting or a computer that slept through the due time
MAX_WAIT_SECONDS = 3600
# After a failed check (offline, logged out) the service is tried again this much later
RETRY_SECONDS = 3600
# Playlists named in a notification, the rest are counted
NOTIFY_PLAYLISTS = 4


def interval_hours(config: dict) -> int:
    return INTERVALS.get(config.get("AUTO_CHECK", DEFAULT_INTERVAL), INTERVALS[DEFAULT_INTERVAL])


def seconds_since(iso: str | None, now: datetime) -> float:
    """How long ago a check was; never checked counts as long ago."""
    if not iso:
        return float("inf")
    return (now - datetime.fromisoformat(iso)).total_seconds()


def due_playlists(db_path, hours: int, now: datetime) -> tuple[list[dict], float | None]:
    """The tracked playlists whose last check is older than hours, and the seconds until the next one is
    due (None when nothing is tracked)."""
    interval = hours * 3600
    due, next_due = [], None
    for playlist in history.tracked_playlists(db_path):
        left = interval - seconds_since(playlist["last_checked"], now)
        if left <= 0:
            due.append(playlist)
        else:
            next_due = left if next_due is None else min(next_due, left)
    if due:
        next_due = 0
    return due, next_due


def notification(service_name: str, results: list[dict]) -> str | None:
    """The changes worth a notification, one line per playlist, or None when there are none."""
    lines = []
    for result in results:
        if "error" in result or result["first_check"]:
            continue
        parts = [t(key, count=len(result[field])) for field, key in (
            ("removed", "auto.removed"), ("unplayable", "auto.unplayable"), ("playable_again", "auto.playable"),
        ) if result[field]]
        if parts:
            lines.append(f"{result['name']}: {', '.join(parts)}")
    if not lines:
        return None
    if len(lines) > NOTIFY_PLAYLISTS:
        lines = lines[:NOTIFY_PLAYLISTS - 1] + [t("auto.more", count=len(lines) - NOTIFY_PLAYLISTS + 1)]
    return f"{service_name}\n" + "\n".join(lines)


class AutoChecker:
    def __init__(self, notify: Callable[[str], None], on_checked: Callable[[str, list[dict]], None]):
        """notify(message) shows a notification; on_checked(service name, results) passes the results on to
        the window. Both are called on the checker's thread."""
        self.notify = notify
        self.on_checked = on_checked
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        # When a check of a service last failed, to wait a while before trying again
        self._failed: dict[str, float] = {}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="auto-check", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        self._stop.wait(FIRST_LOOK_SECONDS)
        while not self._stop.is_set():
            try:
                wait = self.look()
            except Exception:  # an unexpected error must not end automatic checks for good
                wait = RETRY_SECONDS
            self._stop.wait(max(60, wait))

    def look(self) -> float:
        """Check what is due; returns the seconds until the next look."""
        hours = interval_hours(load_config())
        if not hours:
            return MAX_WAIT_SECONDS
        wait = MAX_WAIT_SECONDS
        for service in SERVICES:
            if self._stop.is_set():
                break
            name = service.__name__.rsplit(".", 1)[-1]
            failed = self._failed.get(name)
            if failed is not None and time.monotonic() - failed < RETRY_SECONDS:
                wait = min(wait, RETRY_SECONDS - (time.monotonic() - failed))
                continue
            due, next_due = due_playlists(service.DB_PATH, hours, datetime.now().astimezone())
            if due:
                self._check(service, name, due)
            elif next_due is not None:
                wait = min(wait, next_due)
        return wait

    def _check(self, service, name: str, playlists: list[dict]) -> None:
        try:
            client = service.connect()
        except TrackerError:  # no credentials for this service: nothing to check
            self._failed[name] = time.monotonic()
            return
        results = []
        for playlist in playlists:
            try:
                results.append(history.check_playlist(client, playlist["playlist_id"], service.DB_PATH))
            except service.LoginRequired:
                self._failed[name] = time.monotonic()
                break
            except TrackerError as error:
                # Offline or the playlist is gone: the others may still work, this one is tried next time
                results.append({"name": playlist["name"], "error": str(error)})
                self._failed[name] = time.monotonic()
        else:
            if all("error" not in result for result in results):
                self._failed.pop(name, None)
        if not any("error" not in result for result in results):
            return
        title = TITLES.get(name, name)
        message = notification(title, results)
        if message:
            self.notify(message)
        self.on_checked(title, results)
