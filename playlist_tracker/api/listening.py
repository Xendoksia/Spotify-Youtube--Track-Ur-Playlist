"""
The Recently played tab and the mini player as data for the desktop window: what Spotify plays now, as the
recorder sees it (as ui/mini_player.py and the NowPlaying card), and the last plays grouped by day (as
ui/recent_plays.py).
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

from playlist_tracker.api.overview import cover_url
from playlist_tracker.core.i18n import number, t
from playlist_tracker.core.text import format_length
from playlist_tracker.music import listening, nowplaying
from playlist_tracker.ui.stats.text import duration_text, month_name, plays_text

RECENT_COUNT = 200


def now_playing(tracker: nowplaying.LocalTracker | None) -> dict:
    """The recorder's state ("off", "idle", "playing", "paused") and the song while one plays or is paused.
    position is the time into the song now; the window moves it on by itself between two asks."""
    if tracker is None:
        # Another copy of the app records
        return {"available": False, "enabled": False, "state": "off", "error": None, "play": None}
    status = tracker.status()
    play, state = status["play"], status["state"]
    shown = None
    if play and state in ("playing", "paused"):
        position = play.get("position")
        if position is not None and state == "playing" and play.get("position_at"):
            # Between two reads of the media session the song keeps going
            position += (time.monotonic() - play["position_at"]) * 1000
        duration = play.get("duration")
        if position is not None and duration:
            position = min(position, duration)
        shown = {"key": play["key"], "name": play["name"], "artist": play["artist"], "album": play["album"] or "",
                 "recorded": play["id"] is not None, "position": position, "duration": duration,
                 "listened": format_length(play["ms"]) or "0:00",
                 "image": cover_url(play["artist"], play["album"], play["name"])}
    return {"available": True, "enabled": tracker.enabled, "state": state, "error": status["error"], "play": shown}


def day_title(day, today) -> str:
    if day == today:
        return t("listening.today")
    if day == today - timedelta(days=1):
        return t("listening.yesterday")
    weekday = t("stats.weekdays").split(",")[day.weekday()]
    year = f" {day.year}" if day.year != today.year else ""
    return f"{day.day} {month_name(day.month)}{year}, {weekday}"


def recent() -> dict:
    """The last plays, newest first, under day headings with the whole day's totals."""
    today = datetime.now().astimezone().date()
    days: list[dict] = []
    for play in listening.recent_plays(RECENT_COUNT):
        moment = listening.from_utc(play["played_at"]).astimezone()
        if not days or days[-1]["date"] != moment.date():
            day = moment.date()
            # The whole day, also the plays older than the ones listed
            start = datetime(day.year, day.month, day.day).astimezone()
            totals = listening.summary(start, start + timedelta(days=1))
            summary = "  ·  ".join([plays_text(totals["plays"])]
                                   + ([duration_text(totals["minutes"])] if totals["minutes"] else []))
            days.append({"date": day, "title": day_title(day, today), "summary": summary, "plays": []})
        days[-1]["plays"].append({
            "id": play["id"], "key": play["track_key"], "time": f"{moment:%H:%M}", "title": play["name"],
            "subtitle": "  ·  ".join(part for part in (play["artist"], play["album"]) if part),
            "length": format_length(play["ms_played"]),
        })
    for day in days:
        day["date"] = day["date"].isoformat()
    return {"info": t("listening.info", count=number(sum(listening.counts().values()))),
            "empty": t("listening.empty"), "days": days}
