# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

(Desktop app built with Electron + React + TypeScript in `desktop/`, Windows only, with a Python backend. A Flutter phone app in `mobile/` mirrors it.)

## Users
One person, the owner, keeps their own Spotify and YouTube playlists and their own listening. They open the desktop app at their PC through the day. On the playlist tracking page they want to know what changed in their playlists since the last check.

## Product Purpose
Playlist Tracker watches chosen Spotify and YouTube playlists and records every change: a track added, a track removed, a track turned unplayable or playable again. It also records the user's own listening and turns it into statistics, Wrapped, and discovery suggestions. Success on the tracking page is seeing the last check's changes at first glance.

## Positioning
Spotify and YouTube show a playlist as it is now. They forget what left it. This app keeps the full history of each tracked playlist, from the first snapshot onward, on the user's own machine and synced to their phone.

## Operating Context
- Checks run in the backend one at a time and can also run automatically. Progress shows as a status line, and the card of the playlist being compared shows that state.
- Each service needs its own login. Without API details, the service's settings tab opens.
- The history can be filtered by playlist and by event kind and saved as CSV.

## Capabilities and Constraints
- Services: Spotify and YouTube. Each playlist can be tracked or not, and playlists can be loaded from the account or added by link.
- Event kinds: added, removed, unplayable, playable, initial snapshot.
- Interface texts are Turkish and English (i18n). App texts never use semicolons and stay short.
- Light and dark themes both follow Windows or the user's setting.
- The target machine has an Intel GPU, so window-sized fades and full-page motion must be avoided.
- Open: the user did not say which job they do most on the tracking page besides seeing the changes.

## Brand Commitments
- Name: Playlist Tracker. Font: Segoe UI Variable, with Segoe Fluent Icons for icons.
- Every page keeps the app's shared theme: the tokens in `desktop/src/styles.css` (light and dark), Segoe UI, the cards and heroes the other pages use. A redesign changes a page's structure, never its theme (user, 2026-11-24).

## Evidence on Hand
- Real data lives in `%APPDATA%/Playlist Tracker` (`history.db`, `listening.db`). As of 2026-11-24 it holds 6 Spotify playlists, 2 of them tracked ("Xen's Chillin Temple", 160 tracks, and "Xen's Car Musics", 279 tracks), 18 added, 7 removed and 5 initial snapshot events.
- Album covers come from Spotify and Deezer through the artwork cache.

## Product Principles
1. Change first. What moved since the last check leads, and the inventory follows.
2. The record is the product. Nothing that left a playlist is forgotten.
3. One owner, one machine. The data stays personal and on the device.
4. Calm while working. Checks run in the background without blocking the page.
