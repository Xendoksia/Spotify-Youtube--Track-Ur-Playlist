"""
Running in the background: one instance at a time, a system tray icon and starting with Windows.

Only one copy of the app may run, otherwise two listening trackers would record the same song twice.
A second copy asks the running one to show its window and exits.
"""

from __future__ import annotations

import queue
import socket
import sys
import threading
from pathlib import Path
from typing import Callable

from playlist_tracker.core.config import BASE_DIR
from playlist_tracker.core.i18n import t

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:  # the app still works without a tray icon, closing the window then exits
    pystray = None

APP_NAME = "Spotify Playlist Tracker"
MUTEX_NAME = "Local\\SpotifyPlaylistTracker"
PORT_FILE = BASE_DIR / ".instance"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
MINIMIZED_FLAG = "--minimized"
ICON_COLOR = "#1aa34a"

TRAY_AVAILABLE = pystray is not None


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

    @staticmethod
    def notify_running() -> None:
        """Ask the copy that is already running to bring its window to the front."""
        try:
            port = int(PORT_FILE.read_text(encoding="utf-8"))
            with socket.create_connection(("127.0.0.1", port), timeout=2) as connection:
                connection.sendall(b"show")
        except (OSError, ValueError):
            pass

    def release(self) -> None:
        if self._server:
            server, self._server = self._server, None
            server.close()
            PORT_FILE.unlink(missing_ok=True)


def icon_image(size: int = 64):
    """A green circle with equalizer bars, drawn so no image file has to be shipped."""
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


class Tray:
    """System tray icon. Menu actions run on the tray thread; window actions are queued for Tk."""

    def __init__(self, commands: queue.Queue[str], is_paused: Callable[[], bool],
                 set_paused: Callable[[bool], None]):
        self.commands = commands
        self.is_paused = is_paused
        self.set_paused = set_paused
        self._icon = None
        self.hint_shown = False

    def start(self) -> None:
        if not TRAY_AVAILABLE or self._icon:
            return
        # Texts are read on every menu open, so a language change applies without restarting the icon
        menu = pystray.Menu(
            pystray.MenuItem(lambda item: t("tray.open"), lambda: self.commands.put("show"), default=True),
            pystray.MenuItem(lambda item: t("tray.pause"), lambda: self.set_paused(not self.is_paused()),
                             checked=lambda item: self.is_paused()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda item: t("tray.quit"), lambda: self.commands.put("quit")),
        )
        self._icon = pystray.Icon("spotify-playlist-tracker", icon_image(), t("app.title"), menu)
        self._icon.run_detached()

    def set_title(self, title: str) -> None:
        if self._icon:
            self._icon.title = title

    def notify(self, message: str) -> None:
        if self._icon:
            try:
                self._icon.notify(message, t("app.title"))
            except Exception:  # notifications are a nicety, never a reason to fail
                pass

    def stop(self) -> None:
        if self._icon:
            icon, self._icon = self._icon, None
            icon.stop()


def autostart_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" {MINIMIZED_FLAG}'
    # pythonw runs without a console window
    python = Path(sys.executable)
    pythonw = python.with_name("pythonw.exe")
    if pythonw.exists():
        python = pythonw
    return f'"{python}" "{Path(BASE_DIR, "app.py")}" {MINIMIZED_FLAG}'


def autostart_supported() -> bool:
    return sys.platform == "win32"


def autostart_enabled() -> bool:
    if not autostart_supported():
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
    except OSError:
        return False
    return bool(value)


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


def start_minimized() -> bool:
    return MINIMIZED_FLAG in sys.argv[1:]


def close_to_tray(config: dict) -> bool:
    return TRAY_AVAILABLE and config.get("CLOSE_TO_TRAY", True) is not False
