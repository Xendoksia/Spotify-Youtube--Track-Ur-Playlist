"""
Playlist tracking as data and actions for the desktop window, as the earlier window's playlist tabs and
history tab: each service's playlists as cards, tracking one or
not, logging in, loading one's playlists, adding one by link, checking the tracked ones, the result of the last
check, and the history of changes.

Network work runs on one worker thread at a time, as in the earlier window; its progress and end are told to the
window as "task" events, and the cards change with a "playlists" event.
"""

from __future__ import annotations

import re
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib.parse import urlencode

from playlist_tracker.core.config import load_config
from playlist_tracker.core.errors import TrackerError
from playlist_tracker.core.i18n import number, t
from playlist_tracker.api.listening import day_title
from playlist_tracker.api.overview import cover_url
from playlist_tracker.core.text import track_label
from playlist_tracker.playlists import history
from playlist_tracker.playlists.services import EVENTS, SERVICES, event_label
from playlist_tracker.music.text import month_name

# Order of the latest changes on a card: what went wrong first
CHANGE_ORDER = (history.EVENT_REMOVED, history.EVENT_UNPLAYABLE, history.EVENT_PLAYABLE, history.EVENT_ADDED)
# The CSS name of each event's color
EVENT_KINDS = {history.EVENT_ADDED: "added", history.EVENT_REMOVED: "removed",
               history.EVENT_UNPLAYABLE: "unplayable", history.EVENT_PLAYABLE: "playable",
               history.EVENT_INITIAL: "initial"}


def short_date(iso: str) -> str:
    """A check time as "4 Nov 15:27"."""
    moment = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
    return f"{moment.day} {month_name(moment.month, True)} {moment:%H:%M}"


def service_of(name: str):
    for service in SERVICES:
        if service.name == name or service.key == name:
            return service
    raise ValueError(name)


ACTIVITY_DAYS = 30


def activity(days: dict[str, dict[str, int]] | None, today: datetime) -> dict | None:
    """A card's tracks added and removed per day over the last 30 days, or None when nothing changed."""
    if not days:
        return None
    result, added, removed = [], 0, 0
    for back in range(ACTIVITY_DAYS - 1, -1, -1):
        day = today - timedelta(days=back)
        counts = days.get(day.strftime("%Y-%m-%d"), {"added": 0, "removed": 0})
        added += counts["added"]
        removed += counts["removed"]
        result.append({**counts, "tooltip": f"{day.day} {month_name(day.month)}\n"
                                            f"+{counts['added']}  −{counts['removed']}"})
    return {"days": result, "label": t("panel.last_days", count=ACTIVITY_DAYS),
            "added": f"+{number(added)}", "removed": f"−{number(removed)}"}


def track_image(service, track: dict) -> str:
    """A track's picture: the album cover, or the video's thumbnail on YouTube."""
    if service.key == "youtube":
        return "/api/video-thumbnail?" + urlencode({"id": track.get("uri") or ""})
    return cover_url(track.get("artist") or "", track.get("album"), track.get("name") or "")


def event_text(event: str) -> dict:
    return {"kind": EVENT_KINDS.get(event, "initial"), "label": event_label(event)}


class Playlists:
    def __init__(self, emit: Callable[..., None]):
        self.emit = emit
        # Per service: the playlists loaded from the account or added by link this run (owner and size), by id;
        # whether one is tracked always comes from the database, which syncing also changes
        self.loaded: dict[str, dict[str, dict]] = {service.name: {} for service in SERVICES}
        # Per service: the result of the last check, by hand or automatic
        self.results: dict[str, dict | None] = {service.name: None for service in SERVICES}
        self.status = ""
        self.busy: str | None = None
        self._lock = threading.Lock()

    # Reading

    def services(self) -> dict:
        config = load_config()
        return {"services": [{
            "name": service.name, "key": service.key, "account": service.account,
            "has_credentials": service.has_credentials(config),
        } for service in SERVICES], "busy": self.busy, "status": self.status}

    def page(self, name: str) -> dict:
        service = service_of(name)
        config = load_config()
        user = service.session_user(config)
        stored = history.known_playlists(service.db_path)
        tracked = {p["playlist_id"]: p for p in stored if p["tracked"]}
        summaries = history.playlist_summaries(service.db_path)
        latest = history.latest_tracks(service.db_path)
        today = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        since = (today - timedelta(days=ACTIVITY_DAYS - 1)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        changes_by_day = history.daily_changes(since, service.db_path)
        cards = {}
        for playlist_id, p in self.loaded[service.name].items():
            cards[playlist_id] = {"name": p["name"], "owner": p.get("owner", ""), "count": p.get("track_count")}
        # Playlists added by link are not loaded again after a restart: from the database they keep their card even
        # when tracking is switched off, so it can be switched on again
        for p in stored:
            cards.setdefault(p["playlist_id"], {"name": p["name"], "owner": "", "count": None})
        items = t(f"items.{service.items}")
        result = []
        for playlist_id, card in cards.items():
            summary = summaries.get(playlist_id) or {}
            known = tracked.get(playlist_id)
            count = card["count"] if card["count"] not in (None, "") else summary.get("tracks")
            details = [part for part in (card["owner"], f"{number(count)} {items}" if count is not None else "") if part]
            checked = known["last_checked"] if known else None
            changes = []
            if summary.get("changes"):
                for event in CHANGE_ORDER:
                    if summary["changes"].get(event):
                        changes.append({**event_text(event), "symbol": event_label(event).split()[0],
                                        "count": number(summary["changes"][event])})
            result.append({
                "id": playlist_id, "name": card["name"], "tracked": known is not None,
                "details": "  ·  ".join(details),
                "checked": t("panel.last_checked", date=short_date(checked)) if checked else t("panel.never_checked"),
                "last_change": t("panel.last_change", date=short_date(summary["changed_at"])) if changes else "",
                "changes": changes, "url": service.playlist_url.format(playlist_id),
                "covers": [track_image(service, track) for track in latest.get(playlist_id, [])],
                "latest": t("panel.latest", track=track_label(latest[playlist_id][0]))
                if latest.get(playlist_id) else "",
                "activity": activity(changes_by_day.get(playlist_id), today),
            })
        result.sort(key=lambda card: (not card["tracked"], card["name"].lower()))
        return {
            "name": service.name, "key": service.key,
            "login": {"user": user, "text": t("login.logged_in", user=user) if user is not None else "",
                      "button": t("login.switch") if user is not None else t("login.button", account=service.account)},
            "has_credentials": service.has_credentials(config),
            "playlists": result, "tracked_count": len(tracked),
            "result": self.results[service.name], "busy": self.busy, "status": self.status,
        }

    # Tracking

    def toggle(self, name: str, playlist_id: str) -> dict:
        service = service_of(name)
        tracked = {p["playlist_id"] for p in history.tracked_playlists(service.db_path)}
        self._set_tracked(service, playlist_id, playlist_id not in tracked)
        return self.page(name)

    def set_all(self, name: str, tracked: bool) -> dict:
        service = service_of(name)
        current = {p["playlist_id"] for p in history.tracked_playlists(service.db_path)}
        for playlist_id in self._card_names(service):
            if (playlist_id in current) != tracked:
                self._set_tracked(service, playlist_id, tracked)
        return self.page(name)

    def _card_names(self, service) -> dict[str, str]:
        names = {pid: p["name"] for pid, p in self.loaded[service.name].items()}
        for p in history.known_playlists(service.db_path):
            names.setdefault(p["playlist_id"], p["name"])
        return names

    def _set_tracked(self, service, playlist_id: str, tracked: bool) -> None:
        name = self._card_names(service).get(playlist_id)
        if name is None:
            raise ValueError(playlist_id)
        history.set_tracked(playlist_id, name, tracked, service.db_path)

    # Work over the network

    def _set_status(self, text: str, checking: str | None = None) -> None:
        """Tell the window the progress; checking is the id of the playlist being checked now."""
        self.status = text
        self.emit("task", status=text, busy=self.busy, checking=checking)

    def _run(self, name: str, task: Callable[[], object], on_success: Callable[[object], None],
             status: str = "", keyless: bool = False) -> dict:
        """Start network work for a service unless some is running; its end comes as a "task" event with
        state "done", "error" (message) or "login" (logging in is needed again; message). keyless: the work can
        run without keys on a service that reads links from their page."""
        service = service_of(name)
        if not (keyless and service.keyless_links) and not service.has_credentials(load_config()):
            return {"started": False, "reason": "credentials"}
        with self._lock:
            if self.busy:
                return {"started": False, "reason": "busy"}
            self.busy = service.name
        if status:
            self._set_status(status)

        def worker():
            state, message = "done", ""
            try:
                on_success(task())
            except service.login_required as error:
                state, message = "login", t("dialog.login_now", error=str(error))
                self.status = t("status.login_required")
            except TrackerError as error:
                state, message = "error", str(error)
                self.status = t("status.error")
            except Exception as error:
                state, message = "error", t("error.unexpected", error=repr(error))
                self.status = t("status.error")
            finally:
                self.busy = None
            self.emit("task", service=service.name, state=state, message=message, status=self.status, busy=None)
            self.emit("playlists", service=service.name)

        threading.Thread(target=worker, name="playlists", daemon=True).start()
        return {"started": True}

    def login(self, name: str) -> dict:
        """Log in in the browser, then load the account's playlists, as the earlier window did."""
        service = service_of(name)

        def task():
            user = service.connect().login()
            return user, service.connect().my_playlists()

        def done(result):
            user, playlists = result
            self._take_loaded(service, playlists)
            self.status = t("status.logged_in", service=service.name, user=user)
        return self._run(name, task, done, t(f"login.hint.{service.key}"))

    def _take_loaded(self, service, result) -> None:
        readable, others = result
        for p in readable:
            self.loaded[service.name][p["id"]] = {"name": p["name"], "owner": p["owner"],
                                                  "track_count": p["track_count"]}
        note = t("status.hidden_others", count=len(others)) if others else ""
        self.status = t("status.found", count=len(readable), service=service.name) + note

    def load(self, name: str) -> dict:
        service = service_of(name)

        return self._run(name, lambda: service.connect().my_playlists(),
                         lambda result: self._take_loaded(service, result),
                         t("status.loading", service=service.name))

    def add(self, name: str, link: str) -> dict:
        service = service_of(name)
        try:
            playlist_id = service.parse_playlist_id(link.strip())
        except TrackerError as error:
            return {"started": False, "reason": "error", "message": str(error)}

        def done(playlist_name):
            existing = self.loaded[service.name].get(playlist_id, {})
            self.loaded[service.name][playlist_id] = {**existing, "name": playlist_name}
            history.set_tracked(playlist_id, playlist_name, True, service.db_path)
            self.status = t("status.now_tracked", name=playlist_name)
        return self._run(name, lambda: service.connect().playlist_name(playlist_id), done, t("status.fetching"),
                         keyless=True)

    def check(self, name: str) -> dict:
        service = service_of(name)
        selected = [(p["playlist_id"], p["name"]) for p in history.tracked_playlists(service.db_path)]
        if not selected:
            return {"started": False, "reason": "nothing",
                    "title": t("dialog.nothing_selected"), "message": t("dialog.nothing_selected.text")}

        def task():
            client = service.connect()
            results = []
            for index, (playlist_id, playlist_name) in enumerate(selected, 1):
                self._set_status(t("status.checking", index=index, count=len(selected), name=playlist_name),
                                 checking=playlist_id)
                try:
                    results.append(history.check_playlist(client, playlist_id, service.db_path))
                except service.login_required:
                    raise
                except TrackerError as error:
                    results.append({"name": playlist_name, "error": str(error)})
            return results
        return self._run(name, task, lambda results: self.show_results(service.name, results), keyless=True)

    def show_results(self, name: str, results: list[dict], automatic: bool = False) -> None:
        """Keep a check's result for its tab, from the Check button or the automatic check."""
        service = service_of(name)
        items = t(f"items.{service.items}")
        playlists, total_changes = [], 0
        for r in results:
            if "error" in r:
                playlists.append({"name": r["name"], "meta": "", "note": t("result.error", error=r["error"]),
                                  "error": True, "rows": []})
                continue
            existing = self.loaded[service.name].get(r["playlist_id"])
            if existing is not None:
                existing.update(name=r["name"], track_count=r["total"])
            meta = f"{number(r['total'])} {items}"
            if r["first_check"]:
                playlists.append({"name": r["name"], "meta": meta, "note": t("result.initial"), "error": False,
                                  "rows": [{**event_text(history.EVENT_UNPLAYABLE), "track": track_label(track),
                                            "date": ""} for track in r["unavailable"]]})
                continue
            changes = ([(history.EVENT_ADDED, track) for track in r["added"]]
                       + [(history.EVENT_REMOVED, track) for track in r["removed"]]
                       + [(history.EVENT_UNPLAYABLE, track) for track in r["unplayable"]]
                       + [(history.EVENT_PLAYABLE, track) for track in r["playable_again"]])
            total_changes += len(changes)
            playlists.append({
                "name": r["name"], "meta": meta, "error": False,
                "note": t("result.changes", count=len(changes)) if changes else t("result.no_changes"),
                "rows": [{**event_text(event), "track": track_label(track),
                          "date": t("result.added", date=short_date(track["added_at"])).strip()
                          if track.get("added_at") else ""} for event, track in changes],
            })
        self.results[service.name] = {"playlists": playlists}
        self.status = t("status.auto_check_done" if automatic else "status.check_done", count=len(results),
                        changes=total_changes)
        if automatic:
            self.emit("task", service=service.name, state="done", message="", status=self.status, busy=self.busy)
            self.emit("playlists", service=service.name)

    # History

    def history(self, name: str, playlist_id: str | None, event: str | None) -> dict:
        """The changes found, newest first, under a heading for each day they were found."""
        service = service_of(name)
        tracked = sorted(history.tracked_playlists(service.db_path), key=lambda p: p["name"].lower())
        today = datetime.now().astimezone().date()
        days: list[dict] = []
        for r in history.get_events(playlist_id or None, service.db_path):
            if event and r["event"] != event:
                continue
            moment = datetime.fromisoformat(r["checked_at"].replace("Z", "+00:00")).astimezone()
            if not days or days[-1]["date"] != moment.date():
                days.append({"date": moment.date(), "title": day_title(moment.date(), today), "counts": {}, "rows": []})
            day = days[-1]
            initial = r["event"] == history.EVENT_INITIAL
            count = re.match(r"(\d+) ", r["name"] or "")
            day["counts"][r["event"]] = day["counts"].get(r["event"], 0) + 1
            day["rows"].append({
                **event_text(r["event"]), "time": f"{moment:%H:%M}", "playlist": r["playlist"] or "",
                "title": t("history.initial_count", count=count.group(1)) if initial and count else r["name"] or "",
                "artist": "" if initial else r["artist"] or "",
                "added": t("result.added", date=short_date(r["added_at"])).strip().strip("()") if r["added_at"] else "",
                "image": None if initial else track_image(service, r),
            })
        for day in days:
            day["date"] = day["date"].isoformat()
            day["counts"] = [{**event_text(e), "symbol": event_label(e).split()[0], "count": number(day["counts"][e])}
                             for e in (*CHANGE_ORDER[::-1], history.EVENT_INITIAL) if day["counts"].get(e)]
        return {"playlists": [{"id": p["playlist_id"], "name": p["name"]} for p in tracked],
                "events": [{"id": e, "label": event_label(e)} for e in EVENTS], "days": days}

    def export(self, name: str, path: str) -> dict:
        service = service_of(name)
        count = history.export_csv(path, service.db_path)
        self.status = t("status.exported", count=count, service=service.name, path=path)
        self.emit("task", status=self.status, busy=self.busy)
        return {"count": count}
