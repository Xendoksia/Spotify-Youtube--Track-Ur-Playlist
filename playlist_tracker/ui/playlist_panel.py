"""
One service's tab of playlist tracking: its playlists as cards (tracked ones in the service's color, with
their last check and latest changes), and the result of the last check.
"""

from __future__ import annotations

import tkinter as tk
import webbrowser
from datetime import datetime
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from playlist_tracker.core.config import load_config
from playlist_tracker.core.errors import TrackerError
from playlist_tracker.core.i18n import number, t
from playlist_tracker.core.text import track_label
from playlist_tracker.playlists import history
from playlist_tracker.ui.services import EVENTS, Service, event_color, event_label
from playlist_tracker.ui.stats.text import month_name
from playlist_tracker.ui.stats.widgets import ScrollFrame
from playlist_tracker.ui.theme import FONT, FONT_BOLD, TYPE, P, mix, px, text_box

if TYPE_CHECKING:
    from playlist_tracker.ui.main_window import App

CHECK_SIZE = 20
CARD_COLUMNS = 3
# Order of the latest changes on a card: what went wrong first
CHANGE_ORDER = (history.EVENT_REMOVED, history.EVENT_UNPLAYABLE, history.EVENT_PLAYABLE, history.EVENT_ADDED)


def short_date(iso: str) -> str:
    """A check time as "4 Nov 15:27"."""
    moment = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
    return f"{moment.day} {month_name(moment.month, True)} {moment:%H:%M}"


def badge_color(color: str) -> str:
    """The background of an event badge: its color, faint."""
    return mix(P.surface, color, 0.22 if P.dark else 0.16)


class PlaylistCard(tk.Frame):
    """A playlist: click to track it or not; "Open" opens it in the browser."""

    def __init__(self, parent, panel: "PlaylistPanel", playlist_id: str, playlist: dict, summary: dict | None):
        tracked = playlist["tracked"]
        self.background = panel.service.tint if tracked else P.surface
        # The service's color, softened so a row of tracked cards does not shout
        self.border = mix(P.surface, panel.service.accent, 0.7) if tracked else P.border
        super().__init__(parent, background=self.background, highlightthickness=1,
                         highlightbackground=self.border, highlightcolor=self.border, cursor="hand2")
        self.panel, self.playlist_id = panel, playlist_id
        summary = summary or {}
        body = tk.Frame(self, background=self.background)
        body.pack(fill="both", expand=True, padx=px(12), pady=px(12))
        body.columnconfigure(1, weight=1)

        check = self._check_mark(body, tracked, panel.service.accent)
        check.grid(row=0, column=0, rowspan=2, sticky="nw", padx=(0, px(10)), pady=(px(3), 0))
        name = tk.Label(body, text=playlist["name"], font=TYPE["heading"], background=self.background,
                        foreground=P.text if tracked else P.muted, anchor="w", justify="left", wraplength=px(300))
        name.grid(row=0, column=1, sticky="w")
        opener = tk.Label(body, text=f"{t('panel.open')} ↗", background=self.background, foreground=P.focus,
                          font=FONT, cursor="hand2")
        opener.grid(row=0, column=2, sticky="ne", padx=(px(8), 0))
        opener.bind("<Button-1>", lambda e: webbrowser.open(panel.service.playlist_url.format(playlist_id)))

        count = playlist["track_count"] if playlist["track_count"] != "" else summary.get("tracks")
        details = [part for part in (playlist["owner"],
                                     f"{number(count)} {t(f'items.{panel.service.items}')}" if count is not None
                                     else "") if part]
        clickable = [self, body, check, name]
        line = self._line(body, "  ·  ".join(details), 1)
        if line:
            clickable.append(line)
        checked = playlist["last_checked"]
        clickable.append(self._line(body, t("panel.last_checked", date=short_date(checked)) if checked
                                    else t("panel.never_checked"), 2))
        if summary.get("changes"):
            row = tk.Frame(body, background=self.background)
            row.grid(row=3, column=1, columnspan=2, sticky="w", pady=(px(4), 0))
            clickable.append(row)
            clickable.append(self._label(row, t("panel.last_change", date=short_date(summary["changed_at"]))))
            for event in CHANGE_ORDER:
                if summary["changes"].get(event):
                    symbol = event_label(event).split()[0]
                    chip = tk.Label(row, text=f"{symbol}{number(summary['changes'][event])}", font=FONT_BOLD,
                                    background=self.background, foreground=event_color(event))
                    chip.pack(side="left", padx=(px(6), 0))
                    clickable.append(chip)
        for widget in clickable:
            widget.bind("<Button-1>", lambda e: panel.toggle(playlist_id))
            widget.bind("<Enter>", lambda e: self._hover(True))
            widget.bind("<Leave>", self._on_leave)

    def _check_mark(self, parent, tracked: bool, accent: str) -> tk.Canvas:
        """A filled circle with a tick when tracked, an empty ring when not."""
        size = px(CHECK_SIZE)
        canvas = tk.Canvas(parent, width=size, height=size, background=self.background, highlightthickness=0)
        if tracked:
            canvas.create_oval(1, 1, size - 1, size - 1, fill=accent, outline=accent)
            canvas.create_line(size * 0.28, size * 0.52, size * 0.44, size * 0.68, size * 0.73, size * 0.34,
                               fill="#ffffff", width=max(2, px(2)), capstyle="round", joinstyle="round")
        else:
            canvas.create_oval(1, 1, size - 1, size - 1, outline=P.muted, width=max(1, px(1.5)))
        return canvas

    def _label(self, parent, text: str) -> tk.Label:
        label = tk.Label(parent, text=text, background=self.background, foreground=P.muted, font=FONT)
        label.pack(side="left")
        return label

    def _line(self, parent, text: str, row: int) -> tk.Label | None:
        if not text:
            return None
        label = tk.Label(parent, text=text, background=self.background, foreground=P.muted, font=FONT, anchor="w")
        label.grid(row=row, column=1, columnspan=2, sticky="w", pady=(px(2), 0))
        return label

    def _hover(self, on: bool):
        color = P.muted if on and self.border == P.border else self.border
        self.configure(highlightbackground=color, highlightcolor=color)

    def _on_leave(self, event):
        # Moving onto a part of the card is not leaving it
        under = self.winfo_containing(event.x_root, event.y_root)
        if under is None or not str(under).startswith(str(self)):
            self._hover(False)


class PlaylistPanel(ttk.Frame):
    """Playlist cards, selection and check results for one service."""

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

        # Packed from the bottom first, so the cards take whatever height is left
        self.result_box = text_box(self, height=8)
        self.result_box.configure(tabs=(px(170),), spacing1=px(2), spacing3=px(2), padx=px(12), pady=px(8))
        self.result_box.pack(side="bottom", fill="x")
        for event in EVENTS:
            self.result_box.tag_configure(event, foreground=event_color(event))
            self.result_box.tag_configure(f"badge-{event}", foreground=event_color(event),
                                          background=badge_color(event_color(event)), font=FONT_BOLD)
        self.result_box.tag_configure("heading", font=FONT_BOLD, spacing1=px(8))
        self.result_box.tag_configure("muted", foreground=P.muted)
        ttk.Label(self, text=t("panel.last_result"), style="Section.TLabel").pack(side="bottom", anchor="w",
                                                                                  pady=(px(16), px(8)))
        footer = ttk.Frame(self, style="Card.TFrame")
        footer.pack(side="bottom", fill="x", pady=(px(12), 0))
        ttk.Button(footer, text=t("panel.select_all"), command=lambda: self._set_all(True)).pack(side="left")
        ttk.Button(footer, text=t("panel.clear_selection"),
                   command=lambda: self._set_all(False)).pack(side="left", padx=px(8))
        self.check_button = ttk.Button(footer, command=self.check, style=f"{self.service.name}.Accent.TButton")
        self.check_button.pack(side="right")

        page = ScrollFrame(self)
        page.content.configure(padding=(0, 0, px(12), 0))
        page.pack(fill="both", expand=True)
        self.cards = page.content
        for column in range(CARD_COLUMNS):
            self.cards.columnconfigure(column, weight=1, uniform="card")

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
        for card in self.cards.winfo_children():
            card.destroy()
        summaries = history.playlist_summaries(self.service.db_path)
        ordered = sorted(self.playlists.items(), key=lambda x: (not x[1]["tracked"], x[1]["name"].lower()))
        for index, (playlist_id, p) in enumerate(ordered):
            card = PlaylistCard(self.cards, self, playlist_id, p, summaries.get(playlist_id))
            row, column = divmod(index, CARD_COLUMNS)
            card.grid(row=row, column=column, sticky="nsew", padx=(0 if column == 0 else px(12), 0),
                      pady=(0 if row == 0 else px(12), 0))
        if not ordered:
            ttk.Label(self.cards, text=t("panel.empty", service=self.service.name), style="CardMuted.TLabel"
                      ).grid(row=0, column=0, columnspan=CARD_COLUMNS, pady=px(24))
        self.check_button.configure(text=t("panel.check", count=len(self.tracked_names())))
        self.app.history.update_filter()

    def tracked_names(self):
        return sorted((p["name"] for p in self.playlists.values() if p["tracked"]), key=str.lower)

    def _set_tracked(self, playlist_id, tracked):
        p = self.playlists[playlist_id]
        p["tracked"] = tracked
        history.set_tracked(playlist_id, p["name"], tracked, self.service.db_path)

    def toggle(self, playlist_id):
        self._set_tracked(playlist_id, not self.playlists[playlist_id]["tracked"])
        self.render()

    def _set_all(self, tracked):
        for playlist_id, p in self.playlists.items():
            if p["tracked"] != tracked:
                self._set_tracked(playlist_id, tracked)
        self.render()

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

    def _badge(self, event: str, text: str, date: str = ""):
        """One track of a result: the event as a colored badge, the track, and when it was added."""
        box = self.result_box
        box.insert("end", f"  {event_label(event)}  ", f"badge-{event}")
        box.insert("end", f"\t{text}")
        if date:
            box.insert("end", f"   {date}", "muted")
        box.insert("end", "\n")

    def show_results(self, results, automatic: bool = False):
        """Show the result of a check, from the Check button or the automatic check."""
        box = self.result_box
        box.configure(state="normal")
        box.delete("1.0", "end")
        total_changes = 0
        items = t(f"items.{self.service.items}")
        for r in results:
            if "error" in r:
                box.insert("end", f"{r['name']}  ", "heading")
                box.insert("end", t("result.error", error=r["error"]) + "\n", history.EVENT_REMOVED)
                continue
            p = self.playlists.get(r["playlist_id"])
            if p:
                p.update(name=r["name"], track_count=r["total"], last_checked=r["checked_at"])
            box.insert("end", f"{r['name']}  ", "heading")
            box.insert("end", f"{number(r['total'])} {items}  ·  ", "muted")
            if r["first_check"]:
                box.insert("end", t("result.initial") + "\n", "muted")
                for track in r["unavailable"]:
                    self._badge(history.EVENT_UNPLAYABLE, track_label(track))
                continue
            changes = (
                [(history.EVENT_ADDED, track) for track in r["added"]]
                + [(history.EVENT_REMOVED, track) for track in r["removed"]]
                + [(history.EVENT_UNPLAYABLE, track) for track in r["unplayable"]]
                + [(history.EVENT_PLAYABLE, track) for track in r["playable_again"]]
            )
            total_changes += len(changes)
            if not changes:
                box.insert("end", t("result.no_changes") + "\n", "muted")
                continue
            box.insert("end", t("result.changes", count=len(changes)) + "\n", "muted")
            for event, track in changes:
                added = t("result.added", date=short_date(track["added_at"])).strip() if track.get("added_at") else ""
                self._badge(event, track_label(track), added)
        box.configure(state="disabled")
        self.render()
        self.app.history.refresh()
        self.app.set_status(t("status.auto_check_done" if automatic else "status.check_done", count=len(results),
                              changes=total_changes))
