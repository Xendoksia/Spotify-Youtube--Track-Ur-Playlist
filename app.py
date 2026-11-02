"""
Playlist Tracker - graphical interface for Spotify and YouTube playlists.

Run with:  python app.py
(or double-click "Spotify Playlist Tracker.bat" on Windows)
"""

import threading
import tkinter as tk
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

import tracker
import youtube
from tracker import TrackerError, format_date, track_label

EVENT_LABELS = {
    tracker.EVENT_ADDED: "+ Added",
    tracker.EVENT_REMOVED: "− Removed",
    tracker.EVENT_UNPLAYABLE: "! Unplayable",
    tracker.EVENT_PLAYABLE: "✓ Playable again",
    tracker.EVENT_INITIAL: "• Initial snapshot",
}
EVENT_COLORS = {
    tracker.EVENT_ADDED: "#1a7f37",
    tracker.EVENT_REMOVED: "#c62828",
    tracker.EVENT_UNPLAYABLE: "#b26a00",
    tracker.EVENT_PLAYABLE: "#1565c0",
    tracker.EVENT_INITIAL: "#666666",
}
CHECKED, UNCHECKED = "☑", "☐"
ALL = "All"


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
    login_hint: str
    account: str


SPOTIFY = Service(
    name="Spotify", db_path=tracker.DB_PATH, connect=tracker.connect, parse_playlist_id=tracker.parse_playlist_id,
    playlist_url="https://open.spotify.com/playlist/{}", items="tracks", login_required=tracker.LoginRequired,
    has_credentials=lambda c: bool(c.get("CLIENT_ID") and c.get("CLIENT_SECRET")),
    session_user=lambda c: c.get("USER", "") if c.get("REFRESH_TOKEN") else None,
    unavailable_label=lambda: f"Not playable in {tracker.market()}",
    login_hint="The Spotify authorization page opened in your browser, press “Agree”…",
    account="Spotify",
)
YOUTUBE = Service(
    name="YouTube", db_path=youtube.DB_PATH, connect=youtube.connect, parse_playlist_id=youtube.parse_playlist_id,
    playlist_url=youtube.PLAYLIST_URL, items="videos", login_required=youtube.LoginRequired,
    has_credentials=youtube.has_credentials,
    session_user=lambda c: c.get("YOUTUBE_USER", "") if c.get("YOUTUBE_REFRESH_TOKEN") else None,
    unavailable_label=lambda: "Unavailable (deleted, private or blocked in your region)",
    login_hint="The Google sign-in page opened in your browser, choose your account and allow access…",
    account="Google",
)
SERVICES = (SPOTIFY, YOUTUBE)


class PlaylistPanel(ttk.Frame):
    """Playlist list, selection and check results for one service."""

    def __init__(self, app: "App", service: Service):
        super().__init__(app.tabs, padding=10)
        self.app = app
        self.service = service
        self.playlists: dict[str, dict] = {}
        self._build()
        self._load_tracked()
        self.update_login_status()

    def _build(self):
        name = self.service.name
        form = ttk.Frame(self)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        top = ttk.Frame(form)
        top.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        self.fetch_button = ttk.Button(top, text=f"Load my {name} playlists", command=self.load_my_playlists)
        self.fetch_button.pack(side="left")
        self.login_button = ttk.Button(top, command=self.login)
        self.login_button.pack(side="right")
        self.login_label = ttk.Label(top, foreground="#1a7f37")
        self.login_label.pack(side="right", padx=6)

        ttk.Label(form, text="or playlist link:").grid(row=1, column=0, sticky="w", pady=2)
        self.link_entry = ttk.Entry(form)
        self.link_entry.grid(row=1, column=1, sticky="ew", padx=6, pady=2)
        self.link_entry.bind("<Return>", lambda e: self.add_by_link())
        self.add_button = ttk.Button(form, text="Add", command=self.add_by_link)
        self.add_button.grid(row=1, column=2, sticky="ew", pady=2)

        ttk.Label(
            self, foreground="#666",
            text="Tick the playlists you want to track, then press “Check selected”.",
        ).pack(anchor="w", pady=(10, 4))

        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True)
        columns = ("tracked", "name", "owner", "tracks", "last_checked")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        for column, heading, width, anchor in (
            ("tracked", "Track", 60, "center"),
            ("name", "Playlist", 380, "w"),
            ("owner", "Owner", 160, "w"),
            ("tracks", self.service.items.capitalize(), 70, "center"),
            ("last_checked", "Last checked", 140, "center"),
        ):
            self.table.heading(column, text=heading)
            self.table.column(column, width=width, anchor=anchor, stretch=(column == "name"))
        self.table.tag_configure("tracked", background="#e8f5e9")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.table.bind("<Button-1>", self._on_row_click)
        self.table.bind("<space>", lambda e: self._toggle_selected())
        self.table.bind("<Double-1>", self._open_playlist)

        footer = ttk.Frame(self)
        footer.pack(fill="x", pady=(8, 0))
        ttk.Button(footer, text="Select all", command=lambda: self._set_all(True)).pack(side="left")
        ttk.Button(footer, text="Clear selection", command=lambda: self._set_all(False)).pack(side="left", padx=6)
        self.check_button = ttk.Button(footer, text="▶  Check selected", command=self.check)
        self.check_button.pack(side="right")

        ttk.Label(self, text="Last check result:").pack(anchor="w", pady=(10, 2))
        self.result_box = tk.Text(self, height=9, wrap="word", font=("Segoe UI", 10),
                                  relief="solid", borderwidth=1, state="disabled")
        self.result_box.pack(fill="x")
        for event, color in EVENT_COLORS.items():
            self.result_box.tag_configure(event, foreground=color)
        self.result_box.tag_configure("heading", font=("Segoe UI", 10, "bold"))

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
        for playlist_id, p in ordered:
            self.table.insert(
                "", "end", iid=playlist_id, tags=("tracked",) if p["tracked"] else (),
                values=(CHECKED if p["tracked"] else UNCHECKED, p["name"], p["owner"],
                        p["track_count"], format_date(p["last_checked"]) or "—"),
            )
        self.check_button.configure(text=f"▶  Check selected ({len(self.tracked_names())})")
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
            self.login_label.configure(text=f"● Logged in: {user}")
            self.login_button.configure(text="Switch account")
        else:
            self.login_label.configure(text="")
            self.login_button.configure(text=f"Log in with {self.service.account}")

    def run(self, task, on_success):
        self.app.run_in_background(self, task, on_success)

    def login(self):
        self.app.set_status(self.service.login_hint)

        def on_success(user):
            self.app.set_status(f"Logged in to {self.service.name} as {user}")
            self.load_my_playlists()

        self.run(lambda: self.service.connect().login(), on_success)

    def load_my_playlists(self):
        self.app.set_status(f"Loading {self.service.name} playlists…")

        def on_success(result):
            readable, others = result
            for p in readable:
                existing = self.playlists.get(p["id"], {})
                self.playlists[p["id"]] = {
                    "name": p["name"], "owner": p["owner"], "track_count": p["track_count"],
                    "tracked": existing.get("tracked", False), "last_checked": existing.get("last_checked"),
                }
            self.render()
            note = (f" ({len(others)} followed playlists by other users are hidden: "
                    f"Spotify does not expose their tracks)") if others else ""
            self.app.set_status(f"{len(readable)} {self.service.name} playlists found.{note}")

        self.run(lambda: self.service.connect().my_playlists(), on_success)

    def add_by_link(self):
        link = self.link_entry.get().strip()
        if not link:
            return
        try:
            playlist_id = self.service.parse_playlist_id(link)
        except TrackerError as e:
            messagebox.showerror("Error", str(e), parent=self)
            return
        self.app.set_status("Fetching playlist info…")

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
            self.app.set_status(f"“{name}” is now tracked.")

        self.run(lambda: self.service.connect().playlist_name(playlist_id), on_success)

    def check(self):
        selected = [pid for pid, p in self.playlists.items() if p["tracked"]]
        if not selected:
            messagebox.showinfo("Nothing selected", "Tick the playlists you want to track first.", parent=self)
            return

        def task():
            client = self.service.connect()
            results = []
            for i, playlist_id in enumerate(selected, 1):
                name = self.playlists[playlist_id]["name"]
                self.app.after(0, lambda i=i, name=name:
                               self.app.set_status(f"Checking ({i}/{len(selected)}): {name}"))
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
        items = self.service.items
        for r in results:
            if "error" in r:
                box.insert("end", f"{r['name']}: ", "heading")
                box.insert("end", f"ERROR – {r['error']}\n", tracker.EVENT_REMOVED)
                continue
            p = self.playlists.get(r["playlist_id"])
            if p:
                p.update(name=r["name"], track_count=r["total"], last_checked=r["checked_at"])
            box.insert("end", f"{r['name']} ({r['total']} {items}): ", "heading")
            if r["first_check"]:
                box.insert("end", "initial snapshot recorded, changes will appear from the next check on.\n",
                           tracker.EVENT_INITIAL)
                for t in r["unavailable"]:
                    box.insert("end", f"    ! {self.service.unavailable_label()}: {track_label(t)}\n",
                               tracker.EVENT_UNPLAYABLE)
                continue
            changes = (
                [(tracker.EVENT_ADDED, t) for t in r["added"]]
                + [(tracker.EVENT_REMOVED, t) for t in r["removed"]]
                + [(tracker.EVENT_UNPLAYABLE, t) for t in r["unplayable"]]
                + [(tracker.EVENT_PLAYABLE, t) for t in r["playable_again"]]
            )
            total_changes += len(changes)
            if not changes:
                box.insert("end", "no changes.\n")
                continue
            box.insert("end", f"{len(changes)} changes\n")
            for event, t in changes:
                added = f"   (added: {format_date(t['added_at'])})" if t.get("added_at") else ""
                box.insert("end", f"    {EVENT_LABELS[event]:<18} {track_label(t)}{added}\n", event)
        box.configure(state="disabled")
        self.render()
        self.app.refresh_history()
        self.app.set_status(f"Check complete: {len(results)} playlists, {total_changes} changes.")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Playlist Tracker")
        self.geometry("1050x700")
        self.minsize(800, 500)

        self.busy = False
        self.panels: dict[str, PlaylistPanel] = {}

        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Treeview", rowheight=24)

        self._build_ui()
        self.refresh_history()

        config = tracker.load_config()
        if not any(s.has_credentials(config) for s in SERVICES):
            self.after(200, self.open_settings)

    def _build_ui(self):
        header = ttk.Frame(self, padding=(10, 8, 10, 0))
        header.pack(fill="x")
        ttk.Button(header, text="⚙ Settings", command=self.open_settings).pack(side="right")
        self.status_label = ttk.Label(header, text="Ready.", foreground="#555")
        self.status_label.pack(side="left")

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=8)
        # The history tab is built first because panels update its playlist filter while loading
        self._build_history_tab()
        for index, service in enumerate(SERVICES):
            panel = PlaylistPanel(self, service)
            self.panels[service.name] = panel
            self.tabs.insert(index, panel, text=f"  {service.name}  ")
        self.tabs.select(0)
        self.update_history_filter()

    def _build_history_tab(self):
        tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(tab, text="  History  ")

        toolbar = ttk.Frame(tab)
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="Source:").pack(side="left")
        self.source_filter = ttk.Combobox(toolbar, state="readonly", width=10, values=[s.name for s in SERVICES])
        self.source_filter.current(0)
        self.source_filter.pack(side="left", padx=6)
        self.source_filter.bind("<<ComboboxSelected>>", lambda e: self._on_source_changed())
        ttk.Label(toolbar, text="Playlist:").pack(side="left", padx=(12, 0))
        self.playlist_filter = ttk.Combobox(toolbar, state="readonly", width=40)
        self.playlist_filter.pack(side="left", padx=6)
        self.playlist_filter.bind("<<ComboboxSelected>>", lambda e: self.refresh_history())
        ttk.Label(toolbar, text="Event:").pack(side="left", padx=(12, 0))
        self.event_filter = ttk.Combobox(toolbar, state="readonly", width=18,
                                         values=[ALL] + list(EVENT_LABELS.values()))
        self.event_filter.current(0)
        self.event_filter.pack(side="left", padx=6)
        self.event_filter.bind("<<ComboboxSelected>>", lambda e: self.refresh_history())
        ttk.Button(toolbar, text="Export CSV", command=self._export_csv).pack(side="right")
        ttk.Button(toolbar, text="Refresh", command=self.refresh_history).pack(side="right", padx=6)

        table_frame = ttk.Frame(tab)
        table_frame.pack(fill="both", expand=True, pady=(8, 0))
        columns = ("checked_at", "playlist", "event", "track", "added_at")
        self.history_table = ttk.Treeview(table_frame, columns=columns, show="headings")
        for column, heading, width in (
            ("checked_at", "Detected", 130),
            ("playlist", "Playlist", 200),
            ("event", "Event", 120),
            ("track", "Track / video", 400),
            ("added_at", "Added to playlist", 130),
        ):
            self.history_table.heading(column, text=heading)
            self.history_table.column(column, width=width, stretch=(column == "track"))
        for event, color in EVENT_COLORS.items():
            self.history_table.tag_configure(event, foreground=color)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.history_table.yview)
        self.history_table.configure(yscrollcommand=scrollbar.set)
        self.history_table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Label(
            tab, foreground="#666",
            text="“Detected” is the time of the check that noticed the change. "
                 "The change happened between the previous check and this time.",
        ).pack(anchor="w", pady=(6, 0))

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
                error = f"Unexpected error: {e!r}"
            self.after(0, lambda: self._on_task_done(panel, on_success, result, error, login_required))

        threading.Thread(target=worker, daemon=True).start()

    def _on_task_done(self, panel, on_success, result, error, login_required):
        self._set_busy(False)
        panel.update_login_status()
        if login_required:
            self.set_status("Login required.")
            if messagebox.askyesno("Login required", f"{error}\n\nLog in now?", parent=self):
                panel.login()
        elif error:
            self.set_status("Error.")
            messagebox.showerror("Error", error, parent=self)
        else:
            on_success(result)

    def _history_panel(self) -> PlaylistPanel:
        return self.panels[self.source_filter.get()]

    def update_history_filter(self):
        panel = self.panels.get(self.source_filter.get())
        if not panel:
            return
        self.playlist_filter.configure(values=[ALL] + panel.tracked_names())
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
        if selected_playlist and selected_playlist != ALL:
            playlist_id = next((k for k, v in panel.playlists.items() if v["name"] == selected_playlist), None)
        selected_event = self.event_filter.get()
        event_code = next((k for k, v in EVENT_LABELS.items() if v == selected_event), None)

        self.history_table.delete(*self.history_table.get_children())
        for r in tracker.get_events(playlist_id, panel.service.db_path):
            if event_code and r["event"] != event_code:
                continue
            self.history_table.insert("", "end", tags=(r["event"],), values=(
                format_date(r["checked_at"]), r["playlist"] or "", EVENT_LABELS.get(r["event"], r["event"]),
                track_label(r), format_date(r["added_at"]),
            ))

    def _export_csv(self):
        service = self._history_panel().service
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".csv", initialfile=f"{service.name.lower()}_history.csv",
            filetypes=[("CSV (Excel)", "*.csv")],
        )
        if path:
            count = tracker.export_csv(path, service.db_path)
            self.set_status(f"{count} {service.name} records exported to {path}")

    def open_settings(self, service: Service = SPOTIFY):
        window = tk.Toplevel(self)
        window.title("API settings")
        window.transient(self)
        window.resizable(False, False)
        notebook = ttk.Notebook(window)
        notebook.pack(fill="both", padx=10, pady=(10, 0))
        config = tracker.load_config()

        def link(parent, text, url, row):
            label = ttk.Label(parent, text=text, foreground="#1565c0", cursor="hand2")
            label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(4, 10))
            label.bind("<Button-1>", lambda e: webbrowser.open(url))

        def field(parent, label, key, row, secret=False):
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
            entry = ttk.Entry(parent, width=50, show="•" if secret else "")
            entry.insert(0, config.get(key, ""))
            entry.grid(row=row, column=1, pady=3)
            return entry

        spotify_tab = ttk.Frame(notebook, padding=14)
        notebook.add(spotify_tab, text="  Spotify  ")
        ttk.Label(spotify_tab, justify="left", text=(
            "1) Log in at developer.spotify.com/dashboard with your Spotify account\n"
            f"2) “Create app” → enter a name, Redirect URI: {tracker.REDIRECT_URI}\n"
            "3) Tick “Web API”, save → copy the Client ID and Client Secret from Settings"
        )).grid(row=0, column=0, columnspan=2, sticky="w")
        link(spotify_tab, "Open Dashboard", "https://developer.spotify.com/dashboard", 1)
        spotify_entries = {
            "CLIENT_ID": field(spotify_tab, "Client ID:", "CLIENT_ID", 2),
            "CLIENT_SECRET": field(spotify_tab, "Client Secret:", "CLIENT_SECRET", 3, secret=True),
        }

        youtube_tab = ttk.Frame(notebook, padding=14)
        notebook.add(youtube_tab, text="  YouTube  ")
        ttk.Label(youtube_tab, justify="left", text=(
            "1) Open console.cloud.google.com, create a project and enable “YouTube Data API v3”\n"
            "2) Credentials → Create credentials → API key. This is enough for public and unlisted playlists.\n"
            "3) Optional, for private playlists and “Load my playlists”: set up the OAuth consent screen\n"
            "    (add your Google account as a test user), then Create credentials → OAuth client ID → Desktop app"
        )).grid(row=0, column=0, columnspan=2, sticky="w")
        link(youtube_tab, "Open Google Cloud Console", "https://console.cloud.google.com/apis/library/youtube.googleapis.com", 1)
        youtube_entries = {
            "YOUTUBE_API_KEY": field(youtube_tab, "API key:", "YOUTUBE_API_KEY", 2, secret=True),
            "YOUTUBE_CLIENT_ID": field(youtube_tab, "OAuth Client ID:", "YOUTUBE_CLIENT_ID", 3),
            "YOUTUBE_CLIENT_SECRET": field(youtube_tab, "OAuth Client Secret:", "YOUTUBE_CLIENT_SECRET", 4, secret=True),
        }

        def save():
            updated = tracker.load_config()
            values = {k: e.get().strip() for k, e in {**spotify_entries, **youtube_entries}.items()}
            for id_key, secret_key, tab in (("CLIENT_ID", "CLIENT_SECRET", spotify_tab),
                                            ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", youtube_tab)):
                if bool(values[id_key]) != bool(values[secret_key]):
                    notebook.select(tab)
                    messagebox.showwarning("Missing values", "Enter both the Client ID and the Client Secret.",
                                           parent=window)
                    return
            if not any(values.values()):
                messagebox.showwarning("Missing values", "Enter the credentials of at least one service.",
                                       parent=window)
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
            tracker.save_config(updated)
            window.destroy()
            for panel in self.panels.values():
                panel.update_login_status()
            self.set_status("Settings saved.")

        ttk.Button(window, text="Save", command=save).pack(anchor="e", padx=10, pady=10)
        notebook.select(youtube_tab if service is YOUTUBE else spotify_tab)
        window.grab_set()


if __name__ == "__main__":
    App().mainloop()
