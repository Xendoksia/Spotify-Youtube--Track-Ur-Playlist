"""
Playlist history shared by Spotify and YouTube: each check stores a snapshot of the playlist, compares it
with the previous one and records added, removed and unplayable tracks with a timestamp. Every service
keeps its own database file.
"""

from __future__ import annotations

import csv
import sqlite3
from datetime import datetime
from pathlib import Path

from playlist_tracker.core.i18n import t
from playlist_tracker.core.text import format_date

EVENT_ADDED = "ADDED"
EVENT_REMOVED = "REMOVED"
EVENT_UNPLAYABLE = "UNPLAYABLE"
EVENT_PLAYABLE = "PLAYABLE_AGAIN"
EVENT_INITIAL = "INITIAL_SNAPSHOT"

SCHEMA = """
CREATE TABLE IF NOT EXISTS playlists (
    playlist_id TEXT PRIMARY KEY,
    name TEXT,
    last_checked TEXT,
    tracked INTEGER DEFAULT 0
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


def open_db(db_path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def tracked_playlists(db_path: Path) -> list[dict]:
    with open_db(db_path) as db:
        return [dict(r) for r in db.execute("SELECT * FROM playlists WHERE tracked = 1 ORDER BY name")]


def set_tracked(playlist_id: str, name: str, tracked: bool, db_path: Path) -> None:
    with open_db(db_path) as db:
        db.execute(
            "INSERT INTO playlists (playlist_id, name, tracked) VALUES (?, ?, ?) "
            "ON CONFLICT(playlist_id) DO UPDATE SET name = excluded.name, tracked = excluded.tracked",
            (playlist_id, name, int(tracked)),
        )


def _write_event(db: sqlite3.Connection, playlist_id: str, checked_at: str, event: str, track: dict) -> None:
    db.execute(
        "INSERT INTO events (playlist_id, checked_at, event, uri, name, artist, album, added_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (playlist_id, checked_at, event, track.get("uri", ""), track.get("name", ""),
         track.get("artist", ""), track.get("album", ""), track.get("added_at", "")),
    )


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
                for track in result[field]:
                    _write_event(db, playlist_id, now, event, track)
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
