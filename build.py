"""
Builds a single-file Windows program: dist/Spotify Playlist Tracker.exe

    python -m pip install pyinstaller -r requirements.txt
    python build.py

The .exe needs no Python installation. It keeps its settings and history next to itself, so copy
config.json and the .db files into the same folder to take your existing data along.
"""

import subprocess
import sys
from pathlib import Path

import background

ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"


def main() -> None:
    if not background.TRAY_AVAILABLE:
        sys.exit("Install the optional packages first: python -m pip install -r requirements.txt")
    BUILD_DIR.mkdir(exist_ok=True)
    icon = BUILD_DIR / "icon.ico"
    background.icon_image(256).save(icon, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])
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
