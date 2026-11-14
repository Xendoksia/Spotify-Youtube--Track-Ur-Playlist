"""
Rounded controls for ttk, as the phone app's: buttons, entry fields and drop-downs with round corners, switches in
place of check boxes, thin scrollbars without arrows and a pill-shaped period switcher.

ttk draws a widget from elements; these replace the borders and indicators with pictures drawn here with Pillow
(antialiased by drawing four times as large and averaging, which leaves no bright halo at the edges), which ttk stretches between their corners. apply() runs after
theme.apply_theme has set the palette. Without Pillow the flat look of apply_theme stays.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from playlist_tracker.ui.theme import FONT_BOLD, P, mix, px

try:
    from PIL import Image, ImageDraw, ImageTk
except ImportError:
    Image = None

# Drawn this many times as large, then made smaller: smooth curves
SUPERSAMPLE = 4
RADIUS = 8
# The pictures must live as long as the styles that use them; made again with every theme
_images: list = []


def _picture(root, width: int, height: int, shapes, base: str = "#000000") -> str:
    """A picture of width x height pixels with shapes(draw, k) drawn on it at k times the size; its Tk name.
    The clear pixels have the color base, so that edges made smaller fade into it rather than into black."""
    k = SUPERSAMPLE
    image = Image.new("RGBA", (width * k, height * k), tuple(int(base[i:i + 2], 16) for i in (1, 3, 5)) + (0,))
    shapes(ImageDraw.Draw(image), k)
    photo = ImageTk.PhotoImage(image.resize((width, height), Image.BOX), master=root)
    _images.append(photo)
    return str(photo)


def _box(root, fill: str, border: str | None = None, radius: int | None = None, size: int | None = None) -> str:
    """A rounded box to stretch: radius in pixels, a 1 px border when given."""
    radius = px(RADIUS) if radius is None else radius
    # Corners of radius + 2 (what ttk keeps as they are) and a middle it stretches
    size = size or 2 * (radius + 2) + 4

    def shapes(draw, k):
        outer = (0, 0, size * k - 1, size * k - 1)
        if border:
            draw.rounded_rectangle(outer, radius * k, fill=border)
            draw.rounded_rectangle((k, k, (size - 1) * k - 1, (size - 1) * k - 1), (radius - 1) * k, fill=fill)
        else:
            draw.rounded_rectangle(outer, radius * k, fill=fill)
    return _picture(root, size, size, shapes, base=border or fill)


def _button(style, root, name: str, fill: str, border: str | None, hover: str, hover_border: str | None,
            disabled: str, disabled_border: str | None, radius: int | None = None, behind: str | None = None):
    """Give the button style `name` a rounded body, lighter or darker under the mouse and when pressed; behind is
    the color around its corners, that of the card it is on."""
    element = f"{name}.body"
    radius = px(RADIUS) if radius is None else radius
    normal = _box(root, fill, border, radius)
    over = _box(root, hover, hover_border, radius)
    style.element_create(element, "image", normal, ("disabled", _box(root, disabled, disabled_border, radius)),
                         ("pressed", over), ("active", over), border=radius + 2, sticky="nsew")
    style.layout(name, [(element, {"sticky": "nsew", "children": [
        ("Button.padding", {"sticky": "nsew", "children": [("Button.label", {"sticky": "nsew"})]})]})])
    # ttk fills the button's background first: around the corners it shows
    behind = behind or P.surface
    style.configure(name, background=behind)
    style.map(name, background=[("disabled", behind), ("pressed", behind), ("active", behind)])


def _field(style, root, name: str, arrow: bool):
    """Entry fields and drop-downs: a rounded field whose border turns blue while typing in it."""
    radius = px(RADIUS)
    element = f"{name}.body"
    normal = _box(root, P.surface, P.border, radius)
    style.element_create(element, "image", normal, ("focus", _box(root, P.surface, P.focus, radius)),
                         ("disabled", _box(root, P.bg, P.border, radius)), border=radius + 2, sticky="nsew")
    inner = [("Entry.padding" if not arrow else "Combobox.padding",
              {"sticky": "nsew", "children": [("Entry.textarea" if not arrow else "Combobox.textarea",
                                               {"sticky": "nsew"})]})]
    if arrow:
        inner.insert(0, (f"{name}.chevron", {"side": "right", "sticky": ""}))
    style.layout(name, [(element, {"sticky": "nsew", "children": inner})])


def _chevron(root, color: str) -> str:
    """A small downward chevron, with room around it."""
    width, height = px(28), px(16)

    def shapes(draw, k):
        middle, top, half = width * k / 2 - px(4) * k, height * k / 2 - px(2) * k, px(4) * k
        draw.line([(middle - half, top), (middle, top + half), (middle + half, top)], fill=color,
                  width=max(1, round(1.6 * k * px(1))), joint="curve")
    return _picture(root, width, height, shapes)


def _switch(root, on: bool, hovered: bool = False) -> str:
    """The phone's switch: a pill track with a round knob, left when off and right (green) when on, and a gap
    after it before the text."""
    width, height, gap = px(36), px(20), px(10)
    track = P.chart if on else (mix(P.surface, P.muted, 0.25) if hovered else P.surface)

    def shapes(draw, k):
        draw.rounded_rectangle((0, 0, width * k - 1, height * k - 1), height * k / 2,
                               fill=P.chart if on else P.muted)
        if not on:
            draw.rounded_rectangle((k * 1.5, k * 1.5, width * k - 1 - k * 1.5, height * k - 1 - k * 1.5),
                                   height * k / 2 - k * 1.5, fill=track)
        knob = height * k * (0.62 if on else 0.5)
        center_x = (width * k - height * k / 2) if on else height * k / 2
        center_y = height * k / 2
        draw.ellipse((center_x - knob / 2, center_y - knob / 2, center_x + knob / 2, center_y + knob / 2),
                     fill="#ffffff" if on else P.muted)
    return _picture(root, width + gap, height, shapes)


def _thumb(root, active: bool) -> str:
    """A thin rounded scrollbar thumb, with a little room on both sides of it."""
    width, bar = px(12), px(6)
    color = P.scrollbar_active if active else P.scrollbar

    def shapes(draw, k):
        left = (width - bar) * k / 2
        draw.rounded_rectangle((left, 0, left + bar * k - 1, width * 2 * k - 1), bar * k / 2, fill=color)
    return _picture(root, width, width * 2, shapes)


def apply(root: tk.Misc, style: ttk.Style, accents: dict[str, tuple[str, str]]) -> None:
    """accents maps a button style prefix to (color, pressed color), as in theme.apply_theme."""
    if Image is None:
        return
    _images.clear()

    # Buttons
    _button(style, root, "TButton", P.surface, P.border, P.hover, P.muted, P.bg, P.border)
    _button(style, root, "Icon.TButton", P.surface, P.border, P.hover, P.muted, P.bg, P.border)
    style.configure("TButton", padding=(px(16), px(7)))
    _button(style, root, "Accent.TButton", P.focus, None, P.focus_active, None, P.disabled, None)
    # On the window's background rather than on a card (the settings' Save)
    _button(style, root, "Page.Accent.TButton", P.focus, None, P.focus_active, None, P.disabled, None, behind=P.bg)
    style.configure("Page.Accent.TButton", foreground="#ffffff")
    for prefix, (color, active) in accents.items():
        _button(style, root, f"{prefix}.Accent.TButton", color, None, active, None, P.disabled, None)

    # The period switcher: the chosen period on a raised pill (the track under them is drawn by track())
    _button(style, root, "Nav.TButton", P.nav, None, mix(P.nav, P.surface, 0.5), None, P.nav, None, px(7), P.nav)
    _button(style, root, "NavSelected.TButton", P.surface, None, P.surface, None, P.surface, None, px(7), P.nav)
    for name in ("Nav.TButton", "NavSelected.TButton"):
        style.configure(name, padding=(px(16), px(5)), font=FONT_BOLD)

    # Frames holding other widgets are never given an image element in their layout: that made Tk recompute the
    # layout of pages with them for ever (the app froze at start). Their rounded shape is drawn behind their
    # widgets instead (Backdrop: tile(), track()); their flat square border gives way to it
    style.configure("Tile.TFrame", bordercolor=P.surface)

    # Entry fields and drop-downs
    _field(style, root, "TEntry", arrow=False)
    style.element_create("TCombobox.chevron", "image", _chevron(root, P.muted),
                         ("disabled", _chevron(root, P.disabled)))
    _field(style, root, "TCombobox", arrow=True)
    for name in ("TEntry", "TCombobox"):
        style.configure(name, padding=(px(10), px(6)))

    # Switches in place of check boxes
    style.element_create("Switch.indicator", "image", _switch(root, False),
                         ("selected", _switch(root, True)), ("active", _switch(root, False, hovered=True)))
    style.layout("Card.TCheckbutton", [("Checkbutton.padding", {"sticky": "nsew", "children": [
        ("Switch.indicator", {"side": "left", "sticky": ""}),
        ("Checkbutton.label", {"side": "left", "sticky": "nsew"})]})])

    # Thin scrollbars without arrows
    style.element_create("Thin.thumb", "image", _thumb(root, False), ("active", _thumb(root, True)),
                         ("pressed", _thumb(root, True)), border=(0, px(6)), sticky="ns")
    style.layout("Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
        ("Thin.thumb", {"expand": "1", "sticky": "nsew"})]})])
    style.configure("Vertical.TScrollbar", troughcolor=P.surface, bordercolor=P.surface, lightcolor=P.surface,
                    darkcolor=P.surface)


_corners: dict = {}


def _corner(radius: int, inset: int):
    """The top left corner of a rounded mask, radius pixels square, antialiased; made once for each size."""
    key = (radius, inset)
    if key not in _corners:
        k = SUPERSAMPLE
        corner = Image.new("L", (radius * k, radius * k), 0)
        ImageDraw.Draw(corner).ellipse((inset * k, inset * k, (2 * radius - inset) * k - 1,
                                        (2 * radius - inset) * k - 1), fill=255)
        _corners[key] = corner.resize((radius, radius), Image.BOX)
    return _corners[key]


def _rounded_mask(width: int, height: int, radius: int, inset: int = 0):
    """A mask of a rounded rectangle filling width x height, inset pixels in from its edges: two plain rectangles
    and the four corners, which are drawn smooth only once (resizing the window draws cards again and again)."""
    radius = max(1, min(radius, width // 2, height // 2))
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    draw.rectangle((inset, radius, width - 1 - inset, height - 1 - radius), fill=255)
    draw.rectangle((radius, inset, width - 1 - radius, height - 1 - inset), fill=255)
    corner = _corner(radius, inset)
    mask.paste(corner, (0, 0))
    mask.paste(corner.transpose(Image.FLIP_LEFT_RIGHT), (width - radius, 0))
    mask.paste(corner.transpose(Image.FLIP_TOP_BOTTOM), (0, height - radius))
    mask.paste(corner.transpose(Image.ROTATE_180), (width - radius, height - radius))
    return mask


def rounded_card(width: int, height: int, fill, border: str | None, behind: str, radius: int | None = None):
    """A card of width x height as a Pillow image: fill (a color, or an image of that size such as a gradient) with
    round corners and a 1 px border, on the color behind it. None without Pillow."""
    if Image is None or width < 2 or height < 2:
        return None
    radius = px(RADIUS + 4) if radius is None else radius
    card = Image.new("RGB", (width, height), behind)
    body = fill if not isinstance(fill, str) else Image.new("RGB", (width, height), fill)
    if border:
        card.paste(Image.new("RGB", (width, height), border), (0, 0), _rounded_mask(width, height, radius))
        card.paste(body, (0, 0), _rounded_mask(width, height, radius, inset=1))
    else:
        card.paste(body, (0, 0), _rounded_mask(width, height, radius))
    return card


class Backdrop:
    """A rounded card drawn behind the widgets of a frame, as rounded_card, following its size. The frame's own
    background should be the color behind the card, and its children keep inside the corners. It is a picture
    placed under them, so it takes no part in laying them out."""

    # Drawn again this long after the frame's size last changed, not on every step of resizing the window
    DELAY_MS = 30

    def __init__(self, frame: tk.Misc, fill: str, border: str | None, behind: str, radius: int | None = None):
        self.frame, self.fill, self.border, self.behind, self.radius = frame, fill, border, behind, radius
        self.label = tk.Label(frame, background=behind, borderwidth=0, highlightthickness=0)
        # A ttk frame places inside its padding: out by as much, to cover all of it
        left, top, right, bottom = _padding(frame)
        self.label.place(x=-left, y=-top, relwidth=1, relheight=1, width=left + right, height=top + bottom)
        self.label.lower()
        self._size = None
        self._photo = None
        self._job = None
        frame.bind("<Configure>", lambda event: self._later(), add="+")

    def set_border(self, border: str | None):
        if border != self.border:
            self.border = border
            self._size = None
            self.draw()

    def _later(self):
        if self._job is not None:
            self.frame.after_cancel(self._job)
        self._job = self.frame.after(self.DELAY_MS, self.draw)

    def draw(self):
        self._job = None
        if not self.frame.winfo_exists():
            return
        size = (self.frame.winfo_width(), self.frame.winfo_height())
        if size == self._size:
            return
        self._size = size
        image = rounded_card(*size, self.fill, self.border, self.behind, self.radius)
        if image is not None:
            self._photo = ImageTk.PhotoImage(image, master=self.frame)
            self.label.configure(image=self._photo)


def _padding(frame: tk.Misc) -> tuple[int, int, int, int]:
    """A ttk frame's padding as left, top, right, bottom (none for a plain tk frame)."""
    try:
        values = [int(float(str(value))) for value in frame.tk.splitlist(frame.cget("padding"))]
    except (tk.TclError, ValueError):
        return 0, 0, 0, 0
    if not values:
        return 0, 0, 0, 0
    left = values[0]
    top = values[1] if len(values) > 1 else left
    right = values[2] if len(values) > 2 else left
    bottom = values[3] if len(values) > 3 else top
    return left, top, right, bottom


def tile(parent, behind: str | None = None, **options) -> ttk.Frame:
    """A card (a ttk frame in the Tile style) with round corners; behind is the color around it, by default that
    of the surface it is on."""
    frame = ttk.Frame(parent, style="Tile.TFrame", **options)
    if Image is not None:
        frame.backdrop = Backdrop(frame, P.surface, P.border, behind or P.surface)
    return frame


def track(frame: ttk.Frame) -> None:
    """The pill-shaped track of the period switcher, on a card."""
    if Image is not None:
        frame.configure(style="Card.TFrame")
        frame.backdrop = Backdrop(frame, P.nav, None, P.surface, px(10))
