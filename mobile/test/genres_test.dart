import 'package:flutter_test/flutter_test.dart';
import 'package:playlist_tracker/data/genres.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  test('titles are compared without version notes, several artists by the first', () {
    expect(titleKey('Snuff - Remastered (2026)'), 'snuff');
    expect(titleKey('All Hope Is Gone [Deluxe]'), 'all hope is gone');
    expect(nameVariants('Linkin Park feat. JAY-Z'), ['Linkin Park feat. JAY-Z', 'Linkin Park']);
  });

  test('the same named artist whose releases were heard gives the genres, most voted first', () async {
    SharedPreferences.setMockInitialValues({});
    final asked = <String>[];
    final genres = Genres(fetch: (url) async {
      asked.add(url.path);
      if (url.path == '/ws/2/artist/') {
        return {
          'artists': [
            {'id': 'other', 'name': 'Slipknot'},
            {'id': 'real', 'name': 'slipknot'},
          ],
        };
      }
      if (url.path == '/ws/2/release-group') {
        return {
          'release-groups': url.queryParameters['artist'] == 'real'
              ? [{'title': 'All Hope Is Gone'}]
              : [{'title': 'Something Else'}],
        };
      }
      return {
        'genres': [
          {'name': 'nu metal', 'count': 5},
          {'name': 'metal', 'count': 9},
          {'name': 'unvoted', 'count': 0},
        ],
      };
    });
    await genres.load();
    genres.request('Slipknot', 'slipknot', {'Snuff', 'All Hope Is Gone (Deluxe)'});
    expect(genres.waiting('slipknot'), isTrue);
    while (genres.waiting('slipknot')) {
      await Future<void>.delayed(const Duration(milliseconds: 50));
    }
    expect(genres.genres('slipknot'), ['metal', 'nu metal']);
    expect(genres.mainGenre('slipknot'), 'metal');
    expect(asked.last, '/ws/2/artist/real');
  });
}
