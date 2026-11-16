/// The rows the desktop app syncs to Supabase (see supabase/migrations in the repository).
library;

/// The same text with different case or spacing is the same artist or track, as in the desktop app's key().
String textKey(String? text) => (text ?? '').toLowerCase().split(RegExp(r'\s+')).where((w) => w.isNotEmpty).join(' ');

/// Media controls sometimes list several artists in one name; the first is the main one
List<String> nameVariants(String artist) {
  final first = artist.split(RegExp(r',|&| feat\.? | ft\.? | x ', caseSensitive: false)).first.trim();
  return {artist, first}.where((name) => name.isNotEmpty).toList();
}

/// A time as the desktop app writes it for syncing: UTC with microseconds, so such texts sort by time.
String utcStamp(DateTime moment) {
  final utc = moment.toUtc();
  String two(int n) => n.toString().padLeft(2, '0');
  final micros = (utc.millisecond * 1000 + utc.microsecond).toString().padLeft(6, '0');
  return '${utc.year}-${two(utc.month)}-${two(utc.day)}T${two(utc.hour)}:${two(utc.minute)}:${two(utc.second)}'
      '.${micros}Z';
}

class Play {
  final String uid;
  final String deviceId;
  final String? deviceName;
  final DateTime playedAt;
  final String artist;
  final String name;
  final String album;
  final int msPlayed;

  /// Where it was recorded: "android" on a phone, "local" or "spotify" by the desktop app
  final String source;

  Play({
    required this.uid,
    required this.deviceId,
    this.deviceName,
    required this.playedAt,
    required this.artist,
    required this.name,
    required this.album,
    required this.msPlayed,
    this.source = '',
  });

  String get artistKey => textKey(artist);
  String get trackKey => '$artistKey|${textKey(name)}';

  factory Play.fromRow(Map<String, dynamic> row) => Play(
        uid: row['uid'] as String,
        deviceId: row['device_id'] as String,
        deviceName: row['device_name'] as String?,
        playedAt: DateTime.parse(row['played_at'] as String).toLocal(),
        artist: row['artist'] as String? ?? '',
        name: row['name'] as String? ?? '',
        album: row['album'] as String? ?? '',
        msPlayed: row['ms_played'] as int? ?? 0,
        source: row['source'] as String? ?? '',
      );
}

class TrackedPlaylist {
  final String service;
  final String playlistId;
  final String name;

  TrackedPlaylist({required this.service, required this.playlistId, required this.name});

  factory TrackedPlaylist.fromRow(Map<String, dynamic> row) => TrackedPlaylist(
        service: row['service'] as String,
        playlistId: row['playlist_id'] as String,
        name: row['name'] as String? ?? row['playlist_id'] as String,
      );
}

/// What a check of a playlist found, as the desktop app's history.EVENT_* names
enum EventKind {
  added('ADDED'),
  removed('REMOVED'),
  unplayable('UNPLAYABLE'),
  playableAgain('PLAYABLE_AGAIN'),
  initial('INITIAL_SNAPSHOT');

  final String code;
  const EventKind(this.code);

  static EventKind? of(String code) => values.where((kind) => kind.code == code).firstOrNull;
}

class PlaylistEvent {
  final String uid;
  final String service;
  final String playlistId;
  final DateTime checkedAt;
  final EventKind kind;
  final String name;
  final String artist;
  final String album;

  /// The track's Spotify address or YouTube video id
  final String uri;

  PlaylistEvent({
    required this.uid,
    required this.service,
    required this.playlistId,
    required this.checkedAt,
    required this.kind,
    required this.name,
    required this.artist,
    required this.album,
    this.uri = '',
  });

  /// The first check stores "`count` tracks recorded" as the name
  int? get initialCount => kind == EventKind.initial ? int.tryParse(name.split(' ').first) : null;

  /// Null for an event of a newer app version this one does not know
  static PlaylistEvent? fromRow(Map<String, dynamic> row) {
    final kind = EventKind.of(row['event'] as String);
    if (kind == null) return null;
    return PlaylistEvent(
      uid: row['uid'] as String,
      service: row['service'] as String,
      playlistId: row['playlist_id'] as String,
      checkedAt: DateTime.parse(row['checked_at'] as String).toLocal(),
      kind: kind,
      name: row['name'] as String? ?? '',
      artist: row['artist'] as String? ?? '',
      album: row['album'] as String? ?? '',
      uri: row['uri'] as String? ?? '',
    );
  }
}
