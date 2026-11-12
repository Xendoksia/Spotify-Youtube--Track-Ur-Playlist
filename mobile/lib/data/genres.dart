/// Artists' genres from MusicBrainz, which needs no account, found the same way as the desktop app's
/// artist_info.py: a MusicBrainz artist of the same name is used only when some of its releases match the album or
/// track names in the listening history, so a different artist of the same name is not taken. The genres are kept
/// on the phone; artists are looked up one at a time, as MusicBrainz allows one request per second.
library;

import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'artwork.dart' show Fetch, retryAfter;
import 'models.dart';
import 'stats.dart';

const _musicBrainz = 'https://musicbrainz.org/ws/2';
const _userAgent = 'SpotifyPlaylistTracker/1.0 ( https://github.com/Xendoksia/Spotify-Youtube--Track-Ur-Playlist )';
const _gap = Duration(milliseconds: 1100);

/// Same named artists compared against the listening history, best search matches first
const _candidates = 4;
const _kept = 3;

Future<Object?> _fetch(Uri url) async {
  for (var attempt = 0;; attempt++) {
    final response = await http.get(url, headers: {'User-Agent': _userAgent}).timeout(const Duration(seconds: 20));
    // 503 means too many requests at the moment
    if (response.statusCode == 503 && attempt < 2) {
      await Future<void>.delayed(_gap * (attempt + 2));
      continue;
    }
    if (response.statusCode != 200) throw http.ClientException('HTTP ${response.statusCode}', url);
    return jsonDecode(utf8.decode(response.bodyBytes));
  }
}

/// Compare titles without version notes such as " - Remastered" or " (Deluxe Edition)"
String titleKey(String title) => textKey(plainTitle(title));

class Genres extends ChangeNotifier {
  static final instance = Genres();

  final Fetch fetch;
  final DateTime Function() clock;

  Genres({this.fetch = _fetch, DateTime Function()? clock}) : clock = clock ?? DateTime.now;

  /// artist key → {"genres": [...]} or {"missing": seconds since epoch}
  Map<String, Object?> _cache = {};
  var _loaded = false;
  final _queue = <(String, String, Set<String>)>[];
  final _waiting = <String>{};
  var _working = false;
  DateTime? _lastRequest;
  Timer? _notify;

  Future<void> load() async {
    if (_loaded) return;
    _loaded = true;
    try {
      final prefs = await SharedPreferences.getInstance();
      _cache = (jsonDecode(prefs.getString('ARTIST_GENRES') ?? '{}') as Map).cast<String, Object?>();
    } catch (_) {}
    notifyListeners();
  }

  Future<void> _save() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('ARTIST_GENRES', jsonEncode(_cache));
    } catch (_) {}
  }

  /// The artist's genres, most voted first, once known
  List<String>? genres(String artistKey) {
    final facts = _cache[artistKey];
    return facts is Map && facts['genres'] is List ? (facts['genres'] as List).cast<String>() : null;
  }

  String? mainGenre(String artistKey) => genres(artistKey)?.firstOrNull;

  bool waiting(String artistKey) => _waiting.contains(artistKey);

  /// Look the artist up in the background unless known (or not found within a week); listeners hear when it is
  void request(String artist, String artistKey, Set<String> titles) {
    if (!_loaded || _waiting.contains(artistKey)) return;
    final facts = _cache[artistKey];
    if (facts is Map) {
      final missing = facts['missing'];
      if (missing is! num) return;
      final since = clock().difference(DateTime.fromMillisecondsSinceEpoch(missing.toInt() * 1000));
      if (since < retryAfter) return;
    }
    _waiting.add(artistKey);
    _queue.add((artist, artistKey, titles));
    if (!_working) _work();
  }

  Future<void> _work() async {
    _working = true;
    while (_queue.isNotEmpty) {
      final (artist, key, titles) = _queue.removeAt(0);
      try {
        _cache[key] = await _lookUp(artist, titles);
        unawaited(_save());
      } catch (_) {
        // Offline or MusicBrainz unavailable: asked again next time
      }
      _waiting.remove(key);
      // Redrawn at most every few seconds while the genres come in
      _notify ??= Timer(const Duration(seconds: 3), () {
        _notify = null;
        notifyListeners();
      });
    }
    _working = false;
  }

  Future<Map<String, Object?>> _get(String path, Map<String, String> params) async {
    final wait = _lastRequest == null ? Duration.zero : _gap - clock().difference(_lastRequest!);
    if (wait > Duration.zero) await Future<void>.delayed(wait);
    try {
      final result = await fetch(Uri.parse('$_musicBrainz$path').replace(queryParameters: {...params, 'fmt': 'json'}));
      return (result as Map).cast<String, Object?>();
    } finally {
      _lastRequest = clock();
    }
  }

  Future<Map<String, Object?>> _lookUp(String artist, Set<String> titles) async {
    final heard = titles.map(titleKey).where((t) => t.isNotEmpty).toSet();
    String? id;
    for (final name in nameVariants(artist)) {
      final results = ((await _get('/artist/', {'query': 'artist:"$name"', 'limit': '10'}))['artists'] as List?) ?? [];
      final sameName = results.cast<Map>().where((a) =>
          textKey(a['name'] as String?) == textKey(name) ||
          ((a['aliases'] as List?) ?? []).cast<Map>().any((alias) => textKey(alias['name'] as String?) == textKey(name)));
      var bestHits = 0;
      for (final candidate in sameName.take(_candidates)) {
        final groups = ((await _get('/release-group', {'artist': candidate['id'] as String, 'limit': '100'}))[
                'release-groups'] as List?) ??
            [];
        final hits = groups.cast<Map>().map((g) => titleKey(g['title'] as String? ?? '')).toSet().intersection(heard);
        if (hits.length > bestHits) {
          id = candidate['id'] as String;
          bestHits = hits.length;
        }
      }
      if (id != null) break;
    }
    if (id == null) return {'missing': clock().millisecondsSinceEpoch ~/ 1000};
    final details = await _get('/artist/$id', {'inc': 'genres'});
    final genres = ((details['genres'] as List?) ?? []).cast<Map>().where((g) => (g['count'] as num? ?? 0) > 0).toList()
      ..sort((a, b) => (b['count'] as num).compareTo(a['count'] as num));
    return {'genres': [for (final g in genres.take(_kept)) g['name'] as String]};
  }
}

/// A genre's share of a period's plays: an artist's plays count for its main genre
class GenreShare {
  final String name;
  final int plays;
  final List<String> artists;

  GenreShare(this.name, this.plays, this.artists);
}

/// The period's genres, most played first, with the plays whose artist's genre is known and the artists still
/// being looked up; asks for the genres it does not know yet
({List<GenreShare> genres, int known, int total, int waiting}) genreShares(List<Play> all, List<Play> plays) {
  final genres = Genres.instance;
  final shares = <String, GenreShare>{};
  var known = 0;
  var waiting = 0;
  final artists = topArtists(plays, limit: 1 << 30);
  for (final artist in artists) {
    final genre = genres.mainGenre(artist.key);
    if (genre != null) {
      shares.putIfAbsent(genre, () => GenreShare(genre, 0, []));
      final share = shares[genre]!;
      // A collaboration is listed by its main artist, once
      final name = nameVariants(artist.title).last;
      shares[genre] = GenreShare(genre, share.plays + artist.plays,
          share.artists.any((a) => textKey(a) == textKey(name)) ? share.artists : [...share.artists, name]);
      known += artist.plays;
    } else {
      genres.request(artist.title, artist.key, {
        for (final play in all.where((p) => p.artistKey == artist.key)) ...[play.name, play.album],
      });
      if (genres.waiting(artist.key)) waiting++;
    }
  }
  final sorted = shares.values.toList()..sort((a, b) => b.plays.compareTo(a.plays));
  return (genres: sorted, known: known, total: plays.length, waiting: waiting);
}
