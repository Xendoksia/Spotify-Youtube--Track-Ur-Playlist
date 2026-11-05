"""
Takes the screenshots of the README: opens the app with your own data, shows its pages one by one and saves
each as docs/<name>.png. Windows only. Close the app first, or a second recorder would count songs twice.

    python docs/screenshots.py [en|tr]

The account page is left out, as it shows your e-mail address.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import queue
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import ImageGrab  # noqa: E402

from playlist_tracker.core import account, config, i18n  # noqa: E402
from playlist_tracker.music import listening as plays, nowplaying  # noqa: E402
from playlist_tracker.ui import main_window, theme  # noqa: E402

DOCS = Path(__file__).resolve().parent
DWMWA_EXTENDED_FRAME_BOUNDS = 9
# Covers and photos are fetched in the background
SETTLE_SECONDS = 4


class NoTray:
    hint_shown = True

    def set_title(self, title):
        pass

    def notify(self, message):
        pass


def wait(app, seconds=SETTLE_SECONDS):
    end = time.time() + seconds
    while time.time() < end:
        app.update()
        time.sleep(0.05)


def grab(app, name: str):
    """The window as seen on screen with its title bar, without the invisible resize borders around it."""
    app.lift()
    app.attributes("-topmost", True)
    wait(app, 0.5)
    hwnd = ctypes.windll.user32.GetParent(app.winfo_id())
    rect = ctypes.wintypes.RECT()
    ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect),
                                               ctypes.sizeof(rect))
    ImageGrab.grab((rect.left, rect.top, rect.right, rect.bottom)).save(DOCS / f"{name}.png", optimize=True)
    app.attributes("-topmost", False)
    print("saved", name)


def most_played_artist() -> str | None:
    """The artist played most this week, whose page is shown."""
    start, end = plays.period_range("week")
    with plays.open_db() as db:
        row = db.execute("SELECT artist_key FROM listens WHERE played_at >= ? AND played_at < ? GROUP BY artist_key "
                         "ORDER BY COUNT(*) DESC LIMIT 1", (plays.to_utc(start), plays.to_utc(end))).fetchone()
    return row[0] if row else None


def open_app(theme_name: str, language: str) -> main_window.App:
    # Settings as saved, with the theme and language asked for
    load = config.load_config
    main_window.load_config = lambda: {**load(), "THEME": theme_name, "LANGUAGE": language}
    account.decided = True
    # Recording runs as in the app, so the recent plays and the mini player show what Spotify plays
    tracker = nowplaying.LocalTracker()
    tracker.start()
    app = main_window.App(tracker, queue.Queue(), NoTray())
    app.bind("<Destroy>", lambda e: e.widget is app and tracker.stop())
    wait(app)
    return app


def main():
    theme.make_dpi_aware()
    language = sys.argv[1] if len(sys.argv) > 1 else "en"
    i18n.set_language(language)

    app = open_app("dark", language)
    listening = app.listening
    listening.tabs.select(listening.stats)
    wait(app)
    grab(app, "statistics")

    top_artist = most_played_artist()
    if top_artist:
        listening.stats.open_detail("artist_key", top_artist)
        wait(app)
        grab(app, "artist")
        listening.stats.show_overview()

    listening.tabs.select(1)
    wait(app)
    grab(app, "recent")

    app.show_section("playlists")
    app.tabs.select(0)
    wait(app, 1)
    grab(app, "playlists")

    app.show_section("help")
    wait(app, 1)
    grab(app, "help")

    app.show_login()
    wait(app, 1)
    grab(app, "login")
    app.destroy()

    app = open_app("light", language)
    app.listening.tabs.select(app.listening.stats)
    wait(app)
    grab(app, "statistics-light")
    app.destroy()


if __name__ == "__main__":
    main()
