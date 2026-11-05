"""
The account, as a page of the window: a login screen while logged out, the account's details once logged in.
"""

from __future__ import annotations

import threading
from datetime import datetime
from tkinter import ttk
from typing import TYPE_CHECKING

from playlist_tracker.core import account, sync
from playlist_tracker.core.errors import TrackerError
from playlist_tracker.core.i18n import number, t
from playlist_tracker.music import artwork, listening
from playlist_tracker.ui.stats.text import month_name
from playlist_tracker.ui.stats.widgets import Hero, card, card_row
from playlist_tracker.ui.theme import FONT, TYPE, P, px

if TYPE_CHECKING:
    from playlist_tracker.ui.main_window import App

AVATAR_SIZE = 96
AVATAR_PATH = artwork.ART_DIR / "account" / "avatar.jpg"
# Longer lines are hard to read on a wide window
TEXT_WIDTH = 640


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
        # The whole page, like the other pages
        self.card = ttk.Frame(self, padding=px(24), style="Card.TFrame")
        self.card.pack(fill="both", expand=True)
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
                          justify="left", wraplength=px(TEXT_WIDTH), font=font or FONT)
        label.pack(anchor="w", pady=pady)
        return label

    def _message_line(self):
        """A line for what is going on or what went wrong, under the buttons."""
        self.message = ttk.Label(self.card, style="CardMuted.TLabel", wraplength=px(TEXT_WIDTH),
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
        self._message_line()

    def _build_profile(self, user: dict):
        # The profile on the colors of the user's picture, like the number one cards of the statistics
        self.hero = Hero(self.card, t("account.caption"), round_image=True, image_size=AVATAR_SIZE)
        self.hero.pack(fill="x")
        self._show_avatar(user)

        row = card_row(self.card)
        sync_card = card(row, "sync", t("account.sync"), column=0)
        self.sync_status = ttk.Label(sync_card, style="Card.TLabel", font=TYPE["display"])
        self.sync_status.pack(anchor="w")
        self.sync_time = ttk.Label(sync_card, style="CardMuted.TLabel")
        self.sync_time.pack(anchor="w", pady=(px(4), 0))
        self.sync_counts = ttk.Label(sync_card, style="Card.TLabel", wraplength=px(260), justify="left")
        self.sync_counts.pack(anchor="w", pady=(px(12), 0))
        self._buttons(sync_card, ((t("account.sync_now"), self.sync_now, "Accent.TButton"),))

        device_card = card(row, "device", t("account.device"), column=1)
        ttk.Label(device_card, text=sync.device()[1], style="Card.TLabel", font=TYPE["display"]).pack(anchor="w")
        self.device_plays = ttk.Label(device_card, style="CardMuted.TLabel")
        self.device_plays.pack(anchor="w", pady=(px(4), 0))
        self.device_waiting = ttk.Label(device_card, style="Card.TLabel")
        self.device_waiting.pack(anchor="w", pady=(px(12), 0))

        account_card = card(row, "account", t("account.details"), column=2)
        details = ttk.Frame(account_card, style="Card.TFrame")
        details.pack(fill="x")
        for index, (label, value) in enumerate(((t("account.provider"), (user.get("provider") or "").capitalize()),
                                                (t("account.created"), self._date(user.get("created_at"))),
                                                (t("account.user_id"), (user.get("id") or "")[:8]))):
            ttk.Label(details, text=label, style="CardMuted.TLabel").grid(row=index, column=0, sticky="w",
                                                                         pady=px(2))
            ttk.Label(details, text=value or "—", style="Card.TLabel").grid(row=index, column=1, sticky="w",
                                                                           padx=(px(16), 0), pady=px(2))
        self._buttons(account_card, ((t("account.refresh"), self.refresh, "TButton"),
                                     (t("account.logout"), self.logout, "TButton")))
        self._message_line()
        self.show_sync()

    @staticmethod
    def _buttons(parent, buttons):
        """Buttons along the bottom of a card."""
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.pack(side="bottom", anchor="w", pady=(px(16), 0))
        for index, (text, command, style) in enumerate(buttons):
            ttk.Button(frame, text=text, command=command, style=style).pack(side="left",
                                                                            padx=(0 if index == 0 else px(8), 0))

    @staticmethod
    def _date(iso: str | None) -> str:
        """The day an account was made, as "5 November 2026"."""
        if not iso:
            return ""
        try:
            moment = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
        except ValueError:
            return iso
        return f"{moment.day} {month_name(moment.month)} {moment.year}"

    def show_sync(self):
        """The outcome of the last sync and what waits on this computer."""
        status = getattr(self, "sync_status", None)
        if status is None or not status.winfo_exists():
            return
        last = sync.last
        if last.get("error"):
            text, color = t("account.sync_state.failed"), P.removed
            when, counts = "", last["error"]
        elif last.get("at"):
            text, color = t("account.sync_state.done"), P.added
            when = t("account.sync_at", time=f"{last['at']:%H:%M}")
            counts = t("account.sync_counts", sent=number(last["sent"]), received=number(last["received"]))
        else:
            text, color = t("account.sync_state.waiting"), P.muted
            when, counts = t("account.sync_every"), ""
        status.configure(text=f"● {text}", foreground=color)
        self.sync_time.configure(text=when)
        self.sync_counts.configure(text=counts, foreground=P.removed if last.get("error") else P.text)
        total, waiting = sum(listening.counts().values()), listening.unsynced_count()
        self.device_plays.configure(text=t("account.device_plays", count=number(total)))
        self.device_waiting.configure(text=t("account.device_waiting", count=number(waiting)) if waiting
                                      else t("account.device_all_sent"),
                                      foreground=P.text if waiting else P.added)

    def _show_avatar(self, user: dict):
        hero = getattr(self, "hero", None)
        if hero is None or not hero.winfo_exists():
            return
        name = user.get("name") or user.get("email") or "?"
        detail = t("account.since", provider=(user.get("provider") or "").capitalize(),
                   date=self._date(user.get("created_at")))
        # Without a picture yet, the first letter of the name on a circle
        hero.show(name, user.get("email") if user.get("name") else "", detail,
                  AVATAR_PATH if AVATAR_PATH.exists() else None)

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
        self.download_avatar(user)
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
            AVATAR_PATH.unlink(missing_ok=True)
            self.show()
            self.app.update_account()
            self.app.show_login()
        self._run(lambda: account.AccountClient().logout(), done, t("account.logging_out"))

    def download_avatar(self, user: dict):
        url = user.get("avatar")
        if not url:
            return

        def worker():
            try:
                saved = artwork.save_image(artwork._get(url, as_json=False), AVATAR_PATH)
            except OSError:
                return
            if saved:
                # The page may not have been opened yet; it shows the picture when it is
                self.app.after(0, lambda: self._show_avatar(user))

        threading.Thread(target=worker, daemon=True).start()
