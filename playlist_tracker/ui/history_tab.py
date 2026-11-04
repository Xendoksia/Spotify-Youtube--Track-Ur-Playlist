"""
History tab of playlist tracking: every change recorded in the playlists of one service, filterable by
playlist and event, and exported to CSV.
"""

from __future__ import annotations

import re
from tkinter import filedialog, ttk

from playlist_tracker.core.i18n import t
from playlist_tracker.core.text import format_date, track_label
from playlist_tracker.playlists import history
from playlist_tracker.ui.services import EVENTS, SERVICES, event_color, event_label
from playlist_tracker.ui.theme import P, px


class HistoryTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=px(16), style="Card.TFrame")
        self.app = app
        self._build()

    def _build(self):
        tab = self

        toolbar = ttk.Frame(tab, style="Card.TFrame")
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text=t("history.source"), style="Card.TLabel").pack(side="left")
        self.source_filter = ttk.Combobox(toolbar, state="readonly", width=10, values=[s.name for s in SERVICES])
        self.source_filter.current(0)
        self.source_filter.pack(side="left", padx=px(8))
        self.source_filter.bind("<<ComboboxSelected>>", lambda e: self._on_source_changed())
        ttk.Label(toolbar, text=t("history.playlist"), style="Card.TLabel").pack(side="left", padx=(px(12), 0))
        self.playlist_filter = ttk.Combobox(toolbar, state="readonly", width=40)
        self.playlist_filter.pack(side="left", padx=px(8))
        self.playlist_filter.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Label(toolbar, text=t("history.event"), style="Card.TLabel").pack(side="left", padx=(px(12), 0))
        self.event_filter = ttk.Combobox(toolbar, state="readonly", width=20,
                                         values=[t("history.all")] + [event_label(e) for e in EVENTS])
        self.event_filter.current(0)
        self.event_filter.pack(side="left", padx=px(8))
        self.event_filter.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Button(toolbar, text=t("history.export"), command=self._export_csv).pack(side="right")
        ttk.Button(toolbar, text=t("history.refresh"), command=self.refresh).pack(side="right", padx=px(8))

        table_frame = ttk.Frame(tab, style="Card.TFrame")
        table_frame.pack(fill="both", expand=True, pady=(px(12), 0))
        columns = ("checked_at", "playlist", "event", "track", "added_at")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        for column, heading, width in (
            ("checked_at", t("history.detected"), 130),
            ("playlist", t("column.playlist"), 200),
            ("event", t("history.event_column"), 140),
            ("track", t("history.item"), 400),
            ("added_at", t("history.added"), 130),
        ):
            self.table.heading(column, text=heading, anchor="w")
            self.table.column(column, width=px(width), stretch=(column == "track"))
        self.table.tag_configure("odd", background=P.stripe)
        for event in EVENTS:
            self.table.tag_configure(event, foreground=event_color(event))
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Label(tab, style="CardMuted.TLabel", text=t("history.note")).pack(anchor="w", pady=(px(8), 0))

    def _panel(self):
        return self.app.panels[self.source_filter.get()]

    def update_filter(self):
        panel = self.app.panels.get(self.source_filter.get())
        if not panel:
            return
        self.playlist_filter.configure(values=[t("history.all")] + panel.tracked_names())
        if not self.playlist_filter.get():
            self.playlist_filter.current(0)

    def _on_source_changed(self):
        self.playlist_filter.set("")
        self.update_filter()
        self.refresh()

    def refresh(self):
        if not self.app.panels:
            return
        panel = self._panel()
        selected_playlist = self.playlist_filter.get()
        playlist_id = None
        if self.playlist_filter.current() > 0:
            playlist_id = next((k for k, v in panel.playlists.items() if v["name"] == selected_playlist), None)
        event_index = self.event_filter.current()
        event_code = EVENTS[event_index - 1] if event_index > 0 else None

        self.table.delete(*self.table.get_children())
        rows = [r for r in history.get_events(playlist_id, panel.service.db_path)
                if not event_code or r["event"] == event_code]
        for index, r in enumerate(rows):
            tags = (r["event"], "odd") if index % 2 else (r["event"],)
            item = track_label(r)
            count = re.match(r"(\d+) ", r["name"] or "")
            if r["event"] == history.EVENT_INITIAL and count:
                item = t("history.initial_count", count=count.group(1))
            self.table.insert("", "end", tags=tags, values=(
                format_date(r["checked_at"]), r["playlist"] or "", event_label(r["event"]),
                item, format_date(r["added_at"]),
            ))

    def _export_csv(self):
        service = self._panel().service
        path = filedialog.asksaveasfilename(
            parent=self.app, defaultextension=".csv", initialfile=f"{service.key}_history.csv",
            filetypes=[(t("csv.filetype"), "*.csv")],
        )
        if path:
            count = history.export_csv(path, service.db_path)
            self.app.set_status(t("status.exported", count=count, service=service.name, path=path))
