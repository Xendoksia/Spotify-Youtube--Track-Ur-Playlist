"""
The page of one track, artist or album as data for the desktop window, as the earlier window's detail page:
totals, plays over time, and for a track its album and the hours it is played at,
for an artist its most played tracks and a few facts, for an album its track list and how much was heard.
"""

from __future__ import annotations

import threading
from datetime import date, datetime, timedelta
from typing import Callable

from playlist_tracker.api.overview import artist_url, cover_url
from playlist_tracker.core.i18n import number, t
from playlist_tracker.core.text import format_length
from playlist_tracker.music import artist_info, artwork, listening, recommend
from playlist_tracker.music.text import date_text, duration_text, hour_buckets, month_name, plays_text, summary_text, tracks_text

ARTIST_TRACKS = 15
ARTIST_ALBUMS = 10
# More rows than there are tracks, to find one's place among all of them
ALL_TRACKS = 1_000_000
# Plays of tracks of an album fetched at most (the album's own tracks come from Deezer)
ALBUM_TRACKS = 100
# Up to this many days of history the chart shows days, after that months
DAILY_LIMIT = 62
MIN_DAYS = 14
COLUMNS = ("track_key", "artist_key", listening.ALBUM)
DAY_PARTS = ("night", "morning", "afternoon", "evening")
# Share of the plays a part of the day needs to be called the usual one
DAY_PART_LEAD = 0.4
# An artist's last days compared with as many days before them
TREND_DAYS = 7
# The track's climb marks the day it first reached this place or better
TOP_PLACES = 10

_looked_up: set[tuple[str, str]] = set()
_looked_up_lock = threading.Lock()


def tracklist(artist: str, album: str, arrived: Callable[[], None]) -> list[dict] | None:
    """The album's tracks from Deezer, looked up in the background the first time; arrived() when found."""
    tracks = artwork.cached_tracklist(artist, album)
    if tracks is None:
        with _looked_up_lock:
            if (artist, album) in _looked_up:
                return None
            _looked_up.add((artist, album))

        def look_up():
            try:
                artwork.fetch_tracklist(artist, album)
            except Exception:  # offline: shown without the album's own track list
                return
            arrived()
        threading.Thread(target=look_up, name="tracklist", daemon=True).start()
    return tracks


def track_row(track: dict, length: str = "") -> dict:
    return {"key": track["key"], "column": "track_key", "title": track["name"], "subtitle": length,
            "value": track["plays"], "value_text": number(track["plays"]),
            "detail": summary_text(plays_text(track["plays"]), minutes=track["minutes"])}


def album_rows(artist: str, album: str, album_key: str, arrived) -> tuple[list[dict], list[dict] | None]:
    """The album's tracks in album order with how often each was played (only the played ones while
    Deezer's track list is unknown), and that track list."""
    start, end = listening.period_range("all")
    played = listening.top_tracks(start, end, ALBUM_TRACKS, album=album_key)
    tracks = tracklist(artist, album, arrived)
    rows, left = [], list(played)
    for index, track in enumerate(tracks or []):
        match = next((p for p in left if artwork.same_title(p["name"], track["title"])), None)
        length = format_length(track["ms"])
        if match:
            left.remove(match)
            rows.append(track_row(match, length))
        else:
            rows.append({"key": f"unheard-{index}", "column": None, "title": track["title"], "subtitle": length,
                         "value": 0, "value_text": "—", "detail": t("detail.not_heard")})
    # Played tracks Deezer does not list (bonus tracks, other editions) come after
    rows += [track_row(track) for track in left]
    return rows, tracks


def timeline(column: str, key: str, info: dict) -> dict:
    first = listening.from_utc(info["first_played"]).astimezone()
    today = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    # At least two weeks, so a track heard only recently does not fill the chart with two huge columns
    start = min(first.replace(hour=0, minute=0, second=0, microsecond=0), today - timedelta(days=MIN_DAYS - 1))
    end = today + timedelta(days=1)
    if (end - start).days <= DAILY_LIMIT:
        counts = listening.timeline(start, end, "day", column, key)
        days = [start + timedelta(days=i) for i in range((end - start).days)]
        return {"title": t("stats.per_day"), "buckets": [{
            "label": str(day.day), "value": counts.get(day.strftime("%Y-%m-%d"), 0),
            "tooltip": f"{day.day} {month_name(day.month)}\n{plays_text(counts.get(day.strftime('%Y-%m-%d'), 0))}",
        } for day in days]}
    counts = listening.timeline(start, end, "month", column, key)
    buckets = []
    year, month = start.year, start.month
    while (year, month) <= (today.year, today.month):
        value = counts.get(f"{year}-{month:02d}", 0)
        buckets.append({"label": f"{month_name(month, True)} {year % 100:02d}", "value": value,
                        "tooltip": f"{month_name(month)} {year}\n{plays_text(value)}"})
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return {"title": t("stats.per_month"), "buckets": buckets}


def journey(key: str, info: dict) -> dict:
    """The track's place among all tracks and its plays so far at the end of each day (or month, as the timeline),
    from its first play: where it started and stands, its best place and the day it first reached the top ten."""
    first = listening.from_utc(info["first_played"]).astimezone()
    today = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    start = first.replace(hour=0, minute=0, second=0, microsecond=0)
    end = today + timedelta(days=1)
    daily = (end - start).days <= DAILY_LIMIT
    if daily:
        starts = [start + timedelta(days=i) for i in range((end - start).days)]
        nexts = starts[1:] + [end]
    else:
        starts, year, month = [], start.year, start.month
        while (year, month) <= (today.year, today.month):
            starts.append(start.replace(year=year, month=month, day=1))
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        nexts = starts[1:] + [end]
    places = listening.rank_history(key, nexts)
    when = (lambda day: f"{day.day} {month_name(day.month)}") if daily else \
        (lambda day: f"{month_name(day.month)} {day.year}")
    points = [{"label": str(day.day) if daily else f"{month_name(day.month, True)} {day.year % 100:02d}",
               "rank": place[0] if place else None, "plays": place[2] if place else 0,
               "tooltip": f"{when(day)}\n{t('detail.journey.rank', rank=number(place[0]))}  ·  {plays_text(place[2])}"
                          if place else when(day)}
              for day, place in zip(starts, places)]
    ranked = [(i, place) for i, place in enumerate(places) if place]
    if not ranked:
        return {"title": t("detail.journey"), "points": points, "band": "", "plays_text": "", "summary": "",
                "best": None, "best_text": "",
                "top": None, "top_text": ""}
    began, now, plays = ranked[0][1][0], ranked[-1][1][0], ranked[-1][1][2]
    best = min(ranked, key=lambda item: (item[1][0], -item[0]))[0]
    top = next((i for i, place in ranked if place[0] <= TOP_PLACES), None)
    # Marked only when it is a day of its own, not the start or the best one it would cover
    if top in (best, ranked[0][0]):
        top = None
    summary = "detail.journey.up" if now < began else "detail.journey.down" if now > began else "detail.journey.same"
    return {
        "title": t("detail.journey"), "points": points, "band": t("detail.journey.band", places=TOP_PLACES),
        "plays_text": plays_text(plays),
        "summary": t(summary, start=number(began), now=number(now), plays=plays_text(plays)),
        "best": best, "best_text": t("detail.journey.best", rank=number(places[best][0])),
        "top": top,
        "top_text": t("detail.journey.top", when=when(starts[top])) if top is not None else "",
    }


def with_peak(timeline: dict) -> dict:
    """The timeline with its most played day or month (the latest of equal ones) for the artist's curve."""
    buckets = timeline["buckets"]
    peak = max(range(len(buckets)), key=lambda i: (buckets[i]["value"], i))
    if not buckets[peak]["value"]:
        return {**timeline, "peak": None, "peak_text": ""}
    when = buckets[peak]["tooltip"].split("\n")[0]
    daily = timeline["title"] == t("stats.per_day")
    return {**timeline, "peak": peak, "peak_text": t("detail.timeline.peak_day" if daily else "detail.timeline.peak", when=when)}


def trend(column: str, key: str) -> dict | None:
    """Plays of the last TREND_DAYS days against the same number of days before them: up, down or same, with the
    change in percent when there were plays before. None when neither had any."""
    today = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    end = today + timedelta(days=1)
    middle = end - timedelta(days=TREND_DAYS)
    recent = sum(listening.timeline(middle, end, "month", column, key).values())
    before = sum(listening.timeline(middle - timedelta(days=TREND_DAYS), middle, "month", column, key).values())
    if not recent and not before:
        return None
    # Before the recording began there is nothing to compare with
    start, _ = listening.period_range("all")
    began = min(listening.timeline(start, end, "day"), default=None)
    if not began or date.fromisoformat(began) > (middle - timedelta(days=TREND_DAYS)).date():
        return {"direction": "", "change": "", "against": "",
                "recent": t("detail.trend.recent", days=TREND_DAYS, plays=plays_text(recent))}
    direction = "up" if recent > before else "down" if recent < before else "same"
    if not before:
        change, against = "", t("detail.trend.none_before", days=TREND_DAYS)
    elif direction == "same":
        change, against = "", t("detail.trend.same", days=TREND_DAYS)
    else:
        change = t("stats.percent", value=number(round(abs(recent - before) * 100 / before)))
        against = t("detail.trend.against", days=TREND_DAYS)
    return {"direction": direction, "change": change, "against": against,
            "recent": t("detail.trend.recent", days=TREND_DAYS, plays=plays_text(recent))}


def day_part(hours: list[int]) -> str | None:
    """The part of the day with the most plays: night (0-6), morning, afternoon or evening (18-24); None when no
    part has a clear lead, so the page does not say "mostly" of an even spread."""
    parts = [sum(hours[start:start + 6]) for start in range(0, 24, 6)]
    total = sum(parts)
    best = max(range(4), key=lambda part: parts[part])
    return DAY_PARTS[best] if total and parts[best] / total >= DAY_PART_LEAD else None


def day_curve(hours: list[int]) -> dict:
    """The most played hour and the part of the day, for the curve of the track's hours."""
    if not any(hours):
        return {"peak": None, "peak_text": "", "summary": ""}
    peak = max(range(24), key=lambda hour: hours[hour])
    part = day_part(hours)
    return {"peak": peak, "peak_text": t("detail.hours.peak", hour=f"{peak:02d}:00"),
            "summary": t(f"detail.hours.{part}") if part else t("detail.hours.spread")}


def longest_run(days: list[date]) -> int:
    """The most days in a row among the days."""
    longest = run = 0
    last = None
    for day in sorted(days):
        run = run + 1 if last is not None and day == last + timedelta(days=1) else 1
        last = day
        longest = max(longest, run)
    return longest


def highlights(key: str) -> list[dict]:
    """A track's place among all the tracks, the day it was played most (the latest of equal ones) and its most
    days in a row."""
    start, end = listening.period_range("all")
    ranked = [r["key"] for r in listening.top_tracks(start, end, ALL_TRACKS)]
    per_day = {date.fromisoformat(day): count
               for day, count in listening.timeline(start, end, "day", "track_key", key).items()}
    best = max(per_day, key=lambda day: (per_day[day], day))
    run = longest_run(list(per_day))
    return [
        {"icon": "star", "label": t("detail.highlights.rank"),
         "value": t("detail.highlights.rank_value", rank=number(ranked.index(key) + 1), total=number(len(ranked)))},
        {"icon": "calendar", "label": t("detail.highlights.best_day"),
         "value": f"{best.day} {month_name(best.month)} {best.year}  ·  {plays_text(per_day[best])}"},
        {"icon": "flag", "label": t("detail.highlights.run"),
         "value": t("detail.highlights.day_one" if run == 1 else "detail.highlights.days", days=number(run))},
    ]


def weekdays(column: str, key: str) -> dict:
    """Plays per day of the week from Monday, with the day it is played most on."""
    start, end = listening.period_range("all")
    counts = [0] * 7
    for day, count in listening.timeline(start, end, "day", column, key).items():
        counts[date.fromisoformat(day).weekday()] += count
    short, full = t("stats.weekdays").split(","), t("detail.weekdays_full").split(",")
    peak = max(range(7), key=lambda day: counts[day])
    return {"title": t("detail.weekdays"), "summary": t("detail.weekdays.peak", day=full[peak]), "peak": peak,
            "buckets": [{"label": short[day], "value": counts[day],
                         "tooltip": f"{full[day]}\n{plays_text(counts[day])}"} for day in range(7)]}


def tile(name: str, value, text: str, kind: str = "number") -> dict:
    """kind: "number" and "duration" count up in the window, "text" (dates, names) is shown as it is."""
    return {"name": name, "label": t(f"detail.tile.{name}"), "value": value, "text": text, "kind": kind}


def alike(kind: str, title: str, info: dict) -> dict | None:
    """What the suggestion models find most alike to a track or an artist, the played ones opening their page and
    the others their Spotify search, or None when the model does not know it."""
    if kind == "track":
        songs = recommend.alike_songs(info["artist"], info["name"])
        rows = [{"title": s["title"], "subtitle": s["artist"], "image": cover_url(s["artist"], "", s["title"]),
                 "fallback": artist_url(s["artist"]), "column": "track_key", "key": s["track_key"],
                 "artist": s["artist"], "song": s["title"]} for s in songs]
        played = t("detail.alike.played_song")
    elif kind == "artist":
        artists = recommend.alike_artists(title)
        rows = [{"title": a["name"], "subtitle": "", "image": artist_url(a["name"]), "fallback": "",
                 "column": "artist_key", "key": a["artist_key"], "artist": a["name"], "song": ""} for a in artists]
        played = t("detail.alike.played_artist")
    else:
        return None
    if not rows:
        return None
    return {"kind": kind, "title": t(f"detail.alike.{kind}"), "summary": t(f"detail.alike.{kind}_summary", name=title),
            "played": played, "rows": rows}


def detail(column: str, key: str, arrived: Callable[[], None]) -> dict | None:
    """The page's data, or None when nothing of it was played. arrived() is called when facts or a track
    list looked up in the background were found, so the window can ask again."""
    if column not in COLUMNS:
        raise ValueError(column)
    # A collaboration's name, as a track links it, opens its first artist's page
    if column == "artist_key":
        key = listening.main_artist_key(key)
    info = listening.detail(column, key)
    if not info:
        return None
    kind = "artist" if column == "artist_key" else "album" if column == listening.ALBUM else "track"
    # An artist heard in collaborations is named alone, not after one of them
    title = (listening.artist_name(key) or info["artist"]) if kind == "artist" else         info["album"] if kind == "album" else info["name"]
    summary = summary_text(plays_text(info["plays"]), minutes=info["minutes"])
    hero = {"caption": t(f"detail.{kind}"), "title": title, "detail": summary, "about": "",
            "subtitle": info["artist"],
            # Each artist of a collaboration opens their own page
            "artists": listening.artist_links(info["artist"]),
            "image": cover_url(info["artist"], info["album"], info["name"])}
    if kind == "artist":
        facts = artist_info.request(title, key, arrived)
        hero.update(subtitle=tracks_text(info["tracks"]), artists=[], image=artist_url(title),
                    about=artist_info.describe(facts) if facts else "")
    page = {"kind": kind, "column": column, "key": key, "title": title, "hero": hero,
            "timeline": timeline(column, key, info)}
    tiles = [tile("plays", info["plays"], number(info["plays"])),
             tile("time", info["minutes"], duration_text(info["minutes"]) if info["minutes"] else "—", "duration")]

    if kind == "album":
        rows, tracks = album_rows(info["artist"], info["album"], key, arrived)
        heard = sum(1 for row in rows if row["value"])
        favorite = max(rows, key=lambda row: row["value"]) if rows else None
        tiles += [tile("heard", heard, f"{number(heard)} / {number(len(rows))}" if tracks else number(heard), "text"),
                  tile("favorite", 0, favorite["title"] if favorite and favorite["value"] else "—", "text")]
        if tracks:
            length = sum(track["ms"] for track in tracks) // 60000
            hero["about"] = t("detail.album_length", tracks=number(len(tracks)), length=duration_text(length))
        share = heard / len(rows) if tracks and rows else 1.0
        page["progress"] = {
            "share": share,
            "text": t("detail.album_progress", percent=t("stats.percent", value=round(share * 100)))
                    if tracks else t("detail.album_progress_unknown"),
        }
        # The album as a record of its tracks in album order, each slice as long as it was played
        best = rows.index(favorite) if favorite and favorite["value"] else None
        page["vinyl"] = {
            "title": t("detail.vinyl"),
            "summary": t("detail.vinyl.summary", number=number(best + 1), title=favorite["title"]) if best is not None
                       else "",
            "center": f"{number(heard)}/{number(len(rows))}" if tracks else number(heard),
            "caption": t("detail.vinyl.caption"),
        }
        page["tracks"] = {"title": t("detail.album_tracks", heard=number(heard), total=number(len(rows)))
                          if tracks else t("detail.artist_tracks"), "rows": rows, "pictures": False}
    else:
        tiles += [tile("first", 0, date_text(info["first_played"]), "text"),
                  tile("last", 0, date_text(info["last_played"]), "text")]

    if kind == "artist":
        page["timeline"] = with_peak(page["timeline"])
        page["trend"] = trend(column, key)
        start, end = listening.period_range("all")
        page["tracks"] = {"title": t("detail.artist_tracks"), "pictures": True, "rows": [{
            **track_row(r, r["album"] or ""), "image": cover_url(r["artist"], r["album"], r["name"]),
        } for r in listening.top_tracks(start, end, ARTIST_TRACKS, artist_key=key)]}
        page["albums"] = {"title": t("detail.artist_albums"), "rows": [{
            "key": listening.album_key(r["artist_key"], r["album_lower"]), "column": listening.ALBUM,
            "title": r["album"], "subtitle": "", "value": r["plays"], "value_text": number(r["plays"]),
            "detail": plays_text(r["plays"]), "image": cover_url(r["artist"], r["album"], r["name"]),
        } for r in listening.top_albums(start, end, ARTIST_ALBUMS, artist_key=key)]}

    if kind == "track":
        start, end = listening.period_range("all")
        hours = listening.hours(start, end, column, key)
        page["hours"] = {"title": t("detail.track_hours"), "buckets": hour_buckets(hours), **day_curve(hours)}
        page["highlights"] = {"title": t("detail.highlights"), "items": highlights(key)}
        page["weekdays"] = weekdays(column, key)
        page["journey"] = journey(key, info)
        page["album"] = None
        if info["album"]:
            album_key = listening.album_key(info["artist_key"], info["album_lower"])
            rows, tracks = album_rows(info["artist"], info["album"], album_key, arrived)
            heard = sum(1 for row in rows if row["value"])
            page["album"] = {
                "caption": t("detail.album"), "key": album_key, "title": info["album"], "image": hero["image"],
                "heard": t("detail.album_heard", heard=number(heard), total=number(len(rows))) if tracks
                         else t("detail.album_heard_unknown", heard=number(heard)),
                "open": t("detail.album_open"),
            }
    page["alike"] = alike(kind, title, info)
    page["tiles"] = tiles
    # The page takes the color of its picture, as the statistics take their number one's
    picture = artwork.fetch_artist(title) if kind == "artist" else         artwork.fetch_cover(info["artist"], info["album"], info["name"])
    page["mood"] = artwork.mood(picture)
    page["palette"] = artwork.palette(picture)
    return page
