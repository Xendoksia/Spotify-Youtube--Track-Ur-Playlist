"""
YouTube playlist history tracker (client + command line).

Uses the same diff logic as tracker.py but keeps its history in a separate database,
youtube_history.db, so the Spotify history is never touched.

Command line usage:
    python youtube.py login                          Log in with your Google account (optional)
    python youtube.py check <playlist url> [...]     Check playlists and record changes
    python youtube.py history [playlist url]         Show the recorded change history
    python youtube.py export [file.csv]              Export the full history to CSV

Requires YOUTUBE_API_KEY (public and unlisted playlists) and/or YOUTUBE_CLIENT_ID and
YOUTUBE_CLIENT_SECRET (private playlists, "load my playlists") in config.json.
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

import tracker
from tracker import BASE_DIR, TrackerError, load_config, market, save_config

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
        if not api_key and not (client_id and client_secret):
            raise YouTubeError("No YouTube API key or OAuth client is set. Add one in Settings.")
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
                raise YouTubeError("Invalid Google OAuth Client ID / Client Secret. Check them in Settings.")
            if "invalid_grant" in body:
                config = load_config()
                config.pop("YOUTUBE_REFRESH_TOKEN", None)
                save_config(config)
                raise LoginRequired("Your Google session has expired. Please log in again.")
            raise YouTubeError(f"Google login failed ({error.code}): {body}", error.code)
        except urllib.error.URLError as error:
            raise YouTubeError(f"Could not connect to Google: {error.reason}")

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
            raise YouTubeError("Logging in needs a Google OAuth Client ID and Client Secret. Add them in Settings. "
                               "Public and unlisted playlists work with just the API key.")
        state = secrets.token_urlsafe(16)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        server, params = tracker.start_redirect_server(0)
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
        tracker.wait_for_redirect(server, params, timeout)

        if "error" in params:
            if params["error"] == "access_denied":
                raise YouTubeError("Login was cancelled. If your OAuth app is in testing mode, add your Google "
                                   "account as a test user on the OAuth consent screen.")
            raise YouTubeError(f"Google login failed: {params['error']}")
        if "code" not in params:
            raise YouTubeError("Login timed out. Make sure the OAuth client type is “Desktop app”.")
        if params.get("state") != state:
            raise YouTubeError("Login could not be verified. Please try again.")

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
                raise LoginRequired("Please log in with Google first, or add a YouTube API key in Settings.")
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
                    raise YouTubeError("The daily YouTube API quota is used up. Try again tomorrow.", error.code)
                if reason in ("keyInvalid", "API_KEY_INVALID") or "API key not valid" in message:
                    raise YouTubeError("Invalid YouTube API key. Check it in Settings.", error.code)
                if reason in ("accessNotConfigured", "SERVICE_DISABLED"):
                    raise YouTubeError("YouTube Data API v3 is not enabled in your Google Cloud project.", error.code)
                if error.code == 401 and token:
                    self._token = None
                    raise LoginRequired("Your Google session is no longer valid. Please log in again.")
                raise YouTubeError(f"YouTube API error {error.code}: {message}", error.code) from error
            except urllib.error.URLError as error:
                raise YouTubeError(f"Could not connect to YouTube: {error.reason}")

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
            raise LoginRequired("Log in with Google to load your own playlists. "
                                "Public and unlisted playlists can also be added by link.")
        playlists = [{
            "id": item["id"],
            "name": item["snippet"].get("title") or item["id"],
            "owner": item["snippet"].get("channelTitle") or "",
            "track_count": (item.get("contentDetails") or {}).get("itemCount", ""),
        } for item in self._pages("/playlists", {"part": "snippet,contentDetails", "mine": "true"})]
        return playlists, []

    def playlist_name(self, playlist_id: str) -> str:
        items = self.get("/playlists", {"part": "snippet", "id": playlist_id}).get("items") or []
        if not items:
            raise YouTubeError("Playlist not found. Is the link correct? Private playlists can only be read "
                               "after logging in with the Google account that owns them.", 404)
        return items[0]["snippet"].get("title") or playlist_id

    def playlist_tracks(self, playlist_id: str) -> list[dict]:
        try:
            items = list(self._pages("/playlistItems", {"part": "snippet", "playlistId": playlist_id}))
        except YouTubeError as error:
            if error.status == 403:
                raise YouTubeError("This playlist is private. Log in with the Google account that owns it.", 403)
            if error.status == 404:
                raise YouTubeError("Playlist not found. Is the link correct?", 404)
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


def connect() -> YouTubeClient:
    config = load_config()
    return YouTubeClient(config.get("YOUTUBE_API_KEY"), config.get("YOUTUBE_CLIENT_ID"),
                         config.get("YOUTUBE_CLIENT_SECRET"))


def parse_playlist_id(link: str) -> str:
    link = link.strip()
    match = re.search(r"[?&]list=([A-Za-z0-9_-]+)", link)
    playlist_id = match.group(1) if match else link
    if playlist_id == "WL":
        raise YouTubeError("“Watch later” cannot be read through the YouTube API.")
    if playlist_id.startswith("RD"):
        raise YouTubeError("YouTube Mixes are generated automatically and cannot be tracked.")
    if re.fullmatch(r"(PL|UU|FL|LL|OL)[A-Za-z0-9_-]{8,}", playlist_id):
        return playlist_id
    raise YouTubeError(f"Not a valid YouTube playlist link: {link}")


def main() -> None:
    tracker.run_cli(__doc__, connect, parse_playlist_id, DB_PATH, lambda: "Unavailable", "youtube_history.csv")


if __name__ == "__main__":
    main()
