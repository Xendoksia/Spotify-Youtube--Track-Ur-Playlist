/// Searching the recorded plays for tracks, artists and albums, as the desktop app's api/search: matching ignores
/// case, accents and Turkish letters, so "goksel" finds Göksel, and every word typed must appear.
library;

import 'models.dart';
import 'stats.dart';

/// Rows shown per kind
const searchLimit = 6;

/// Shorter queries match too much to be useful
const searchMinLength = 2;

const _plain = {
  'ı': 'i',
  'İ': 'i',
  'ş': 's',
  'Ş': 's',
  'ğ': 'g',
  'Ğ': 'g',
  'ü': 'u',
  'Ü': 'u',
  'ö': 'o',
  'Ö': 'o',
  'ç': 'c',
  'Ç': 'c',
  'â': 'a',
  'Â': 'a',
  'î': 'i',
  'Î': 'i',
  'û': 'u',
  'Û': 'u',
  'á': 'a',
  'à': 'a',
  'ä': 'a',
  'ã': 'a',
  'å': 'a',
  'é': 'e',
  'è': 'e',
  'ê': 'e',
  'ë': 'e',
  'í': 'i',
  'ì': 'i',
  'ï': 'i',
  'ó': 'o',
  'ò': 'o',
  'ô': 'o',
  'õ': 'o',
  'ú': 'u',
  'ù': 'u',
  'ñ': 'n',
  'ý': 'y',
  'ÿ': 'y',
};

/// Text without case, accents or Turkish letters, its spaces collapsed, for matching
String fold(String text) {
  final buffer = StringBuffer();
  for (final char in text.split('')) {
    buffer.write(_plain[char] ?? char.toLowerCase());
  }
  return buffer.toString().split(RegExp(r'\s+')).where((part) => part.isNotEmpty).join(' ');
}

/// How well the fields match: every word must appear in them; the first field starting with the query is best,
/// then a word of it starting so, then anywhere. Null when they do not match.
int? searchScore(String query, List<String> fields) {
  final words = query.split(' ');
  final joined = fields.map(fold).join(' ');
  if (!words.every(joined.contains)) return null;
  final first = fold(fields.first);
  if (first.startsWith(query)) return 0;
  if (first.split(' ').any((part) => part.startsWith(words.first))) return 1;
  return 2;
}

class SearchResults {
  final List<Ranked> tracks;
  final List<Ranked> artists;
  final List<Ranked> albums;

  const SearchResults(this.tracks, this.artists, this.albums);

  bool get isEmpty => tracks.isEmpty && artists.isEmpty && albums.isEmpty;
}

List<Ranked> _best(List<Ranked> rows, String query, List<String> Function(Ranked) fields) {
  final scored = [
    for (final row in rows)
      if (searchScore(query, fields(row)) case final score?) (score, row),
  ]..sort((a, b) => a.$1 != b.$1 ? a.$1.compareTo(b.$1) : b.$2.plays.compareTo(a.$2.plays));
  return [for (final (_, row) in scored.take(searchLimit)) row];
}

/// The tracks, artists and albums of all [plays] whose names hold every word of [query], best and most played first;
/// null for a query too short to search
SearchResults? searchPlays(List<Play> plays, String query) {
  final folded = fold(query);
  if (folded.length < searchMinLength) return null;
  const all = 1 << 30;
  return SearchResults(
    _best(topTracks(plays, limit: all), folded, (row) => [row.title, row.artist]),
    _best(topArtists(plays, limit: all), folded, (row) => [row.title]),
    _best(topAlbums(plays, limit: all), folded, (row) => [row.title, row.artist]),
  );
}
