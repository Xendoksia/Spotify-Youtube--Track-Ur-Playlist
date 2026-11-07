"""
Starts the app: one running copy, the listening recorder and the tray icon, which outlive the window when
it is rebuilt after a language or theme change.
"""

from __future__ import annotations

from playlist_tracker import background
from playlist_tracker.core import account, i18n, sync
from playlist_tracker.core.config import load_config
from playlist_tracker.music import nowplaying
from playlist_tracker.playlists.auto_check import AutoChecker
from playlist_tracker.ui import theme
from playlist_tracker.ui.listening_view import set_tracking, tracking_enabled
from playlist_tracker.ui.main_window import App


def main():
    theme.make_dpi_aware()
    i18n.set_language(load_config().get("LANGUAGE"))
    instance = background.SingleInstance()
    if not instance.acquire():
        # Already running: a second tracker would record every song twice, so show the open window instead
        if not background.start_minimized():
            instance.notify_running()
        return

    # The tracker and tray icon outlive windows rebuilt after a language or theme change,
    # so a song keeps being one play
    account.end_unremembered_session()
    local_tracker = nowplaying.LocalTracker()
    if tracking_enabled(load_config()):
        local_tracker.start()
    commands = instance.requests
    tray = background.Tray(commands, is_paused=lambda: not local_tracker.enabled,
                           set_paused=lambda paused: set_tracking(local_tracker, not paused))
    tray.start()
    # Results go to the window through the same queue as the tray's requests
    checker = AutoChecker(tray.notify, lambda service, results: commands.put(("checked", service, results)))
    checker.start()
    sync.syncer = sync.Syncer(lambda result: commands.put(("synced", result)))
    sync.syncer.start()
    hidden = background.start_minimized()
    section = None
    try:
        while True:
            app = App(local_tracker, commands, tray, hidden, section)
            app.mainloop()
            hidden, section = app.restart_hidden, app.restart_section
            if not app.restart:
                break
    finally:
        checker.stop()
        sync.syncer.stop()
        tray.stop()
        local_tracker.stop()
        instance.release()
