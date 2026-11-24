/// The rows the desktop app syncs to Supabase (see supabase/migrations in the repository).
library;

/// The same text with different case or spacing is the same artist or track, as in the desktop app's key().
String textKey(String? text) => (text ?? '').toLowerCase().split(RegExp(r'\s+')).where((w) => w.isNotEmpty).join(' ');

/// Media controls sometimes list several artists in one name; the first is the main one
List<String> nameVariants(String artist) {
  final first = artist.split(RegExp(r',|&| feat\.? | ft\.? | x ', caseSensitive: false)).first.trim();
  return {artist, first}.where((name) => name.isNotEmpty).toList();
}

// Collaborations list their artists with commas (or "feat."); an ampersand is left alone, as bands such as
// "Judge & Jury" or "Simon & Garfunkel" carry one in their name
final _creditSeparators = RegExp(r',| feat\.? | ft\.? ', caseSensitive: false);

/// The artists listed in one artist name, a collaboration's in order
List<String> creditParts(String artist) => _creditParts(artist);

List<String> _creditParts(String artist) {
  final parts = artist.split(_creditSeparators).map((part) => part.trim()).where((part) => part.isNotEmpty).toList();
  return parts.isEmpty ? [artist] : parts;
}

/// The keys of artists heard on their own or first in a collaboration, as the desktop app's known_artists
Set<String> knownArtists(Iterable<String> names) => {for (final name in names) textKey(_creditParts(name).first)};

/// The artists one artist name credits, as the desktop app's listening.credited: a collaboration such as
/// "Şanışer, Sena Şener" goes to its first artist, and to its others too when they are [known] artists themselves
List<String> credited(String artist, Set<String> known) {
  final parts = _creditParts(artist);
  return [parts.first, ...parts.skip(1).where((part) => known.contains(textKey(part)))];
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

/// A playlist the desktop app knows: tracked, found in an account and not decided on (not [seen]), or neither
class TrackedPlaylist {
  final String service;
  final String playlistId;
  final String name;
  final bool tracked;

  /// False for a playlist found in an account that nobody decided to track or not
  final bool seen;

  /// Its size as the account gave it, for one not checked yet
  final int? size;
  final DateTime? foundAt;

  TrackedPlaylist({
    required this.service,
    required this.playlistId,
    required this.name,
    this.tracked = true,
    this.seen = true,
    this.size,
    this.foundAt,
  });

  bool get found => !tracked && !seen;

  factory TrackedPlaylist.fromRow(Map<String, dynamic> row) => TrackedPlaylist(
    service: row['service'] as String,
    playlistId: row['playlist_id'] as String,
    name: row['name'] as String? ?? row['playlist_id'] as String,
    tracked: row['tracked'] as bool? ?? true,
    seen: row['seen'] as bool? ?? true,
    size: (row['size'] as num?)?.toInt(),
    foundAt: row['found_at'] == null ? null : DateTime.tryParse(row['found_at'] as String)?.toLocal(),
  );
}

/// The desktop app's last check of the tracked playlists, its next automatic one, and a check asked for here
class PlaylistStatus {
  final DateTime? checkedAt;
  final int checkedCount;
  final DateTime? nextCheck;
  final DateTime? checkRequestedAt;

  const PlaylistStatus({this.checkedAt, this.checkedCount = 0, this.nextCheck, this.checkRequestedAt});

  static DateTime? _time(Object? value) => value == null ? null : DateTime.tryParse(value as String)?.toLocal();

  factory PlaylistStatus.fromRow(Map<String, dynamic>? row) => row == null
      ? const PlaylistStatus()
      : PlaylistStatus(
          checkedAt: _time(row['checked_at']),
          checkedCount: (row['checked_count'] as num?)?.toInt() ?? 0,
          nextCheck: _time(row['next_check']),
          checkRequestedAt: _time(row['check_requested_at']),
        );

  /// A check asked for here that the desktop app has not answered yet
  bool get waiting =>
      checkRequestedAt != null && (checkedAt == null || checkRequestedAt!.isAfter(checkedAt!));
}

/// A playlist link of Spotify or YouTube, as the desktop app's parse_playlist_id: (service, playlist id), or null
(String, String)? parsePlaylistLink(String link) {
  link = link.trim();
  final spotify = RegExp(r'playlist[/:]([A-Za-z0-9]{22})').firstMatch(link);
  if (spotify != null) return ('spotify', spotify.group(1)!);
  if (RegExp(r'^[A-Za-z0-9]{22}$').hasMatch(link)) return ('spotify', link);
  final youtube = RegExp(r'[?&]list=([A-Za-z0-9_-]+)').firstMatch(link)?.group(1) ?? link;
  if (RegExp(r'^(PL|UU|FL|LL|OL)[A-Za-z0-9_-]{8,}$').hasMatch(youtube)) return ('youtube', youtube);
  return null;
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
