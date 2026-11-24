"""
The artist and song similarity models in models/ (models/README.md): for each artist or song, the 50 most alike
in ListenBrainz' open listening data, best first. They work offline and are read once, on first use.
"""

from __future__ import annotations

import gzip
import json
import re
import sys
import threading
from array import array
from pathlib import Path

# Next to the code in the repository, inside the built backend's own folder once packed (build.py)
MODEL_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2])) / "models"


def loose(key: str) -> str:
    """A key without punctuation: the data spells "What I've Done" with a straight and a curly apostrophe alike,
    and dashes several ways."""
    return " ".join(re.sub(r"[^\w|]+", " ", key).split())


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
        # The song model's second table (version 2): RP3beta's neighbours, empty when its file is missing
        self._rp3 = array("i")
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
            rp3 = array("i")
            try:
                with gzip.open(folder / f"{self.kind}_neighbours_rp3.i32.gz", "rb") as f:
                    rp3.frombytes(f.read())
            except (OSError, ValueError):
                pass
            by_key: dict[str, int] = {}
            # Of the names with the same key, apart from punctuation, the one with most listeners
            for index, item in enumerate(items):
                known = by_key.get(loose(item["key"]))
                if known is None or item["listeners"] > items[known]["listeners"]:
                    by_key[loose(item["key"])] = index
            self.items, self._ids, self._by_key = items, ids, by_key
            self._rp3 = rp3 if items and len(rp3) == len(ids) else array("i")
            self._width = len(ids) // len(items) if items else 0
            self._loaded = True

    def available(self) -> bool:
        self._load()
        return bool(self.items)

    def find(self, key: str) -> int | None:
        self._load()
        return self._by_key.get(loose(key))

    def neighbours(self, index: int) -> list[int]:
        self._load()
        row = self._ids[index * self._width:(index + 1) * self._width]
        return [j for j in row if j >= 0]

    def neighbours_rp3(self, index: int) -> list[int] | None:
        """The RP3beta table's neighbours, or None without that table (the knn one alone is used then)."""
        self._load()
        if not self._rp3:
            return None
        row = self._rp3[index * self._width:(index + 1) * self._width]
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
                found.setdefault(loose(song["key"].split("|")[0]), []).append(index)
            for indices in found.values():
                indices.sort(key=lambda i: -songs.items[i]["listeners"])
            _songs_of = found
    return _songs_of.get(loose(artist_key), [])
