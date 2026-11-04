"""
A strip along the bottom of the window showing the song playing in the Spotify app: cover, title,
artist, the time into the song with a progress line, and whether the play is recorded yet.
Clicking it opens the song's page in the listening statistics.
"""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk

import artwork
import nowplaying
from charts import placeholder
from i18n import t
from theme import FONT, P, px

# Often enough for the clock to tick each second; paused, hidden or in the tray only a change has to show
UPDATE_MS = 500
IDLE_UPDATE_MS = 1000
COVER_SIZE = 44


def clock(ms: float) -> str:
    seconds = int(ms // 1000)
    return f"{seconds // 60}:{seconds % 60:02d}"


class MiniPlayer(ttk.Frame):
    def __init__(self, parent, local_tracker: nowplaying.LocalTracker, open_track, first_widget: tk.Misc):
        """open_track(track_key) shows a song's page; first_widget is the window's topmost part, packed before
        everything else, so the strip is packed ahead of it and keeps its place at the bottom."""
        super().__init__(parent, style="Card.TFrame")
        self.first_widget = first_widget
        self.local_tracker = local_tracker
        self.open_track = open_track
        self.fetcher = artwork.Fetcher(self)
        self._shown_key = None
        # What the strip shows now, compared before changing anything
        self._shown = None
        self._cover_image = None
        self._play = None
        self._visible = False

        self.progress = tk.Canvas(self, height=px(3), background=P.grid, highlightthickness=0)
        self.progress.pack(fill="x")
        body = ttk.Frame(self, padding=(px(16), px(8)), style="Card.TFrame")
        body.pack(fill="x")
        size = px(COVER_SIZE)
        self.cover = tk.Canvas(body, width=size, height=size, background=P.surface, highlightthickness=0)
        self.cover.pack(side="left")
        # The time and state are packed before the names, so a long name is cut off instead of pushing them out
        self.state = ttk.Label(body, style="CardMuted.TLabel", font=FONT)
        self.state.pack(side="right")
        self.time = ttk.Label(body, style="Card.TLabel", font=FONT)
        self.time.pack(side="right", padx=(px(16), px(16)))
        text = ttk.Frame(body, style="Card.TFrame")
        text.pack(side="left", fill="x", expand=True, padx=(px(12), 0))
        self.title = ttk.Label(text, style="Section.TLabel")
        self.title.pack(anchor="w")
        self.subtitle = ttk.Label(text, style="CardMuted.TLabel")
        self.subtitle.pack(anchor="w")

        self._clickable = (self, body, self.cover, text, self.title, self.subtitle, self.state, self.time,
                           self.progress)
        for widget in self._clickable:
            widget.bind("<Button-1>", lambda e: self._open())
        self._update()

    def _open(self):
        # Only a recorded song has a page
        if self._play and self._play["id"] is not None:
            self.open_track(self._play["key"])

    def _show(self, visible: bool):
        if visible != self._visible:
            self._visible = visible
            if visible:
                self.pack(side="bottom", fill="x", before=self.first_widget)
            else:
                self.pack_forget()

    def _cover_arrived(self):
        self._shown_key = None

    def _draw_cover(self, play: dict):
        size = px(COVER_SIZE)
        path = self.fetcher.cover(play["artist"], play["album"] or "", play["name"], self._cover_arrived)
        self._cover_image = artwork.photo(path, size, P.surface, radius=px(4))
        self.cover.delete("all")
        if self._cover_image is not None:
            self.cover.create_image(0, 0, image=self._cover_image, anchor="nw")
        else:
            placeholder(self.cover, 0, 0, size, play["name"], False, ("Segoe UI Semibold", 14))

    def _update(self):
        if not self.winfo_exists():
            return
        if not self.winfo_toplevel().winfo_viewable():
            self.after(IDLE_UPDATE_MS, self._update)
            return
        status = self.local_tracker.status()
        play, state = status["play"], status["state"]
        self._play = play if state in ("playing", "paused") else None
        self._show(self._play is not None)
        if self._play:
            self._fill(play, state == "playing")
        self.after(UPDATE_MS if state == "playing" else IDLE_UPDATE_MS, self._update)

    def _fill(self, play: dict, playing: bool):
        if play["key"] != self._shown_key:
            self._shown_key = play["key"]
            self.title.configure(text=play["name"])
            self.subtitle.configure(text=play["artist"] + (f"  ·  {play['album']}" if play["album"] else ""))
            self._draw_cover(play)

        position = play.get("position")
        if position is not None and playing and play.get("position_at"):
            # Between two reads of the media session the song keeps going
            position += (time.monotonic() - play["position_at"]) * 1000
        duration = play.get("duration")
        width = 0
        if position is not None and duration:
            position = min(position, duration)
            time_text = f"{clock(position)} / {clock(duration)}"
            width = round(self.progress.winfo_width() * position / duration)
        else:
            time_text = clock(position) if position is not None else ""
        shown = (play["key"], time_text, width, playing, play["id"] is not None)
        if shown == self._shown:
            # Nothing that is on screen changed (paused), so Tk has nothing to redraw
            return
        self._shown = shown

        self.time.configure(text=time_text)
        self.progress.delete("all")
        if width:
            self.progress.create_rectangle(0, 0, width, px(3), fill=P.chart, width=0)

        state = t("mini.playing" if playing else "mini.paused")
        if play["id"] is not None:
            state += t("mini.recorded")
        self.state.configure(text=state, foreground=P.added if playing else P.muted)
        cursor = "hand2" if play["id"] is not None else ""
        for widget in self._clickable:
            widget.configure(cursor=cursor)
