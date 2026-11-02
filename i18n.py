"""
Interface translations (English and Turkish).

The language is read from LANGUAGE in config.json; when it is not set, the system
language is used. Look up texts with t("key", name=value, ...).
"""

from __future__ import annotations

import locale

LANGUAGES = {"en": "English", "tr": "Türkçe"}
DEFAULT_LANGUAGE = "en"

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "app.title": "Playlist Tracker",
        "status.ready": "Ready.",
        "button.settings": "⚙  Settings",
        "tab.history": "History",
        "nav.playlists": "Playlist tracking",
        "nav.listening": "Listening",

        "listening.recent_tab": "Recently played",
        "listening.track_toggle": "Record what Spotify plays on this computer",
        "listening.info": "Recorded plays: {count}",
        "listening.now.off": "Recording is off.",
        "listening.now.idle": "Nothing is playing in the Spotify app right now.",
        "listening.now.playing": "●  Playing: {track}  ·  {listened}",
        "listening.now.paused": "❚❚  Paused: {track}  ·  {listened}",
        "listening.now.recorded": "  ·  recorded ✓",
        "listening.now.error": "Could not read the Spotify app: {error}",
        "listening.column.played_at": "Played at",
        "listening.column.track": "Track",
        "listening.column.artist": "Artist",
        "listening.column.album": "Album",
        "listening.column.listened": "Listened",
        "listening.column.source": "Source",
        "listening.source.local": "This computer",
        "listening.source.spotify": "Spotify (earlier)",
        "stats.tab": "Statistics",
        "stats.hero.track": "Most played track",
        "stats.hero.artist": "Most played artist",
        "stats.period.week": "Week",
        "stats.period.month": "Month",
        "stats.period.year": "Year",
        "stats.period.all": "All time",
        "stats.all_time": "All time",
        "stats.tile.plays": "Plays",
        "stats.tile.time": "Listening time",
        "stats.tile.tracks": "Different tracks",
        "stats.tile.artists": "Different artists",
        "stats.vs.week": "vs. previous week",
        "stats.vs.month": "vs. previous month",
        "stats.vs.year": "vs. previous year",
        "stats.percent": "{value}%",
        "stats.top_tracks": "More top tracks",
        "stats.top_artists": "More top artists",
        "stats.per_day": "Plays per day",
        "stats.per_month": "Plays per month",
        "stats.per_year": "Plays per year",
        "stats.hours": "Plays by hour of day",
        "stats.empty": "No plays recorded in this period.",
        "stats.plays_one": "1 play",
        "stats.plays": "{count} plays",
        "stats.different_tracks_one": "1 different track",
        "stats.different_tracks": "{count} different tracks",
        "stats.minutes": "{minutes} min",
        "stats.hours_minutes": "{hours} h {minutes} min",
        "stats.months": "January,February,March,April,May,June,July,August,September,October,November,December",
        "stats.months_short": "Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec",
        "stats.weekdays": "Mon,Tue,Wed,Thu,Fri,Sat,Sun",

        "panel.load_playlists": "Load my {service} playlists",
        "panel.or_link": "or playlist link:",
        "panel.add": "Add",
        "panel.hint": "Tick the playlists you want to track, then press “Check selected”.",
        "panel.select_all": "Select all",
        "panel.clear_selection": "Clear selection",
        "panel.check": "▶  Check selected ({count})",
        "panel.last_result": "Last check result",
        "column.tracked": "Track",
        "column.playlist": "Playlist",
        "column.owner": "Owner",
        "column.tracks": "Tracks",
        "column.videos": "Videos",
        "column.last_checked": "Last checked",
        "items.tracks": "tracks",
        "items.videos": "videos",

        "login.logged_in": "● Logged in: {user}",
        "login.switch": "Switch account",
        "login.button": "Log in with {account}",
        "login.hint.spotify": "The Spotify authorization page opened in your browser, press “Agree”…",
        "login.hint.youtube": "The Google sign-in page opened in your browser, choose your account and allow access…",

        "status.logged_in": "Logged in to {service} as {user}",
        "status.loading": "Loading {service} playlists…",
        "status.found": "{count} {service} playlists found.",
        "status.hidden_others": " ({count} followed playlists by other users are hidden: "
                                "Spotify does not expose their tracks)",
        "status.fetching": "Fetching playlist info…",
        "status.now_tracked": "“{name}” is now tracked.",
        "status.checking": "Checking ({index}/{count}): {name}",
        "status.check_done": "Check complete: {count} playlists, {changes} changes.",
        "status.login_required": "Login required.",
        "status.error": "Error.",
        "status.exported": "{count} {service} records exported to {path}",
        "status.saved": "Settings saved.",

        "dialog.error": "Error",
        "dialog.nothing_selected": "Nothing selected",
        "dialog.nothing_selected.text": "Tick the playlists you want to track first.",
        "dialog.login_required": "Login required",
        "dialog.login_now": "{error}\n\nLog in now?",
        "error.unexpected": "Unexpected error: {error}",

        "result.error": "ERROR – {error}",
        "result.heading": "{name} ({total} {items}): ",
        "result.initial": "initial snapshot recorded, changes will appear from the next check on.",
        "result.no_changes": "no changes.",
        "result.changes": "{count} changes",
        "result.added": "   (added: {date})",

        "unavailable.spotify": "Not playable in {market}",
        "unavailable.youtube": "Unavailable (deleted, private or blocked in your region)",

        "event.ADDED": "+ Added",
        "event.REMOVED": "− Removed",
        "event.UNPLAYABLE": "! Unplayable",
        "event.PLAYABLE_AGAIN": "✓ Playable again",
        "event.INITIAL_SNAPSHOT": "• Initial snapshot",

        "history.source": "Source:",
        "history.playlist": "Playlist:",
        "history.event": "Event:",
        "history.all": "All",
        "history.export": "Export CSV",
        "history.refresh": "Refresh",
        "history.detected": "Detected",
        "history.event_column": "Event",
        "history.item": "Track / video",
        "history.added": "Added to playlist",
        "history.initial_count": "{count} items recorded",
        "history.note": "“Detected” is the time of the check that noticed the change. "
                        "The change happened between the previous check and this time.",

        "csv.filetype": "CSV (Excel)",
        "csv.checked_at": "Checked at",
        "csv.playlist": "Playlist",
        "csv.event": "Event",
        "csv.artist": "Artist",
        "csv.track": "Track",
        "csv.album": "Album",
        "csv.added": "Added to playlist",
        "csv.uri": "URI",

        "settings.title": "Settings",
        "settings.general": "General",
        "settings.language": "Language:",
        "settings.theme": "Theme:",
        "settings.restart_note": "Language and theme changes are applied when you save.",
        "settings.save": "Save",
        "settings.client_id": "Client ID:",
        "settings.client_secret": "Client Secret:",
        "settings.api_key": "API key:",
        "settings.oauth_client_id": "OAuth Client ID:",
        "settings.oauth_client_secret": "OAuth Client Secret:",
        "settings.spotify_steps": "1) Log in at developer.spotify.com/dashboard with your Spotify account\n"
                                  "2) “Create app” → enter a name, Redirect URI: {redirect_uri}\n"
                                  "3) Tick “Web API”, save → copy the Client ID and Client Secret from Settings",
        "settings.open_dashboard": "Open Dashboard",
        "settings.youtube_steps": "1) Open console.cloud.google.com, create a project and enable "
                                  "“YouTube Data API v3”\n"
                                  "2) Credentials → Create credentials → API key. This is enough for public and "
                                  "unlisted playlists.\n"
                                  "3) Optional, for private playlists and “Load my playlists”: set up the OAuth "
                                  "consent screen\n"
                                  "    (add your Google account as a test user), then Create credentials → "
                                  "OAuth client ID → Desktop app",
        "settings.open_console": "Open Google Cloud Console",
        "settings.missing": "Missing values",
        "settings.missing_pair": "Enter both the Client ID and the Client Secret.",
        "theme.system": "System default",
        "theme.light": "Light",
        "theme.dark": "Dark",

        "redirect.success": "Login complete. You can close this tab and return to the app.",
        "redirect.failed": "Login was cancelled or failed.",
        "login.cancelled": "Login was cancelled.",
        "login.not_verified": "Login could not be verified. Please try again.",
        "playlist.not_found": "Playlist not found. Is the link correct?",

        "spotify.no_credentials": "CLIENT_ID and CLIENT_SECRET are not set.",
        "spotify.invalid_client": "Invalid Client ID / Client Secret. Check them in Settings.",
        "spotify.session_expired": "Your Spotify session has expired. Please log in again.",
        "spotify.login_failed_code": "Spotify login failed ({code}): {body}",
        "spotify.login_failed": "Spotify login failed: {error}",
        "spotify.connect_failed": "Could not connect to Spotify: {reason}",
        "spotify.login_first": "Please log in with the “Log in with Spotify” button first.",
        "spotify.port_in_use": "Port 8888 is in use. Close any other open login window and try again.",
        "spotify.login_timeout": "Login timed out. If the authorization page did not open, make sure the "
                                 "Redirect URI in the Dashboard is exactly {redirect_uri}",
        "spotify.api_error": "Spotify API error {code}: {body}",
        "spotify.not_exposed": "Spotify does not expose the tracks of this playlist: only playlists you "
                               "own or collaborate on can be checked.",
        "spotify.invalid_link": "Not a valid Spotify playlist link: {link}",

        "youtube.no_credentials": "No YouTube API key or OAuth client is set. Add one in Settings.",
        "youtube.invalid_client": "Invalid Google OAuth Client ID / Client Secret. Check them in Settings.",
        "youtube.session_expired": "Your Google session has expired. Please log in again.",
        "youtube.login_failed_code": "Google login failed ({code}): {body}",
        "youtube.login_failed": "Google login failed: {error}",
        "youtube.connect_google_failed": "Could not connect to Google: {reason}",
        "youtube.needs_oauth": "Logging in needs a Google OAuth Client ID and Client Secret. Add them in "
                               "Settings. Public and unlisted playlists work with just the API key.",
        "youtube.login_cancelled": "Login was cancelled. If your OAuth app is in testing mode, add your Google "
                                   "account as a test user on the OAuth consent screen.",
        "youtube.login_timeout": "Login timed out. Make sure the OAuth client type is “Desktop app”.",
        "youtube.login_first": "Please log in with Google first, or add a YouTube API key in Settings.",
        "youtube.quota": "The daily YouTube API quota is used up. Try again tomorrow.",
        "youtube.invalid_key": "Invalid YouTube API key. Check it in Settings.",
        "youtube.api_disabled": "YouTube Data API v3 is not enabled in your Google Cloud project.",
        "youtube.session_invalid": "Your Google session is no longer valid. Please log in again.",
        "youtube.api_error": "YouTube API error {code}: {message}",
        "youtube.connect_failed": "Could not connect to YouTube: {reason}",
        "youtube.load_needs_login": "Log in with Google to load your own playlists. "
                                    "Public and unlisted playlists can also be added by link.",
        "youtube.playlist_not_found": "Playlist not found. Is the link correct? Private playlists can only be "
                                      "read after logging in with the Google account that owns them.",
        "youtube.private": "This playlist is private. Log in with the Google account that owns it.",
        "youtube.watch_later": "“Watch later” cannot be read through the YouTube API.",
        "youtube.mix": "YouTube Mixes are generated automatically and cannot be tracked.",
        "youtube.invalid_link": "Not a valid YouTube playlist link: {link}",
    },
    "tr": {
        "app.title": "Playlist Takipçisi",
        "status.ready": "Hazır.",
        "button.settings": "⚙  Ayarlar",
        "tab.history": "Geçmiş",
        "nav.playlists": "Playlist takibi",
        "nav.listening": "Dinleme",

        "listening.recent_tab": "Son dinlenenler",
        "listening.track_toggle": "Bu bilgisayarda Spotify'da çalanları kaydet",
        "listening.info": "Kayıtlı çalma: {count}",
        "listening.now.off": "Kayıt kapalı.",
        "listening.now.idle": "Spotify uygulamasında şu an bir şey çalmıyor.",
        "listening.now.playing": "●  Çalıyor: {track}  ·  {listened}",
        "listening.now.paused": "❚❚  Duraklatıldı: {track}  ·  {listened}",
        "listening.now.recorded": "  ·  kaydedildi ✓",
        "listening.now.error": "Spotify uygulaması okunamadı: {error}",
        "listening.column.played_at": "Çalınma zamanı",
        "listening.column.track": "Şarkı",
        "listening.column.artist": "Sanatçı",
        "listening.column.album": "Albüm",
        "listening.column.listened": "Dinlenen",
        "listening.column.source": "Kaynak",
        "listening.source.local": "Bu bilgisayar",
        "listening.source.spotify": "Spotify (önceki)",
        "stats.tab": "İstatistikler",
        "stats.hero.track": "En çok dinlenen şarkı",
        "stats.hero.artist": "En çok dinlenen sanatçı",
        "stats.period.week": "Hafta",
        "stats.period.month": "Ay",
        "stats.period.year": "Yıl",
        "stats.period.all": "Tüm zamanlar",
        "stats.all_time": "Tüm zamanlar",
        "stats.tile.plays": "Çalma",
        "stats.tile.time": "Dinleme süresi",
        "stats.tile.tracks": "Farklı şarkı",
        "stats.tile.artists": "Farklı sanatçı",
        "stats.vs.week": "önceki haftaya göre",
        "stats.vs.month": "önceki aya göre",
        "stats.vs.year": "önceki yıla göre",
        "stats.percent": "%{value}",
        "stats.top_tracks": "Diğer favori şarkılar",
        "stats.top_artists": "Diğer favori sanatçılar",
        "stats.per_day": "Günlere göre çalma",
        "stats.per_month": "Aylara göre çalma",
        "stats.per_year": "Yıllara göre çalma",
        "stats.hours": "Günün saatlerine göre çalma",
        "stats.empty": "Bu dönemde kayıtlı çalma yok.",
        "stats.plays_one": "1 çalma",
        "stats.plays": "{count} çalma",
        "stats.different_tracks_one": "1 farklı şarkı",
        "stats.different_tracks": "{count} farklı şarkı",
        "stats.minutes": "{minutes} dk",
        "stats.hours_minutes": "{hours} sa {minutes} dk",
        "stats.months": "Ocak,Şubat,Mart,Nisan,Mayıs,Haziran,Temmuz,Ağustos,Eylül,Ekim,Kasım,Aralık",
        "stats.months_short": "Oca,Şub,Mar,Nis,May,Haz,Tem,Ağu,Eyl,Eki,Kas,Ara",
        "stats.weekdays": "Pzt,Sal,Çar,Per,Cum,Cmt,Paz",

        "panel.load_playlists": "{service} listelerimi yükle",
        "panel.or_link": "veya liste linki:",
        "panel.add": "Ekle",
        "panel.hint": "Takip etmek istediğin listeleri işaretle, sonra “Seçilenleri kontrol et”e bas.",
        "panel.select_all": "Tümünü seç",
        "panel.clear_selection": "Seçimi temizle",
        "panel.check": "▶  Seçilenleri kontrol et ({count})",
        "panel.last_result": "Son kontrol sonucu",
        "column.tracked": "Takip",
        "column.playlist": "Liste",
        "column.owner": "Sahibi",
        "column.tracks": "Şarkı",
        "column.videos": "Video",
        "column.last_checked": "Son kontrol",
        "items.tracks": "şarkı",
        "items.videos": "video",

        "login.logged_in": "● Giriş yapıldı: {user}",
        "login.switch": "Hesap değiştir",
        "login.button": "{account} ile giriş yap",
        "login.hint.spotify": "Spotify yetkilendirme sayfası tarayıcında açıldı, “Kabul et”e bas…",
        "login.hint.youtube": "Google giriş sayfası tarayıcında açıldı, hesabını seç ve izin ver…",

        "status.logged_in": "{service} hesabına giriş yapıldı: {user}",
        "status.loading": "{service} listeleri yükleniyor…",
        "status.found": "{count} {service} listesi bulundu.",
        "status.hidden_others": " (başka kullanıcılara ait {count} takip edilen liste gizlendi: "
                                "Spotify bu listelerin şarkılarını vermiyor)",
        "status.fetching": "Liste bilgisi alınıyor…",
        "status.now_tracked": "“{name}” artık takip ediliyor.",
        "status.checking": "Kontrol ediliyor ({index}/{count}): {name}",
        "status.check_done": "Kontrol tamamlandı: {count} liste, {changes} değişiklik.",
        "status.login_required": "Giriş gerekli.",
        "status.error": "Hata.",
        "status.exported": "{count} {service} kaydı {path} dosyasına aktarıldı",
        "status.saved": "Ayarlar kaydedildi.",

        "dialog.error": "Hata",
        "dialog.nothing_selected": "Seçim yok",
        "dialog.nothing_selected.text": "Önce takip etmek istediğin listeleri işaretle.",
        "dialog.login_required": "Giriş gerekli",
        "dialog.login_now": "{error}\n\nŞimdi giriş yapılsın mı?",
        "error.unexpected": "Beklenmeyen hata: {error}",

        "result.error": "HATA – {error}",
        "result.heading": "{name} ({total} {items}): ",
        "result.initial": "ilk kayıt alındı, değişiklikler bir sonraki kontrolden itibaren görünecek.",
        "result.no_changes": "değişiklik yok.",
        "result.changes": "{count} değişiklik",
        "result.added": "   (eklenme: {date})",

        "unavailable.spotify": "{market} bölgesinde çalınamıyor",
        "unavailable.youtube": "Kullanılamıyor (silinmiş, gizli veya bölgende engelli)",

        "event.ADDED": "+ Eklendi",
        "event.REMOVED": "− Silindi",
        "event.UNPLAYABLE": "! Çalınamıyor",
        "event.PLAYABLE_AGAIN": "✓ Yeniden çalınabilir",
        "event.INITIAL_SNAPSHOT": "• İlk kayıt",

        "history.source": "Kaynak:",
        "history.playlist": "Liste:",
        "history.event": "Olay:",
        "history.all": "Tümü",
        "history.export": "CSV dışa aktar",
        "history.refresh": "Yenile",
        "history.detected": "Tespit",
        "history.event_column": "Olay",
        "history.item": "Şarkı / video",
        "history.added": "Listeye eklenme",
        "history.initial_count": "{count} öğe kaydedildi",
        "history.note": "“Tespit”, değişikliği fark eden kontrolün zamanıdır. "
                        "Değişiklik bir önceki kontrol ile bu zaman arasında olmuştur.",

        "csv.filetype": "CSV (Excel)",
        "csv.checked_at": "Kontrol zamanı",
        "csv.playlist": "Liste",
        "csv.event": "Olay",
        "csv.artist": "Sanatçı",
        "csv.track": "Şarkı",
        "csv.album": "Albüm",
        "csv.added": "Listeye eklenme",
        "csv.uri": "URI",

        "settings.title": "Ayarlar",
        "settings.general": "Genel",
        "settings.language": "Dil:",
        "settings.theme": "Tema:",
        "settings.restart_note": "Dil ve tema değişiklikleri kaydettiğinde uygulanır.",
        "settings.save": "Kaydet",
        "settings.client_id": "Client ID:",
        "settings.client_secret": "Client Secret:",
        "settings.api_key": "API anahtarı:",
        "settings.oauth_client_id": "OAuth Client ID:",
        "settings.oauth_client_secret": "OAuth Client Secret:",
        "settings.spotify_steps": "1) developer.spotify.com/dashboard adresine Spotify hesabınla giriş yap\n"
                                  "2) “Create app” → bir isim gir, Redirect URI: {redirect_uri}\n"
                                  "3) “Web API”yi işaretle, kaydet → Settings'ten Client ID ve Client Secret'ı kopyala",
        "settings.open_dashboard": "Dashboard'u aç",
        "settings.youtube_steps": "1) console.cloud.google.com'u aç, bir proje oluştur ve "
                                  "“YouTube Data API v3”ü etkinleştir\n"
                                  "2) Credentials → Create credentials → API key. Herkese açık ve liste dışı "
                                  "listeler için bu yeterli.\n"
                                  "3) İsteğe bağlı, gizli listeler ve “Listelerimi yükle” için: OAuth consent "
                                  "screen'i ayarla\n"
                                  "    (Google hesabını test kullanıcısı olarak ekle), sonra Create credentials → "
                                  "OAuth client ID → Desktop app",
        "settings.open_console": "Google Cloud Console'u aç",
        "settings.missing": "Eksik bilgi",
        "settings.missing_pair": "Client ID ve Client Secret'ın ikisini de gir.",
        "theme.system": "Sistem varsayılanı",
        "theme.light": "Açık",
        "theme.dark": "Koyu",

        "redirect.success": "Giriş tamamlandı. Bu sekmeyi kapatıp uygulamaya dönebilirsin.",
        "redirect.failed": "Giriş iptal edildi veya başarısız oldu.",
        "login.cancelled": "Giriş iptal edildi.",
        "login.not_verified": "Giriş doğrulanamadı. Lütfen tekrar dene.",
        "playlist.not_found": "Liste bulunamadı. Link doğru mu?",

        "spotify.no_credentials": "CLIENT_ID ve CLIENT_SECRET ayarlanmamış.",
        "spotify.invalid_client": "Client ID / Client Secret geçersiz. Ayarlar'dan kontrol et.",
        "spotify.session_expired": "Spotify oturumunun süresi doldu. Lütfen tekrar giriş yap.",
        "spotify.login_failed_code": "Spotify girişi başarısız ({code}): {body}",
        "spotify.login_failed": "Spotify girişi başarısız: {error}",
        "spotify.connect_failed": "Spotify'a bağlanılamadı: {reason}",
        "spotify.login_first": "Önce “Spotify ile giriş yap” butonuyla giriş yap.",
        "spotify.port_in_use": "8888 portu kullanımda. Açık kalan başka bir giriş penceresini kapatıp tekrar dene.",
        "spotify.login_timeout": "Giriş zaman aşımına uğradı. Yetkilendirme sayfası açılmadıysa Dashboard'daki "
                                 "Redirect URI'nin tam olarak {redirect_uri} olduğundan emin ol",
        "spotify.api_error": "Spotify API hatası {code}: {body}",
        "spotify.not_exposed": "Spotify bu listenin şarkılarını vermiyor: yalnızca sahibi olduğun veya ortak "
                               "çalıştığın listeler kontrol edilebilir.",
        "spotify.invalid_link": "Geçerli bir Spotify liste linki değil: {link}",

        "youtube.no_credentials": "YouTube API anahtarı veya OAuth istemcisi ayarlanmamış. Ayarlar'dan ekle.",
        "youtube.invalid_client": "Google OAuth Client ID / Client Secret geçersiz. Ayarlar'dan kontrol et.",
        "youtube.session_expired": "Google oturumunun süresi doldu. Lütfen tekrar giriş yap.",
        "youtube.login_failed_code": "Google girişi başarısız ({code}): {body}",
        "youtube.login_failed": "Google girişi başarısız: {error}",
        "youtube.connect_google_failed": "Google'a bağlanılamadı: {reason}",
        "youtube.needs_oauth": "Giriş için Google OAuth Client ID ve Client Secret gerekli. Ayarlar'dan ekle. "
                               "Herkese açık ve liste dışı listeler yalnızca API anahtarıyla da çalışır.",
        "youtube.login_cancelled": "Giriş iptal edildi. OAuth uygulaman test modundaysa Google hesabını OAuth "
                                   "consent screen'de test kullanıcısı olarak ekle.",
        "youtube.login_timeout": "Giriş zaman aşımına uğradı. OAuth istemci türünün “Desktop app” olduğundan emin ol.",
        "youtube.login_first": "Önce Google ile giriş yap veya Ayarlar'dan bir YouTube API anahtarı ekle.",
        "youtube.quota": "Günlük YouTube API kotası doldu. Yarın tekrar dene.",
        "youtube.invalid_key": "YouTube API anahtarı geçersiz. Ayarlar'dan kontrol et.",
        "youtube.api_disabled": "Google Cloud projende YouTube Data API v3 etkin değil.",
        "youtube.session_invalid": "Google oturumun artık geçerli değil. Lütfen tekrar giriş yap.",
        "youtube.api_error": "YouTube API hatası {code}: {message}",
        "youtube.connect_failed": "YouTube'a bağlanılamadı: {reason}",
        "youtube.load_needs_login": "Kendi listelerini yüklemek için Google ile giriş yap. "
                                    "Herkese açık ve liste dışı listeleri linkle de ekleyebilirsin.",
        "youtube.playlist_not_found": "Liste bulunamadı. Link doğru mu? Gizli listeler yalnızca sahibi olan "
                                      "Google hesabıyla giriş yapıldıktan sonra okunabilir.",
        "youtube.private": "Bu liste gizli. Listenin sahibi olan Google hesabıyla giriş yap.",
        "youtube.watch_later": "“Daha sonra izle” listesi YouTube API üzerinden okunamıyor.",
        "youtube.mix": "YouTube Mix'leri otomatik oluşturulur ve takip edilemez.",
        "youtube.invalid_link": "Geçerli bir YouTube liste linki değil: {link}",
    },
}

_language: str | None = None


def system_language() -> str:
    name = (locale.getlocale()[0] or "").lower()
    return "tr" if name.startswith(("tr", "turkish")) else DEFAULT_LANGUAGE


def current() -> str:
    global _language
    if _language is None:
        import tracker  # imported here because tracker itself uses t()
        _language = tracker.load_config().get("LANGUAGE") or system_language()
        if _language not in LANGUAGES:
            _language = DEFAULT_LANGUAGE
    return _language


def set_language(code: str | None) -> None:
    global _language
    _language = code if code in LANGUAGES else None


def number(value: int) -> str:
    """Format a whole number with the thousands separator of the current language."""
    text = f"{value:,}"
    return text.replace(",", ".") if current() == "tr" else text


def t(key: str, **values) -> str:
    text = STRINGS[current()].get(key) or STRINGS[DEFAULT_LANGUAGE][key]
    return text.format(**values) if values else text
