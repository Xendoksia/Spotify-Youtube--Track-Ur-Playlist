"""
Detail page of one track or artist, opened by clicking it in the statistics: all time totals,
plays over time and, for an artist, their most played tracks. It opens inside the statistics tab,
with back / forward buttons between the pages visited and a close button back to the statistics.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from tkinter import ttk

import artist_info
import artwork
import listening
from charts import BarList, ColumnChart, count_up
from i18n import number, t
from stats_view import Hero, ScrollFrame, duration_text, month_name, plays_text, summary_text, tracks_text
from theme import P, icon, px

ARTIST_TRACKS = 15
# Up to this many days of history the chart shows days, after that months
DAILY_LIMIT = 62
MIN_DAYS = 14


def date_text(iso: str) -> str:
    moment = listening.from_utc(iso).astimezone()
    return f"{moment.day} {month_name(moment.month)} {moment.year}"


class DetailView(ttk.Frame):
    """The navigation bar and the detail page on display, with the history of pages visited."""

    def __init__(self, parent, on_close):
        super().__init__(parent, style="Card.TFrame")
        self.on_close = on_close
        self.history: list[tuple[str, str]] = []
        self.index = -1
        self.page = None
        bar = ttk.Frame(self, style="Card.TFrame")
        bar.pack(fill="x", padx=px(16), pady=(px(16), 0))
        self.back_button = ttk.Button(bar, text=icon("back"), style="Icon.TButton", command=lambda: self.step(-1))
        self.back_button.pack(side="left")
        self.forward_button = ttk.Button(bar, text=icon("forward"), style="Icon.TButton", command=lambda: self.step(1))
        self.forward_button.pack(side="left", padx=(px(4), 0))
        self.title_label = ttk.Label(bar, style="Period.TLabel")
        self.title_label.pack(side="left", padx=px(12))
        ttk.Button(bar, text=icon("close"), style="Icon.TButton", command=self.close).pack(side="right")

    def open(self, column: str, key: str):
        """Show a page, dropping the pages that were ahead of the current one."""
        del self.history[self.index + 1:]
        self.history.append((column, key))
        self.index = len(self.history) - 1
        self._show()

    def step(self, direction: int):
        # Back from the first page returns to the statistics
        if self.index + direction < 0:
            self.close()
        elif self.index + direction < len(self.history):
            self.index += direction
            self._show()

    def close(self):
        self.history, self.index = [], -1
        if self.page is not None:
            self.page.destroy()
            self.page = None
        self.on_close()

    def refresh(self):
        if self.page is not None:
            self.page.refresh()

    def _show(self):
        if self.page is not None:
            self.page.destroy()
        column, key = self.history[self.index]
        self.page = DetailPage(self, column, key, self.open)
        self.page.pack(fill="both", expand=True)
        self.forward_button.configure(state="normal" if self.index < len(self.history) - 1 else "disabled")
        self.page.refresh()


class DetailPage(ttk.Frame):
    def __init__(self, parent: DetailView, column: str, key: str, open_page):
        super().__init__(parent, style="Card.TFrame")
        self.view = parent
        self.column, self.key = column, key
        self.open_page = open_page
        self.is_artist = column == "artist_key"
        self.fetcher = artwork.Fetcher(self)
        self._images = []
        self._refresh_pending = False
        self._build()

    def _build(self):
        page = ScrollFrame(self)
        page.pack(fill="both", expand=True, pady=(px(12), 0))
        content = page.content

        caption = t("detail.artist" if self.is_artist else "detail.track")
        self.hero = Hero(content, caption, round_image=self.is_artist)
        self.hero.pack(fill="x")

        tiles = ttk.Frame(content, style="Card.TFrame")
        tiles.pack(fill="x", pady=(px(16), 0))
        self.tiles = {}
        for index, name in enumerate(("plays", "time", "first", "last")):
            tiles.columnconfigure(index, weight=1, uniform="tile")
            tile = ttk.Frame(tiles, padding=(px(14), px(10)), style="Tile.TFrame")
            tile.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else px(10), 0))
            ttk.Label(tile, text=t(f"detail.tile.{name}"), style="CardMuted.TLabel").pack(anchor="w")
            # Dates are longer than numbers, so they get a smaller font
            value = ttk.Label(tile, style="TileValue.TLabel" if name in ("plays", "time") else "Period.TLabel")
            value.pack(anchor="w", pady=(px(4), 0))
            self.tiles[name] = value

        self.timeline_title = ttk.Label(content, style="Section.TLabel")
        self.timeline_title.pack(anchor="w", pady=(px(24), px(8)))
        self.timeline = ColumnChart(content, 170, t("stats.empty"))
        self.timeline.pack(fill="x")

        if self.is_artist:
            ttk.Label(content, text=t("detail.artist_tracks"), style="Section.TLabel"
                      ).pack(anchor="w", pady=(px(24), px(8)))
            self.tracks = BarList(content, t("stats.empty"), 1)
            self.tracks.pack(fill="x")

    def _artwork_arrived(self):
        if not self._refresh_pending:
            self._refresh_pending = True
            self.after(400, self.refresh)

    def _keep(self, image):
        # Tk shows an image only while Python holds a reference to it
        if image is not None:
            self._images.append(image)
        return image

    def _cover(self, row: dict, size: int, radius: int):
        path = self.fetcher.cover(row["artist"], row["album"] or "", row["name"], self._artwork_arrived)
        return self._keep(artwork.photo(path, px(size), P.surface, radius=px(radius)))

    def _artist_photo(self, name: str, size: int):
        path = self.fetcher.artist(name, self._artwork_arrived)
        return self._keep(artwork.photo(path, px(size), P.surface, round_=True))

    def refresh(self):
        if not self.winfo_exists():
            return
        self._refresh_pending = False
        self._images = []
        info = listening.detail(self.column, self.key)
        if not info:
            self.view.title_label.configure(text="")
            self.hero.show_empty(t("stats.empty"))
            return

        title = info["artist"] if self.is_artist else info["name"]
        self.view.title_label.configure(text=title)
        if self.is_artist:
            self.hero.show(title, tracks_text(info["tracks"]), summary_text(plays_text(info["plays"]),
                                                                            minutes=info["minutes"]),
                           self.fetcher.artist(title, self._artwork_arrived))
            facts = artist_info.request(title, self.key, self, self._artwork_arrived)
            self.hero.set_about(artist_info.describe(facts) if facts else "")
        else:
            subtitle = info["artist"] + (f"  ·  {info['album']}" if info["album"] else "")
            self.hero.show(title, subtitle, summary_text(plays_text(info["plays"]), minutes=info["minutes"]),
                           self.fetcher.cover(info["artist"], info["album"] or "", info["name"],
                                              self._artwork_arrived))
            # The artist line leads to the artist's own page
            self.hero.on_subtitle_click(lambda: self.open_page("artist_key", info["artist_key"]))

        count_up(self.tiles["plays"], info["plays"], number)
        count_up(self.tiles["time"], info["minutes"], lambda minutes: duration_text(minutes) if minutes else "—")
        self.tiles["first"].configure(text=date_text(info["first_played"]))
        self.tiles["last"].configure(text=date_text(info["last_played"]))
        self._fill_timeline(info)

        if self.is_artist:
            start, end = listening.period_range("all")
            rows = listening.top_tracks(start, end, ARTIST_TRACKS, artist_key=self.key)
            self.tracks.configure(height=px(BarList.ROW_HEIGHT * max(1, len(rows))))
            self.tracks.set_rows([{
                "title": r["name"], "subtitle": r["album"] or "", "value": r["plays"],
                "value_text": number(r["plays"]),
                "tooltip": f"{r['name']}\n" + summary_text(plays_text(r["plays"]), minutes=r["minutes"]),
                "image": self._cover(r, BarList.IMAGE_SIZE, 4),
                "on_click": lambda key=r["key"]: self.open_page("track_key", key),
            } for r in rows])

    def _fill_timeline(self, info: dict):
        first = listening.from_utc(info["first_played"]).astimezone()
        today = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        # At least two weeks, so a track heard only recently does not fill the chart with two huge columns
        start = min(first.replace(hour=0, minute=0, second=0, microsecond=0), today - timedelta(days=MIN_DAYS - 1))
        end = today + timedelta(days=1)
        if (end - start).days <= DAILY_LIMIT:
            counts = listening.timeline(start, end, "day", self.column, self.key)
            days = [start + timedelta(days=i) for i in range((end - start).days)]
            buckets = [{
                "label": str(day.day), "value": counts.get(day.strftime("%Y-%m-%d"), 0),
                "tooltip": f"{day.day} {month_name(day.month)}\n{plays_text(counts.get(day.strftime('%Y-%m-%d'), 0))}",
            } for day in days]
            self.timeline_title.configure(text=t("stats.per_day"))
        else:
            counts = listening.timeline(start, end, "month", self.column, self.key)
            buckets = []
            year, month = start.year, start.month
            while (year, month) <= (today.year, today.month):
                value = counts.get(f"{year}-{month:02d}", 0)
                buckets.append({"label": f"{month_name(month, True)} {year % 100:02d}", "value": value,
                                "tooltip": f"{month_name(month)} {year}\n{plays_text(value)}"})
                year, month = (year + 1, 1) if month == 12 else (year, month + 1)
            self.timeline_title.configure(text=t("stats.per_month"))
        self.timeline.set_buckets(buckets)
