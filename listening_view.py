"""
Listening section of the interface: recorded Spotify plays, kept apart from playlist tracking.
"""

from __future__ import annotations

import threading
from tkinter import ttk

import listening
import tracker
from i18n import t
from theme import P
from tracker import TrackerError, format_date

SYNC_INTERVAL_MS = 30 * 60 * 1000


def format_length(ms: int) -> str:
    seconds = (ms or 0) // 1000
    return f"{seconds // 60}:{seconds % 60:02d}"


class ListeningView(ttk.Frame):
    """Sub-tabs for listening data; statistics are added next to “Recently played”."""

    def __init__(self, parent, app, service):
        super().__init__(parent)
        self.app = app
        # Used by App.run_in_background, which needs the service's credentials and login errors
        self.service = service
        self._syncing = False
        self._build()
        self.refresh()
        self.after(1500, self._sync_loop)

    def _build(self):
        self.login_banner = ttk.Frame(self, padding=(14, 10), style="Banner.TFrame")
        ttk.Label(self.login_banner, text=t("listening.login_needed"), style="Banner.TLabel"
                  ).pack(side="left")
        ttk.Button(self.login_banner, text=t("login.button", account=self.service.account),
                   style=f"{self.service.name}.Accent.TButton", command=self.login).pack(side="right")

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True)

        tab = ttk.Frame(self.tabs, padding=16, style="Card.TFrame")
        self.tabs.add(tab, text=f"  {t('listening.recent_tab')}  ")

        toolbar = ttk.Frame(tab, style="Card.TFrame")
        toolbar.pack(fill="x")
        self.sync_button = ttk.Button(toolbar, text=t("listening.sync"), command=self.sync,
                                      style=f"{self.service.name}.Accent.TButton")
        self.sync_button.pack(side="left")
        self.info_label = ttk.Label(toolbar, style="CardMuted.TLabel")
        self.info_label.pack(side="left", padx=12)

        table_frame = ttk.Frame(tab, style="Card.TFrame")
        table_frame.pack(fill="both", expand=True, pady=(12, 0))
        columns = ("played_at", "track", "artist", "album", "length")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        for column, width, anchor in (("played_at", 140, "w"), ("track", 300, "w"), ("artist", 220, "w"),
                                      ("album", 220, "w"), ("length", 70, "center")):
            self.table.heading(column, text=t(f"listening.column.{column}"), anchor=anchor)
            self.table.column(column, width=width, anchor=anchor, stretch=column in ("track", "artist", "album"))
        self.table.tag_configure("odd", background=P.stripe)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Label(tab, text=t("listening.note"), style="CardMuted.TLabel").pack(anchor="w", pady=(8, 0))

    @property
    def buttons(self):
        return (self.sync_button,)

    def update_login_status(self):
        if listening.needs_login(tracker.load_config()):
            self.login_banner.pack(fill="x", pady=(0, 10), before=self.tabs)
        else:
            self.login_banner.pack_forget()

    def login(self):
        self.app.panels[self.service.name].login()

    def refresh(self):
        self.update_login_status()
        plays = listening.recent_plays(500)
        self.table.delete(*self.table.get_children())
        for index, p in enumerate(plays):
            self.table.insert("", "end", tags=("odd",) if index % 2 else (), values=(
                format_date(p["played_at"]), p["name"], p["artist"], p["album"], format_length(p["duration_ms"])))
        with listening.open_db() as db:
            total = db.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
        synced = format_date(listening.last_sync()) or t("listening.never")
        self.info_label.configure(text=t("listening.info", time=synced, count=total)
                                  + ("" if total else "  ·  " + t("listening.empty")))

    def sync(self):
        self.app.set_status(t("listening.syncing"))

        def on_success(new):
            self.refresh()
            self.app.set_status(t("listening.synced", count=new))

        self.app.run_in_background(self, lambda: listening.sync(self.service.connect()), on_success)

    def _sync_loop(self):
        self.after(SYNC_INTERVAL_MS, self._sync_loop)
        self.auto_sync()

    def auto_sync(self):
        """Sync quietly in the background; errors only show up in the status line."""
        config = tracker.load_config()
        if self._syncing or not self.service.has_credentials(config) or listening.needs_login(config):
            return
        self._syncing = True

        def worker():
            try:
                new, error = listening.sync(self.service.connect()), None
            except TrackerError as e:
                new, error = 0, str(e)
            except Exception as e:
                new, error = 0, t("error.unexpected", error=repr(e))
            self.after(0, lambda: self._on_auto_sync(new, error))

        threading.Thread(target=worker, daemon=True).start()

    def _on_auto_sync(self, new, error):
        self._syncing = False
        self.refresh()
        if error:
            self.app.set_status(t("listening.auto_sync_failed", error=error))
        elif new:
            self.app.set_status(t("listening.synced", count=new))
