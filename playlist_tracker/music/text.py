"""
Numbers, durations and dates of the listening statistics written out in the interface language.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from playlist_tracker.core.i18n import number, t
from playlist_tracker.music import listening


def plays_text(count: int) -> str:
    return t("stats.plays_one") if count == 1 else t("stats.plays", count=number(count))


def tracks_text(count: int) -> str:
    return t("stats.different_tracks_one") if count == 1 else t("stats.different_tracks", count=number(count))


def summary_text(*parts: str, minutes: int) -> str:
    """Join details with the listening time; plays recorded without a duration add none, so 0 is left out."""
    return "  ·  ".join([*parts, duration_text(minutes)] if minutes else parts)


def duration_text(minutes: int) -> str:
    hours, minutes = divmod(int(minutes), 60)
    return t("stats.hours_minutes", hours=number(hours), minutes=minutes) if hours else t("stats.minutes",
                                                                                        minutes=minutes)


def month_name(month: int, short: bool = False) -> str:
    return t("stats.months_short" if short else "stats.months").split(",")[month - 1]


def date_text(iso: str) -> str:
    moment = listening.from_utc(iso).astimezone()
    return f"{moment.day} {month_name(moment.month)} {moment.year}"


def period_title(period: str, start: datetime, end: datetime) -> str:
    last = end - timedelta(days=1)
    if period == "week":
        if start.month == last.month:
            return f"{start.day} – {last.day} {month_name(last.month)} {last.year}"
        first_year = f" {start.year}" if start.year != last.year else ""
        return (f"{start.day} {month_name(start.month, True)}{first_year} – "
                f"{last.day} {month_name(last.month, True)} {last.year}")
    if period == "month":
        return f"{month_name(start.month)} {start.year}"
    if period == "year":
        return str(start.year)
    return t("stats.all_time")


def hour_buckets(hours: list[int]) -> list[dict]:
    """Plays per hour of the day as chart columns."""
    return [{"label": f"{hour:02d}", "value": count,
             "tooltip": f"{hour:02d}:00 – {(hour + 1) % 24:02d}:00\n{plays_text(count)}"}
            for hour, count in enumerate(hours)]
