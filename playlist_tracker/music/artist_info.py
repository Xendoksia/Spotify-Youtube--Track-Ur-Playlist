"""
Short facts about an artist: whether it is a band or a solo artist, where it comes from, when it started,
its genres and its members. They are written out as a sentence or two on the artist's page, and the
genres feed the genre share in the statistics.

Facts come from MusicBrainz and place names in the interface language from Wikidata; neither needs an
account. Only the artist's name and MusicBrainz ids are sent. To avoid showing a different artist of the
same name, a MusicBrainz artist is used only when some of its releases match the album or track names
in the listening history. Everything is cached in artwork/artist_info.json.
"""

from __future__ import annotations

import json
import queue
import re
import threading
import time
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

from playlist_tracker.core.i18n import current as current_language, t
from playlist_tracker.music import listening
from playlist_tracker.music.artwork import ART_DIR, RETRY_SECONDS, SSL_CONTEXT
from playlist_tracker.music.listening import key

CACHE_PATH = ART_DIR / "artist_info.json"
MUSICBRAINZ_URL = "https://musicbrainz.org/ws/2"
WIKIDATA_URL = "https://www.wikidata.org/w/api.php"
USER_AGENT = "SpotifyPlaylistTracker/1.0 ( https://github.com/Xendoksia/Spotify-Youtube--Track-Ur-Playlist )"
# MusicBrainz allows one request per second
REQUEST_GAP = 1.1
# Same named artists compared against the listening history, best search matches first
MAX_CANDIDATES = 4
GENRES = 3
MEMBERS = 6
# Only these place types read naturally as "formed in <place>"
CITY_TYPES = ("City", "Municipality")
FIRST = 0  # queue priority of an artist page; the genre share fills in behind it
LATER = 1

_lock = threading.Lock()
_cache: dict | None = None
_queue: queue.PriorityQueue = queue.PriorityQueue()
_waiting: dict[str, list[tuple[object, Callable[[], None]]]] = {}
_worker: threading.Thread | None = None
_last_request = 0.0
_order = 0


def _load() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _cache = {}
        _cache.setdefault("artists", {})
        _cache.setdefault("areas", {})
    return _cache


def _save() -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = CACHE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(_cache, ensure_ascii=False), encoding="utf-8")
    temporary.replace(CACHE_PATH)


def _get(url: str, params: dict) -> dict:
    request = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20, context=SSL_CONTEXT) as response:
        return json.load(response)


def _musicbrainz(path: str, **params) -> dict:
    global _last_request
    wait = _last_request + REQUEST_GAP - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    for attempt in range(3):
        try:
            return _get(MUSICBRAINZ_URL + path, {**params, "fmt": "json"})
        except urllib.error.HTTPError as error:
            # 503 means too many requests at the moment
            if error.code != 503 or attempt == 2:
                raise
            time.sleep(REQUEST_GAP * (attempt + 2))
        finally:
            _last_request = time.monotonic()


def _title_key(title: str) -> str:
    """Compare titles without version notes such as " - Remastered" or " (Deluxe Edition)"."""
    return key(re.sub(r"\s*(\(.*?\)|\[.*?\])", "", (title or "").split(" - ")[0]))


def _name_variants(artist: str) -> list[str]:
    # Media controls sometimes list several artists in one name; the first is the main one
    first = re.split(r",|&| feat\.? | ft\.? | x ", artist, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    return list(dict.fromkeys(name for name in (artist, first) if name))


def _find_artist(artist: str, titles: set[str]) -> str | None:
    """The MusicBrainz id of the artist, or None when no same named artist has releases we listened to."""
    for name in _name_variants(artist):
        results = _musicbrainz("/artist/", query=f'artist:"{name}"', limit=10).get("artists") or []
        same_name = [a for a in results if key(a.get("name", "")) == key(name)
                     or any(key(alias.get("name", "")) == key(name) for alias in a.get("aliases") or [])]
        best, best_hits = None, 0
        for candidate in same_name[:MAX_CANDIDATES]:
            groups = _musicbrainz("/release-group", artist=candidate["id"], limit=100).get("release-groups") or []
            hits = len({_title_key(g.get("title", "")) for g in groups} & titles)
            if hits > best_hits:
                best, best_hits = candidate["id"], hits
        if best:
            return best
    return None


def _area(area: dict | None) -> dict | None:
    """Type and translated names of a MusicBrainz place, cached by id."""
    if not area or not area.get("id"):
        return None
    areas = _load()["areas"]
    if area["id"] in areas:
        return areas[area["id"]]
    details = _musicbrainz(f"/area/{area['id']}", inc="url-rels")
    names = {"en": details.get("name") or area.get("name")}
    wikidata = next((r["url"]["resource"].rsplit("/", 1)[-1] for r in details.get("relations") or []
                     if r.get("type") == "wikidata"), None)
    if wikidata:
        try:
            entity = _get(WIKIDATA_URL, {"action": "wbgetentities", "ids": wikidata, "props": "labels",
                                         "languages": "en|tr", "format": "json"})["entities"][wikidata]
            names.update({language: label["value"] for language, label in entity.get("labels", {}).items()})
        except (OSError, ValueError, KeyError):
            pass
    result = {"type": details.get("type"), "names": names}
    with _lock:
        areas[area["id"]] = result
    return result


def _look_up(artist: str, artist_key: str) -> dict:
    artist_id = _find_artist(artist, {_title_key(title) for title in listening.artist_titles(artist_key)} - {""})
    if not artist_id:
        return {"missing": time.time()}
    details = _musicbrainz(f"/artist/{artist_id}", inc="genres+artist-rels")
    life = details.get("life-span") or {}
    genres = sorted((g for g in details.get("genres") or [] if g.get("count", 0) > 0),
                    key=lambda g: -g["count"])
    members = [r["artist"]["name"] for r in details.get("relations") or []
               if r.get("type") == "member of band" and r.get("direction") == "backward" and not r.get("ended")]
    return {
        "id": artist_id,
        "type": details.get("type"),
        "area": _area(details.get("area")),
        "begin_area": _area(details.get("begin-area")),
        "begin": (life.get("begin") or "")[:4],
        "end": (life.get("end") or "")[:4],
        "ended": bool(life.get("ended")),
        "genres": [g["name"] for g in genres[:GENRES]],
        "members": list(dict.fromkeys(members)),
    }


def _work():
    while True:
        _, _, artist, artist_key = _queue.get()
        with _lock:
            # Asked again with a higher priority and already answered
            if artist_key not in _waiting:
                continue
        try:
            facts = _look_up(artist, artist_key)
        except Exception:  # offline or MusicBrainz unavailable: asked again next time
            facts = None
        with _lock:
            if facts is not None:
                _load()["artists"][artist_key] = facts
                _save()
            callbacks = _waiting.pop(artist_key, [])
        if facts is not None:
            for widget, done in callbacks:
                try:
                    widget.after(0, done)
                except (RuntimeError, tk.TclError):  # the window was closed meanwhile
                    pass


def cached(artist_key: str) -> dict | None:
    """Facts already known about the artist; None while unknown or not found."""
    with _lock:
        facts = _load()["artists"].get(artist_key)
    return facts if facts and "missing" not in facts else None


def waiting(artist_key: str) -> bool:
    """Whether the artist is still being looked up."""
    with _lock:
        return artist_key in _waiting


def request(artist: str, artist_key: str, widget, done: Callable[[], None], priority: int = FIRST) -> dict | None:
    """Return the cached facts, or look them up in the background and call done on the Tk thread."""
    global _worker, _order
    with _lock:
        facts = _load()["artists"].get(artist_key)
        if facts is not None and ("missing" not in facts or time.time() - facts["missing"] < RETRY_SECONDS):
            return facts if "missing" not in facts else None
        first_request = artist_key not in _waiting
        callbacks = _waiting.setdefault(artist_key, [])
        if (widget, done) not in callbacks:
            callbacks.append((widget, done))
        if first_request or priority == FIRST:
            # An artist page asked while the genre share is still filling in jumps the queue
            _order += 1
            _queue.put((priority, _order, artist, artist_key))
        if _worker is None:
            _worker = threading.Thread(target=_work, name="artist-info", daemon=True)
            _worker.start()
    return None


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} {t('info.and')} {items[-1]}"


# English country names that read with "the": "a band from the United States"
WITH_THE = ("United ", "Netherlands", "Philippines", "Czech Republic", "Dominican Republic", "Bahamas")


def _place(area: dict | None, country: bool = False) -> str:
    if not area:
        return ""
    names = area["names"]
    name = names.get(current_language()) or names.get("en") or ""
    if country and current_language() == "en" and name.startswith(WITH_THE):
        name = "the " + name
    return name


def _article(word: str) -> str:
    # English only; Turkish has no articles
    return "an" if word[:1].lower() in "aeiou" else "a"


def describe(facts: dict) -> str:
    """One to three short sentences about the artist, or "" when there is nothing to say."""
    person = facts.get("type") == "Person"
    kind = {"Person": "person", "Group": "group", "Orchestra": "orchestra", "Choir": "choir"}.get(
        facts.get("type"), "other")
    origin, genres = _place(facts.get("area"), country=True), _join(facts.get("genres") or [])
    sentences = []
    if origin or genres:
        if genres:
            what = t(f"info.kind_after_genre.{kind}", genres=genres)
        else:
            what = t(f"info.kind.{kind}")
        template = "info.origin" if origin else "info.no_origin"
        sentence = t(template, origin=origin, what=what, article=_article(what))
        sentences.append(sentence[:1].upper() + sentence[1:])

    begin_area = facts.get("begin_area")
    city = _place(begin_area) if begin_area and begin_area.get("type") in CITY_TYPES else ""
    begin, end = facts.get("begin"), facts.get("end")
    start = "born" if person else "formed"
    if begin and end and facts.get("ended") and not person:
        sentences.append(t("info.active", begin=begin, end=end))
    elif city or begin:
        variant = "city_year" if city and begin else "city" if city else "year"
        sentences.append(t(f"info.{start}.{variant}", city=city, year=begin))
    if person and end:
        sentences.append(t("info.died", year=end))

    members = facts.get("members") or []
    if members and not person:
        shown = members[:MEMBERS] + ([t("info.others")] if len(members) > MEMBERS else [])
        sentences.append(t("info.members", names=_join(shown)))
    return " ".join(sentences)
