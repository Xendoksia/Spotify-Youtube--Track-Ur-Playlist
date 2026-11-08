import 'dart:async';

import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';

import 'models.dart';

/// A song the Spotify app plays (or has paused) on the phone
class Song {
  final String title;
  final String artist;
  final String album;
  final int? duration;
  final bool playing;

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

  bool hasAccess = false;
  Song? song;
  StreamSubscription<dynamic>? _subscription;

  NowPlaying() {
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
