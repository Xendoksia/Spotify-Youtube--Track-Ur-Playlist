"""
The statistics overview as data for the desktop window (desktop/): the same numbers and texts as the earlier
window's overview, with changes named by kind instead of color so the window picks the colors.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from urllib.parse import urlencode

from playlist_tracker.core.i18n import number, t
from playlist_tracker.music import listening
from playlist_tracker.music.text import (duration_text, hour_buckets, month_name, period_title, plays_text,
                                            summary_text, tracks_text)

TOP_COUNT = 10
TILES = (("plays", "plays", number), ("time", "minutes", duration_text),
         ("tracks", "tracks", number), ("artists", "artists", number))


def cover_url(artist: str, album: str | None, name: str) -> str:
    return "/api/cover?" + urlencode({"artist": artist or "", "album": album or "", "name": name or ""})


def artist_url(name: str) -> str:
    return "/api/artist-photo?" + urlencode({"name": name or ""})


def overview(period: str, offset: int) -> dict:
    if period not in listening.PERIODS:
        raise ValueError(period)
    offset = 0 if period == "all" else max(0, offset)
    start, end = listening.period_range(period, offset)
    if period == "all":
        start = listening.first_play() or start
    tracks = listening.top_tracks(start, end, TOP_COUNT)
    artists = listening.top_artists(start, end, TOP_COUNT)
    track_change = rank_changes(period, offset, start, "track_key")
    artist_change = rank_changes(period, offset, start, "artist_key")
    return {
        "period": period,
        "offset": offset,
        "title": period_title(period, start, end),
        "can_previous": period != "all",
        "can_next": period != "all" and offset > 0,
        "tiles": tiles(period, offset, start, end),
        "track_hero": track_hero(tracks[0], track_change) if tracks else None,
        "artist_hero": artist_hero(artists[0], artist_change) if artists else None,
        "top_tracks": [{
            "key": r["key"], "rank": rank, "title": r["name"], "subtitle": r["artist"],
            "value": r["plays"], "value_text": number(r["plays"]),
            "detail": summary_text(plays_text(r["plays"]), minutes=r["minutes"]),
            "change": track_change(r["key"], rank), "image": cover_url(r["artist"], r["album"], r["name"]),
        } for rank, r in enumerate(tracks[1:], start=2)],
        "top_artists": [{
            "key": r["key"], "rank": rank, "title": r["name"], "subtitle": tracks_text(r["tracks"]),
            "value": r["plays"], "value_text": number(r["plays"]),
            "detail": summary_text(plays_text(r["plays"]), tracks_text(r["tracks"]), minutes=r["minutes"]),
            "change": artist_change(r["key"], rank), "image": artist_url(r["name"]),
        } for rank, r in enumerate(artists[1:], start=2)],
        "timeline": timeline(period, start, end),
        "hours": {"title": t("stats.hours"), "buckets": hour_buckets(listening.hours(start, end))},
    }


def tiles(period: str, offset: int, start: datetime, end: datetime) -> list[dict]:
    current = listening.summary(start, end)
    previous = None
    if period != "all":
        previous_start, previous_end = listening.period_range(period, offset + 1)
        if offset == 0:
            # The current period is still running, so compare with the same stretch of the previous one
            previous_end = min(previous_end, previous_start + (datetime.now().astimezone() - start))
        previous = listening.summary(previous_start, previous_end)
    bucket, points = trend_points(period, start, end)
    by_bucket = listening.summary_by(start, end, bucket) if len(points) > 1 else {}
    result = []
    for name, key, text in TILES:
        label = t(f"stats.tile.{name}")
        delta = None
        if previous and previous[key]:
            change = round((current[key] - previous[key]) * 100 / previous[key])
            arrow = "▲" if change > 0 else "▼" if change < 0 else "="
            delta = {"text": f"{arrow} {t('stats.percent', value=abs(change))}  {t(f'stats.vs.{period}')}",
                     "kind": "up" if change > 0 else "down" if change < 0 else "same"}
        result.append({"name": name, "label": label, "value": current[key],
                       "text": text(current[key]), "kind": "duration" if name == "time" else "number",
                       "delta": delta,
                       "trend": trend(by_bucket, points, key, label, text)})
    return result


def trend(by_bucket: dict[str, dict], points: list[tuple[str, str]], key: str, label: str, text) -> list[dict]:
    """A tile's value per day, month or year of the period, for its trend line."""
    result = []
    for point, when in points if by_bucket else []:
        value = by_bucket.get(point, {}).get(key, 0)
        result.append({"value": value, "tooltip": f"{when}\n{label}: {text(value)}"})
    return result


def trend_points(period: str, start: datetime, end: datetime) -> tuple[str, list[tuple[str, str]]]:
    """The tiles' trend lines: the period's days (or months, or years) up to now as (bucket, label)."""
    last = min(end, datetime.now().astimezone()) - timedelta(seconds=1)
    if period in ("week", "month") or (last - start).days < 62:
        days = [start + timedelta(days=i) for i in range((last - start).days + 1)]
        return "day", [(day.strftime("%Y-%m-%d"), f"{day.day} {month_name(day.month)}") for day in days]
    months = []
    year, month = start.year, start.month
    while (year, month) <= (last.year, last.month):
        months.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    if len(months) > 36:
        return "year", [(str(year), str(year)) for year in range(start.year, last.year + 1)]
    return "month", [(f"{year}-{month:02d}", f"{month_name(month)} {year}") for year, month in months]


def track_hero(top: dict, change) -> dict:
    return {"key": top["key"], "caption": t("stats.hero.track"), "title": top["name"], "subtitle": top["artist"],
            "detail": summary_text(plays_text(top["plays"]), minutes=top["minutes"]),
            "change": change(top["key"], 1), "image": cover_url(top["artist"], top["album"], top["name"])}


def artist_hero(top: dict, change) -> dict:
    return {"key": top["key"], "caption": t("stats.hero.artist"), "title": top["name"],
            "subtitle": tracks_text(top["tracks"]),
            "detail": summary_text(plays_text(top["plays"]), minutes=top["minutes"]),
            "change": change(top["key"], 1), "image": artist_url(top["name"])}


def rank_changes(period: str, offset: int, start: datetime, column: str):
    """change(key, rank) → {kind, short, long} compared with the whole previous period, or None."""
    if period == "all":
        return lambda key, rank: None
    previous_start, previous_end = listening.period_range(period, offset + 1)
    previous = listening.ranks(previous_start, previous_end, column)
    known = listening.heard_before(start, column)
    # Songs heard before recording began look new too, so new and back are only told apart
    # once the whole previous period was recorded
    first = listening.first_play()
    recorded_before = first is not None and first <= previous_start

    def change(key, rank):
        before = previous.get(key)
        if before is None:
            if not recorded_before:
                return None
            # New means heard for the first time ever, like the discoveries; one heard before
            # but not in the previous period is back
            if key in known:
                return {"kind": "back", "short": t("stats.change.back"), "long": t("stats.change.back_long")}
            return {"kind": "new", "short": t("stats.change.new"), "long": t("stats.change.new_long")}
        if before == rank:
            return {"kind": "same", "short": "=", "long": t("stats.change.same")}
        arrow = "▲" if before > rank else "▼"
        return {"kind": "up" if before > rank else "down", "short": f"{arrow}{abs(before - rank)}",
                "long": t("stats.change.moved", arrow=arrow, count=abs(before - rank), rank=before)}
    return change


def timeline(period: str, start: datetime, end: datetime) -> dict:
    if period in ("week", "month"):
        counts = listening.timeline(start, end, "day")
        days = [start + timedelta(days=i) for i in range((end - start).days)]
        buckets = [{
            "label": t("stats.weekdays").split(",")[day.weekday()] if period == "week" else str(day.day),
            "value": counts.get(day.strftime("%Y-%m-%d"), 0),
            "tooltip": f"{day.day} {month_name(day.month)}\n{plays_text(counts.get(day.strftime('%Y-%m-%d'), 0))}",
        } for day in days]
        return {"title": t("stats.per_day"), "buckets": buckets}
    counts = listening.timeline(start, end, "month")
    months = []
    year, month = start.year, start.month
    last = end - timedelta(days=1)
    while (year, month) <= (last.year, last.month):
        months.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    if len(months) > 36:
        totals: dict[int, int] = {}
        for (year, month) in months:
            totals[year] = totals.get(year, 0) + counts.get(f"{year}-{month:02d}", 0)
        return {"title": t("stats.per_year"),
                "buckets": [{"label": str(year), "value": value, "tooltip": f"{year}\n{plays_text(value)}"}
                            for year, value in totals.items()]}
    buckets = []
    for year, month in months:
        value = counts.get(f"{year}-{month:02d}", 0)
        label = month_name(month, True)
        if period == "all":
            label += f" {year % 100:02d}"
        buckets.append({"label": label, "value": value, "tooltip": f"{month_name(month)} {year}\n{plays_text(value)}"})
    return {"title": t("stats.per_month"), "buckets": buckets}
