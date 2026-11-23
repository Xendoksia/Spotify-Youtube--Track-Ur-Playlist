import 'package:flutter_test/flutter_test.dart';
import 'package:playlist_tracker/data/models.dart';
import 'package:playlist_tracker/data/search.dart';

void main() {
  Play play(String artist, String name, String album) => Play(
    uid: '$artist$name',
    deviceId: 'd',
    playedAt: DateTime(2026, 11, 2),
    artist: artist,
    name: name,
    album: album,
    msPlayed: 200000,
  );

  test('Turkish letters and accents match plain ones', () {
    expect(fold('Göksel'), 'goksel');
    expect(fold('  IŞIL  Ayman '), 'isil ayman');
    expect(fold('Beyoncé'), 'beyonce');
  });

  test('every word must match and a start ranks first', () {
    expect(searchScore('linkin numb', ['In The End', 'Linkin Park']), isNull);
    expect(searchScore('numb', ['Numb', 'Linkin Park']), 0);
    expect(searchScore('end', ['In The End', 'Linkin Park']), 1);
    expect(searchScore('park', ['Numb', 'Linkin Park']), 2);
  });

  test('a collaboration is searched as its artists when one is heard alone', () {
    final plays = [
      play('Şanışer', 'Görünce', 'A'),
      play('Şanışer, Sena Şener', 'Yağmur', 'B'),
      play('Simon & Garfunkel', 'The Boxer', 'C'),
    ];
    expect(searchPlays(plays, 'sanis')!.artists.map((a) => (a.title, a.plays)), [('Şanışer', 2)]);
    expect(searchPlays(plays, 'sena')!.artists.single.title, 'Sena Şener');
    expect(searchPlays(plays, 'simon')!.artists.single.title, 'Simon & Garfunkel');
  });

  test('plays are searched as tracks, artists and albums', () {
    final plays = [play('Göksel', 'Acıyor', 'Yollar'), play('Slipknot', 'Snuff', 'All Hope Is Gone')];
    final found = searchPlays(plays, 'goks')!;
    expect(found.artists.single.title, 'Göksel');
    expect(found.tracks.single.title, 'Acıyor');
    expect(found.albums.single.title, 'Yollar');
    expect(searchPlays(plays, 'a'), isNull);
  });
}
