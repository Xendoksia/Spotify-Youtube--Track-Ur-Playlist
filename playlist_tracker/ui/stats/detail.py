"""
Detail page of one track, artist or album, opened by clicking it in the statistics (see DetailPage).
It opens inside the statistics tab, with back / forward buttons between the pages visited and a close
button back to the statistics.
"""

from __future__ import annotations

import threading
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk

from playlist_tracker.core.i18n import number, t
from playlist_tracker.core.text import format_length
from playlist_tracker.music import artist_info, artwork, listening
from playlist_tracker.ui.charts import Animation, BarList, ColumnChart, count_up, rounded_rect
from playlist_tracker.ui.stats.text import (date_text, duration_text, hour_buckets, month_name, plays_text,
                                            summary_text, tracks_text)
from playlist_tracker.ui.stats.widgets import Hero, Pictures, ScrollFrame
from playlist_tracker.ui.theme import TYPE, P, icon, px

ARTIST_TRACKS = 15
# Plays of tracks of an album fetched at most (the album's own tracks come from Deezer)
ALBUM_TRACKS = 100
# The album's cover is larger on its own page than a track's; the album card of a track page has a small one
ALBUM_IMAGE = 180
ALBUM_CARD_IMAGE = 72
# Up to this many days of history the chart shows days, after that months
DAILY_LIMIT = 62
MIN_DAYS = 14


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
    """The page of one track, artist or album. All three show totals and plays over time; a track adds
    its album and the hours it is played at, an artist its most played tracks, and an album is built
    around its track list: how much of it was heard, the favorite and every track with its plays."""

    def __init__(self, parent: DetailView, column: str, key: str, open_page):
        super().__init__(parent, style="Card.TFrame")
        self.view = parent
        self.column, self.key = column, key
        self.open_page = open_page
        self.is_artist = column == "artist_key"
        self.is_album = column == listening.ALBUM
        self.is_track = not self.is_artist and not self.is_album
        self._looked_up: set[tuple[str, str]] = set()
        self.pictures = Pictures(self, self.refresh)
        self._build()

    # Building

    def _build(self):
        page = ScrollFrame(self)
        page.pack(fill="both", expand=True, pady=(px(12), 0))
        content = page.content

        caption = t("detail.artist" if self.is_artist else "detail.album" if self.is_album else "detail.track")
        self.hero = Hero(content, caption, round_image=self.is_artist,
                         image_size=ALBUM_IMAGE if self.is_album else Hero.IMAGE_SIZE)
        self.hero.pack(fill="x")

        names = ("plays", "time", "heard", "favorite") if self.is_album else ("plays", "time", "first", "last")
        tiles = ttk.Frame(content, style="Card.TFrame")
        tiles.pack(fill="x", pady=(px(16), 0))
        self.tiles = {}
        for index, name in enumerate(names):
            tiles.columnconfigure(index, weight=1, uniform="tile")
            tile = ttk.Frame(tiles, padding=(px(16), px(12)), style="Tile.TFrame")
            tile.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else px(12), 0))
            ttk.Label(tile, text=t(f"detail.tile.{name}"), style="CardMuted.TLabel").pack(anchor="w")
            # Dates and names are longer than numbers, so they get a smaller font
            value = ttk.Label(tile, style="TileValue.TLabel" if name in ("plays", "time", "heard") else "Period.TLabel",
                              wraplength=px(200))
            value.pack(anchor="w", pady=(px(4), 0))
            self.tiles[name] = value

        if self.is_album:
            self._build_album(content)
        elif self.is_track:
            self._build_track(content)
        else:
            self._build_timeline(content)
            self.tracks_title = ttk.Label(content, text=t("detail.artist_tracks"), style="Section.TLabel")
            self.tracks_title.pack(anchor="w", pady=(px(24), px(8)))
            self.tracks = BarList(content, t("stats.empty"), 1)
            self.tracks.pack(fill="x")

    def _build_timeline(self, parent):
        self.timeline_title = ttk.Label(parent, style="Section.TLabel")
        self.timeline_title.pack(anchor="w", pady=(px(24), px(8)))
        self.timeline = ColumnChart(parent, 170, t("stats.empty"))
        self.timeline.pack(fill="x")

    def _build_album(self, content):
        # How much of the album was heard, as a bar filling up
        progress = ttk.Frame(content, padding=(px(16), px(12)), style="Tile.TFrame")
        progress.pack(fill="x", pady=(px(16), 0))
        self.progress_label = ttk.Label(progress, style="Card.TLabel", font=TYPE["heading"])
        self.progress_label.pack(anchor="w")
        self.progress_bar = tk.Canvas(progress, height=px(10), background=P.surface, highlightthickness=0)
        self.progress_bar.pack(fill="x", pady=(px(8), 0))
        self.progress_bar.bind("<Configure>", lambda e: self._draw_progress(self._progress_shown))
        self._progress_shown = 0.0

        # The track list is what an album page is about, so it comes before the chart
        self.tracks_title = ttk.Label(content, text=t("detail.artist_tracks"), style="Section.TLabel")
        self.tracks_title.pack(anchor="w", pady=(px(24), px(8)))
        self.tracks = BarList(content, t("stats.empty"), 1, images=False)
        self.tracks.pack(fill="x")
        self._build_timeline(content)

    def _build_track(self, content):
        # The album the track is on, and the hours of the day it is played at, side by side
        row = ttk.Frame(content, style="Card.TFrame")
        row.pack(fill="x", pady=(px(16), 0))
        row.columnconfigure(0, weight=2, uniform="track")
        row.columnconfigure(1, weight=3, uniform="track")
        self.album_card = ttk.Frame(row, padding=px(16), style="Tile.TFrame", cursor="hand2")
        self.album_card.grid(row=0, column=0, sticky="nsew")
        ttk.Label(self.album_card, text=t("detail.album").upper(), style="Caption.TLabel").pack(anchor="w")
        inner = ttk.Frame(self.album_card, style="Card.TFrame")
        inner.pack(fill="x", pady=(px(8), 0))
        self.album_cover = ttk.Label(inner, style="Card.TLabel")
        self.album_cover.pack(side="left")
        text = ttk.Frame(inner, style="Card.TFrame")
        text.pack(side="left", fill="x", expand=True, padx=(px(12), 0))
        self.album_name = ttk.Label(text, style="Card.TLabel", font=TYPE["heading"], wraplength=px(220))
        self.album_name.pack(anchor="w")
        self.album_heard = ttk.Label(text, style="CardMuted.TLabel", wraplength=px(220))
        self.album_heard.pack(anchor="w", pady=(px(4), 0))
        self.album_go = ttk.Label(text, text=t("detail.album_open"), style="Card.TLabel", foreground=P.added)
        self.album_go.pack(anchor="w", pady=(px(8), 0))
        self._album_action = None
        for widget in (self.album_card, inner, self.album_cover, text, self.album_name, self.album_heard,
                       self.album_go):
            widget.bind("<Button-1>", lambda e: self._album_action and self._album_action())

        hours = ttk.Frame(row, padding=px(16), style="Tile.TFrame")
        hours.grid(row=0, column=1, sticky="nsew", padx=(px(16), 0))
        ttk.Label(hours, text=t("detail.track_hours"), style="Section.TLabel").pack(anchor="w", pady=(0, px(8)))
        self.hours = ColumnChart(hours, 120, t("stats.empty"))
        self.hours.pack(fill="x")
        self._build_timeline(content)

    # Data

    def _tracklist(self, artist: str, album: str) -> list[dict] | None:
        """The album's tracks from Deezer, looked up in the background the first time."""
        tracklist = artwork.cached_tracklist(artist, album)
        if tracklist is None and (artist, album) not in self._looked_up:
            self._looked_up.add((artist, album))

            def look_up():
                try:
                    artwork.fetch_tracklist(artist, album)
                except Exception:  # offline: shown without the album's own track list
                    return
                self.after(0, self.pictures.arrived)
            threading.Thread(target=look_up, name="tracklist", daemon=True).start()
        return tracklist

    def refresh(self):
        if not self.winfo_exists():
            return
        self.pictures.clear()
        info = listening.detail(self.column, self.key)
        if not info:
            self.view.title_label.configure(text="")
            self.hero.show_empty(t("stats.empty"))
            return

        title = info["artist"] if self.is_artist else info["album"] if self.is_album else info["name"]
        self.view.title_label.configure(text=title)
        summary = summary_text(plays_text(info["plays"]), minutes=info["minutes"])
        if self.is_artist:
            self.hero.show(title, tracks_text(info["tracks"]), summary, self.pictures.artist_path(title))
            facts = artist_info.request(title, self.key, self, self.pictures.arrived)
            self.hero.set_about(artist_info.describe(facts) if facts else "")
        else:
            self.hero.show(title, info["artist"], summary,
                           self.pictures.cover_path(info["artist"], info["album"], info["name"]))
            # The artist line leads to the artist's own page
            self.hero.on_subtitle_click(lambda: self.open_page("artist_key", info["artist_key"]))

        count_up(self.tiles["plays"], info["plays"], number)
        count_up(self.tiles["time"], info["minutes"], lambda minutes: duration_text(minutes) if minutes else "—")
        if not self.is_album:
            self.tiles["first"].configure(text=date_text(info["first_played"]))
            self.tiles["last"].configure(text=date_text(info["last_played"]))
        self._fill_timeline(info)

        if self.is_album:
            self._fill_album(info)
        elif self.is_track:
            self._fill_track(info)
        else:
            start, end = listening.period_range("all")
            rows = listening.top_tracks(start, end, ARTIST_TRACKS, artist_key=self.key)
            self.tracks.configure(height=px(BarList.ROW_HEIGHT * max(1, len(rows))))
            self.tracks.set_rows([{
                "title": r["name"], "subtitle": r["album"] or "", "value": r["plays"],
                "value_text": number(r["plays"]),
                "tooltip": f"{r['name']}\n" + summary_text(plays_text(r["plays"]), minutes=r["minutes"]),
                "image": self.pictures.cover(r, BarList.IMAGE_SIZE, 4),
                "on_click": lambda key=r["key"]: self.open_page("track_key", key),
            } for r in rows])

    def _album_rows(self, artist: str, album: str, album_key: str) -> tuple[list[dict], list[dict] | None]:
        """The album's tracks in album order with how often each was played (only the played ones while
        Deezer's track list is unknown), and that track list."""
        start, end = listening.period_range("all")
        played = listening.top_tracks(start, end, ALBUM_TRACKS, album=album_key)
        tracklist = self._tracklist(artist, album)
        rows, left = [], list(played)
        for track in tracklist or []:
            match = next((p for p in left if artwork.same_title(p["name"], track["title"])), None)
            length = format_length(track["ms"])
            if match:
                left.remove(match)
                rows.append(self._track_row(match, length))
            else:
                rows.append({"title": track["title"], "subtitle": length, "value": 0, "value_text": "—",
                             "tooltip": f"{track['title']}\n{t('detail.not_heard')}"})
        # Played tracks Deezer does not list (bonus tracks, other editions) come after
        rows += [self._track_row(track) for track in left]
        return rows, tracklist

    def _fill_album(self, info: dict):
        rows, tracklist = self._album_rows(info["artist"], info["album"], self.key)
        heard = sum(1 for row in rows if row["value"])
        favorite = max(rows, key=lambda row: row["value"]) if rows else None
        self.tiles["heard"].configure(text=f"{number(heard)} / {number(len(rows))}" if tracklist else number(heard))
        self.tiles["favorite"].configure(text=favorite["title"] if favorite and favorite["value"] else "—")
        if tracklist:
            length = sum(track["ms"] for track in tracklist) // 60000
            self.hero.set_about(t("detail.album_length", tracks=number(len(tracklist)), length=duration_text(length)))

        share = heard / len(rows) if tracklist and rows else 1.0
        self.progress_label.configure(text=t("detail.album_progress", percent=t("stats.percent", value=round(share * 100)))
                                      if tracklist else t("detail.album_progress_unknown"))
        Animation(self.progress_bar, lambda progress: self._draw_progress(share * progress)).start()

        self.tracks_title.configure(text=t("detail.album_tracks", heard=number(heard), total=number(len(rows)))
                                    if tracklist else t("detail.artist_tracks"))
        self.tracks.configure(height=px(BarList.ROW_HEIGHT * max(1, len(rows))))
        self.tracks.set_rows(rows)

    def _draw_progress(self, share: float):
        self._progress_shown = share
        bar = self.progress_bar
        width, height = bar.winfo_width(), int(bar.cget("height"))
        bar.delete("all")
        rounded_rect(bar, 0, 0, width, height, height / 2, fill=P.grid)
        if share > 0:
            rounded_rect(bar, 0, 0, max(height, width * share), height, height / 2, fill=P.chart)

    def _fill_track(self, info: dict):
        start, end = listening.period_range("all")
        hours = listening.hours(start, end, self.column, self.key)
        self.hours.set_buckets(hour_buckets(hours))
        if not info["album"]:
            self.album_card.grid_remove()
            return
        album_key = listening.album_key(info["artist_key"], info["album_lower"])
        self._album_action = lambda: self.open_page(listening.ALBUM, album_key)
        self.album_name.configure(text=info["album"])
        self.album_cover.configure(image=self.pictures.cover(info, ALBUM_CARD_IMAGE, 6))
        rows, tracklist = self._album_rows(info["artist"], info["album"], album_key)
        heard = sum(1 for row in rows if row["value"])
        self.album_heard.configure(text=t("detail.album_heard", heard=number(heard), total=number(len(rows)))
                                   if tracklist else t("detail.album_heard_unknown", heard=number(heard)))

    def _track_row(self, track: dict, length: str = "") -> dict:
        return {
            "title": track["name"], "subtitle": length, "value": track["plays"], "value_text": number(track["plays"]),
            "tooltip": f"{track['name']}\n" + summary_text(plays_text(track["plays"]), minutes=track["minutes"]),
            "on_click": lambda key=track["key"]: self.open_page("track_key", key),
        }

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
