/// Album covers and artist photos from Deezer's search, which needs no account, found the same way as the
/// desktop app's artwork.py. The picture addresses are kept on the phone; the pictures themselves are cached by
/// cached_network_image.
library;

import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'models.dart';

const _searchUrl = 'https://api.deezer.com';

/// A lookup that found nothing is tried again after this long
const retryAfter = Duration(days: 7);

/// Deezer returns this placeholder path for artists without a photo
const _emptyPicture = '/images/artist//';

/// Drop version notes such as " - Remastered 2026" or " (Deluxe)" that other catalogs spell differently
String plainTitle(String name) {
  final plain = name.split(' - ').first.replaceAll(RegExp(r'\s*(\(.*?\)|\[.*?\])'), '').trim();
  return plain.isEmpty ? name : plain;
}

typedef Fetch = Future<Object?> Function(Uri url);

Future<Object?> _fetch(Uri url) async {
  final response = await http.get(url).timeout(const Duration(seconds: 20));
  if (response.statusCode != 200) throw http.ClientException('HTTP ${response.statusCode}', url);
  return jsonDecode(utf8.decode(response.bodyBytes));
}

class Artwork {
  static final instance = Artwork();

  final Fetch fetch;
  final DateTime Function() clock;

  /// Deezer allows about 50 requests in 5 seconds; a long list must not run into it
  final int parallel;

  Artwork({this.fetch = _fetch, DateTime Function()? clock, this.parallel = 4}) : clock = clock ?? DateTime.now;

  /// key → picture address, or "" with the time when nothing was found
  Map<String, Object?>? _cache;
  final _pending = <String, Future<String?>>{};
  var _running = 0;
  final _waiting = <Completer<void>>[];
  Timer? _saveTimer;

  Future<Map<String, Object?>> _load() async {
    if (_cache != null) return _cache!;
    try {
      final prefs = await SharedPreferences.getInstance();
      _cache = (jsonDecode(prefs.getString('ARTWORK') ?? '{}') as Map).cast<String, Object?>();
    } catch (_) {
      _cache = {};
    }
    return _cache!;
  }

  void _save() {
    _saveTimer?.cancel();
    _saveTimer = Timer(const Duration(seconds: 2), () async {
      try {
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('ARTWORK', jsonEncode(_cache));
      } catch (_) {}
    });
  }

  /// The cover of a track; tracks of one album share it, as in the desktop app
  Future<String?> cover(String artist, String album, String name) => _lookup(
    album.isNotEmpty ? 'cover:${textKey(artist)}|${textKey(album)}' : 'cover:${textKey(artist)}||${textKey(name)}',
    () => _findCover(artist, name),
  );

  Future<String?> albumCover(String artist, String album) =>
      _lookup('cover:${textKey(artist)}|${textKey(album)}', () => _findAlbumCover(artist, album));

  Future<String?> artistPhoto(String artist) => _lookup('artist:${textKey(artist)}', () => _findArtistPhoto(artist));

  /// What the cache knows: the address, "" for nothing found lately, null when not looked up yet
  String? _known(Map<String, Object?> cache, String key) {
    final entry = cache[key];
    if (entry is String) return entry;
    if (entry is int && clock().difference(DateTime.fromMillisecondsSinceEpoch(entry)) < retryAfter) return '';
    return null;
  }

  Future<String?> _lookup(String key, Future<String?> Function() find) {
    return _pending[key] ??= () async {
      try {
        final cache = await _load();
        final known = _known(cache, key);
        if (known != null) return known.isEmpty ? null : known;
        final url = await _limited(find);
        cache[key] = url ?? clock().millisecondsSinceEpoch;
        _save();
        return url;
      } catch (_) {
        return null; // offline: tried again next time
      } finally {
        _pending.remove(key);
      }
    }();
  }

  Future<T> _limited<T>(Future<T> Function() task) async {
    while (_running >= parallel) {
      final turn = Completer<void>();
      _waiting.add(turn);
      await turn.future;
    }
    _running++;
    try {
      return await task();
    } finally {
      _running--;
      if (_waiting.isNotEmpty) _waiting.removeAt(0).complete();
    }
  }

  Future<List<Map<String, dynamic>>> _search(String path, String query) async {
    final result = await fetch(Uri.parse('$_searchUrl$path').replace(queryParameters: {'q': query, 'limit': '5'}));
    final data = result is Map ? result['data'] : null;
    return data is List ? data.whereType<Map<String, dynamic>>().toList() : [];
  }

  /// Exact search first, then a loose one; only the same artist counts
  Future<List<Map<String, dynamic>>> _searchBoth(String path, String exact, String loose) async {
    final results = await _search(path, exact);
    return results.isNotEmpty ? results : _search(path, loose);
  }

  static String _artistOf(Map<String, dynamic> result) => textKey((result['artist'] as Map?)?['name'] as String?);

  Future<String?> _findCover(String artist, String name) async {
    for (final title in {name, plainTitle(name)}) {
      final results = await _searchBoth('/search', 'artist:"$artist" track:"$title"', '$artist $title');
      for (final result in results) {
        if (_artistOf(result) == textKey(artist)) return (result['album'] as Map?)?['cover_big'] as String?;
      }
    }
    return null;
  }

  Future<String?> _findAlbumCover(String artist, String album) async {
    for (final title in {album, plainTitle(album)}) {
      final results = await _searchBoth('/search/album', 'artist:"$artist" album:"$title"', '$artist $title');
      for (final result in results) {
        if (_artistOf(result) == textKey(artist)) return result['cover_big'] as String?;
      }
    }
    return null;
  }

  Future<String?> _findArtistPhoto(String artist) async {
    for (final result in await _search('/search/artist', artist)) {
      final picture = result['picture_big'] as String? ?? '';
      if (textKey(result['name'] as String?) == textKey(artist) && !picture.contains(_emptyPicture)) return picture;
    }
    return null;
  }
}
