"""
Spotify listening history (core + command line).

Spotify only exposes the last 50 played tracks, so each sync stores new plays in
listening.db and all statistics are counted from those recorded plays.
A play counts once Spotify registers it (after about 30 seconds of listening).

Command line usage:
    python listening.py sync                          Store new plays from Spotify
    python listening.py recent                        Show the last recorded plays
    python listening.py stats [week|month|year|all]   Show the most played tracks and artists
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import tracker
from i18n import t
from tracker import BASE_DIR, LoginRequired, SpotifyError, TrackerError, load_config

DB_PATH = BASE_DIR / "listening.db"
REQUIRED_SCOPE = "user-read-recently-played"
PERIODS = ("week", "month", "year", "all")
UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

SCHEMA = """
CREATE TABLE IF NOT EXISTS plays (
    played_at TEXT PRIMARY KEY,
    track_id TEXT,
    name TEXT, artist TEXT, album TEXT,
    duration_ms INTEGER,
    context_type TEXT, context_uri TEXT
);
CREATE TABLE IF NOT EXISTS play_artists (
    played_at TEXT,
    position INTEGER,
    artist_id TEXT,
    artist_name TEXT,
    PRIMARY KEY (played_at, position)
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE INDEX IF NOT EXISTS plays_track ON plays (track_id);
CREATE INDEX IF NOT EXISTS play_artists_artist ON play_artists (artist_id);
"""


def open_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def needs_login(config: dict) -> bool:
    """Sessions created before listening history existed lack the recently-played permission."""
    return not config.get("REFRESH_TOKEN") or REQUIRED_SCOPE not in config.get("SCOPE", "").split()


def to_utc(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime(UTC_FORMAT)


def fetch_recent(client) -> list[dict]:
    """Return the last 50 plays of the logged-in user, oldest first."""
    if needs_login(load_config()):
        raise LoginRequired(t("listening.login_again"))
    try:
        page = client.get("/me/player/recently-played?limit=50")
    except SpotifyError as error:
        if error.status in (401, 403):
            raise LoginRequired(t("listening.login_again"), error.status)
        raise
    plays = []
    for item in page.get("items") or []:
        track = item.get("track") or {}
        if not item.get("played_at") or not track:
            continue
        context = item.get("context") or {}
        artists = [a for a in track.get("artists") or [] if a.get("name")]
        plays.append({
            "played_at": to_utc(datetime.fromisoformat(item["played_at"].replace("Z", "+00:00"))),
            # Local files have no id, their uri is stable instead
            "track_id": track.get("id") or track.get("uri") or track.get("name"),
            "name": track.get("name") or "(untitled)",
            "artist": ", ".join(a["name"] for a in artists),
            "album": (track.get("album") or {}).get("name") or "",
            "duration_ms": track.get("duration_ms") or 0,
            "context_type": context.get("type") or "",
            "context_uri": context.get("uri") or "",
            "artists": [(a.get("id") or a["name"], a["name"]) for a in artists],
        })
    return sorted(plays, key=lambda p: p["played_at"])


def sync(client, db_path: Path = DB_PATH) -> int:
    """Store plays that are not recorded yet and return how many were new."""
    plays = fetch_recent(client)
    new = 0
    with open_db(db_path) as db:
        for p in plays:
            cursor = db.execute(
                "INSERT OR IGNORE INTO plays (played_at, track_id, name, artist, album, duration_ms, "
                "context_type, context_uri) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (p["played_at"], p["track_id"], p["name"], p["artist"], p["album"], p["duration_ms"],
                 p["context_type"], p["context_uri"]),
            )
            if cursor.rowcount:
                new += 1
                db.executemany(
                    "INSERT OR IGNORE INTO play_artists (played_at, position, artist_id, artist_name) "
                    "VALUES (?, ?, ?, ?)",
                    [(p["played_at"], i, artist_id, name) for i, (artist_id, name) in enumerate(p["artists"])],
                )
        db.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('last_sync', ?)",
                   (datetime.now().astimezone().isoformat(timespec="seconds"),))
    return new


def last_sync(db_path: Path = DB_PATH) -> str | None:
    with open_db(db_path) as db:
        row = db.execute("SELECT value FROM meta WHERE key = 'last_sync'").fetchone()
        return row["value"] if row else None


def recent_plays(limit: int = 200, db_path: Path = DB_PATH) -> list[dict]:
    with open_db(db_path) as db:
        return [dict(r) for r in db.execute("SELECT * FROM plays ORDER BY played_at DESC LIMIT ?", (limit,))]


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
        row = db.execute(
            "SELECT COUNT(*) AS plays, COALESCE(SUM(duration_ms), 0) / 60000 AS minutes, "
            "COUNT(DISTINCT track_id) AS tracks FROM plays WHERE played_at >= ? AND played_at < ?",
            _range(start, end)).fetchone()
        artists = db.execute(
            "SELECT COUNT(DISTINCT a.artist_id) FROM play_artists a JOIN plays p USING (played_at) "
            "WHERE p.played_at >= ? AND p.played_at < ?", _range(start, end)).fetchone()[0]
    return {**dict(row), "artists": artists}


def top_tracks(start: datetime, end: datetime, limit: int = 10, db_path: Path = DB_PATH) -> list[dict]:
    with open_db(db_path) as db:
        return [dict(r) for r in db.execute(
            "SELECT track_id, name, artist, COUNT(*) AS plays, SUM(duration_ms) / 60000 AS minutes, "
            "MAX(played_at) AS last_played FROM plays WHERE played_at >= ? AND played_at < ? "
            "GROUP BY track_id ORDER BY plays DESC, minutes DESC, last_played DESC LIMIT ?",
            (*_range(start, end), limit))]


def top_artists(start: datetime, end: datetime, limit: int = 10, db_path: Path = DB_PATH) -> list[dict]:
    """Every artist of a track gets the play, so features count for both artists."""
    with open_db(db_path) as db:
        return [dict(r) for r in db.execute(
            "SELECT a.artist_id, MAX(a.artist_name) AS name, COUNT(*) AS plays, "
            "SUM(p.duration_ms) / 60000 AS minutes, COUNT(DISTINCT p.track_id) AS tracks "
            "FROM play_artists a JOIN plays p USING (played_at) WHERE p.played_at >= ? AND p.played_at < ? "
            "GROUP BY a.artist_id ORDER BY plays DESC, minutes DESC LIMIT ?",
            (*_range(start, end), limit))]


def timeline(start: datetime, end: datetime, bucket: str, db_path: Path = DB_PATH) -> dict[str, int]:
    """Plays per local day ('%Y-%m-%d') or month ('%Y-%m')."""
    pattern = "%Y-%m-%d" if bucket == "day" else "%Y-%m"
    with open_db(db_path) as db:
        return {r[0]: r[1] for r in db.execute(
            "SELECT strftime(?, played_at, 'localtime') AS bucket, COUNT(*) FROM plays "
            "WHERE played_at >= ? AND played_at < ? GROUP BY bucket", (pattern, *_range(start, end)))}


def hours(start: datetime, end: datetime, db_path: Path = DB_PATH) -> list[int]:
    """Plays per local hour of the day, 0-23."""
    counts = [0] * 24
    with open_db(db_path) as db:
        for hour, count in db.execute(
                "SELECT CAST(strftime('%H', played_at, 'localtime') AS INTEGER), COUNT(*) FROM plays "
                "WHERE played_at >= ? AND played_at < ? GROUP BY 1", _range(start, end)):
            counts[hour] = count
    return counts


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    command, args = sys.argv[1].lower(), sys.argv[2:]
    try:
        if command == "sync":
            print(f"{sync(tracker.connect())} new plays stored.")
        elif command == "recent":
            for p in reversed(recent_plays(30)):
                print(f"{tracker.format_date(p['played_at'])}  {tracker.track_label(p)}")
        elif command == "stats" and (not args or args[0] in PERIODS):
            start, end = period_range(args[0] if args else "week")
            s = summary(start, end)
            print(f"{start:%Y-%m-%d} – {end - timedelta(seconds=1):%Y-%m-%d}: {s['plays']} plays, "
                  f"~{s['minutes']} minutes, {s['tracks']} tracks, {s['artists']} artists\n")
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
