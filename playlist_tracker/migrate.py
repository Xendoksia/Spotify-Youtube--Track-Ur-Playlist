"""
Moving the data to the installed desktop window's folder: the first time it starts with an empty folder, the
settings, histories and pictures are copied from where the earlier program kept them. That place is found from
the command Windows starts the earlier program with (app.py's or the .exe's folder).
"""

from __future__ import annotations

import shlex
import shutil
from pathlib import Path

from playlist_tracker import background

DATA_FILES = ("config.json", "history.db", "listening.db", "youtube_history.db")
ART_FOLDER = "artwork"


def has_data(folder: Path) -> bool:
    return any((folder / name).exists() for name in DATA_FILES)


def old_data_dir() -> Path | None:
    """The folder of the program Windows starts at login, when its data is there."""
    command = background.autostart_value()
    if not command:
        return None
    try:
        parts = shlex.split(command, posix=False)
    except ValueError:
        return None
    for part in parts:
        folder = Path(part.strip('"')).parent
        if part.lower().strip('"').endswith((".py", ".exe")) and has_data(folder):
            return folder
    return None


def migrate(target: Path) -> Path | None:
    """Copy the earlier program's data into target once, while target has none; the folder copied from, or None."""
    if has_data(target):
        return None
    source = old_data_dir()
    if source is None or source.resolve() == target.resolve():
        return None
    target.mkdir(parents=True, exist_ok=True)
    for name in DATA_FILES:
        if (source / name).exists():
            shutil.copy2(source / name, target / name)
    if (source / ART_FOLDER).is_dir():
        shutil.copytree(source / ART_FOLDER, target / ART_FOLDER, dirs_exist_ok=True)
    return source
