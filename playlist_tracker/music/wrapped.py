"""
When the monthly (or yearly) summary is there and who saw it: it is there only on the first days of a month
(SHOW_DAYS), for the month before, and on the first days of January for the year before too. It opens by itself
the first time the window is seen on one of those days (AUTO_OPEN, the year first), and a notification says it is
ready (notice_due). Until seen it waits behind the bell (inbox); once seen it is gone, to keep it special. The
slides are made in api/wrapped.py.
"""

from __future__ import annotations

from datetime import datetime

from playlist_tracker.core.config import load_config, save_config
from playlist_tracker.music import listening

# Days of the month on which the summary of the previous month can be seen
SHOW_DAYS = (1, 2)
# Open it by itself the first time the window is shown on one of those days
AUTO_OPEN = True
# The "ready" notification comes on the first of those days from this hour, not to come at midnight
NOTICE_HOUR = 10
TOP = 5


def available_month() -> tuple[datetime, datetime] | None:
    """The previous month on the first days of a month, if it has plays; otherwise there is no summary."""
    if datetime.now().day not in SHOW_DAYS:
        return None
    previous = listening.period_range("month", 1)
    return previous if listening.summary(*previous)["plays"] else None


def available_year() -> tuple[datetime, datetime] | None:
    """The previous year on the first days of January, if it has plays."""
    now = datetime.now()
    if now.month != 1 or now.day not in SHOW_DAYS:
        return None
    previous = listening.period_range("year", 1)
    return previous if listening.summary(*previous)["plays"] else None


def available() -> list[tuple[datetime, datetime]]:
    """The summaries there are today, the year's first."""
    return [summary for summary in (available_year(), available_month()) if summary]


def is_year(start: datetime, end: datetime) -> bool:
    return start.month == 1 and end.month == 1 and end.year == start.year + 1


def _key(summary: tuple[datetime, datetime]) -> str:
    start = summary[0]
    return str(start.year) if is_year(*summary) else start.strftime("%Y-%m")


def _setting(summary: tuple[datetime, datetime], what: str) -> str:
    """WRAPPED_SHOWN / WRAPPED_NOTIFIED for a month, WRAPPED_YEAR_... for a year."""
    return f"WRAPPED_YEAR_{what}" if is_year(*summary) else f"WRAPPED_{what}"


def inbox() -> list[tuple[datetime, datetime]]:
    """The summaries ready and not seen yet, behind the bell: last month's all through this month and in January
    last year's too, so one whose notification was missed is still there. Opening one takes it out (seen)."""
    candidates = [listening.period_range("month", 1)]
    if datetime.now().month == 1:
        candidates.insert(0, listening.period_range("year", 1))
    config = load_config()
    return [summary for summary in candidates
            if config.get(_setting(summary, "SHOWN")) != _key(summary) and listening.summary(*summary)["plays"]]


def seen(summary: tuple[datetime, datetime]) -> None:
    """Opened: out of the box, when it was there (another month's summary leaves it as it is)."""
    if _key(summary) in {_key(waiting) for waiting in inbox()}:
        mark_shown(summary)


def month_to_show() -> tuple[datetime, datetime]:
    """For looking at the summary on any day (the window's --summary): the previous month, or this one while the
    previous has no plays."""
    previous = listening.period_range("month", 1)
    return previous if listening.summary(*previous)["plays"] else listening.period_range("month")


def auto_open_due() -> tuple[datetime, datetime] | None:
    """The summary to open by itself, once each (needs AUTO_OPEN): in January the year's, then the month's."""
    if not AUTO_OPEN:
        return None
    config = load_config()
    return next((s for s in available() if config.get(_setting(s, "SHOWN")) != _key(s)), None)


def notice_due() -> tuple[datetime, datetime] | None:
    """The summary to tell about with a notification, once: it is there and was not seen yet."""
    now = datetime.now()
    if now.day == SHOW_DAYS[0] and now.hour < NOTICE_HOUR:
        return None
    config = load_config()
    return next((s for s in available() if _key(s) not in (config.get(_setting(s, "SHOWN")),
                                                            config.get(_setting(s, "NOTIFIED")))), None)


def _mark(summary: tuple[datetime, datetime], what: str) -> None:
    config = load_config()
    config[_setting(summary, what)] = _key(summary)
    save_config(config)


def mark_notified(summary: tuple[datetime, datetime]) -> None:
    _mark(summary, "NOTIFIED")


def mark_shown(summary: tuple[datetime, datetime]) -> None:
    _mark(summary, "SHOWN")
