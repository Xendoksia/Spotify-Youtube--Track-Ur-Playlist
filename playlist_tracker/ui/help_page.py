"""
How the app works, as a page of the window: what Spotify and YouTube allow, why so much has to be set up and
what the listening statistics can and cannot know. Each topic is a card with what happens, why and what to do.
"""

from __future__ import annotations

from tkinter import ttk

from playlist_tracker.core.i18n import t
from playlist_tracker.ui.stats.widgets import ScrollFrame, card
from playlist_tracker.ui.theme import TYPE, P, px

# (icon, key): the texts are help.<key>.title, help.<key>.why and help.<key>.todo; todo may be empty
TOPICS = (
    ("settings", "setup"),
    ("list", "own_lists"),
    ("flag", "link"),
    ("tag", "unplayable"),
    ("history", "auto_check"),
    ("tracks", "listening"),
)


class HelpPage(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        ttk.Label(self, text=t("help.title"), style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, text=t("help.lead"), font=TYPE["lead"], foreground=P.muted
                  ).pack(anchor="w", pady=(px(4), px(12)))
        scroll = ScrollFrame(self)
        scroll.pack(fill="both", expand=True)
        for icon_name, key in TOPICS:
            self._topic(scroll.content, icon_name, key)

    @staticmethod
    def _topic(parent, icon_name: str, key: str):
        frame = card(parent, icon_name, t(f"help.{key}.title"))
        frame.pack(fill="x", pady=(px(12), 0))
        labels = [ttk.Label(frame, text=t(f"help.{key}.why"), style="Card.TLabel", justify="left")]
        labels[0].pack(anchor="w", fill="x", pady=(px(8), 0))
        todo = t(f"help.{key}.todo")
        if todo:
            labels.append(ttk.Label(frame, text=todo, style="CardMuted.TLabel", justify="left"))
            labels[1].pack(anchor="w", fill="x", pady=(px(8), 0))
        frame.bind("<Configure>", lambda e: [label.configure(wraplength=max(px(200), e.width - px(40)))
                                             for label in labels])
