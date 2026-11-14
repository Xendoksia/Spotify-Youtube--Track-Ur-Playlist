"""
Pages under a row of tab titles, the selected one underlined in the accent color. It takes the place of
ttk.Notebook, whose raised tabs looked dated next to the rest of the interface, and keeps the part of its
interface the app uses: add, insert and select.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from playlist_tracker.ui.theme import FONT_BOLD, P, px

UNDERLINE = 2


class Tabs(ttk.Frame):
    def __init__(self, parent, background: str | None = None):
        """Pages are created with this widget as their parent and shown in a bordered panel under the titles;
        background is the color around the titles (the window's by default)."""
        super().__init__(parent, style="Card.TFrame" if background == P.surface else "TFrame")
        self.background = background or P.bg
        self.bar = tk.Frame(self, background=self.background)
        self.bar.pack(fill="x")
        # Its page keeps inside the panel's rounded corners
        self.panel = ttk.Frame(self, style="SurfacePanel.TFrame" if background == P.surface else "Panel.TFrame",
                               padding=px(5))
        self.panel.pack(fill="both", expand=True, pady=(px(8), 0))
        self.pages: list[ttk.Frame] = []
        self._titles: dict[ttk.Frame, tuple[tk.Frame, tk.Label, tk.Frame]] = {}
        self.current: ttk.Frame | None = None

    def add(self, page, text: str):
        self.insert(len(self.pages), page, text)

    def insert(self, index: int, page, text: str):
        title = tk.Frame(self.bar, background=self.background, cursor="hand2")
        label = tk.Label(title, text=text.strip(), font=FONT_BOLD, background=self.background, foreground=P.muted,
                         cursor="hand2")
        label.pack(padx=px(4), pady=(px(4), px(6)))
        line = tk.Frame(title, height=px(UNDERLINE), background=self.background)
        line.pack(fill="x")
        for widget in (title, label):
            widget.bind("<Button-1>", lambda e, page=page: self.select(page))
            widget.bind("<Enter>", lambda e, page=page: self._hover(page, True))
            widget.bind("<Leave>", lambda e, page=page: self._hover(page, False))
        self._titles[page] = (title, label, line)
        self.pages.insert(index, page)
        for other in self.pages:
            self._titles[other][0].pack_forget()
        for position, other in enumerate(self.pages):
            self._titles[other][0].pack(side="left", padx=(0 if position == 0 else px(20), 0))
        if self.current is None:
            self.select(page)

    def select(self, page_or_index):
        page = self.pages[page_or_index] if isinstance(page_or_index, int) else page_or_index
        if self.current is not None and self.current is not page:
            self.current.pack_forget()
        self.current = page
        page.pack(in_=self.panel, fill="both", expand=True)
        for other, (_, label, line) in self._titles.items():
            selected = other is page
            label.configure(foreground=P.text if selected else P.muted)
            line.configure(background=P.chart if selected else self.background)

    def _hover(self, page, on: bool):
        if page is not self.current:
            self._titles[page][1].configure(foreground=P.text if on else P.muted)
