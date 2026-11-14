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

    # The period switcher: a pill-shaped track, the chosen period on a raised pill
    style.element_create("Nav.track", "image", _box(root, P.nav, None, px(10)), border=px(12), sticky="nsew")
    style.layout("Nav.TFrame", [("Nav.track", {"sticky": "nsew"})])
    # Around the track's corners: the card it is on
    style.configure("Nav.TFrame", background=P.surface)
    _button(style, root, "Nav.TButton", P.nav, None, mix(P.nav, P.surface, 0.5), None, P.nav, None, px(7), P.nav)
    _button(style, root, "NavSelected.TButton", P.surface, None, P.surface, None, P.surface, None, px(7), P.nav)
    for name in ("Nav.TButton", "NavSelected.TButton"):
        style.configure(name, padding=(px(16), px(5)), font=FONT_BOLD)

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
