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

APP_NAME = "Spotify Playlist Tracker"
MUTEX_NAME = "Local\\SpotifyPlaylistTracker"
PORT_FILE = BASE_DIR / ".instance"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
ICON_COLOR = "#1aa34a"
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


def icon_image(size: int = 64):
    """A green circle with equalizer bars, drawn so no image file has to be shipped (build.py makes the
    icon files from it)."""
    from PIL import Image, ImageDraw

    scale = 4
    image = Image.new("RGBA", (size * scale, size * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    s = size * scale
    draw.ellipse((0, 0, s - 1, s - 1), fill=ICON_COLOR)
    bar, gap = s * 0.12, s * 0.07
    left = (s - 3 * bar - 2 * gap) / 2
    for index, height in enumerate((0.34, 0.52, 0.26)):
        x = left + index * (bar + gap)
        top, bottom = s * (0.5 - height / 2), s * (0.5 + height / 2)
        draw.rounded_rectangle((x, top, x + bar, bottom), radius=bar / 2, fill="white")
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
            value, _ = winreg.QueryValueEx(key, APP_NAME)
    except OSError:
        return ""
    return value or ""


def autostart_enabled() -> bool:
    return bool(autostart_value())


def set_autostart(enabled: bool) -> None:
    if not autostart_supported():
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
