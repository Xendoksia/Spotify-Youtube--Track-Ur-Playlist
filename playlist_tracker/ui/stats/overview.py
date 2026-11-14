"""
The statistics overview of a week, month, year or all time: totals compared with the previous period, the
number one track and artist, the top lists with their moves, plays over time and by hour, and the cards of
sections.py. Everything is counted from the plays recorded in listening.db.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk

from playlist_tracker.core.i18n import number, t
from playlist_tracker.music import listening
from playlist_tracker.ui.charts import BarList, ColumnChart, count_up
from playlist_tracker.ui.stats import wrapped
from playlist_tracker.ui.stats.sections import Collage, Discoveries, Diversity, Genres, GenreShift, Milestones
from playlist_tracker.ui.stats.text import (duration_text, hour_buckets, month_name, period_title, plays_text,
                                            summary_text, tracks_text)
from playlist_tracker.ui.stats.widgets import Hero, Pictures, ScrollFrame, card, card_row
from playlist_tracker.ui.theme import TYPE, P, icon, px

TOP_COUNT = 10


def change_tip(change, key, rank) -> str:
    """The rank change written out, as an extra tooltip line."""
    result = change(key, rank, long=True)
    return f"\n{result[0]}" if result else ""


class Overview(ttk.Frame):
    def __init__(self, parent, open_detail, open_wrapped):
        """open_detail(column, key) shows the page of a track, artist or album; open_wrapped(summary) a
        monthly or yearly summary from the bell."""
        super().__init__(parent, style="Card.TFrame")
        self.open_detail = open_detail
        self.period = "week"
        self.offset = 0
        self.pictures = Pictures(self, self.refresh)
        self._build(open_wrapped)

    def opener(self, column: str, key: str):
        return lambda: self.open_detail(column, key)

    # Building

    def _build(self, open_wrapped):
        toolbar = ttk.Frame(self, style="Card.TFrame")
        toolbar.pack(fill="x", padx=px(16), pady=(px(16), 0))
        switcher = ttk.Frame(toolbar, padding=px(4), style="Nav.TFrame")
        switcher.pack(side="left")
        self.period_buttons = {}
        for period in listening.PERIODS:
            button = ttk.Button(switcher, text=t(f"stats.period.{period}"), style="Nav.TButton",
                                command=lambda period=period: self.select_period(period))
            button.pack(side="left")
            self.period_buttons[period] = button
        self.previous_button = ttk.Button(toolbar, text=icon("back"), style="Icon.TButton", command=lambda: self.move(1))
        self.previous_button.pack(side="left", padx=(px(16), 0))
        self.next_button = ttk.Button(toolbar, text=icon("forward"), style="Icon.TButton", command=lambda: self.move(-1))
        self.next_button.pack(side="left", padx=(px(4), 0))
        self.title_label = ttk.Label(toolbar, style="Period.TLabel")
        self.title_label.pack(side="left", padx=px(12))
        # The summaries waiting to be seen (wrapped.inbox), with their number beside the bell: the only way to
        # them besides their opening by itself, so that they stay something to look forward to
        self.open_wrapped = open_wrapped
        self.inbox_button = ttk.Button(toolbar, text=icon("bell"), style="Icon.TButton", command=self._show_inbox)
        self.inbox_button.pack(side="right")
        self.inbox_count = ttk.Label(toolbar, style="Card.TLabel", foreground=P.chart, font=TYPE["heading"])

        page = ScrollFrame(self)
        page.pack(fill="both", expand=True, pady=(px(12), 0))
        content = page.content

        tiles = ttk.Frame(content, style="Card.TFrame")
        tiles.pack(fill="x")
        self.tiles = {}
        for index, name in enumerate(("plays", "time", "tracks", "artists")):
            tiles.columnconfigure(index, weight=1, uniform="tile")
            tile = ttk.Frame(tiles, padding=(px(16), px(12)), style="Tile.TFrame")
            tile.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else px(12), 0))
            ttk.Label(tile, text=t(f"stats.tile.{name}"), style="CardMuted.TLabel").pack(anchor="w")
            value = ttk.Label(tile, style="TileValue.TLabel")
            value.pack(anchor="w")
            delta = ttk.Label(tile, style="CardMuted.TLabel", font=TYPE["small"])
            delta.pack(anchor="w")
            self.tiles[name] = (value, delta)

        heroes = ttk.Frame(content, style="Card.TFrame")
        heroes.pack(fill="x", pady=(px(16), 0))
        heroes.columnconfigure((0, 1), weight=1, uniform="hero")
        self.track_hero = Hero(heroes, t("stats.hero.track"), round_image=False)
        self.track_hero.grid(row=0, column=0, sticky="nsew")
        self.artist_hero = Hero(heroes, t("stats.hero.artist"), round_image=True)
        self.artist_hero.grid(row=0, column=1, sticky="nsew", padx=(px(12), 0))

        empty = t("stats.empty")
        # Below the overview, every section is a bordered card with an icon, two to a row where they fit
        lists = card_row(content)
        self.top_tracks = BarList(card(lists, "tracks", t("stats.top_tracks"), 0), empty, TOP_COUNT - 1,
                                  first_rank=2)
        self.top_artists = BarList(card(lists, "artists", t("stats.top_artists"), 1), empty, TOP_COUNT - 1,
                                   round_images=True, first_rank=2)

        charts = card_row(content)
        self.timeline_card = card(charts, "calendar", "", 0, weight=3)
        self.timeline = ColumnChart(self.timeline_card, 170, empty)
        self.hours = ColumnChart(card(charts, "clock", t("stats.hours"), 1, weight=2), 170, empty)
        for chart in (self.top_tracks, self.top_artists, self.timeline, self.hours):
            chart.pack(fill="x")

        self.discoveries = Discoveries(content, self)
        trends = card_row(content)
        self.diversity = Diversity(trends, 0, self)
        self.genre_shift = GenreShift(trends, 1)
        self.milestones = Milestones(content, self)
        last = card_row(content)
        self.genres = Genres(last, 0)
        self.genres.on_change = lambda: self.genre_shift.fill(self.period, *self._range)
        self.collage = Collage(last, 1, self)

    # Period

    def select_period(self, period: str):
        self.period, self.offset = period, 0
        self.refresh()

    def update_inbox(self):
        self.inbox = wrapped.inbox()
        if self.inbox:
            self.inbox_count.configure(text=number(len(self.inbox)))
            self.inbox_count.pack(side="right", after=self.inbox_button, padx=(0, px(4)))
        else:
            self.inbox_count.pack_forget()

    def _show_inbox(self):
        menu = tk.Menu(self, tearoff=0, background=P.surface, foreground=P.text, activebackground=P.hover,
                       activeforeground=P.text, disabledforeground=P.muted, font=TYPE["body"])
        menu.add_command(label=t("inbox.title"), state="disabled")
        menu.add_separator()
        for summary in self.inbox:
            name = period_title("year" if wrapped.is_year(*summary) else "month", *summary)
            menu.add_command(label=t("wrapped.inbox.item", name=name),
                             command=lambda summary=summary: self.open_wrapped(summary))
        if not self.inbox:
            menu.add_command(label=t("inbox.empty"), state="disabled")
        button = self.inbox_button
        menu.tk_popup(button.winfo_rootx(), button.winfo_rooty() + button.winfo_height())

    def move(self, step: int):
        self.offset = max(0, self.offset + step)
        self.refresh()

    # Data

    def refresh(self):
        self.pictures.clear()
        self.update_inbox()
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
        self._fill_top(start, end)
        self.discoveries.fill(self.period, start, end)
        self.diversity.fill(self.period, self.offset, start, end)
        self._range = (start, end)
        self.milestones.fill(self.period, start, end)
        self.genres.fill(start, end)
        # After the genres card, which asks for the genres it needs
        self.genre_shift.fill(self.period, start, end)
        self.collage.fill(start, end)
        self._fill_timeline(start, end)
        self.hours.set_buckets(hour_buckets(listening.hours(start, end)))

    def _fill_top(self, start, end):
        tracks = listening.top_tracks(start, end, TOP_COUNT)
        artists = listening.top_artists(start, end, TOP_COUNT)
        track_change = self._rank_changes(start, end, "track_key")
        artist_change = self._rank_changes(start, end, "artist_key")
        if tracks:
            top = tracks[0]
            self.track_hero.on_click(self.opener("track_key", top["key"]))
            self.track_hero.show(top["name"], top["artist"],
                                 summary_text(plays_text(top["plays"]), minutes=top["minutes"]),
                                 self.pictures.cover_path(top["artist"], top["album"], top["name"]),
                                 track_change(top["key"], 1, long=True))
        else:
            self.track_hero.show_empty(t("stats.empty"))
        if artists:
            top = artists[0]
            self.artist_hero.on_click(self.opener("artist_key", top["key"]))
            self.artist_hero.show(top["name"], tracks_text(top["tracks"]),
                                  summary_text(plays_text(top["plays"]), minutes=top["minutes"]),
                                  self.pictures.artist_path(top["name"]),
                                  artist_change(top["key"], 1, long=True))
        else:
            self.artist_hero.show_empty(t("stats.empty"))

        size = BarList.IMAGE_SIZE
        self.top_tracks.set_rows([{
            "title": r["name"], "subtitle": r["artist"], "value": r["plays"], "value_text": number(r["plays"]),
            "tooltip": f"{r['name']}\n{r['artist']}\n" + summary_text(plays_text(r["plays"]), minutes=r["minutes"])
                       + change_tip(track_change, r["key"], rank),
            "image": self.pictures.cover(r, size, 4), "change": track_change(r["key"], rank),
            "on_click": self.opener("track_key", r["key"]),
        } for rank, r in enumerate(tracks[1:], start=2)])
        self.top_artists.set_rows([{
            "title": r["name"], "subtitle": tracks_text(r["tracks"]),
            "value": r["plays"], "value_text": number(r["plays"]),
            "tooltip": f"{r['name']}\n" + summary_text(
                plays_text(r["plays"]), tracks_text(r["tracks"]), minutes=r["minutes"])
                       + change_tip(artist_change, r["key"], rank),
            "image": self.pictures.artist_photo(r["name"], size), "change": artist_change(r["key"], rank),
            "on_click": self.opener("artist_key", r["key"]),
        } for rank, r in enumerate(artists[1:], start=2)])

    def _rank_changes(self, start, end, column: str):
        """Returns change(key, rank) → (text, color) comparing with the whole previous period, or None."""
        if self.period == "all":
            return lambda key, rank, long=False: None
        previous_start, previous_end = listening.period_range(self.period, self.offset + 1)
        previous = listening.ranks(previous_start, previous_end, column)
        known = listening.heard_before(start, column)
        # Songs heard before recording began look new too, so new and back are only told apart
        # once the whole previous period was recorded
        first = listening.first_play()
        recorded_before = first is not None and first <= previous_start

        def change(key, rank, long=False):
            before = previous.get(key)
            if before is None:
                if not recorded_before:
                    return None
                # New means heard for the first time ever, like the discoveries; one heard before
                # but not in the previous period is back
                if key in known:
                    return t("stats.change.back_long" if long else "stats.change.back"), P.muted
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
            count_up(value_label, current[key], text)
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
