"""
Running in the background: one recording copy at a time, the app's icon and starting with Windows.

Only one copy may record, otherwise two listening trackers would record the same song twice. The desktop window
(desktop/) keeps a single window itself; its backend takes this lock, and a second backend only serves data.
"""

from __future__ import annotations

import os
import queue
import socket
import sys
import threading

from playlist_tracker.core.config import BASE_DIR

APP_NAME = "Songlog"
# The startup entry's names before the app was called Songlog, moved to APP_NAME
OLD_APP_NAMES = ("Spotify Playlist Tracker",)
MUTEX_NAME = "Local\\SpotifyPlaylistTracker"
PORT_FILE = BASE_DIR / ".instance"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
# The icon's colors, the window's dark theme (desktop/src/styles.css): its raised surface, --chart green for the
# notebook, a darker green for its spine, --series-3 amber for the bookmark and --text for the headphones and pages
ICON_TILE = "#262a31"
ICON_COVER = "#2ea043"
ICON_SPINE = "#1f7a35"
ICON_RIBBON = "#c98500"
ICON_LIGHT = "#e6e8eb"
# The desktop window names the command Windows starts it with (desktop/electron/main.ts)
AUTOSTART_ENV = "PLAYLIST_TRACKER_AUTOSTART"


class SingleInstance:
    """Holds the instance lock and listens for "show" requests from later copies of the app."""

    def __init__(self):
        self._handle = None
        self._lock_file = None
        self._server: socket.socket | None = None
        self.requests: queue.Queue[str] = queue.Queue()

    def acquire(self) -> bool:
        """True if this is the only running copy."""
        if sys.platform == "win32":
            import ctypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateMutexW.restype = ctypes.c_void_p
            self._handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
            if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
                return False
        else:
            import fcntl
            self._lock_file = open(BASE_DIR / ".instance.lock", "w")
            try:
                fcntl.flock(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return False
        self._listen()
        return True

    def _listen(self) -> None:
        try:
            self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server.bind(("127.0.0.1", 0))
            self._server.listen()
            PORT_FILE.write_text(str(self._server.getsockname()[1]), encoding="utf-8")
        except OSError:
            self._server = None
            return
        threading.Thread(target=self._accept, name="instance-listener", daemon=True).start()

    def _accept(self) -> None:
        while self._server:
            try:
                connection, _ = self._server.accept()
            except OSError:
                return
            with connection:
                connection.settimeout(2)
                try:
                    if connection.recv(16).strip() == b"show":
                        self.requests.put("show")
                except OSError:
                    pass

    def release(self) -> None:
        if self._server:
            server, self._server = self._server, None
            server.close()
            PORT_FILE.unlink(missing_ok=True)


def icon_image(size: int = 64, detailed: bool | None = None):
    """The app's icon, Songlog's listening notebook: a green notebook with an amber bookmark wearing headphones, on a
    rounded dark tile. Drawn so no image file has to be shipped (build.py makes the icon files from it). Small sizes
    leave out the pages and the spine, which would run together."""
    from PIL import Image, ImageDraw

    if detailed is None:
        detailed = size >= 64
    scale = 4
    s = size * scale
    image = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, s - 1, s - 1), radius=s * 0.22, fill=ICON_TILE)
    # The drawing is laid out on 120 units, as the logo (desktop/src/components/Logo.tsx)
    u = s / 120

    def box(x0, y0, x1, y1):
        return (x0 * u, y0 * u, x1 * u, y1 * u)

    def band(radius, width):
        """The headband: half a ring around (60, 60) whose line runs at radius, down to the ear cups."""
        outer = radius + width / 2
        draw.arc(box(60 - outer, 60 - outer, 60 + outer, 60 + outer), 180, 360, fill=ICON_LIGHT,
                 width=round(width * u))
        for x in (60 - radius, 60 + radius):
            draw.line(box(x, 60, x, 74), fill=ICON_LIGHT, width=round(width * u))
            draw.ellipse(box(x - width / 2, 74 - width / 2, x + width / 2, 74 + width / 2), fill=ICON_LIGHT)

    if detailed:
        draw.rounded_rectangle(box(34, 55, 90, 104), radius=6 * u, fill=ICON_LIGHT)
        draw.rounded_rectangle(box(30, 50, 86, 100), radius=7 * u, fill=ICON_COVER)
        draw.rounded_rectangle(box(30, 50, 40, 100), radius=4 * u, fill=ICON_SPINE)
        draw.polygon([(62 * u, 50 * u), (62 * u, 80 * u), (68 * u, 74 * u), (74 * u, 80 * u), (74 * u, 50 * u)],
                     fill=ICON_RIBBON)
        band(39, 8)
        draw.rounded_rectangle(box(11, 64, 29, 96), radius=9 * u, fill=ICON_LIGHT)
        draw.rounded_rectangle(box(91, 64, 109, 96), radius=9 * u, fill=ICON_LIGHT)
    else:
        draw.rounded_rectangle(box(30, 50, 90, 102), radius=8 * u, fill=ICON_COVER)
        draw.polygon([(60 * u, 50 * u), (60 * u, 82 * u), (68 * u, 74 * u), (76 * u, 82 * u), (76 * u, 50 * u)],
                     fill=ICON_RIBBON)
        band(40, 12)
        draw.rounded_rectangle(box(8, 62, 30, 96), radius=11 * u, fill=ICON_LIGHT)
        draw.rounded_rectangle(box(90, 62, 112, 96), radius=11 * u, fill=ICON_LIGHT)
    return image.resize((size, size), Image.LANCZOS)


def autostart_command() -> str:
    return os.environ.get(AUTOSTART_ENV, "")


def autostart_supported() -> bool:
    """On Windows, when the window said how it is started."""
    return sys.platform == "win32" and bool(autostart_command())


def autostart_value() -> str:
    """The command Windows starts the app with at login, or "" when it is not started."""
    if sys.platform != "win32":
        return ""
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            for name in (APP_NAME, *OLD_APP_NAMES):
                try:
                    value, _ = winreg.QueryValueEx(key, name)
                except OSError:
                    continue
                if value:
                    return value
    except OSError:
        pass
    return ""


def autostart_enabled() -> bool:
    return bool(autostart_value())


def set_autostart(enabled: bool) -> None:
    if not autostart_supported():
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, autostart_command())
        for name in (*OLD_APP_NAMES, *(() if enabled else (APP_NAME,))):
            try:
                winreg.DeleteValue(key, name)
            except FileNotFoundError:
                pass
