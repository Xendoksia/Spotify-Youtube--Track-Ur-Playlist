"""
The monthly and yearly summary as data for the desktop window: its slides, the bell's box of summaries not seen
yet, and when one opens by itself. When a summary is there and who saw it follow the rules of
music/wrapped.py, which the phone follows too.

A slide is a caption and parts shown one after another: big (a number counting up), heading, text, image, list,
columns, genre and tiles.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from playlist_tracker.api.overview import artist_url, cover_url, period_mood
from playlist_tracker.core.i18n import number, t
from playlist_tracker.music import artist_info, artwork, listening
from playlist_tracker.music import wrapped
from playlist_tracker.music.text import duration_text, month_name, period_title, plays_text

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
    without marking it (the window's --summary)."""
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


# A genre's family by words in its name, for its sigil and its word to the listener, as the phone's genreFamily
# (mobile/lib/screens/listening/wrapped_visuals.dart)
GENRE_FAMILIES = [
    (("turkish", "türk", "anatolian", "arabesk"), "turkish"),
    (("metal", "core", "djent", "grind"), "metal"),
    (("hip hop", "hip-hop", "rap", "trap", "drill"), "hiphop"),
    (("rock", "grunge", "punk", "emo", "alternative", "indie"), "rock"),
    (("electro", "house", "techno", "edm", "trance", "dubstep", "synth", "dance", "drum and bass"), "electronic"),
    (("pop",), "pop"),
    (("jazz", "blues", "soul", "funk", "r&b"), "jazz"),
    (("classical", "soundtrack", "ambient", "lo-fi", "lofi", "piano", "score"), "calm"),
    (("folk", "country", "acoustic", "singer-songwriter"), "folk"),
    (("latin", "reggaeton", "salsa", "bachata"), "latin"),
]

# Pairs of genres, and of families, with a word of their own
GENRE_PAIRS = {
    ("metalcore", "nu metal"): "metalcore_numetal",
    ("metalcore", "post-hardcore"): "metalcore_posthardcore",
    ("alternative rock", "nu metal"): "numetal_altrock",
    ("alternative rock", "post-grunge"): "altrock_postgrunge",
    ("hard rock", "heavy metal"): "hardrock_heavymetal",
    ("hip hop", "trap"): "hiphop_trap",
}
FAMILY_PAIRS = {
    ("metal", "rock"), ("electronic", "metal"), ("metal", "pop"), ("hiphop", "metal"), ("pop", "rock"),
    ("electronic", "rock"), ("hiphop", "rock"), ("folk", "rock"), ("electronic", "pop"), ("hiphop", "pop"),
    ("electronic", "hiphop"), ("hiphop", "jazz"), ("rock", "turkish"), ("pop", "turkish"), ("metal", "metal"),
    ("rock", "rock"),
}


def genre_family(genre: str) -> str:
    name = genre.lower()
    for words, family in GENRE_FAMILIES:
        if any(word in name for word in words):
            return family
    return "other"


def genre_message(first: str, second: str | None) -> str:
    """The text key of the word to the listener of the two biggest genres: one for the pair when there is, else
    for the first genre's family (as the phone's genreMessage)."""
    if second is not None:
        names = tuple(sorted((first.lower(), second.lower())))
        if names in GENRE_PAIRS:
            return f"wrapped.genre.combo.{GENRE_PAIRS[names]}"
        families = tuple(sorted((genre_family(first), genre_family(second))))
        if families in FAMILY_PAIRS:
            return f"wrapped.genre.combo.{'_'.join(families)}"
    return f"wrapped.genre.say.{genre_family(first)}"


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
    # The most played artists of each genre, for their photos
    genre_artists: dict[str, list[dict]] = {}
    for artist in artists_all:
        facts = artist_info.cached(artist["key"])
        if facts and facts["genres"]:
            genre = facts["genres"][0]
            genre_plays[genre] = genre_plays.get(genre, 0) + artist["plays"]
            their = genre_artists.setdefault(genre, [])
            if len(their) < 4:
                their.append(artist)
    genres = sorted(((name, plays * 100 / total) for name, plays in genre_plays.items()),
                    key=lambda item: -item[1])[:3] if total else []
    days = listening.timeline(start, end, "day")
    title = period_title("year" if year else "month", start, end)

    def text(value: str, muted: bool = True, gap: bool = False) -> dict:
        return {"type": "text", "text": value, "muted": muted, "gap": gap}

    # Each slide with a song plays one the slides before did not
    played: set[tuple[str, str]] = set()

    def song_of(rows: list[dict]) -> dict | None:
        for row in rows:
            if (row["artist"], row["name"]) not in played:
                played.add((row["artist"], row["name"]))
                return {"artist": row["artist"], "title": row["name"]}
        return None

    def song_by(artist: dict) -> dict | None:
        return song_of(listening.top_tracks(start, end, 10, artist_key=artist["key"]))

    slides = []
    # Intro, over a wall of the month's covers (one per album)
    caption = (t("wrapped.intro.caption.year", year=start.year) if year
               else t("wrapped.intro.caption", month=month_name(start.month)))
    seen_covers: set[str] = set()
    wall = []
    for row in listening.top_tracks(start, end, 60):
        cover = f"{row['artist']}|{row['album'] or row['name']}"
        if cover not in seen_covers and len(wall) < 21:
            seen_covers.add(cover)
            wall.append(cover_url(row["artist"], row["album"], row["name"]))
    parts = []
    if totals["minutes"]:
        parts += [{"type": "big", "value": totals["minutes"], "kind": "minutes"},
                  text(t("wrapped.intro.listened"), muted=False)]
        if totals["minutes"] >= 120:
            parts.append({"type": "chip", "icon": "clock",
                          "text": t("wrapped.hours", hours=number(totals["minutes"] // 60))})
    else:
        parts.append({"type": "big", "value": totals["plays"], "kind": "plays"})
    # How the period compares with the one before, by time listened (by plays when lengths are missing)
    before_start = start.replace(year=start.year - 1) if year else (start - timedelta(days=1)).replace(day=1)
    previous = listening.summary(before_start, start)
    now_value, before_value = ((totals["minutes"], previous["minutes"]) if totals["minutes"] and previous["minutes"]
                               else (totals["plays"], previous["plays"]))
    if before_value:
        change = round((now_value - before_value) * 100 / before_value)
        if change:
            key = ("wrapped.change.up" if change > 0 else "wrapped.change.down") + (".year" if year else "")
            name = str(before_start.year) if year else month_name(before_start.month)
            parts.append({"type": "chip", "icon": "up" if change > 0 else "down",
                          "text": t(key, value=number(abs(change)), previous=name)})
    parts.append(text(t("wrapped.intro.detail", plays=plays_text(totals["plays"]), tracks=number(totals["tracks"]),
                        artists=number(totals["artists"])), gap=True))
    slides.append({"caption": caption, "parts": parts, "wall": wall})

    if tracks:
        track = tracks[0]
        parts = [
            {"type": "record", "src": cover_url(track["artist"], track["album"], track["name"])},
            {"type": "heading", "text": track["name"]},
            text(track["artist"]),
            {"type": "big", "value": track["plays"], "kind": "times"},
        ]
        if track["minutes"]:
            parts.append({"type": "chip", "icon": "music",
                          "text": t("wrapped.track.time", time=duration_text(track["minutes"]))})
        slides.append({"caption": t(of_period("wrapped.track.caption")), "parts": parts,
                       "open": {"column": "track_key", "key": track["key"]},
                       # Its 30 second preview plays while the slide shows
                       "song": song_of([track]),
                       "mood": artwork.mood(artwork.fetch_cover(track["artist"], track["album"], track["name"]))})
    if artists:
        artist = artists[0]
        detail = plays_text(artist["plays"])
        if artist["minutes"]:
            detail += f"  ·  {duration_text(artist['minutes'])}"
        share = artist["plays"] / totals["plays"] if totals["plays"] else 0
        parts = [{"type": "ring", "src": artist_url(artist["name"]), "share": share},
                 {"type": "heading", "text": artist["name"]}, text(detail, muted=False),
                 {"type": "chip", "icon": "artists", "text": t("wrapped.artist.share", value=number(round(share * 100)))}]
        facts = artist_info.cached(artist["key"])
        if facts:
            parts.append(text(artist_info.describe(facts), gap=True))
        # The artist's song played most in the period plays while the slide shows
        song = song_by(artist)
        slides.append({"caption": t(of_period("wrapped.artist.caption")), "parts": parts,
                       "open": {"column": "artist_key", "key": artist["key"]},
                       "song": song,
                       "mood": artwork.mood(artwork.fetch_artist(artist["name"]))})
    if len(tracks) > 1:
        # The highest song not played on a slide before
        slides.append({"caption": t("wrapped.tracks.caption"), "song": song_of(tracks),
                       "parts": [{"type": "podium", "round": False, "rows": [{
            "key": r["key"], "column": "track_key", "title": r["name"], "subtitle": r["artist"],
            "value_text": plays_text(r["plays"]), "image": cover_url(r["artist"], r["album"], r["name"]),
        } for r in tracks]}]})
    if len(artists) > 1:
        # The second artist's song played most, the first artist having its own slide
        slides.append({"caption": t("wrapped.artists.caption"),
                       "song": next(filter(None, (song_by(a) for a in artists[1:])), None),
                       "parts": [{"type": "podium", "round": True, "rows": [{
            "key": r["key"], "column": "artist_key", "title": r["name"], "subtitle": "",
            "value_text": plays_text(r["plays"]), "image": artist_url(r["name"]),
        } for r in artists]}]})
    if new_tracks:
        parts = []
        if new_artists:
            parts.append({"type": "bubbles", "items": [
                {"src": artist_url(a["name"]), "title": a["name"], "column": "artist_key", "key": a["key"]}
                for a in new_artists[:8]]})
        parts += [{"type": "big", "value": len(new_tracks), "kind": "new_tracks"},
                  text(t("wrapped.new_artists", count=number(len(new_artists))), muted=False)]
        if new_artists:
            parts.append({"type": "chip", "icon": "star",
                          "text": t("wrapped.top_new_artist", name=new_artists[0]["name"])})
        if first_month:
            parts.append(text(t("stats.discoveries.first_period"), gap=True))
        slides.append({"caption": t("wrapped.discoveries.caption"), "parts": parts})
    if totals["plays"]:
        day, plays = max(days.items(), key=lambda item: item[1])
        date = datetime.strptime(day, "%Y-%m-%d")
        weekdays = t("stats.weekdays").split(",")
        hours = listening.hours(start, end)
        peak = max(range(24), key=lambda hour: hours[hour])
        length = (min(end, datetime.now().astimezone()) - start).days + 1
        if year:
            months = listening.timeline(start, end, "month")
            calendar = {"type": "calendar", "columns": 6, "blank": 0, "headers": [],
                        "counts": [months.get(f"{start.year}-{m:02d}", 0) for m in range(1, 13)]}
        else:
            last = ((end - timedelta(days=1)).day)
            calendar = {"type": "calendar", "columns": 7, "blank": start.weekday(),
                        "headers": [name[:1] for name in weekdays],
                        "counts": [days.get(f"{start.year}-{start.month:02d}-{d:02d}", 0) for d in range(1, last + 1)]}
        busiest_day = f"{date.day} {month_name(date.month)}" if year else \
            f"{date.day} {month_name(date.month)}, {weekdays[date.weekday()]}"
        slides.append({"caption": t("wrapped.rhythm.caption"), "parts": [
            {"type": "clock", "hours": hours, "peak": f"{peak:02d}:00", "label": t("wrapped.peak_hour.short")},
            calendar,
            text(t("wrapped.busiest", day=busiest_day, plays=plays_text(plays)), muted=False, gap=True),
            text(t("wrapped.days_listened", active=number(len(days)), days=number(max(length, len(days))))),
        ]})
    if genres:
        name, share = genres[0]
        slides.append({"caption": t("wrapped.genres.caption"), "parts": [{
            "type": "spotlight", "name": capitalized(name), "family": genre_family(name),
            "share": t("wrapped.genre.share", value=t("stats.percent", value=round(share))),
            "message": t(genre_message(name, genres[1][0] if len(genres) > 1 else None)),
            "photos": [{"src": artist_url(a["name"]), "title": a["name"], "column": "artist_key", "key": a["key"]}
                       for a in genre_artists.get(name, [])],
            "others": [{"family": genre_family(other), "name": capitalized(other), "value": round(value),
                        "text": t("stats.percent", value=round(value))} for other, value in genres[1:]],
        }]})
    if totals["plays"]:
        # The month on one card, as the phone's closing poster: it carries its own title, so no caption above
        slides.append({"caption": "", "parts": [{
            "type": "poster", "month": title, "caption": t(of_period("wrapped.poster.caption")),
            "artists_caption": t("wrapped.artists.caption"), "tracks_caption": t("wrapped.tracks.caption"),
            "artists": [{"name": r["name"], "key": r["key"], "image": artist_url(r["name"])} for r in artists],
            "tracks": [{"name": r["name"], "key": r["key"]} for r in tracks],
            "minutes_caption": t("wrapped.poster.minutes"), "minutes": totals["minutes"],
            "genre_caption": t(of_period("wrapped.genre")),
            "genre": capitalized(genres[0][0]) if genres else None,
            "line": "  \u00b7  ".join([plays_text(totals["plays"]),
                                       t("wrapped.poster.tracks", count=number(totals["tracks"])),
                                       t("wrapped.poster.artists", count=number(totals["artists"]))]),
        }]})
    # The stage takes each slide's color from its picture, and the others turn on from the month's
    return {"id": value, "title": t("wrapped.title", month=title), "slides": slides,
            "mood": period_mood(tracks[:1], artists[:1])}
