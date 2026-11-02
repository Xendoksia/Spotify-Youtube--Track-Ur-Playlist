"""
Listening history (core + command line).

nowplaying.py records what the Spotify desktop app plays on this computer, without the Spotify API,
and stores the plays in listening.db. All statistics are counted from these plays.

Command line usage:
    python listening.py recent                        Show the last recorded plays
    python listening.py stats [week|month|year|all]   Show the most played tracks and artists
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import tracker
from tracker import BASE_DIR, TrackerError

DB_PATH = BASE_DIR / "listening.db"
PERIODS = ("week", "month", "year", "all")
UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
SOURCE_LOCAL = "local"
SOURCE_SPOTIFY = "spotify"  # plays read from Spotify's recently played list by an earlier version
# Like Spotify, a track counts as played after 30 seconds
MIN_PLAY_MS = 30_000
# Sources record slightly different times for the same play (its start or end), so plays of the same
# track closer than its length plus this margin are matched
MATCH_MARGIN = timedelta(minutes=3)

SCHEMA = """
CREATE TABLE IF NOT EXISTS listens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    played_at TEXT NOT NULL,
    source TEXT NOT NULL,
    artist TEXT, name TEXT, album TEXT,
    artist_key TEXT NOT NULL,
    track_key TEXT NOT NULL,
    ms_played INTEGER,
    UNIQUE (source, played_at, track_key)
);
CREATE INDEX IF NOT EXISTS listens_time ON listens (played_at);
CREATE INDEX IF NOT EXISTS listens_track ON listens (track_key, played_at);
CREATE INDEX IF NOT EXISTS listens_artist ON listens (artist_key);
"""


def open_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    _migrate(db)
    return db


def _migrate(db: sqlite3.Connection) -> None:
    """Move plays stored by the earlier Spotify-only version into the listens table."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'plays'").fetchone():
        return
    for p in db.execute("SELECT * FROM plays").fetchall():
        first_artist = db.execute("SELECT artist_name FROM play_artists WHERE played_at = ? ORDER BY position",
                                  (p["played_at"],)).fetchone()
        _insert(db, {"played_at": p["played_at"], "artist": first_artist[0] if first_artist else p["artist"],
                     "name": p["name"], "album": p["album"], "ms_played": None,
                     "length_ms": p["duration_ms"]}, SOURCE_SPOTIFY)
    db.executescript("DROP TABLE plays; DROP TABLE play_artists; DROP TABLE IF EXISTS meta;")
    db.commit()


def key(text: str) -> str:
    return " ".join((text or "").casefold().split())


def to_utc(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime(UTC_FORMAT)


def from_utc(text: str) -> datetime:
    return datetime.strptime(text, UTC_FORMAT).replace(tzinfo=timezone.utc)


def _insert(db: sqlite3.Connection, play: dict, source: str) -> bool:
    """Store a play unless it is already recorded, by this or another source; return True if stored."""
    artist_key, track_key = key(play["artist"]), key(play["artist"]) + "|" + key(play["name"])
    moment = from_utc(play["played_at"])
    window = MATCH_MARGIN + timedelta(milliseconds=play.get("length_ms") or play.get("ms_played") or 0)
    duplicate = db.execute(
        "SELECT 1 FROM listens WHERE track_key = ? AND source != ? AND played_at BETWEEN ? AND ? LIMIT 1",
        (track_key, source, to_utc(moment - window), to_utc(moment + window))).fetchone()
    if duplicate:
        return False
    cursor = db.execute(
        "INSERT OR IGNORE INTO listens (played_at, source, artist, name, album, artist_key, track_key, ms_played) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (play["played_at"], source, play["artist"], play["name"], play["album"], artist_key, track_key,
         play.get("ms_played")))
    return cursor.rowcount > 0


def record_local(play: dict, db_path: Path = DB_PATH) -> int | None:
    """Store a play detected on this computer; return its id, or None if it is already recorded."""
    with open_db(db_path) as db:
        if _insert(db, {**play, "ms_played": play["ms"]}, SOURCE_LOCAL):
            return db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return None


def update_local(play_id: int, ms_played: int, db_path: Path = DB_PATH) -> None:
    with open_db(db_path) as db:
        db.execute("UPDATE listens SET ms_played = ? WHERE id = ?", (ms_played, play_id))


def first_play(db_path: Path = DB_PATH) -> datetime | None:
    with open_db(db_path) as db:
        first = db.execute("SELECT MIN(played_at) FROM listens").fetchone()[0]
    return from_utc(first).astimezone() if first else None


def counts(db_path: Path = DB_PATH) -> dict[str, int]:
    with open_db(db_path) as db:
        return {r[0]: r[1] for r in db.execute("SELECT source, COUNT(*) FROM listens GROUP BY source")}


def recent_plays(limit: int = 200, db_path: Path = DB_PATH) -> list[dict]:
    with open_db(db_path) as db:
        return [dict(r) for r in db.execute("SELECT * FROM listens ORDER BY played_at DESC LIMIT ?", (limit,))]


def period_range(period: str, offset: int = 0, now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return the local [start, end) of the current week/month/year, or `offset` periods back from it."""
    now = (now or datetime.now()).astimezone()
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        start = day - timedelta(days=day.weekday()) - timedelta(weeks=offset)
        return start, start + timedelta(weeks=1)
    if period == "month":
        index = day.year * 12 + day.month - 1 - offset
        start = day.replace(year=index // 12, month=index % 12 + 1, day=1)
        index += 1
        return start, start.replace(year=index // 12, month=index % 12 + 1)
    if period == "year":
        start = day.replace(year=day.year - offset, month=1, day=1)
        return start, start.replace(year=start.year + 1)
    return datetime(2000, 1, 1).astimezone(), now + timedelta(days=1)


def _range(start: datetime, end: datetime) -> tuple[str, str]:
    return to_utc(start), to_utc(end)


def summary(start: datetime, end: datetime, db_path: Path = DB_PATH) -> dict:
    with open_db(db_path) as db:
        return dict(db.execute(
            "SELECT COUNT(*) AS plays, COALESCE(SUM(ms_played), 0) / 60000 AS minutes, "
            "COUNT(DISTINCT track_key) AS tracks, COUNT(DISTINCT artist_key) AS artists "
            "FROM listens WHERE played_at >= ? AND played_at < ?", _range(start, end)).fetchone())


def top_tracks(start: datetime, end: datetime, limit: int = 10, artist_key: str | None = None,
               db_path: Path = DB_PATH) -> list[dict]:
    """Most played tracks of the period, optionally of one artist only."""
    with open_db(db_path) as db:
        return [dict(r) for r in db.execute(
            "SELECT track_key AS key, MAX(name) AS name, MAX(artist) AS artist, MAX(album) AS album, "
            "COUNT(*) AS plays, COALESCE(SUM(ms_played), 0) / 60000 AS minutes, MAX(played_at) AS last_played "
            "FROM listens WHERE played_at >= ? AND played_at < ? AND (? IS NULL OR artist_key = ?) "
            "GROUP BY track_key ORDER BY plays DESC, last_played DESC LIMIT ?",
            (*_range(start, end), artist_key, artist_key, limit))]


def top_artists(start: datetime, end: datetime, limit: int = 10, db_path: Path = DB_PATH) -> list[dict]:
    with open_db(db_path) as db:
        return [dict(r) for r in db.execute(
            "SELECT artist_key AS key, MAX(artist) AS name, COUNT(*) AS plays, COUNT(DISTINCT track_key) AS tracks, "
            "COALESCE(SUM(ms_played), 0) / 60000 AS minutes "
            "FROM listens WHERE played_at >= ? AND played_at < ? "
            "GROUP BY artist_key ORDER BY plays DESC, MAX(played_at) DESC LIMIT ?", (*_range(start, end), limit))]


def _first_heard(start: datetime, end: datetime, column: str, fields: str, db_path: Path) -> list[dict]:
    """Tracks or artists whose very first recorded play falls in the period, most played first."""
    with open_db(db_path) as db:
        return [dict(r) for r in db.execute(
            f"WITH firsts AS (SELECT {column} AS key, MIN(played_at) AS first_played FROM listens GROUP BY {column}) "
            f"SELECT l.{column} AS key, {fields}, COUNT(*) AS plays, "
            "COALESCE(SUM(l.ms_played), 0) / 60000 AS minutes, MIN(f.first_played) AS first_played "
            f"FROM listens l JOIN firsts f ON f.key = l.{column} "
            "WHERE f.first_played >= ? AND f.first_played < ? AND l.played_at >= ? AND l.played_at < ? "
            f"GROUP BY l.{column} ORDER BY plays DESC, first_played DESC", _range(start, end) * 2)]


def new_tracks(start: datetime, end: datetime, db_path: Path = DB_PATH) -> list[dict]:
    return _first_heard(start, end, "track_key",
                        "MAX(l.name) AS name, MAX(l.artist) AS artist, MAX(l.album) AS album", db_path)


def new_artists(start: datetime, end: datetime, db_path: Path = DB_PATH) -> list[dict]:
    return _first_heard(start, end, "artist_key",
                        "MAX(l.artist) AS name, COUNT(DISTINCT l.track_key) AS tracks", db_path)


def forgotten(days: int = 30, min_plays: int = 3, limit: int = 10, now: datetime | None = None,
              db_path: Path = DB_PATH) -> list[dict]:
    """Tracks played at least `min_plays` times but not once in the last `days` days, most played first."""
    since = to_utc((now or datetime.now()).astimezone() - timedelta(days=days))
    with open_db(db_path) as db:
        return [dict(r) for r in db.execute(
            "SELECT track_key AS key, MAX(name) AS name, MAX(artist) AS artist, MAX(album) AS album, "
            "COUNT(*) AS plays, COALESCE(SUM(ms_played), 0) / 60000 AS minutes, MAX(played_at) AS last_played "
            "FROM listens GROUP BY track_key HAVING plays >= ? AND last_played < ? "
            "ORDER BY plays DESC, last_played DESC LIMIT ?", (min_plays, since, limit))]


def ranks(start: datetime, end: datetime, column: str, db_path: Path = DB_PATH) -> dict[str, int]:
    """Rank (1 = most played) of every track or artist played in the period, ordered like top_tracks/top_artists.

    column: "track_key" or "artist_key".
    """
    _check_column(column)
    with open_db(db_path) as db:
        rows = db.execute(
            f"SELECT {column} FROM listens WHERE played_at >= ? AND played_at < ? "
            f"GROUP BY {column} ORDER BY COUNT(*) DESC, MAX(played_at) DESC", _range(start, end))
        return {row[0]: index for index, row in enumerate(rows, start=1)}


def timeline(start: datetime, end: datetime, bucket: str, column: str | None = None, key: str | None = None,
             db_path: Path = DB_PATH) -> dict[str, int]:
    """Plays per local day ('%Y-%m-%d') or month ('%Y-%m'), optionally of one track or artist."""
    pattern = "%Y-%m-%d" if bucket == "day" else "%Y-%m"
    where = ""
    if column:
        _check_column(column)
        where = f" AND {column} = ?"
    with open_db(db_path) as db:
        return {r[0]: r[1] for r in db.execute(
            "SELECT strftime(?, played_at, 'localtime') AS bucket, COUNT(*) FROM listens "
            f"WHERE played_at >= ? AND played_at < ?{where} GROUP BY bucket",
            (pattern, *_range(start, end), *([key] if column else [])))}


def _check_column(column: str) -> None:
    if column not in ("track_key", "artist_key"):
        raise ValueError(column)


def detail(column: str, key: str, db_path: Path = DB_PATH) -> dict | None:
    """All time totals of one track (column "track_key") or artist ("artist_key")."""
    _check_column(column)
    with open_db(db_path) as db:
        row = db.execute(
            "SELECT MAX(name) AS name, MAX(artist) AS artist, MAX(album) AS album, MAX(artist_key) AS artist_key, "
            "COUNT(*) AS plays, COALESCE(SUM(ms_played), 0) / 60000 AS minutes, COUNT(DISTINCT track_key) AS tracks, "
            "MIN(played_at) AS first_played, MAX(played_at) AS last_played "
            f"FROM listens WHERE {column} = ?", (key,)).fetchone()
    return dict(row) if row and row["plays"] else None


def artist_titles(artist_key: str, db_path: Path = DB_PATH) -> set[str]:
    """The album and track names heard from one artist."""
    with open_db(db_path) as db:
        rows = db.execute("SELECT DISTINCT album, name FROM listens WHERE artist_key = ?", (artist_key,)).fetchall()
    return {title for row in rows for title in row if title}


def hours(start: datetime, end: datetime, db_path: Path = DB_PATH) -> list[int]:
    """Plays per local hour of the day, 0-23."""
    counts_by_hour = [0] * 24
    with open_db(db_path) as db:
        for hour, count in db.execute(
                "SELECT CAST(strftime('%H', played_at, 'localtime') AS INTEGER), COUNT(*) FROM listens "
                "WHERE played_at >= ? AND played_at < ? GROUP BY 1", _range(start, end)):
            counts_by_hour[hour] = count
    return counts_by_hour


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    command, args = sys.argv[1].lower(), sys.argv[2:]
    try:
        if command == "recent":
            for p in reversed(recent_plays(30)):
                print(f"{tracker.format_date(p['played_at'])}  [{p['source']}]  {tracker.track_label(p)}")
        elif command == "stats" and (not args or args[0] in PERIODS):
            start, end = period_range(args[0] if args else "week")
            s = summary(start, end)
            print(f"{start:%Y-%m-%d} – {end - timedelta(seconds=1):%Y-%m-%d}: {s['plays']} plays, "
                  f"{s['minutes']} minutes, {s['tracks']} tracks, {s['artists']} artists\n")
            print("Top tracks:")
            for i, r in enumerate(top_tracks(start, end), 1):
                print(f"  {i:>2}. {r['plays']:>4}×  {tracker.track_label(r)}")
            print("\nTop artists:")
            for i, r in enumerate(top_artists(start, end), 1):
                print(f"  {i:>2}. {r['plays']:>4}×  {r['name']}")
        else:
            print(__doc__)
    except TrackerError as error:
        sys.exit(str(error))


if __name__ == "__main__":
    main()
