"""
The error the playlist clients and databases raise with a message for the user.
"""

from __future__ import annotations


class TrackerError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status
