"""
Listening history: nowplaying.py records what the Spotify desktop app plays on this computer, without
the Spotify API, and stores the plays in listening.db. All statistics are counted from these plays.
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from playlist_tracker.core.config import BASE_DIR

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
    uid TEXT,
    device TEXT,
    synced INTEGER NOT NULL DEFAULT 0,
    UNIQUE (source, played_at, track_key)
);
CREATE INDEX IF NOT EXISTS listens_time ON listens (played_at);
CREATE INDEX IF NOT EXISTS listens_track ON listens (track_key, played_at);
CREATE INDEX IF NOT EXISTS listens_artist ON listens (artist_key);
"""


@contextmanager
def open_db(db_path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    """A connection for a with block: committed at its end (rolled back on an error) and always closed.
    sqlite3's own with block does not close it, so the file stayed open until garbage collection."""
    db = sqlite3.connect(db_path)
    try:
        db.row_factory = sqlite3.Row
        db.executescript(SCHEMA)
        _migrate(db)
        with db:
            yield db
    finally:
        db.close()


def _migrate(db: sqlite3.Connection) -> None:
    _add_sync_columns(db)
    _move_spotify_plays(db)


def _add_sync_columns(db: sqlite3.Connection) -> None:
    """Give plays stored before syncing an id that is the same on every device (uid), the device that recorded
    them (device, NULL for this computer) and whether they still have to be sent (synced)."""
    columns = {row[1] for row in db.execute("PRAGMA table_info(listens)")}
    if "uid" not in columns:
        db.execute("ALTER TABLE listens ADD COLUMN uid TEXT")
        db.execute("ALTER TABLE listens ADD COLUMN device TEXT")
        db.execute("ALTER TABLE listens ADD COLUMN synced INTEGER NOT NULL DEFAULT 0")
        db.executemany("UPDATE listens SET uid = ? WHERE id = ?",
                       [(str(uuid.uuid4()), row[0]) for row in db.execute("SELECT id FROM listens")])
        db.commit()
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS listens_uid ON listens (uid)")
    db.execute("CREATE INDEX IF NOT EXISTS listens_unsynced ON listens (synced) WHERE synced = 0")


def _move_spotify_plays(db: sqlite3.Connection) -> None:
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


def name_variants(artist: str) -> list[str]:
    """Media controls sometimes list several artists in one name; the first is the main one."""
    first = re.split(r",|&| feat\.? | ft\.? | x ", artist, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    return list(dict.fromkeys(name for name in (artist, first) if name))


_CREDIT_SEPARATORS = re.compile(r",|&| feat\.? | ft\.? | x ", flags=re.IGNORECASE)


def credited(artist: str, solo_keys: set[str]) -> list[str]:
    """The artists one artist name credits: a collaboration such as "Şanışer, Sena Şener" is its artists when one
    of them is also heard on their own (solo_keys), so a band named "Simon & Garfunkel" stays one."""
    parts = [part.strip() for part in _CREDIT_SEPARATORS.split(artist or "") if part.strip()]
    if len(parts) > 1 and any(key(part) in solo_keys for part in parts):
        return parts
    return [artist]


def _artist_names(db: sqlite3.Connection) -> list[tuple[str, str]]:
    return [(r[0], r[1]) for r in db.execute("SELECT DISTINCT artist, artist_key FROM listens")]


def artist_keys(artist_key: str, db_path: Path = DB_PATH) -> list[str]:
    """The stored artist keys whose plays belong to an artist: its own and those of collaborations crediting it."""
    with open_db(db_path) as db:
        names = _artist_names(db)
    solo = {stored for _, stored in names}
    found = {stored for name, stored in names
             if stored == artist_key or artist_key in {key(part) for part in credited(name, solo)}}
    return sorted(found) or [artist_key]


def artist_name(artist_key: str, db_path: Path = DB_PATH) -> str | None:
    """An artist's name as written, also when it is only heard in collaborations."""
    with open_db(db_path) as db:
        names = _artist_names(db)
    solo = {stored for _, stored in names}
    for name, stored in names:
        for part in credited(name, solo):
            if key(part) == artist_key:
                return part
    return None


def credited_artists(db_path: Path = DB_PATH) -> list[dict]:
    """Every artist with their plays, collaborations counted for each artist they credit, most played first."""
    with open_db(db_path) as db:
        rows = db.execute("SELECT artist, artist_key, track_key FROM listens").fetchall()
    solo = {r[1] for r in rows}
    artists: dict[str, dict] = {}
    for artist, _, track in rows:
        for part in credited(artist, solo):
            entry = artists.setdefault(key(part), {"key": key(part), "name": part, "plays": 0, "track_keys": set()})
            entry["plays"] += 1
            entry["track_keys"].add(track)
    result = [{"key": a["key"], "name": a["name"], "plays": a["plays"], "tracks": len(a["track_keys"])}
              for a in artists.values()]
    return sorted(result, key=lambda a: -a["plays"])


def _artist_where(artist_key: str | None, db_path: Path) -> tuple[str, tuple]:
    """The WHERE condition for an artist's plays (collaborations crediting them included), or all plays."""
    if artist_key is None:
        return "1", ()
    keys = artist_keys(artist_key, db_path)
    return f"artist_key IN ({', '.join('?' * len(keys))})", tuple(keys)


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
        "INSERT OR IGNORE INTO listens (played_at, source, artist, name, album, artist_key, track_key, ms_played, "
        "uid, device, synced) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (play["played_at"], source, play["artist"], play["name"], play["album"], artist_key, track_key,
         play.get("ms_played"), play.get("uid") or str(uuid.uuid4()), play.get("device"),
         1 if play.get("device") else 0))
    return cursor.rowcount > 0


def record_local(play: dict, db_path: Path = DB_PATH) -> int | None:
    """Store a play detected on this computer; return its id, or None if it is already recorded."""
    with open_db(db_path) as db:
        if _insert(db, {**play, "ms_played": play["ms"]}, SOURCE_LOCAL):
            return db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return None


def update_local(play_id: int, ms_played: int, db_path: Path = DB_PATH) -> None:
    with open_db(db_path) as db:
        db.execute("UPDATE listens SET ms_played = ?, synced = 0 WHERE id = ?", (ms_played, play_id))


# Syncing between devices (see core/sync.py)

def unsynced(limit: int, db_path: Path = DB_PATH) -> list[dict]:
    """Plays recorded or changed since they were last sent."""
    with open_db(db_path) as db:
        return [dict(r) for r in db.execute(
            "SELECT uid, device, played_at, source, artist, name, album, ms_played FROM listens "
            "WHERE synced = 0 ORDER BY id LIMIT ?", (limit,))]


def unsynced_count(db_path: Path = DB_PATH) -> int:
    with open_db(db_path) as db:
        return db.execute("SELECT COUNT(*) FROM listens WHERE synced = 0").fetchone()[0]


def mark_synced(plays: list[dict], db_path: Path = DB_PATH) -> None:
    """Note plays as sent, unless their listening time changed in the meantime (then they go again)."""
    with open_db(db_path) as db:
        db.executemany("UPDATE listens SET synced = 1 WHERE uid = ? AND ms_played IS ?",
                       [(p["uid"], p["ms_played"]) for p in plays])


def all_uids(db_path: Path = DB_PATH) -> set[str]:
    """The ids of every play stored here, for comparing with the cloud."""
    with open_db(db_path) as db:
        return {r[0] for r in db.execute("SELECT uid FROM listens WHERE uid IS NOT NULL")}


def mark_unsynced(uids: set[str], db_path: Path = DB_PATH) -> None:
    """Plays the cloud turned out not to have: they go again with the next send."""
    with open_db(db_path) as db:
        db.executemany("UPDATE listens SET synced = 0 WHERE uid = ?", [(uid,) for uid in uids])


def mark_all_unsynced(db_path: Path = DB_PATH) -> None:
    """After logging out: every play goes to the next account logged in."""
    with open_db(db_path) as db:
        db.execute("UPDATE listens SET synced = 0")


def merge_remote(plays: list[dict], db_path: Path = DB_PATH) -> int:
    """Store plays recorded on other devices; return how many were new. A play already here keeps the longest
    listening time."""
    added = 0
    with open_db(db_path) as db:
        for play in plays:
            if db.execute("SELECT 1 FROM listens WHERE uid = ?", (play["uid"],)).fetchone():
                db.execute("UPDATE listens SET ms_played = MAX(COALESCE(ms_played, 0), ?) WHERE uid = ?",
                           (play["ms_played"] or 0, play["uid"]))
            elif _insert(db, play, play["source"]):
                added += 1
    return added


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


def summary_by(start: datetime, end: datetime, bucket: str, db_path: Path = DB_PATH) -> dict[str, dict]:
    """summary() per local day ('%Y-%m-%d'), month ('%Y-%m') or year ('%Y')."""
    pattern = {"day": "%Y-%m-%d", "month": "%Y-%m", "year": "%Y"}[bucket]
    with open_db(db_path) as db:
        return {r["bucket"]: {name: r[name] for name in ("plays", "minutes", "tracks", "artists")}
                for r in db.execute(
            "SELECT strftime(?, played_at, 'localtime') AS bucket, COUNT(*) AS plays, "
            "COALESCE(SUM(ms_played), 0) / 60000 AS minutes, "
            "COUNT(DISTINCT track_key) AS tracks, COUNT(DISTINCT artist_key) AS artists "
            "FROM listens WHERE played_at >= ? AND played_at < ? GROUP BY bucket", (pattern, *_range(start, end)))}


def top_tracks(start: datetime, end: datetime, limit: int = 10, artist_key: str | None = None,
               album: str | None = None, db_path: Path = DB_PATH) -> list[dict]:
    """Most played tracks of the period, optionally of one artist or one album (an album_key) only."""
    where, params = _filter(ALBUM, album) if album else _artist_where(artist_key, db_path)
    with open_db(db_path) as db:
        return [dict(r) for r in db.execute(
            "SELECT track_key AS key, MAX(name) AS name, MAX(artist) AS artist, MAX(album) AS album, "
            "COUNT(*) AS plays, COALESCE(SUM(ms_played), 0) / 60000 AS minutes, MAX(played_at) AS last_played "
            f"FROM listens WHERE played_at >= ? AND played_at < ? AND {where} "
            "GROUP BY track_key ORDER BY plays DESC, SUM(ms_played) DESC, last_played DESC LIMIT ?",
            (*_range(start, end), *params, limit))]


def rank_history(key: str, ends: list[datetime], db_path: Path = DB_PATH) -> list[tuple[int, int, int] | None]:
    """The track's place among all tracks, how many tracks there were and its own plays, counting the plays before
    each of the moments in ends (in order), ranked as top_tracks ranks them; None before its first play."""
    with open_db(db_path) as db:
        rows = db.execute("SELECT track_key, played_at, COALESCE(ms_played, 0) FROM listens ORDER BY played_at").fetchall()
    # Per track: plays, milliseconds and last play so far, compared as top_tracks orders them
    tallies: dict[str, list] = {}
    places: list[tuple[int, int, int] | None] = []
    index = 0
    for end in ends:
        until = to_utc(end)
        while index < len(rows) and rows[index][1] < until:
            track, played_at, ms = rows[index]
            tally = tallies.setdefault(track, [0, 0, ""])
            tally[0] += 1
            tally[1] += ms
            tally[2] = played_at
            index += 1
        mine = tallies.get(key)
        if mine is None:
            places.append(None)
            continue
        ahead = sum(1 for tally in tallies.values() if tally > mine)
        places.append((ahead + 1, len(tallies), mine[0]))
    return places


def top_albums(start: datetime, end: datetime, limit: int = 10, artist_key: str | None = None,
               db_path: Path = DB_PATH) -> list[dict]:
    """Most played albums of the period, optionally of one artist only; plays without an album name are left out."""
    where, params = _artist_where(artist_key, db_path)
    with open_db(db_path) as db:
        return [dict(r) for r in db.execute(
            "SELECT artist_key, LOWER(album) AS album_lower, MAX(artist) AS artist, MAX(album) AS album, "
            "MAX(name) AS name, COUNT(*) AS plays, "
            "MAX(played_at) AS last_played "
            "FROM listens WHERE played_at >= ? AND played_at < ? AND COALESCE(album, '') != '' "
            f"AND {where} "
            "GROUP BY artist_key, LOWER(album) ORDER BY plays DESC, SUM(ms_played) DESC, last_played DESC LIMIT ?",
            (*_range(start, end), *params, limit))]


def top_artists(start: datetime, end: datetime, limit: int = 10, db_path: Path = DB_PATH) -> list[dict]:
    with open_db(db_path) as db:
        return [dict(r) for r in db.execute(
            "SELECT artist_key AS key, MAX(artist) AS name, COUNT(*) AS plays, COUNT(DISTINCT track_key) AS tracks, "
            "COALESCE(SUM(ms_played), 0) / 60000 AS minutes "
            "FROM listens WHERE played_at >= ? AND played_at < ? "
            "GROUP BY artist_key ORDER BY plays DESC, SUM(ms_played) DESC, MAX(played_at) DESC LIMIT ?", (*_range(start, end), limit))]


def _first_heard(start: datetime, end: datetime, column: str, fields: str, db_path: Path) -> list[dict]:
    """Tracks or artists whose very first recorded play falls in the period, most played first."""
    with open_db(db_path) as db:
        return [dict(r) for r in db.execute(
            f"WITH firsts AS (SELECT {column} AS key, MIN(played_at) AS first_played FROM listens GROUP BY {column}) "
            f"SELECT l.{column} AS key, {fields}, COUNT(*) AS plays, "
            "COALESCE(SUM(l.ms_played), 0) / 60000 AS minutes, MIN(f.first_played) AS first_played "
            f"FROM listens l JOIN firsts f ON f.key = l.{column} "
            "WHERE f.first_played >= ? AND f.first_played < ? AND l.played_at >= ? AND l.played_at < ? "
            f"GROUP BY l.{column} ORDER BY plays DESC, SUM(l.ms_played) DESC, first_played DESC", _range(start, end) * 2)]


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
            "ORDER BY plays DESC, SUM(ms_played) DESC, last_played DESC LIMIT ?", (min_plays, since, limit))]


def diversity(start: datetime, end: datetime, db_path: Path = DB_PATH) -> dict:
    """How varied the period's listening was: its plays, different tracks and artists, the plays of its five
    most played artists, and the plays of tracks heard for the first time ever in it."""
    period = _range(start, end)
    with open_db(db_path) as db:
        row = dict(db.execute(
            "SELECT COUNT(*) AS plays, COUNT(DISTINCT track_key) AS tracks, COUNT(DISTINCT artist_key) AS artists "
            "FROM listens WHERE played_at >= ? AND played_at < ?", period).fetchone())
        row["top5"] = db.execute(
            "SELECT COALESCE(SUM(plays), 0) FROM (SELECT COUNT(*) AS plays FROM listens "
            "WHERE played_at >= ? AND played_at < ? GROUP BY artist_key ORDER BY plays DESC LIMIT 5)",
            period).fetchone()[0]
        row["new"] = db.execute(
            "WITH firsts AS (SELECT track_key, MIN(played_at) AS first_played FROM listens GROUP BY track_key) "
            "SELECT COUNT(*) FROM listens l JOIN firsts f USING (track_key) "
            "WHERE l.played_at >= ? AND l.played_at < ? AND f.first_played >= ? AND f.first_played < ?",
            period * 2).fetchone()[0]
    return row


def artist_days(start: datetime, end: datetime, db_path: Path = DB_PATH) -> list[tuple[str, str, int]]:
    """Plays per local day ('%Y-%m-%d') and artist in the period: (day, artist_key, plays)."""
    with open_db(db_path) as db:
        return [tuple(r) for r in db.execute(
            "SELECT strftime('%Y-%m-%d', played_at, 'localtime') AS day, artist_key, COUNT(*) FROM listens "
            "WHERE played_at >= ? AND played_at < ? GROUP BY day, artist_key ORDER BY day", _range(start, end))]


# Counts worth marking: of all plays, of one artist's plays and of one track's plays
TOTAL_STEPS = (100, 250, 500, 1000, 2500, 5000, 10_000, 25_000, 50_000, 100_000)
ARTIST_STEPS = (10, 25, 50, 100, 250, 500, 1000)
TRACK_STEPS = (10, 25, 50, 100, 250)
# The day an artist was first heard is a milestone once the artist has this many plays
MET_PLAYS = ARTIST_STEPS[0]
_milestones: dict = {}


def milestones(db_path: Path = DB_PATH) -> list[dict]:
    """Every milestone so far, newest first: the 100th play, an artist's 25th play, a track's 10th play, the day
    an artist who now has MET_PLAYS plays was first heard, and the start of recording. Each has kind ("total",
    "artist", "track", "met", "start"), at (UTC text), count, and for artists and tracks name, artist, key."""
    with open_db(db_path) as db:
        signature = (str(db_path), *db.execute("SELECT COUNT(*), MAX(id) FROM listens").fetchone())
        cached = _milestones.get(str(db_path))
        # Worked out again only when plays were added or changed
        if cached and cached[0] == signature:
            return cached[1]
        rows = db.execute("SELECT played_at, artist_key, artist, track_key, name FROM listens ORDER BY played_at").fetchall()
    found: list[dict] = []
    if rows:
        found.append({"kind": "start", "at": rows[0]["played_at"], "count": 0})
    artist_plays: dict[str, int] = {}
    track_plays: dict[str, int] = {}
    first_heard: dict[str, dict] = {}
    for index, row in enumerate(rows, start=1):
        if index in TOTAL_STEPS:
            found.append({"kind": "total", "at": row["played_at"], "count": index})
        artist = artist_plays[row["artist_key"]] = artist_plays.get(row["artist_key"], 0) + 1
        if artist == 1:
            first_heard[row["artist_key"]] = row
        if artist in ARTIST_STEPS:
            found.append({"kind": "artist", "at": row["played_at"], "count": artist, "name": row["artist"],
                          "key": row["artist_key"]})
        track = track_plays[row["track_key"]] = track_plays.get(row["track_key"], 0) + 1
        if track in TRACK_STEPS:
            found.append({"kind": "track", "at": row["played_at"], "count": track, "name": row["name"],
                          "artist": row["artist"], "key": row["track_key"]})
    for artist_key, row in first_heard.items():
        if artist_plays[artist_key] >= MET_PLAYS:
            found.append({"kind": "met", "at": row["played_at"], "count": artist_plays[artist_key],
                          "name": row["artist"], "key": artist_key})
    found.sort(key=lambda milestone: milestone["at"], reverse=True)
    _milestones[str(db_path)] = (signature, found)
    return found


def next_total_step(db_path: Path = DB_PATH) -> tuple[int, int] | None:
    """The next count of all plays worth marking and how many plays are left to it."""
    plays = summary(datetime(2000, 1, 1).astimezone(), datetime.now().astimezone() + timedelta(days=1),
                    db_path)["plays"]
    step = next((step for step in TOTAL_STEPS if step > plays), None)
    return (step, step - plays) if step else None


def plays_without_length(db_path: Path = DB_PATH) -> list[dict]:
    """Tracks with plays stored without a listening time (by an earlier version), with the longest
    time recorded for the same track, if any."""
    with open_db(db_path) as db:
        return [dict(r) for r in db.execute(
            "SELECT track_key AS key, MAX(artist) AS artist, MAX(name) AS name, "
            "(SELECT MAX(ms_played) FROM listens o WHERE o.track_key = l.track_key) AS known_ms "
            "FROM listens l WHERE ms_played IS NULL GROUP BY track_key")]


def set_missing_length(track_key: str, ms: int, db_path: Path = DB_PATH) -> None:
    """Give the plays of a track stored without a listening time the track's length (0: unknown)."""
    with open_db(db_path) as db:
        db.execute("UPDATE listens SET ms_played = ?, synced = 0 WHERE track_key = ? AND ms_played IS NULL",
                   (ms, track_key))


def heard_before(moment: datetime, column: str, db_path: Path = DB_PATH) -> set[str]:
    """Tracks or artists ("track_key" / "artist_key") with a play before the moment."""
    _check_column(column)
    with open_db(db_path) as db:
        return {row[0] for row in db.execute(f"SELECT DISTINCT {column} FROM listens WHERE played_at < ?",
                                             (to_utc(moment),))}


def ranks(start: datetime, end: datetime, column: str, db_path: Path = DB_PATH) -> dict[str, int]:
    """Rank (1 = most played) of every track or artist played in the period, ordered like top_tracks/top_artists.

    column: "track_key" or "artist_key".
    """
    _check_column(column)
    with open_db(db_path) as db:
        rows = db.execute(
            f"SELECT {column} FROM listens WHERE played_at >= ? AND played_at < ? "
            f"GROUP BY {column} ORDER BY COUNT(*) DESC, SUM(ms_played) DESC, MAX(played_at) DESC", _range(start, end))
        return {row[0]: index for index, row in enumerate(rows, start=1)}


def timeline(start: datetime, end: datetime, bucket: str, column: str | None = None, key: str | None = None,
             db_path: Path = DB_PATH) -> dict[str, int]:
    """Plays per local day ('%Y-%m-%d') or month ('%Y-%m'), optionally of one track, artist or album."""
    pattern = "%Y-%m-%d" if bucket == "day" else "%Y-%m"
    where, params = _filter(column, key, db_path) if column else ("1", ())
    with open_db(db_path) as db:
        return {r[0]: r[1] for r in db.execute(
            "SELECT strftime(?, played_at, 'localtime') AS bucket, COUNT(*) FROM listens "
            f"WHERE played_at >= ? AND played_at < ? AND {where} GROUP BY bucket",
            (pattern, *_range(start, end), *params))}


def _check_column(column: str) -> None:
    if column not in ("track_key", "artist_key"):
        raise ValueError(column)


# The "column" of an album for detail() and timeline(); its key comes from album_key()
ALBUM = "album"
_ALBUM_SEPARATOR = "\x1f"


def album_key(artist_key: str, album_lower: str) -> str:
    """The key of an album: its artist and its name as SQLite's LOWER() writes it (see top_albums)."""
    return f"{artist_key}{_ALBUM_SEPARATOR}{album_lower}"


def _filter(column: str, key: str, db_path: Path = DB_PATH) -> tuple[str, tuple]:
    """The WHERE condition picking the plays of one track, artist or album."""
    if column == ALBUM:
        artist_key, album = key.split(_ALBUM_SEPARATOR, 1)
        return "artist_key = ? AND LOWER(album) = ?", (artist_key, album)
    _check_column(column)
    if column == "artist_key":
        return _artist_where(key, db_path)
    return f"{column} = ?", (key,)


def detail(column: str, key: str, db_path: Path = DB_PATH) -> dict | None:
    """All time totals of one track (column "track_key"), artist ("artist_key") or album (ALBUM)."""
    where, params = _filter(column, key, db_path)
    with open_db(db_path) as db:
        row = db.execute(
            "SELECT MAX(name) AS name, MAX(artist) AS artist, MAX(album) AS album, MAX(artist_key) AS artist_key, "
            "LOWER(MAX(album)) AS album_lower, "
            "COUNT(*) AS plays, COALESCE(SUM(ms_played), 0) / 60000 AS minutes, COUNT(DISTINCT track_key) AS tracks, "
            "MIN(played_at) AS first_played, MAX(played_at) AS last_played "
            f"FROM listens WHERE {where}", params).fetchone()
    return dict(row) if row and row["plays"] else None


def artist_titles(artist_key: str, db_path: Path = DB_PATH) -> set[str]:
    """The album and track names heard from one artist."""
    with open_db(db_path) as db:
        where, params = _artist_where(artist_key, db_path)
        rows = db.execute(f"SELECT DISTINCT album, name FROM listens WHERE {where}", params).fetchall()
    return {title for row in rows for title in row if title}


def hours(start: datetime, end: datetime, column: str | None = None, key: str | None = None,
          db_path: Path = DB_PATH) -> list[int]:
    """Plays per local hour of the day, 0-23, optionally of one track, artist or album."""
    where, params = _filter(column, key, db_path) if column else ("1", ())
    counts_by_hour = [0] * 24
    with open_db(db_path) as db:
        for hour, count in db.execute(
                "SELECT CAST(strftime('%H', played_at, 'localtime') AS INTEGER), COUNT(*) FROM listens "
                f"WHERE played_at >= ? AND played_at < ? AND {where} GROUP BY 1", (*_range(start, end), *params)):
            counts_by_hour[hour] = count
    return counts_by_hour


# The days in a row at which a streak earns its next title, as the phone's streakLevels
STREAK_LEVELS = [3, 7, 14, 21, 30, 50, 100, 365]


def streak_level(days: int) -> int:
    """The level a run of days has reached, 0 before the first."""
    return sum(1 for step in STREAK_LEVELS if days >= step)


def streak_place(days: int) -> float:
    """Where a run of days stands on the ladder of levels, counted in stops, as the phone's streakPlace."""
    level = streak_level(days)
    if level == 0:
        return 0.0
    if level == len(STREAK_LEVELS):
        return len(STREAK_LEVELS) - 1.0
    start = STREAK_LEVELS[level - 1]
    return level - 1 + (days - start) / (STREAK_LEVELS[level] - start)


def streak_next_level(days: int) -> int | None:
    """The days at which the next level comes, or None at the highest."""
    return next((step for step in STREAK_LEVELS if step > days), None)


def current_run(days: set[date], today: date) -> tuple[int, bool, date | None]:
    """The run of days going on now (up to today, or up to yesterday while today is not among them yet): its
    length, whether today is in it, and its first day."""
    played = today in days
    day = today if played else today - timedelta(days=1)
    current = 0
    while day in days:
        current += 1
        day -= timedelta(days=1)
    return current, played, (day + timedelta(days=1) if current else None)


def days_with_artists(db_path: Path = DB_PATH) -> list[tuple[date, str]]:
    """Each local day with each artist played on it, for runs of one genre."""
    with open_db(db_path) as db:
        return [(date.fromisoformat(r[0]), r[1]) for r in db.execute(
            "SELECT DISTINCT date(played_at, 'localtime'), artist_key FROM listens") if r[0]]


def streak(today: date | None = None, db_path: Path = DB_PATH) -> dict:
    """Days in a row with at least one play, as the phone's streakOf: current (up to today, or up to yesterday
    while today has no play yet), today (today has a play), longest, before (the longest run that ended before the
    current one began), start (the current run's first day) and recent (the last 14 days, oldest first)."""
    today = today or datetime.now().date()
    with open_db(db_path) as db:
        days = {date.fromisoformat(r[0]) for r in db.execute(
            "SELECT DISTINCT date(played_at, 'localtime') FROM listens") if r[0]}
    current, played, start = current_run(days, today)
    longest = before = run = 0
    last = None
    for day in sorted(days):
        run = run + 1 if last is not None and day == last + timedelta(days=1) else 1
        last = day
        longest = max(longest, run)
        if start is None or day < start:
            before = max(before, run)
    return {"current": current, "today": played, "longest": longest, "before": before, "start": start,
            "recent": [today - timedelta(days=back) in days for back in range(13, -1, -1)]}


def streak_special(streak: dict) -> str | None:
    """"record" the day the current run first beats every earlier one, "level_up" the day it earns its next title,
    else None."""
    if not streak["today"]:
        return None
    current = streak["current"]
    if streak["before"] >= 3 and current == streak["before"] + 1:
        return "record"
    if current in STREAK_LEVELS:
        return "level_up"
    return None
