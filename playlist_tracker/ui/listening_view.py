"""
Listening section of the interface: plays recorded on this computer, kept apart from playlist tracking.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from playlist_tracker.core.config import load_config, save_config
from playlist_tracker.core.i18n import t
from playlist_tracker.music import listening, nowplaying
from playlist_tracker.ui.recent_plays import NowPlaying, RecentList
from playlist_tracker.ui.stats.tab import StatsTab
from playlist_tracker.ui.stats.widgets import ScrollFrame
from playlist_tracker.ui.tabs import Tabs
from playlist_tracker.ui.theme import px

STATUS_INTERVAL_MS = 1000
# In the tray or behind the playlist section nothing is drawn, so the status is only looked at for new plays
HIDDEN_INTERVAL_MS = 5000
# Plays in the Recently played list
RECENT_COUNT = 200


def tracking_enabled(config: dict) -> bool:
    return config.get("LOCAL_TRACKING", True) is not False


def set_tracking(local_tracker: nowplaying.LocalTracker, enabled: bool) -> None:
    """Turn recording on or off and remember the choice (used by the checkbox and the tray menu)."""
    config = load_config()
    config["LOCAL_TRACKING"] = enabled
    save_config(config)
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
        # The pages are rebuilt only when seen, not for every play stored while the window is in the tray
        self._stale = True
        self._build()
        self.bind("<Map>", self._on_map)
        self._poll_status()

    def _build(self):
        self.tabs = Tabs(self)
        self.tabs.pack(fill="both", expand=True)
        self.stats = StatsTab(self.tabs)
        self.tabs.add(self.stats, text=t("stats.tab"))

        tab = ttk.Frame(self.tabs, padding=px(16), style="Card.TFrame")
        self.tabs.add(tab, text=t("listening.recent_tab"))

        toolbar = ttk.Frame(tab, style="Card.TFrame")
        toolbar.pack(fill="x")
        self.tracking = tk.BooleanVar(value=tracking_enabled(load_config()))
        ttk.Checkbutton(toolbar, text=t("listening.track_toggle"), variable=self.tracking,
                        command=self._toggle_tracking, style="Card.TCheckbutton").pack(side="left")
        self.info_label = ttk.Label(toolbar, style="CardMuted.TLabel")
        self.info_label.pack(side="right")

        self.now_playing = NowPlaying(tab, self.app.open_track_page)
        self.now_playing.pack(fill="x", pady=(px(12), 0))

        page = ScrollFrame(tab)
        page.content.configure(padding=(0, px(8), px(12), 0))
        page.pack(fill="both", expand=True, pady=(px(8), 0))
        self.recent = RecentList(page.content, self.app.open_track_page)
        self.recent.pack(fill="x")

    def _toggle_tracking(self):
        set_tracking(self.local_tracker, self.tracking.get())

    def mark_stale(self):
        """The listening data changed: rebuild the pages now if they are seen, or when they are shown."""
        self._stale = True
        self._refresh_if_stale()

    def _refresh_if_stale(self):
        if self._stale and self.winfo_viewable():
            self.refresh()

    def _on_map(self, event):
        # Shown from the tray or the other section: bring everything up to date at once, not at the next poll
        if event.widget is self:
            self._refresh_if_stale()
            self._show_status()

    def _poll_status(self):
        if self.local_tracker.version != self._version:
            self._version = self.local_tracker.version
            self.mark_stale()
        if not self.winfo_viewable():
            self.after(HIDDEN_INTERVAL_MS, self._poll_status)
            return
        self._show_status()
        self.after(STATUS_INTERVAL_MS, self._poll_status)

    def _show_status(self):
        status = self.local_tracker.status()
        # Recording can also be paused from the tray menu
        if self.tracking.get() != self.local_tracker.enabled:
            self.tracking.set(self.local_tracker.enabled)
        self.now_playing.show(status, enabled=status["state"] != "off")

    def _fill_recent(self):
        self.recent.set_plays(listening.recent_plays(RECENT_COUNT))

    def refresh(self):
        self._stale = False
        self.stats.refresh()
        self._fill_recent()
        self.info_label.configure(text=t("listening.info", count=sum(listening.counts().values())))
