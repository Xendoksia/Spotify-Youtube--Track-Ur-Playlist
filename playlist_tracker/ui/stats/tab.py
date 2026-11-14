"""
Statistics tab of the Listening section. It shows the overview, and in its place the page of a track,
artist or album, or the monthly summary.
"""

from __future__ import annotations

from datetime import datetime
from tkinter import ttk

from playlist_tracker.ui.stats import wrapped
from playlist_tracker.ui.stats.detail import DetailView
from playlist_tracker.ui.stats.overview import Overview


class StatsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, style="Card.TFrame")
        self.detail = None
        self.wrapped = None
        self.overview = Overview(self, self.open_detail, self.open_wrapped)
        self.overview.pack(fill="both", expand=True)

    def refresh(self):
        if self.detail is not None:
            self.detail.refresh()
        self.overview.refresh()

    def open_detail(self, column: str, key: str):
        """Show a track, artist or album page in place of the statistics."""
        if self.detail is None:
            self.detail = DetailView(self, on_close=self.show_overview)
            self._bind_keys()
        self._show_layer(self.detail)
        self.detail.open(column, key)

    def open_wrapped(self, month: tuple[datetime, datetime] | None = None):
        """Show the summary of the given month or year, by default the month's available today."""
        month = month or wrapped.available_month()
        if month is None:
            return
        if self.wrapped is None:
            self.wrapped = wrapped.WrappedView(self, on_close=self.show_overview)
            self._bind_keys()
        self._show_layer(self.wrapped)
        self.wrapped.show(*month)

    def show_overview(self):
        self._show_layer(self.overview)

    def _show_layer(self, layer):
        for other in (self.overview, self.detail, self.wrapped):
            if other is not None and other is not layer:
                other.pack_forget()
        layer.pack(fill="both", expand=True)

    def _bind_keys(self):
        if getattr(self, "_keys_bound", False):
            return
        self._keys_bound = True
        window = self.winfo_toplevel()
        window.bind("<Escape>", lambda e: self._layer_key(0), add="+")
        window.bind("<Alt-Left>", lambda e: self._layer_key(-1), add="+")
        window.bind("<Alt-Right>", lambda e: self._layer_key(1), add="+")
        window.bind("<Left>", lambda e: self._layer_key(-1, slides_only=True), add="+")
        window.bind("<Right>", lambda e: self._layer_key(1, slides_only=True), add="+")

    def _layer_key(self, direction: int, slides_only: bool = False):
        """Alt+Left / Alt+Right (and plain arrows in the summary) go back and forward, Escape (0) closes."""
        for layer in (self.detail, self.wrapped):
            if layer is None or not layer.winfo_ismapped() or (slides_only and layer is not self.wrapped):
                continue
            if direction:
                layer.step(direction)
            else:
                layer.close()
