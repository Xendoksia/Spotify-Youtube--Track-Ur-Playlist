"""
The app without its Tk window, started by the desktop window (desktop/, Electron): records listening, checks
playlists and syncs like main.py, and serves the window's data through api/server.py.

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

from playlist_tracker import background
from playlist_tracker.api import server
from playlist_tracker.core import account, i18n, sync
from playlist_tracker.core.config import load_config, save_config
from playlist_tracker.music import nowplaying
from playlist_tracker.playlists.auto_check import AutoChecker

_emit_lock = threading.Lock()


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


def forward(commands) -> None:
    """Requests of later copies and results of the background work, as events for the window."""
    while True:
        command = commands.get()
        if command == "show":
            emit("show")
        elif isinstance(command, tuple) and command[0] == "checked":
            emit("checked", service=command[1])
        elif isinstance(command, tuple) and command[0] == "synced":
            emit("synced")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    token = os.environ.get("PLAYLIST_TRACKER_TOKEN")
    if not token:
        sys.exit("PLAYLIST_TRACKER_TOKEN is not set")
    i18n.set_language(load_config().get("LANGUAGE"))
    instance = background.SingleInstance()
    owner = instance.acquire()
    tracker = checker = None
    recording = None
    if owner:
        account.end_unremembered_session()
        tracker = nowplaying.LocalTracker()
        if tracking_enabled():
            tracker.start()
        recording = {"enabled": lambda: tracker.enabled, "set": lambda enabled: set_tracking(tracker, enabled)}
        commands = instance.requests
        checker = AutoChecker(lambda message: emit("notify", message=message),
                              lambda service, results: commands.put(("checked", service, results)))
        checker.start()
        sync.syncer = sync.Syncer(lambda result: commands.put(("synced", result)))
        sync.syncer.start()
        threading.Thread(target=forward, args=(commands,), name="events", daemon=True).start()

    api = server.start(server.Api(token, recording, emit))
    emit("ready", port=api.server_address[1], recording=owner)
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
