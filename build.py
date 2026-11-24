"""
Builds the program the desktop window (desktop/) starts behind itself, into build/backend:

    python -m pip install pyinstaller -r requirements.txt
    python build.py

It needs no Python installation. The window's installer (npm run dist in desktop/) runs this and takes it
from there.
"""

import os
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
        # The suggestion models (music/model.py), read from the backend's own folder
        "--add-data", f"{ROOT / 'models'}{os.pathsep}models",
    ], check=True, cwd=ROOT)
    # PyInstaller names the folder after the program; the installer looks for build/backend
    target = BUILD_DIR / "backend"
    if target.exists():
        shutil.rmtree(target)
    (BUILD_DIR / BACKEND_NAME).rename(target)
    print(f"\nDone: {target / (BACKEND_NAME + '.exe')}")


def main() -> None:
    build_backend()


if __name__ == "__main__":
    main()
