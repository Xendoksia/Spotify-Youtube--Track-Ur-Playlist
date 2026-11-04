"""
Dates and track names written out the same way everywhere.
"""

from __future__ import annotations

from datetime import datetime


def format_date(iso: str | None) -> str:
    """Convert an ISO timestamp to a readable local time."""
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso


def track_label(track: dict) -> str:
    return f"{track['artist']} - {track['name']}" if track.get("artist") else track.get("name", "")


def format_length(ms: int | None) -> str:
    """A length of time as m:ss, or "" when unknown."""
    if not ms:
        return ""
    seconds = ms // 1000
    return f"{seconds // 60}:{seconds % 60:02d}"
