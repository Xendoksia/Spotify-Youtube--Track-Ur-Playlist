"""
The app behind the desktop window (desktop/, Electron), which starts it: records listening, checks playlists and
syncs, and serves the window's data through api/server.py.

Events go to the window as JSON lines on stdout ({"event": "ready", "port": ...} first); the backend stops
when stdin closes, which happens when the window's process ends. The token for the API is read from the
PLAYLIST_TRACKER_TOKEN environment variable.

When another copy of the app is already recording, only the data is served, so no song is recorded twice.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time

from playlist_tracker import background, migrate
from playlist_tracker.api import server, wrapped as api_wrapped
from playlist_tracker.api.account import Account
from playlist_tracker.api.playlists import Playlists
from playlist_tracker.core import account, i18n, sync
from playlist_tracker.core.config import BASE_DIR, load_config, save_config
from playlist_tracker.music import artwork, nowplaying
from playlist_tracker.playlists.auto_check import AutoChecker

_emit_lock = threading.Lock()
# How often the recorder is looked at for new plays
PLAYS_LOOK_SECONDS = 2
SUMMARY_FIRST_SECONDS = 60
SUMMARY_LOOK_SECONDS = 600


def emit(event: str, **values) -> None:
    with _emit_lock:
        sys.stdout.write(json.dumps({"event": event, **values}, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def tracking_enabled() -> bool:
    return load_config().get("LOCAL_TRACKING", True) is not False


def set_tracking(tracker: nowplaying.LocalTracker, enabled: bool) -> None:
    config = load_config()
    config["LOCAL_TRACKING"] = enabled
    save_config(config)
    if enabled:
        tracker.start()
    else:
        tracker.stop()
    emit("recording", enabled=enabled)


def forward(commands, playlists: Playlists) -> None:
    """Requests of later copies and results of the background work, as events for the window."""
    while True:
        command = commands.get()
        if command == "show":
            emit("show")
        elif isinstance(command, tuple) and command[0] == "checked":
            # Results of the automatic check: ("checked", service name, results)
            playlists.show_results(command[1], command[2], automatic=True)
        elif isinstance(command, tuple) and command[0] == "synced":
            # What the sync brought: plays, playlists tracked elsewhere, changes found elsewhere, settings
            result = command[1] or {}
            if result.get("settings"):
                # Language or theme changed on another device
                i18n.set_language(load_config().get("LANGUAGE"))
                emit("appearance")
            emit("synced", **{key: bool(result.get(key)) for key in ("received", "playlists", "events", "settings")})


def watch_plays(tracker: nowplaying.LocalTracker) -> None:
    """Tell the window when a play was recorded or its listening time grew, so its pages count again."""
    version = tracker.version
    while True:
        time.sleep(PLAYS_LOOK_SECONDS)
        if tracker.version != version:
            version = tracker.version
            emit("plays")


def notify_summaries() -> None:
    """On the first days of a month, say once that the summary of the month before (and in January, of the year
    before) is ready, as the earlier window did; looked at every 10 minutes, so it also comes when the month turns."""
    time.sleep(SUMMARY_FIRST_SECONDS)
    while True:
        try:
            messages = api_wrapped.notices()
        except Exception:  # never a reason to stop looking
            messages = []
        for message in messages:
            emit("notify", message=message, open="summary")
        if messages:
            emit("inbox")
        time.sleep(SUMMARY_LOOK_SECONDS)


def take_over_earlier_program() -> str | None:
    """In the installed desktop window: copy the earlier program's data the first time, and start this window
    with Windows in its place when the earlier one was. Returns what to tell about the copy."""
    if not os.environ.get("PLAYLIST_TRACKER_DATA"):
        return None
    message = None
    source = migrate.migrate(BASE_DIR)
    if source is not None:
        i18n.set_language(load_config().get("LANGUAGE"))
        message = i18n.t("migrate.done", path=str(source))
    command = os.environ.get(background.AUTOSTART_ENV)
    if command and background.autostart_enabled() and background.autostart_value() != command:
        try:
            background.set_autostart(True)
        except OSError:  # it stays as it was; the setting can be changed by hand
            pass
    return message


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    token = os.environ.get("PLAYLIST_TRACKER_TOKEN")
    if not token:
        sys.exit("PLAYLIST_TRACKER_TOKEN is not set")
    i18n.set_language(load_config().get("LANGUAGE"))
    instance = background.SingleInstance()
    owner = instance.acquire()
    playlists = Playlists(emit)
    # Told once the window listens, after "ready"
    migrated = take_over_earlier_program() if owner else None
    tracker = checker = None
    if owner:
        account.end_unremembered_session()
        tracker = nowplaying.LocalTracker()
        if tracking_enabled():
            tracker.start()
        threading.Thread(target=watch_plays, args=(tracker,), name="plays", daemon=True).start()
        threading.Thread(target=notify_summaries, name="summaries", daemon=True).start()
        # Plays stored without a listening time by an early version get their track's length
        threading.Thread(target=artwork.fill_missing_lengths, args=(lambda: emit("plays"),), name="lengths",
                         daemon=True).start()
        commands = instance.requests
        checker = AutoChecker(lambda message: emit("notify", message=message),
                              lambda service, results: commands.put(("checked", service, results)))
        checker.start()
        sync.syncer = sync.Syncer(lambda result: commands.put(("synced", result)))
        sync.syncer.start()
        threading.Thread(target=forward, args=(commands, playlists), name="events", daemon=True).start()

    api = server.start(server.Api(token, tracker, lambda enabled: set_tracking(tracker, enabled), emit, playlists, Account(emit)))
    emit("ready", port=api.server_address[1], recording=owner)
    if migrated:
        emit("notify", message=migrated)
    try:
        # Until the window's process ends and closes our stdin
        while sys.stdin.readline():
            pass
    finally:
        api.shutdown()
        if owner:
            checker.stop()
            sync.syncer.stop()
            tracker.stop()
            instance.release()


if __name__ == "__main__":
    main()
