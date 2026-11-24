"""
The artist and song similarity models in models/ (models/README.md): for each artist or song, the 50 most alike
in ListenBrainz' open listening data, best first. They work offline and are read once, on first use.
"""

from __future__ import annotations

import gzip
import json
import sys
import threading
from array import array
from pathlib import Path

# Next to the code in the repository, inside the built backend's own folder once packed (build.py)
MODEL_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2])) / "models"


class Model:
    """One of the two models: its items ({name, key, listeners}, songs also {artist, title}) and their
    neighbours."""

    def __init__(self, kind: str, folder: Path | None = None):
        self.kind = kind
        self.folder = folder
        self._lock = threading.Lock()
        self._loaded = False
        self.items: list[dict] = []
        self._ids = array("i")
        self._width = 0
        self._by_key: dict[str, int] = {}

    def _load(self) -> None:
        with self._lock:
            if self._loaded:
                return
            folder = self.folder or MODEL_DIR
            try:
                with gzip.open(folder / f"{self.kind}s.json.gz", "rt", encoding="utf-8") as f:
                    items = json.load(f)
                ids = array("i")
                with gzip.open(folder / f"{self.kind}_neighbours.i32.gz", "rb") as f:
                    ids.frombytes(f.read())  # little-endian, as Windows itself
            except (OSError, ValueError):
                items, ids = [], array("i")
            by_key: dict[str, int] = {}
            # Of the names with the same key, the one with most listeners
            for index, item in enumerate(items):
                known = by_key.get(item["key"])
                if known is None or item["listeners"] > items[known]["listeners"]:
                    by_key[item["key"]] = index
            self.items, self._ids, self._by_key = items, ids, by_key
            self._width = len(ids) // len(items) if items else 0
            self._loaded = True

    def available(self) -> bool:
        self._load()
        return bool(self.items)

    def find(self, key: str) -> int | None:
        self._load()
        return self._by_key.get(key)

    def neighbours(self, index: int) -> list[int]:
        self._load()
        row = self._ids[index * self._width:(index + 1) * self._width]
        return [j for j in row if j >= 0]


artists = Model("artist")
songs = Model("song")

_songs_of: dict[str, list[int]] | None = None
_songs_lock = threading.Lock()


def songs_of(artist_key: str) -> list[int]:
    """The model's songs of an artist (by the key of its first artist), most listeners first."""
    global _songs_of
    with _songs_lock:
        if _songs_of is None:
            found: dict[str, list[int]] = {}
            for index, song in enumerate(songs.items if songs.available() else []):
                found.setdefault(song["key"].split("|")[0], []).append(index)
            for indices in found.values():
                indices.sort(key=lambda i: -songs.items[i]["listeners"])
            _songs_of = found
    return _songs_of.get(artist_key, [])
