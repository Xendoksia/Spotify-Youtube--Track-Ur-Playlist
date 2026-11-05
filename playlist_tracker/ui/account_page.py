"""
The account, as a page of the window: a login screen while logged out, the account's details once logged in.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from playlist_tracker.core import account, sync
from playlist_tracker.core.config import load_config
from playlist_tracker.core.errors import TrackerError
from playlist_tracker.core.i18n import number, t
from playlist_tracker.core.text import format_date
from playlist_tracker.music import artwork
from playlist_tracker.ui.theme import FONT, TYPE, P, px

if TYPE_CHECKING:
    from playlist_tracker.ui.main_window import App

AVATAR_SIZE = 72
AVATAR_PATH = artwork.ART_DIR / "account" / "avatar.jpg"
CARD_WIDTH = 560


class AccountPage(ttk.Frame):
    def __init__(self, parent, app: "App"):
        super().__init__(parent)
        self.app = app
        self.busy = False
        self.sync_label = None

    def show(self):
        """Build the page for the saved account state."""
        for child in self.winfo_children():
            child.destroy()
        ttk.Label(self, text=t("account.title"), style="Title.TLabel").pack(anchor="w", pady=(0, px(12)))
        self.card = ttk.Frame(self, padding=px(24), style="Tile.TFrame", width=px(CARD_WIDTH))
        self.card.pack(anchor="nw")
        self.message = None
        self.sync_label = None
        if not account.configured():
            self._text(t("account.not_configured"), muted=True)
        elif account.profile():
            self._build_profile(account.profile())
        else:
            self._build_login()

    # Building blocks

    def _text(self, text: str, muted: bool = False, font=None, pady=(0, 0)) -> ttk.Label:
        label = ttk.Label(self.card, text=text, style="CardMuted.TLabel" if muted else "Card.TLabel",
                          justify="left", wraplength=px(CARD_WIDTH - 48), font=font or FONT)
        label.pack(anchor="w", pady=pady)
        return label

    def _message_line(self):
        """A line for what is going on or what went wrong, under the buttons."""
        self.message = ttk.Label(self.card, style="CardMuted.TLabel", wraplength=px(CARD_WIDTH - 48),
                                 justify="left")
        self.message.pack(anchor="w", pady=(px(12), 0))

    def _say(self, text: str, error: bool = False):
        if self.message is not None and self.message.winfo_exists():
            self.message.configure(text=text, foreground=P.removed if error else P.muted)

    def _build_login(self):
        self._text(t("account.login_title"), font=TYPE["display"])
        self._text(t("account.login_lead"), muted=True, pady=(px(8), px(16)))
        buttons = ttk.Frame(self.card, style="Card.TFrame")
        buttons.pack(anchor="w")
        self.login_button = ttk.Button(buttons, text=t("account.login_google"), style="Accent.TButton",
                                       command=self.login)
        self.login_button.pack(side="left")
        if not load_config().get(account.SKIPPED_KEY):
            skip = ttk.Label(buttons, text=t("account.skip"), style="Card.TLabel", foreground=P.focus,
                             cursor="hand2")
            skip.pack(side="left", padx=(px(16), 0))
            skip.bind("<Button-1>", lambda e: self.skip())
        self._message_line()

    def _build_profile(self, user: dict):
        top = ttk.Frame(self.card, style="Card.TFrame")
        top.pack(anchor="w", fill="x")
        self.avatar = tk.Label(top, background=P.surface)
        self.avatar.pack(side="left", padx=(0, px(16)))
        self._show_avatar(user)
        names = ttk.Frame(top, style="Card.TFrame")
        names.pack(side="left", fill="x")
        ttk.Label(names, text=user.get("name") or user.get("email"), style="Card.TLabel",
                  font=TYPE["display"]).pack(anchor="w")
        if user.get("name"):
            ttk.Label(names, text=user.get("email"), style="CardMuted.TLabel").pack(anchor="w", pady=(px(2), 0))

        details = ttk.Frame(self.card, style="Card.TFrame")
        details.pack(anchor="w", fill="x", pady=(px(16), 0))
        rows = [(t("account.provider"), (user.get("provider") or "").capitalize()),
                (t("account.created"), format_date(user.get("created_at"))),
                (t("account.user_id"), user.get("id")),
                (t("account.sync"), "")]
        for row, (label, value) in enumerate(rows):
            ttk.Label(details, text=label, style="CardMuted.TLabel").grid(row=row, column=0, sticky="w",
                                                                         pady=px(2))
            value_label = ttk.Label(details, text=value or "—", style="Card.TLabel")
            value_label.grid(row=row, column=1, sticky="w", padx=(px(16), 0), pady=px(2))
        self.sync_label = value_label
        self.show_sync()

        buttons = ttk.Frame(self.card, style="Card.TFrame")
        buttons.pack(anchor="w", pady=(px(20), 0))
        ttk.Button(buttons, text=t("account.sync_now"), style="Accent.TButton",
                   command=self.sync_now).pack(side="left")
        ttk.Button(buttons, text=t("account.refresh"), command=self.refresh).pack(side="left", padx=(px(8), 0))
        ttk.Button(buttons, text=t("account.logout"), command=self.logout).pack(side="left", padx=(px(8), 0))
        self._message_line()

    def show_sync(self):
        """The outcome of the last sync, on the sync row."""
        if self.sync_label is None or not self.sync_label.winfo_exists():
            return
        last = sync.last
        if last.get("error"):
            text, color = t("account.sync_failed", error=last["error"]), P.removed
        elif last.get("at"):
            text, color = t("account.sync_done", time=f"{last['at']:%H:%M}", sent=number(last["sent"]),
                            received=number(last["received"])), P.text
        else:
            text, color = t("account.sync_waiting"), P.muted
        self.sync_label.configure(text=text, foreground=color)

    def _show_avatar(self, user: dict):
        image = artwork.photo(AVATAR_PATH, px(AVATAR_SIZE), P.surface, round_=True)
        if image:
            self.avatar.configure(image=image, text="", width=0, height=0)
            self.avatar.image = image
        else:
            # The first letter on a circle until the picture is downloaded
            letter = (user.get("name") or user.get("email") or "?")[:1].upper()
            self.avatar.configure(text=letter, font=TYPE["name"], foreground=P.chart, width=2)

    # Actions, run off the window's thread

    def _run(self, task, on_success, status: str):
        if self.busy:
            return
        self.busy = True
        self._say(status)

        def worker():
            try:
                result, error = task(), None
            except TrackerError as e:
                result, error = None, str(e)
            self.app.after(0, lambda: self._done(on_success, result, error))

        threading.Thread(target=worker, daemon=True).start()

    def _done(self, on_success, result, error):
        self.busy = False
        if error:
            # A session that ended shows the login screen again
            if not account.profile():
                self.show()
            self._say(error, error=True)
            return
        on_success(result)

    def login(self):
        self._run(lambda: account.AccountClient().login(), self._logged_in, t("account.waiting"))

    def _logged_in(self, user: dict):
        self._download_avatar(user)
        self.show()
        self._say(t("account.welcome", name=user.get("name") or user.get("email")))
        self.app.update_account()
        if sync.syncer:
            sync.syncer.wake()

    def sync_now(self):
        if not sync.syncer:
            return

        def done(result):
            self.show_sync()
            self._say("")
            if result.get("received"):
                self.app.listening.mark_stale()
            if result.get("playlists"):
                for panel in self.app.panels.values():
                    panel.reload_tracked()
        self._run(sync.syncer.run_once, done, t("account.syncing"))

    def refresh(self):
        self._run(lambda: account.AccountClient().refresh(), self._logged_in, t("account.refreshing"))

    def logout(self):
        def done(_):
            sync.forget()
            AVATAR_PATH.unlink(missing_ok=True)
            self.show()
            self.app.update_account()
        self._run(lambda: account.AccountClient().logout(), done, t("account.logging_out"))

    def skip(self):
        account.skip()
        self.app.show_section("listening")

    def _download_avatar(self, user: dict):
        url = user.get("avatar")
        if not url:
            return

        def worker():
            try:
                saved = artwork.save_image(artwork._get(url, as_json=False), AVATAR_PATH)
            except OSError:
                return
            if saved:
                self.app.after(0, lambda: self.avatar.winfo_exists() and self._show_avatar(user))

        threading.Thread(target=worker, daemon=True).start()
