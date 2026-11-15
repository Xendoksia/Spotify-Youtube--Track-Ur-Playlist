"""
The monthly and yearly summary as data for the desktop window: its slides, the bell's box of summaries not seen
yet, and when one opens by itself. When a summary is there and who saw it follow the Tk window's rules
(ui/stats/wrapped.py), so the two windows and the phone agree.

A slide is a caption and parts shown one after another: big (a number counting up), heading, text, image, list,
columns, genre and tiles.
"""

from __future__ import annotations

from datetime import datetime

from playlist_tracker.api.overview import artist_url, cover_url
from playlist_tracker.core.i18n import number, t
from playlist_tracker.music import artist_info, listening
from playlist_tracker.ui.stats import wrapped
from playlist_tracker.ui.stats.text import duration_text, month_name, period_title, plays_text

TOP = wrapped.TOP


def summary_id(summary: tuple[datetime, datetime]) -> str:
    """"2026" for a year, "2026-10" for a month (as the settings write them)."""
    start = summary[0]
    return str(start.year) if wrapped.is_year(*summary) else start.strftime("%Y-%m")


def from_id(value: str) -> tuple[datetime, datetime]:
    if len(value) == 4:
        start = datetime(int(value), 1, 1).astimezone()
        return start, start.replace(year=start.year + 1)
    year, month = int(value[:4]), int(value[5:7])
    start = datetime(year, month, 1).astimezone()
    return start, start.replace(year=year + month // 12, month=month % 12 + 1)


def inbox() -> dict:
    """The summaries waiting behind the bell."""
    items = []
    for summary in wrapped.inbox():
        year = wrapped.is_year(*summary)
        items.append({"id": summary_id(summary),
                      "title": t("wrapped.inbox.item", name=period_title("year" if year else "month", *summary)),
                      "detail": t("wrapped.inbox.detail.year" if year else "wrapped.inbox.detail")})
    return {"items": items}


def due(force: bool = False) -> dict:
    """The summary to open by itself now, once (marked seen); force gives the last month with plays on any day,
    without marking it (app.py --summary)."""
    if force:
        return {"id": summary_id(wrapped.month_to_show())}
    summary = wrapped.auto_open_due()
    if summary is None:
        return {"id": None}
    wrapped.mark_shown(summary)
    return {"id": summary_id(summary)}


def notices() -> list[str]:
    """The "summary ready" notifications to give now, each once."""
    messages = []
    while summary := wrapped.notice_due():
        wrapped.mark_notified(summary)
        messages.append(t("wrapped.year.notice", year=summary[0].year) if wrapped.is_year(*summary)
                        else t("wrapped.notice", month=month_name(summary[0].month)))
    return messages


def capitalized(name: str) -> str:
    return name[:1].upper() + name[1:]


def summary(value: str) -> dict:
    """The slides of one summary; opening it takes it out of the box."""
    start, end = from_id(value)
    wrapped.seen((start, end))
    year = wrapped.is_year(start, end)

    def of_period(key: str) -> str:
        # "Song of the year" for "Song of the month"
        return f"{key}.year" if year else key

    totals = listening.summary(start, end)
    artists_all = listening.top_artists(start, end, -1)
    tracks = listening.top_tracks(start, end, TOP)
    artists = artists_all[:TOP]
    new_tracks = listening.new_tracks(start, end)
    new_artists = listening.new_artists(start, end)
    first = listening.first_play()
    # Everything counts as new in the month recording began
    first_month = first is not None and first >= start
    total = sum(a["plays"] for a in artists_all)
    genre_plays: dict[str, int] = {}
    for artist in artists_all:
        facts = artist_info.cached(artist["key"])
        if facts and facts["genres"]:
            genre_plays[facts["genres"][0]] = genre_plays.get(facts["genres"][0], 0) + artist["plays"]
    genres = sorted(((name, plays * 100 / total) for name, plays in genre_plays.items()),
                    key=lambda item: -item[1])[:3] if total else []
    days = listening.timeline(start, end, "day")
    title = period_title("year" if year else "month", start, end)

    def text(value: str, muted: bool = True, gap: bool = False) -> dict:
        return {"type": "text", "text": value, "muted": muted, "gap": gap}

    slides = []
    # Intro
    caption = (t("wrapped.intro.caption.year", year=start.year) if year
               else t("wrapped.intro.caption", month=month_name(start.month)))
    parts = []
    if totals["minutes"]:
        parts += [{"type": "big", "value": totals["minutes"], "kind": "minutes"},
                  text(t("wrapped.intro.listened"), muted=False)]
    else:
        parts.append({"type": "big", "value": totals["plays"], "kind": "plays"})
    parts.append(text(t("wrapped.intro.detail", plays=plays_text(totals["plays"]), tracks=number(totals["tracks"]),
                        artists=number(totals["artists"])), gap=True))
    slides.append({"caption": caption, "parts": parts})

    if tracks:
        track = tracks[0]
        slides.append({"caption": t(of_period("wrapped.track.caption")), "parts": [
            {"type": "image", "src": cover_url(track["artist"], track["album"], track["name"]), "round": False},
            {"type": "heading", "text": track["name"]},
            text(track["artist"]),
            text(t("wrapped.times", count=number(track["plays"])), muted=False, gap=True),
        ], "open": {"column": "track_key", "key": track["key"]}})
    if artists:
        artist = artists[0]
        detail = plays_text(artist["plays"])
        if artist["minutes"]:
            detail += f"  ·  {duration_text(artist['minutes'])}"
        parts = [{"type": "image", "src": artist_url(artist["name"]), "round": True},
                 {"type": "heading", "text": artist["name"]}, text(detail, muted=False)]
        facts = artist_info.cached(artist["key"])
        if facts:
            parts.append(text(artist_info.describe(facts), gap=True))
        slides.append({"caption": t(of_period("wrapped.artist.caption")), "parts": parts,
                       "open": {"column": "artist_key", "key": artist["key"]}})
    if len(tracks) > 1:
        slides.append({"caption": t("wrapped.tracks.caption"), "parts": [{"type": "list", "round": False, "rows": [{
            "key": r["key"], "column": "track_key", "title": r["name"], "subtitle": r["artist"], "value": r["plays"],
            "value_text": number(r["plays"]), "detail": plays_text(r["plays"]),
            "image": cover_url(r["artist"], r["album"], r["name"]),
        } for r in tracks]}]})
    if len(artists) > 1:
        slides.append({"caption": t("wrapped.artists.caption"), "parts": [{"type": "list", "round": True, "rows": [{
            "key": r["key"], "column": "artist_key", "title": r["name"], "subtitle": "", "value": r["plays"],
            "value_text": number(r["plays"]), "detail": plays_text(r["plays"]), "image": artist_url(r["name"]),
        } for r in artists]}]})
    if new_tracks:
        parts = [{"type": "big", "value": len(new_tracks), "kind": "new_tracks"},
                 text(t("wrapped.new_artists", count=number(len(new_artists))), muted=False)]
        if new_artists:
            parts.append(text(t("wrapped.top_new_artist", name=new_artists[0]["name"]), gap=True))
        if first_month:
            parts.append(text(t("stats.discoveries.first_period"), gap=True))
        slides.append({"caption": t("wrapped.discoveries.caption"), "parts": parts})
    if totals["plays"]:
        day, plays = max(days.items(), key=lambda item: item[1])
        date = datetime.strptime(day, "%Y-%m-%d")
        weekday = t("stats.weekdays").split(",")[date.weekday()]
        hours = listening.hours(start, end)
        peak = max(range(24), key=lambda hour: hours[hour])
        length = (min(end, datetime.now().astimezone()) - start).days + 1
        slides.append({"caption": t("wrapped.rhythm.caption"), "parts": [
            text(t("wrapped.busiest", day=f"{date.day} {month_name(date.month)}, {weekday}", plays=plays_text(plays)),
                 muted=False),
            {"type": "heading", "text": f"{peak:02d}:00 – {(peak + 1) % 24:02d}:00"},
            text(t("wrapped.peak_hour")),
            {"type": "columns", "buckets": [{"label": f"{hour:02d}", "value": count,
                                             "tooltip": f"{hour:02d}:00\n{plays_text(count)}"}
                                            for hour, count in enumerate(hours)]},
            text(t("wrapped.days_listened", active=number(len(days)), days=number(max(length, len(days)))), gap=True),
        ]})
    if genres:
        slides.append({"caption": t("wrapped.genres.caption"), "parts": [
            {"type": "genre", "name": capitalized(name), "value": round(share), "first": index == 0}
            for index, (name, share) in enumerate(genres)]})
    if totals["plays"]:
        tiles = [(t("stats.tile.time"), duration_text(totals["minutes"]) if totals["minutes"] else "—"),
                 (t("stats.tile.plays"), number(totals["plays"])),
                 (t("stats.tile.tracks"), number(totals["tracks"])),
                 (t("stats.tile.artists"), number(totals["artists"]))]
        if tracks:
            tiles.append((t(of_period("wrapped.track.caption")), tracks[0]["name"]))
        if artists:
            tiles.append((t(of_period("wrapped.artist.caption")), artists[0]["name"]))
        if genres:
            tiles.append((t(of_period("wrapped.genre")), capitalized(genres[0][0])))
        if new_artists and not first_month:
            tiles.append((t("stats.new_artists"), number(len(new_artists))))
        slides.append({"caption": t("wrapped.closing.caption", month=title), "parts": [
            {"type": "tiles", "tiles": [{"caption": caption, "value": value} for caption, value in tiles]}]})
    return {"id": value, "title": t("wrapped.title", month=title), "slides": slides}
