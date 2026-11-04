"""
Parts of the "Recently played" tab: a card with the song Spotify is playing now, and the last plays grouped by
day, each one opening its song's page. The list has no covers: two hundred pictures made it slow.
"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime, timedelta

from playlist_tracker.core.i18n import t
from playlist_tracker.core.text import format_length
from playlist_tracker.music import artwork, listening
from playlist_tracker.ui.charts import Chart, fit_text, placeholder, rounded_rect
from playlist_tracker.ui.stats.text import duration_text, month_name, plays_text
from playlist_tracker.ui.theme import FONT, TYPE, P, px

ROW_HEIGHT = 48
HEADER_HEIGHT = 40
NOW_COVER = 56


def day_title(day, today) -> str:
    if day == today:
        return t("listening.today")
    if day == today - timedelta(days=1):
        return t("listening.yesterday")
    weekday = t("stats.weekdays").split(",")[day.weekday()]
    year = f" {day.year}" if day.year != today.year else ""
    return f"{day.day} {month_name(day.month)}{year}, {weekday}"


class RecentList(Chart):
    """The plays as rows under day headings: time, song, artist and album, and how long it was heard."""

    def __init__(self, parent, open_track):
        super().__init__(parent, ROW_HEIGHT, t("listening.empty"))
        self.open_track = open_track
        self.items: list[dict] = []

    def set_plays(self, plays: list[dict]):
        """plays: newest first."""
        today = datetime.now().astimezone().date()
        items, day = [], None
        for play in plays:
            moment = listening.from_utc(play["played_at"]).astimezone()
            if moment.date() != day:
                day = moment.date()
                # The whole day, also the plays older than the ones listed
                start = datetime(day.year, day.month, day.day).astimezone()
                totals = listening.summary(start, start + timedelta(days=1))
                summary = "  ·  ".join([plays_text(totals["plays"])]
                                       + ([duration_text(totals["minutes"])] if totals["minutes"] else []))
                items.append({"header": day_title(day, today), "summary": summary})
            subtitle = "  ·  ".join(part for part in (play["artist"], play["album"]) if part)
            items.append({
                "time": f"{moment:%H:%M}", "title": play["name"], "subtitle": subtitle,
                "length": format_length(play["ms_played"]),
                "tooltip": f"{play['name']}\n{subtitle}",
                "on_click": lambda key=play["track_key"]: self.open_track(key),
            })
        self.items = items
        height = sum(HEADER_HEIGHT if "header" in item else ROW_HEIGHT for item in items)
        self.configure(height=px(max(height, ROW_HEIGHT * 2)))
        self.redraw()

    def draw(self, width, height):
        if not self.items:
            return False
        y = 0
        time_width = self.small_font.measure("00:00") + px(16)
        text_left = time_width
        length_width = self.small_font.measure("00:00") + px(8)
        text_width = width - text_left - length_width - px(16)
        for index, item in enumerate(self.items):
            if "header" in item:
                top = y + (px(8) if index else 0)
                self.create_text(0, top + px(HEADER_HEIGHT) / 2, text=item["header"], anchor="w",
                                 fill=P.text, font=TYPE["heading"])
                self.create_text(width - px(4), top + px(HEADER_HEIGHT) / 2, text=item["summary"], anchor="e",
                                 fill=P.muted, font=self.small_font)
                y += px(HEADER_HEIGHT)
                continue
            row = px(ROW_HEIGHT)
            middle = y + row / 2
            background = rounded_rect(self, 0, y + 2, width, y + row - 2, px(6), fill="")
            self.create_text(px(8), middle, text=item["time"], anchor="w", fill=P.muted, font=self.small_font)
            self.create_text(text_left, middle - px(8), text=fit_text(item["title"], self.font, text_width),
                             anchor="w", fill=P.text, font=self.font)
            self.create_text(text_left, middle + px(9), text=fit_text(item["subtitle"], self.small_font, text_width),
                             anchor="w", fill=P.muted, font=self.small_font)
            self.create_text(width - px(8), middle, text=item["length"], anchor="e", fill=P.muted,
                             font=self.small_font)
            self.add_hit_area(0, y, width, y + row, item["tooltip"], [], item["on_click"], background)
            y += row
        return True


class NowPlaying(tk.Frame):
    """What Spotify plays now, with its cover; once the play is recorded, clicking it opens the song's page."""

    def __init__(self, parent, open_track):
        super().__init__(parent, background=P.surface, highlightthickness=1, highlightbackground=P.border)
        self.open_track = open_track
        self.fetcher = artwork.Fetcher(self)
        self._shown = None
        self._image = None
        self._play = None
        size = px(NOW_COVER)
        self.cover = tk.Canvas(self, width=size, height=size, background=P.surface, highlightthickness=0)
        self.cover.pack(side="left", padx=px(12), pady=px(12))
        text = self._text = tk.Frame(self, background=P.surface)
        text.pack(side="left", fill="x", expand=True, pady=px(12))
        self.title = tk.Label(text, font=TYPE["heading"], background=P.surface, foreground=P.text, anchor="w")
        self.title.pack(fill="x")
        self.subtitle = tk.Label(text, font=FONT, background=P.surface, foreground=P.muted, anchor="w")
        self.subtitle.pack(fill="x")
        self.state = tk.Label(text, font=TYPE["small"], background=P.surface, foreground=P.muted, anchor="w")
        self.state.pack(fill="x", pady=(px(2), 0))
        for widget in (self, self.cover, text, self.title, self.subtitle, self.state):
            widget.bind("<Button-1>", lambda e: self._open())

    def _open(self):
        if self._play and self._play["id"] is not None:
            self.open_track(self._play["key"])

    def _cover_arrived(self):
        self._shown = None

    def show(self, status: dict, enabled: bool):
        """Show the recorder's status (see LocalTracker.status); only what changed is drawn again."""
        play, state = status["play"], status["state"]
        playing = play if state in ("playing", "paused") else None
        if not enabled:
            message, color = t("listening.now.off"), P.muted
        elif status["error"]:
            message, color = t("listening.now.error", error=status["error"]), P.removed
        else:
            message, color = t("listening.now.idle"), P.muted
        if playing is None:
            shown = (message,)
        else:
            shown = (playing["key"], state, playing["ms"] // 1000, playing["id"] is not None)
        if shown == self._shown:
            return
        self._shown = shown
        self._play = playing
        self.cover.delete("all")
        self._image = None
        size = px(NOW_COVER)
        if playing is None:
            self.title.configure(text=message, foreground=color, font=FONT)
            self.subtitle.configure(text="")
            self.state.configure(text="")
            # Only the message, on one line
            self.cover.pack_forget()
            self.subtitle.pack_forget()
            self.state.pack_forget()
            self._text.pack_configure(padx=px(12))
            self.configure(cursor="")
            return
        if not self.cover.winfo_manager():
            self._text.pack_configure(padx=0)
            self.cover.pack(side="left", padx=px(12), pady=px(12), before=self._text)
            self.subtitle.pack(fill="x")
            self.state.pack(fill="x", pady=(px(2), 0))
        path = self.fetcher.cover(playing["artist"], playing["album"] or "", playing["name"], self._cover_arrived)
        self._image = artwork.photo(path, size, P.surface, radius=px(6))
        if self._image is not None:
            self.cover.create_image(0, 0, image=self._image, anchor="nw")
        else:
            placeholder(self.cover, 0, 0, size, playing["name"], False, ("Segoe UI Semibold", 16))
        self.title.configure(text=playing["name"], foreground=P.text, font=TYPE["heading"])
        self.subtitle.configure(text="  ·  ".join(part for part in (playing["artist"], playing["album"]) if part))
        listened = format_length(playing["ms"]) or "0:00"
        text = t("listening.card.playing" if state == "playing" else "listening.card.paused", listened=listened)
        if playing["id"] is not None:
            text += t("listening.now.recorded")
        self.state.configure(text=text, foreground=P.added if state == "playing" else P.muted)
        self.configure(cursor="hand2" if playing["id"] is not None else "")
