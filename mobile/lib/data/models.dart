/// The rows the desktop app syncs to Supabase (see supabase/migrations in the repository).
library;

/// The same text with different case or spacing is the same artist or track, as in the desktop app's key().
String textKey(String? text) => (text ?? '').toLowerCase().split(RegExp(r'\s+')).where((w) => w.isNotEmpty).join(' ');

/// Media controls sometimes list several artists in one name; the first is the main one
List<String> nameVariants(String artist) {
  final first = artist.split(RegExp(r',|&| feat\.? | ft\.? | x ', caseSensitive: false)).first.trim();
  return {artist, first}.where((name) => name.isNotEmpty).toList();
}

final _creditSeparators = RegExp(r',|&| feat\.? | ft\.? | x ', caseSensitive: false);

/// The artists one artist name credits, as the desktop app's listening.credited: a collaboration such as
/// "Şanışer, Sena Şener" is its artists when one of them is also heard on their own ([soloKeys]), so a band named
/// "Simon & Garfunkel" stays one
List<String> credited(String artist, Set<String> soloKeys) {
  final parts = artist.split(_creditSeparators).map((part) => part.trim()).where((part) => part.isNotEmpty).toList();
  if (parts.length > 1 && parts.any((part) => soloKeys.contains(textKey(part)))) return parts;
  return [artist];
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

/// Plays of a track closer than its length plus this are one play recorded by two sources, as the desktop app's
/// listening.MATCH_MARGIN
const matchMargin = Duration(minutes: 3);

/// The plays without those another source recorded too (a song playing on the computer may also show on the
/// phone), as the desktop app keeps them: the computer's play stays and the phone's of the same track within its
/// length plus [matchMargin] is left out. The order is kept.
List<Play> withoutDuplicates(List<Play> plays) {
  // The phone's ("android") come last, so the computer's are the ones kept
  final ordered = [...plays.where((p) => p.source != 'android'), ...plays.where((p) => p.source == 'android')];
  final kept = <String, List<Play>>{};
  final dropped = <String>{};
  for (final play in ordered) {
    final window = matchMargin + Duration(milliseconds: play.msPlayed);
    final same = kept.putIfAbsent(play.trackKey, () => []);
    if (same.any((other) => other.source != play.source && other.playedAt.difference(play.playedAt).abs() <= window)) {
      dropped.add(play.uid);
    } else {
      same.add(play);
    }
  }
  return dropped.isEmpty
      ? plays
      : [
          for (final play in plays)
            if (!dropped.contains(play.uid)) play,
        ];
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
