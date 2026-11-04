"""
Spotify client: logs in with the user's account and reads their playlists and the tracks in them.
The history of the checks is kept in history.db (see history.py).
"""

from __future__ import annotations

import base64
import json
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

from playlist_tracker.core.config import BASE_DIR, load_config, market, save_config
from playlist_tracker.core.errors import TrackerError
from playlist_tracker.core.i18n import t
from playlist_tracker.playlists.oauth import start_redirect_server, wait_for_redirect

DB_PATH = BASE_DIR / "history.db"
REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPES = "playlist-read-private playlist-read-collaborative"
API_URL = "https://api.spotify.com/v1"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"


class SpotifyError(TrackerError):
    pass


class LoginRequired(SpotifyError):
    pass


class SpotifyClient:
    def __init__(self, client_id: str | None, client_secret: str | None):
        if not client_id or not client_secret:
            raise SpotifyError(t("spotify.no_credentials"))
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: str | None = None
        self._token_expires = 0.0

    def _request_token(self, payload: dict) -> dict:
        credentials = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        request = urllib.request.Request(
            TOKEN_URL,
            data=urllib.parse.urlencode(payload).encode(),
            headers={"Authorization": f"Basic {credentials}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            body = error.read().decode(errors="replace")
            if "invalid_client" in body:
                raise SpotifyError(t("spotify.invalid_client"))
            if "invalid_grant" in body:
                config = load_config()
                config.pop("REFRESH_TOKEN", None)
                save_config(config)
                raise LoginRequired(t("spotify.session_expired"))
            raise SpotifyError(t("spotify.login_failed_code", code=error.code, body=body), error.code)
        except urllib.error.URLError as error:
            raise SpotifyError(t("spotify.connect_failed", reason=error.reason))

    def _store_token(self, data: dict) -> None:
        self._token = data["access_token"]
        self._token_expires = time.time() + data.get("expires_in", 3600) - 60

    def _access_token(self) -> str:
        if self._token and time.time() < self._token_expires:
            return self._token
        config = load_config()
        refresh_token = config.get("REFRESH_TOKEN")
        if not refresh_token:
            raise LoginRequired(t("spotify.login_first"))
        data = self._request_token({"grant_type": "refresh_token", "refresh_token": refresh_token})
        if data.get("refresh_token") and data["refresh_token"] != refresh_token:
            config["REFRESH_TOKEN"] = data["refresh_token"]
            save_config(config)
        self._store_token(data)
        return self._token

    def login(self, timeout: int = 180) -> str:
        """Run the OAuth authorization code flow through the browser and store the session."""
        state = secrets.token_urlsafe(16)
        try:
            server, params = start_redirect_server(8888)
        except OSError:
            raise SpotifyError(t("spotify.port_in_use"))
        webbrowser.open(AUTH_URL + "?" + urllib.parse.urlencode({
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
            "state": state,
        }))
        wait_for_redirect(server, params, timeout)

        if "error" in params:
            if params["error"] == "access_denied":
                raise SpotifyError(t("login.cancelled"))
            raise SpotifyError(t("spotify.login_failed", error=params["error"]))
        if "code" not in params:
            raise SpotifyError(t("spotify.login_timeout", redirect_uri=REDIRECT_URI))
        if params.get("state") != state:
            raise SpotifyError(t("login.not_verified"))

        data = self._request_token({
            "grant_type": "authorization_code",
            "code": params["code"],
            "redirect_uri": REDIRECT_URI,
        })
        self._store_token(data)
        me = self.get("/me")
        config = load_config()
        config["REFRESH_TOKEN"] = data["refresh_token"]
        config["USER"] = me.get("display_name") or me.get("id")
        save_config(config)
        return config["USER"]

    def get(self, url: str, retries: int = 3) -> dict:
        if not url.startswith("http"):
            url = API_URL + url
        for attempt in range(retries):
            request = urllib.request.Request(url, headers={"Authorization": f"Bearer {self._access_token()}"})
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    return json.load(response)
            except urllib.error.HTTPError as error:
                if error.code == 429 and attempt < retries - 1:
                    time.sleep(int(error.headers.get("Retry-After", "2")))
                    continue
                body = error.read().decode(errors="replace")
                raise SpotifyError(t("spotify.api_error", code=error.code, body=body), error.code) from error
            except urllib.error.URLError as error:
                raise SpotifyError(t("spotify.connect_failed", reason=error.reason))

    def my_playlists(self) -> tuple[list[dict], list[dict]]:
        """Return (readable, others) playlists of the logged-in user.

        Spotify only exposes tracks of playlists the user owns or collaborates on,
        so followed playlists of other users are returned separately.
        """
        me = self.get("/me")
        readable, others = [], []
        url = "/me/playlists?limit=50"
        while url:
            page = self.get(url)
            for item in page.get("items") or []:
                if not item or not item.get("id"):
                    continue
                owner = item.get("owner") or {}
                total = (item.get("items") or item.get("tracks") or {}).get("total")
                playlist = {
                    "id": item["id"],
                    "name": item.get("name") or item["id"],
                    "owner": owner.get("display_name") or owner.get("id") or "",
                    "track_count": total if total is not None else "",
                }
                is_readable = owner.get("id") == me.get("id") or item.get("collaborative")
                (readable if is_readable else others).append(playlist)
            url = page.get("next")
        return readable, others

    def playlist_name(self, playlist_id: str) -> str:
        try:
            return self.get(f"/playlists/{playlist_id}?fields=name").get("name") or playlist_id
        except SpotifyError as error:
            if error.status == 404:
                raise SpotifyError(t("playlist.not_found"), 404)
            raise

    def playlist_tracks(self, playlist_id: str) -> list[dict]:
        query = urllib.parse.urlencode({"limit": 100, "market": market()})
        try:
            page = self.get(f"/playlists/{playlist_id}/items?{query}")
        except SpotifyError as error:
            if error.status == 403:
                raise SpotifyError(t("spotify.not_exposed"), 403)
            raise
        tracks = []
        while True:
            for entry in page.get("items") or []:
                track = entry.get("track") or entry.get("item")
                if not track or not track.get("uri"):
                    continue
                tracks.append({
                    # added_at changes when a track is removed and re-added, so it is part of the key
                    "key": f"{track['uri']}|{entry.get('added_at')}",
                    "uri": track["uri"],
                    "name": track.get("name") or "(untitled)",
                    "artist": ", ".join(a["name"] for a in track.get("artists") or [] if a.get("name")),
                    "album": (track.get("album") or {}).get("name") or "",
                    "added_at": entry.get("added_at") or "",
                    "added_by": (entry.get("added_by") or {}).get("id") or "",
                    "playable": 0 if track.get("is_playable") is False else 1,
                })
            if not page.get("next"):
                return tracks
            page = self.get(page["next"])


def connect() -> SpotifyClient:
    config = load_config()
    return SpotifyClient(config.get("CLIENT_ID"), config.get("CLIENT_SECRET"))


def parse_playlist_id(link: str) -> str:
    match = re.search(r"playlist[/:]([A-Za-z0-9]{22})", link)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9]{22}", link.strip()):
        return link.strip()
    raise SpotifyError(t("spotify.invalid_link", link=link))
