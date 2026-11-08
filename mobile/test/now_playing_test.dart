import 'package:flutter_test/flutter_test.dart';
import 'package:playlist_tracker/data/now_playing.dart';

void main() {
  final at = DateTime(2026, 11, 8, 12);

  Song song({bool playing = true, int? duration = 200000}) => Song.fromMap({
        'title': 'Some  Song',
        'artist': 'The Artist',
        'album': 'An Album',
        'duration': duration,
        'position': 60000,
        'positionAt': at.millisecondsSinceEpoch,
        'speed': 1.0,
        'playing': playing,
      });

  test('a playing song moves on between updates, a paused one stays', () {
    final later = at.add(const Duration(seconds: 5));
    expect(song().positionAtTime(later), 65000);
    expect(song(playing: false).positionAtTime(later), 60000);
  });

  test('the position stops at the song\'s end', () {
    expect(song().positionAtTime(at.add(const Duration(minutes: 10))), 200000);
    expect(song(duration: null).positionAtTime(at.add(const Duration(minutes: 10))), 660000);
  });

  test('the key matches the plays\' track key', () {
    expect(song().trackKey, 'the artist|some song');
  });
}
