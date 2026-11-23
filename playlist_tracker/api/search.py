"""
Searching the recorded plays for tracks, artists and albums as the window types, so their pages can be opened
from anywhere. Matching ignores case, accents and Turkish letters, so "goksel" finds Göksel.
"""

from __future__ import annotations

import unicodedata

from playlist_tracker.api.overview import artist_url, cover_url
from playlist_tracker.core.i18n import number
from playlist_tracker.music import listening
from playlist_tracker.music.text import plays_text, tracks_text

# Rows shown per kind
LIMIT = 6
# Shorter queries match too much to be useful
MIN_LENGTH = 2


def fold(text: str) -> str:
    """Text without case, accents or Turkish letters, its spaces collapsed, for matching."""
    text = (text or "").replace("ı", "i").replace("İ", "i")
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return " ".join("".join(c for c in decomposed if not unicodedata.combining(c)).split())


def _score(query: str, words: list[str], *fields: str) -> int | None:
    """How well the fields match: every word of the query must appear in them; the first field starting with the
    query is best, then a word of it starting so, then anywhere. None when they do not match."""
    joined = " ".join(fold(field) for field in fields)
    if not all(word in joined for word in words):
        return None
    first = fold(fields[0])
    if first.startswith(query):
        return 0
    if any(part.startswith(words[0]) for part in first.split()):
        return 1
    return 2


def _best(rows: list[dict], query: str, fields) -> list[dict]:
    words = query.split()
    scored = [(score, row) for row in rows if (score := _score(query, words, *fields(row))) is not None]
    scored.sort(key=lambda item: (item[0], -item[1]["plays"]))
    return [row for _, row in scored[:LIMIT]]


def search(query: str) -> dict:
    """The tracks, artists and albums whose names hold every word of the query, best and most played first."""
    folded = fold(query)
    if len(folded) < MIN_LENGTH:
        return {"query": query, "tracks": [], "artists": [], "albums": []}
    start, end = listening.period_range("all")
    tracks = _best(listening.top_tracks(start, end, 1_000_000), folded, lambda r: (r["name"], r["artist"]))
    # Artists of collaborations each on their own, so "Şanışer, Sena Şener" finds Şanışer and Sena Şener
    artists = _best(listening.credited_artists(), folded, lambda r: (r["name"],))
    albums = _best(listening.top_albums(start, end, 1_000_000), folded, lambda r: (r["album"], r["artist"]))
    return {
        "query": query,
        "tracks": [{"key": r["key"], "column": "track_key", "title": r["name"], "subtitle": r["artist"],
                    "value": r["plays"], "value_text": number(r["plays"]), "detail": plays_text(r["plays"]),
                    "image": cover_url(r["artist"], r["album"], r["name"])} for r in tracks],
        "artists": [{"key": r["key"], "column": "artist_key", "title": r["name"], "subtitle": tracks_text(r["tracks"]),
                     "value": r["plays"], "value_text": number(r["plays"]), "detail": plays_text(r["plays"]),
                     "image": artist_url(r["name"]), "round": True} for r in artists],
        "albums": [{"key": listening.album_key(r["artist_key"], r["album_lower"]), "column": listening.ALBUM,
                    "title": r["album"], "subtitle": r["artist"], "value": r["plays"],
                    "value_text": number(r["plays"]), "detail": plays_text(r["plays"]),
                    "image": cover_url(r["artist"], r["album"], r["name"])} for r in albums],
    }
