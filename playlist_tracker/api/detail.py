"""
The page of one track, artist or album as data for the desktop window, as the earlier window's detail page:
totals, plays over time, and for a track its album and the hours it is played at,
for an artist its most played tracks and a few facts, for an album its track list and how much was heard.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta
from typing import Callable

from playlist_tracker.api.overview import artist_url, cover_url
from playlist_tracker.core.i18n import number, t
from playlist_tracker.core.text import format_length
from playlist_tracker.music import artist_info, artwork, listening, styles
from playlist_tracker.music.text import date_text, duration_text, hour_buckets, month_name, plays_text, summary_text, tracks_text

ARTIST_TRACKS = 15
# Plays of tracks of an album fetched at most (the album's own tracks come from Deezer)
ALBUM_TRACKS = 100
# Up to this many days of history the chart shows days, after that months
DAILY_LIMIT = 62
MIN_DAYS = 14
COLUMNS = ("track_key", "artist_key", listening.ALBUM)

_looked_up: set[tuple[str, str]] = set()
_looked_up_lock = threading.Lock()


def tracklist(artist: str, album: str, arrived: Callable[[], None]) -> list[dict] | None:
    """The album's tracks from Deezer, looked up in the background the first time; arrived() when found."""
    tracks = artwork.cached_tracklist(artist, album)
    if tracks is None:
        with _looked_up_lock:
            if (artist, album) in _looked_up:
                return None
            _looked_up.add((artist, album))

        def look_up():
            try:
                artwork.fetch_tracklist(artist, album)
            except Exception:  # offline: shown without the album's own track list
                return
            arrived()
        threading.Thread(target=look_up, name="tracklist", daemon=True).start()
    return tracks


def track_row(track: dict, length: str = "") -> dict:
    return {"key": track["key"], "column": "track_key", "title": track["name"], "subtitle": length,
            "value": track["plays"], "value_text": number(track["plays"]),
            "detail": summary_text(plays_text(track["plays"]), minutes=track["minutes"])}


def album_rows(artist: str, album: str, album_key: str, arrived) -> tuple[list[dict], list[dict] | None]:
    """The album's tracks in album order with how often each was played (only the played ones while
    Deezer's track list is unknown), and that track list."""
    start, end = listening.period_range("all")
    played = listening.top_tracks(start, end, ALBUM_TRACKS, album=album_key)
    tracks = tracklist(artist, album, arrived)
    rows, left = [], list(played)
    for index, track in enumerate(tracks or []):
        match = next((p for p in left if artwork.same_title(p["name"], track["title"])), None)
        length = format_length(track["ms"])
        if match:
            left.remove(match)
            rows.append(track_row(match, length))
        else:
            rows.append({"key": f"unheard-{index}", "column": None, "title": track["title"], "subtitle": length,
                         "value": 0, "value_text": "—", "detail": t("detail.not_heard")})
    # Played tracks Deezer does not list (bonus tracks, other editions) come after
    rows += [track_row(track) for track in left]
    return rows, tracks


def timeline(column: str, key: str, info: dict) -> dict:
    first = listening.from_utc(info["first_played"]).astimezone()
    today = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    # At least two weeks, so a track heard only recently does not fill the chart with two huge columns
    start = min(first.replace(hour=0, minute=0, second=0, microsecond=0), today - timedelta(days=MIN_DAYS - 1))
    end = today + timedelta(days=1)
    if (end - start).days <= DAILY_LIMIT:
        counts = listening.timeline(start, end, "day", column, key)
        days = [start + timedelta(days=i) for i in range((end - start).days)]
        return {"title": t("stats.per_day"), "buckets": [{
            "label": str(day.day), "value": counts.get(day.strftime("%Y-%m-%d"), 0),
            "tooltip": f"{day.day} {month_name(day.month)}\n{plays_text(counts.get(day.strftime('%Y-%m-%d'), 0))}",
        } for day in days]}
    counts = listening.timeline(start, end, "month", column, key)
    buckets = []
    year, month = start.year, start.month
    while (year, month) <= (today.year, today.month):
        value = counts.get(f"{year}-{month:02d}", 0)
        buckets.append({"label": f"{month_name(month, True)} {year % 100:02d}", "value": value,
                        "tooltip": f"{month_name(month)} {year}\n{plays_text(value)}"})
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return {"title": t("stats.per_month"), "buckets": buckets}


def tile(name: str, value, text: str, kind: str = "number") -> dict:
    """kind: "number" and "duration" count up in the window, "text" (dates, names) is shown as it is."""
    return {"name": name, "label": t(f"detail.tile.{name}"), "value": value, "text": text, "kind": kind}


def detail(column: str, key: str, arrived: Callable[[], None]) -> dict | None:
    """The page's data, or None when nothing of it was played. arrived() is called when facts or a track
    list looked up in the background were found, so the window can ask again."""
    if column not in COLUMNS:
        raise ValueError(column)
    info = listening.detail(column, key)
    if not info:
        return None
    kind = "artist" if column == "artist_key" else "album" if column == listening.ALBUM else "track"
    title = info["artist"] if kind == "artist" else info["album"] if kind == "album" else info["name"]
    summary = summary_text(plays_text(info["plays"]), minutes=info["minutes"])
    hero = {"caption": t(f"detail.{kind}"), "title": title, "detail": summary, "about": "",
            "subtitle": info["artist"], "subtitle_link": {"column": "artist_key", "key": info["artist_key"]},
            "image": cover_url(info["artist"], info["album"], info["name"])}
    if kind == "artist":
        facts = artist_info.request(title, key, arrived)
        hero.update(subtitle=tracks_text(info["tracks"]), subtitle_link=None, image=artist_url(title),
                    about=artist_info.describe(facts) if facts else "")
    page = {"kind": kind, "column": column, "key": key, "title": title, "hero": hero,
            "timeline": timeline(column, key, info)}
    tiles = [tile("plays", info["plays"], number(info["plays"])),
             tile("time", info["minutes"], duration_text(info["minutes"]) if info["minutes"] else "—", "duration")]

    if kind == "album":
        rows, tracks = album_rows(info["artist"], info["album"], key, arrived)
        heard = sum(1 for row in rows if row["value"])
        favorite = max(rows, key=lambda row: row["value"]) if rows else None
        tiles += [tile("heard", heard, f"{number(heard)} / {number(len(rows))}" if tracks else number(heard), "text"),
                  tile("favorite", 0, favorite["title"] if favorite and favorite["value"] else "—", "text")]
        if tracks:
            length = sum(track["ms"] for track in tracks) // 60000
            hero["about"] = t("detail.album_length", tracks=number(len(tracks)), length=duration_text(length))
        share = heard / len(rows) if tracks and rows else 1.0
        page["progress"] = {
            "share": share,
            "text": t("detail.album_progress", percent=t("stats.percent", value=round(share * 100)))
                    if tracks else t("detail.album_progress_unknown"),
        }
        page["tracks"] = {"title": t("detail.album_tracks", heard=number(heard), total=number(len(rows)))
                          if tracks else t("detail.artist_tracks"), "rows": rows, "pictures": False}
    else:
        tiles += [tile("first", 0, date_text(info["first_played"]), "text"),
                  tile("last", 0, date_text(info["last_played"]), "text")]

    if kind == "artist":
        start, end = listening.period_range("all")
        page["tracks"] = {"title": t("detail.artist_tracks"), "pictures": True, "rows": [{
            **track_row(r, r["album"] or ""), "image": cover_url(r["artist"], r["album"], r["name"]),
        } for r in listening.top_tracks(start, end, ARTIST_TRACKS, artist_key=key)]}

    if kind == "track":
        start, end = listening.period_range("all")
        page["hours"] = {"title": t("detail.track_hours"),
                         "buckets": hour_buckets(listening.hours(start, end, column, key))}
        page["album"] = None
        if info["album"]:
            album_key = listening.album_key(info["artist_key"], info["album_lower"])
            rows, tracks = album_rows(info["artist"], info["album"], album_key, arrived)
            heard = sum(1 for row in rows if row["value"])
            page["album"] = {
                "caption": t("detail.album"), "key": album_key, "title": info["album"], "image": hero["image"],
                "heard": t("detail.album_heard", heard=number(heard), total=number(len(rows))) if tracks
                         else t("detail.album_heard_unknown", heard=number(heard)),
                "open": t("detail.album_open"),
            }
    if kind != "artist":
        # Its first styles on Discogs, after the album's length
        found = styles.request(info["artist"], info["artist_key"], info["album"] or None, info["name"], arrived)
        if found:
            hero["about"] = "  ·  ".join(part for part in (hero["about"], ", ".join(found[:styles.SHOWN])) if part)
    page["tiles"] = tiles
    # The page takes the color of its picture, as the statistics take their number one's
    picture = artwork.fetch_artist(title) if kind == "artist" else         artwork.fetch_cover(info["artist"], info["album"], info["name"])
    page["mood"] = artwork.mood(picture)
    return page
