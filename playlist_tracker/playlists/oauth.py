"""
Local web server that catches the browser's redirect at the end of a Spotify or Google login.
"""

from __future__ import annotations

import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

from playlist_tracker.core.i18n import t


def start_redirect_server(port: int) -> tuple[HTTPServer, dict]:
    """Start a local server that captures the OAuth redirect; port 0 picks a free port."""
    params: dict[str, str] = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            query = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).items()}
            if "code" not in query and "error" not in query:
                self.send_response(404)
                self.end_headers()
                return
            params.update(query)
            message = t("redirect.success") if "code" in params else t("redirect.failed")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<html><body style='font-family:sans-serif;padding:40px'>"
                             f"<h2>{message}</h2></body></html>".encode("utf-8"))

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", port), CallbackHandler)
    server.timeout = 1
    return server, params


def wait_for_redirect(server: HTTPServer, params: dict, timeout: int) -> None:
    deadline = time.time() + timeout
    try:
        while "code" not in params and "error" not in params and time.time() < deadline:
            server.handle_request()
    finally:
        server.server_close()
