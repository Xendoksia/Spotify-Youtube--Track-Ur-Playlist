"""
A month in review, shown slide by slide in the statistics tab: time listened, the song and artist of the
month, the top five of each, discoveries, the busiest day and hour, genres and a closing summary.

It is there only on the first days of a month (SHOW_DAYS), for the month before: it opens by itself the first
time the window is shown on one of those days (AUTO_OPEN), and from the "Monthly summary" button.
"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import ttk

import artist_info
import artwork
import listening
import tracker
from charts import Animation, BarList, ColumnChart, count_up, mix
from i18n import number, t
from stats_view import duration_text, month_name, period_title, plays_text
from theme import P, icon, px

try:
    from PIL import Image, ImageTk
except ImportError:  # artwork.picture() then gives no pictures, so these are not needed
    pass

# Days of the month on which the summary of the previous month can be seen
SHOW_DAYS = (1, 2)
# Open it by itself the first time the window is shown on one of those days
AUTO_OPEN = True
TOP = 5
IMAGE = 200
LIST_WIDTH = 620
BIG_FONT = ("Segoe UI Semibold", 44)
NAME_FONT = ("Segoe UI Semibold", 24)
BODY_FONT = ("Segoe UI", 13)
CAPTION_FONT = ("Segoe UI Semibold", 11)
TILE_FONT = ("Segoe UI Semibold", 20)
# The old slide fades out under a cover, then the parts of the new one fade in one after another
FADE_OUT_MS = 180
FADE_IN_MS = 380
REVEAL_DELAY_MS = 60
REVEAL_STEP_MS = 110
PICTURE_FRAMES = 10


def available_month() -> tuple[datetime, datetime] | None:
    """The previous month on the first days of a month, if it has plays; otherwise there is no summary."""
    if datetime.now().day not in SHOW_DAYS:
        return None
    previous = listening.period_range("month", 1)
    return previous if listening.summary(*previous)["plays"] else None


def month_to_show() -> tuple[datetime, datetime]:
    """For looking at the summary on any day (app.py --summary): the previous month, or this one while the
    previous has no plays."""
    previous = listening.period_range("month", 1)
    return previous if listening.summary(*previous)["plays"] else listening.period_range("month")


def auto_open_due() -> tuple[datetime, datetime] | None:
    """The month to open the summary of by itself, once (needs AUTO_OPEN)."""
    month = available_month() if AUTO_OPEN else None
    if month is None or tracker.load_config().get("WRAPPED_SHOWN") == month[0].strftime("%Y-%m"):
        return None
    return month


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
        self.slide = None
        self._changing = False
        # What each part of the slide does when it appears: action(instant)
        self._on_reveal: dict = {}

        bar = ttk.Frame(self, style="Card.TFrame")
        bar.pack(fill="x", padx=px(16), pady=(px(16), 0))
        self.back_button = ttk.Button(bar, text=icon("back"), style="Icon.TButton", command=lambda: self.step(-1))
        self.back_button.pack(side="left")
        self.next_button = ttk.Button(bar, text=icon("forward"), style="Icon.TButton", command=lambda: self.step(1))
        self.next_button.pack(side="left", padx=(px(4), 0))
        self.title_label = ttk.Label(bar, style="Period.TLabel")
        self.title_label.pack(side="left", padx=px(12))
        ttk.Button(bar, text=icon("close"), style="Icon.TButton", command=self.close).pack(side="right")
        self.dots = ttk.Label(bar, style="CardMuted.TLabel")
        self.dots.pack(side="right", padx=px(16))
        self.stage = ttk.Frame(self, style="Card.TFrame")
        self.stage.pack(fill="both", expand=True)

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

    # Navigation and transitions

    def step(self, direction: int):
        index = self.index + direction
        if 0 <= index < len(self.slides) and not self._changing:
            self.index = index
            self._fade_out(self._render)

    def close(self):
        self.on_close()

    def _fade_out(self, then):
        """Cover the stage with a window of its background color going from clear to solid, then call then.

        Only the cover's transparency changes, which Windows draws smoothly; moving the widgets themselves
        stutters."""
        try:
            cover = tk.Toplevel(self)
            cover.withdraw()
            cover.overrideredirect(True)
            cover.transient(self.winfo_toplevel())
            cover.configure(background=P.surface)
            cover.attributes("-alpha", 0.0)
            cover.geometry(f"{self.stage.winfo_width()}x{self.stage.winfo_height()}"
                           f"+{self.stage.winfo_rootx()}+{self.stage.winfo_rooty()}")
            cover.deiconify()
        except tk.TclError:
            then()
            return
        self._changing = True

        def fade(progress):
            if not cover.winfo_exists():
                return
            cover.attributes("-alpha", progress)
            if progress >= 1:
                then()
                # The new slide starts out in the background color, so lifting the cover shows no change
                self.update_idletasks()
                cover.destroy()
                self.winfo_toplevel().focus_force()
                self._changing = False
        Animation(cover, fade, FADE_OUT_MS).start()

    def _render(self, animate: bool = True):
        """Build the current slide with its parts in the background color, then bring them in one by one;
        without animate (a picture arrived) everything shows at once."""
        if self.slide is not None:
            self.slide.destroy()
        self._images = []
        self._on_reveal = {}
        self.slide = ttk.Frame(self.stage, style="Card.TFrame")
        self.slides[self.index](self.slide)
        self.slide.place(relx=0.5, rely=0.5, anchor="center")
        self.dots.configure(text=" ".join("●" if i == self.index else "○" for i in range(len(self.slides))))
        self.back_button.configure(state="normal" if self.index > 0 else "disabled")
        self.next_button.configure(state="normal" if self.index < len(self.slides) - 1 else "disabled")
        slide = self.slide
        for order, part in enumerate(slide.pack_slaves()):
            actions = self._on_reveal.get(part, [])
            if not animate:
                for action in actions:
                    action(True)
            elif actions:
                self.after(REVEAL_DELAY_MS + order * REVEAL_STEP_MS,
                           lambda actions=actions: slide is self.slide and [action(False) for action in actions])

    # Building blocks

    def _when_shown(self, part, action):
        self._on_reveal.setdefault(part, []).append(action)

    def _fade_in(self, part, widget, color: str, option: str = "foreground"):
        """Start widget's color option at the background and bring it to color when part appears."""
        widget.configure(**{option: P.surface})

        def show(instant):
            if instant:
                widget.configure(**{option: color})
                return
            Animation(widget, lambda progress: widget.winfo_exists()
                      and widget.configure(**{option: mix(P.surface, color, progress)}), FADE_IN_MS).start()
        self._when_shown(part, show)

    def _label(self, parent, text: str, color: str, font, **pack):
        label = ttk.Label(parent, text=text, style="Card.TLabel", font=font, justify="center",
                          wraplength=px(LIST_WIDTH))
        label.pack(**pack)
        self._fade_in(label, label, color)
        return label

    def _caption(self, parent, key: str, **values):
        self._label(parent, t(key, **values).upper(), P.chart, CAPTION_FONT, pady=(0, px(12)))

    def _big(self, parent, value: int, text, pady=0, color=None):
        label = self._label(parent, text(0), color or P.chart, BIG_FONT, pady=pady)

        def count(instant):
            if instant:
                label._count_value = value
                label.configure(text=text(value))
            else:
                count_up(label, value, text)
        self._when_shown(label, count)
        return label

    def _heading(self, parent, text: str):
        self._label(parent, text, P.text, NAME_FONT)

    def _body(self, parent, text: str, muted: bool = True, pady=(px(6), 0)):
        self._label(parent, text, P.muted if muted else P.text, BODY_FONT, pady=pady)

    def _picture(self, parent, path, **shape):
        """The picture fades in from the background through a few frames prepared in advance."""
        side = px(IMAGE)
        final = artwork.picture(path, side, P.surface, **shape)
        if final is None:
            return
        background = Image.new("RGB", final.size, P.surface)
        frames = [ImageTk.PhotoImage(Image.blend(background, final, (i + 1) / PICTURE_FRAMES))
                  for i in range(PICTURE_FRAMES)]
        self._images.extend(frames)
        blank = ImageTk.PhotoImage(background)
        self._images.append(blank)
        label = ttk.Label(parent, image=blank, style="Card.TLabel")
        label.pack(pady=(0, px(16)))

        def show(instant):
            if instant:
                label.configure(image=frames[-1])
                return
            Animation(label, lambda progress: label.winfo_exists() and label.configure(
                image=frames[min(PICTURE_FRAMES - 1, int(progress * PICTURE_FRAMES))]), FADE_IN_MS).start()
        self._when_shown(label, show)

    def _refresh_later(self):
        # A picture finished downloading: draw the slide again with it
        if self.winfo_exists() and self.slides and not self._changing:
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

    def _list(self, parent, rows: list[dict], round_images: bool = False):
        chart = BarList(parent, "", len(rows), round_images=round_images)
        chart.configure(width=px(LIST_WIDTH))
        chart.pack()
        # The bars grow from zero once the list appears
        self._when_shown(chart, lambda instant: chart.set_rows(rows))

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
        path = self.fetcher.cover(track["artist"], track["album"] or "", track["name"], self._refresh_later)
        self._picture(slide, path, radius=px(12))
        self._heading(slide, track["name"])
        self._body(slide, track["artist"])
        self._body(slide, t("wrapped.times", count=number(track["plays"])), muted=False, pady=(px(16), 0))

    def _top_artist(self, slide):
        artist = self.data["artists"][0]
        self._caption(slide, "wrapped.artist.caption")
        self._picture(slide, self.fetcher.artist(artist["name"], self._refresh_later), round_=True)
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
        self._when_shown(chart, lambda instant: chart.set_buckets(buckets))
        days = (min(self.data["end"], datetime.now().astimezone()) - self.data["start"]).days + 1
        self._body(slide, t("wrapped.days_listened", active=number(self.data["days_listened"]),
                            days=number(max(days, self.data["days_listened"]))), pady=(px(16), 0))

    def _genres(self, slide):
        self._caption(slide, "wrapped.genres.caption")
        for index, (name, share) in enumerate(self.data["genres"]):
            name = name[:1].upper() + name[1:]

            def text(value, name=name):
                return f"{name}  {t('stats.percent', value=value)}"
            if index == 0:
                self._big(slide, round(share), text, pady=(0, px(8)))
            else:
                label = self._label(slide, text(0), P.muted, NAME_FONT, pady=(0, px(8)))
                self._when_shown(label, lambda instant, label=label, share=share, text=text:
                                 count_up(label, round(share), text))

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
        grid.columnconfigure((0, 1), uniform="tile", minsize=px(300))
        for index, (caption, value) in enumerate(tiles):
            # Plain Tk frames, as their border color can fade in like the text
            tile = tk.Frame(grid, background=P.surface, highlightthickness=1, highlightbackground=P.surface,
                            padx=px(16), pady=px(12))
            tile.grid(row=index // 2, column=index % 2, sticky="nsew", padx=px(6), pady=px(6))
            caption_label = ttk.Label(tile, text=caption, style="Card.TLabel")
            caption_label.pack(anchor="w")
            value_label = ttk.Label(tile, text=value, style="Card.TLabel", font=TILE_FONT, wraplength=px(270))
            value_label.pack(anchor="w")
            # The tiles come in one after another
            delay = index * REVEAL_STEP_MS // 2
            for widget, option, color in ((tile, "highlightbackground", P.border),
                                          (caption_label, "foreground", P.muted), (value_label, "foreground", P.text)):
                widget.configure(**{option: P.surface})
                self._when_shown(grid, lambda instant, widget=widget, option=option, color=color, delay=delay:
                                 widget.configure(**{option: color}) if instant else grid.after(
                                     delay, lambda: widget.winfo_exists() and Animation(
                                         widget, lambda progress: widget.winfo_exists() and widget.configure(
                                             **{option: mix(P.surface, color, progress)}), FADE_IN_MS).start()))
