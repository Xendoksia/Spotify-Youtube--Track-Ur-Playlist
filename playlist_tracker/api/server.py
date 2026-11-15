"""
A small JSON API on 127.0.0.1 for the desktop window (desktop/, Electron). Every request carries the token
the window was started with, as an X-Token header or a token query parameter (for images), so web pages
open in a browser cannot read the listening history.
"""

from __future__ import annotations

import json
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlparse

from playlist_tracker.api import overview
from playlist_tracker.core import i18n
from playlist_tracker.core.config import load_config
from playlist_tracker.music import artwork


class Api:
    """The routes; recording is None in a window started while another copy records."""

    def __init__(self, token: str, recording: dict | None):
        self.token = token
        # {"enabled": () -> bool, "set": (bool) -> None}
        self.recording = recording
        self.routes: dict[tuple[str, str], Callable[[dict, dict], object]] = {
            ("GET", "/api/app"): self.app,
            ("GET", "/api/overview"): self.overview,
            ("GET", "/api/recording"): self.get_recording,
            ("POST", "/api/recording"): self.set_recording,
        }

    def app(self, query, body):
        """The interface texts in the chosen language and the chosen theme ("system", "light" or "dark")."""
        language = i18n.current()
        theme = load_config().get("THEME")
        return {"language": language, "theme": theme if theme in ("light", "dark") else "system",
                "strings": {**i18n.STRINGS[i18n.DEFAULT_LANGUAGE], **i18n.STRINGS[language]}}

    def overview(self, query, body):
        return overview.overview(query.get("period", "week"), int(query.get("offset", 0)))

    def get_recording(self, query, body):
        if self.recording is None:
            return {"available": False, "enabled": False}
        return {"available": True, "enabled": self.recording["enabled"]()}

    def set_recording(self, query, body):
        if self.recording is not None:
            self.recording["set"](bool(body.get("enabled")))
        return self.get_recording(query, body)

    def image(self, path: str, query: dict) -> Path | None:
        if path == "/api/cover":
            return artwork.fetch_cover(query.get("artist", ""), query.get("album", ""), query.get("name", ""))
        if path == "/api/artist-photo":
            return artwork.fetch_artist(query.get("name", ""))
        return None


def handler_for(api: Api):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # stdout carries the events to the window
            pass

        def _allowed(self, query: dict) -> bool:
            return api.token in (self.headers.get("X-Token"), query.get("token"))

        def _send(self, status: int, data: bytes, content_type: str, cache: bool = False):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            if cache:
                self.send_header("Cache-Control", "max-age=86400")
            self.end_headers()
            self.wfile.write(data)

        def _json(self, status: int, value):
            self._send(status, json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json")

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "X-Token, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST")
            self.end_headers()

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

        def _handle(self, method: str):
            url = urlparse(self.path)
            query = {k: v[0] for k, v in parse_qs(url.query).items()}
            if not self._allowed(query):
                return self._json(403, {"error": "forbidden"})
            if method == "GET" and url.path in ("/api/cover", "/api/artist-photo"):
                path = api.image(url.path, query)
                if path is None:
                    return self._send(404, b"", "image/jpeg")
                return self._send(200, path.read_bytes(), "image/jpeg", cache=True)
            route = api.routes.get((method, url.path))
            if route is None:
                return self._json(404, {"error": "not found"})
            body = {}
            if method == "POST":
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}") if length else {}
            try:
                self._json(200, route(query, body))
            except (ValueError, KeyError) as error:
                self._json(400, {"error": str(error)})
            except Exception:
                traceback.print_exc()
                self._json(500, {"error": "internal"})

    return Handler


def start(api: Api) -> ThreadingHTTPServer:
    """Serve on a free port of 127.0.0.1 on a background thread; the port is server.server_address[1]."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(api))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, name="api", daemon=True).start()
    return server
