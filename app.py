"""
Playlist Tracker - graphical interface for Spotify and YouTube playlists.

Run with:  python app.py
(or double-click "Spotify Playlist Tracker.bat" on Windows)
"""

import re
import queue
import sys
import threading
import tkinter as tk
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

import artwork
import background
import i18n
import nowplaying
import theme
import tracker
import youtube
from i18n import t
from listening_view import ListeningView, set_tracking, tracking_enabled
from mini_player import MiniPlayer
from theme import FONT_BOLD, P, px, text_box
from tracker import TrackerError, format_date, track_label

# Start with the monthly summary open, to look at it before it opens by itself
SUMMARY_FLAG = "--summary"
EVENTS = (tracker.EVENT_ADDED, tracker.EVENT_REMOVED, tracker.EVENT_UNPLAYABLE, tracker.EVENT_PLAYABLE,
          tracker.EVENT_INITIAL)
EVENT_COLOR_KEYS = {
    tracker.EVENT_ADDED: "added",
    tracker.EVENT_REMOVED: "removed",
    tracker.EVENT_UNPLAYABLE: "unplayable",
    tracker.EVENT_PLAYABLE: "playable",
    tracker.EVENT_INITIAL: "initial",
}
CHECKED, UNCHECKED = "☑", "☐"


def event_label(event: str) -> str:
    return t(f"event.{event}") if event in EVENTS else event


def event_color(event: str) -> str:
    return getattr(P, EVENT_COLOR_KEYS[event])


@dataclass
class Service:
    name: str
    db_path: Path
    connect: Callable
    parse_playlist_id: Callable[[str], str]
    playlist_url: str
    items: str
    login_required: type
    has_credentials: Callable[[dict], bool]
    session_user: Callable[[dict], "str | None"]
    unavailable_label: Callable[[], str]
    account: str
    accent: str
    accent_active: str

    @property
    def key(self) -> str:
        return self.name.lower()

    @property
    def tint(self) -> str:
        return getattr(P, f"{self.key}_tint")


SPOTIFY = Service(
    name="Spotify", db_path=tracker.DB_PATH, connect=tracker.connect, parse_playlist_id=tracker.parse_playlist_id,
    playlist_url="https://open.spotify.com/playlist/{}", items="tracks", login_required=tracker.LoginRequired,
    has_credentials=lambda c: bool(c.get("CLIENT_ID") and c.get("CLIENT_SECRET")),
    session_user=lambda c: c.get("USER", "") if c.get("REFRESH_TOKEN") else None,
    unavailable_label=lambda: t("unavailable.spotify", market=tracker.market()),
    account="Spotify",
    accent="#1aa34a", accent_active="#168a3f",
)
YOUTUBE = Service(
    name="YouTube", db_path=youtube.DB_PATH, connect=youtube.connect, parse_playlist_id=youtube.parse_playlist_id,
    playlist_url=youtube.PLAYLIST_URL, items="videos", login_required=youtube.LoginRequired,
    has_credentials=youtube.has_credentials,
    session_user=lambda c: c.get("YOUTUBE_USER", "") if c.get("YOUTUBE_REFRESH_TOKEN") else None,
    unavailable_label=lambda: t("unavailable.youtube"),
    account="Google",
    accent="#e62117", accent_active="#c41b12",
)
SERVICES = (SPOTIFY, YOUTUBE)


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
        for p in tracker.tracked_playlists(self.service.db_path):
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
        self.app.update_history_filter()

    def tracked_names(self):
        return sorted((p["name"] for p in self.playlists.values() if p["tracked"]), key=str.lower)

    def _set_tracked(self, playlist_id, tracked):
        p = self.playlists[playlist_id]
        p["tracked"] = tracked
        tracker.set_tracked(playlist_id, p["name"], tracked, self.service.db_path)

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
        user = self.service.session_user(tracker.load_config())
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
            tracker.set_tracked(playlist_id, name, True, self.service.db_path)
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
                    results.append(tracker.check_playlist(client, playlist_id, self.service.db_path))
                except self.service.login_required:
                    raise
                except TrackerError as e:
                    results.append({"name": name, "error": str(e)})
            return results

        self.run(task, self._on_check_done)

    def _on_check_done(self, results):
        box = self.result_box
        box.configure(state="normal")
        box.delete("1.0", "end")
        total_changes = 0
        items = t(f"items.{self.service.items}")
        for r in results:
            if "error" in r:
                box.insert("end", f"{r['name']}: ", "heading")
                box.insert("end", t("result.error", error=r["error"]) + "\n", tracker.EVENT_REMOVED)
                continue
            p = self.playlists.get(r["playlist_id"])
            if p:
                p.update(name=r["name"], track_count=r["total"], last_checked=r["checked_at"])
            box.insert("end", t("result.heading", name=r["name"], total=r["total"], items=items), "heading")
            if r["first_check"]:
                box.insert("end", t("result.initial") + "\n", tracker.EVENT_INITIAL)
                for track in r["unavailable"]:
                    box.insert("end", f"    ! {self.service.unavailable_label()}: {track_label(track)}\n",
                               tracker.EVENT_UNPLAYABLE)
                continue
            changes = (
                [(tracker.EVENT_ADDED, track) for track in r["added"]]
                + [(tracker.EVENT_REMOVED, track) for track in r["removed"]]
                + [(tracker.EVENT_UNPLAYABLE, track) for track in r["unplayable"]]
                + [(tracker.EVENT_PLAYABLE, track) for track in r["playable_again"]]
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
        self.app.refresh_history()
        self.app.set_status(t("status.check_done", count=len(results), changes=total_changes))


class App(tk.Tk):
    def __init__(self, local_tracker: nowplaying.LocalTracker, commands: queue.Queue[str],
                 tray: background.Tray, hidden: bool = False):
        super().__init__()
        self.local_tracker = local_tracker
        self.commands = commands
        self.tray = tray
        config = tracker.load_config()
        i18n.set_language(config.get("LANGUAGE"))
        self.title(t("app.title"))
        tray.set_title(t("app.title"))

        self.busy = False
        self.restart = False
        self.panels: dict[str, PlaylistPanel] = {}
        self.sections: dict[str, tuple[ttk.Frame, ttk.Button]] = {}

        theme.apply_theme(self, config.get("THEME"), {s.name: (s.accent, s.accent_active) for s in SERVICES})
        # After the theme, which sets the scale for this screen
        theme.place_window(self, 1100, 780)
        self.minsize(px(860), px(600))

        if background.TRAY_AVAILABLE:
            from PIL import ImageTk
            self._icon = ImageTk.PhotoImage(background.icon_image(64))
            self.iconphoto(True, self._icon)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_ui()
        self.refresh_history()
        # Plays stored without a listening time by an earlier version get their track's length
        threading.Thread(target=artwork.fill_missing_lengths, name="lengths", daemon=True,
                         args=(lambda: self.after(0, self.listening.mark_stale),)).start()
        self._poll_commands()

        if hidden:
            # Started with Windows: keep running in the tray, or minimized when there is no tray
            if background.close_to_tray(config):
                self.withdraw()
            else:
                self.iconify()
        elif not any(s.has_credentials(config) for s in SERVICES):
            self.after(200, self.open_settings)
        elif SUMMARY_FLAG in sys.argv[1:]:
            self.after(500, lambda: self._open_monthly_summary(force=True))
        else:
            self.after(500, self._open_monthly_summary)

    def on_close(self):
        if not background.close_to_tray(tracker.load_config()):
            self.quit_app()
            return
        self.withdraw()
        if not self.tray.hint_shown:
            self.tray.hint_shown = True
            self.tray.notify(t("tray.hint"))

    def show_window(self):
        self.deiconify()
        self.state("normal")
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, lambda: self.attributes("-topmost", False))
        self.focus_force()
        # Brought back from the tray on the first days of a month: the summary of the month before
        self.after(500, self._open_monthly_summary)

    def quit_app(self):
        self.restart = False
        self.destroy()

    def _poll_commands(self):
        # Requests from the tray icon and from copies of the app started later, which run on other threads
        while True:
            try:
                command = self.commands.get_nowait()
            except queue.Empty:
                break
            if command == "show":
                self.show_window()
            elif command == "quit":
                self.quit_app()
                return
        self.after(200, self._poll_commands)

    def _build_ui(self):
        header = ttk.Frame(self, padding=(px(16), px(12), px(16), px(4)))
        header.pack(fill="x")
        ttk.Label(header, text=t("app.title"), style="Title.TLabel").pack(side="left")
        ttk.Button(header, text=t("button.settings"), command=self.open_settings).pack(side="right")
        nav = ttk.Frame(header, padding=px(4), style="Nav.TFrame")
        nav.pack(side="left", padx=(px(24), 0))
        self.status_label = ttk.Label(header, text=t("status.ready"), style="Muted.TLabel")
        self.status_label.pack(side="left", padx=(px(16), 0), pady=(px(4), 0))
        self.mini_player = MiniPlayer(self, self.local_tracker, self.open_track_page, header)

        # Playlist tracking and listening statistics are separate sections with their own tabs
        playlist_section = ttk.Frame(self)
        self.tabs = ttk.Notebook(playlist_section)
        self.tabs.pack(fill="both", expand=True)
        self.listening = ListeningView(self, self, self.local_tracker)
        for name, frame in (("playlists", playlist_section), ("listening", self.listening)):
            button = ttk.Button(nav, text=t(f"nav.{name}"), style="Nav.TButton",
                                command=lambda name=name: self.show_section(name))
            button.pack(side="left")
            self.sections[name] = (frame, button)
        # The history tab is built first because panels update its playlist filter while loading
        self._build_history_tab()
        for index, service in enumerate(SERVICES):
            panel = PlaylistPanel(self, service)
            self.panels[service.name] = panel
            self.tabs.insert(index, panel, text=f"  {service.name}  ")
        self.tabs.select(0)
        self.update_history_filter()
        self.show_section("playlists")

    def _open_monthly_summary(self, force: bool = False):
        """On the first days of a month, show the summary of the month before once (see wrapped_view.SHOW_DAYS);
        force shows the last month with plays on any day."""
        import wrapped_view
        due = wrapped_view.month_to_show() if force else wrapped_view.auto_open_due()
        if due:
            if not force:
                wrapped_view.mark_shown(due[0])
            self.show_section("listening")
            self.listening.tabs.select(self.listening.stats)
            self.listening.stats.open_wrapped(due)

    def open_track_page(self, track_key: str):
        self.show_section("listening")
        self.listening.tabs.select(self.listening.stats)
        self.listening.stats.open_detail("track_key", track_key)

    def show_section(self, name):
        for key, (frame, button) in self.sections.items():
            if key == name:
                frame.pack(fill="both", expand=True, padx=px(16), pady=(px(8), px(16)))
                button.configure(style="NavSelected.TButton")
            else:
                frame.pack_forget()
                button.configure(style="Nav.TButton")

    def _build_history_tab(self):
        tab = ttk.Frame(self.tabs, padding=px(16), style="Card.TFrame")
        self.tabs.add(tab, text=f"  {t('tab.history')}  ")

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
        self.playlist_filter.bind("<<ComboboxSelected>>", lambda e: self.refresh_history())
        ttk.Label(toolbar, text=t("history.event"), style="Card.TLabel").pack(side="left", padx=(px(12), 0))
        self.event_filter = ttk.Combobox(toolbar, state="readonly", width=20,
                                         values=[t("history.all")] + [event_label(e) for e in EVENTS])
        self.event_filter.current(0)
        self.event_filter.pack(side="left", padx=px(8))
        self.event_filter.bind("<<ComboboxSelected>>", lambda e: self.refresh_history())
        ttk.Button(toolbar, text=t("history.export"), command=self._export_csv).pack(side="right")
        ttk.Button(toolbar, text=t("history.refresh"), command=self.refresh_history).pack(side="right", padx=px(8))

        table_frame = ttk.Frame(tab, style="Card.TFrame")
        table_frame.pack(fill="both", expand=True, pady=(px(12), 0))
        columns = ("checked_at", "playlist", "event", "track", "added_at")
        self.history_table = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        for column, heading, width in (
            ("checked_at", t("history.detected"), 130),
            ("playlist", t("column.playlist"), 200),
            ("event", t("history.event_column"), 140),
            ("track", t("history.item"), 400),
            ("added_at", t("history.added"), 130),
        ):
            self.history_table.heading(column, text=heading, anchor="w")
            self.history_table.column(column, width=px(width), stretch=(column == "track"))
        self.history_table.tag_configure("odd", background=P.stripe)
        for event in EVENTS:
            self.history_table.tag_configure(event, foreground=event_color(event))
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.history_table.yview)
        self.history_table.configure(yscrollcommand=scrollbar.set)
        self.history_table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Label(tab, style="CardMuted.TLabel", text=t("history.note")).pack(anchor="w", pady=(px(8), 0))

    def set_status(self, text):
        self.status_label.configure(text=text)

    def _set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        for panel in self.panels.values():
            for button in panel.buttons:
                button.configure(state=state)
        self.configure(cursor="watch" if busy else "")

    def run_in_background(self, panel, task, on_success):
        """Run network work on a worker thread so the window stays responsive."""
        if self.busy:
            return
        if not panel.service.has_credentials(tracker.load_config()):
            self.open_settings(panel.service)
            return
        self._set_busy(True)

        def worker():
            result, error, login_required = None, None, False
            try:
                result = task()
            except panel.service.login_required as e:
                error, login_required = str(e), True
            except TrackerError as e:
                error = str(e)
            except Exception as e:
                error = t("error.unexpected", error=repr(e))
            self.after(0, lambda: self._on_task_done(panel, on_success, result, error, login_required))

        threading.Thread(target=worker, daemon=True).start()

    def _on_task_done(self, panel, on_success, result, error, login_required):
        self._set_busy(False)
        panel.update_login_status()
        if login_required:
            self.set_status(t("status.login_required"))
            if messagebox.askyesno(t("dialog.login_required"), t("dialog.login_now", error=error), parent=self):
                panel.login()
        elif error:
            self.set_status(t("status.error"))
            messagebox.showerror(t("dialog.error"), error, parent=self)
        else:
            on_success(result)

    def _history_panel(self) -> PlaylistPanel:
        return self.panels[self.source_filter.get()]

    def update_history_filter(self):
        panel = self.panels.get(self.source_filter.get())
        if not panel:
            return
        self.playlist_filter.configure(values=[t("history.all")] + panel.tracked_names())
        if not self.playlist_filter.get():
            self.playlist_filter.current(0)

    def _on_source_changed(self):
        self.playlist_filter.set("")
        self.update_history_filter()
        self.refresh_history()

    def refresh_history(self):
        if not self.panels:
            return
        panel = self._history_panel()
        selected_playlist = self.playlist_filter.get()
        playlist_id = None
        if self.playlist_filter.current() > 0:
            playlist_id = next((k for k, v in panel.playlists.items() if v["name"] == selected_playlist), None)
        event_index = self.event_filter.current()
        event_code = EVENTS[event_index - 1] if event_index > 0 else None

        self.history_table.delete(*self.history_table.get_children())
        rows = [r for r in tracker.get_events(playlist_id, panel.service.db_path)
                if not event_code or r["event"] == event_code]
        for index, r in enumerate(rows):
            tags = (r["event"], "odd") if index % 2 else (r["event"],)
            item = track_label(r)
            count = re.match(r"(\d+) ", r["name"] or "")
            if r["event"] == tracker.EVENT_INITIAL and count:
                item = t("history.initial_count", count=count.group(1))
            self.history_table.insert("", "end", tags=tags, values=(
                format_date(r["checked_at"]), r["playlist"] or "", event_label(r["event"]),
                item, format_date(r["added_at"]),
            ))

    def _export_csv(self):
        service = self._history_panel().service
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".csv", initialfile=f"{service.key}_history.csv",
            filetypes=[(t("csv.filetype"), "*.csv")],
        )
        if path:
            count = tracker.export_csv(path, service.db_path)
            self.set_status(t("status.exported", count=count, service=service.name, path=path))

    def open_settings(self, service: Service = SPOTIFY):
        window = tk.Toplevel(self)
        window.title(t("settings.title"))
        window.transient(self)
        window.resizable(False, False)
        window.configure(background=P.bg)
        theme.dark_title_bar(window)
        notebook = ttk.Notebook(window)
        notebook.pack(fill="both", padx=px(16), pady=(px(16), 0))
        config = tracker.load_config()

        def link(parent, text, url, row):
            label = ttk.Label(parent, text=text, style="Card.TLabel", foreground=P.focus, cursor="hand2")
            label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(px(4), px(12)))
            label.bind("<Button-1>", lambda e: webbrowser.open(url))

        def field(parent, label, key, row, secret=False):
            ttk.Label(parent, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=px(4))
            entry = ttk.Entry(parent, width=50, show="•" if secret else "")
            entry.insert(0, config.get(key, ""))
            entry.grid(row=row, column=1, sticky="ew", pady=px(4))
            return entry

        def choice(parent, label, options, selected, row):
            ttk.Label(parent, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=px(4))
            box = ttk.Combobox(parent, state="readonly", width=24, values=list(options.values()))
            box.current(list(options).index(selected))
            box.grid(row=row, column=1, sticky="w", pady=px(4), padx=(px(8), 0))
            return lambda: list(options)[box.current()]

        spotify_tab = ttk.Frame(notebook, padding=px(16), style="Card.TFrame")
        notebook.add(spotify_tab, text="  Spotify  ")
        ttk.Label(spotify_tab, justify="left", style="CardMuted.TLabel",
                  text=t("settings.spotify_steps", redirect_uri=tracker.REDIRECT_URI)
                  ).grid(row=0, column=0, columnspan=2, sticky="w")
        link(spotify_tab, t("settings.open_dashboard"), "https://developer.spotify.com/dashboard", 1)
        spotify_entries = {
            "CLIENT_ID": field(spotify_tab, t("settings.client_id"), "CLIENT_ID", 2),
            "CLIENT_SECRET": field(spotify_tab, t("settings.client_secret"), "CLIENT_SECRET", 3, secret=True),
        }

        youtube_tab = ttk.Frame(notebook, padding=px(16), style="Card.TFrame")
        notebook.add(youtube_tab, text="  YouTube  ")
        ttk.Label(youtube_tab, justify="left", style="CardMuted.TLabel", text=t("settings.youtube_steps")
                  ).grid(row=0, column=0, columnspan=2, sticky="w")
        link(youtube_tab, t("settings.open_console"),
             "https://console.cloud.google.com/apis/library/youtube.googleapis.com", 1)
        youtube_entries = {
            "YOUTUBE_API_KEY": field(youtube_tab, t("settings.api_key"), "YOUTUBE_API_KEY", 2, secret=True),
            "YOUTUBE_CLIENT_ID": field(youtube_tab, t("settings.oauth_client_id"), "YOUTUBE_CLIENT_ID", 3),
            "YOUTUBE_CLIENT_SECRET": field(youtube_tab, t("settings.oauth_client_secret"),
                                           "YOUTUBE_CLIENT_SECRET", 4, secret=True),
        }

        general_tab = ttk.Frame(notebook, padding=px(16), style="Card.TFrame")
        notebook.add(general_tab, text=f"  {t('settings.general')}  ")
        current_theme = config.get("THEME") if config.get("THEME") in theme.THEMES else "system"
        get_language = choice(general_tab, t("settings.language"), i18n.LANGUAGES, i18n.current(), 0)
        get_theme = choice(general_tab, t("settings.theme"), {k: t(f"theme.{k}") for k in theme.THEMES},
                           current_theme, 1)
        tray_var = tk.BooleanVar(value=background.close_to_tray(config))
        ttk.Checkbutton(general_tab, text=t("settings.close_to_tray"), variable=tray_var,
                        style="Card.TCheckbutton", state="normal" if background.TRAY_AVAILABLE else "disabled"
                        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(px(12), px(4)))
        autostart_var = tk.BooleanVar(value=background.autostart_enabled())
        ttk.Checkbutton(general_tab, text=t("settings.autostart"), variable=autostart_var,
                        style="Card.TCheckbutton",
                        state="normal" if background.autostart_supported() else "disabled"
                        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=px(4))
        ttk.Label(general_tab, text=t("settings.restart_note"), style="CardMuted.TLabel"
                  ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(px(12), 0))

        def save():
            updated = tracker.load_config()
            values = {k: e.get().strip() for k, e in {**spotify_entries, **youtube_entries}.items()}
            for id_key, secret_key, tab in (("CLIENT_ID", "CLIENT_SECRET", spotify_tab),
                                            ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", youtube_tab)):
                if bool(values[id_key]) != bool(values[secret_key]):
                    notebook.select(tab)
                    messagebox.showwarning(t("settings.missing"), t("settings.missing_pair"), parent=window)
                    return
            # A session issued for different app credentials is no longer valid
            for keys, token_key in ((("CLIENT_ID", "CLIENT_SECRET"), "REFRESH_TOKEN"),
                                    (("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET"), "YOUTUBE_REFRESH_TOKEN")):
                if any(values[k] != config.get(k, "") for k in keys):
                    updated.pop(token_key, None)
            for key, value in values.items():
                if value:
                    updated[key] = value
                else:
                    updated.pop(key, None)
            appearance_changed = get_language() != i18n.current() or get_theme() != current_theme
            updated["LANGUAGE"], updated["THEME"] = get_language(), get_theme()
            if background.TRAY_AVAILABLE:
                updated["CLOSE_TO_TRAY"] = tray_var.get()
            tracker.save_config(updated)
            if autostart_var.get() != background.autostart_enabled():
                try:
                    background.set_autostart(autostart_var.get())
                except OSError as error:
                    messagebox.showerror(t("settings.title"), t("settings.autostart_failed", error=error),
                                         parent=window)
            window.destroy()
            if appearance_changed:
                # Rebuild the whole window so every widget picks up the new texts and colors
                self.restart = True
                self.destroy()
                return
            for panel in self.panels.values():
                panel.update_login_status()
            self.set_status(t("status.saved"))

        ttk.Button(window, text=t("settings.save"), command=save, style="Accent.TButton"
                   ).pack(anchor="e", padx=px(16), pady=px(16))
        notebook.select(youtube_tab if service is YOUTUBE else spotify_tab)
        window.grab_set()


def main():
    theme.make_dpi_aware()
    i18n.set_language(tracker.load_config().get("LANGUAGE"))
    instance = background.SingleInstance()
    if not instance.acquire():
        # Already running: a second tracker would record every song twice, so show the open window instead
        if not background.start_minimized():
            instance.notify_running()
        return

    # The tracker and tray icon outlive windows rebuilt after a language or theme change,
    # so a song keeps being one play
    local_tracker = nowplaying.LocalTracker()
    if tracking_enabled(tracker.load_config()):
        local_tracker.start()
    commands = instance.requests
    tray = background.Tray(commands, is_paused=lambda: not local_tracker.enabled,
                           set_paused=lambda paused: set_tracking(local_tracker, not paused))
    tray.start()
    hidden = background.start_minimized()
    try:
        while True:
            app = App(local_tracker, commands, tray, hidden)
            app.mainloop()
            hidden = False
            if not app.restart:
                break
    finally:
        tray.stop()
        local_tracker.stop()
        instance.release()


if __name__ == "__main__":
    main()
