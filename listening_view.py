"""
Listening section of the interface: plays recorded on this computer and imported from the
Spotify data export, kept apart from playlist tracking.
"""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk
from types import SimpleNamespace

import listening
import nowplaying
import tracker
from i18n import t
from theme import P
from tracker import format_date

PRIVACY_URL = "https://www.spotify.com/account/privacy/"
STATUS_INTERVAL_MS = 1000


def format_length(ms: int | None) -> str:
    if not ms:
        return "—"
    seconds = ms // 1000
    return f"{seconds // 60}:{seconds % 60:02d}"


def tracking_enabled(config: dict) -> bool:
    return config.get("LOCAL_TRACKING", True) is not False


class ListeningView(ttk.Frame):
    """Sub-tabs for listening data; statistics are added next to “Recently played”."""

    # Importing needs no account and raises no login errors (an empty tuple matches no exception)
    service = SimpleNamespace(login_required=())

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

        tab = ttk.Frame(self.tabs, padding=16, style="Card.TFrame")
        self.tabs.add(tab, text=f"  {t('listening.recent_tab')}  ")

        toolbar = ttk.Frame(tab, style="Card.TFrame")
        toolbar.pack(fill="x")
        self.tracking = tk.BooleanVar(value=tracking_enabled(tracker.load_config()))
        ttk.Checkbutton(toolbar, text=t("listening.track_toggle"), variable=self.tracking,
                        command=self._toggle_tracking, style="Card.TCheckbutton").pack(side="left")
        self.import_button = ttk.Button(toolbar, text=t("listening.import"), command=self.import_export)
        self.import_button.pack(side="right")
        self.info_label = ttk.Label(toolbar, style="CardMuted.TLabel")
        self.info_label.pack(side="right", padx=12)

        self.now_label = ttk.Label(tab, style="Card.TLabel")
        self.now_label.pack(anchor="w", pady=(10, 0))

        table_frame = ttk.Frame(tab, style="Card.TFrame")
        table_frame.pack(fill="both", expand=True, pady=(10, 0))
        columns = ("played_at", "track", "artist", "album", "listened", "source")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        for column, width, anchor in (("played_at", 140, "w"), ("track", 280, "w"), ("artist", 200, "w"),
                                      ("album", 200, "w"), ("listened", 80, "center"), ("source", 130, "w")):
            self.table.heading(column, text=t(f"listening.column.{column}"), anchor=anchor)
            self.table.column(column, width=width, anchor=anchor, stretch=column in ("track", "artist", "album"))
        self.table.tag_configure("odd", background=P.stripe)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        footer = ttk.Frame(tab, style="Card.TFrame")
        footer.pack(fill="x", pady=(8, 0))
        ttk.Label(footer, text=t("listening.note"), style="CardMuted.TLabel", justify="left").pack(side="left")
        export_link = ttk.Label(footer, text=t("listening.request_export"), style="Card.TLabel",
                                foreground=P.focus, cursor="hand2")
        export_link.pack(side="right", anchor="n")
        export_link.bind("<Button-1>", lambda e: webbrowser.open(PRIVACY_URL))

    @property
    def buttons(self):
        return (self.import_button,)

    def update_login_status(self):
        pass

    def _toggle_tracking(self):
        config = tracker.load_config()
        config["LOCAL_TRACKING"] = self.tracking.get()
        tracker.save_config(config)
        if self.tracking.get():
            self.local_tracker.start()
        else:
            self.local_tracker.stop()

    def _poll_status(self):
        status = self.local_tracker.status()
        play, state = status["play"], status["state"]
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
        self.table.delete(*self.table.get_children())
        for index, p in enumerate(listening.recent_plays(500)):
            self.table.insert("", "end", tags=("odd",) if index % 2 else (), values=(
                format_date(p["played_at"]), p["name"], p["artist"], p["album"], format_length(p["ms_played"]),
                t(f"listening.source.{p['source']}")))
        self.info_label.configure(text=t("listening.info", count=sum(listening.counts().values())))

    def import_export(self):
        paths = filedialog.askopenfilenames(parent=self, title=t("listening.import"), filetypes=[
            (t("listening.export_files"), "*.zip *.json"), ("ZIP", "*.zip"), ("JSON", "*.json")])
        if not paths:
            return
        self.app.set_status(t("listening.importing"))

        def on_success(result):
            stored, skipped = result
            self.refresh()
            message = t("listening.imported", stored=stored, skipped=skipped)
            self.app.set_status(message)
            messagebox.showinfo(t("listening.import"), message, parent=self)

        self.app.run_in_background(self, lambda: listening.import_export(paths), on_success,
                                   needs_credentials=False)
