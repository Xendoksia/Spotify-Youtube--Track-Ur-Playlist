"""
The main window: playlist tracking and listening statistics as two sections, with the mini player along
the bottom.
"""

from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from playlist_tracker import background
from playlist_tracker.core import i18n
from playlist_tracker.core.config import load_config
from playlist_tracker.core.errors import TrackerError
from playlist_tracker.core.i18n import t
from playlist_tracker.music import artwork, nowplaying
from playlist_tracker.ui import theme
from playlist_tracker.ui.history_tab import HistoryTab
from playlist_tracker.ui.listening_view import ListeningView
from playlist_tracker.ui.mini_player import MiniPlayer
from playlist_tracker.ui.playlist_panel import PlaylistPanel
from playlist_tracker.ui.services import SERVICES, SPOTIFY, Service
from playlist_tracker.ui.settings_page import SettingsPage
from playlist_tracker.ui.sidebar import Sidebar
from playlist_tracker.ui.tabs import Tabs
from playlist_tracker.ui.theme import px

# Start with the monthly summary open, to look at it before it opens by itself
SUMMARY_FLAG = "--summary"


class App(tk.Tk):
    def __init__(self, local_tracker: nowplaying.LocalTracker, commands: queue.Queue[str],
                 tray: background.Tray, hidden: bool = False, section: str = "listening"):
        """section: the page shown first (after a language or theme change, the settings again)."""
        super().__init__()
        self.local_tracker = local_tracker
        self.commands = commands
        self.tray = tray
        config = load_config()
        i18n.set_language(config.get("LANGUAGE"))
        self.title(t("app.title"))
        tray.set_title(t("app.title"))

        self.busy = False
        self.restart = False
        # The page to show when the window is rebuilt
        self.restart_section = "listening"
        self.panels: dict[str, PlaylistPanel] = {}
        self.sections: dict[str, ttk.Frame] = {}
        self.section: str | None = None

        theme.apply_theme(self, config.get("THEME"), {s.name: (s.accent, s.accent_active) for s in SERVICES})
        # After the theme, which sets the scale for this screen
        theme.place_window(self, 1440, 940)
        self.minsize(px(860), px(600))

        if background.TRAY_AVAILABLE:
            from PIL import ImageTk
            self._icon = ImageTk.PhotoImage(background.icon_image(64))
            self.iconphoto(True, self._icon)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_ui(section)
        self.history.refresh()
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
            self.after(200, lambda: self.open_settings(SPOTIFY))
        elif SUMMARY_FLAG in sys.argv[1:]:
            self.after(500, lambda: self._open_monthly_summary(force=True))
        else:
            self.after(500, self._open_monthly_summary)

    def on_close(self):
        if not background.close_to_tray(load_config()):
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
        # Requests from the tray icon, the automatic check and copies of the app started later, which run on
        # other threads
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
            elif isinstance(command, tuple) and command[0] == "checked":
                # Results of the automatic check: ("checked", service name, results)
                _, service_name, results = command
                self.panels[service_name].show_results(results, automatic=True)
        self.after(200, self._poll_commands)

    def _build_ui(self, section: str):
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        self.sidebar = Sidebar(body, t("app.title"))
        self.sidebar.pack(side="left", fill="y")
        self.content = ttk.Frame(body, padding=(px(24), px(16), px(24), px(16)))
        self.content.pack(side="left", fill="both", expand=True)
        # Along the bottom of the window, under the sidebar too
        self.mini_player = MiniPlayer(self, self.local_tracker, self.open_track_page, body)

        # Listening comes first: it is the home page; playlist tracking and settings are pages of their own
        self.listening = ListeningView(self.content, self, self.local_tracker)
        playlist_section = ttk.Frame(self.content)
        self.tabs = Tabs(playlist_section)
        self.tabs.pack(fill="both", expand=True)
        self.settings = SettingsPage(self.content, self)
        for name, frame, glyph, bottom in (("listening", self.listening, "tracks", False),
                                           ("playlists", playlist_section, "list", False),
                                           ("settings", self.settings, "settings", True)):
            self.sections[name] = frame
            text = t("settings.title") if name == "settings" else t(f"nav.{name}")
            self.sidebar.add(name, text, glyph, lambda name=name: self.show_section(name), bottom=bottom)
        # The history tab is built first because panels update its playlist filter while loading
        self.history = HistoryTab(self.tabs, self)
        self.tabs.add(self.history, text=t("tab.history"))
        for index, service in enumerate(SERVICES):
            panel = PlaylistPanel(self, service)
            self.panels[service.name] = panel
            self.tabs.insert(index, panel, text=service.name)
        self.tabs.select(0)
        self.history.update_filter()
        self.show_section(section if section in self.sections else "listening")

    def _open_monthly_summary(self, force: bool = False):
        """On the first days of a month, show the summary of the month before once (see wrapped.SHOW_DAYS);
        force shows the last month with plays on any day."""
        from playlist_tracker.ui.stats import wrapped
        due = wrapped.month_to_show() if force else wrapped.auto_open_due()
        if due:
            if not force:
                wrapped.mark_shown(due[0])
            self.show_section("listening")
            self.listening.tabs.select(self.listening.stats)
            self.listening.stats.open_wrapped(due)

    def open_track_page(self, track_key: str):
        self.show_section("listening")
        self.listening.tabs.select(self.listening.stats)
        self.listening.stats.open_detail("track_key", track_key)

    def show_section(self, name, service: Service | None = None):
        """Show a page; service picks the settings tab of a service with missing credentials."""
        if name == "settings" and (name != self.section or service):
            # Built anew from the saved settings each time it is opened
            self.settings.show(service)
        if name == self.section:
            return
        for key, frame in self.sections.items():
            if key == name:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()
        self.section = name
        self.sidebar.select(name)

    def set_status(self, text):
        self.sidebar.status.configure(text=text)

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
        if not panel.service.has_credentials(load_config()):
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

    def open_settings(self, service: Service | None = None):
        self.show_section("settings", service)
