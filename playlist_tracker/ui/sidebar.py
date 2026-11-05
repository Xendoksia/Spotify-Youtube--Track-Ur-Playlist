"""
The navigation along the left side of the window: the app's name, its sections with an icon each, settings at
the bottom and a line for what the app is doing.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from playlist_tracker import background
from playlist_tracker.ui.theme import FONT, FONT_BOLD, TYPE, P, icon, icon_font, mix, px

WIDTH = 220
ITEM_HEIGHT = 40
ACCENT_WIDTH = 3


class Sidebar(tk.Frame):
    def __init__(self, parent, title: str):
        self.background = mix(P.bg, P.surface, 0.5)
        super().__init__(parent, background=self.background, width=px(WIDTH))
        self.pack_propagate(False)
        self.items: dict[str, dict] = {}
        self.selected: str | None = None

        top = tk.Frame(self, background=self.background)
        top.pack(fill="x", padx=px(16), pady=(px(20), px(24)))
        if background.TRAY_AVAILABLE:
            from PIL import ImageTk
            self._logo = ImageTk.PhotoImage(background.icon_image(px(30)))
            tk.Label(top, image=self._logo, background=self.background).pack(side="left", padx=(0, px(10)))
        tk.Label(top, text=title, font=TYPE["heading"], background=self.background, foreground=P.text,
                 anchor="w", justify="left", wraplength=px(WIDTH - 80)).pack(side="left", fill="x")

        self.main = tk.Frame(self, background=self.background)
        self.main.pack(fill="x", padx=px(8))
        self.bottom = tk.Frame(self, background=self.background)
        self.bottom.pack(side="bottom", fill="x", padx=px(8), pady=(0, px(12)))
        # What the app is doing, above settings; empty while there is nothing to say
        self.status = tk.Label(self, font=TYPE["small"], background=self.background, foreground=P.muted,
                               anchor="w", justify="left", wraplength=px(WIDTH - 32))
        self.status.pack(side="bottom", fill="x", padx=px(16), pady=(0, px(8)))

    def add(self, name: str, text: str, glyph_name: str, command: Callable[[], None], bottom: bool = False):
        parent = self.bottom if bottom else self.main
        item = tk.Frame(parent, background=self.background, height=px(ITEM_HEIGHT), cursor="hand2")
        item.pack(fill="x", pady=px(2))
        item.pack_propagate(False)
        accent = tk.Frame(item, background=self.background, width=px(ACCENT_WIDTH))
        accent.pack(side="left", fill="y", pady=px(8))
        glyph = icon(glyph_name)
        mark = tk.Label(item, text=glyph, font=(icon_font(), 13), background=self.background, foreground=P.muted,
                        width=2) if glyph else None
        if mark:
            mark.pack(side="left", padx=(px(10), px(6)))
        label = tk.Label(item, text=text, font=FONT, background=self.background, foreground=P.muted, anchor="w")
        label.pack(side="left", fill="x", padx=(0 if mark else px(14), 0))
        parts = [part for part in (item, mark, label) if part]
        self.items[name] = {"item": item, "accent": accent, "mark": mark, "label": label, "parts": parts}
        for widget in parts:
            widget.bind("<Button-1>", lambda e: command())
            widget.bind("<Enter>", lambda e, name=name: self._paint(name, hover=True))
            widget.bind("<Leave>", lambda e, name=name: self._on_leave(name, e))

    def set_text(self, name: str, text: str):
        self.items[name]["label"].configure(text=text)

    def select(self, name: str):
        previous, self.selected = self.selected, name
        if previous in self.items:
            self._paint(previous)
        self._paint(name)

    def _on_leave(self, name: str, event):
        # Moving onto the icon or the text of the same item is not leaving it
        under = self.winfo_containing(event.x_root, event.y_root)
        if under is None or under not in self.items[name]["parts"]:
            self._paint(name)

    def _paint(self, name: str, hover: bool = False):
        parts = self.items[name]
        selected = name == self.selected
        fill = P.surface if selected else P.hover if hover else self.background
        for widget in parts["parts"]:
            widget.configure(background=fill)
        parts["accent"].configure(background=P.chart if selected else fill)
        color = P.text if selected or hover else P.muted
        parts["label"].configure(foreground=color, font=FONT_BOLD if selected else FONT)
        if parts["mark"]:
            parts["mark"].configure(foreground=P.chart if selected else color)
