"""
Builds a single-file Windows program: dist/Spotify Playlist Tracker.exe

    python -m pip install pyinstaller -r requirements.txt
    python build.py

The .exe needs no Python installation. It keeps its settings and history next to itself, so copy
config.json and the .db files into the same folder to take your existing data along.

    python build.py backend

builds the program the desktop window (desktop/) starts behind itself, into build/backend; the window's
installer (npm run dist in desktop/) takes it from there.
"""

import shutil
import subprocess
import sys
from pathlib import Path

from playlist_tracker import background

ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"


BACKEND_NAME = "PlaylistTrackerBackend"


def make_icon():
    BUILD_DIR.mkdir(exist_ok=True)
    icon = BUILD_DIR / "icon.ico"
    background.icon_image(256).save(icon, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])
    return icon


def build_backend() -> None:
    """A folder rather than one file: it starts at once, where one file unpacks itself first every time. It is a
    console program because the window talks to it through its standard input and output; the window starts
    it hidden."""
    icon = make_icon()
    subprocess.run([
        sys.executable, "-m", "PyInstaller", str(ROOT / "playlist_tracker" / "backend.py"),
        "--name", BACKEND_NAME,
        "--onedir", "--console", "--noconfirm", "--clean",
        "--icon", str(icon),
        "--paths", str(ROOT),
        "--distpath", str(BUILD_DIR),
        "--workpath", str(BUILD_DIR / "backend-work"),
        "--specpath", str(BUILD_DIR),
        "--collect-submodules", "winrt",
    ], check=True, cwd=ROOT)
    # PyInstaller names the folder after the program; the installer looks for build/backend
    target = BUILD_DIR / "backend"
    if target.exists():
        shutil.rmtree(target)
    (BUILD_DIR / BACKEND_NAME).rename(target)
    print(f"\nDone: {target / (BACKEND_NAME + '.exe')}")


def main() -> None:
    if sys.argv[1:] == ["backend"]:
        build_backend()
        return
    if not background.TRAY_AVAILABLE:
        sys.exit("Install the optional packages first: python -m pip install -r requirements.txt")
    icon = make_icon()
    subprocess.run([
        sys.executable, "-m", "PyInstaller", str(ROOT / "app.py"),
        "--name", background.APP_NAME,
        "--onefile", "--windowed", "--noconfirm", "--clean",
        "--icon", str(icon),
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(BUILD_DIR),
        "--specpath", str(BUILD_DIR),
        # winrt is a namespace package whose parts are found at run time, and pystray picks its backend the same way
        "--collect-submodules", "winrt",
        "--hidden-import", "pystray._win32",
    ], check=True, cwd=ROOT)
    print(f"\nDone: {ROOT / 'dist' / (background.APP_NAME + '.exe')}")


if __name__ == "__main__":
    main()
