"""
The app account: a Google login through Supabase Auth, the base of syncing between devices later.

The login runs in the browser with PKCE: Supabase sends the browser back to a local server with a code, which is
exchanged for a session. The refresh token is kept in config.json, the profile (name, e-mail, picture) next to it
so it shows without a connection.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

from playlist_tracker.core.config import load_config, save_config
from playlist_tracker.core.errors import TrackerError
from playlist_tracker.core.i18n import t
from playlist_tracker.playlists.oauth import start_redirect_server, wait_for_redirect

REDIRECT_PORT = 8889
REDIRECT_URI = f"http://127.0.0.1:{REDIRECT_PORT}/callback"
# Asked once after the first start; afterwards the app opens on listening
SKIPPED_KEY = "ACCOUNT_SKIPPED"

# One session for the whole app: Supabase hands out a new refresh token with each renewal and the old one stops
# working, so the window and the sync thread must not renew it each on their own
_session = {"token": None, "expires": 0.0}
_session_lock = threading.RLock()


class AccountError(TrackerError):
    pass


def configured(config: dict | None = None) -> bool:
    config = load_config() if config is None else config
    return bool(config.get("SUPABASE_URL") and config.get("SUPABASE_KEY"))


def profile(config: dict | None = None) -> dict | None:
    """The logged-in user as last seen: name, email, avatar, provider, created_at; None when logged out."""
    config = load_config() if config is None else config
    return config.get("ACCOUNT") if config.get("ACCOUNT_REFRESH_TOKEN") else None


def _profile_of(user: dict) -> dict:
    metadata = user.get("user_metadata") or {}
    return {
        "id": user.get("id", ""),
        "email": user.get("email") or metadata.get("email") or "",
        "name": metadata.get("full_name") or metadata.get("name") or "",
        "avatar": metadata.get("avatar_url") or metadata.get("picture") or "",
        "provider": (user.get("app_metadata") or {}).get("provider", ""),
        "created_at": user.get("created_at", ""),
    }


class AccountClient:
    def __init__(self, config: dict | None = None):
        config = load_config() if config is None else config
        if not configured(config):
            raise AccountError(t("account.not_configured"))
        self.url = config["SUPABASE_URL"].rstrip("/")
        self.key = config["SUPABASE_KEY"]

    def _call(self, path: str, payload=None, token: str | None = None, method: str | None = None,
              headers: dict | None = None):
        headers = {"apikey": self.key, "Content-Type": "application/json", **(headers or {})}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(self.url + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read()
                return json.loads(body) if body else None
        except urllib.error.HTTPError as error:
            body = error.read().decode(errors="replace")
            try:
                details = json.loads(body)
                message = details.get("msg") or details.get("error_description") or details.get("message") or body
            except ValueError:
                message = body
            raise AccountError(t("account.failed", code=error.code, message=message), error.code)
        except urllib.error.URLError as error:
            raise AccountError(t("account.connect_failed", reason=error.reason))

    def _store(self, session: dict) -> dict:
        """Keep the session of a login or refresh; return the profile."""
        _session["token"] = session["access_token"]
        _session["expires"] = time.time() + session.get("expires_in", 3600) - 60
        config = load_config()
        config["ACCOUNT_REFRESH_TOKEN"] = session["refresh_token"]
        config["ACCOUNT"] = _profile_of(session.get("user") or {})
        config.pop(SKIPPED_KEY, None)
        save_config(config)
        return config["ACCOUNT"]

    def login(self, timeout: int = 180) -> dict:
        """Log in with Google in the browser; return the profile."""
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        try:
            server, params = start_redirect_server(REDIRECT_PORT)
        except OSError:
            raise AccountError(t("account.port_in_use", port=REDIRECT_PORT))
        webbrowser.open(f"{self.url}/auth/v1/authorize?" + urllib.parse.urlencode({
            "provider": "google",
            "redirect_to": REDIRECT_URI,
            "code_challenge": challenge,
            "code_challenge_method": "s256",
        }))
        wait_for_redirect(server, params, timeout)
        if "error" in params:
            if params["error"] == "access_denied":
                raise AccountError(t("login.cancelled"))
            raise AccountError(t("account.login_failed", error=params.get("error_description") or params["error"]))
        if "code" not in params:
            raise AccountError(t("account.login_timeout", redirect_uri=REDIRECT_URI))
        session = self._call("/auth/v1/token?grant_type=pkce",
                             {"auth_code": params["code"], "code_verifier": verifier})
        with _session_lock:
            return self._store(session)

    def refresh(self) -> dict:
        """Renew the session and read the profile again from Supabase."""
        with _session_lock:
            refresh_token = load_config().get("ACCOUNT_REFRESH_TOKEN")
            if not refresh_token:
                raise AccountError(t("account.logged_out"))
            try:
                session = self._call("/auth/v1/token?grant_type=refresh_token", {"refresh_token": refresh_token})
            except AccountError as error:
                if error.status in (400, 401):
                    # The session was revoked or has expired: log out here too
                    self._forget()
                    raise AccountError(t("account.session_expired"), error.status)
                raise
            return self._store(session)

    def access_token(self) -> str:
        with _session_lock:
            if not _session["token"] or time.time() >= _session["expires"]:
                self.refresh()
            return _session["token"]

    def rest(self, method: str, path: str, payload=None, prefer: str | None = None):
        """A call to the database API (PostgREST) as the logged-in user, e.g. rest("GET", "plays?select=uid")."""
        headers = {"Prefer": prefer} if prefer else None
        try:
            return self._call(f"/rest/v1/{path}", payload, self.access_token(), method, headers)
        except AccountError as error:
            if error.status != 401:
                raise
            # The token ran out early (the computer slept): renew it once
            with _session_lock:
                _session["token"] = None
            return self._call(f"/rest/v1/{path}", payload, self.access_token(), method, headers)

    def logout(self) -> None:
        try:
            if load_config().get("ACCOUNT_REFRESH_TOKEN"):
                self._call("/auth/v1/logout", {}, self.access_token())
        except AccountError:
            pass  # logging out here matters more than telling Supabase
        finally:
            with _session_lock:
                self._forget()

    def _forget(self) -> None:
        _session["token"] = None
        config = load_config()
        config.pop("ACCOUNT_REFRESH_TOKEN", None)
        config.pop("ACCOUNT", None)
        save_config(config)


def skip() -> None:
    """Continue without an account; the login screen is not opened at start any more."""
    config = load_config()
    config[SKIPPED_KEY] = True
    save_config(config)


def ask_at_start(config: dict | None = None) -> bool:
    config = load_config() if config is None else config
    return configured(config) and not profile(config) and not config.get(SKIPPED_KEY)
