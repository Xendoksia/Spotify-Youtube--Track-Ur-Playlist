"""
Cards of the statistics overview that look beyond the top lists: discoveries (or, over all time, the
tracks not played lately), the share of each genre and the album collage. Each one fills itself in for the
period the overview shows.
"""

from __future__ import annotations

from datetime import datetime
from tkinter import ttk

from playlist_tracker.core.i18n import number, t
from playlist_tracker.core.text import format_date
from playlist_tracker.music import artist_info, collage, listening
from playlist_tracker.ui.charts import BarList
from playlist_tracker.ui.stats.text import plays_text, summary_text, tracks_text
from playlist_tracker.ui.stats.widgets import SECTION_GAP, card, card_column
from playlist_tracker.ui.theme import px

DISCOVERY_COUNT = 5
FORGOTTEN_COUNT = 10
FORGOTTEN_DAYS = 30
FORGOTTEN_MIN_PLAYS = 3
GENRE_COUNT = 8
GENRE_REDRAW_MS = 3000
# Largest side of the album collage, in design pixels
COLLAGE_PREVIEW = 420


def fit_height(chart: BarList, rows: int) -> None:
    """Make a list only as tall as its rows: it is often short or empty."""
    chart.configure(height=px(BarList.ROW_HEIGHT * rows if rows else 60))


class Discoveries:
    """Tracks and artists heard for the first time ever in the period. Under all time the tracks once played
    a lot but not lately take their place, as that looks back from today."""

    def __init__(self, parent, page):
        """page: the overview, for its pictures and for opening detail pages."""
        self.page = page
        slot = ttk.Frame(parent, style="Card.TFrame")
        slot.pack(fill="x", pady=(px(SECTION_GAP), 0))

        self.discoveries = card(slot, "star", t("stats.discoveries"), summary=True)
        lists = ttk.Frame(self.discoveries, style="Card.TFrame")
        lists.pack(fill="x")
        empty = t("stats.discoveries.none")
        self.new_tracks = BarList(card_column(lists, t("stats.new_tracks"), 0), empty, DISCOVERY_COUNT)
        self.new_artists = BarList(card_column(lists, t("stats.new_artists"), 1), empty, DISCOVERY_COUNT,
                                   round_images=True)
        for chart in (self.new_tracks, self.new_artists):
            chart.pack(fill="x")

        self.forgotten_card = card(slot, "history", t("stats.forgotten"), summary=True)
        self.forgotten_card.summary.configure(
            text=t("stats.forgotten.summary", days=FORGOTTEN_DAYS, plays=FORGOTTEN_MIN_PLAYS))
        self.forgotten = BarList(self.forgotten_card, t("stats.forgotten.none", days=FORGOTTEN_DAYS),
                                 FORGOTTEN_COUNT)
        self.forgotten.pack(fill="x")

    def fill(self, period: str, start, end):
        # Everything is new over all time, so discoveries only make sense for a week, month or year
        if period == "all":
            self.discoveries.pack_forget()
            self._fill_forgotten()
            return
        self.forgotten_card.pack_forget()
        self.discoveries.pack(fill="x")
        tracks = listening.new_tracks(start, end)
        artists = listening.new_artists(start, end)
        plays = listening.summary(start, end)["plays"]
        if tracks or artists:
            text = t("stats.discoveries.summary", tracks=number(len(tracks)), artists=number(len(artists)))
            if plays:
                share = round(sum(r["plays"] for r in tracks) * 100 / plays)
                text += "  ·  " + t("stats.discoveries.share", percent=t("stats.percent", value=share))
            first = listening.first_play()
            if first and first >= start:
                text += "\n" + t("stats.discoveries.first_period")
        else:
            text = t("stats.discoveries.none")
        self.discoveries.summary.configure(text=text)

        pictures, size = self.page.pictures, BarList.IMAGE_SIZE
        self.new_tracks.set_rows([{
            "title": r["name"], "subtitle": r["artist"], "value": r["plays"], "value_text": number(r["plays"]),
            "tooltip": f"{r['name']}\n{r['artist']}\n" + summary_text(plays_text(r["plays"]), minutes=r["minutes"])
                       + "\n" + t("stats.discoveries.first_heard", date=format_date(r["first_played"])),
            "image": pictures.cover(r, size, 4), "on_click": self.page.opener("track_key", r["key"]),
        } for r in tracks[:DISCOVERY_COUNT]])
        self.new_artists.set_rows([{
            "title": r["name"], "subtitle": tracks_text(r["tracks"]), "value": r["plays"],
            "value_text": number(r["plays"]),
            "tooltip": f"{r['name']}\n" + summary_text(plays_text(r["plays"]), tracks_text(r["tracks"]),
                                                       minutes=r["minutes"])
                       + "\n" + t("stats.discoveries.first_heard", date=format_date(r["first_played"])),
            "image": pictures.artist_photo(r["name"], size), "on_click": self.page.opener("artist_key", r["key"]),
        } for r in artists[:DISCOVERY_COUNT]])

    def _fill_forgotten(self):
        self.forgotten_card.pack(fill="x")
        today = datetime.now().astimezone()
        rows = []
        for r in listening.forgotten(FORGOTTEN_DAYS, FORGOTTEN_MIN_PLAYS, FORGOTTEN_COUNT):
            days = (today - listening.from_utc(r["last_played"])).days
            rows.append({
                "title": r["name"], "subtitle": r["artist"], "value": r["plays"], "value_text": number(r["plays"]),
                "tooltip": f"{r['name']}\n{r['artist']}\n"
                           + summary_text(plays_text(r["plays"]), minutes=r["minutes"]) + "\n"
                           + t("stats.forgotten.last", date=format_date(r["last_played"]), days=number(days)),
                "image": self.page.pictures.cover(r, BarList.IMAGE_SIZE, 4),
                "on_click": self.page.opener("track_key", r["key"]),
            })
        fit_height(self.forgotten, len(rows))
        self.forgotten.set_rows(rows)


class Genres:
    """Share of the period's plays per genre; an artist's plays count for its main genre. Genres are looked
    up one artist at a time, so the card redraws itself as they arrive."""

    def __init__(self, row, column: int):
        self.card = card(row, "tag", t("stats.genres"), column, summary=True)
        self.chart = BarList(self.card, t("stats.genres.none"), GENRE_COUNT, images=False)
        self.chart.pack(fill="x")
        self._pending = False
        self._range = None

    def fill(self, start, end):
        self._range = (start, end)
        self._fill()

    def _arrived(self):
        # Redraw only this card, at most every few seconds
        if not self._pending:
            self._pending = True
            self.card.after(GENRE_REDRAW_MS, self._fill)

    def _fill(self):
        self._pending = False
        if not self.card.winfo_exists() or self._range is None:
            return
        artists = listening.top_artists(*self._range, -1)
        total = sum(a["plays"] for a in artists)
        genres: dict[str, dict] = {}
        known = waiting = 0
        for artist in artists:
            facts = artist_info.request(artist["name"], artist["key"], self.card, self._arrived,
                                        priority=artist_info.LATER)
            if facts and facts["genres"]:
                genre = genres.setdefault(facts["genres"][0], {"plays": 0, "artists": []})
                genre["plays"] += artist["plays"]
                genre["artists"].append(artist["name"])
                known += artist["plays"]
            elif artist_info.waiting(artist["key"]):
                waiting += 1
        parts = []
        if total:
            parts.append(t("stats.genres.summary", percent=t("stats.percent", value=round(100 * known / total))))
        if waiting:
            parts.append(t("stats.genres.loading", count=number(waiting)))
        self.card.summary.configure(text="  ·  ".join(parts))
        rows = sorted(genres.items(), key=lambda item: -item[1]["plays"])[:GENRE_COUNT]
        fit_height(self.chart, len(rows))
        self.chart.set_rows([{
            "title": name[:1].upper() + name[1:],
            "subtitle": ", ".join(genre["artists"][:3]),
            "value": genre["plays"],
            "value_text": t("stats.percent", value=round(100 * genre["plays"] / total)),
            "tooltip": f"{name}\n{plays_text(genre['plays'])}\n"
                       + t("stats.genres.artists", names=", ".join(genre["artists"][:5])),
        } for name, genre in rows])


def share(part: int, whole: int) -> int:
    return round(100 * part / whole) if whole else 0


class Diversity:
    """How varied the period's listening was: the share of its five most played artists, of different tracks
    and of new tracks, with a sentence comparing it with the period before."""

    NAMES = ("top5", "variety", "new")
    # Points of difference in the new tracks' share that count as more or less discovery
    CHANGE = 5
    FOCUSED, WIDE = 70, 40

    def __init__(self, row, column: int):
        self.card = card(row, "layers", t("stats.diversity"), column)
        values = ttk.Frame(self.card, style="Card.TFrame")
        values.pack(fill="x")
        self.cells = {}
        for index, name in enumerate(self.NAMES):
            values.columnconfigure(index, weight=1, uniform="diversity")
            cell = ttk.Frame(values, style="Card.TFrame")
            cell.grid(row=0, column=index, sticky="w")
            ttk.Label(cell, text=t(f"stats.diversity.{name}"), style="CardMuted.TLabel").pack(anchor="w")
            cell.value = ttk.Label(cell, style="TileValue.TLabel")
            cell.value.pack(anchor="w")
            self.cells[name] = cell
        self.verdict = ttk.Label(self.card, style="Card.TLabel", justify="left")
        self.verdict.pack(anchor="w", fill="x", pady=(px(12), 0))
        self.card.bind("<Configure>", lambda e: self.verdict.configure(wraplength=max(px(200), e.width - px(40))))

    def fill(self, period: str, offset: int, start, end):
        now = listening.diversity(start, end)
        if not now["plays"]:
            for cell in self.cells.values():
                cell.value.configure(text="—")
            self.verdict.configure(text=t("stats.empty"))
            self.verdict.pack(anchor="w", fill="x", pady=(px(12), 0))
            return
        percent = lambda value: t("stats.percent", value=value)  # noqa: E731
        top5, new = share(now["top5"], now["plays"]), share(now["new"], now["plays"])
        self.cells["top5"].value.configure(text=percent(top5))
        self.cells["variety"].value.configure(text=percent(share(now["tracks"], now["plays"])))
        sentences = []
        # Over all time every track is new, so there is nothing to compare
        if period == "all":
            self.cells["new"].grid_remove()
        else:
            self.cells["new"].grid()
            self.cells["new"].value.configure(text=percent(new))
            previous_start, previous_end = listening.period_range(period, offset + 1)
            first = listening.first_play()
            # Only once the whole period before was recorded, or everything in it would look new
            if first is not None and first <= previous_start:
                before = listening.diversity(previous_start, previous_end)
                if before["plays"]:
                    before_new = share(before["new"], before["plays"])
                    key = ("more_new" if new - before_new >= self.CHANGE
                           else "more_familiar" if before_new - new >= self.CHANGE else "same")
                    sentences.append(t(f"stats.diversity.{key}", before=percent(before_new), now=percent(new)))
        if top5 >= self.FOCUSED and now["artists"] > 5:
            sentences.append(t("stats.diversity.focused"))
        elif top5 <= self.WIDE:
            sentences.append(t("stats.diversity.wide"))
        self.verdict.configure(text=" ".join(sentences))
        # No sentence (the period before was not wholly recorded): no empty line under the values
        if sentences:
            self.verdict.pack(anchor="w", fill="x", pady=(px(12), 0))
        else:
            self.verdict.pack_forget()


class Collage:
    """The period's most played album covers in a grid; a cover opens its album's page."""

    def __init__(self, row, column: int, page):
        self.page = page
        self.albums = []
        self._side = px(COLLAGE_PREVIEW)
        self._range = None
        self.card = card(row, "disc", t("stats.collage"), column, summary=True)
        self.card.summary.configure(text=t("stats.collage.summary"))
        if not collage.available:
            self.card.grid_remove()
        self.preview = ttk.Label(self.card, style="Card.TLabel", cursor="hand2")
        self.preview.pack(anchor="center")
        self.preview.bind("<Button-1>", self._click)
        # The collage shrinks to fit a narrow card
        self.card.bind("<Configure>", lambda e: self._fit())

    def fill(self, start, end):
        self._range = (start, end)
        if not collage.available:
            return
        # Twice as many as fit, as some are left out for sharing a cover with another
        albums = listening.top_albums(start, end, collage.COLUMNS ** 2 * 2)
        for album in albums:
            album["cover"] = self.page.pictures.cover_path(album["artist"], album["album"], album["name"])
        self.albums = collage.distinct(albums, collage.COLUMNS ** 2)
        if not self.albums:
            self.preview.configure(image="", text=t("stats.empty"))
            return
        from PIL import ImageTk
        image = collage.build(self.albums, collage.COLUMNS, self._side)
        self.preview.configure(image=self.page.pictures.keep(ImageTk.PhotoImage(image)), text="")

    def _fit(self):
        width = self.card.winfo_width() - 2 * px(16) - 2
        side = max(px(160), min(px(COLLAGE_PREVIEW), width))
        if abs(side - self._side) > px(8) and self._range:
            self._side = side
            self.fill(*self._range)

    def _click(self, event):
        cell = self._side / collage.COLUMNS
        column, row = int(event.x // cell), int(event.y // cell)
        index = row * collage.COLUMNS + column
        if 0 <= column < collage.COLUMNS and index < len(self.albums):
            album = self.albums[index]
            self.page.open_detail(listening.ALBUM, listening.album_key(album["artist_key"], album["album_lower"]))
