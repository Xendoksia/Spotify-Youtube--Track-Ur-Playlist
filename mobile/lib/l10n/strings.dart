/// Texts in English and Turkish, the desktop app's two languages. The language follows the account's setting
/// (chosen on any device), else the phone's.
library;

import 'package:flutter/widgets.dart';

import '../state/app_controller.dart';

const languages = {'en': 'English', 'tr': 'Türkçe'};

const _strings = <String, Map<String, String>>{
  'en': {
    'app.title': 'Playlist Tracker',
    'login.lead': 'Log in with the account you use in the desktop app to see your plays and playlists here.',
    'login.google': 'Log in with Google',
    'login.failed': 'Could not log in: {error}',
    'login.not_configured': 'The app was built without the Supabase settings. Run it with '
        '--dart-define-from-file=config.json (see mobile/README.md).',
    'nav.listening': 'Listening',
    'nav.playlists': 'Playlists',
    'nav.account': 'Account',
    'load.failed': 'Could not load: {error}',
    'load.retry': 'Try again',
    'period.week': 'Week',
    'period.month': 'Month',
    'period.year': 'Year',
    'period.all': 'All time',
    'period.this_week': 'This week',
    'period.all_time': 'All time',
    'stats.plays': 'Plays',
    'stats.time': 'Listening time',
    'stats.tracks': 'Tracks',
    'stats.artists': 'Artists',
    'stats.chart': 'Minutes listened',
    'stats.top_tracks': 'Top tracks',
    'stats.top_artists': 'Top artists',
    'stats.top_albums': 'Top albums',
    'stats.recent': 'Recently played',
    'stats.empty': 'No plays in this period.',
    'stats.none_yet': 'No plays yet. Plays recorded by the desktop app appear here after it syncs.',
    'stats.plays_count': '{count} plays',
    'stats.change.new': 'NEW',
    'minutes': '{minutes} min',
    'hours': '{hours} h {minutes} min',
    'day.today': 'Today',
    'day.yesterday': 'Yesterday',
    'playlists.empty': 'No tracked playlists yet. Track playlists in the desktop app; they appear here after it '
        'syncs.',
    'playlists.no_changes': 'No changes found yet',
    'playlists.latest': 'Latest changes, {date}',
    'playlists.history': 'History',
    'playlists.no_history': 'No checks of this playlist synced yet.',
    'event.ADDED': 'Added',
    'event.REMOVED': 'Removed',
    'event.UNPLAYABLE': 'Unplayable',
    'event.PLAYABLE_AGAIN': 'Playable again',
    'event.INITIAL_SNAPSHOT': 'First check',
    'event.initial_count': '{count} tracks recorded',
    'account.devices': 'Devices',
    'account.device_unknown': 'Unknown device',
    'account.appearance': 'Appearance',
    'account.language': 'Language',
    'account.theme': 'Theme',
    'account.synced_note': 'The language and theme are the same on all your devices.',
    'theme.system': 'System',
    'theme.light': 'Light',
    'theme.dark': 'Dark',
    'account.logout': 'Log out',
    'account.member_since': 'Member since {date}',
  },
  'tr': {
    'app.title': 'Playlist Tracker',
    'login.lead': 'Dinlemelerini ve listelerini burada görmek için masaüstü uygulamada kullandığın hesapla giriş '
        'yap.',
    'login.google': 'Google ile giriş yap',
    'login.failed': 'Giriş yapılamadı: {error}',
    'login.not_configured': 'Uygulama Supabase ayarları olmadan derlenmiş. --dart-define-from-file=config.json ile '
        'çalıştır (mobile/README.md\'ye bak).',
    'nav.listening': 'Dinleme',
    'nav.playlists': 'Listeler',
    'nav.account': 'Hesap',
    'load.failed': 'Yüklenemedi: {error}',
    'load.retry': 'Tekrar dene',
    'period.week': 'Hafta',
    'period.month': 'Ay',
    'period.year': 'Yıl',
    'period.all': 'Tümü',
    'period.this_week': 'Bu hafta',
    'period.all_time': 'Tüm zamanlar',
    'stats.plays': 'Dinleme',
    'stats.time': 'Dinleme süresi',
    'stats.tracks': 'Şarkı',
    'stats.artists': 'Sanatçı',
    'stats.chart': 'Dinlenen dakika',
    'stats.top_tracks': 'En çok dinlenen şarkılar',
    'stats.top_artists': 'En çok dinlenen sanatçılar',
    'stats.top_albums': 'En çok dinlenen albümler',
    'stats.recent': 'Son dinlenenler',
    'stats.empty': 'Bu dönemde dinleme yok.',
    'stats.none_yet': 'Henüz dinleme yok. Masaüstü uygulamanın kaydettikleri eşitlendikten sonra burada görünür.',
    'stats.plays_count': '{count} dinleme',
    'stats.change.new': 'YENİ',
    'minutes': '{minutes} dk',
    'hours': '{hours} sa {minutes} dk',
    'day.today': 'Bugün',
    'day.yesterday': 'Dün',
    'playlists.empty': 'Henüz takip edilen liste yok. Listeleri masaüstü uygulamada takip et; eşitlendikten sonra '
        'burada görünürler.',
    'playlists.no_changes': 'Henüz değişiklik bulunmadı',
    'playlists.latest': 'Son değişiklikler, {date}',
    'playlists.history': 'Geçmiş',
    'playlists.no_history': 'Bu listenin henüz eşitlenmiş bir kontrolü yok.',
    'event.ADDED': 'Eklendi',
    'event.REMOVED': 'Silindi',
    'event.UNPLAYABLE': 'Çalınamıyor',
    'event.PLAYABLE_AGAIN': 'Yeniden çalınabilir',
    'event.INITIAL_SNAPSHOT': 'İlk kontrol',
    'event.initial_count': '{count} şarkı kaydedildi',
    'account.devices': 'Cihazlar',
    'account.device_unknown': 'Bilinmeyen cihaz',
    'account.appearance': 'Görünüm',
    'account.language': 'Dil',
    'account.theme': 'Tema',
    'account.synced_note': 'Dil ve tema tüm cihazlarında aynıdır.',
    'theme.system': 'Sistem',
    'theme.light': 'Açık',
    'theme.dark': 'Koyu',
    'account.logout': 'Çıkış yap',
    'account.member_since': '{date} tarihinden beri üye',
  },
};

/// The text of key in language, with {name} placeholders filled from args
String translate(String language, String key, [Map<String, Object> args = const {}]) {
  var text = _strings[language]?[key] ?? _strings['en']![key] ?? key;
  args.forEach((name, value) => text = text.replaceAll('{$name}', '$value'));
  return text;
}

extension Texts on BuildContext {
  /// t('stats.plays_count', {'count': 3}) in the app's current language
  String t(String key, [Map<String, Object> args = const {}]) => translate(AppScope.of(this).language, key, args);
}
