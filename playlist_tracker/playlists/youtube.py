"""
YouTube client: reads playlists through the YouTube Data API, with an API key (public and unlisted playlists)
and/or a Google login (private playlists, "load my playlists"). Its history is kept apart from Spotify's,
in youtube_history.db, with the same comparison (see history.py).
"""

from __future__ import annotations

import base64
import hashlib
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

DB_PATH = BASE_DIR / "youtube_history.db"

API_URL = "https://www.googleapis.com/youtube/v3"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
PLAYLIST_URL = "https://www.youtube.com/playlist?list={}"


class YouTubeError(TrackerError):
    pass


class LoginRequired(YouTubeError):
    pass


def has_credentials(config: dict) -> bool:
    return bool(config.get("YOUTUBE_API_KEY")
                or (config.get("YOUTUBE_CLIENT_ID") and config.get("YOUTUBE_CLIENT_SECRET")))


def _error_details(body: str) -> tuple[str, str]:
    """Return (reason, message) from a Google API error body."""
    try:
        error = json.loads(body).get("error") or {}
    except ValueError:
        return "", body
    if isinstance(error, str):
        return error, body
    reasons = [e.get("reason", "") for e in error.get("errors") or []]
    return (reasons[0] if reasons else error.get("status", "")), error.get("message", body)


def _is_available(video: dict | None, region: str) -> int:
    """Deleted and private videos are not returned by videos.list at all."""
    if not video:
        return 0
    if (video.get("status") or {}).get("uploadStatus") in ("deleted", "failed", "rejected"):
        return 0
    restriction = (video.get("contentDetails") or {}).get("regionRestriction") or {}
    if "allowed" in restriction and region not in restriction["allowed"]:
        return 0
    return 0 if region in restriction.get("blocked", []) else 1


class YouTubeClient:
    def __init__(self, api_key: str | None, client_id: str | None, client_secret: str | None):
        self.api_key = api_key
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: str | None = None
        self._token_expires = 0.0

    def _request_token(self, payload: dict) -> dict:
        payload = {**payload, "client_id": self.client_id, "client_secret": self.client_secret}
        request = urllib.request.Request(TOKEN_URL, data=urllib.parse.urlencode(payload).encode())
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            body = error.read().decode(errors="replace")
            if "invalid_client" in body:
                raise YouTubeError(t("youtube.invalid_client"))
            if "invalid_grant" in body:
                config = load_config()
                config.pop("YOUTUBE_REFRESH_TOKEN", None)
                save_config(config)
                raise LoginRequired(t("youtube.session_expired"))
            raise YouTubeError(t("youtube.login_failed_code", code=error.code, body=body), error.code)
        except urllib.error.URLError as error:
            raise YouTubeError(t("youtube.connect_google_failed", reason=error.reason))

    def _store_token(self, data: dict) -> None:
        self._token = data["access_token"]
        self._token_expires = time.time() + data.get("expires_in", 3600) - 60

    def _access_token(self) -> str | None:
        """Return an OAuth access token, or None when not logged in (the API key is used then)."""
        if self._token and time.time() < self._token_expires:
            return self._token
        refresh_token = load_config().get("YOUTUBE_REFRESH_TOKEN")
        if not refresh_token or not (self.client_id and self.client_secret):
            return None
        self._store_token(self._request_token({"grant_type": "refresh_token", "refresh_token": refresh_token}))
        return self._token

    def login(self, timeout: int = 180) -> str:
        """Run the OAuth flow for installed apps (loopback redirect + PKCE) and store the session."""
        if not (self.client_id and self.client_secret):
            raise YouTubeError(t("youtube.needs_oauth"))
        state = secrets.token_urlsafe(16)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        server, params = start_redirect_server(0)
        redirect_uri = f"http://127.0.0.1:{server.server_address[1]}"
        webbrowser.open(AUTH_URL + "?" + urllib.parse.urlencode({
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": SCOPE,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "access_type": "offline",
            "prompt": "consent",
        }))
        wait_for_redirect(server, params, timeout)

        if "error" in params:
            if params["error"] == "access_denied":
                raise YouTubeError(t("youtube.login_cancelled"))
            raise YouTubeError(t("youtube.login_failed", error=params["error"]))
        if "code" not in params:
            raise YouTubeError(t("youtube.login_timeout"))
        if params.get("state") != state:
            raise YouTubeError(t("login.not_verified"))

        data = self._request_token({
            "grant_type": "authorization_code",
            "code": params["code"],
            "code_verifier": verifier,
            "redirect_uri": redirect_uri,
        })
        self._store_token(data)
        channels = self.get("/channels", {"part": "snippet", "mine": "true"}).get("items") or []
        config = load_config()
        config["YOUTUBE_REFRESH_TOKEN"] = data["refresh_token"]
        config["YOUTUBE_USER"] = channels[0]["snippet"]["title"] if channels else "Google account"
        save_config(config)
        return config["YOUTUBE_USER"]

    def get(self, path: str, params: dict, retries: int = 3) -> dict:
        for attempt in range(retries):
            token = self._access_token()
            query = dict(params)
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            elif self.api_key:
                query["key"] = self.api_key
            else:
                raise LoginRequired(t("youtube.login_first"))
            request = urllib.request.Request(f"{API_URL}{path}?{urllib.parse.urlencode(query)}", headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    return json.load(response)
            except urllib.error.HTTPError as error:
                if error.code in (429, 500, 503) and attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                reason, message = _error_details(error.read().decode(errors="replace"))
                if reason == "quotaExceeded":
                    raise YouTubeError(t("youtube.quota"), error.code)
                if reason in ("keyInvalid", "API_KEY_INVALID") or "API key not valid" in message:
                    raise YouTubeError(t("youtube.invalid_key"), error.code)
                if reason in ("accessNotConfigured", "SERVICE_DISABLED"):
                    raise YouTubeError(t("youtube.api_disabled"), error.code)
                if error.code == 401 and token:
                    self._token = None
                    raise LoginRequired(t("youtube.session_invalid"))
                raise YouTubeError(t("youtube.api_error", code=error.code, message=message), error.code) from error
            except urllib.error.URLError as error:
                raise YouTubeError(t("youtube.connect_failed", reason=error.reason))

    def _pages(self, path: str, params: dict):
        params = {**params, "maxResults": 50}
        while True:
            page = self.get(path, params)
            yield from page.get("items") or []
            if not page.get("nextPageToken"):
                return
            params["pageToken"] = page["nextPageToken"]

    def my_playlists(self) -> tuple[list[dict], list[dict]]:
        """Return (readable, others) like SpotifyClient; all own YouTube playlists are readable."""
        if not self._access_token():
            raise LoginRequired(t("youtube.load_needs_login"))
        playlists = [{
            "id": item["id"],
            "name": item["snippet"].get("title") or item["id"],
            "owner": item["snippet"].get("channelTitle") or "",
            "track_count": (item.get("contentDetails") or {}).get("itemCount", ""),
        } for item in self._pages("/playlists", {"part": "snippet,contentDetails", "mine": "true"})]
        return playlists, []

    def _keyless(self) -> bool:
        """Neither an API key nor a login: playlists are read from their page (PageReader)."""
        return not self.api_key and not self._access_token()

    def playlist_name(self, playlist_id: str) -> str:
        if self._keyless():
            return PageReader().playlist_name(playlist_id)
        items = self.get("/playlists", {"part": "snippet", "id": playlist_id}).get("items") or []
        if not items:
            raise YouTubeError(t("youtube.playlist_not_found"), 404)
        return items[0]["snippet"].get("title") or playlist_id

    def playlist_tracks(self, playlist_id: str) -> list[dict]:
        if self._keyless():
            return PageReader().playlist_tracks(playlist_id)
        try:
            items = list(self._pages("/playlistItems", {"part": "snippet", "playlistId": playlist_id}))
        except YouTubeError as error:
            if error.status == 403:
                raise YouTubeError(t("youtube.private"), 403)
            if error.status == 404:
                raise YouTubeError(t("playlist.not_found"), 404)
            raise

        video_ids = list(dict.fromkeys(
            v for v in ((i["snippet"].get("resourceId") or {}).get("videoId") for i in items) if v))
        videos = {}
        for start in range(0, len(video_ids), 50):
            batch = ",".join(video_ids[start:start + 50])
            for video in self.get("/videos", {"part": "status,contentDetails", "id": batch}).get("items") or []:
                videos[video["id"]] = video

        region = market()
        tracks = []
        for item in items:
            snippet = item["snippet"]
            video_id = (snippet.get("resourceId") or {}).get("videoId")
            if not video_id:
                continue
            tracks.append({
                # A playlist item id is unique per entry, so a removed and re-added video gets a new key
                "key": item["id"],
                "uri": video_id,
                "name": snippet.get("title") or "(untitled)",
                "artist": snippet.get("videoOwnerChannelTitle") or "",
                "album": "",
                "added_at": snippet.get("publishedAt") or "",
                "added_by": "",
                "playable": _is_available(videos.get(video_id), region),
            })
        return tracks


BROWSE_URL = "https://www.youtube.com/youtubei/v1/browse?prettyPrint=false"
# The website's own client; an older version keeps working for a long time
WEB_CLIENT = {"clientName": "WEB", "clientVersion": "2.20261119.07.00", "hl": "en"}
# Asks the playlist page to list unavailable videos too, which it otherwise hides
SHOW_UNAVAILABLE = "wgYCCAA%3D"


class PageReader:
    """Reads a public or unlisted playlist without an API key or a login, the way the YouTube website does. Used
    when neither is set up. The website gives no id per entry, so the video id is the key (a video in the playlist
    twice gets "#2"), and history.py matches it with the entries read through the API before."""

    def _browse(self, body: dict) -> dict:
        request = urllib.request.Request(
            BROWSE_URL, data=json.dumps({"context": {"client": {**WEB_CLIENT, "gl": market()}}, **body}).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise YouTubeError(t("youtube.api_error", code=error.code, message=error.reason), error.code)
        except urllib.error.URLError as error:
            raise YouTubeError(t("youtube.connect_failed", reason=error.reason))

    def _first_page(self, playlist_id: str) -> dict:
        data = self._browse({"browseId": f"VL{playlist_id}", "params": SHOW_UNAVAILABLE})
        if not (data.get("metadata") or {}).get("playlistMetadataRenderer"):
            # A private or deleted playlist comes back without its details, only an error alert
            raise YouTubeError(t("youtube.private_or_missing"), 404)
        return data

    def playlist_name(self, playlist_id: str) -> str:
        return self._first_page(playlist_id)["metadata"]["playlistMetadataRenderer"].get("title") or playlist_id

    def playlist_tracks(self, playlist_id: str) -> list[dict]:
        data = self._first_page(playlist_id)
        try:
            items = (data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"][0]["tabRenderer"]["content"]
                     ["sectionListRenderer"]["contents"][0]["itemSectionRenderer"]["contents"])
        except (KeyError, IndexError):
            items = []
        tracks: list[dict] = []
        seen: dict[str, int] = {}
        while items:
            following = None
            for item in items:
                if "continuationItemViewModel" in item or "continuationItemRenderer" in item:
                    following = _continuation_token(item)
                    continue
                track = _page_track(item.get("lockupViewModel") or {})
                if track is None:
                    continue
                seen[track["uri"]] = seen.get(track["uri"], 0) + 1
                if seen[track["uri"]] > 1:
                    track["key"] += f"#{seen[track['uri']]}"
                tracks.append(track)
            if not following:
                break
            more = self._browse({"continuation": following})
            items = [entry for action in more.get("onResponseReceivedActions") or []
                     for entry in (action.get("appendContinuationItemsAction") or {}).get("continuationItems") or []]
        return tracks


def _continuation_token(item) -> str | None:
    """The token for the next 100 videos, wherever the page puts its continuationCommand."""
    if isinstance(item, dict):
        command = item.get("continuationCommand")
        if isinstance(command, dict) and command.get("token"):
            return command["token"]
        children = item.values()
    elif isinstance(item, list):
        children = item
    else:
        return None
    for child in children:
        token = _continuation_token(child)
        if token:
            return token
    return None


def _page_track(lockup: dict) -> dict | None:
    """A video of the playlist page; one without a title is unavailable (deleted, private or blocked here)."""
    if lockup.get("contentType") != "LOCKUP_CONTENT_TYPE_VIDEO" or not lockup.get("contentId"):
        return None
    metadata = (lockup.get("metadata") or {}).get("lockupMetadataViewModel") or {}
    title = (metadata.get("title") or {}).get("content") or ""
    rows = ((metadata.get("metadata") or {}).get("contentMetadataViewModel") or {}).get("metadataRows") or []
    parts = [part["text"].get("content", "") for row in rows for part in row.get("metadataParts") or []
             if "text" in part]
    return {
        "key": lockup["contentId"], "uri": lockup["contentId"], "name": title or "(unavailable)",
        "artist": (parts[0] if parts and title else "").strip(), "album": "", "added_at": "", "added_by": "",
        "playable": int(bool(title)), "loose_key": True,
    }


def connect() -> YouTubeClient:
    config = load_config()
    return YouTubeClient(config.get("YOUTUBE_API_KEY"), config.get("YOUTUBE_CLIENT_ID"),
                         config.get("YOUTUBE_CLIENT_SECRET"))


def parse_playlist_id(link: str) -> str:
    link = link.strip()
    match = re.search(r"[?&]list=([A-Za-z0-9_-]+)", link)
    playlist_id = match.group(1) if match else link
    if playlist_id == "WL":
        raise YouTubeError(t("youtube.watch_later"))
    if playlist_id.startswith("RD"):
        raise YouTubeError(t("youtube.mix"))
    if re.fullmatch(r"(PL|UU|FL|LL|OL)[A-Za-z0-9_-]{8,}", playlist_id):
        return playlist_id
    raise YouTubeError(t("youtube.invalid_link", link=link))
