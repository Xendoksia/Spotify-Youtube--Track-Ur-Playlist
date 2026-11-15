"""
The account as data and actions for the desktop window, as the Tk window's account page (ui/account_page.py) and
login screen (ui/login_screen.py): the profile, how syncing goes, this computer's plays, and logging in, out,
reading the account again and syncing now. Each action runs on a thread of its own and ends with an "account"
event: state "done" (message) or "error" (message).
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Callable

from playlist_tracker.core import account, sync
from playlist_tracker.core.errors import TrackerError
from playlist_tracker.core.i18n import number, t
from playlist_tracker.music import artwork, listening
from playlist_tracker.ui.stats.text import month_name

AVATAR_PATH = artwork.ART_DIR / "account" / "avatar.jpg"


def day(iso: str | None) -> str:
    """The day an account was made, as "5 November 2026"."""
    if not iso:
        return ""
    try:
        moment = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return iso
    return f"{moment.day} {month_name(moment.month)} {moment.year}"


def sync_state() -> dict:
    """The outcome of the last sync and what waits on this computer."""
    last = sync.last
    if last.get("error"):
        state, text, when, counts = "failed", t("account.sync_state.failed"), "", last["error"]
    elif last.get("at"):
        state, text = "done", t("account.sync_state.done")
        when = t("account.sync_at", time=f"{last['at']:%H:%M}")
        counts = t("account.sync_counts", sent=number(last["sent"]), received=number(last["received"]))
    else:
        state, text, when, counts = "waiting", t("account.sync_state.waiting"), t("account.sync_every"), ""
    total, waiting = sum(listening.counts().values()), listening.unsynced_count()
    return {
        "state": state, "text": text, "when": when, "counts": counts,
        "device": sync.device()[1], "plays": t("account.device_plays", count=number(total)),
        "waiting": t("account.device_waiting", count=number(waiting)) if waiting else t("account.device_all_sent"),
        "all_sent": not waiting,
    }


class Account:
    def __init__(self, emit: Callable[..., None]):
        self.emit = emit
        self.busy = False
        self._lock = threading.Lock()

    def page(self) -> dict:
        user = account.profile()
        result = {"configured": account.configured(), "needs_login": account.needs_login(),
                  "remembered": account.remembered(), "busy": self.busy, "profile": None}
        if user:
            name = user.get("name") or user.get("email") or "?"
            result["profile"] = {
                "name": name, "first_name": name.split()[0],
                "email": user.get("email") if user.get("name") else "",
                "detail": t("account.since", provider=(user.get("provider") or "").capitalize(),
                            date=day(user.get("created_at"))),
                "avatar": "/api/avatar" if AVATAR_PATH.exists() else None,
                "details": [{"label": t("account.provider"), "value": (user.get("provider") or "").capitalize() or "—"},
                            {"label": t("account.created"), "value": day(user.get("created_at")) or "—"},
                            {"label": t("account.user_id"), "value": (user.get("id") or "")[:8] or "—"}],
            }
            result["sync"] = sync_state()
        return result

    def skip(self) -> dict:
        """Going on without an account: not asked again while the app runs."""
        account.decided = True
        return self.page()

    def _run(self, task: Callable[[], object], on_success: Callable[[object], str], status: str) -> dict:
        with self._lock:
            if self.busy:
                return {"started": False}
            self.busy = True
        self.emit("account", state="busy", message=status)

        def worker():
            try:
                message = on_success(task())
                state = "done"
            except TrackerError as error:
                state, message = "error", str(error)
            except Exception as error:  # e.g. offline in an unexpected way
                state, message = "error", t("error.unexpected", error=repr(error))
            finally:
                self.busy = False
            self.emit("account", state=state, message=message)

        threading.Thread(target=worker, name="account", daemon=True).start()
        return {"started": True}

    def _logged_in(self, user: dict) -> str:
        account.decided = True
        self.download_avatar(user)
        if sync.syncer:
            sync.syncer.wake()
        return t("account.welcome", name=user.get("name") or user.get("email"))

    def login(self, remember: bool | None = None) -> dict:
        if remember is not None:
            account.set_remembered(remember)
        return self._run(lambda: account.AccountClient().login(), self._logged_in, t("account.waiting"))

    def refresh(self) -> dict:
        return self._run(lambda: account.AccountClient().refresh(), self._logged_in, t("account.refreshing"))

    def logout(self) -> dict:
        def done(_):
            AVATAR_PATH.unlink(missing_ok=True)
            account.decided = False
            return ""
        return self._run(lambda: account.AccountClient().logout(), done, t("account.logging_out"))

    def sync_now(self) -> dict:
        if not sync.syncer:
            return {"started": False}
        # The syncer tells the window what came with the usual "synced" event
        return self._run(sync.syncer.run_once, lambda result: "", t("account.syncing"))

    def download_avatar(self, user: dict) -> None:
        url = user.get("avatar")
        if not url:
            return

        def worker():
            try:
                saved = artwork.save_image(artwork._get(url, as_json=False), AVATAR_PATH)
            except OSError:
                return
            if saved:
                self.emit("account", state="avatar", message="")

        threading.Thread(target=worker, name="avatar", daemon=True).start()
