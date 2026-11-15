"""
Playlist history shared by Spotify and YouTube: each check stores a snapshot of the playlist, compares it
with the previous one and records added, removed and unplayable tracks with a timestamp. Every service
keeps its own database file.
"""

from __future__ import annotations

import csv
import sqlite3
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from playlist_tracker.core.i18n import t
from playlist_tracker.core.text import format_date

EVENT_ADDED = "ADDED"
EVENT_REMOVED = "REMOVED"
EVENT_UNPLAYABLE = "UNPLAYABLE"
EVENT_PLAYABLE = "PLAYABLE_AGAIN"
EVENT_INITIAL = "INITIAL_SNAPSHOT"
# A check from the window and the automatic check must not compare the same playlist at the same time,
# or both would record its changes
_check_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS playlists (
    playlist_id TEXT PRIMARY KEY,
    name TEXT,
    last_checked TEXT,
    tracked INTEGER DEFAULT 0,
    changed_at TEXT,
    synced INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tracks (
    playlist_id TEXT,
    key TEXT,
    uri TEXT, name TEXT, artist TEXT, album TEXT,
    added_at TEXT, added_by TEXT,
    playable INTEGER,
    first_seen TEXT,
    last_seen TEXT,
    in_playlist INTEGER,
    PRIMARY KEY (playlist_id, key)
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    playlist_id TEXT,
    checked_at TEXT,
    event TEXT,
    uri TEXT, name TEXT, artist TEXT, album TEXT,
    added_at TEXT
);
"""


@contextmanager
def open_db(db_path: Path) -> Iterator[sqlite3.Connection]:
    """A connection for a with block: committed at its end (rolled back on an error) and always closed.
    sqlite3's own with block does not close it, so the file stayed open until garbage collection."""
    db = sqlite3.connect(db_path)
    try:
        db.row_factory = sqlite3.Row
        db.executescript(SCHEMA)
        _add_sync_columns(db)
        with db:
            yield db
    finally:
        db.close()


def _add_sync_columns(db: sqlite3.Connection) -> None:
    """Playlists stored before syncing: when tracking last changed (changed_at, unknown for them) and whether
    that still has to be sent (synced). Events stored before syncing get an id that is the same on every device
    (uid), the device that found them (device, NULL for this computer) and synced."""
    if "changed_at" not in {row[1] for row in db.execute("PRAGMA table_info(playlists)")}:
        db.execute("ALTER TABLE playlists ADD COLUMN changed_at TEXT")
        db.execute("ALTER TABLE playlists ADD COLUMN synced INTEGER NOT NULL DEFAULT 0")
        db.commit()
    if "uid" not in {row[1] for row in db.execute("PRAGMA table_info(events)")}:
        db.execute("ALTER TABLE events ADD COLUMN uid TEXT")
        db.execute("ALTER TABLE events ADD COLUMN device TEXT")
        db.execute("ALTER TABLE events ADD COLUMN synced INTEGER NOT NULL DEFAULT 0")
        db.executemany("UPDATE events SET uid = ? WHERE id = ?",
                       [(str(uuid.uuid4()), row[0]) for row in db.execute("SELECT id FROM events")])
        db.commit()
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS events_uid ON events (uid)")


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def tracked_playlists(db_path: Path) -> list[dict]:
    with open_db(db_path) as db:
        return [dict(r) for r in db.execute("SELECT * FROM playlists WHERE tracked = 1 ORDER BY name")]


def set_tracked(playlist_id: str, name: str, tracked: bool, db_path: Path) -> None:
    with open_db(db_path) as db:
        db.execute(
            "INSERT INTO playlists (playlist_id, name, tracked, changed_at, synced) VALUES (?, ?, ?, ?, 0) "
            "ON CONFLICT(playlist_id) DO UPDATE SET name = excluded.name, tracked = excluded.tracked, "
            "changed_at = excluded.changed_at, synced = 0",
            (playlist_id, name, int(tracked), now_utc()),
        )


# Syncing between devices (see core/sync.py): the latest change to tracking wins

# A playlist whose tracking changed before syncing existed loses to any change made on another device
NEVER = "1970-01-01T00:00:00.000000Z"


def unsynced_playlists(db_path: Path) -> list[dict]:
    with open_db(db_path) as db:
        return [{**dict(r), "changed_at": r["changed_at"] or NEVER} for r in db.execute(
            "SELECT playlist_id, name, tracked, changed_at FROM playlists WHERE synced = 0")]


def mark_playlists_synced(playlists: list[dict], db_path: Path) -> None:
    """Note playlists as sent, unless their tracking changed again in the meantime."""
    with open_db(db_path) as db:
        db.executemany("UPDATE playlists SET synced = 1 WHERE playlist_id = ? AND COALESCE(changed_at, ?) = ?",
                       [(p["playlist_id"], NEVER, p["changed_at"]) for p in playlists])


def mark_all_playlists_unsynced(db_path: Path) -> None:
    """After logging out: every playlist goes to the next account logged in."""
    with open_db(db_path) as db:
        db.execute("UPDATE playlists SET synced = 0")


def merge_remote_playlists(playlists: list[dict], db_path: Path) -> int:
    """Take tracking changes made on other devices when they are newer than this one's; return how many
    playlists changed here."""
    changed = 0
    with open_db(db_path) as db:
        for p in playlists:
            local = db.execute("SELECT tracked, changed_at FROM playlists WHERE playlist_id = ?",
                               (p["playlist_id"],)).fetchone()
            if local and (local["changed_at"] or NEVER) >= p["changed_at"]:
                continue
            db.execute(
                "INSERT INTO playlists (playlist_id, name, tracked, changed_at, synced) VALUES (?, ?, ?, ?, 1) "
                "ON CONFLICT(playlist_id) DO UPDATE SET name = COALESCE(excluded.name, name), "
                "tracked = excluded.tracked, changed_at = excluded.changed_at, synced = 1",
                (p["playlist_id"], p["name"], int(p["tracked"]), p["changed_at"]))
            if not local or bool(local["tracked"]) != bool(p["tracked"]):
                changed += 1
    return changed


# Events: every device checks with its own last snapshot, so two devices can find the same change. An event is
# left out when the same track's nearest event before it or after it is the same one: the change is already there

TRACK_FIELDS = ("uri", "name", "artist", "album", "added_at")
EVENT_FIELDS = ("uid", "device", "playlist_id", "checked_at", "event", "uri", "name", "artist", "album", "added_at")


def _duplicate(db: sqlite3.Connection, event: dict) -> bool:
    for f in TRACK_FIELDS:
        event[f] = event.get(f) or ""
    if event["event"] == EVENT_INITIAL:
        return db.execute("SELECT 1 FROM events WHERE playlist_id = ? AND event = ?",
                          (event["playlist_id"], EVENT_INITIAL)).fetchone() is not None
    track = "playlist_id = ? AND uri = ? AND added_at = ? AND event != ?"
    params = (event["playlist_id"], event["uri"], event["added_at"], EVENT_INITIAL,
              event["checked_at"])
    for query in (f"SELECT event FROM events WHERE {track} AND datetime(checked_at) <= datetime(?) "
                  "ORDER BY datetime(checked_at) DESC, id DESC LIMIT 1",
                  f"SELECT event FROM events WHERE {track} AND datetime(checked_at) > datetime(?) "
                  "ORDER BY datetime(checked_at), id LIMIT 1"):
        nearest = db.execute(query, params).fetchone()
        if nearest and nearest["event"] == event["event"]:
            return True
    return False


def _insert_event(db: sqlite3.Connection, event: dict, synced: int) -> bool:
    """Store an event unless it is already there; return whether it was stored."""
    if _duplicate(db, event) or db.execute("SELECT 1 FROM events WHERE uid = ?", (event["uid"],)).fetchone():
        return False
    values = [event.get(f) for f in EVENT_FIELDS]
    db.execute(f"INSERT INTO events ({', '.join(EVENT_FIELDS)}, synced) VALUES ({', '.join('?' * 11)})",
               (*values, synced))
    return True


def unsynced_events(limit: int, db_path: Path) -> list[dict]:
    with open_db(db_path) as db:
        return [dict(r) for r in db.execute(
            f"SELECT {', '.join(EVENT_FIELDS)} FROM events WHERE synced = 0 ORDER BY id LIMIT ?", (limit,))]


def mark_events_synced(events: list[dict], db_path: Path) -> None:
    with open_db(db_path) as db:
        db.executemany("UPDATE events SET synced = 1 WHERE uid = ?", [(e["uid"],) for e in events])


def mark_all_events_unsynced(db_path: Path) -> None:
    """After another account logs in: every event goes to it."""
    with open_db(db_path) as db:
        db.execute("UPDATE events SET synced = 0")


def merge_remote_events(events: list[dict], db_path: Path) -> int:
    """Take events found on other devices; return how many were new here."""
    with open_db(db_path) as db:
        return sum(_insert_event(db, event, synced=1) for event in events)


def playlist_summaries(db_path: Path) -> dict[str, dict]:
    """Per playlist: how many tracks it had at its last check, and its latest changes (when they were
    found and how many of each event)."""
    summaries: dict[str, dict] = {}
    with open_db(db_path) as db:
        for row in db.execute("SELECT playlist_id, COUNT(*) AS tracks FROM tracks WHERE in_playlist = 1 "
                              "GROUP BY playlist_id"):
            summaries[row["playlist_id"]] = {"tracks": row["tracks"], "changed_at": None, "changes": {}}
        for row in db.execute(
            "SELECT playlist_id, checked_at, event, COUNT(*) AS count FROM events e WHERE event != ? AND checked_at = "
            "(SELECT MAX(checked_at) FROM events WHERE playlist_id = e.playlist_id AND event != ?) "
            "GROUP BY playlist_id, event", (EVENT_INITIAL, EVENT_INITIAL),
        ):
            summary = summaries.setdefault(row["playlist_id"], {"tracks": None, "changed_at": None, "changes": {}})
            summary["changed_at"] = row["checked_at"]
            summary["changes"][row["event"]] = row["count"]
    return summaries


def latest_tracks(db_path: Path, count: int = 4) -> dict[str, list[dict]]:
    """Per playlist: its most recently added tracks, one per album (or per video when there are no albums),
    newest first, for the card's covers."""
    latest: dict[str, list[dict]] = {}
    seen: dict[str, set] = {}
    with open_db(db_path) as db:
        for row in db.execute("SELECT playlist_id, uri, name, artist, album, added_at FROM tracks "
                              "WHERE in_playlist = 1 ORDER BY playlist_id, added_at DESC, first_seen DESC"):
            tracks = latest.setdefault(row["playlist_id"], [])
            if len(tracks) >= count:
                continue
            cover = (row["artist"] or "").lower(), (row["album"] or row["uri"] or "").lower()
            if cover in seen.setdefault(row["playlist_id"], set()):
                continue
            seen[row["playlist_id"]].add(cover)
            tracks.append(dict(row))
    return latest


def _write_event(db: sqlite3.Connection, playlist_id: str, checked_at: str, event: str, track: dict) -> bool:
    """Record a change found here; False when another device already found it."""
    return _insert_event(db, {"uid": str(uuid.uuid4()), "device": None, "playlist_id": playlist_id,
                              "checked_at": checked_at, "event": event, **{f: track.get(f) for f in TRACK_FIELDS}},
                         synced=0)


def get_events(playlist_id: str | None, db_path: Path) -> list[dict]:
    query = "SELECT e.*, p.name AS playlist FROM events e LEFT JOIN playlists p USING (playlist_id)"
    params: tuple = ()
    if playlist_id:
        query += " WHERE e.playlist_id = ?"
        params = (playlist_id,)
    with open_db(db_path) as db:
        return [dict(r) for r in db.execute(query + " ORDER BY e.id DESC", params)]


def check_playlist(client, playlist_id: str, db_path: Path) -> dict:
    """Fetch a playlist, diff it against the previous snapshot, record events and return the result.

    Works with any client that provides playlist_name() and playlist_tracks().
    """
    with _check_lock:
        return _check_playlist(client, playlist_id, db_path)


def _check_playlist(client, playlist_id: str, db_path: Path) -> dict:
    name = client.playlist_name(playlist_id)
    current = client.playlist_tracks(playlist_id)
    now = datetime.now().astimezone().isoformat(timespec="seconds")

    with open_db(db_path) as db:
        row = db.execute("SELECT last_checked FROM playlists WHERE playlist_id = ?", (playlist_id,)).fetchone()
        first_check = row is None or row["last_checked"] is None
        db.execute(
            "INSERT INTO playlists (playlist_id, name, last_checked) VALUES (?, ?, ?) "
            "ON CONFLICT(playlist_id) DO UPDATE SET name = excluded.name, last_checked = excluded.last_checked",
            (playlist_id, name, now),
        )

        previous = {
            r["key"]: dict(r)
            for r in db.execute("SELECT * FROM tracks WHERE playlist_id = ? AND in_playlist = 1", (playlist_id,))
        }
        current_by_key = {track["key"]: track for track in current}
        for k, track in current_by_key.items():
            # Unavailable items may lose their metadata (YouTube shows "Deleted video"), keep the last known one
            if k in previous and not track["playable"]:
                track.update({f: previous[k][f] for f in ("name", "artist", "album")})
        kept = [(previous[k], track) for k, track in current_by_key.items() if k in previous]

        result = {
            "playlist_id": playlist_id,
            "name": name,
            "total": len(current),
            "checked_at": now,
            "first_check": first_check,
            "added": [track for k, track in current_by_key.items() if k not in previous],
            "removed": [track for k, track in previous.items() if k not in current_by_key],
            "unplayable": [track for old, track in kept if old["playable"] and not track["playable"]],
            "playable_again": [track for old, track in kept if not old["playable"] and track["playable"]],
            "unavailable": [track for track in current if not track["playable"]],
        }

        for track in current:
            db.execute(
                "INSERT INTO tracks (playlist_id, key, uri, name, artist, album, added_at, added_by, "
                "playable, first_seen, last_seen, in_playlist) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1) "
                "ON CONFLICT(playlist_id, key) DO UPDATE SET name = excluded.name, artist = excluded.artist, "
                "album = excluded.album, playable = excluded.playable, "
                "last_seen = excluded.last_seen, in_playlist = 1",
                (playlist_id, track["key"], track["uri"], track["name"], track["artist"], track["album"],
                 track["added_at"], track["added_by"], track["playable"], now, now),
            )
        for track in result["removed"]:
            db.execute("UPDATE tracks SET in_playlist = 0 WHERE playlist_id = ? AND key = ?",
                       (playlist_id, track["key"]))

        if first_check:
            _write_event(db, playlist_id, now, EVENT_INITIAL, {"name": f"{len(current)} tracks recorded"})
            result.update(added=[], removed=[], unplayable=[], playable_again=[])
        else:
            for event, field in ((EVENT_ADDED, "added"), (EVENT_REMOVED, "removed"),
                                 (EVENT_UNPLAYABLE, "unplayable"), (EVENT_PLAYABLE, "playable_again")):
                # A change another device already found is not news here
                result[field] = [track for track in result[field]
                                 if _write_event(db, playlist_id, now, event, track)]
    return result


def export_csv(path: str, db_path: Path) -> int:
    rows = list(reversed(get_events(None, db_path)))
    # utf-8-sig and ';' let Excel open the file directly with correct encoding in most locales
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([t(f"csv.{column}") for column in
                         ("checked_at", "playlist", "event", "artist", "track", "album", "added", "uri")])
        for r in rows:
            writer.writerow([format_date(r["checked_at"]), r["playlist"], t(f"event.{r['event']}"), r["artist"],
                             r["name"],
                             r["album"], format_date(r["added_at"]), r["uri"]])
    return len(rows)
