"""
Syncs with the account in Supabase while the app runs (also in the tray): plays recorded or changed here are
sent, plays recorded on the user's other devices are fetched into listening.db. Tracked playlists, the changes
found by checking them and the language and theme go both ways too.

Each play and event has an id that is the same everywhere (uid), so sending or fetching one twice changes
nothing. Fetching asks only for what changed since the last fetch (SYNC_PULLED and the like in config.json, the
server's time).
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
from playlist_tracker.playlists import auto_check, history, spotify, youtube

# Not right at startup, while the app and Windows are still busy starting
FIRST_SYNC_SECONDS = 10
INTERVAL_SECONDS = 5 * 60
# Rows per request
BATCH = 500
# A row written while the previous fetch ran can carry a slightly earlier time, so fetches overlap by this much
OVERLAP = timedelta(minutes=2)

# Service names in Supabase and their databases
PLAYLIST_DATABASES = {"spotify": spotify.DB_PATH, "youtube": youtube.DB_PATH}

# Settings that follow the user to every device; the others (tray, autostart, credentials) belong to a computer
SYNCED_SETTINGS = ("LANGUAGE", "THEME", "DISCOVER_HIDDEN", "DISCOVER_FAME")

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
    since, changed_since = _since_query("SYNC_PULLED")
    added, offset, newest = 0, 0, since
    query = "select=uid,device_id,played_at,source,artist,name,album,ms_played,updated_at" \
            f"&device_id=neq.{device_id}&order=updated_at,uid&limit={BATCH}{changed_since}"
    while True:
        rows = client.rest("GET", f"plays?{query}&offset={offset}") or []
        added += listening.merge_remote([{**row, "device": row["device_id"]} for row in rows])
        if rows:
            newest = rows[-1]["updated_at"]
        if len(rows) < BATCH:
            break
        offset += BATCH
    _save_since("SYNC_PULLED", since, newest)
    return added


# How often the plays here are compared with the cloud's, and how many ids are asked for at once
CHECK_EVERY = timedelta(days=1)
CHECK_BATCH = 100


def cloud_uids(client: account.AccountClient) -> set[str]:
    """The ids of every play of the account in the cloud."""
    uids, offset = set(), 0
    while True:
        rows = client.rest("GET", f"plays?select=uid&order=uid&limit={BATCH}&offset={offset}") or []
        uids.update(row["uid"] for row in rows)
        if len(rows) < BATCH:
            return uids
        offset += BATCH


def check(client: account.AccountClient, user_id: str) -> dict:
    """Compare the plays here with the cloud's and mend what differs: plays the cloud lacks are sent again and
    plays this computer lacks are fetched. A play another device recorded at the same time as this computer is
    kept here once (listening._insert), so it stays only in the cloud: counted as "twice". The outcome is kept in
    config.json (SYNC_CHECK) for the account page."""
    here, cloud = listening.all_uids(), cloud_uids(client)
    missing_there = here - cloud
    if missing_there:
        listening.mark_unsynced(missing_there)
        push(client, user_id)
    missing_here = sorted(cloud - here)
    fetched = 0
    for start in range(0, len(missing_here), CHECK_BATCH):
        ids = ",".join(missing_here[start:start + CHECK_BATCH])
        rows = client.rest("GET", "plays?select=uid,device_id,played_at,source,artist,name,album,ms_played"
                                  f"&uid=in.({ids})") or []
        fetched += listening.merge_remote([{**row, "device": row["device_id"]} for row in rows])
    result = {"at": datetime.now().astimezone().isoformat(), "cloud": len(cloud), "here": len(here) + fetched,
              "sent": len(missing_there), "fetched": fetched, "twice": len(missing_here) - fetched}
    config = load_config()
    config["SYNC_CHECK"] = result
    save_config(config)
    return result


def check_due() -> bool:
    """The plays were not compared with the cloud in the last day."""
    done = (load_config().get("SYNC_CHECK") or {}).get("at")
    return not done or datetime.now().astimezone() - datetime.fromisoformat(done) >= CHECK_EVERY


def _since_query(key: str) -> tuple[str | None, str]:
    """The last fetch time saved under key and the filter for rows changed since then."""
    since = load_config().get(key)
    if not since:
        return None, ""
    start = datetime.fromisoformat(since) - OVERLAP
    return since, "&updated_at=gte." + start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _save_since(key: str, since: str | None, newest: str | None) -> None:
    if newest and newest != since:
        config = load_config()
        config[key] = newest
        save_config(config)


def push_playlists(client: account.AccountClient, user_id: str) -> int:
    """Send tracking changes not sent yet; return how many."""
    sent = 0
    for service, db_path in PLAYLIST_DATABASES.items():
        playlists = history.unsynced_playlists(db_path)
        if not playlists:
            continue
        rows = [{"user_id": user_id, "service": service, "playlist_id": p["playlist_id"], "name": p["name"],
                 "tracked": bool(p["tracked"]), "changed_at": p["changed_at"], "seen": bool(p["seen"]),
                 "size": p["size"], "found_at": p["found_at"]} for p in playlists]
        client.rest("POST", "tracked_playlists?on_conflict=user_id,service,playlist_id", rows,
                    "resolution=merge-duplicates,return=minimal")
        history.mark_playlists_synced(playlists, db_path)
        sent += len(playlists)
    return sent


def pull_playlists(client: account.AccountClient) -> int:
    """Fetch tracking changes since the last fetch; return how many playlists changed here. This device's own
    changes come back too and change nothing."""
    since, query = _since_query("SYNC_PLAYLISTS_PULLED")
    changed, offset, newest = 0, 0, since
    while True:
        rows = client.rest("GET", "tracked_playlists?select=service,playlist_id,name,tracked,changed_at,seen,size,"
                           "found_at,updated_at"
                           f"&order=updated_at,service,playlist_id&limit={BATCH}&offset={offset}{query}") or []
        for service, db_path in PLAYLIST_DATABASES.items():
            mine = [row for row in rows if row["service"] == service]
            if mine:
                changed += history.merge_remote_playlists(mine, db_path)
        if rows:
            newest = rows[-1]["updated_at"]
        if len(rows) < BATCH:
            break
        offset += BATCH
    _save_since("SYNC_PLAYLISTS_PULLED", since, newest)
    return changed


def push_events(client: account.AccountClient, user_id: str) -> int:
    """Send the playlist changes found here and not sent yet; return how many."""
    device_id, _ = device()
    sent = 0
    for service, db_path in PLAYLIST_DATABASES.items():
        while events := history.unsynced_events(BATCH, db_path):
            rows = [{**{f: e[f] for f in history.EVENT_FIELDS if f != "device"}, "user_id": user_id,
                     "service": service, "device_id": e["device"] or device_id} for e in events]
            client.rest("POST", "playlist_events?on_conflict=user_id,uid", rows,
                        "resolution=ignore-duplicates,return=minimal")
            history.mark_events_synced(events, db_path)
            sent += len(events)
    return sent


def pull_events(client: account.AccountClient) -> int:
    """Fetch playlist changes found on other devices since the last fetch; return how many were new here."""
    device_id, _ = device()
    since, changed_since = _since_query("SYNC_EVENTS_PULLED")
    added, offset, newest = 0, 0, since
    query = "select=uid,device_id,service,playlist_id,checked_at,event,uri,name,artist,album,added_at,updated_at"             f"&device_id=neq.{device_id}&order=updated_at,uid&limit={BATCH}{changed_since}"
    while True:
        rows = client.rest("GET", f"playlist_events?{query}&offset={offset}") or []
        for service, db_path in PLAYLIST_DATABASES.items():
            mine = [{**row, "device": row["device_id"]} for row in rows if row["service"] == service]
            if mine:
                added += history.merge_remote_events(mine, db_path)
        if rows:
            newest = rows[-1]["updated_at"]
        if len(rows) < BATCH:
            break
        offset += BATCH
    _save_since("SYNC_EVENTS_PULLED", since, newest)
    return added


def settings_changed(config: dict) -> None:
    """The language, theme or Discover settings were changed here (config is saved by the caller): send it with the next sync."""
    config["SETTINGS_CHANGED_AT"] = history.now_utc()
    config["SETTINGS_SYNCED"] = False


def push_settings(client: account.AccountClient, user_id: str) -> bool:
    config = load_config()
    changed_at = config.get("SETTINGS_CHANGED_AT")
    if not changed_at or config.get("SETTINGS_SYNCED"):
        return False
    # An emptied list of hidden suggestions is sent too, so the other devices show them again
    data = {key: config[key] for key in SYNCED_SETTINGS if config.get(key) is not None}
    client.rest("POST", "settings?on_conflict=user_id", [{"user_id": user_id, "data": data,
                                                         "changed_at": changed_at}],
                "resolution=merge-duplicates,return=minimal")
    config = load_config()
    # Unless they changed again in the meantime
    if config.get("SETTINGS_CHANGED_AT") == changed_at:
        config["SETTINGS_SYNCED"] = True
        save_config(config)
    return True


def pull_settings(client: account.AccountClient) -> bool:
    """Take the settings when they were changed later on another device; return whether any changed here."""
    [row] = client.rest("GET", "settings?select=data,changed_at") or [None]
    config = load_config()
    if not row or row["changed_at"] <= (config.get("SETTINGS_CHANGED_AT") or history.NEVER):
        return False
    changed = False
    for key in SYNCED_SETTINGS:
        if key in row["data"] and row["data"][key] != config.get(key):
            config[key] = row["data"][key]
            changed = True
    config["SETTINGS_CHANGED_AT"] = row["changed_at"]
    config["SETTINGS_SYNCED"] = True
    save_config(config)
    return changed


def sync_now() -> dict:
    """Send and fetch once; returns {"sent", "received"}. Raises TrackerError when offline or logged out."""
    user = account.profile()
    if not user:
        raise account.AccountError("")
    if load_config().get("SYNC_USER") != user["id"]:
        forget()
        config = load_config()
        config["SYNC_USER"] = user["id"]
        save_config(config)
    client = account.AccountClient()
    sent = push(client, user["id"])
    received = pull(client)
    push_playlists(client, user["id"])
    playlists = pull_playlists(client)
    push_events(client, user["id"])
    events = pull_events(client)
    push_settings(client, user["id"])
    settings = pull_settings(client)
    push_status(client, user["id"])
    check = pull_check_request(client)
    return {"sent": sent, "received": received, "playlists": playlists, "events": events, "settings": settings,
            "check": check}


def push_status(client: account.AccountClient, user_id: str) -> bool:
    """Tell the phone the last check of the tracked playlists and the next automatic one, when they changed."""
    status = auto_check.status()
    config = load_config()
    if config.get("SYNC_STATUS_SENT") == status:
        return False
    client.rest("POST", "playlist_status?on_conflict=user_id", [{"user_id": user_id, **status}],
                "resolution=merge-duplicates,return=minimal")
    config = load_config()
    config["SYNC_STATUS_SENT"] = status
    save_config(config)
    return True


def pull_check_request(client: account.AccountClient) -> bool:
    """Whether a check of the tracked playlists was asked for on the phone since the last one answered."""
    [row] = client.rest("GET", "playlist_status?select=check_requested_at") or [None]
    asked = (row or {}).get("check_requested_at")
    config = load_config()
    if not asked or asked <= config.get("CHECK_REQUEST_DONE", ""):
        return False
    config["CHECK_REQUEST_DONE"] = asked
    save_config(config)
    return True


def forget() -> None:
    """Another account logged in: it gets every play, playlist, event and the settings, and fetches from the
    start."""
    listening.mark_all_unsynced()
    for db_path in PLAYLIST_DATABASES.values():
        history.mark_all_playlists_unsynced(db_path)
        history.mark_all_events_unsynced(db_path)
    config = load_config()
    for key in ("SYNC_PULLED", "SYNC_PLAYLISTS_PULLED", "SYNC_EVENTS_PULLED"):
        config.pop(key, None)
    config["SETTINGS_SYNCED"] = False
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
                config = load_config()
                config["SYNC_LAST_OK"] = last["at"].isoformat()
                save_config(config)
                # Once a day the plays here are compared with the cloud's, and what differs is mended; a failed
                # comparison waits for the next sync and does not count as a failed sync
                if check_due():
                    try:
                        user = account.profile()
                        if user:
                            check(account.AccountClient(), user["id"])
                    except Exception:
                        pass
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
