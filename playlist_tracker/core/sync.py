"""
Syncs the plays with the account in Supabase while the app runs (also in the tray): plays recorded or changed
here are sent, plays recorded on the user's other devices are fetched into listening.db.

Each play has an id that is the same everywhere (uid), so sending or fetching one twice changes nothing. Fetching
asks only for what changed since the last fetch (SYNC_PULLED in config.json, the server's time).
"""

from __future__ import annotations

import platform
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable

from playlist_tracker.core import account
from playlist_tracker.core.config import load_config, save_config
from playlist_tracker.core.errors import TrackerError
from playlist_tracker.music import listening

# Not right at startup, while the app and Windows are still busy starting
FIRST_SYNC_SECONDS = 10
INTERVAL_SECONDS = 5 * 60
# Rows per request
BATCH = 500
# A row written while the previous fetch ran can carry a slightly earlier time, so fetches overlap by this much
OVERLAP = timedelta(minutes=2)

# The outcome of the last sync, for the account page: at (local time), sent, received, error
last: dict = {}


def device() -> tuple[str, str]:
    """This computer's id (made once) and name."""
    config = load_config()
    if not config.get("DEVICE_ID"):
        config["DEVICE_ID"] = str(uuid.uuid4())
        save_config(config)
    return config["DEVICE_ID"], platform.node() or "PC"


def push(client: account.AccountClient, user_id: str) -> int:
    """Send the plays not sent yet; return how many."""
    device_id, device_name = device()
    sent = 0
    while True:
        plays = listening.unsynced(BATCH)
        if not plays:
            return sent
        rows = [{"user_id": user_id, "uid": p["uid"], "device_id": p["device"] or device_id,
                 "played_at": p["played_at"], "source": p["source"], "artist": p["artist"], "name": p["name"],
                 "album": p["album"], "ms_played": p["ms_played"]} for p in plays]
        # Plays of this computer carry its name; a play recorded elsewhere keeps the name its own device sent.
        # Rows of one request must have the same fields, so the two go separately
        own = [{**row, "device_name": device_name} for row, p in zip(rows, plays) if not p["device"]]
        others = [row for row, p in zip(rows, plays) if p["device"]]
        for group in (own, others):
            if group:
                client.rest("POST", "plays?on_conflict=user_id,uid", group,
                            "resolution=merge-duplicates,return=minimal")
        listening.mark_synced(plays)
        sent += len(plays)


def pull(client: account.AccountClient) -> int:
    """Fetch plays of other devices changed since the last fetch; return how many were new here."""
    device_id, _ = device()
    since = load_config().get("SYNC_PULLED")
    added, offset, newest = 0, 0, since
    query = "select=uid,device_id,played_at,source,artist,name,album,ms_played,updated_at" \
            f"&device_id=neq.{device_id}&order=updated_at,uid&limit={BATCH}"
    if since:
        start = datetime.fromisoformat(since) - OVERLAP
        query += "&updated_at=gte." + start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    while True:
        rows = client.rest("GET", f"plays?{query}&offset={offset}") or []
        added += listening.merge_remote([{**row, "device": row["device_id"]} for row in rows])
        if rows:
            newest = rows[-1]["updated_at"]
        if len(rows) < BATCH:
            break
        offset += BATCH
    if newest and newest != since:
        config = load_config()
        config["SYNC_PULLED"] = newest
        save_config(config)
    return added


def sync_now() -> dict:
    """Send and fetch once; returns {"sent", "received"}. Raises TrackerError when offline or logged out."""
    user = account.profile()
    if not user:
        raise account.AccountError("")
    client = account.AccountClient()
    sent = push(client, user["id"])
    received = pull(client)
    return {"sent": sent, "received": received}


def forget() -> None:
    """After logging out: the next account gets every play and fetches from the start."""
    listening.mark_all_unsynced()
    config = load_config()
    config.pop("SYNC_PULLED", None)
    save_config(config)
    last.clear()


class Syncer:
    def __init__(self, on_synced: Callable[[dict], None]):
        """on_synced(last) is called on the syncer's thread after every sync."""
        self.on_synced = on_synced
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="sync", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def wake(self) -> None:
        """Sync now, e.g. right after logging in."""
        self._wake.set()

    def _run(self) -> None:
        self._wake.wait(FIRST_SYNC_SECONDS)
        while not self._stop.is_set():
            self._wake.clear()
            if account.configured() and account.profile():
                self.run_once()
            self._wake.wait(INTERVAL_SECONDS)

    def run_once(self) -> dict:
        with self._lock:
            try:
                result = sync_now()
                last.clear()
                last.update(result, at=datetime.now().astimezone(), error=None)
            except TrackerError as error:
                last["error"] = str(error) or None
                last.setdefault("at", None)
            except Exception as error:  # an unexpected error must not end syncing for good
                last["error"] = repr(error)
                last.setdefault("at", None)
        self.on_synced(dict(last))
        return dict(last)


# Started by main.py; the account page asks it to sync now
syncer: Syncer | None = None
