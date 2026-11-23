"""
The overview's cards below the charts as data for the desktop window: discoveries (or, over all time, the
forgotten tracks), diversity, milestones, genres, genres over time and the album collage. The same counts
and texts as the earlier window's cards.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from playlist_tracker.api.overview import artist_url, cover_url
from playlist_tracker.core.i18n import number, t
from playlist_tracker.core.text import format_date
from playlist_tracker.music import artist_info, artwork, collage, listening
from playlist_tracker.music.listening import key, name_variants
from playlist_tracker.music.text import month_name, plays_text, summary_text, tracks_text

DISCOVERY_COUNT = 5
FORGOTTEN_COUNT = 10
FORGOTTEN_DAYS = 30
FORGOTTEN_MIN_PLAYS = 3
GENRE_COUNT = 8
GENRE_SHIFT_COUNT = 4
GENRE_SHIFT_MAX_MONTHS = 36
DIVERSITY_TOP = 5
# Points of difference in the new tracks' share that count as more or less discovery
DIVERSITY_CHANGE = 5
FOCUSED, WIDE = 70, 40
MILESTONES_SHOWN = 8
YEAR_AGO_SHOWN = 3
# More rows than any month has, to see where a track or artist stands
ALL_ROWS = 1_000_000


def period_bounds(period: str, offset: int) -> tuple[str, int, datetime, datetime]:
    if period not in listening.PERIODS:
        raise ValueError(period)
    offset = 0 if period == "all" else max(0, offset)
    start, end = listening.period_range(period, offset)
    if period == "all":
        start = listening.first_play() or start
    return period, offset, start, end


def share(part: int, whole: int) -> int:
    return round(100 * part / whole) if whole else 0


def percent(value: int) -> str:
    return t("stats.percent", value=value)


def capitalized(name: str) -> str:
    return name[:1].upper() + name[1:]


def sections(period: str, offset: int) -> dict:
    period, offset, start, end = period_bounds(period, offset)
    return {
        "discoveries": None if period == "all" else discoveries(start, end),
        "forgotten": forgotten() if period == "all" else None,
        "diversity": diversity(period, offset, start, end),
        "streak": streak_card(),
        "year_ago": year_ago(),
        "milestones": milestones(start, end),
        "collage": album_collage(start, end),
    }


# Discoveries

def track_row(r: dict, extra: str) -> dict:
    return {"key": r["key"], "title": r["name"], "subtitle": r["artist"], "value": r["plays"],
            "value_text": number(r["plays"]),
            "detail": summary_text(plays_text(r["plays"]), minutes=r["minutes"]) + "\n" + extra,
            "image": cover_url(r["artist"], r["album"], r["name"])}


def discoveries(start: datetime, end: datetime) -> dict:
    """Tracks and artists heard for the first time ever in the period."""
    tracks = listening.new_tracks(start, end)
    artists = listening.new_artists(start, end)
    plays = listening.summary(start, end)["plays"]
    if tracks or artists:
        summary = t("stats.discoveries.summary", tracks=number(len(tracks)), artists=number(len(artists)))
        if plays:
            new_share = share(sum(r["plays"] for r in tracks), plays)
            summary += "  ·  " + t("stats.discoveries.share", percent=percent(new_share))
        first = listening.first_play()
        if first and first >= start:
            summary += "\n" + t("stats.discoveries.first_period")
    else:
        summary = t("stats.discoveries.none")
    return {
        "title": t("stats.discoveries"), "summary": summary, "empty": t("stats.discoveries.none"),
        "tracks_title": t("stats.new_tracks"), "artists_title": t("stats.new_artists"),
        "tracks": [track_row(r, t("stats.discoveries.first_heard", date=format_date(r["first_played"])))
                   for r in tracks[:DISCOVERY_COUNT]],
        "artists": [{
            "key": r["key"], "title": r["name"], "subtitle": tracks_text(r["tracks"]), "value": r["plays"],
            "value_text": number(r["plays"]),
            "detail": summary_text(plays_text(r["plays"]), tracks_text(r["tracks"]), minutes=r["minutes"])
                      + "\n" + t("stats.discoveries.first_heard", date=format_date(r["first_played"])),
            "image": artist_url(r["name"]),
        } for r in artists[:DISCOVERY_COUNT]],
    }


def forgotten() -> dict:
    """Over all time, the tracks once played a lot but not lately, as that looks back from today."""
    today = datetime.now().astimezone()
    rows = []
    for r in listening.forgotten(FORGOTTEN_DAYS, FORGOTTEN_MIN_PLAYS, FORGOTTEN_COUNT):
        days = (today - listening.from_utc(r["last_played"])).days
        rows.append(track_row(r, t("stats.forgotten.last", date=format_date(r["last_played"]), days=number(days))))
    return {"title": t("stats.forgotten"),
            "summary": t("stats.forgotten.summary", days=FORGOTTEN_DAYS, plays=FORGOTTEN_MIN_PLAYS),
            "empty": t("stats.forgotten.none", days=FORGOTTEN_DAYS), "tracks": rows}


# Diversity

def diversity(period: str, offset: int, start: datetime, end: datetime) -> dict:
    """The share of the five most played artists, of different tracks and of new tracks, with a sentence
    comparing it with the period before, and those five artists with their share of the plays."""
    now = listening.diversity(start, end)
    result = {"title": t("stats.diversity"), "top_title": t("stats.diversity.top_artists"), "values": [],
              "verdict": "", "artists": []}
    if not now["plays"]:
        result["verdict"] = t("stats.empty")
        return result
    top5, new = share(now["top5"], now["plays"]), share(now["new"], now["plays"])
    values = [("top5", top5), ("variety", share(now["tracks"], now["plays"]))]
    sentences = []
    # Over all time every track is new, so there is nothing to compare
    if period != "all":
        values.append(("new", new))
        previous_start, previous_end = listening.period_range(period, offset + 1)
        first = listening.first_play()
        # Only once the whole period before was recorded, or everything in it would look new
        if first is not None and first <= previous_start:
            before = listening.diversity(previous_start, previous_end)
            if before["plays"]:
                before_new = share(before["new"], before["plays"])
                verdict = ("more_new" if new - before_new >= DIVERSITY_CHANGE
                           else "more_familiar" if before_new - new >= DIVERSITY_CHANGE else "same")
                sentences.append(t(f"stats.diversity.{verdict}", before=percent(before_new), now=percent(new)))
    if top5 >= FOCUSED and now["artists"] > 5:
        sentences.append(t("stats.diversity.focused"))
    elif top5 <= WIDE:
        sentences.append(t("stats.diversity.wide"))
    result["values"] = [{"label": t(f"stats.diversity.{name}"), "value": value, "text": percent(value)}
                        for name, value in values]
    result["verdict"] = " ".join(sentences)
    result["artists"] = [{
        "key": a["key"], "title": a["name"], "subtitle": tracks_text(a["tracks"]), "value": a["plays"],
        "value_text": percent(share(a["plays"], now["plays"])), "detail": plays_text(a["plays"]),
    } for a in listening.top_artists(start, end, DIVERSITY_TOP)]
    return result


# Milestones

def year_back(moment: datetime) -> datetime:
    """The same moment a year earlier (29 February becomes the 28th)."""
    try:
        return moment.replace(year=moment.year - 1)
    except ValueError:
        return moment.replace(year=moment.year - 1, day=28)


def milestone_date(iso: str) -> str:
    moment = listening.from_utc(iso).astimezone()
    year = f" {moment.year}" if moment.year != datetime.now().year else ""
    return f"{moment.day} {month_name(moment.month, True)}{year}"


def milestone_text(milestone: dict) -> str:
    count = number(milestone["count"])
    if milestone["kind"] == "total":
        return t("stats.milestones.total", count=count)
    if milestone["kind"] == "artist":
        return t("stats.milestones.artist", name=milestone["name"], count=count)
    if milestone["kind"] == "track":
        return t("stats.milestones.track", name=milestone["name"], artist=milestone["artist"], count=count)
    if milestone["kind"] == "met":
        return t("stats.milestones.met", name=milestone["name"], plays=plays_text(milestone["count"]))
    return t("stats.milestones.start")


def milestones(start: datetime, end: datetime) -> dict:
    """The milestones reached in the period with how far the next count of plays is."""
    step = listening.next_total_step()
    period_start, period_end = listening.to_utc(start), listening.to_utc(end)
    reached = [m for m in listening.milestones() if period_start <= m["at"] < period_end][:MILESTONES_SHOWN]
    return {
        "title": t("stats.milestones"),
        "summary": t("stats.milestones.next", count=number(step[0]), left=number(step[1])) if step else "",
        "empty": t("stats.milestones.none"),
        "items": [{
            "date": milestone_date(m["at"]), "text": milestone_text(m), "kind": m["kind"],
            "column": "artist_key" if m["kind"] in ("artist", "met") else "track_key" if m["kind"] == "track" else None,
            "key": m.get("key"),
        } for m in reached],
    }


def month_bounds(moment: datetime) -> tuple[datetime, datetime]:
    """The start of moment's month and of the next one."""
    start = moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)


def now_status(key: str, ranked: list[str]) -> dict:
    """Where a track or artist of a year ago stands in this month's plays."""
    status = ("top" if key in ranked[:YEAR_AGO_SHOWN] else "still" if key in ranked else "gone")
    return {"status": status, "status_text": t(f"stats.year_ago.{status}", count=YEAR_AGO_SHOWN)}


def year_ago(now: datetime | None = None, db_path=listening.DB_PATH) -> dict | None:
    """The tracks and artists played most in the same month a year earlier, each with where it stands this month,
    or None without plays then, so the card only shows up once there is a year of plays behind it."""
    now = (now or datetime.now()).astimezone()
    start, end = month_bounds(now.replace(year=now.year - 1, day=1))
    tracks = listening.top_tracks(start, end, YEAR_AGO_SHOWN, db_path=db_path)
    if not tracks:
        return None
    this_start, this_end = month_bounds(now)
    tracks_now = [r["key"] for r in listening.top_tracks(this_start, this_end, ALL_ROWS, db_path=db_path)]
    artists_now = [r["key"] for r in listening.top_artists(this_start, this_end, ALL_ROWS, db_path=db_path)]
    return {
        "title": t("stats.year_ago"),
        "summary": t("stats.year_ago.summary", month=f"{month_name(start.month)} {start.year}"),
        "tracks_title": t("stats.year_ago.tracks"), "artists_title": t("stats.year_ago.artists"),
        "tracks": [{"key": r["key"], "title": r["name"], "subtitle": r["artist"],
                    "image": cover_url(r["artist"], r["album"], r["name"]), **now_status(r["key"], tracks_now)}
                   for r in tracks],
        "artists": [{"key": r["key"], "title": r["name"], "subtitle": "", "image": artist_url(r["name"]),
                     **now_status(r["key"], artists_now)}
                    for r in listening.top_artists(start, end, YEAR_AGO_SHOWN, db_path=db_path)],
    }


# Streak

def genre_streak() -> dict | None:
    """The genre family with the longest run going on now, by its artists' main genres, as the phone's
    StreakCard: {family, days, today}, or None without one."""
    from playlist_tracker.api.wrapped import genre_family
    days: dict[str, set] = {}
    families: dict[str, str | None] = {}
    for day, artist in listening.days_with_artists():
        if artist not in families:
            facts = artist_info.cached(artist)
            families[artist] = genre_family(facts["genres"][0]) if facts and facts["genres"] else None
        if families[artist]:
            days.setdefault(families[artist], set()).add(day)
    best = None
    today = datetime.now().date()
    for family, played in days.items():
        current, in_today, _ = listening.current_run(played, today)
        if current and (best is None or current > best["days"]
                        or (current == best["days"] and best["family"] == "other" and family != "other")):
            best = {"family": family, "days": current, "today": in_today}
    return best


def streak_card() -> dict:
    """Two streaks: days in a row with any play (the longest run, a hint, the song and artist that carried it),
    and apart, days in a row of one genre with its title at 3, 7, 14, 30 and 100 days and the road to the next."""
    streak = listening.streak()
    days = streak["current"]
    record = listening.streak_special(streak) == "record"
    card = {
        "title": t("stats.streak"), "value": number(days),
        "unit": t("stats.streak.day_one" if days == 1 else "stats.streak.days"),
        "longest": t("stats.streak.longest", days=number(streak["longest"])) if streak["longest"] else "",
        "hint": t("stats.streak.record", days=number(days)) if record
        else t("stats.streak.none" if days == 0 else "stats.streak.going" if streak["today"] else "stats.streak.keep"),
        "record": record, "genre": None, "stars": [],
    }
    if not days:
        return card
    start = datetime.combine(streak["start"], datetime.min.time()).astimezone()
    end = datetime.now().astimezone() + timedelta(days=1)
    for row in listening.top_tracks(start, end, 1):
        card["stars"].append({"label": t("stats.streak.song"), "column": "track_key", "key": row["key"],
                              "title": f"{row['name']}  ·  {row['artist']}", "plays": plays_text(row["plays"]),
                              "image": cover_url(row["artist"], row["album"], row["name"]), "round": False})
    for row in listening.top_artists(start, end, 1):
        card["stars"].append({"label": t("stats.streak.artist"), "column": "artist_key", "key": row["key"],
                              "title": row["name"], "plays": plays_text(row["plays"]),
                              "image": artist_url(row["name"]), "round": True})
    genre = genre_streak()
    if genre:
        family, run = genre["family"], genre["days"]
        level = listening.streak_level(run)
        next_level = listening.streak_next_level(run)
        part = {
            "family": family,
            "headline": t("stats.streak.genre", days=number(run), genre=t(f"stats.streak.genre.{family}")),
            "level_up": genre["today"] and run in listening.STREAK_LEVELS and t("stats.streak.level_up") or None,
            "say": t(f"stats.streak.{family}.{level}.say") if level else None,
            "road": None,
        }
        # The whole ladder of titles, and where the run is on it
        part["road"] = {"labels": [number(step) for step in listening.STREAK_LEVELS],
                        "place": listening.streak_place(run), "next": level}
        if next_level is None:
            part["next"] = t("stats.streak.top")
        else:
            part["next"] = (t("stats.streak.first") if level == 0
                            else t("stats.streak.next_tomorrow") if next_level - run == 1
                            else t("stats.streak.next", days=number(next_level), left=number(next_level - run)))
        card["genre"] = part
    return card


# Album collage

def album_collage(start: datetime, end: datetime) -> dict:
    """The period's most played albums, one per cover; the window lays their covers out in a grid."""
    count = collage.COLUMNS ** 2
    albums = []
    if collage.available:
        # Twice as many as fit, as some are left out for sharing a cover with another
        albums = listening.top_albums(start, end, count * 2)
        for album in albums:
            path = artwork.cover_path(album["artist"], album["album"], album["name"])
            album["cover"] = path if path.exists() else None
        albums = collage.distinct(albums, count)
    return {
        "title": t("stats.collage"), "summary": t("stats.collage.summary"), "empty": t("stats.empty"),
        "columns": collage.COLUMNS, "available": collage.available,
        "albums": [{
            "key": listening.album_key(a["artist_key"], a["album_lower"]), "title": a["album"],
            "artist": a["artist"], "detail": plays_text(a["plays"]),
            "image": cover_url(a["artist"], a["album"], a["name"]),
        } for a in albums],
    }


# Genres

def genres(period: str, offset: int, arrived: Callable[[], None]) -> dict:
    """The genre share and the genres over time. Genres are looked up one artist at a time in the
    background; arrived() is called as each is found, so the window can ask again."""
    period, offset, start, end = period_bounds(period, offset)
    previous = None if period == "all" else listening.period_range(period, offset + 1)
    return {"genres": genre_share(start, end, arrived, period, previous), "shift": genre_shift(period, start, end)}


def genre_share(start: datetime, end: datetime, arrived: Callable[[], None], period: str = "all",
                previous: tuple[datetime, datetime] | None = None) -> dict:
    """Share of the period's plays per genre; an artist's plays count for its main genre. With it the ring of the
    biggest genres and the genre families against the previous period (when given)."""
    artists = listening.top_artists(start, end, -1)
    total = sum(a["plays"] for a in artists)
    found: dict[str, dict] = {}
    waiting = 0
    for artist in artists:
        facts = artist_info.request(artist["name"], artist["key"], arrived, priority=artist_info.LATER)
        if facts and facts["genres"]:
            genre = found.setdefault(facts["genres"][0], {"plays": 0, "artists": []})
            genre["plays"] += artist["plays"]
            # A collaboration is listed by its main artist, once
            name = name_variants(artist["name"])[-1]
            if all(key(name) != key(other) for other in genre["artists"]):
                genre["artists"].append(name)
        elif artist_info.waiting(artist["key"]):
            waiting += 1
    ordered = sorted(found.items(), key=lambda item: -item[1]["plays"])
    names = [capitalized(name) for name, _ in ordered]
    parts = []
    if names:
        parts.append(t(f"stats.genres.summary.{min(len(names), 3)}", first=names[0],
                       second=names[1] if len(names) > 1 else "", third=names[2] if len(names) > 2 else "",
                       count=number(len(names))))
    if waiting:
        parts.append(t("stats.genres.loading", count=number(waiting)))
    known = sum(genre["plays"] for _, genre in ordered)
    return {
        "title": t("stats.genres"), "summary": "  ·  ".join(parts), "empty": t("stats.genres.none"),
        "waiting": waiting,
        "ring": genre_ring(ordered, known),
        "families": family_web({name: genre["plays"] for name, genre in ordered}, period, previous),
        "rows": [{
            "key": name, "title": capitalized(name), "subtitle": ", ".join(genre["artists"][:3]),
            "value": genre["plays"], "value_text": percent(share(genre["plays"], total)),
            "detail": f"{plays_text(genre['plays'])}\n" + t("stats.genres.artists", names=", ".join(genre["artists"][:5])),
        } for name, genre in ordered[:GENRE_COUNT]],
    }


RING_COUNT = 4
WEB_AXES = 6
# The families the web always shows enough of to make a shape, when the period has fewer
WEB_DEFAULTS = ("metal", "rock", "pop")


def genre_ring(ordered: list[tuple[str, dict]], known: int) -> list[dict]:
    """The ring's slices: the biggest genres (series 0-3) and the rest of the known ones ("other"), as shares of
    the plays whose genre is known."""
    slices = [{"series": index, "text": capitalized(name), "share": genre["plays"] / known,
               "percent": percent(share(genre["plays"], known))}
              for index, (name, genre) in enumerate(ordered[:RING_COUNT])]
    rest = sum(genre["plays"] for _, genre in ordered[RING_COUNT:])
    if rest:
        slices.append({"series": "other", "text": t("stats.genre_shift.other"), "share": rest / known,
                       "percent": percent(share(rest, known))})
    return slices


def family_shares(plays: dict[str, int]) -> dict[str, float]:
    """The share of each genre family (wrapped.GENRE_FAMILIES) of the plays by genre"""
    from playlist_tracker.api.wrapped import genre_family
    total = sum(plays.values())
    families: dict[str, float] = {}
    for name, count in plays.items():
        family = genre_family(name)
        families[family] = families.get(family, 0) + count / total
    return families


def family_web(plays: dict[str, int], period: str, previous: tuple[datetime, datetime] | None) -> dict | None:
    """The genre families' shares for the web: up to six axes, the period's biggest families first, beside the
    previous period's shares when there are (its artists' genres as far as they are known)."""
    if not plays:
        return None
    now = family_shares(plays)
    before: dict[str, float] = {}
    if previous:
        counts: dict[str, int] = {}
        for artist in listening.top_artists(previous[0], previous[1], -1):
            if genre := main_genre(artist["key"]):
                counts[genre] = counts.get(genre, 0) + artist["plays"]
        before = family_shares(counts) if counts else {}
    names = sorted((name for name in set(now) | set(before) if name != "other"),
                   key=lambda name: (-now.get(name, 0), -before.get(name, 0)))[:WEB_AXES]
    for name in WEB_DEFAULTS:
        if len(names) >= 3:
            break
        if name not in names:
            names.append(name)
    legend = {"current": t(f"stats.this.{period}"), "previous": t(f"stats.previous.{period}")} if before else None

    def tooltip(name: str) -> str:
        lines = [t(f"stats.family.{name}")]
        lines.append(f"{legend['current']}: {percent(round(100 * now.get(name, 0)))}" if legend
                     else percent(round(100 * now.get(name, 0))))
        if legend:
            lines.append(f"{legend['previous']}: {percent(round(100 * before.get(name, 0)))}")
        return "\n".join(lines)

    return {
        "axes": [{"name": t(f"stats.family.{name}"), "now": now.get(name, 0),
                  "before": before.get(name, 0) if before else None, "tooltip": tooltip(name)} for name in names],
        "legend": legend,
    }


def main_genre(artist_key: str) -> str | None:
    """An artist's main genre once it is known (the genre share looks them up)."""
    facts = artist_info.cached(artist_key)
    return facts["genres"][0] if facts and facts["genres"] else None


def yearly_shift(period: str, days: list) -> bool:
    """All time past three years goes by year."""
    if period != "all" or not days:
        return False
    first = datetime.strptime(days[0][0], "%Y-%m-%d")
    today = datetime.now()
    return (today.year - first.year) * 12 + today.month - first.month >= GENRE_SHIFT_MAX_MONTHS


def shift_bucket(period: str, day: str, yearly: bool) -> str:
    """The column a day ('%Y-%m-%d') falls in: the day of a week, the week of a month, the month of a year."""
    if yearly:
        return day[:4]
    if period == "week":
        return day
    if period == "month":
        # A week begins on Monday, or on the 1st when the month begins in the middle of it
        moment = datetime.strptime(day, "%Y-%m-%d")
        return max(moment - timedelta(days=moment.weekday()), moment.replace(day=1)).strftime("%Y-%m-%d")
    return day[:7]


def shift_label(period: str, bucket: str, yearly: bool) -> str:
    if yearly:
        return bucket
    if period == "week":
        return t("stats.weekdays").split(",")[datetime.strptime(bucket, "%Y-%m-%d").weekday()]
    if period == "month":
        moment = datetime.strptime(bucket, "%Y-%m-%d")
        return f"{moment.day} {month_name(moment.month, True)}"
    year, month = int(bucket[:4]), int(bucket[5:7])
    return month_name(month, True) + (f" {year % 100:02d}" if period == "all" else "")


def shift_buckets(period: str, start: datetime, end: datetime, first_day: str | None, yearly: bool) -> list[str]:
    """Every column of the period in order, also the ones without plays, up to today; all time starts at the
    first play (first_day)."""
    if period == "all":
        if first_day is None:
            return []
        start = datetime.strptime(first_day, "%Y-%m-%d").astimezone()
    keys: list[str] = []
    day = start
    today = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    last = min(end, today + timedelta(days=1))
    while day < last:
        bucket = shift_bucket(period, day.strftime("%Y-%m-%d"), yearly)
        if bucket not in keys:
            keys.append(bucket)
        day += timedelta(days=1)
    return keys


def shift_column(label: str, counts: dict[str, int], top: list[str]) -> dict:
    """One column: the shares of the top genres (series 0-3) and of the rest ("other"), bottom first."""
    total = sum(counts.values())
    if not total:
        return {"label": label, "segments": [], "tooltip": f"{label}\n{t('stats.genres.none')}"}
    others = total - sum(counts.get(name, 0) for name in top)
    segments = [{"series": index, "share": counts.get(name, 0) / total} for index, name in enumerate(top)]
    segments.append({"series": "other", "share": others / total})
    lines = [f"{capitalized(name)}: {percent(share(counts.get(name, 0), total))}" for name in top if counts.get(name)]
    if others:
        lines.append(f"{t('stats.genre_shift.other')}: {percent(share(others, total))}")
    return {"label": label, "segments": segments, "tooltip": "\n".join([label, *lines])}


def genre_shift(period: str, start: datetime, end: datetime) -> dict:
    """How the share of the period's main genres changed over it: per day of a week, per week of a month, per
    month of a year (or of all time, per year past three years). The biggest genres get a color (series 0-3),
    the rest is "other"; plays by artists of unknown genre are left out."""
    days = listening.artist_days(start, end)
    yearly = yearly_shift(period, days)
    buckets: dict[str, dict[str, int]] = {}
    totals: dict[str, int] = {}
    known = 0
    for day, artist_key, plays in days:
        genre = main_genre(artist_key)
        if genre is None:
            continue
        known += plays
        counts = buckets.setdefault(shift_bucket(period, day, yearly), {})
        counts[genre] = counts.get(genre, 0) + plays
        totals[genre] = totals.get(genre, 0) + plays
    top = [name for name, _ in sorted(totals.items(), key=lambda item: -item[1])[:GENRE_SHIFT_COUNT]]
    keys = shift_buckets(period, start, end, days[0][0] if days else None, yearly)
    columns = [shift_column(shift_label(period, key, yearly), buckets.get(key, {}), top) for key in keys]
    others = known - sum(totals[name] for name in top)
    legend = [{"series": index, "text": f"{capitalized(name)}  {percent(share(totals[name], known))}"}
              for index, name in enumerate(top)]
    if others:
        legend.append({"series": "other", "text": f"{t('stats.genre_shift.other')}  {percent(share(others, known))}"})
    unit = "year" if yearly else period
    return {
        "title": t("stats.genre_shift"),
        "summary": t("stats.genre_shift.summary", unit=t(f"stats.genre_shift.unit.{unit}")) if known else "",
        "empty": t("stats.genres.none"), "legend": legend, "columns": columns if known else [],
    }
