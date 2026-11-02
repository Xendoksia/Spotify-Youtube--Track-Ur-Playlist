"""
A month in review, shown slide by slide in the statistics tab: time listened, the song and artist of the
month, the top five of each, discoveries, the busiest day and hour, genres and a closing summary.

It is meant to open by itself on the first of each month for the month before (AUTO_OPEN); until that is
switched on it opens from the "Monthly summary" button, for the last month with plays.
"""

from __future__ import annotations

from datetime import datetime
from tkinter import ttk

import artist_info
import artwork
import listening
import tracker
from charts import Animation, BarList, ColumnChart, count_up
from i18n import number, t
from stats_view import duration_text, month_name, period_title, plays_text
from theme import P, px

# Open the summary of the previous month when the app is first opened in a new month
AUTO_OPEN = False
TOP = 5
IMAGE = 200
LIST_WIDTH = 620
BIG_FONT = ("Segoe UI Semibold", 44)
NAME_FONT = ("Segoe UI Semibold", 24)
BODY_FONT = ("Segoe UI", 13)
CAPTION_FONT = ("Segoe UI Semibold", 11)
# A new slide slides in from this far (a share of the width) and its parts appear one after another
SLIDE_SHIFT = 0.35
REVEAL_DELAY_MS = 120
REVEAL_STEP_MS = 130


def month_to_show() -> tuple[datetime, datetime]:
    """The previous month, or this one while the previous has no plays (recording started this month)."""
    previous = listening.period_range("month", 1)
    if listening.summary(*previous)["plays"]:
        return previous
    return listening.period_range("month")


def auto_open_due() -> tuple[datetime, datetime] | None:
    """The previous month, when its summary has not been shown yet and it has plays (needs AUTO_OPEN)."""
    if not AUTO_OPEN:
        return None
    start, end = listening.period_range("month", 1)
    if tracker.load_config().get("WRAPPED_SHOWN") == start.strftime("%Y-%m") or not listening.summary(start, end)["plays"]:
        return None
    return start, end


def mark_shown(start: datetime) -> None:
    config = tracker.load_config()
    config["WRAPPED_SHOWN"] = start.strftime("%Y-%m")
    tracker.save_config(config)


class WrappedView(ttk.Frame):
    def __init__(self, parent, on_close):
        super().__init__(parent, style="Card.TFrame")
        self.on_close = on_close
        self.fetcher = artwork.Fetcher(self)
        self._images = []
        self.slides = []
        self.index = 0
        self.data: dict = {}

        bar = ttk.Frame(self, style="Card.TFrame")
        bar.pack(fill="x", padx=px(16), pady=(px(16), 0))
        self.back_button = ttk.Button(bar, text="‹", width=3, command=lambda: self.step(-1))
        self.back_button.pack(side="left")
        self.next_button = ttk.Button(bar, text="›", width=3, command=lambda: self.step(1))
        self.next_button.pack(side="left", padx=(px(4), 0))
        self.title_label = ttk.Label(bar, style="Period.TLabel")
        self.title_label.pack(side="left", padx=px(12))
        ttk.Button(bar, text="✕", width=3, command=self.close).pack(side="right")
        self.dots = ttk.Label(bar, style="CardMuted.TLabel")
        self.dots.pack(side="right", padx=px(16))
        self.stage = ttk.Frame(self, style="Card.TFrame")
        self.stage.pack(fill="both", expand=True)
        self.slide = None
        self._leaving = None
        self._slide_animation = None
        # Animations of a slide's parts, started when the part appears
        self._on_reveal: dict = {}

    # Data

    def show(self, start: datetime, end: datetime):
        self.data = self._collect(start, end)
        self.title_label.configure(text=t("wrapped.title", month=period_title("month", start, end)))
        self.slides = [slide for slide, wanted in (
            (self._intro, True),
            (self._top_track, bool(self.data["tracks"])),
            (self._top_artist, bool(self.data["artists"])),
            (self._top_tracks, len(self.data["tracks"]) > 1),
            (self._top_artists, len(self.data["artists"]) > 1),
            (self._discoveries, bool(self.data["new_tracks"])),
            (self._rhythm, bool(self.data["summary"]["plays"])),
            (self._genres, bool(self.data["genres"])),
            (self._closing, bool(self.data["summary"]["plays"])),
        ) if wanted]
        self.index = 0
        self._render()

    def _collect(self, start, end) -> dict:
        artists_all = listening.top_artists(start, end, -1)
        total = sum(a["plays"] for a in artists_all)
        genres: dict[str, int] = {}
        for artist in artists_all:
            facts = artist_info.cached(artist["key"])
            if facts and facts["genres"]:
                genres[facts["genres"][0]] = genres.get(facts["genres"][0], 0) + artist["plays"]
        days = listening.timeline(start, end, "day")
        busiest = max(days.items(), key=lambda item: item[1]) if days else None
        hours = listening.hours(start, end)
        first = listening.first_play()
        return {
            "start": start, "end": end,
            "summary": listening.summary(start, end),
            "tracks": listening.top_tracks(start, end, TOP),
            "artists": artists_all[:TOP],
            "new_tracks": listening.new_tracks(start, end),
            "new_artists": listening.new_artists(start, end),
            # Everything counts as new in the month recording began
            "first_month": first is not None and first >= start,
            "busiest": busiest, "days_listened": len(days), "hours": hours,
            "genres": sorted(((name, plays * 100 / total) for name, plays in genres.items()),
                             key=lambda item: -item[1])[:3] if total else [],
        }

    # Navigation

    def step(self, direction: int):
        index = self.index + direction
        if 0 <= index < len(self.slides):
            self.index = index
            self._render(direction)

    def close(self):
        self.on_close()

    def _render(self, direction: int = 0, animate: bool = True):
        """Build the current slide; with animate it slides in from the side of direction and its parts
        appear one by one, without it (a picture arrived) it is simply redrawn."""
        if self._slide_animation is not None:
            self._slide_animation.stop()
        if self._leaving is not None:
            self._leaving.destroy()
        self._leaving, old = None, self.slide
        self._images = []
        self._on_reveal = {}
        self.slide = ttk.Frame(self.stage, style="Card.TFrame")
        self.slides[self.index](self.slide)
        self.dots.configure(text=" ".join("●" if i == self.index else "○" for i in range(len(self.slides))))
        self.back_button.configure(state="normal" if self.index > 0 else "disabled")
        self.next_button.configure(state="normal" if self.index < len(self.slides) - 1 else "disabled")

        if old is not None and (not animate or not direction):
            old.destroy()
        if not animate:
            self.slide.place(relx=0.5, rely=0.5, anchor="center")
            for action in self._on_reveal.values():
                action()
            self._on_reveal = {}
            return

        parts = []
        for widget in self.slide.pack_slaves():
            info = widget.pack_info()
            info["in_"] = info.pop("in")
            parts.append((widget, info))
            widget.pack_forget()
        self.slide.place(relx=0.5 + SLIDE_SHIFT * direction, rely=0.5, anchor="center")
        if direction:
            self._leaving = old

            def move(progress):
                self.slide.place_configure(relx=0.5 + SLIDE_SHIFT * direction * (1 - progress))
                if old is not None and old.winfo_exists():
                    old.place_configure(relx=0.5 - SLIDE_SHIFT * direction * progress)
                    if progress >= 1:
                        old.destroy()
            self._slide_animation = Animation(self, move)
            self._slide_animation.start()
        slide = self.slide
        for index, (widget, info) in enumerate(parts):
            self.after(REVEAL_DELAY_MS + index * REVEAL_STEP_MS,
                       lambda widget=widget, info=info: self._reveal(slide, widget, info))

    def _reveal(self, slide, widget, info):
        if slide is not self.slide or not widget.winfo_exists():
            return
        widget.pack(**info)
        action = self._on_reveal.pop(widget, None)
        if action:
            action()

    # Building blocks

    def _caption(self, parent, key: str, **values):
        ttk.Label(parent, text=t(key, **values).upper(), style="Card.TLabel", foreground=P.chart,
                  font=CAPTION_FONT).pack(pady=(0, px(12)))

    def _big(self, parent, value: int, text, pady=0):
        label = ttk.Label(parent, text=text(0), style="Card.TLabel", foreground=P.chart, font=BIG_FONT)
        label.pack(pady=pady)
        self._on_reveal[label] = lambda: count_up(label, value, text)

    def _heading(self, parent, text: str):
        ttk.Label(parent, text=text, style="Card.TLabel", font=NAME_FONT, justify="center",
                  wraplength=px(LIST_WIDTH)).pack()

    def _body(self, parent, text: str, muted: bool = True, pady=(px(6), 0)):
        ttk.Label(parent, text=text, style="CardMuted.TLabel" if muted else "Card.TLabel", font=BODY_FONT,
                  justify="center", wraplength=px(LIST_WIDTH)).pack(pady=pady)

    def _picture(self, parent, make):
        """make(size) gives the picture at a size in pixels; it grows into place when it appears."""
        side = px(IMAGE)
        if make(side) is None:
            return
        box = ttk.Frame(parent, style="Card.TFrame", width=side, height=side)
        box.pack_propagate(False)
        box.pack(pady=(0, px(16)))
        label = ttk.Label(box, style="Card.TLabel")
        label.place(relx=0.5, rely=0.5, anchor="center")

        def grow(progress):
            if label.winfo_exists():
                # Tk shows an image only while Python holds a reference to it
                label.image = make(max(1, round(side * (0.5 + 0.5 * progress))))
                label.configure(image=label.image)
        self._on_reveal[box] = lambda: Animation(label, grow).start()

    def _refresh_later(self):
        # A picture finished downloading: draw the slide again with it
        if self.winfo_exists() and self.slides:
            self.after(300, lambda: self._render(animate=False))

    def _cover(self, row: dict, size: int, radius: int):
        path = self.fetcher.cover(row["artist"], row["album"] or "", row["name"], self._refresh_later)
        image = artwork.photo(path, px(size), P.surface, radius=px(radius))
        if image is not None:
            self._images.append(image)
        return image

    def _artist_photo(self, name: str, size: int):
        image = artwork.photo(self.fetcher.artist(name, self._refresh_later), px(size), P.surface, round_=True)
        if image is not None:
            self._images.append(image)
        return image

    def _cover_maker(self, row: dict, radius: int):
        path = self.fetcher.cover(row["artist"], row["album"] or "", row["name"], self._refresh_later)
        return lambda size: artwork.photo(path, size, P.surface, radius=px(radius))

    def _photo_maker(self, name: str):
        path = self.fetcher.artist(name, self._refresh_later)
        return lambda size: artwork.photo(path, size, P.surface, round_=True)

    def _list(self, parent, rows: list[dict], round_images: bool = False):
        chart = BarList(parent, "", len(rows), round_images=round_images)
        chart.configure(width=px(LIST_WIDTH))
        chart.pack()
        # The bars grow from zero once the list appears
        self._on_reveal[chart] = lambda: chart.set_rows(rows)

    # Slides

    def _intro(self, slide):
        summary = self.data["summary"]
        self._caption(slide, "wrapped.intro.caption", month=month_name(self.data["start"].month))
        if summary["minutes"]:
            self._big(slide, summary["minutes"], lambda m: t("wrapped.minutes", minutes=number(m)))
            self._body(slide, t("wrapped.intro.listened"), muted=False)
        else:
            self._big(slide, summary["plays"], lambda p: plays_text(p))
        self._body(slide, t("wrapped.intro.detail", plays=plays_text(summary["plays"]),
                            tracks=number(summary["tracks"]), artists=number(summary["artists"])), pady=(px(16), 0))

    def _top_track(self, slide):
        track = self.data["tracks"][0]
        self._caption(slide, "wrapped.track.caption")
        self._picture(slide, self._cover_maker(track, 12))
        self._heading(slide, track["name"])
        self._body(slide, track["artist"])
        self._body(slide, t("wrapped.times", count=number(track["plays"])), muted=False, pady=(px(16), 0))

    def _top_artist(self, slide):
        artist = self.data["artists"][0]
        self._caption(slide, "wrapped.artist.caption")
        self._picture(slide, self._photo_maker(artist["name"]))
        self._heading(slide, artist["name"])
        detail = plays_text(artist["plays"])
        if artist["minutes"]:
            detail += f"  ·  {duration_text(artist['minutes'])}"
        self._body(slide, detail, muted=False)
        facts = artist_info.cached(artist["key"])
        if facts:
            self._body(slide, artist_info.describe(facts), pady=(px(16), 0))

    def _top_tracks(self, slide):
        self._caption(slide, "wrapped.tracks.caption")
        self._list(slide, [{
            "title": r["name"], "subtitle": r["artist"], "value": r["plays"], "value_text": number(r["plays"]),
            "tooltip": f"{r['name']}\n{plays_text(r['plays'])}", "image": self._cover(r, BarList.IMAGE_SIZE, 4),
        } for r in self.data["tracks"]])

    def _top_artists(self, slide):
        self._caption(slide, "wrapped.artists.caption")
        self._list(slide, [{
            "title": r["name"], "subtitle": "", "value": r["plays"], "value_text": number(r["plays"]),
            "tooltip": f"{r['name']}\n{plays_text(r['plays'])}",
            "image": self._artist_photo(r["name"], BarList.IMAGE_SIZE),
        } for r in self.data["artists"]], round_images=True)

    def _discoveries(self, slide):
        new_tracks, new_artists = self.data["new_tracks"], self.data["new_artists"]
        self._caption(slide, "wrapped.discoveries.caption")
        self._big(slide, len(new_tracks), lambda n: t("wrapped.new_tracks", count=number(n)))
        self._body(slide, t("wrapped.new_artists", count=number(len(new_artists))), muted=False)
        if new_artists:
            self._body(slide, t("wrapped.top_new_artist", name=new_artists[0]["name"]), pady=(px(16), 0))
        if self.data["first_month"]:
            self._body(slide, t("stats.discoveries.first_period"), pady=(px(16), 0))

    def _rhythm(self, slide):
        self._caption(slide, "wrapped.rhythm.caption")
        day, plays = self.data["busiest"]
        date = datetime.strptime(day, "%Y-%m-%d")
        weekday = t("stats.weekdays").split(",")[date.weekday()]
        self._body(slide, t("wrapped.busiest", day=f"{date.day} {month_name(date.month)}, {weekday}",
                            plays=plays_text(plays)), muted=False, pady=0)
        hours = self.data["hours"]
        peak = max(range(24), key=lambda hour: hours[hour])
        self._heading(slide, f"{peak:02d}:00 – {(peak + 1) % 24:02d}:00")
        self._body(slide, t("wrapped.peak_hour"), pady=(0, px(16)))
        chart = ColumnChart(slide, 140)
        chart.configure(width=px(LIST_WIDTH))
        chart.pack()
        buckets = [{"label": f"{hour:02d}", "value": count, "tooltip": f"{hour:02d}:00\n{plays_text(count)}"}
                   for hour, count in enumerate(hours)]
        self._on_reveal[chart] = lambda: chart.set_buckets(buckets)
        days = (min(self.data["end"], datetime.now().astimezone()) - self.data["start"]).days + 1
        self._body(slide, t("wrapped.days_listened", active=number(self.data["days_listened"]),
                            days=number(max(days, self.data["days_listened"]))), pady=(px(16), 0))

    def _genres(self, slide):
        self._caption(slide, "wrapped.genres.caption")
        for index, (name, share) in enumerate(self.data["genres"]):
            name = name[:1].upper() + name[1:]

            def text(value, name=name):
                return f"{name}  {t('stats.percent', value=value)}"
            label = ttk.Label(slide, text=text(0), style="Card.TLabel" if index == 0 else "CardMuted.TLabel",
                              foreground=P.chart if index == 0 else P.muted,
                              font=BIG_FONT if index == 0 else NAME_FONT)
            label.pack(pady=(0, px(8)))
            self._on_reveal[label] = lambda label=label, share=share, text=text: count_up(label, round(share), text)

    def _closing(self, slide):
        data, summary = self.data, self.data["summary"]
        self._caption(slide, "wrapped.closing.caption", month=period_title("month", data["start"], data["end"]))
        grid = ttk.Frame(slide, style="Card.TFrame")
        grid.pack()
        tiles = [(t("stats.tile.time"), duration_text(summary["minutes"]) if summary["minutes"] else "—"),
                 (t("stats.tile.plays"), number(summary["plays"])),
                 (t("stats.tile.tracks"), number(summary["tracks"])),
                 (t("stats.tile.artists"), number(summary["artists"]))]
        if data["tracks"]:
            tiles.append((t("wrapped.track.caption"), data["tracks"][0]["name"]))
        if data["artists"]:
            tiles.append((t("wrapped.artist.caption"), data["artists"][0]["name"]))
        if data["genres"]:
            name = data["genres"][0][0]
            tiles.append((t("wrapped.genre"), name[:1].upper() + name[1:]))
        if data["new_artists"] and not data["first_month"]:
            tiles.append((t("stats.new_artists"), number(len(data["new_artists"]))))
        built = []
        for index, (caption, value) in enumerate(tiles):
            tile = ttk.Frame(grid, padding=(px(16), px(12)), style="Tile.TFrame", width=px(300))
            ttk.Label(tile, text=caption, style="CardMuted.TLabel").pack(anchor="w")
            ttk.Label(tile, text=value, style="TileValue.TLabel", wraplength=px(270)).pack(anchor="w")
            built.append(tile)
        grid.columnconfigure((0, 1), uniform="tile", minsize=px(300))

        def place_tile(index):
            if built[index].winfo_exists():
                built[index].grid(row=index // 2, column=index % 2, sticky="nsew", padx=px(6), pady=px(6))

        # The tiles come in one after another, like the parts of every slide
        self._on_reveal[grid] = lambda: [grid.after(index * REVEAL_STEP_MS // 2, place_tile, index)
                                         for index in range(len(built))]
