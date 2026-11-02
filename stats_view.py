"""
Statistics tab of the Listening section: most played tracks and artists of a week, month or
year, counted from the plays recorded in listening.db.
"""

from __future__ import annotations

import colorsys
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk

import artist_info
import artwork
import collage
import listening
from charts import BarList, ColumnChart, count_up, mix, placeholder, rounded_rect
from i18n import number, t
from theme import P, icon, px
from tracker import format_date

available = artwork.available
if available:
    from PIL import Image, ImageTk

TOP_COUNT = 10
DISCOVERY_COUNT = 5
GENRE_COUNT = 8
GENRE_REDRAW_MS = 3000
# Side of the album collage, in design pixels
COLLAGE_PREVIEW = 420
FORGOTTEN_DAYS = 30
FORGOTTEN_MIN_PLAYS = 3


def plays_text(count: int) -> str:
    return t("stats.plays_one") if count == 1 else t("stats.plays", count=number(count))


def tracks_text(count: int) -> str:
    return t("stats.different_tracks_one") if count == 1 else t("stats.different_tracks", count=number(count))


def summary_text(*parts: str, minutes: int) -> str:
    """Join details with the listening time; plays recorded without a duration add none, so 0 is left out."""
    return "  ·  ".join([*parts, duration_text(minutes)] if minutes else parts)


def duration_text(minutes: int) -> str:
    hours, minutes = divmod(int(minutes), 60)
    return t("stats.hours_minutes", hours=number(hours), minutes=minutes) if hours else t("stats.minutes",
                                                                                        minutes=minutes)


def month_name(month: int, short: bool = False) -> str:
    return t("stats.months_short" if short else "stats.months").split(",")[month - 1]


def period_title(period: str, start: datetime, end: datetime) -> str:
    last = end - timedelta(days=1)
    if period == "week":
        if start.month == last.month:
            return f"{start.day} – {last.day} {month_name(last.month)} {last.year}"
        first_year = f" {start.year}" if start.year != last.year else ""
        return (f"{start.day} {month_name(start.month, True)}{first_year} – "
                f"{last.day} {month_name(last.month, True)} {last.year}")
    if period == "month":
        return f"{month_name(start.month)} {start.year}"
    if period == "year":
        return str(start.year)
    return t("stats.all_time")


def change_tip(change, key, rank) -> str:
    """The rank change written out, as an extra tooltip line."""
    result = change(key, rank, long=True)
    return f"\n{result[0]}" if result else ""


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
    CAPTION_FONT = ("Segoe UI Semibold", 9)
    TITLE_FONT = ("Segoe UI Semibold", 17)
    SUBTITLE_FONT = ("Segoe UI", 11)
    TEXT_FONT = ("Segoe UI", 10)

    def __init__(self, parent, caption: str, round_image: bool):
        super().__init__(parent, height=px(self.IMAGE_SIZE + 2 * self.PADDING), background=P.surface,
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

    def _over_subtitle(self, event) -> bool:
        box = self.bbox("subtitle")
        return bool(self._subtitle_action and box and box[0] <= event.x <= box[2] and box[1] <= event.y <= box[3])

    def _on_motion(self, event):
        if self._subtitle_action:
            self.configure(cursor="hand2" if self._over_subtitle(event) or self._action else "")

    def _on_click(self, event):
        if self._over_subtitle(event):
            self._subtitle_action()
        elif self._action:
            self._action()

    # Drawing

    def _background(self, width: int, height: int):
        """The two color gradient of the picture, or None to keep the plain card color."""
        colors = artwork.colors(self._content["path"])
        if colors is None:
            return None
        left, right = self.TINT["dark" if P.dark else "light"]
        if self._hovered:
            left, right = left + self.HOVER_TINT, right + self.HOVER_TINT
        start, end = (Image.new("RGB", (1, 1), card_tint(color, strength)).resize((width, height))
                      for color, strength in zip(colors, (left, right)))
        # Left to right, from the picture's first color to its second
        mask = Image.linear_gradient("L").rotate(90).resize((width, height))
        return ImageTk.PhotoImage(Image.composite(start, end, mask))

    def _draw(self):
        width = self.winfo_width()
        if width < 50:
            return
        self.delete("all")
        self._images = []
        content, pad, size = self._content, px(self.PADDING), px(self.IMAGE_SIZE)

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

        left = pad + size + px(18)
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

        line(self.caption, self.CAPTION_FONT, P.muted)
        line(content["title"], self.TITLE_FONT, P.text, px(4))
        line(content["subtitle"], self.SUBTITLE_FONT, P.muted, tags=("content", "subtitle"))
        line(content["detail"], self.TEXT_FONT, P.text, px(10))
        if content["change"]:
            line(content["change"][0], self.TEXT_FONT, content["change"][1], px(4))
        line(self._about, self.TEXT_FONT, P.text, px(12))

        height = max(2 * pad + size, y + pad)
        if int(self.cget("height")) != height:
            self.configure(height=height)
        background = self._background(width, height) if available else None
        if background is not None:
            self._images.append(background)
            self.create_image(0, 0, image=background, anchor="nw", tags="background")
            self.tag_lower("background")
        self.create_rectangle(0, 0, width - 1, height - 1, outline=P.muted if self._hovered else P.border)


class StatsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, style="Card.TFrame")
        self.period = "week"
        self.offset = 0
        self.fetcher = artwork.Fetcher(self)
        self._images = []
        self._refresh_pending = False
        self.detail = None
        self.wrapped = None
        self.overview = ttk.Frame(self, style="Card.TFrame")
        self.overview.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        toolbar = ttk.Frame(self.overview, style="Card.TFrame")
        toolbar.pack(fill="x", padx=px(16), pady=(px(16), 0))
        switcher = ttk.Frame(toolbar, padding=px(3), style="Nav.TFrame")
        switcher.pack(side="left")
        self.period_buttons = {}
        for period in listening.PERIODS:
            button = ttk.Button(switcher, text=t(f"stats.period.{period}"), style="Nav.TButton",
                                command=lambda period=period: self.select_period(period))
            button.pack(side="left")
            self.period_buttons[period] = button
        self.previous_button = ttk.Button(toolbar, text=icon("back"), style="Icon.TButton", command=lambda: self.move(1))
        self.previous_button.pack(side="left", padx=(px(16), 0))
        self.next_button = ttk.Button(toolbar, text=icon("forward"), style="Icon.TButton", command=lambda: self.move(-1))
        self.next_button.pack(side="left", padx=(px(4), 0))
        self.title_label = ttk.Label(toolbar, style="Period.TLabel")
        self.title_label.pack(side="left", padx=px(12))
        # Shown only on the days the monthly summary is there (see wrapped_view.SHOW_DAYS)
        self.wrapped_button = ttk.Button(toolbar, text=t("wrapped.button"), style="Accent.TButton",
                                         command=self.open_wrapped)

        page = ScrollFrame(self.overview)
        page.pack(fill="both", expand=True, pady=(px(12), 0))
        content = page.content

        tiles = ttk.Frame(content, style="Card.TFrame")
        tiles.pack(fill="x")
        self.tiles = {}
        for index, name in enumerate(("plays", "time", "tracks", "artists")):
            tiles.columnconfigure(index, weight=1, uniform="tile")
            tile = ttk.Frame(tiles, padding=(px(14), px(10)), style="Tile.TFrame")
            tile.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else px(10), 0))
            ttk.Label(tile, text=t(f"stats.tile.{name}"), style="CardMuted.TLabel").pack(anchor="w")
            value = ttk.Label(tile, style="TileValue.TLabel")
            value.pack(anchor="w")
            delta = ttk.Label(tile, style="CardMuted.TLabel", font=("Segoe UI", 9))
            delta.pack(anchor="w")
            self.tiles[name] = (value, delta)

        heroes = ttk.Frame(content, style="Card.TFrame")
        heroes.pack(fill="x", pady=(px(16), 0))
        heroes.columnconfigure((0, 1), weight=1, uniform="hero")
        self.track_hero = Hero(heroes, t("stats.hero.track"), round_image=False)
        self.track_hero.grid(row=0, column=0, sticky="nsew")
        self.artist_hero = Hero(heroes, t("stats.hero.artist"), round_image=True)
        self.artist_hero.grid(row=0, column=1, sticky="nsew", padx=(px(10), 0))

        empty = t("stats.empty")
        lists = ttk.Frame(content, style="Card.TFrame")
        lists.pack(fill="x", pady=(px(24), 0))
        self.top_tracks = BarList(self._card(lists, t("stats.top_tracks"), 0), empty, TOP_COUNT - 1, first_rank=2)
        self.top_artists = BarList(self._card(lists, t("stats.top_artists"), 1), empty, TOP_COUNT - 1,
                                   round_images=True, first_rank=2)

        # Tracks and artists heard for the first time ever in this period
        self.discoveries = ttk.Frame(content, style="Card.TFrame")
        self.discoveries.pack(fill="x", pady=(px(24), 0))
        ttk.Label(self.discoveries, text=t("stats.discoveries"), style="Period.TLabel").pack(anchor="w")
        self.discovery_summary = ttk.Label(self.discoveries, style="CardMuted.TLabel")
        self.discovery_summary.pack(anchor="w", pady=(px(2), px(12)))
        discovery_lists = ttk.Frame(self.discoveries, style="Card.TFrame")
        discovery_lists.pack(fill="x")
        empty_new = t("stats.discoveries.none")
        self.new_tracks = BarList(self._card(discovery_lists, t("stats.new_tracks"), 0), empty_new, DISCOVERY_COUNT)
        self.new_artists = BarList(self._card(discovery_lists, t("stats.new_artists"), 1), empty_new,
                                   DISCOVERY_COUNT, round_images=True)
        for chart in (self.new_tracks, self.new_artists):
            chart.pack(fill="x")

        # Share of the period's plays per genre; an artist's plays count for its main genre
        self.genres_section = ttk.Frame(content, style="Card.TFrame")
        self.genres_section.pack(fill="x", pady=(px(24), 0))
        ttk.Label(self.genres_section, text=t("stats.genres"), style="Period.TLabel").pack(anchor="w")
        self.genre_summary = ttk.Label(self.genres_section, style="CardMuted.TLabel")
        self.genre_summary.pack(anchor="w", pady=(px(2), px(12)))
        self.genres = BarList(self.genres_section, t("stats.genres.none"), GENRE_COUNT, images=False)
        self.genres.pack(fill="x")
        self._genres_pending = False
        self._range = None

        # Tracks once played a lot but not lately; it looks back from today, so it belongs to the all time view
        self.forgotten_section = ttk.Frame(content, style="Card.TFrame")
        ttk.Label(self.forgotten_section, text=t("stats.forgotten"), style="Period.TLabel").pack(anchor="w")
        ttk.Label(self.forgotten_section, style="CardMuted.TLabel",
                  text=t("stats.forgotten.summary", days=FORGOTTEN_DAYS, plays=FORGOTTEN_MIN_PLAYS)
                  ).pack(anchor="w", pady=(px(2), px(12)))
        self.forgotten = BarList(self.forgotten_section, t("stats.forgotten.none", days=FORGOTTEN_DAYS), TOP_COUNT)
        self.forgotten.pack(fill="x")

        self.charts = charts = ttk.Frame(content, style="Card.TFrame")
        charts.pack(fill="x", pady=(px(24), 0))
        self.timeline_card = self._card(charts, "", 0, weight=3)
        self.timeline = ColumnChart(self.timeline_card, 170, empty)
        self.hours = ColumnChart(self._card(charts, t("stats.hours"), 1, weight=2), 170, empty)
        for chart in (self.top_tracks, self.top_artists, self.timeline, self.hours):
            chart.pack(fill="x")

        # The period's most played album covers in a grid; a cover opens its artist's page
        self.collage_albums = []
        self.collage_section = ttk.Frame(content, style="Card.TFrame")
        if collage.available:
            self.collage_section.pack(fill="x", pady=(px(24), 0))
        ttk.Label(self.collage_section, text=t("stats.collage"), style="Period.TLabel").pack(anchor="w")
        ttk.Label(self.collage_section, text=t("stats.collage.summary"), style="CardMuted.TLabel"
                  ).pack(anchor="w", pady=(px(2), px(12)))
        self.collage_preview = ttk.Label(self.collage_section, style="Card.TLabel", cursor="hand2")
        self.collage_preview.pack(anchor="center")
        self.collage_preview.bind("<Button-1>", self._collage_click)

    def _card(self, parent, title: str, column: int, weight: int = 1) -> ttk.Frame:
        parent.columnconfigure(column, weight=weight, uniform="card")
        card = ttk.Frame(parent, style="Card.TFrame")
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else px(32), 0))
        card.title = ttk.Label(card, text=title, style="Section.TLabel")
        card.title.pack(anchor="w", pady=(0, px(8)))
        return card

    def select_period(self, period: str):
        self.period, self.offset = period, 0
        self.refresh()

    def move(self, step: int):
        self.offset = max(0, self.offset + step)
        self.refresh()

    def _artwork_arrived(self):
        # Several downloads usually finish together, so redraw once for all of them
        if not self._refresh_pending:
            self._refresh_pending = True
            self.after(400, self.refresh)

    def _opener(self, column: str, key: str):
        return lambda: self.open_detail(column, key)

    def open_detail(self, column: str, key: str):
        """Show a track or artist page in place of the statistics."""
        if self.detail is None:
            # Imported here because the detail page builds on this module
            from detail_view import DetailView
            self.detail = DetailView(self, on_close=self.show_overview)
            self._bind_keys()
        self._show_layer(self.detail)
        self.detail.open(column, key)

    def open_wrapped(self, month: tuple[datetime, datetime] | None = None):
        """Show the monthly summary of the given month, by default the one available today."""
        # Imported here because the summary builds on this module
        import wrapped_view
        month = month or wrapped_view.available_month()
        if month is None:
            return
        if self.wrapped is None:
            self.wrapped = wrapped_view.WrappedView(self, on_close=self.show_overview)
            self._bind_keys()
        self._show_layer(self.wrapped)
        self.wrapped.show(*month)

    def _update_wrapped_button(self):
        import wrapped_view
        if wrapped_view.available_month():
            self.wrapped_button.pack(side="right")
        else:
            self.wrapped_button.pack_forget()

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

    def _show_layer(self, layer):
        for other in (self.overview, self.detail, self.wrapped):
            if other is not None and other is not layer:
                other.pack_forget()
        layer.pack(fill="both", expand=True)

    def show_overview(self):
        self._show_layer(self.overview)

    def _cover(self, row: dict, size: int, radius: int):
        path = self.fetcher.cover(row["artist"], row["album"] or "", row["name"], self._artwork_arrived)
        return self._keep(artwork.photo(path, px(size), P.surface, radius=px(radius)))

    def _artist_photo(self, name: str, size: int):
        path = self.fetcher.artist(name, self._artwork_arrived)
        return self._keep(artwork.photo(path, px(size), P.surface, round_=True))

    def _keep(self, image):
        # Tk shows an image only while Python holds a reference to it
        if image is not None:
            self._images.append(image)
        return image

    def refresh(self):
        if self.detail is not None:
            self.detail.refresh()
        self._refresh_pending = False
        self._images = []
        self._update_wrapped_button()
        for period, button in self.period_buttons.items():
            button.configure(style="NavSelected.TButton" if period == self.period else "Nav.TButton")
        has_steps = self.period != "all"
        self.previous_button.configure(state="normal" if has_steps else "disabled")
        self.next_button.configure(state="normal" if has_steps and self.offset > 0 else "disabled")

        start, end = listening.period_range(self.period, self.offset)
        if self.period == "all":
            start = listening.first_play() or start
        self.title_label.configure(text=period_title(self.period, start, end))
        self._fill_tiles(start, end)

        tracks = listening.top_tracks(start, end, TOP_COUNT)
        artists = listening.top_artists(start, end, TOP_COUNT)
        track_change = self._rank_changes(start, end, "track_key")
        artist_change = self._rank_changes(start, end, "artist_key")
        if tracks:
            top = tracks[0]
            self.track_hero.on_click(self._opener("track_key", top["key"]))
            self.track_hero.show(top["name"], top["artist"],
                                 summary_text(plays_text(top["plays"]), minutes=top["minutes"]),
                                 self.fetcher.cover(top["artist"], top["album"] or "", top["name"],
                                                    self._artwork_arrived),
                                 track_change(top["key"], 1, long=True))
        else:
            self.track_hero.show_empty(t("stats.empty"))
        if artists:
            top = artists[0]
            self.artist_hero.on_click(self._opener("artist_key", top["key"]))
            self.artist_hero.show(top["name"], tracks_text(top["tracks"]),
                                  summary_text(plays_text(top["plays"]), minutes=top["minutes"]),
                                  self.fetcher.artist(top["name"], self._artwork_arrived),
                                  artist_change(top["key"], 1, long=True))
        else:
            self.artist_hero.show_empty(t("stats.empty"))

        size = BarList.IMAGE_SIZE
        self.top_tracks.set_rows([{
            "title": r["name"], "subtitle": r["artist"], "value": r["plays"], "value_text": number(r["plays"]),
            "tooltip": f"{r['name']}\n{r['artist']}\n" + summary_text(plays_text(r["plays"]), minutes=r["minutes"])
                       + change_tip(track_change, r["key"], rank),
            "image": self._cover(r, size, 4), "change": track_change(r["key"], rank), "on_click": self._opener("track_key", r["key"]),
        } for rank, r in enumerate(tracks[1:], start=2)])
        self.top_artists.set_rows([{
            "title": r["name"], "subtitle": tracks_text(r["tracks"]),
            "value": r["plays"], "value_text": number(r["plays"]),
            "tooltip": f"{r['name']}\n" + summary_text(
                plays_text(r["plays"]), tracks_text(r["tracks"]), minutes=r["minutes"])
                       + change_tip(artist_change, r["key"], rank),
            "image": self._artist_photo(r["name"], size), "change": artist_change(r["key"], rank),
            "on_click": self._opener("artist_key", r["key"]),
        } for rank, r in enumerate(artists[1:], start=2)])
        self._fill_discoveries(start, end)
        self._range = (start, end)
        self._fill_genres()
        self._fill_collage(start, end)
        self._fill_timeline(start, end)
        hours = listening.hours(start, end)
        self.hours.set_buckets([{
            "label": f"{hour:02d}", "value": count,
            "tooltip": f"{hour:02d}:00 – {(hour + 1) % 24:02d}:00\n{plays_text(count)}",
        } for hour, count in enumerate(hours)])

    def _rank_changes(self, start, end, column: str):
        """Returns change(key, rank) → (text, color) comparing with the whole previous period, or None."""
        if self.period == "all":
            return lambda key, rank, long=False: None
        previous_start, previous_end = listening.period_range(self.period, self.offset + 1)
        previous = listening.ranks(previous_start, previous_end, column)
        known = listening.heard_before(start, column)
        # Songs heard before recording began look new too, so new and back are only told apart
        # once the whole previous period was recorded
        first = listening.first_play()
        recorded_before = first is not None and first <= previous_start

        def change(key, rank, long=False):
            before = previous.get(key)
            if before is None:
                if not recorded_before:
                    return None
                # New means heard for the first time ever, like the discoveries; one heard before
                # but not in the previous period is back
                if key in known:
                    return t("stats.change.back_long" if long else "stats.change.back"), P.muted
                return t("stats.change.new_long" if long else "stats.change.new"), P.playable
            if before == rank:
                return (t("stats.change.same") if long else "="), P.muted
            arrow = "▲" if before > rank else "▼"
            if long:
                text = t("stats.change.moved", arrow=arrow, count=abs(before - rank), rank=before)
            else:
                text = f"{arrow}{abs(before - rank)}"
            return text, P.added if before > rank else P.removed
        return change

    def _fill_collage(self, start, end):
        if not collage.available:
            return
        # Twice as many as fit, as some are left out for sharing a cover with another
        albums = listening.top_albums(start, end, collage.COLUMNS ** 2 * 2)
        for album in albums:
            album["cover"] = self.fetcher.cover(album["artist"], album["album"], album["name"], self._artwork_arrived)
        self.collage_albums = collage.distinct(albums, collage.COLUMNS ** 2)
        if not self.collage_albums:
            self.collage_preview.configure(image="", text=t("stats.empty"))
            return
        from PIL import ImageTk
        image = collage.build(self.collage_albums, collage.COLUMNS, px(COLLAGE_PREVIEW))
        self.collage_preview.configure(image=self._keep(ImageTk.PhotoImage(image)), text="")

    def _collage_click(self, event):
        cell = px(COLLAGE_PREVIEW) / collage.COLUMNS
        column, row = int(event.x // cell), int(event.y // cell)
        index = row * collage.COLUMNS + column
        if 0 <= column < collage.COLUMNS and index < len(self.collage_albums):
            self.open_detail("artist_key", self.collage_albums[index]["artist_key"])

    def _genre_arrived(self):
        # Genres arrive one artist at a time, so redraw only this section, at most every few seconds
        if not self._genres_pending:
            self._genres_pending = True
            self.after(GENRE_REDRAW_MS, self._fill_genres)

    def _fill_genres(self):
        self._genres_pending = False
        if not self.winfo_exists() or self._range is None:
            return
        artists = listening.top_artists(*self._range, -1)
        total = sum(a["plays"] for a in artists)
        genres: dict[str, dict] = {}
        known = waiting = 0
        for artist in artists:
            facts = artist_info.request(artist["name"], artist["key"], self, self._genre_arrived,
                                        priority=artist_info.LATER)
            if facts and facts["genres"]:
                genre = genres.setdefault(facts["genres"][0], {"plays": 0, "artists": []})
                genre["plays"] += artist["plays"]
                genre["artists"].append(artist["name"])
                known += artist["plays"]
            elif artist_info.waiting(artist["key"]):
                waiting += 1
        parts = []
        if total:
            parts.append(t("stats.genres.summary", percent=t("stats.percent", value=round(100 * known / total))))
        if waiting:
            parts.append(t("stats.genres.loading", count=number(waiting)))
        self.genre_summary.configure(text="  ·  ".join(parts))
        rows = sorted(genres.items(), key=lambda item: -item[1]["plays"])[:GENRE_COUNT]
        self.genres.configure(height=px(BarList.ROW_HEIGHT * len(rows) if rows else 60))
        self.genres.set_rows([{
            "title": name[:1].upper() + name[1:],
            "subtitle": ", ".join(genre["artists"][:3]),
            "value": genre["plays"],
            "value_text": t("stats.percent", value=round(100 * genre["plays"] / total)),
            "tooltip": f"{name}\n{plays_text(genre['plays'])}\n"
                       + t("stats.genres.artists", names=", ".join(genre["artists"][:5])),
        } for name, genre in rows])

    def _fill_discoveries(self, start, end):
        # Everything is new over all time, so the section only makes sense for a week, month or year
        if self.period == "all":
            self.discoveries.pack_forget()
            self._fill_forgotten()
            return
        self.forgotten_section.pack_forget()
        self.discoveries.pack(fill="x", pady=(px(24), 0), before=self.genres_section)
        tracks = listening.new_tracks(start, end)
        artists = listening.new_artists(start, end)
        plays = listening.summary(start, end)["plays"]
        if tracks or artists:
            text = t("stats.discoveries.summary", tracks=number(len(tracks)), artists=number(len(artists)))
            if plays:
                share = round(sum(r["plays"] for r in tracks) * 100 / plays)
                text += "  ·  " + t("stats.discoveries.share", percent=t("stats.percent", value=share))
            first = listening.first_play()
            if first and first >= start:
                text += "\n" + t("stats.discoveries.first_period")
        else:
            text = t("stats.discoveries.none")
        self.discovery_summary.configure(text=text)

        size = BarList.IMAGE_SIZE
        self.new_tracks.set_rows([{
            "title": r["name"], "subtitle": r["artist"], "value": r["plays"], "value_text": number(r["plays"]),
            "tooltip": f"{r['name']}\n{r['artist']}\n" + summary_text(plays_text(r["plays"]), minutes=r["minutes"])
                       + "\n" + t("stats.discoveries.first_heard", date=format_date(r["first_played"])),
            "image": self._cover(r, size, 4), "on_click": self._opener("track_key", r["key"]),
        } for r in tracks[:DISCOVERY_COUNT]])
        self.new_artists.set_rows([{
            "title": r["name"], "subtitle": tracks_text(r["tracks"]), "value": r["plays"],
            "value_text": number(r["plays"]),
            "tooltip": f"{r['name']}\n" + summary_text(plays_text(r["plays"]), tracks_text(r["tracks"]),
                                                       minutes=r["minutes"])
                       + "\n" + t("stats.discoveries.first_heard", date=format_date(r["first_played"])),
            "image": self._artist_photo(r["name"], size), "on_click": self._opener("artist_key", r["key"]),
        } for r in artists[:DISCOVERY_COUNT]])

    def _fill_forgotten(self):
        self.forgotten_section.pack(fill="x", pady=(px(24), 0), before=self.genres_section)
        today = datetime.now().astimezone()
        rows = []
        for r in listening.forgotten(FORGOTTEN_DAYS, FORGOTTEN_MIN_PLAYS, TOP_COUNT):
            days = (today - listening.from_utc(r["last_played"])).days
            rows.append({
                "title": r["name"], "subtitle": r["artist"], "value": r["plays"], "value_text": number(r["plays"]),
                "tooltip": f"{r['name']}\n{r['artist']}\n"
                           + summary_text(plays_text(r["plays"]), minutes=r["minutes"]) + "\n"
                           + t("stats.forgotten.last", date=format_date(r["last_played"]), days=number(days)),
                "image": self._cover(r, BarList.IMAGE_SIZE, 4), "on_click": self._opener("track_key", r["key"]),
            })
        # Only as tall as needed: the list is often short or empty
        self.forgotten.configure(height=px(BarList.ROW_HEIGHT * len(rows) if rows else 60))
        self.forgotten.set_rows(rows)

    def _fill_tiles(self, start, end):
        current = listening.summary(start, end)
        previous = None
        if self.period != "all":
            previous_start, previous_end = listening.period_range(self.period, self.offset + 1)
            if self.offset == 0:
                # The current period is still running, so compare with the same stretch of the previous one
                previous_end = min(previous_end, previous_start + (datetime.now().astimezone() - start))
            previous = listening.summary(previous_start, previous_end)
        for name, key, text in (("plays", "plays", number), ("time", "minutes", duration_text),
                                ("tracks", "tracks", number), ("artists", "artists", number)):
            value_label, delta_label = self.tiles[name]
            count_up(value_label, current[key], text)
            delta = ""
            if previous and previous[key]:
                change = round((current[key] - previous[key]) * 100 / previous[key])
                arrow = "▲" if change > 0 else "▼" if change < 0 else "="
                delta = f"{arrow} {t('stats.percent', value=abs(change))}  {t(f'stats.vs.{self.period}')}"
            delta_label.configure(text=delta)

    def _fill_timeline(self, start, end):
        if self.period in ("week", "month"):
            counts = listening.timeline(start, end, "day")
            days = [start + timedelta(days=i) for i in range((end - start).days)]
            buckets = [{
                "label": t("stats.weekdays").split(",")[day.weekday()] if self.period == "week" else str(day.day),
                "value": counts.get(day.strftime("%Y-%m-%d"), 0),
                "tooltip": f"{day.day} {month_name(day.month)}\n"
                           f"{plays_text(counts.get(day.strftime('%Y-%m-%d'), 0))}",
            } for day in days]
            title = t("stats.per_day")
        else:
            counts = listening.timeline(start, end, "month")
            months = []
            year, month = start.year, start.month
            last = end - timedelta(days=1)
            while (year, month) <= (last.year, last.month):
                months.append((year, month))
                year, month = (year + 1, 1) if month == 12 else (year, month + 1)
            if len(months) > 36:
                totals: dict[int, int] = {}
                for (year, month) in months:
                    totals[year] = totals.get(year, 0) + counts.get(f"{year}-{month:02d}", 0)
                buckets = [{"label": str(year), "value": value, "tooltip": f"{year}\n{plays_text(value)}"}
                           for year, value in totals.items()]
                title = t("stats.per_year")
            else:
                buckets = []
                for year, month in months:
                    value = counts.get(f"{year}-{month:02d}", 0)
                    label = month_name(month, True)
                    if self.period == "all":
                        label += f" {year % 100:02d}"
                    buckets.append({"label": label, "value": value,
                                    "tooltip": f"{month_name(month)} {year}\n{plays_text(value)}"})
                title = t("stats.per_month")
        self.timeline_card.title.configure(text=title)
        self.timeline.set_buckets(buckets)
