"""
Settings as data for the desktop window, as the Tk window's settings page (ui/settings_page.py): the Spotify and
YouTube credentials, language, theme, the automatic check and running in the background. Saving follows the
same rules, and a changed language or theme is told to the window (and to other devices by syncing).
"""

from __future__ import annotations

from typing import Callable

from playlist_tracker import background
from playlist_tracker.core import i18n, sync
from playlist_tracker.core.config import load_config, save_config
from playlist_tracker.core.i18n import t
from playlist_tracker.playlists import auto_check, spotify

THEMES = ("system", "light", "dark")
CREDENTIALS = ("CLIENT_ID", "CLIENT_SECRET", "YOUTUBE_API_KEY", "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET")
# An ID and its secret go together; a session issued for other app credentials is no longer valid
PAIRS = ((("CLIENT_ID", "CLIENT_SECRET"), "REFRESH_TOKEN", "spotify"),
         (("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET"), "YOUTUBE_REFRESH_TOKEN", "youtube"))
# The help topics: (icon, key); the texts are help.<key>.title, .why and .todo (todo may be empty)
HELP_TOPICS = (("settings", "setup"), ("list", "own_lists"), ("flag", "link"), ("tag", "unplayable"),
               ("history", "auto_check"), ("tracks", "listening"))


def current_theme(config: dict) -> str:
    return config.get("THEME") if config.get("THEME") in THEMES else "system"


def settings() -> dict:
    config = load_config()
    interval = config.get("AUTO_CHECK")
    if interval not in auto_check.INTERVALS:
        interval = auto_check.DEFAULT_INTERVAL
    return {
        "values": {key: config.get(key, "") for key in CREDENTIALS},
        "language": i18n.current(), "languages": [{"id": k, "label": v} for k, v in i18n.LANGUAGES.items()],
        "theme": current_theme(config), "themes": [{"id": k, "label": t(f"theme.{k}")} for k in THEMES],
        "auto_check": interval,
        "auto_checks": [{"id": k, "label": t(f"auto_check.{k}")} for k in auto_check.INTERVALS],
        # The window keeps running in the tray unless this is turned off
        "close_to_tray": config.get("CLOSE_TO_TRAY", True) is not False,
        "autostart": background.autostart_enabled(), "autostart_supported": background.autostart_supported(),
        "spotify_steps": t("settings.spotify_steps", redirect_uri=spotify.REDIRECT_URI),
    }


def save(body: dict, emit: Callable[..., None]) -> dict:
    """Save what the window sends; {"ok": False, "tab", "title", "message"} when something is missing."""
    config = load_config()
    updated = dict(config)
    values = {key: str((body.get("values") or {}).get(key, "")).strip() for key in CREDENTIALS}
    for keys, token_key, tab in PAIRS:
        if bool(values[keys[0]]) != bool(values[keys[1]]):
            return {"ok": False, "tab": tab, "title": t("settings.missing"), "message": t("settings.missing_pair")}
    for keys, token_key, tab in PAIRS:
        if any(values[k] != config.get(k, "") for k in keys):
            updated.pop(token_key, None)
    for key, value in values.items():
        if value:
            updated[key] = value
        else:
            updated.pop(key, None)
    language = body.get("language") if body.get("language") in i18n.LANGUAGES else i18n.current()
    theme = body.get("theme") if body.get("theme") in THEMES else current_theme(config)
    appearance_changed = language != i18n.current() or theme != current_theme(config)
    updated["LANGUAGE"], updated["THEME"] = language, theme
    if appearance_changed:
        sync.settings_changed(updated)
    if body.get("auto_check") in auto_check.INTERVALS:
        updated["AUTO_CHECK"] = body["auto_check"]
    updated["CLOSE_TO_TRAY"] = bool(body.get("close_to_tray", True))
    save_config(updated)
    message = t("status.saved")
    if bool(body.get("autostart")) != background.autostart_enabled():
        try:
            background.set_autostart(bool(body.get("autostart")))
        except OSError as error:
            message = t("settings.autostart_failed", error=error)
    if appearance_changed:
        i18n.set_language(language)
        if sync.syncer:
            sync.syncer.wake()
        emit("appearance")
    # The tray's choice and the services' login lines may have changed
    emit("settings")
    return {"ok": True, "message": message, "appearance_changed": appearance_changed}


def help_page() -> dict:
    return {"title": t("help.title"), "lead": t("help.lead"), "topics": [
        {"icon": icon, "title": t(f"help.{key}.title"), "why": t(f"help.{key}.why"), "todo": t(f"help.{key}.todo")}
        for icon, key in HELP_TOPICS]}
