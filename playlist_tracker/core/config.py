"""
Settings in config.json and where the app keeps its files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Settings and history live next to the program: app.py, or the .exe when it is built with PyInstaller
BASE_DIR = (Path(sys.executable).resolve().parent if getattr(sys, "frozen", False)
            else Path(__file__).resolve().parents[2])
CONFIG_PATH = BASE_DIR / "config.json"
DEFAULT_MARKET = "TR"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def market() -> str:
    """Country code used to check playability on Spotify and YouTube."""
    return load_config().get("MARKET") or DEFAULT_MARKET
