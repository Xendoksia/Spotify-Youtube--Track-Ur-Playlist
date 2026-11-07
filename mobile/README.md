# Playlist Tracker – mobile (Android)

The phone side of Playlist Tracker, in Flutter. It logs in with the same Google account as the desktop app and shows
what the desktop app synced to Supabase: listening statistics, tracked playlists and the changes their checks found.
The language and theme are shared with the desktop app. Recording plays on the phone itself comes later (M2 in
ROADMAP).

## Layout

```
lib/
  main.dart                 start: Supabase, date formats, settings
  app.dart                  MaterialApp, theme, language; login screen or the app
  config.dart               Supabase address and key (from config.json at build time), login redirect
  data/
    models.dart             Play, TrackedPlaylist, PlaylistEvent: the synced rows
    repository.dart         reads and writes Supabase
    stats.dart              statistics of a period (no Flutter, tested in test/stats_test.dart)
  state/
    app_controller.dart     language and theme (AppScope gives it to the widgets)
    data_store.dart         the loaded plays, playlists and events
  l10n/strings.dart         English and Turkish texts
  theme/palette.dart        the desktop app's colors
  screens/
    login_screen.dart
    home_screen.dart        bottom navigation
    listening/              statistics: period bar, chart, top lists, recent plays
    playlists/              tracked playlists and the history of one
    account_screen.dart     profile, devices, language and theme, log out
  widgets/                  cards, top lists, badges, number and date formats
test/                       unit tests of the statistics, widget tests of the screens
android/                    the Android project (manifest: internet, login redirect)
```

## Setup (once)

1. Flutter is in `C:\Users\Deniz\dev\flutter` (on the user PATH), Android Studio's Java is used for builds.
2. Accept the Android SDK licenses and install the platform tools, in a terminal:
   ```
   flutter doctor --android-licenses
   "%LOCALAPPDATA%\Android\Sdk\cmdline-tools\latest\bin\sdkmanager.bat" "platform-tools"
   flutter doctor
   ```
3. `config.json` next to this file holds `SUPABASE_URL` and `SUPABASE_KEY` (the publishable key, as in the desktop
   app's config.json; see `config.example.json`). It is kept out of git.
4. In Supabase: **Authentication → URL Configuration → Redirect URLs**, add
   `io.github.xendoksia.playlisttracker://login-callback`, or the browser cannot come back to the app after logging in.

## Test

Without a phone:

```
flutter analyze
flutter test
```

On the phone (Android, USB):

1. On the phone: Settings → About phone → tap *Build number* 7 times; then Developer options → *USB debugging* on.
2. Connect it with USB and allow the computer on the phone. `flutter devices` lists it.
3. `flutter run --dart-define-from-file=config.json` — builds, installs and opens the app. `r` in the terminal
   reloads code changes, `q` quits. The first build takes a few minutes.

Without a cable: `flutter build apk --dart-define-from-file=config.json`, copy
`build\app\outputs\flutter-apk\app-release.apk` to the phone and open it (allow installing unknown apps).

On an emulator instead: Android Studio → Device Manager → create a device, start it, then `flutter run` as above.

What to check: log in with Google; Listening shows the same numbers as the desktop app for the same period;
Playlists lists the tracked playlists with their latest changes and history; changing the language or theme in
Account changes the desktop app too within 5 minutes (and the other way round after pulling to refresh).
