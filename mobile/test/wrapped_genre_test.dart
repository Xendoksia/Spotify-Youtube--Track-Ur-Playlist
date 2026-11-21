import 'package:flutter_test/flutter_test.dart';
import 'package:playlist_tracker/data/genres.dart';

void main() {
  test('genres fall into families by the words in their names', () {
    expect(genreFamily('Metalcore'), 'metal');
    expect(genreFamily('alternative metal'), 'metal');
    expect(genreFamily('post-grunge'), 'rock');
    expect(genreFamily('synth-pop'), 'electronic');
    expect(genreFamily('Turkish rock'), 'turkish');
    expect(genreFamily('polka'), 'other');
  });

  test('the two biggest genres get a word of their own, else the first one\'s family does', () {
    expect(genreMessage('Metalcore', 'Nu metal'), 'wrapped.genre.combo.metalcore_numetal');
    expect(genreMessage('nu metal', 'metalcore'), 'wrapped.genre.combo.metalcore_numetal');
    expect(genreMessage('Hard rock', 'Pop'), 'wrapped.genre.combo.pop_rock');
    expect(genreMessage('deathcore', 'thrash metal'), 'wrapped.genre.combo.metal_metal');
    expect(genreMessage('jazz', 'folk'), 'wrapped.genre.say.jazz');
    expect(genreMessage('Pop', null), 'wrapped.genre.say.pop');
  });
}
