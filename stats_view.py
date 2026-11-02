"""
Statistics tab of the Listening section: most played tracks and artists of a week, month or
year, counted from the plays recorded in listening.db.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from tkinter import ttk

import listening
from charts import BarList, ColumnChart
from i18n import number, t

TOP_COUNT = 10


def plays_text(count: int) -> str:
    return t("stats.plays_one") if count == 1 else t("stats.plays", count=number(count))


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


class StatsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=16, style="Card.TFrame")
        self.period = "week"
        self.offset = 0
        self._build()

    def _build(self):
        toolbar = ttk.Frame(self, style="Card.TFrame")
        toolbar.pack(fill="x")
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

        tiles = ttk.Frame(self, style="Card.TFrame")
        tiles.pack(fill="x", pady=(14, 0))
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

        empty = t("stats.empty")
        top = ttk.Frame(self, style="Card.TFrame")
        top.pack(fill="both", expand=True, pady=(16, 0))
        self.top_tracks = BarList(self._card(top, t("stats.top_tracks"), 0), 290, empty)
        self.top_artists = BarList(self._card(top, t("stats.top_artists"), 1), 290, empty)

        bottom = ttk.Frame(self, style="Card.TFrame")
        bottom.pack(fill="both", expand=True, pady=(16, 0))
        self.timeline_card = self._card(bottom, "", 0, weight=3)
        self.timeline = ColumnChart(self.timeline_card, 140, empty)
        self.hours = ColumnChart(self._card(bottom, t("stats.hours"), 1, weight=2), 140, empty)
        for chart in (self.top_tracks, self.top_artists, self.timeline, self.hours):
            chart.pack(fill="both", expand=True)

    def _card(self, parent, title: str, column: int, weight: int = 1) -> ttk.Frame:
        parent.columnconfigure(column, weight=weight, uniform="card")
        parent.rowconfigure(0, weight=1)
        card = ttk.Frame(parent, style="Card.TFrame")
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 24, 0))
        card.title = ttk.Label(card, text=title, style="Section.TLabel")
        card.title.pack(anchor="w", pady=(0, 6))
        return card

    def select_period(self, period: str):
        self.period, self.offset = period, 0
        self.refresh()

    def move(self, step: int):
        self.offset = max(0, self.offset + step)
        self.refresh()

    def refresh(self):
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

        self.top_tracks.set_rows([{
            "title": r["name"], "subtitle": r["artist"], "value": r["plays"], "value_text": number(r["plays"]),
            "tooltip": f"{r['name']}\n{r['artist']}\n{plays_text(r['plays'])}  ·  {duration_text(r['minutes'])}",
        } for r in listening.top_tracks(start, end, TOP_COUNT)])
        self.top_artists.set_rows([{
            "title": r["name"], "subtitle": "", "value": r["plays"], "value_text": number(r["plays"]),
            "tooltip": f"{r['name']}\n{plays_text(r['plays'])}  ·  {t('stats.different_tracks', count=r['tracks'])}"
                       f"  ·  {duration_text(r['minutes'])}",
        } for r in listening.top_artists(start, end, TOP_COUNT)])
        self._fill_timeline(start, end)
        hours = listening.hours(start, end)
        self.hours.set_buckets([{
            "label": f"{hour:02d}", "value": count,
            "tooltip": f"{hour:02d}:00 – {(hour + 1) % 24:02d}:00\n{plays_text(count)}",
        } for hour, count in enumerate(hours)])

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
