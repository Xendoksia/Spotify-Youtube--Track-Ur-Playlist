"""
The notifications box: a bell with the number of things waiting on it, and the card it opens under itself, as the
phone's bottom sheet. For now it holds the monthly and yearly summaries not seen yet (wrapped.inbox).
"""

from __future__ import annotations

import sys
import time
import tkinter as tk
from dataclasses import dataclass
from typing import Callable

from playlist_tracker.core.i18n import number, t
from playlist_tracker.ui.charts import Animation
from playlist_tracker.ui.theme import TYPE, P, icon, icon_font, mix, px

# Windows 11 rounds the card's corners (DWMWA_WINDOW_CORNER_PREFERENCE = DWMWCP_ROUND)
DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND = 33, 2
WIDTH = 360
OPEN_MS = 160


@dataclass
class Item:
    title: str
    detail: str
    open: Callable[[], None]


def round_corners(window: tk.Misc) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(DWMWCP_ROUND)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(value),
                                                   ctypes.sizeof(value))
    except (AttributeError, OSError):
        pass


class BellButton(tk.Canvas):
    """A round button with a bell, and the number waiting on a green badge at its corner."""

    SIZE = 36

    def __init__(self, parent, background: str, command: Callable[[], None]):
        size = px(self.SIZE)
        super().__init__(parent, width=size, height=size, background=background, highlightthickness=0,
                         cursor="hand2")
        self.background, self.command = background, command
        self.count = 0
        self.hovered = False
        self.bind("<Enter>", lambda event: self._hover(True))
        self.bind("<Leave>", lambda event: self._hover(False))
        self.bind("<Button-1>", lambda event: self.command())
        self._draw()

    def set_count(self, count: int):
        self.count = count
        self._draw()

    def _hover(self, hovered: bool):
        self.hovered = hovered
        self._draw()

    def _draw(self):
        self.delete("all")
        size = px(self.SIZE)
        if self.hovered:
            self.create_oval(1, 1, size - 1, size - 1, fill=P.hover, outline="")
        font = (icon_font(), 13) if icon_font() else TYPE["heading"]
        self.create_text(size / 2, size / 2 + 1, text=icon("bell"), font=font,
                         fill=P.text if self.count else P.muted)
        if self.count:
            radius = px(8)
            x, y = size - radius - 1, radius + 1
            self.create_oval(x - radius, y - radius, x + radius, y + radius, fill=P.chart, outline=self.background,
                             width=2)
            self.create_text(x, y, text=number(min(self.count, 9)), font=("Segoe UI Semibold", 7), fill="#ffffff")


class InboxPopup(tk.Toplevel):
    """The card under the bell. It closes when clicked away from, with Esc, or when an item is opened."""

    def __init__(self, anchor: tk.Widget, items: list[Item]):
        super().__init__(anchor)
        self.closed_at = None
        self.overrideredirect(True)
        self.configure(background=P.border)
        self.attributes("-alpha", 0.0)
        card = tk.Frame(self, background=P.surface, padx=px(8), pady=px(8))
        card.pack(fill="both", expand=True, padx=1, pady=1)

        header = tk.Frame(card, background=P.surface)
        header.pack(fill="x", padx=px(8), pady=(px(4), px(8)))
        tk.Label(header, text=t("inbox.title"), font=TYPE["heading"], background=P.surface,
                 foreground=P.text).pack(side="left")
        if items:
            tk.Label(header, text=t("inbox.new", count=number(len(items))), font=TYPE["caption"],
                     background=mix(P.surface, P.chart, 0.18), foreground=P.chart, padx=px(8),
                     pady=px(2)).pack(side="right")

        for item in items:
            self._row(card, item)
        if not items:
            self._empty(card)

        width = px(WIDTH)
        self.update_idletasks()
        x = anchor.winfo_rootx() + anchor.winfo_width() - width
        y = anchor.winfo_rooty() + anchor.winfo_height() + px(6)
        self.geometry(f"{width}x{self.winfo_reqheight()}+{max(0, x)}+{y}")
        round_corners(self)

        self.bind("<Escape>", lambda event: self.close())
        self.bind("<FocusOut>", self._focus_out)
        self.focus_force()
        # Fades in, as the phone's sheet slides up
        Animation(self, lambda progress: self.winfo_exists() and self.attributes("-alpha", progress), OPEN_MS).start()

    def _row(self, parent, item: Item):
        row = tk.Frame(parent, background=P.surface, padx=px(8), pady=px(8), cursor="hand2")
        row.pack(fill="x")
        mark = tk.Canvas(row, width=px(36), height=px(36), background=P.surface, highlightthickness=0)
        mark.create_oval(0, 0, px(36) - 1, px(36) - 1, fill=mix(P.surface, P.chart, 0.18), outline="")
        mark.create_text(px(18), px(18) + 1, text=icon("star"), fill=P.chart,
                         font=(icon_font(), 12) if icon_font() else TYPE["heading"])
        mark.pack(side="left", padx=(0, px(12)))
        texts = tk.Frame(row, background=P.surface)
        texts.pack(side="left", fill="x", expand=True)
        title = tk.Label(texts, text=item.title, font=TYPE["body_bold"], background=P.surface, foreground=P.text,
                         anchor="w")
        title.pack(fill="x")
        detail = tk.Label(texts, text=item.detail, font=TYPE["small"], background=P.surface, foreground=P.muted,
                          anchor="w")
        detail.pack(fill="x")
        arrow = tk.Label(row, text=icon("forward"), background=P.surface, foreground=P.muted,
                         font=(icon_font(), 9) if icon_font() else TYPE["body"])
        arrow.pack(side="right")

        parts = (row, mark, texts, title, detail, arrow)

        def paint(color):
            for part in parts:
                part.configure(background=color)

        def open_item(event=None):
            self.close()
            item.open()
        for part in parts:
            part.bind("<Enter>", lambda event: paint(P.hover))
            part.bind("<Leave>", lambda event: paint(P.surface))
            part.bind("<Button-1>", open_item)

    def _empty(self, parent):
        box = tk.Frame(parent, background=P.surface, pady=px(16))
        box.pack(fill="x")
        tk.Label(box, text=icon("bell"), background=P.surface, foreground=P.muted,
                 font=(icon_font(), 22) if icon_font() else TYPE["display"]).pack()
        tk.Label(box, text=t("inbox.empty"), font=TYPE["body_bold"], background=P.surface,
                 foreground=P.text).pack(pady=(px(8), 0))
        tk.Label(box, text=t("inbox.empty.detail"), font=TYPE["small"], background=P.surface, foreground=P.muted,
                 wraplength=px(WIDTH - 64), justify="center").pack(pady=(px(4), 0))

    def _focus_out(self, event):
        # Focus moving between the card's own parts is not leaving it
        try:
            focused = self.focus_get()
        except KeyError:  # focus went to a widget Tk cannot name, such as a native dialog
            focused = None
        if focused is None or not str(focused).startswith(str(self)):
            self.close()

    def close(self):
        if self.winfo_exists():
            self.closed_at = time.monotonic()
            self.destroy()
