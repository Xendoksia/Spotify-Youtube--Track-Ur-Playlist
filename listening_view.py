"""
Listening section of the interface: plays recorded on this computer, kept apart from playlist tracking.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import listening
import nowplaying
import tracker
from i18n import t
from stats_view import StatsTab
from theme import P, px
from tracker import format_date

STATUS_INTERVAL_MS = 1000


def format_length(ms: int | None) -> str:
    if not ms:
        return "—"
    seconds = ms // 1000
    return f"{seconds // 60}:{seconds % 60:02d}"


def tracking_enabled(config: dict) -> bool:
    return config.get("LOCAL_TRACKING", True) is not False


def set_tracking(local_tracker: nowplaying.LocalTracker, enabled: bool) -> None:
    """Turn recording on or off and remember the choice (used by the checkbox and the tray menu)."""
    config = tracker.load_config()
    config["LOCAL_TRACKING"] = enabled
    tracker.save_config(config)
    if enabled:
        local_tracker.start()
    else:
        local_tracker.stop()


class ListeningView(ttk.Frame):
    """Sub-tabs for listening data: statistics and the list of recent plays."""

    def __init__(self, parent, app, local_tracker: nowplaying.LocalTracker):
        super().__init__(parent)
        self.app = app
        self.local_tracker = local_tracker
        self._version = local_tracker.version
        self._build()
        self.refresh()
        self._poll_status()

    def _build(self):
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True)
        self.stats = StatsTab(self.tabs)
        self.tabs.add(self.stats, text=f"  {t('stats.tab')}  ")

        tab = ttk.Frame(self.tabs, padding=px(16), style="Card.TFrame")
        self.tabs.add(tab, text=f"  {t('listening.recent_tab')}  ")

        toolbar = ttk.Frame(tab, style="Card.TFrame")
        toolbar.pack(fill="x")
        self.tracking = tk.BooleanVar(value=tracking_enabled(tracker.load_config()))
        ttk.Checkbutton(toolbar, text=t("listening.track_toggle"), variable=self.tracking,
                        command=self._toggle_tracking, style="Card.TCheckbutton").pack(side="left")
        self.info_label = ttk.Label(toolbar, style="CardMuted.TLabel")
        self.info_label.pack(side="right")

        self.now_label = ttk.Label(tab, style="Card.TLabel")
        self.now_label.pack(anchor="w", pady=(px(10), 0))

        table_frame = ttk.Frame(tab, style="Card.TFrame")
        table_frame.pack(fill="both", expand=True, pady=(px(10), 0))
        columns = ("played_at", "track", "artist", "album", "listened", "source")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        for column, width, anchor in (("played_at", 140, "w"), ("track", 280, "w"), ("artist", 200, "w"),
                                      ("album", 200, "w"), ("listened", 80, "center"), ("source", 130, "w")):
            self.table.heading(column, text=t(f"listening.column.{column}"), anchor=anchor)
            self.table.column(column, width=px(width), anchor=anchor, stretch=column in ("track", "artist", "album"))
        self.table.tag_configure("odd", background=P.stripe)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _toggle_tracking(self):
        set_tracking(self.local_tracker, self.tracking.get())

    def _poll_status(self):
        status = self.local_tracker.status()
        play, state = status["play"], status["state"]
        # Recording can also be paused from the tray menu
        if self.tracking.get() != self.local_tracker.enabled:
            self.tracking.set(self.local_tracker.enabled)
        if state == "off":
            text, color = t("listening.now.off"), P.muted
        elif status["error"]:
            text, color = t("listening.now.error", error=status["error"]), P.removed
        elif play and state in ("playing", "paused"):
            key = "listening.now.playing" if state == "playing" else "listening.now.paused"
            text = t(key, track=tracker.track_label(play), listened=format_length(play["ms"]) if play["ms"] else "0:00")
            if play["id"] is not None:
                text += t("listening.now.recorded")
            color = P.added if state == "playing" else P.muted
        else:
            text, color = t("listening.now.idle"), P.muted
        self.now_label.configure(text=text, foreground=color)
        if self.local_tracker.version != self._version:
            self._version = self.local_tracker.version
            self.refresh()
        self.after(STATUS_INTERVAL_MS, self._poll_status)

    def refresh(self):
        self.stats.refresh()
        self.table.delete(*self.table.get_children())
        for index, p in enumerate(listening.recent_plays(500)):
            self.table.insert("", "end", tags=("odd",) if index % 2 else (), values=(
                format_date(p["played_at"]), p["name"], p["artist"], p["album"], format_length(p["ms_played"]),
                t(f"listening.source.{p['source']}")))
        self.info_label.configure(text=t("listening.info", count=sum(listening.counts().values())))
