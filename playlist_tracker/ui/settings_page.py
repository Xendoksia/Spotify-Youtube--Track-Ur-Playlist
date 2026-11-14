"""
Settings, as a page of the window: Spotify and YouTube credentials, language, theme, the automatic check and
running in the background.
"""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from playlist_tracker import background
from playlist_tracker.core import i18n, sync
from playlist_tracker.core.config import load_config, save_config
from playlist_tracker.core.i18n import t
from playlist_tracker.playlists import auto_check, spotify
from playlist_tracker.ui import theme
from playlist_tracker.ui.services import SPOTIFY, YOUTUBE, Service
from playlist_tracker.ui.tabs import Tabs
from playlist_tracker.ui.theme import P, px

if TYPE_CHECKING:
    from playlist_tracker.ui.main_window import App


class SettingsPage(ttk.Frame):
    def __init__(self, parent, app: "App"):
        super().__init__(parent)
        self.app = app
        self.tabs = None

    def show(self, service: Service | None = None):
        """Build the page from the saved settings, on the service's tab (for missing credentials) or on the
        general one."""
        for child in self.winfo_children():
            child.destroy()
        self.config = load_config()
        ttk.Label(self, text=t("settings.title"), style="Title.TLabel").pack(anchor="w", pady=(0, px(12)))
        self.tabs = Tabs(self)
        self.tabs.pack(fill="both", expand=True)
        self._build_spotify()
        self._build_youtube()
        self._build_general()
        footer = ttk.Frame(self)
        footer.pack(fill="x", pady=(px(12), 0))
        ttk.Button(footer, text=t("settings.save"), command=self.save, style="Page.Accent.TButton").pack(side="right")
        self.tabs.select(self.youtube_tab if service is YOUTUBE else self.spotify_tab if service is SPOTIFY
                         else self.general_tab)

    # Building blocks

    def _page(self, text: str) -> ttk.Frame:
        page = ttk.Frame(self.tabs, padding=px(24), style="Card.TFrame")
        self.tabs.add(page, text=text)
        return page

    def _link(self, parent, text, url, row):
        label = ttk.Label(parent, text=text, style="Card.TLabel", foreground=P.focus, cursor="hand2")
        label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(px(4), px(12)))
        label.bind("<Button-1>", lambda e: webbrowser.open(url))

    def _field(self, parent, label, key, row, secret=False):
        ttk.Label(parent, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=px(4))
        entry = ttk.Entry(parent, width=50, show="•" if secret else "")
        entry.insert(0, self.config.get(key, ""))
        entry.grid(row=row, column=1, sticky="w", pady=px(4), padx=(px(8), 0))
        return entry

    @staticmethod
    def _choice(parent, label, options, selected, row):
        ttk.Label(parent, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=px(4))
        box = ttk.Combobox(parent, state="readonly", width=24, values=list(options.values()))
        box.current(list(options).index(selected))
        box.grid(row=row, column=1, sticky="w", pady=px(4), padx=(px(8), 0))
        return lambda: list(options)[box.current()]

    def _build_spotify(self):
        self.spotify_tab = page = self._page("Spotify")
        ttk.Label(page, justify="left", style="CardMuted.TLabel",
                  text=t("settings.spotify_steps", redirect_uri=spotify.REDIRECT_URI)
                  ).grid(row=0, column=0, columnspan=2, sticky="w")
        self._link(page, t("settings.open_dashboard"), "https://developer.spotify.com/dashboard", 1)
        self.spotify_entries = {
            "CLIENT_ID": self._field(page, t("settings.client_id"), "CLIENT_ID", 2),
            "CLIENT_SECRET": self._field(page, t("settings.client_secret"), "CLIENT_SECRET", 3, secret=True),
        }

    def _build_youtube(self):
        self.youtube_tab = page = self._page("YouTube")
        ttk.Label(page, justify="left", style="CardMuted.TLabel", text=t("settings.youtube_steps")
                  ).grid(row=0, column=0, columnspan=2, sticky="w")
        self._link(page, t("settings.open_console"),
                   "https://console.cloud.google.com/apis/library/youtube.googleapis.com", 1)
        self.youtube_entries = {
            "YOUTUBE_API_KEY": self._field(page, t("settings.api_key"), "YOUTUBE_API_KEY", 2, secret=True),
            "YOUTUBE_CLIENT_ID": self._field(page, t("settings.oauth_client_id"), "YOUTUBE_CLIENT_ID", 3),
            "YOUTUBE_CLIENT_SECRET": self._field(page, t("settings.oauth_client_secret"),
                                                 "YOUTUBE_CLIENT_SECRET", 4, secret=True),
        }

    def _build_general(self):
        self.general_tab = page = self._page(t("settings.general"))
        config = self.config
        self.current_theme = config.get("THEME") if config.get("THEME") in theme.THEMES else "system"
        self.get_language = self._choice(page, t("settings.language"), i18n.LANGUAGES, i18n.current(), 0)
        self.get_theme = self._choice(page, t("settings.theme"), {k: t(f"theme.{k}") for k in theme.THEMES},
                                      self.current_theme, 1)
        current_interval = config.get("AUTO_CHECK")
        if current_interval not in auto_check.INTERVALS:
            current_interval = auto_check.DEFAULT_INTERVAL
        self.get_auto_check = self._choice(page, t("settings.auto_check"),
                                           {k: t(f"auto_check.{k}") for k in auto_check.INTERVALS},
                                           current_interval, 2)
        ttk.Label(page, text=t("settings.auto_check_note"), style="CardMuted.TLabel"
                  ).grid(row=3, column=1, sticky="w", padx=(px(8), 0))
        self.tray_var = tk.BooleanVar(value=background.close_to_tray(config))
        ttk.Checkbutton(page, text=t("settings.close_to_tray"), variable=self.tray_var,
                        style="Card.TCheckbutton", state="normal" if background.TRAY_AVAILABLE else "disabled"
                        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(px(12), px(4)))
        self.autostart_var = tk.BooleanVar(value=background.autostart_enabled())
        ttk.Checkbutton(page, text=t("settings.autostart"), variable=self.autostart_var,
                        style="Card.TCheckbutton",
                        state="normal" if background.autostart_supported() else "disabled"
                        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=px(4))
        ttk.Label(page, text=t("settings.restart_note"), style="CardMuted.TLabel"
                  ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(px(12), 0))

    # Saving

    def save(self):
        config, app = self.config, self.app
        updated = load_config()
        values = {k: e.get().strip() for k, e in {**self.spotify_entries, **self.youtube_entries}.items()}
        for id_key, secret_key, tab in (("CLIENT_ID", "CLIENT_SECRET", self.spotify_tab),
                                        ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", self.youtube_tab)):
            if bool(values[id_key]) != bool(values[secret_key]):
                self.tabs.select(tab)
                messagebox.showwarning(t("settings.missing"), t("settings.missing_pair"), parent=app)
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
        appearance_changed = self.get_language() != i18n.current() or self.get_theme() != self.current_theme
        updated["LANGUAGE"], updated["THEME"] = self.get_language(), self.get_theme()
        if appearance_changed:
            sync.settings_changed(updated)
        updated["AUTO_CHECK"] = self.get_auto_check()
        if background.TRAY_AVAILABLE:
            updated["CLOSE_TO_TRAY"] = self.tray_var.get()
        save_config(updated)
        if self.autostart_var.get() != background.autostart_enabled():
            try:
                background.set_autostart(self.autostart_var.get())
            except OSError as error:
                messagebox.showerror(t("settings.title"), t("settings.autostart_failed", error=error), parent=app)
        if appearance_changed:
            if sync.syncer:
                sync.syncer.wake()
            app.rebuild("settings")
            return
        self.config = load_config()
        for panel in app.panels.values():
            panel.update_login_status()
        app.set_status(t("status.saved"))
