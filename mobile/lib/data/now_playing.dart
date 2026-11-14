import 'dart:async';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'models.dart';

/// A song the Spotify app plays (or has paused) on the phone
class Song {
  final String title;
  final String artist;
  final String album;
  final int? duration;
  final bool playing;

  /// Stored as a play of the phone, once listened to for 30 seconds
  final bool recorded;

  /// Where the song was at [positionAt], moving on at [speed] while playing
  final int? position;
  final DateTime? positionAt;
  final double speed;

  const Song({
    required this.title,
    required this.artist,
    required this.album,
    this.duration,
    this.position,
    this.positionAt,
    this.speed = 1,
    required this.playing,
    this.recorded = false,
  });

  factory Song.fromMap(Map<Object?, Object?> map) => Song(
        title: map['title'] as String,
        artist: map['artist'] as String? ?? '',
        album: map['album'] as String? ?? '',
        duration: (map['duration'] as num?)?.toInt(),
        position: (map['position'] as num?)?.toInt(),
        positionAt: map['positionAt'] == null
            ? null
            : DateTime.fromMillisecondsSinceEpoch((map['positionAt'] as num).toInt()),
        speed: (map['speed'] as num?)?.toDouble() ?? 1,
        playing: map['playing'] as bool? ?? false,
        recorded: map['recorded'] as bool? ?? false,
      );

  /// The same key as the plays', so the song's page can be found
  String get trackKey => '${textKey(artist)}|${textKey(title)}';

  /// Where the song is now: between two updates from Android it keeps going
  int? positionAtTime(DateTime now) {
    var at = position;
    if (at == null) return null;
    if (playing && positionAt != null) at += (now.difference(positionAt!).inMilliseconds * speed).round();
    if (duration != null && at > duration!) at = duration!;
    return at < 0 ? 0 : at;
  }
}

/// What plays on the phone, read by the Android side (NowPlaying.kt) once notification access is given
class NowPlaying extends ChangeNotifier with WidgetsBindingObserver {
  static const _methods = MethodChannel('playlist_tracker/now_playing');
  static const _events = EventChannel('playlist_tracker/now_playing/events');

  /// Only the Android app reads and records what plays; on a computer the desktop app does
  static bool get supported => !kIsWeb && defaultTargetPlatform == TargetPlatform.android;

  bool hasAccess = false;
  Song? song;
  StreamSubscription<dynamic>? _subscription;

  NowPlaying() {
    if (!supported) return;
    WidgetsBinding.instance.addObserver(this);
    _subscription = _events.receiveBroadcastStream().listen((event) {
      song = event == null ? null : Song.fromMap(event as Map<Object?, Object?>);
      notifyListeners();
    }, onError: (_) {});
    _checkAccess();
  }

  Future<void> _checkAccess() async {
    final had = hasAccess;
    try {
      hasAccess = await _methods.invokeMethod<bool>('hasAccess') ?? false;
    } on MissingPluginException {
      hasAccess = false;
    }
    if (hasAccess != had) {
      // Given (or taken back) in the settings: follow the sessions with it
      await _methods.invokeMethod('restart');
      notifyListeners();
    }
  }

  /// Send the plays recorded on the phone (PlayRecorder.kt) to Supabase, as the desktop app sends its own;
  /// return how many. A play whose listening time grew since it was sent is sent again with the new time.
  Future<int> sendPlays() async {
    if (!supported) return 0;
    final client = Supabase.instance.client;
    final user = client.auth.currentUser;
    if (user == null) return 0;
    final List<Map<Object?, Object?>> plays;
    try {
      plays = [...?await _methods.invokeListMethod<Map<Object?, Object?>>('unsyncedPlays')];
    } on MissingPluginException {
      return 0;
    }
    if (plays.isEmpty) return 0;
    final (deviceId, deviceName) = await device();
    await client.from('plays').upsert([
      for (final play in plays)
        {
          'user_id': user.id,
          'uid': play['uid'],
          'device_id': deviceId,
          'device_name': deviceName,
          'played_at': play['played_at'],
          'source': source,
          'artist': play['artist'],
          'name': play['name'],
          'album': play['album'],
          'ms_played': play['ms_played'],
        },
    ], onConflict: 'user_id,uid');
    await _methods.invokeMethod('markSynced', plays);
    return plays.length;
  }

  /// The source of the phone's plays in Supabase (the desktop app's are "local")
  static const source = 'android';

  /// This phone's id (made once, as the desktop app's DEVICE_ID) and name
  static Future<(String, String)> device() async {
    final prefs = await SharedPreferences.getInstance();
    var id = prefs.getString('DEVICE_ID');
    if (id == null) {
      final random = Random.secure();
      final hex = [for (var i = 0; i < 32; i++) random.nextInt(16).toRadixString(16)].join();
      id = '${hex.substring(0, 8)}-${hex.substring(8, 12)}-4${hex.substring(13, 16)}-'
          '${'89ab'[random.nextInt(4)]}${hex.substring(17, 20)}-${hex.substring(20)}';
      await prefs.setString('DEVICE_ID', id);
    }
    final name = await _methods.invokeMethod<String>('deviceName') ?? 'Android';
    return (id, name);
  }

  /// Android's notification access page, where the app is switched on
  Future<void> openSettings() => _methods.invokeMethod('openSettings');

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _checkAccess();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _subscription?.cancel();
    super.dispose();
  }
}
