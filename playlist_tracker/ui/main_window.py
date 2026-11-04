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
from playlist_tracker.ui.settings_dialog import open_settings
from playlist_tracker.ui.theme import px

# Start with the monthly summary open, to look at it before it opens by itself
SUMMARY_FLAG = "--summary"


class App(tk.Tk):
    def __init__(self, local_tracker: nowplaying.LocalTracker, commands: queue.Queue[str],
                 tray: background.Tray, hidden: bool = False):
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
            self.after(200, self.open_settings)
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
        self.history = HistoryTab(self.tabs, self)
        self.tabs.add(self.history, text=f"  {t('tab.history')}  ")
        for index, service in enumerate(SERVICES):
            panel = PlaylistPanel(self, service)
            self.panels[service.name] = panel
            self.tabs.insert(index, panel, text=f"  {service.name}  ")
        self.tabs.select(0)
        self.history.update_filter()
        self.show_section("playlists")

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

    def show_section(self, name):
        for key, (frame, button) in self.sections.items():
            if key == name:
                frame.pack(fill="both", expand=True, padx=px(16), pady=(px(8), px(16)))
                button.configure(style="NavSelected.TButton")
            else:
                frame.pack_forget()
                button.configure(style="Nav.TButton")

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

    def open_settings(self, service: Service = SPOTIFY):
        open_settings(self, service)
