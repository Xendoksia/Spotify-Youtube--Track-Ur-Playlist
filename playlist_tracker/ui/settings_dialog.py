"""
Settings window.
"""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

from playlist_tracker import background
from playlist_tracker.core import i18n
from playlist_tracker.core.config import load_config, save_config
from playlist_tracker.core.i18n import t
from playlist_tracker.playlists import auto_check, spotify
from playlist_tracker.ui import theme
from playlist_tracker.ui.services import SPOTIFY, YOUTUBE, Service
from playlist_tracker.ui.tabs import Tabs
from playlist_tracker.ui.theme import P, px


def open_settings(app, service: Service = SPOTIFY):
    """Spotify and YouTube credentials, language, theme and running in the background."""
    window = tk.Toplevel(app)
    window.title(t("settings.title"))
    window.transient(app)
    window.resizable(False, False)
    window.configure(background=P.bg)
    theme.dark_title_bar(window)
    notebook = Tabs(window)
    notebook.pack(fill="both", padx=px(16), pady=(px(16), 0))
    config = load_config()

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
    notebook.add(spotify_tab, text="Spotify")
    ttk.Label(spotify_tab, justify="left", style="CardMuted.TLabel",
              text=t("settings.spotify_steps", redirect_uri=spotify.REDIRECT_URI)
              ).grid(row=0, column=0, columnspan=2, sticky="w")
    link(spotify_tab, t("settings.open_dashboard"), "https://developer.spotify.com/dashboard", 1)
    spotify_entries = {
        "CLIENT_ID": field(spotify_tab, t("settings.client_id"), "CLIENT_ID", 2),
        "CLIENT_SECRET": field(spotify_tab, t("settings.client_secret"), "CLIENT_SECRET", 3, secret=True),
    }

    youtube_tab = ttk.Frame(notebook, padding=px(16), style="Card.TFrame")
    notebook.add(youtube_tab, text="YouTube")
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
    notebook.add(general_tab, text=t("settings.general"))
    current_theme = config.get("THEME") if config.get("THEME") in theme.THEMES else "system"
    get_language = choice(general_tab, t("settings.language"), i18n.LANGUAGES, i18n.current(), 0)
    get_theme = choice(general_tab, t("settings.theme"), {k: t(f"theme.{k}") for k in theme.THEMES},
                       current_theme, 1)
    current_interval = config.get("AUTO_CHECK")
    if current_interval not in auto_check.INTERVALS:
        current_interval = auto_check.DEFAULT_INTERVAL
    get_auto_check = choice(general_tab, t("settings.auto_check"),
                            {k: t(f"auto_check.{k}") for k in auto_check.INTERVALS}, current_interval, 2)
    ttk.Label(general_tab, text=t("settings.auto_check_note"), style="CardMuted.TLabel"
              ).grid(row=3, column=1, sticky="w", padx=(px(8), 0))
    tray_var = tk.BooleanVar(value=background.close_to_tray(config))
    ttk.Checkbutton(general_tab, text=t("settings.close_to_tray"), variable=tray_var,
                    style="Card.TCheckbutton", state="normal" if background.TRAY_AVAILABLE else "disabled"
                    ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(px(12), px(4)))
    autostart_var = tk.BooleanVar(value=background.autostart_enabled())
    ttk.Checkbutton(general_tab, text=t("settings.autostart"), variable=autostart_var,
                    style="Card.TCheckbutton",
                    state="normal" if background.autostart_supported() else "disabled"
                    ).grid(row=5, column=0, columnspan=2, sticky="w", pady=px(4))
    ttk.Label(general_tab, text=t("settings.restart_note"), style="CardMuted.TLabel"
              ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(px(12), 0))

    def save():
        updated = load_config()
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
        updated["AUTO_CHECK"] = get_auto_check()
        if background.TRAY_AVAILABLE:
            updated["CLOSE_TO_TRAY"] = tray_var.get()
        save_config(updated)
        if autostart_var.get() != background.autostart_enabled():
            try:
                background.set_autostart(autostart_var.get())
            except OSError as error:
                messagebox.showerror(t("settings.title"), t("settings.autostart_failed", error=error),
                                     parent=window)
        window.destroy()
        if appearance_changed:
            # Rebuild the whole window so every widget picks up the new texts and colors
            app.restart = True
            app.destroy()
            return
        for panel in app.panels.values():
            panel.update_login_status()
        app.set_status(t("status.saved"))

    ttk.Button(window, text=t("settings.save"), command=save, style="Accent.TButton"
               ).pack(anchor="e", padx=px(16), pady=px(16))
    notebook.select(youtube_tab if service is YOUTUBE else spotify_tab)
    window.grab_set()
