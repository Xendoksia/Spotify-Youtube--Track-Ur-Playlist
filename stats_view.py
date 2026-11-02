"""
Statistics tab of the Listening section: most played tracks and artists of a week, month or
year, counted from the plays recorded in listening.db.
"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk

import artwork
import listening
from charts import BarList, ColumnChart, placeholder, rounded_rect
from i18n import number, t
from theme import P
from tracker import format_date

TOP_COUNT = 10
DISCOVERY_COUNT = 5


def plays_text(count: int) -> str:
    return t("stats.plays_one") if count == 1 else t("stats.plays", count=number(count))


def tracks_text(count: int) -> str:
    return t("stats.different_tracks_one") if count == 1 else t("stats.different_tracks", count=number(count))


def summary_text(*parts: str, minutes: int) -> str:
    """Join details with the listening time; plays recorded without a duration add none, so 0 is left out."""
    return "  ·  ".join([*parts, duration_text(minutes)] if minutes else parts)


def duration_text(minutes: int) -> str:
    hours, minutes = divmod(int(minutes), 60)
    return t("stats.hours_minutes", hours=number(hours), minutes=minutes) if hours else t("stats.minutes",
                                                                                        minutes=minutes)


def month_name(month: int, short: bool = False) -> str:
    return t("stats.months_short" if short else "stats.months").split(",")[month - 1]


def period_title(period: str, start: datetime, end: datetime) -> str:
    last = end - timedelta(days=1)
    if period == "week":
        if start.month == last.month:
            return f"{start.day} – {last.day} {month_name(last.month)} {last.year}"
        first_year = f" {start.year}" if start.year != last.year else ""
        return (f"{start.day} {month_name(start.month, True)}{first_year} – "
                f"{last.day} {month_name(last.month, True)} {last.year}")
    if period == "month":
        return f"{month_name(start.month)} {start.year}"
    if period == "year":
        return str(start.year)
    return t("stats.all_time")


def change_tip(change, key, rank) -> str:
    """The rank change written out, as an extra tooltip line."""
    result = change(key, rank, long=True)
    return f"\n{result[0]}" if result else ""


class ScrollFrame(ttk.Frame):
    """A vertically scrolling area; widgets go into .content."""

    def __init__(self, parent):
        super().__init__(parent, style="Card.TFrame")
        self.canvas = tk.Canvas(self, background=P.surface, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.content = ttk.Frame(self.canvas, padding=(16, 4, 16, 16), style="Card.TFrame")
        window = self.canvas.create_window(0, 0, window=self.content, anchor="nw")
        self.content.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(window, width=e.width))
        # The wheel scrolls this area only while the mouse is over it
        self.bind("<Enter>", lambda e: self.bind_all("<MouseWheel>", self._on_wheel))
        self.bind("<Leave>", lambda e: self.unbind_all("<MouseWheel>"))

    def _on_wheel(self, event):
        if self.content.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(-event.delta // 120, "units")


class Hero(ttk.Frame):
    """A large card for the number one track or artist of the period, with its picture."""

    IMAGE_SIZE = 132

    def __init__(self, parent, caption: str, round_image: bool):
        super().__init__(parent, padding=16, style="Tile.TFrame")
        self.round_image = round_image
        size = self.IMAGE_SIZE
        self.picture = tk.Canvas(self, width=size, height=size, background=P.surface, highlightthickness=0)
        self.picture.pack(side="left")
        text = ttk.Frame(self, style="Card.TFrame")
        text.pack(side="left", fill="both", expand=True, padx=(18, 0))
        ttk.Label(text, text=caption.upper(), style="Caption.TLabel").pack(anchor="w", pady=(10, 4))
        self.title = ttk.Label(text, style="HeroTitle.TLabel")
        self.title.pack(anchor="w")
        self.subtitle = ttk.Label(text, style="HeroSubtitle.TLabel")
        self.subtitle.pack(anchor="w")
        details = ttk.Frame(text, style="Card.TFrame")
        details.pack(anchor="w", pady=(10, 0))
        self.detail = ttk.Label(details, style="Card.TLabel")
        self.detail.pack(side="left")
        self.change = ttk.Label(details, style="Card.TLabel")
        self.change.pack(side="left", padx=(10, 0))
        self.bind("<Configure>", lambda e: self._wrap())

    def _wrap(self):
        width = max(120, self.winfo_width() - self.IMAGE_SIZE - 60)
        for label in (self.title, self.subtitle):
            label.configure(wraplength=width)

    def show(self, title: str, subtitle: str, detail: str, image, change: tuple[str, str] | None = None):
        size = self.IMAGE_SIZE
        self.picture.delete("all")
        if image is not None:
            self.picture.create_image(0, 0, image=image, anchor="nw")
        else:
            placeholder(self.picture, 0, 0, size, title, self.round_image, ("Segoe UI Semibold", 40))
        self.title.configure(text=title)
        self.subtitle.configure(text=subtitle)
        self.detail.configure(text=detail)
        text, color = change or ("", P.muted)
        self.change.configure(text=text, foreground=color)

    def show_empty(self, text: str):
        self.picture.delete("all")
        if self.round_image:
            self.picture.create_oval(0, 0, self.IMAGE_SIZE, self.IMAGE_SIZE, fill=P.nav, outline="")
        else:
            rounded_rect(self.picture, 0, 0, self.IMAGE_SIZE, self.IMAGE_SIZE, 10, fill=P.nav)
        self.title.configure(text="—")
        self.subtitle.configure(text=text)
        self.detail.configure(text="")
        self.change.configure(text="")


class StatsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, style="Card.TFrame")
        self.period = "week"
        self.offset = 0
        self.fetcher = artwork.Fetcher(self)
        self._images = []
        self._refresh_pending = False
        self._build()

    def _build(self):
        toolbar = ttk.Frame(self, style="Card.TFrame")
        toolbar.pack(fill="x", padx=16, pady=(16, 0))
        switcher = ttk.Frame(toolbar, padding=3, style="Nav.TFrame")
        switcher.pack(side="left")
        self.period_buttons = {}
        for period in listening.PERIODS:
            button = ttk.Button(switcher, text=t(f"stats.period.{period}"), style="Nav.TButton",
                                command=lambda period=period: self.select_period(period))
            button.pack(side="left")
            self.period_buttons[period] = button
        self.previous_button = ttk.Button(toolbar, text="‹", width=3, command=lambda: self.move(1))
        self.previous_button.pack(side="left", padx=(16, 0))
        self.next_button = ttk.Button(toolbar, text="›", width=3, command=lambda: self.move(-1))
        self.next_button.pack(side="left", padx=(4, 0))
        self.title_label = ttk.Label(toolbar, style="Period.TLabel")
        self.title_label.pack(side="left", padx=12)

        page = ScrollFrame(self)
        page.pack(fill="both", expand=True, pady=(12, 0))
        content = page.content

        tiles = ttk.Frame(content, style="Card.TFrame")
        tiles.pack(fill="x")
        self.tiles = {}
        for index, name in enumerate(("plays", "time", "tracks", "artists")):
            tiles.columnconfigure(index, weight=1, uniform="tile")
            tile = ttk.Frame(tiles, padding=(14, 10), style="Tile.TFrame")
            tile.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 10, 0))
            ttk.Label(tile, text=t(f"stats.tile.{name}"), style="CardMuted.TLabel").pack(anchor="w")
            value = ttk.Label(tile, style="TileValue.TLabel")
            value.pack(anchor="w")
            delta = ttk.Label(tile, style="CardMuted.TLabel", font=("Segoe UI", 9))
            delta.pack(anchor="w")
            self.tiles[name] = (value, delta)

        heroes = ttk.Frame(content, style="Card.TFrame")
        heroes.pack(fill="x", pady=(16, 0))
        heroes.columnconfigure((0, 1), weight=1, uniform="hero")
        self.track_hero = Hero(heroes, t("stats.hero.track"), round_image=False)
        self.track_hero.grid(row=0, column=0, sticky="nsew")
        self.artist_hero = Hero(heroes, t("stats.hero.artist"), round_image=True)
        self.artist_hero.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        empty = t("stats.empty")
        lists = ttk.Frame(content, style="Card.TFrame")
        lists.pack(fill="x", pady=(24, 0))
        self.top_tracks = BarList(self._card(lists, t("stats.top_tracks"), 0), empty, TOP_COUNT - 1, first_rank=2)
        self.top_artists = BarList(self._card(lists, t("stats.top_artists"), 1), empty, TOP_COUNT - 1,
                                   round_images=True, first_rank=2)

        # Tracks and artists heard for the first time ever in this period
        self.discoveries = ttk.Frame(content, style="Card.TFrame")
        self.discoveries.pack(fill="x", pady=(24, 0))
        ttk.Label(self.discoveries, text=t("stats.discoveries"), style="Period.TLabel").pack(anchor="w")
        self.discovery_summary = ttk.Label(self.discoveries, style="CardMuted.TLabel")
        self.discovery_summary.pack(anchor="w", pady=(2, 12))
        discovery_lists = ttk.Frame(self.discoveries, style="Card.TFrame")
        discovery_lists.pack(fill="x")
        empty_new = t("stats.discoveries.none")
        self.new_tracks = BarList(self._card(discovery_lists, t("stats.new_tracks"), 0), empty_new, DISCOVERY_COUNT)
        self.new_artists = BarList(self._card(discovery_lists, t("stats.new_artists"), 1), empty_new,
                                   DISCOVERY_COUNT, round_images=True)
        for chart in (self.new_tracks, self.new_artists):
            chart.pack(fill="x")

        self.charts = charts = ttk.Frame(content, style="Card.TFrame")
        charts.pack(fill="x", pady=(24, 0))
        self.timeline_card = self._card(charts, "", 0, weight=3)
        self.timeline = ColumnChart(self.timeline_card, 170, empty)
        self.hours = ColumnChart(self._card(charts, t("stats.hours"), 1, weight=2), 170, empty)
        for chart in (self.top_tracks, self.top_artists, self.timeline, self.hours):
            chart.pack(fill="x")

    def _card(self, parent, title: str, column: int, weight: int = 1) -> ttk.Frame:
        parent.columnconfigure(column, weight=weight, uniform="card")
        card = ttk.Frame(parent, style="Card.TFrame")
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 32, 0))
        card.title = ttk.Label(card, text=title, style="Section.TLabel")
        card.title.pack(anchor="w", pady=(0, 8))
        return card

    def select_period(self, period: str):
        self.period, self.offset = period, 0
        self.refresh()

    def move(self, step: int):
        self.offset = max(0, self.offset + step)
        self.refresh()

    def _artwork_arrived(self):
        # Several downloads usually finish together, so redraw once for all of them
        if not self._refresh_pending:
            self._refresh_pending = True
            self.after(400, self.refresh)

    def _cover(self, row: dict, size: int, radius: int):
        path = self.fetcher.cover(row["artist"], row["album"] or "", row["name"], self._artwork_arrived)
        return self._keep(artwork.photo(path, size, P.surface, radius=radius))

    def _artist_photo(self, name: str, size: int):
        path = self.fetcher.artist(name, self._artwork_arrived)
        return self._keep(artwork.photo(path, size, P.surface, round_=True))

    def _keep(self, image):
        # Tk shows an image only while Python holds a reference to it
        if image is not None:
            self._images.append(image)
        return image

    def refresh(self):
        self._refresh_pending = False
        self._images = []
        for period, button in self.period_buttons.items():
            button.configure(style="NavSelected.TButton" if period == self.period else "Nav.TButton")
        has_steps = self.period != "all"
        self.previous_button.configure(state="normal" if has_steps else "disabled")
        self.next_button.configure(state="normal" if has_steps and self.offset > 0 else "disabled")

        start, end = listening.period_range(self.period, self.offset)
        if self.period == "all":
            start = listening.first_play() or start
        self.title_label.configure(text=period_title(self.period, start, end))
        self._fill_tiles(start, end)

        tracks = listening.top_tracks(start, end, TOP_COUNT)
        artists = listening.top_artists(start, end, TOP_COUNT)
        track_change = self._rank_changes(start, end, "track_key")
        artist_change = self._rank_changes(start, end, "artist_key")
        if tracks:
            top = tracks[0]
            self.track_hero.show(top["name"], top["artist"],
                                 summary_text(plays_text(top["plays"]), minutes=top["minutes"]),
                                 self._cover(top, Hero.IMAGE_SIZE, 10), track_change(top["key"], 1, long=True))
        else:
            self.track_hero.show_empty(t("stats.empty"))
        if artists:
            top = artists[0]
            self.artist_hero.show(top["name"], tracks_text(top["tracks"]),
                                  summary_text(plays_text(top["plays"]), minutes=top["minutes"]),
                                  self._artist_photo(top["name"], Hero.IMAGE_SIZE),
                                  artist_change(top["key"], 1, long=True))
        else:
            self.artist_hero.show_empty(t("stats.empty"))

        size = BarList.IMAGE_SIZE
        self.top_tracks.set_rows([{
            "title": r["name"], "subtitle": r["artist"], "value": r["plays"], "value_text": number(r["plays"]),
            "tooltip": f"{r['name']}\n{r['artist']}\n" + summary_text(plays_text(r["plays"]), minutes=r["minutes"])
                       + change_tip(track_change, r["key"], rank),
            "image": self._cover(r, size, 4), "change": track_change(r["key"], rank),
        } for rank, r in enumerate(tracks[1:], start=2)])
        self.top_artists.set_rows([{
            "title": r["name"], "subtitle": tracks_text(r["tracks"]),
            "value": r["plays"], "value_text": number(r["plays"]),
            "tooltip": f"{r['name']}\n" + summary_text(
                plays_text(r["plays"]), tracks_text(r["tracks"]), minutes=r["minutes"])
                       + change_tip(artist_change, r["key"], rank),
            "image": self._artist_photo(r["name"], size), "change": artist_change(r["key"], rank),
        } for rank, r in enumerate(artists[1:], start=2)])
        self._fill_discoveries(start, end)
        self._fill_timeline(start, end)
        hours = listening.hours(start, end)
        self.hours.set_buckets([{
            "label": f"{hour:02d}", "value": count,
            "tooltip": f"{hour:02d}:00 – {(hour + 1) % 24:02d}:00\n{plays_text(count)}",
        } for hour, count in enumerate(hours)])

    def _rank_changes(self, start, end, column: str):
        """Returns change(key, rank) → (text, color) comparing with the whole previous period, or None."""
        if self.period == "all":
            return lambda key, rank, long=False: None
        previous = listening.ranks(*listening.period_range(self.period, self.offset + 1), column)

        def change(key, rank, long=False):
            before = previous.get(key)
            if before is None:
                return t("stats.change.new_long" if long else "stats.change.new"), P.playable
            if before == rank:
                return (t("stats.change.same") if long else "="), P.muted
            arrow = "▲" if before > rank else "▼"
            if long:
                text = t("stats.change.moved", arrow=arrow, count=abs(before - rank), rank=before)
            else:
                text = f"{arrow}{abs(before - rank)}"
            return text, P.added if before > rank else P.removed
        return change

    def _fill_discoveries(self, start, end):
        # Everything is new over all time, so the section only makes sense for a week, month or year
        if self.period == "all":
            self.discoveries.pack_forget()
            return
        self.discoveries.pack(fill="x", pady=(24, 0), before=self.charts)
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
        self.discovery_summary.configure(text=text)

        size = BarList.IMAGE_SIZE
        self.new_tracks.set_rows([{
            "title": r["name"], "subtitle": r["artist"], "value": r["plays"], "value_text": number(r["plays"]),
            "tooltip": f"{r['name']}\n{r['artist']}\n" + summary_text(plays_text(r["plays"]), minutes=r["minutes"])
                       + "\n" + t("stats.discoveries.first_heard", date=format_date(r["first_played"])),
            "image": self._cover(r, size, 4),
        } for r in tracks[:DISCOVERY_COUNT]])
        self.new_artists.set_rows([{
            "title": r["name"], "subtitle": tracks_text(r["tracks"]), "value": r["plays"],
            "value_text": number(r["plays"]),
            "tooltip": f"{r['name']}\n" + summary_text(plays_text(r["plays"]), tracks_text(r["tracks"]),
                                                       minutes=r["minutes"])
                       + "\n" + t("stats.discoveries.first_heard", date=format_date(r["first_played"])),
            "image": self._artist_photo(r["name"], size),
        } for r in artists[:DISCOVERY_COUNT]])

    def _fill_tiles(self, start, end):
        current = listening.summary(start, end)
        previous = None
        if self.period != "all":
            previous_start, previous_end = listening.period_range(self.period, self.offset + 1)
            if self.offset == 0:
                # The current period is still running, so compare with the same stretch of the previous one
                previous_end = min(previous_end, previous_start + (datetime.now().astimezone() - start))
            previous = listening.summary(previous_start, previous_end)
        for name, key, text in (("plays", "plays", number), ("time", "minutes", duration_text),
                                ("tracks", "tracks", number), ("artists", "artists", number)):
            value_label, delta_label = self.tiles[name]
            value_label.configure(text=text(current[key]))
            delta = ""
            if previous and previous[key]:
                change = round((current[key] - previous[key]) * 100 / previous[key])
                arrow = "▲" if change > 0 else "▼" if change < 0 else "="
                delta = f"{arrow} {t('stats.percent', value=abs(change))}  {t(f'stats.vs.{self.period}')}"
            delta_label.configure(text=delta)

    def _fill_timeline(self, start, end):
        if self.period in ("week", "month"):
            counts = listening.timeline(start, end, "day")
            days = [start + timedelta(days=i) for i in range((end - start).days)]
            buckets = [{
                "label": t("stats.weekdays").split(",")[day.weekday()] if self.period == "week" else str(day.day),
                "value": counts.get(day.strftime("%Y-%m-%d"), 0),
                "tooltip": f"{day.day} {month_name(day.month)}\n"
                           f"{plays_text(counts.get(day.strftime('%Y-%m-%d'), 0))}",
            } for day in days]
            title = t("stats.per_day")
        else:
            counts = listening.timeline(start, end, "month")
            months = []
            year, month = start.year, start.month
            last = end - timedelta(days=1)
            while (year, month) <= (last.year, last.month):
                months.append((year, month))
                year, month = (year + 1, 1) if month == 12 else (year, month + 1)
            if len(months) > 36:
                totals: dict[int, int] = {}
                for (year, month) in months:
                    totals[year] = totals.get(year, 0) + counts.get(f"{year}-{month:02d}", 0)
                buckets = [{"label": str(year), "value": value, "tooltip": f"{year}\n{plays_text(value)}"}
                           for year, value in totals.items()]
                title = t("stats.per_year")
            else:
                buckets = []
                for year, month in months:
                    value = counts.get(f"{year}-{month:02d}", 0)
                    label = month_name(month, True)
                    if self.period == "all":
                        label += f" {year % 100:02d}"
                    buckets.append({"label": label, "value": value,
                                    "tooltip": f"{month_name(month)} {year}\n{plays_text(value)}"})
                title = t("stats.per_month")
        self.timeline_card.title.configure(text=title)
        self.timeline.set_buckets(buckets)
