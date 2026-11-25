"""
Local web server that catches the browser's redirect at the end of a Spotify or Google login.
"""

from __future__ import annotations

import html
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

from playlist_tracker.core.i18n import current, t


_PAGE = """<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Songlog</title>
<style>
  /* The desktop app's colors (desktop/src/styles.css), light or dark as Windows is */
  :root {{ --bg: #d3d8e0; --surface: #e2e6ec; --border: #c3c9d2; --text: #1f2328; --muted: #555d6a;
           --ok: #1aa34a; --fail: #b42222; color-scheme: light dark; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg: #16181d; --surface: #1f2228; --border: #30343c; --text: #e6e8eb; --muted: #9aa1ac;
             --ok: #3fbf6a; --fail: #e05252; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; padding: 16px; background: var(--bg);
          color: var(--text); font: 15px/1.5 "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif; }}
  .card {{ width: 100%; max-width: 420px; padding: 40px 32px 32px; text-align: center; background: var(--surface);
           border: 1px solid var(--border); border-radius: 20px;
           box-shadow: 0 1px 2px rgb(0 0 0 / .06), 0 8px 32px rgb(0 0 0 / .08); animation: rise .45s ease-out; }}
  .mark {{ width: 72px; height: 72px; margin: 0 auto 20px; border-radius: 50%; display: grid; place-items: center;
           background: color-mix(in srgb, var(--accent) 16%, transparent); color: var(--accent); }}
  .mark svg {{ width: 36px; height: 36px; }}
  .mark path {{ stroke-dasharray: 40; stroke-dashoffset: 40; animation: draw .5s .25s ease-out forwards; }}
  h1 {{ margin: 0 0 8px; font-size: 22px; font-weight: 650; letter-spacing: -.2px; }}
  p {{ margin: 0; color: var(--muted); }}
  .app {{ margin-top: 28px; font-size: 13px; color: var(--muted); display: flex; gap: 8px; justify-content: center;
          align-items: center; }}
  .app svg {{ width: 16px; height: 16px; color: #1aa34a; }}
  @keyframes rise {{ from {{ opacity: 0; transform: translateY(8px); }} }}
  @keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}
  @media (prefers-reduced-motion: reduce) {{ .card, .mark path {{ animation: none; stroke-dashoffset: 0; }} }}
</style>
</head>
<body>
  <main class="card" style="--accent: var({accent})">
    <div class="mark"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"
      stroke-linecap="round" stroke-linejoin="round"><path d="{icon}"/></svg></div>
    <h1>{title}</h1>
    <p>{hint}</p>
    <div class="app"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M3 6h12v2H3zm0 4h12v2H3zm0 4h8v2H3zm14
      -8v8.2A3 3 0 1 0 19 17V8h3V6z"/></svg>Songlog</div>
  </main>
</body>
</html>"""


def result_page(success: bool) -> str:
    """The page the browser shows when a login comes back to the app."""
    key = "success" if success else "failed"
    return _PAGE.format(
        lang=current(),
        accent="--ok" if success else "--fail",
        icon="M5 12.5l4.5 4.5L19 7.5" if success else "M7 7l10 10M17 7L7 17",
        title=html.escape(t(f"redirect.{key}")),
        hint=html.escape(t(f"redirect.{key}_hint")),
    )


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
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(result_page("code" in params).encode("utf-8"))

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
