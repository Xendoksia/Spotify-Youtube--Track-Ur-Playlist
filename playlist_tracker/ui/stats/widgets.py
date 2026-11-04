"""
Parts shared by the pages of the statistics: a scrolling page, bordered cards with an icon, the large
card of a number one track or artist, and the pictures a page shows.
"""

from __future__ import annotations

import colorsys
import tkinter as tk
from tkinter import ttk

from playlist_tracker.music import artwork
from playlist_tracker.ui.charts import placeholder, rounded_rect
from playlist_tracker.ui.theme import TYPE, P, icon, icon_font, mix, px, readable

if artwork.available:
    from PIL import Image, ImageTk

# Space between the cards of a page, in design pixels
SECTION_GAP = 16


class ScrollFrame(ttk.Frame):
    """A vertically scrolling area; widgets go into .content."""

    def __init__(self, parent):
        super().__init__(parent, style="Card.TFrame")
        self.canvas = tk.Canvas(self, background=P.surface, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.content = ttk.Frame(self.canvas, padding=(px(16), px(4), px(16), px(16)), style="Card.TFrame")
        window = self.canvas.create_window(0, 0, window=self.content, anchor="nw")
        self.content.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(window, width=e.width))
        # The wheel scrolls this area only while the mouse is over it
        self.bind("<Enter>", lambda e: self.bind_all("<MouseWheel>", self._on_wheel))
        self.bind("<Leave>", lambda e: self.unbind_all("<MouseWheel>"))
        # A page swapped in under the mouse gets no <Enter>, so it takes the wheel when shown
        self.bind("<Map>", lambda e: self.bind_all("<MouseWheel>", self._on_wheel))

    def _on_wheel(self, event):
        if self.content.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(-event.delta // 120, "units")


def card_row(parent) -> ttk.Frame:
    """A row of cards under the ones before it; cards go into its grid columns."""
    row = ttk.Frame(parent, style="Card.TFrame")
    row.pack(fill="x", pady=(px(SECTION_GAP), 0))
    return row


def card(parent, icon_name: str, title: str, column: int | None = None, weight: int = 1,
         summary: bool = False) -> ttk.Frame:
    """A bordered card with an icon and a title, in a column of parent's grid or packed alone;
    .title and .summary (a muted line under it, when asked for) can be changed later."""
    frame = ttk.Frame(parent, padding=px(16), style="Tile.TFrame")
    header = ttk.Frame(frame, style="Card.TFrame")
    header.pack(fill="x")
    glyph = icon(icon_name)
    if glyph:
        ttk.Label(header, text=glyph, style="Card.TLabel", foreground=P.chart,
                  font=(icon_font(), 13)).pack(side="left", padx=(0, px(12)))
    frame.title = ttk.Label(header, text=title, style="Period.TLabel")
    frame.title.pack(side="left")
    frame.summary = ttk.Label(frame, style="CardMuted.TLabel")
    if summary:
        frame.summary.pack(anchor="w", pady=(px(4), 0))
    # The space between the header and the content
    ttk.Frame(frame, height=px(12), style="Card.TFrame").pack(fill="x")
    if column is None:
        frame.pack(fill="x")
    else:
        parent.columnconfigure(column, weight=weight, uniform="card")
        frame.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else px(SECTION_GAP), 0))
    return frame


def card_column(parent, title: str, column: int) -> ttk.Frame:
    """One of two side by side lists inside a card."""
    parent.columnconfigure(column, weight=1, uniform="column")
    frame = ttk.Frame(parent, style="Card.TFrame")
    frame.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else px(24), 0))
    frame.title = ttk.Label(frame, text=title, style="Section.TLabel")
    frame.title.pack(anchor="w", pady=(0, px(8)))
    return frame


class Pictures:
    """The covers and artist photos a page shows. Missing ones are downloaded in the background, and once
    they are there redraw() is called; several downloads finishing together cause one redraw."""

    def __init__(self, widget: tk.Misc, redraw, delay_ms: int = 400):
        self.widget = widget
        self.redraw = redraw
        self.delay_ms = delay_ms
        self.fetcher = artwork.Fetcher(widget)
        self._images = []
        self._pending = False

    def arrived(self):
        """Something the page waits for has arrived: redraw it soon."""
        if not self._pending:
            self._pending = True
            self.widget.after(self.delay_ms, self._redraw)

    def _redraw(self):
        self._pending = False
        if self.widget.winfo_exists():
            self.redraw()

    def clear(self):
        """Forget the images of the last drawing (call before drawing again)."""
        self._images = []

    def keep(self, image):
        # Tk shows an image only while Python holds a reference to it
        if image is not None:
            self._images.append(image)
        return image

    def cover_path(self, artist: str, album: str, name: str):
        return self.fetcher.cover(artist, album or "", name, self.arrived)

    def artist_path(self, artist: str):
        return self.fetcher.artist(artist, self.arrived)

    def cover(self, row: dict, size: int, radius: int):
        path = self.cover_path(row["artist"], row["album"], row["name"])
        return self.keep(artwork.photo(path, px(size), P.surface, radius=px(radius)))

    def artist_photo(self, name: str, size: int):
        return self.keep(artwork.photo(self.artist_path(name), px(size), P.surface, round_=True))


def card_tint(rgb: tuple[int, int, int], strength: float) -> str:
    """A color of a picture, calmed down to sit behind text and mixed into the card color by strength."""
    hue, saturation, value = colorsys.rgb_to_hsv(*(channel / 255 for channel in rgb))
    saturation = min(saturation, 0.75 if P.dark else 0.6)
    if P.dark:
        value = min(value, 0.6)
    color = "#" + "".join(f"{round(channel * 255):02x}" for channel in colorsys.hsv_to_rgb(hue, saturation, value))
    return mix(P.surface, color, strength)


class Hero(tk.Canvas):
    """A large card for the number one track or artist of the period, with its picture.

    It is drawn on a canvas so its background can run between the two main colors of the picture,
    with the texts on top."""

    IMAGE_SIZE = 132
    PADDING = 16
    # How strongly the picture's colors tint the card, on the left and on the right; more under the mouse
    TINT = {"dark": (0.42, 0.24), "light": (0.20, 0.10)}
    HOVER_TINT = 0.08
    CAPTION_FONT = TYPE["caption"]
    TITLE_FONT = TYPE["display"]
    SUBTITLE_FONT = TYPE["lead"]
    TEXT_FONT = TYPE["body"]

    def __init__(self, parent, caption: str, round_image: bool, image_size: int = IMAGE_SIZE):
        self.image_size = image_size
        super().__init__(parent, height=px(image_size + 2 * self.PADDING), background=P.surface,
                         highlightthickness=0)
        self.caption = caption.upper()
        self.round_image = round_image
        self._content: dict = {"title": "—", "subtitle": "", "detail": "", "path": None, "change": None}
        self._about = ""
        self._action = None
        self._subtitle_action = None
        self._hovered = False
        self._images = []
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))
        self.bind("<Motion>", self._on_motion)
        self.bind("<Button-1>", self._on_click)

    # What the card shows

    def show(self, title: str, subtitle: str, detail: str, path, change: tuple[str, str] | None = None):
        """path: the picture file (or None for a placeholder)."""
        self._content = {"title": title, "subtitle": subtitle, "detail": detail, "path": path, "change": change}
        self._draw()

    def show_empty(self, text: str):
        self.on_click(None)
        self._content = {"title": "—", "subtitle": text, "detail": "", "path": None, "change": None, "empty": True}
        self._draw()

    def set_about(self, text: str):
        """A few sentences about an artist, shown on its own page."""
        self._about = text
        self._draw()

    def on_click(self, action):
        """Make the whole card clickable (None turns it off)."""
        self._action = action
        self.configure(cursor="hand2" if action else "")

    def on_subtitle_click(self, action):
        """Make the subtitle line a link of its own (the artist of a track)."""
        self._subtitle_action = action

    # Mouse

    def _hover(self, on: bool):
        if self._action and on != self._hovered:
            self._hovered = on
            self._draw()

    def _on_subtitle(self, event) -> bool:
        box = self.bbox("subtitle")
        return bool(self._subtitle_action and box and box[0] <= event.x <= box[2] and box[1] <= event.y <= box[3])

    def _on_motion(self, event):
        if self._subtitle_action:
            self.configure(cursor="hand2" if self._on_subtitle(event) or self._action else "")

    def _on_click(self, event):
        action = self._subtitle_action if self._on_subtitle(event) else self._action
        if action:
            action()

    # Drawing

    def _tints(self) -> list[str]:
        """The card's two background colors from its picture, or just the plain card color."""
        colors = artwork.colors(self._content["path"]) if artwork.available else None
        if colors is None:
            return [P.surface]
        left, right = self.TINT["dark" if P.dark else "light"]
        if self._hovered:
            left, right = left + self.HOVER_TINT, right + self.HOVER_TINT
        return [card_tint(color, strength) for color, strength in zip(colors, (left, right))]

    def _background(self, width: int, height: int):
        """The two color gradient of the picture, or None to keep the plain card color."""
        tints = self._tints()
        if len(tints) < 2:
            return None
        start, end = (Image.new("RGB", (1, 1), tint).resize((width, height)) for tint in tints)
        # Left to right, from the picture's first color to its second
        mask = Image.linear_gradient("L").rotate(90).resize((width, height))
        return ImageTk.PhotoImage(Image.composite(start, end, mask))

    def _draw(self):
        width = self.winfo_width()
        if width < 50:
            return
        self.delete("all")
        self._images = []
        content, pad, size = self._content, px(self.PADDING), px(self.image_size)

        if content["path"] is not None:
            image = artwork.picture(content["path"], size, None, round_=self.round_image, radius=px(10))
            if image is not None:
                self._images.append(ImageTk.PhotoImage(image))
                self.create_image(pad, pad, image=self._images[-1], anchor="nw", tags="content")
        if not self._images:
            if content.get("empty"):
                if self.round_image:
                    self.create_oval(pad, pad, pad + size, pad + size, fill=P.nav, outline="", tags="content")
                else:
                    rounded_rect(self, pad, pad, pad + size, pad + size, px(10), fill=P.nav, tags="content")
            else:
                placeholder(self, pad, pad, size, content["title"], self.round_image, ("Segoe UI Semibold", 40))

        left = pad + size + px(16)
        text_width = max(px(120), width - left - pad)
        y = pad + px(10)

        def line(text, font, color, gap=0, tags="content"):
            nonlocal y
            if not text:
                return
            y += gap
            item = self.create_text(left, y, text=text, font=font, fill=color, anchor="nw", width=text_width,
                                    tags=tags)
            y = self.bbox(item)[3]

        # Muted and colored texts get just as much stronger as the picture's colors behind them need
        tints = self._tints()
        muted = readable(P.muted, tints)
        line(self.caption, self.CAPTION_FONT, muted)
        line(content["title"], self.TITLE_FONT, P.text, px(4))
        line(content["subtitle"], self.SUBTITLE_FONT, muted, tags=("content", "subtitle"))
        line(content["detail"], self.TEXT_FONT, P.text, px(10))
        if content["change"]:
            line(content["change"][0], self.TEXT_FONT, readable(content["change"][1], tints), px(4))
        line(self._about, self.TEXT_FONT, P.text, px(12))

        height = max(2 * pad + size, y + pad)
        if int(self.cget("height")) != height:
            self.configure(height=height)
        background = self._background(width, height) if artwork.available else None
        if background is not None:
            self._images.append(background)
            self.create_image(0, 0, image=background, anchor="nw", tags="background")
            self.tag_lower("background")
        self.create_rectangle(0, 0, width - 1, height - 1, outline=P.muted if self._hovered else P.border)
