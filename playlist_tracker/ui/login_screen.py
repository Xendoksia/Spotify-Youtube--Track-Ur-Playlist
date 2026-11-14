"""
The login screen: covers the whole window when the app opens without a remembered session, like the sign-in
screen of any app. Logging in or going on without an account uncovers the app underneath.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable

from playlist_tracker import background
from playlist_tracker.core import account
from playlist_tracker.core.errors import TrackerError
from playlist_tracker.core.i18n import t
from playlist_tracker.ui import skin
from playlist_tracker.ui.theme import FONT, TYPE, P, px

CARD_WIDTH = 400
LOGO_SIZE = 64


class LoginScreen(tk.Frame):
    def __init__(self, parent: tk.Tk, on_done: Callable[[dict | None], None]):
        """on_done(profile) runs after logging in, on_done(None) after choosing to go on without an account."""
        super().__init__(parent, background=P.bg)
        self.on_done = on_done
        self.busy = False
        card = skin.tile(self, behind=P.bg, padding=(px(40), px(36)))
        card.place(relx=0.5, rely=0.45, anchor="center", width=px(CARD_WIDTH))

        if background.TRAY_AVAILABLE:
            from PIL import ImageTk
            self._logo = ImageTk.PhotoImage(background.icon_image(px(LOGO_SIZE)))
            tk.Label(card, image=self._logo, background=P.surface).pack()
        ttk.Label(card, text=t("app.title"), style="Card.TLabel", font=TYPE["display"]
                  ).pack(pady=(px(16), px(4)))
        ttk.Label(card, text=t("login_screen.lead"), style="CardMuted.TLabel", justify="center",
                  wraplength=px(CARD_WIDTH - 80)).pack()

        self.button = ttk.Button(card, text=t("account.login_google"), style="Accent.TButton", command=self.login)
        self.button.pack(fill="x", pady=(px(28), 0), ipady=px(4))
        self.remember = tk.BooleanVar(value=account.remembered())
        ttk.Checkbutton(card, text=t("login_screen.remember"), variable=self.remember,
                        style="Card.TCheckbutton").pack(anchor="w", pady=(px(12), 0))
        # What is going on or what went wrong; shown only while there is something to say
        self.message = ttk.Label(card, style="CardMuted.TLabel", justify="center", wraplength=px(CARD_WIDTH - 80))
        self.line = tk.Frame(card, background=P.border, height=1)
        self.line.pack(fill="x", pady=(px(20), px(16)))
        skip = ttk.Label(card, text=t("account.skip"), style="CardMuted.TLabel", font=FONT, cursor="hand2")
        skip.pack()
        skip.bind("<Button-1>", lambda e: self.skip())
        skip.bind("<Enter>", lambda e: skip.configure(foreground=P.focus))
        skip.bind("<Leave>", lambda e: skip.configure(foreground=P.muted))

    def show(self):
        """Cover the window."""
        self.place(x=0, y=0, relwidth=1, relheight=1)
        self.lift()

    def login(self):
        if self.busy:
            return
        self.busy = True
        self.button.state(["disabled"])
        self._say(t("account.waiting"))
        account.set_remembered(self.remember.get())

        def worker():
            try:
                result, error = account.AccountClient().login(), None
            except TrackerError as e:
                result, error = None, str(e)
            self.after(0, lambda: self._done(result, error))

        threading.Thread(target=worker, daemon=True).start()

    def _done(self, profile: dict | None, error: str | None):
        self.busy = False
        self.button.state(["!disabled"])
        if error:
            self._say(error, P.removed)
            return
        self.on_done(profile)

    def _say(self, text: str, color: str | None = None):
        self.message.configure(text=text, foreground=color or P.muted)
        self.message.pack(pady=(px(12), 0), before=self.line)

    def skip(self):
        if not self.busy:
            self.on_done(None)
