"""
One service's tab of playlist tracking: its playlists, which of them are tracked, and the result of the
last check.
"""

from __future__ import annotations

import webbrowser
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from playlist_tracker.core.config import load_config
from playlist_tracker.core.errors import TrackerError
from playlist_tracker.core.i18n import t
from playlist_tracker.core.text import format_date, track_label
from playlist_tracker.playlists import history
from playlist_tracker.ui.services import EVENTS, Service, event_color, event_label
from playlist_tracker.ui.theme import FONT_BOLD, P, px, text_box

if TYPE_CHECKING:
    from playlist_tracker.ui.main_window import App

CHECKED, UNCHECKED = "☑", "☐"


class PlaylistPanel(ttk.Frame):
    """Playlist list, selection and check results for one service."""

    def __init__(self, app: "App", service: Service):
        super().__init__(app.tabs, padding=px(16), style="Card.TFrame")
        self.app = app
        self.service = service
        self.playlists: dict[str, dict] = {}
        self._build()
        self._load_tracked()
        self.update_login_status()

    def _build(self):
        form = ttk.Frame(self, style="Card.TFrame")
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        top = ttk.Frame(form, style="Card.TFrame")
        top.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, px(12)))
        self.fetch_button = ttk.Button(top, text=t("panel.load_playlists", service=self.service.name),
                                       command=self.load_my_playlists)
        self.fetch_button.pack(side="left")
        self.login_button = ttk.Button(top, command=self.login)
        self.login_button.pack(side="right")
        self.login_label = ttk.Label(top, style="Card.TLabel", foreground=P.added)
        self.login_label.pack(side="right", padx=px(8))

        ttk.Label(form, text=t("panel.or_link"), style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=px(2))
        self.link_entry = ttk.Entry(form)
        self.link_entry.grid(row=1, column=1, sticky="ew", padx=px(8), pady=px(2))
        self.link_entry.bind("<Return>", lambda e: self.add_by_link())
        self.add_button = ttk.Button(form, text=t("panel.add"), command=self.add_by_link)
        self.add_button.grid(row=1, column=2, sticky="ew", pady=px(2))

        ttk.Label(self, style="CardMuted.TLabel", text=t("panel.hint")).pack(anchor="w", pady=(px(16), px(8)))

        table_frame = ttk.Frame(self, style="Card.TFrame")
        table_frame.pack(fill="both", expand=True)
        columns = ("tracked", "name", "owner", "tracks", "last_checked")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse",
                                  height=8)
        for column, heading, width, anchor in (
            ("tracked", t("column.tracked"), 60, "center"),
            ("name", t("column.playlist"), 380, "w"),
            ("owner", t("column.owner"), 160, "w"),
            ("tracks", t(f"column.{self.service.items}"), 70, "center"),
            ("last_checked", t("column.last_checked"), 140, "center"),
        ):
            self.table.heading(column, text=heading, anchor=anchor)
            self.table.column(column, width=px(width), anchor=anchor, stretch=(column == "name"))
        self.table.tag_configure("odd", background=P.stripe)
        self.table.tag_configure("tracked", background=self.service.tint)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.table.bind("<Button-1>", self._on_row_click)
        self.table.bind("<space>", lambda e: self._toggle_selected())
        self.table.bind("<Double-1>", self._open_playlist)

        footer = ttk.Frame(self, style="Card.TFrame")
        footer.pack(fill="x", pady=(px(12), 0))
        ttk.Button(footer, text=t("panel.select_all"), command=lambda: self._set_all(True)).pack(side="left")
        ttk.Button(footer, text=t("panel.clear_selection"),
                   command=lambda: self._set_all(False)).pack(side="left", padx=px(8))
        self.check_button = ttk.Button(footer, command=self.check, style=f"{self.service.name}.Accent.TButton")
        self.check_button.pack(side="right")

        ttk.Label(self, text=t("panel.last_result"), style="Section.TLabel").pack(anchor="w", pady=(px(16), px(8)))
        self.result_box = text_box(self, height=8)
        self.result_box.pack(fill="x")
        for event in EVENTS:
            self.result_box.tag_configure(event, foreground=event_color(event))
        self.result_box.tag_configure("heading", font=FONT_BOLD)

    @property
    def buttons(self):
        return (self.fetch_button, self.add_button, self.check_button, self.login_button)

    def _load_tracked(self):
        for p in history.tracked_playlists(self.service.db_path):
            self.playlists[p["playlist_id"]] = {
                "name": p["name"], "owner": "", "track_count": "",
                "tracked": True, "last_checked": p["last_checked"],
            }
        self.render()

    def render(self):
        self.table.delete(*self.table.get_children())
        ordered = sorted(self.playlists.items(), key=lambda x: (not x[1]["tracked"], x[1]["name"].lower()))
        for index, (playlist_id, p) in enumerate(ordered):
            self.table.insert(
                "", "end", iid=playlist_id, tags=("tracked",) if p["tracked"] else ("odd",) if index % 2 else (),
                values=(CHECKED if p["tracked"] else UNCHECKED, p["name"], p["owner"],
                        p["track_count"], format_date(p["last_checked"]) or "—"),
            )
        self.check_button.configure(text=t("panel.check", count=len(self.tracked_names())))
        self.app.history.update_filter()

    def tracked_names(self):
        return sorted((p["name"] for p in self.playlists.values() if p["tracked"]), key=str.lower)

    def _set_tracked(self, playlist_id, tracked):
        p = self.playlists[playlist_id]
        p["tracked"] = tracked
        history.set_tracked(playlist_id, p["name"], tracked, self.service.db_path)

    def _toggle(self, playlist_id):
        self._set_tracked(playlist_id, not self.playlists[playlist_id]["tracked"])
        self.render()
        if self.table.exists(playlist_id):
            self.table.selection_set(playlist_id)
            self.table.see(playlist_id)

    def _on_row_click(self, event):
        if self.table.identify_region(event.x, event.y) != "cell":
            return
        playlist_id = self.table.identify_row(event.y)
        if playlist_id and self.table.identify_column(event.x) == "#1":
            self._toggle(playlist_id)
            return "break"

    def _toggle_selected(self):
        selection = self.table.selection()
        if selection:
            self._toggle(selection[0])

    def _set_all(self, tracked):
        for playlist_id, p in self.playlists.items():
            if p["tracked"] != tracked:
                self._set_tracked(playlist_id, tracked)
        self.render()

    def _open_playlist(self, event):
        playlist_id = self.table.identify_row(event.y)
        if playlist_id and self.table.identify_column(event.x) != "#1":
            webbrowser.open(self.service.playlist_url.format(playlist_id))

    def update_login_status(self):
        user = self.service.session_user(load_config())
        if user is not None:
            self.login_label.configure(text=t("login.logged_in", user=user))
            self.login_button.configure(text=t("login.switch"))
        else:
            self.login_label.configure(text="")
            self.login_button.configure(text=t("login.button", account=self.service.account))

    def run(self, task, on_success):
        self.app.run_in_background(self, task, on_success)

    def login(self):
        self.app.set_status(t(f"login.hint.{self.service.key}"))

        def on_success(user):
            self.app.set_status(t("status.logged_in", service=self.service.name, user=user))
            self.load_my_playlists()

        self.run(lambda: self.service.connect().login(), on_success)

    def load_my_playlists(self):
        self.app.set_status(t("status.loading", service=self.service.name))

        def on_success(result):
            readable, others = result
            for p in readable:
                existing = self.playlists.get(p["id"], {})
                self.playlists[p["id"]] = {
                    "name": p["name"], "owner": p["owner"], "track_count": p["track_count"],
                    "tracked": existing.get("tracked", False), "last_checked": existing.get("last_checked"),
                }
            self.render()
            note = t("status.hidden_others", count=len(others)) if others else ""
            self.app.set_status(t("status.found", count=len(readable), service=self.service.name) + note)

        self.run(lambda: self.service.connect().my_playlists(), on_success)

    def add_by_link(self):
        link = self.link_entry.get().strip()
        if not link:
            return
        try:
            playlist_id = self.service.parse_playlist_id(link)
        except TrackerError as e:
            messagebox.showerror(t("dialog.error"), str(e), parent=self)
            return
        self.app.set_status(t("status.fetching"))

        def on_success(name):
            existing = self.playlists.get(playlist_id, {})
            self.playlists[playlist_id] = {
                "name": name, "owner": existing.get("owner", ""),
                "track_count": existing.get("track_count", ""),
                "tracked": True, "last_checked": existing.get("last_checked"),
            }
            history.set_tracked(playlist_id, name, True, self.service.db_path)
            self.link_entry.delete(0, "end")
            self.render()
            self.app.set_status(t("status.now_tracked", name=name))

        self.run(lambda: self.service.connect().playlist_name(playlist_id), on_success)

    def check(self):
        selected = [pid for pid, p in self.playlists.items() if p["tracked"]]
        if not selected:
            messagebox.showinfo(t("dialog.nothing_selected"), t("dialog.nothing_selected.text"), parent=self)
            return

        def task():
            client = self.service.connect()
            results = []
            for i, playlist_id in enumerate(selected, 1):
                name = self.playlists[playlist_id]["name"]
                self.app.after(0, lambda i=i, name=name: self.app.set_status(
                    t("status.checking", index=i, count=len(selected), name=name)))
                try:
                    results.append(history.check_playlist(client, playlist_id, self.service.db_path))
                except self.service.login_required:
                    raise
                except TrackerError as e:
                    results.append({"name": name, "error": str(e)})
            return results

        self.run(task, self.show_results)

    def show_results(self, results, automatic: bool = False):
        """Show the result of a check, from the Check button or the automatic check."""
        box = self.result_box
        box.configure(state="normal")
        box.delete("1.0", "end")
        total_changes = 0
        items = t(f"items.{self.service.items}")
        for r in results:
            if "error" in r:
                box.insert("end", f"{r['name']}: ", "heading")
                box.insert("end", t("result.error", error=r["error"]) + "\n", history.EVENT_REMOVED)
                continue
            p = self.playlists.get(r["playlist_id"])
            if p:
                p.update(name=r["name"], track_count=r["total"], last_checked=r["checked_at"])
            box.insert("end", t("result.heading", name=r["name"], total=r["total"], items=items), "heading")
            if r["first_check"]:
                box.insert("end", t("result.initial") + "\n", history.EVENT_INITIAL)
                for track in r["unavailable"]:
                    box.insert("end", f"    ! {self.service.unavailable_label()}: {track_label(track)}\n",
                               history.EVENT_UNPLAYABLE)
                continue
            changes = (
                [(history.EVENT_ADDED, track) for track in r["added"]]
                + [(history.EVENT_REMOVED, track) for track in r["removed"]]
                + [(history.EVENT_UNPLAYABLE, track) for track in r["unplayable"]]
                + [(history.EVENT_PLAYABLE, track) for track in r["playable_again"]]
            )
            total_changes += len(changes)
            if not changes:
                box.insert("end", t("result.no_changes") + "\n")
                continue
            box.insert("end", t("result.changes", count=len(changes)) + "\n")
            for event, track in changes:
                added = t("result.added", date=format_date(track["added_at"])) if track.get("added_at") else ""
                box.insert("end", f"    {event_label(event):<18} {track_label(track)}{added}\n", event)
        box.configure(state="disabled")
        self.render()
        self.app.history.refresh()
        self.app.set_status(t("status.auto_check_done" if automatic else "status.check_done", count=len(results),
                              changes=total_changes))
