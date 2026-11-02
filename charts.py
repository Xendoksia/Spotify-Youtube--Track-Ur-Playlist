"""
Small single-series charts drawn on a tkinter Canvas, so no plotting package is needed.

Marks follow one spec: bars at most 24px thick with a 4px rounded data end and a square
baseline, 2px surface gaps between touching bars, hairline recessive gridlines, text in
text colors (never the mark color) and a hover tooltip on every mark.
"""

from __future__ import annotations

import math
import tkinter as tk
from collections.abc import Callable
from tkinter import font as tkfont

from i18n import number
from theme import FONT, P

RADIUS = 4
MAX_THICKNESS = 24
GAP = 2
SMALL_FONT = ("Segoe UI", 9)


def rounded_bar(canvas: tk.Canvas, x0: float, y0: float, x1: float, y1: float, end: str, **options) -> int:
    """Draw a bar whose data end ("right" or "top") is rounded and whose baseline is square."""
    radius = min(RADIUS, (x1 - x0) / 2, (y1 - y0) / 2)
    if radius < 1:
        return canvas.create_rectangle(x0, y0, x1, y1, width=0, **options)
    if end == "right":
        corners = [(x0, y0, None), (x1, y0, (x1 - radius, y0 + radius, -90)), (x1, y1, (x1 - radius, y1 - radius, 0)),
                   (x0, y1, None)]
    else:
        corners = [(x0, y1, None), (x0, y0, (x0 + radius, y0 + radius, 180)), (x1, y0, (x1 - radius, y0 + radius, 270)),
                   (x1, y1, None)]
    points = []
    for x, y, arc in corners:
        if arc is None:
            points += [x, y]
            continue
        cx, cy, start = arc
        for step in range(7):
            angle = math.radians(start + step * 15)
            points += [cx + radius * math.cos(angle), cy + radius * math.sin(angle)]
    return canvas.create_polygon(points, width=0, **options)


def rounded_rect(canvas: tk.Canvas, x0: float, y0: float, x1: float, y1: float, radius: float, **options) -> int:
    """Draw a rectangle with all four corners rounded."""
    points = []
    for cx, cy, start in ((x1 - radius, y0 + radius, -90), (x1 - radius, y1 - radius, 0),
                          (x0 + radius, y1 - radius, 90), (x0 + radius, y0 + radius, 180)):
        for step in range(7):
            angle = math.radians(start + step * 15)
            points += [cx + radius * math.cos(angle), cy + radius * math.sin(angle)]
    return canvas.create_polygon(points, width=0, **options)


def placeholder(canvas: tk.Canvas, x: float, y: float, size: float, text: str, round_: bool, font) -> None:
    """Draw a neutral tile with the first letter of the name, for items without a picture."""
    if round_:
        canvas.create_oval(x, y, x + size, y + size, fill=P.nav, outline="")
    else:
        rounded_rect(canvas, x, y, x + size, y + size, min(6, size / 5), fill=P.nav)
    canvas.create_text(x + size / 2, y + size / 2, text=(text.strip()[:1] or "♪").upper(), fill=P.muted, font=font)


def nice_max(value: float) -> int:
    """Round an axis maximum up to 1, 2 or 5 times a power of ten."""
    if value <= 0:
        return 1
    power = 10 ** math.floor(math.log10(value))
    return int(next(m * power for m in (1, 2, 5, 10) if m * power >= value))


class Chart(tk.Canvas):
    """Base class: redraws on resize and shows a tooltip for the mark under the mouse."""

    def __init__(self, parent, height: int, empty_text: str = ""):
        super().__init__(parent, height=height, background=P.surface, highlightthickness=0)
        self.empty_text = empty_text
        self.font = tkfont.Font(font=FONT)
        self.small_font = tkfont.Font(font=SMALL_FONT)
        self._marks: dict[int, tuple[str, list[int]]] = {}
        self._clicks: dict[int, Callable[[], None]] = {}
        self._hovered: int | None = None
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda e: self._hover(None, 0, 0))
        self.bind("<Button-1>", self._on_click)

    def redraw(self):
        self.delete("all")
        self._marks.clear()
        self._clicks.clear()
        self._hovered = None
        width, height = self.winfo_width(), self.winfo_height()
        if width < 50 or height < 30:
            return
        if not self.draw(width, height):
            self.create_text(width / 2, height / 2, text=self.empty_text, fill=P.muted, font=FONT)

    def draw(self, width: int, height: int) -> bool:
        """Draw the chart; return False when there is nothing to show."""
        raise NotImplementedError

    def add_hit_area(self, x0, y0, x1, y1, tooltip: str, highlight: list[int],
                     on_click: Callable[[], None] | None = None):
        """Register an invisible area bigger than the mark that triggers its tooltip (and on_click)."""
        area = self.create_rectangle(x0, y0, x1, y1, outline="", fill="", tags="hit")
        self._marks[area] = (tooltip, highlight)
        if on_click:
            self._clicks[area] = on_click

    def _area_at(self, x, y):
        items = [i for i in self.find_overlapping(x, y, x, y) if i in self._marks]
        return items[-1] if items else None

    def _on_motion(self, event):
        item = self._area_at(event.x, event.y)
        self.configure(cursor="hand2" if item in self._clicks else "")
        self._hover(item, event.x, event.y)

    def _on_click(self, event):
        action = self._clicks.get(self._area_at(event.x, event.y))
        if action:
            action()

    def _hover(self, item, x, y):
        self.delete("tooltip")
        if self._hovered is not None and self._hovered != item:
            for mark in self._marks[self._hovered][1]:
                self.itemconfigure(mark, fill=P.chart)
        self._hovered = item
        if item is None:
            return
        tooltip, highlight = self._marks[item]
        for mark in highlight:
            self.itemconfigure(mark, fill=P.chart_hover)
        text = self.create_text(0, 0, text=tooltip, anchor="nw", fill=P.text, font=FONT, tags="tooltip")
        x0, y0, x1, y1 = self.bbox(text)
        box_width, box_height = x1 - x0 + 20, y1 - y0 + 14
        left = min(x + 14, self.winfo_width() - box_width - 2)
        top = y + 16 if y + 16 + box_height < self.winfo_height() else y - box_height - 8
        left, top = max(left, 2), max(top, 2)
        box = self.create_rectangle(left, top, left + box_width, top + box_height, fill=P.surface,
                                    outline=P.border, tags="tooltip")
        self.coords(text, left + 10, top + 7)
        self.tag_raise(box)
        self.tag_raise(text)


class BarList(Chart):
    """Ranked horizontal bars: a label column on the left, bars with the value at their tip on the right."""

    ROW_HEIGHT = 44
    IMAGE_SIZE = 32

    def __init__(self, parent, empty_text: str = "", rows: int = 10, round_images: bool = False, first_rank: int = 1):
        super().__init__(parent, self.ROW_HEIGHT * rows, empty_text)
        self.rows: list[dict] = []
        self.round_images = round_images
        self.first_rank = first_rank

    def set_rows(self, rows: list[dict]):
        """rows: dicts with title, subtitle, value, value_text, tooltip and optionally image (a Tk image)
        and change: (text, color) shown under the rank, such as the move since the previous period,
        and on_click: called when the row is clicked."""
        self.rows = rows
        self.redraw()

    def _fit(self, text: str, font: tkfont.Font, width: float) -> str:
        if font.measure(text) <= width:
            return text
        while text and font.measure(text + "…") > width:
            text = text[:-1]
        return text + "…"

    def draw(self, width, height):
        if not self.rows:
            return False
        row_height = self.ROW_HEIGHT
        label_width = width * 0.5
        rank_width = max(self.small_font.measure(text) for text in
                         [str(self.first_rank + len(self.rows))] + [r["change"][0] for r in self.rows if r.get("change")]
                         ) + 8
        size = self.IMAGE_SIZE
        text_left = rank_width + size + 10
        value_width = max(self.small_font.measure(r["value_text"]) for r in self.rows) + 8
        bar_left = label_width + 12
        bar_space = width - bar_left - value_width
        top_value = max(r["value"] for r in self.rows) or 1
        thickness = 12

        for index, row in enumerate(self.rows):
            middle = index * row_height + row_height / 2
            change = row.get("change")
            self.create_text(rank_width - 6, middle - 8 if change else middle, text=str(self.first_rank + index),
                             anchor="e", fill=P.muted, font=self.small_font)
            if change:
                self.create_text(rank_width - 6, middle + 9, text=change[0], anchor="e", fill=change[1],
                                 font=self.small_font)
            if row.get("image"):
                self.create_image(rank_width, middle, image=row["image"], anchor="w")
            else:
                placeholder(self, rank_width, middle - size / 2, size, row["title"], self.round_images,
                            self.small_font)
            text_width = label_width - text_left
            if row.get("subtitle"):
                self.create_text(text_left, middle - 8, text=self._fit(row["title"], self.font, text_width),
                                 anchor="w", fill=P.text, font=self.font)
                self.create_text(text_left, middle + 9, text=self._fit(row["subtitle"], self.small_font, text_width),
                                 anchor="w", fill=P.muted, font=self.small_font)
            else:
                self.create_text(text_left, middle, text=self._fit(row["title"], self.font, text_width),
                                 anchor="w", fill=P.text, font=self.font)
            length = max(2, bar_space * row["value"] / top_value)
            bar = rounded_bar(self, bar_left, middle - thickness / 2, bar_left + length, middle + thickness / 2,
                              "right", fill=P.chart)
            self.create_text(bar_left + length + 6, middle, text=row["value_text"], anchor="w", fill=P.text,
                             font=self.small_font)
            self.add_hit_area(0, middle - row_height / 2, width, middle + row_height / 2, row["tooltip"], [bar],
                              row.get("on_click"))
        return True


class ColumnChart(Chart):
    """Vertical columns over time buckets, with a light y grid and spaced-out x labels."""

    def __init__(self, parent, height: int, empty_text: str = ""):
        super().__init__(parent, height, empty_text)
        self.buckets: list[dict] = []

    def set_buckets(self, buckets: list[dict]):
        """buckets: dicts with label, value and tooltip."""
        self.buckets = buckets
        self.redraw()

    def draw(self, width, height):
        if not self.buckets or not any(b["value"] for b in self.buckets):
            return False
        axis_max = nice_max(max(b["value"] for b in self.buckets))
        axis_width = self.small_font.measure(str(axis_max)) + 10
        label_height = self.small_font.metrics("linespace") + 6
        top, bottom = 8, height - label_height
        plot_width = width - axis_width

        for tick in (0, axis_max / 2, axis_max):
            y = bottom - (bottom - top) * tick / axis_max
            self.create_line(axis_width, y, width, y, fill=P.grid if tick else P.border)
            if tick == int(tick):
                self.create_text(axis_width - 8, y, text=number(int(tick)), anchor="e", fill=P.muted,
                                 font=self.small_font)

        slot = plot_width / len(self.buckets)
        thickness = max(1, min(MAX_THICKNESS, slot - GAP))
        widest_label = max(self.small_font.measure(b["label"]) for b in self.buckets) + 10
        label_every = max(1, math.ceil(widest_label / slot))
        for index, bucket in enumerate(self.buckets):
            center = axis_width + slot * index + slot / 2
            marks = []
            if bucket["value"]:
                bar_top = bottom - (bottom - top) * bucket["value"] / axis_max
                marks.append(rounded_bar(self, center - thickness / 2, bar_top, center + thickness / 2, bottom,
                                         "top", fill=P.chart))
            if index % label_every == 0:
                self.create_text(center, bottom + 4, text=bucket["label"], anchor="n", fill=P.muted,
                                 font=self.small_font)
            self.add_hit_area(center - slot / 2, top, center + slot / 2, bottom, bucket["tooltip"], marks)
        return True
