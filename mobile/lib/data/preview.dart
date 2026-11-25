/// Deezer's 30 second previews of suggested songs, one at a time, as the desktop app's preview.ts
library;

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/widgets.dart';

import 'artwork.dart';

enum PreviewState { idle, loading, playing, none }

class Preview extends ChangeNotifier with WidgetsBindingObserver {
  static final instance = Preview();

  /// The address is signed for a while, so it is kept this long
  static const keep = Duration(minutes: 30);

  AudioPlayer? _player;

  /// artist|title of the song playing or being looked up
  var _key = '';
  var _state = PreviewState.idle;
  var _progress = 0.0;
  final _missing = <String>{};
  final _urls = <String, (String, DateTime)>{};

  AudioPlayer get _audio => _player ??= () {
        WidgetsBinding.instance.addObserver(this);
        final player = AudioPlayer()..setVolume(0.56);
        player.onPositionChanged.listen((position) async {
          final length = await player.getDuration();
          if (_state == PreviewState.playing && length != null && length.inMilliseconds > 0) {
            _progress = position.inMilliseconds / length.inMilliseconds;
            notifyListeners();
          }
        });
        player.onPlayerComplete.listen((_) => stop());
        return player;
      }();

  static String _keyOf(String artist, String title) => '$artist|$title';

  PreviewState stateOf(String artist, String title) {
    final key = _keyOf(artist, title);
    if (_missing.contains(key)) return PreviewState.none;
    return key == _key ? _state : PreviewState.idle;
  }

  double progressOf(String artist, String title) => _keyOf(artist, title) == _key ? _progress : 0;

  void stop() {
    _player?.stop();
    if (_key.isEmpty) return;
    _key = '';
    _state = PreviewState.idle;
    _progress = 0;
    notifyListeners();
  }

  Future<void> toggle(String artist, String title) async {
    final key = _keyOf(artist, title);
    if (key == _key) return stop();
    await _player?.stop();
    _key = key;
    _state = PreviewState.loading;
    _progress = 0;
    notifyListeners();
    try {
      final kept = _urls[key];
      var url = kept != null && DateTime.now().difference(kept.$2) < keep ? kept.$1 : null;
      url ??= await Artwork.instance.preview(artist, title);
      // Another song was tapped meanwhile
      if (_key != key) return;
      if (url == null) {
        _missing.add(key);
        _key = '';
        _state = PreviewState.idle;
        notifyListeners();
        return;
      }
      _urls[key] = (url, DateTime.now());
      await _audio.play(UrlSource(url));
      if (_key == key) {
        _state = PreviewState.playing;
        notifyListeners();
      }
    } catch (_) {
      // Offline or Deezer's rate limit: tried again on the next tap
      if (_key == key) stop();
    }
  }

  /// A preview stops when the app goes to the background
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused || state == AppLifecycleState.hidden) stop();
  }
}
