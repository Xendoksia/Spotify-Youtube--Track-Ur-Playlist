import 'package:flutter_test/flutter_test.dart';
import 'package:playlist_tracker/data/artwork.dart';
import 'package:playlist_tracker/data/stats.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Deezer answering from a table of query → results, counting the requests
class FakeDeezer {
  final Map<String, List<Map<String, Object?>>> answers;
  final requests = <String>[];

  FakeDeezer(this.answers);

  Future<Object?> fetch(Uri url) async {
    final query = '${url.path} ${url.queryParameters['q']}';
    requests.add(query);
    return {'data': answers[query] ?? []};
  }
}

Map<String, Object?> track(String artist, String cover) => {
      'artist': {'name': artist},
      'album': {'cover_big': cover},
    };

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('version notes are dropped from titles', () {
    expect(plainTitle('Song - Remastered 2026'), 'Song');
    expect(plainTitle('Album (Deluxe) [Live]'), 'Album');
    expect(plainTitle('(Intro)'), '(Intro)');
  });

  test('a cover comes only from the same artist, and the plain title is tried too', () async {
    final deezer = FakeDeezer({
      '/search artist:"Band" track:"Song - Remastered"': [track('Other Band', 'wrong.jpg')],
      '/search artist:"Band" track:"Song"': [track('band', 'right.jpg')],
    });
    final artwork = Artwork(fetch: deezer.fetch);
    expect(await artwork.cover('Band', 'Album', 'Song - Remastered'), 'right.jpg');
  });

  test('an artist without a photo has none', () async {
    final deezer = FakeDeezer({
      '/search/artist Band': [
        {'name': 'Band', 'picture_big': 'https://e-cdns-images.dzcdn.net/images/artist//500x500.jpg'},
      ],
    });
    expect(await Artwork(fetch: deezer.fetch).artistPhoto('Band'), isNull);
  });

  test('a collaboration gets its main artist\'s photo and covers', () async {
    final deezer = FakeDeezer({
      '/search/artist Pera': [
        {'name': 'Pera', 'picture_big': 'pera.jpg'},
      ],
      '/search artist:"Pera" track:"Song"': [track('Pera', 'song.jpg')],
    });
    final artwork = Artwork(fetch: deezer.fetch);
    expect(await artwork.artistPhoto('Pera, Işıl Ayman'), 'pera.jpg');
    expect(await artwork.cover('Pera, Işıl Ayman', '', 'Song'), 'song.jpg');
  });

  test('what was found is not looked up again, nothing found is tried again after a week', () async {
    var now = DateTime(2026, 11, 8);
    final deezer = FakeDeezer({});
    final artwork = Artwork(fetch: deezer.fetch, clock: () => now);
    expect(await artwork.artistPhoto('Band'), isNull);
    final asked = deezer.requests.length;
    expect(await artwork.artistPhoto('Band'), isNull);
    expect(deezer.requests.length, asked);
    now = now.add(const Duration(days: 8));
    await artwork.artistPhoto('Band');
    expect(deezer.requests.length, greaterThan(asked));
  });

  test('tracks of one album share one lookup', () async {
    final deezer = FakeDeezer({
      '/search artist:"Band" track:"One"': [track('Band', 'album.jpg')],
    });
    final artwork = Artwork(fetch: deezer.fetch);
    expect(await artwork.cover('Band', 'Album', 'One'), 'album.jpg');
    expect(await artwork.cover('Band', 'Album', 'Two'), 'album.jpg');
    expect(deezer.requests, hasLength(1));
  });

  test("an album's track list comes from the same artist's album of that title", () async {
    final deezer = FakeDeezer({
      '/search/album artist:"Band" album:"Record (Deluxe)"': [
        {'id': 1, 'title': 'Other Record', 'artist': {'name': 'Band'}},
        {'id': 2, 'title': 'Record', 'artist': {'name': 'Band'}},
      ],
    });
    final artwork = Artwork(fetch: (url) async {
      if (url.path == '/album/2/tracks') {
        return {
          'data': [
            {'title': 'One', 'duration': 180},
            {'title': 'Two', 'duration': 200},
          ],
        };
      }
      return deezer.fetch(url);
    });
    expect(await artwork.tracklist('Band', 'Record (Deluxe)'), [('One', 180000), ('Two', 200000)]);
  });
}
