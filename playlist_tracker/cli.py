"""
Command line, for using the trackers without the window (see cli.py next to app.py).

    python cli.py spotify login                          Log in with your Spotify account (once)
    python cli.py spotify check <playlist url> [...]     Check playlists and record changes
    python cli.py spotify history [playlist url]         Show the recorded change history
    python cli.py spotify export [file.csv]              Export the full history to CSV

    python cli.py youtube login|check|history|export     The same for YouTube playlists

    python cli.py listening recent                       Show the last recorded plays
    python cli.py listening stats [week|month|year|all]  Show the most played tracks and artists

Playlist commands need config.json with CLIENT_ID and CLIENT_SECRET for Spotify, or YOUTUBE_API_KEY
and/or YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET for YouTube (see config.example.json).
"""

from __future__ import annotations

import sys
from datetime import timedelta

from playlist_tracker.core.config import market
from playlist_tracker.core.errors import TrackerError
from playlist_tracker.core.i18n import t
from playlist_tracker.core.text import format_date, track_label
from playlist_tracker.music import listening
from playlist_tracker.playlists import history, spotify, youtube


def print_result(result: dict, unavailable_label: str) -> None:
    print(f"Playlist: {result['name']}  ({result['total']} items)")
    if result["first_check"]:
        print("Initial snapshot recorded. Changes will be tracked from the next check on.")
        for track in result["unavailable"]:
            print(f"   ! {unavailable_label}: {track_label(track)}")
        return
    if not any(result[k] for k in ("added", "removed", "unplayable", "playable_again")):
        print("No changes.")
    for track in result["added"]:
        print(f"  + ADDED        {track_label(track)}   (added: {format_date(track['added_at'])})")
    for track in result["removed"]:
        print(f"  - REMOVED      {track_label(track)}   (added: {format_date(track['added_at'])}, "
              f"last seen: {format_date(track['last_seen'])})")
    for track in result["unplayable"]:
        print(f"  ! UNPLAYABLE   {track_label(track)}")
    for track in result["playable_again"]:
        print(f"  ✓ PLAYABLE      {track_label(track)}")


def run_playlists(command: str, args: list[str], service) -> None:
    """The same commands for the Spotify and YouTube trackers; service is the spotify or youtube module."""
    if service is spotify:
        unavailable_label, default_csv = t("unavailable.spotify", market=market()), "history.csv"
    else:
        unavailable_label, default_csv = t("unavailable.youtube"), "youtube_history.csv"
    if command == "login":
        print(f"Logged in as: {service.connect().login()}")
    elif command == "check" and args:
        client = service.connect()
        for link in args:
            print_result(history.check_playlist(client, service.parse_playlist_id(link), service.DB_PATH),
                         unavailable_label)
    elif command == "history":
        playlist_id = service.parse_playlist_id(args[0]) if args else None
        for r in reversed(history.get_events(playlist_id, service.DB_PATH)):
            added = f"  (added: {format_date(r['added_at'])})" if r["added_at"] else ""
            print(f"{format_date(r['checked_at'])}  [{r['playlist']}]  {r['event']:<18} {track_label(r)}{added}")
    elif command == "export":
        path = args[0] if args else default_csv
        print(f"{history.export_csv(path, service.DB_PATH)} records written to '{path}'.")
    else:
        print(__doc__)


def run_listening(command: str, args: list[str]) -> None:
    if command == "recent":
        for p in reversed(listening.recent_plays(30)):
            print(f"{format_date(p['played_at'])}  [{p['source']}]  {track_label(p)}")
    elif command == "stats" and (not args or args[0] in listening.PERIODS):
        start, end = listening.period_range(args[0] if args else "week")
        s = listening.summary(start, end)
        print(f"{start:%Y-%m-%d} – {end - timedelta(seconds=1):%Y-%m-%d}: {s['plays']} plays, "
              f"{s['minutes']} minutes, {s['tracks']} tracks, {s['artists']} artists\n")
        print("Top tracks:")
        for i, r in enumerate(listening.top_tracks(start, end), 1):
            print(f"  {i:>2}. {r['plays']:>4}×  {track_label(r)}")
        print("\nTop artists:")
        for i, r in enumerate(listening.top_artists(start, end), 1):
            print(f"  {i:>2}. {r['plays']:>4}×  {r['name']}")
    else:
        print(__doc__)


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        return
    section, command, args = sys.argv[1].lower(), sys.argv[2].lower(), sys.argv[3:]
    try:
        if section in ("spotify", "youtube"):
            run_playlists(command, args, spotify if section == "spotify" else youtube)
        elif section == "listening":
            run_listening(command, args)
        else:
            print(__doc__)
    except TrackerError as error:
        sys.exit(str(error))
