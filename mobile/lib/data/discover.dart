/// Artists and songs to discover, as the desktop app's music/recommend.py: the artist and song models in the
/// repository's models/ folder (bundled with the app) list what is alike to the artists and songs played most
/// lately, an artist the model does not know is looked up on Deezer, and what is already played is left out.
/// Worked out at most once a day on a background isolate and saved, and between two only the artists and songs
/// played since are taken out.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io' show gzip;
import 'dart:isolate';
import 'dart:math';
import 'dart:typed_data';

import 'package:flutter/services.dart' show rootBundle;
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'models.dart';
import 'search.dart' show fold;
import 'stats.dart' show plainTitle;

/// The model's settings, which did best in its tests (models/README.md)
const seedCount = 30;
const relatedCount = 50;
const seedDecay = 0.75;

/// A play counts half as much after this many days, so the suggestions follow what is played lately
const halfLifeDays = 30;
const topTracks = 3;
const artistLimit = 11;
const songLimit = 10;

/// At most this many suggested songs of one artist in a list
const songsPerArtist = 2;

/// Worked out again after this long, and an incomplete answer (Deezer unreachable) after the shorter one
const discoverEvery = Duration(hours: 24);
const retryIncomplete = Duration(hours: 1);

/// Copies of the repository's models/ files (see pubspec.yaml)
const modelAssets = [
  'assets/models/artists.json.gz',
  'assets/models/artist_neighbours.i32.gz',
  'assets/models/songs.json.gz',
  'assets/models/song_neighbours.i32.gz',
];

const _deezer = 'https://api.deezer.com';

/// A key without punctuation: the data spells "What I've Done" with a straight and a curly apostrophe alike
String loose(String key) =>
    key.replaceAll(RegExp(r'[^\p{L}\p{N}_|]+', unicode: true), ' ').split(' ').where((w) => w.isNotEmpty).join(' ');

/// A song as the song model keys it: its first artist and its title without version notes
String songKey(String artist, String title) => loose('${fold(creditParts(artist).first)}|${fold(plainTitle(title))}');

/// An artist as the artist model keys it
String artistMatch(String name) => loose(fold(name));

/// What the suggestions start from: each play, by whom and when
typedef PlayRow = ({String artist, String name, int at});

/// One of the two models: its items and, for each, the most alike ones, best first
class Model {
  final List<String> names;

  /// A song's artist, empty for the artist model
  final List<String> artists;
  final List<String> keys;
  final List<int> listeners;
  final Int32List _ids;
  final int _width;
  final Map<String, int> _byKey;

  Model._(this.names, this.artists, this.keys, this.listeners, this._ids, this._width, this._byKey);

  factory Model.parse(Uint8List items, Uint8List neighbours, {required bool songs}) {
    final list = (jsonDecode(utf8.decode(gzip.decode(items))) as List).cast<Map<String, dynamic>>();
    final names = <String>[], artists = <String>[], keys = <String>[], listeners = <int>[];
    final byKey = <String, int>{};
    for (final (index, item) in list.indexed) {
      names.add((songs ? item['title'] : item['name']) as String);
      artists.add(songs ? item['artist'] as String : '');
      keys.add(item['key'] as String);
      listeners.add((item['listeners'] as num).toInt());
      // Of the names with the same key, apart from punctuation, the one with most listeners
      final key = loose(item['key'] as String);
      final known = byKey[key];
      if (known == null || listeners[index] > listeners[known]) byKey[key] = index;
    }
    final raw = Uint8List.fromList(gzip.decode(neighbours));
    final ids = raw.buffer.asInt32List(0, raw.length ~/ 4); // little-endian, as Android itself
    return Model._(names, artists, keys, listeners, ids, list.isEmpty ? 0 : ids.length ~/ list.length, byKey);
  }

  int? find(String key) => _byKey[loose(key)];

  List<int> neighbours(int index) =>
      [for (var i = index * _width; i < (index + 1) * _width; i++) if (_ids[i] >= 0) _ids[i]];
}

/// A seed or a candidate: candidates carry what the page shows of them
typedef Item = Map<String, Object?>;

/// Rank the related items not played yet, as recommend.score: each seed adds its weight, scaled down the lower the
/// item is in its list, picked one at a time, each pick lowering what its seeds add to the rest
List<Item> score(List<Item> seeds, Map<String, List<Item>> relatedOf, Set<String> played,
    {double decay = seedDecay, int size = relatedCount, int? limit}) {
  final shares = <String, Item>{};
  final parts = <String, Map<String, double>>{};
  for (final seed in seeds) {
    final candidates = relatedOf[seed['key']] ?? const [];
    for (final (place, item) in candidates.indexed) {
      final key = loose((item['key'] as String?) ?? fold(item['name'] as String));
      if (played.contains(key)) continue;
      final entry = shares.putIfAbsent(key, () => {...item, 'key': key});
      if (entry['id'] == null && item['id'] != null) entry['id'] = item['id'];
      final share = (seed['weight'] as double) * (1 - place / max(candidates.length, size));
      final mine = parts.putIfAbsent(key, () => {});
      mine[seed['name'] as String] = (mine[seed['name']] ?? 0) + share;
    }
  }
  final used = {for (final seed in seeds) seed['name'] as String: 0};
  double value(String key) =>
      parts[key]!.entries.fold(0.0, (sum, e) => sum + e.value * pow(decay, used[e.key]!).toDouble());
  final ranked = <Item>[];
  while (shares.isNotEmpty && (limit == null || ranked.length < limit)) {
    String? best;
    var bestValue = -1.0;
    for (final key in shares.keys) {
      final v = value(key);
      final fans = (shares[key]!['fans'] as int?) ?? 0;
      if (v > bestValue || (v == bestValue && fans > ((shares[best]!['fans'] as int?) ?? 0))) {
        best = key;
        bestValue = v;
      }
    }
    final item = shares.remove(best)!;
    final because = parts[best]!.keys.toList()..sort((a, b) => parts[best]![b]!.compareTo(parts[best]![a]!));
    ranked.add({...item, 'score': bestValue, 'because': because});
    for (final name in parts[best]!.keys) {
      used[name] = used[name]! + 1;
    }
  }
  return ranked;
}

double _weight(int at, int now) => pow(0.5, max(0, now - at) / Duration.millisecondsPerDay / halfLifeDays).toDouble();

/// The artists played most lately, a collaboration counting for the artists it credits
List<Item> artistSeeds(List<PlayRow> plays, int now) {
  final solo = knownArtists(plays.map((p) => p.artist));
  final found = <String, Item>{};
  for (final play in plays) {
    for (final part in credited(play.artist, solo)) {
      final entry = found.putIfAbsent(textKey(part), () => {'key': textKey(part), 'name': part, 'weight': 0.0});
      entry['weight'] = (entry['weight'] as double) + _weight(play.at, now);
    }
  }
  return (found.values.toList()..sort((a, b) => (b['weight'] as double).compareTo(a['weight'] as double)))
      .take(seedCount)
      .toList();
}

Set<String> heardArtists(Iterable<PlayRow> plays) =>
    {for (final play in plays) for (final part in creditParts(play.artist)) artistMatch(part)};

Set<String> heardSongs(Iterable<PlayRow> plays) => {for (final play in plays) songKey(play.artist, play.name)};

/// Deezer's answers, spaced out as Deezer allows 50 requests in 5 seconds; an error answer is raised
class Deezer {
  final Future<Object?> Function(Uri url) fetch;
  DateTime _next = DateTime(0);

  Deezer([Future<Object?> Function(Uri url)? fetch]) : fetch = fetch ?? _get;

  static Future<Object?> _get(Uri url) async {
    final response = await http.get(url).timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) throw http.ClientException('HTTP ${response.statusCode}', url);
    return jsonDecode(utf8.decode(response.bodyBytes));
  }

  Future<List<Map<String, dynamic>>> data(String path, [Map<String, String>? query]) async {
    final wait = _next.difference(DateTime.now());
    _next = (wait.isNegative ? DateTime.now() : _next).add(const Duration(milliseconds: 150));
    if (!wait.isNegative) await Future<void>.delayed(wait);
    final answer = await fetch(Uri.parse('$_deezer$path').replace(queryParameters: query));
    if (answer is Map && answer['error'] != null) throw StateError('Deezer: ${answer['error']}');
    final list = answer is Map ? answer['data'] : null;
    return list is List ? list.whereType<Map<String, dynamic>>().toList() : [];
  }

  /// The Deezer id of an artist: of the results with the same name, the one with most fans
  Future<int?> artistId(String name) async {
    final same = (await data('/search/artist', {'q': name, 'limit': '10'}))
        .where((r) => fold(r['name'] as String? ?? '') == fold(name))
        .toList();
    if (same.isEmpty) return null;
    same.sort((a, b) => ((b['nb_fan'] as num?) ?? 0).compareTo((a['nb_fan'] as num?) ?? 0));
    return (same.first['id'] as num).toInt();
  }

  Future<List<Item>> related(String name) async {
    final id = await artistId(name);
    if (id == null) return [];
    return [
      for (final a in await data('/artist/$id/related', {'limit': '20'}))
        {'id': (a['id'] as num).toInt(), 'name': a['name'] as String, 'fans': ((a['nb_fan'] as num?) ?? 0).toInt()},
    ];
  }

  Future<List<Item>> top(int id) async {
    final seen = <String>{};
    return [
      for (final t in await data('/artist/$id/top', {'limit': '8'}))
        if (seen.add(fold(plainTitle((t['title_short'] ?? t['title']) as String))))
          {'title': (t['title_short'] ?? t['title']) as String, 'artist': (t['artist'] as Map?)?['name'] ?? ''},
    ];
  }
}

/// Everything worked out from the models: {at, complete, artists, new, known}
Future<Map<String, Object?>> workOut(List<Uint8List> files, List<PlayRow> plays, int now, {Deezer? deezer}) async {
  deezer ??= Deezer();
  final artistModel = Model.parse(files[0], files[1], songs: false);
  final songModel = Model.parse(files[2], files[3], songs: true);
  final playedArtists = heardArtists(plays);
  final playedSongs = heardSongs(plays);
  var complete = true;

  // Artists
  final seeds = artistSeeds(plays, now);
  final relatedOf = <String, List<Item>>{};
  for (final seed in seeds) {
    final index = artistModel.find(fold(seed['name'] as String));
    if (index != null) {
      relatedOf[seed['key'] as String] = [
        for (final j in artistModel.neighbours(index).take(relatedCount))
          {'name': artistModel.names[j], 'fans': artistModel.listeners[j]},
      ];
    } else {
      try {
        relatedOf[seed['key'] as String] = await deezer.related(seed['name'] as String);
      } catch (_) {
        complete = false;
      }
    }
  }
  final songsOf = <String, List<int>>{};
  for (var i = 0; i < songModel.keys.length; i++) {
    songsOf.putIfAbsent(loose(songModel.keys[i].split('|').first), () => []).add(i);
  }
  final artists = score(seeds, relatedOf, playedArtists, limit: artistLimit);
  for (final artist in artists) {
    final seen = {...playedSongs};
    final own = (songsOf[artistMatch(artist['name'] as String)] ?? [])
      ..sort((a, b) => songModel.listeners[b].compareTo(songModel.listeners[a]));
    var tracks = <Item>[
      for (final i in own)
        if (seen.add(loose(songModel.keys[i]))) {'title': songModel.names[i], 'artist': songModel.artists[i]},
    ].take(topTracks).toList();
    if (tracks.isEmpty) {
      try {
        final id = (artist['id'] as int?) ?? await deezer.artistId(artist['name'] as String);
        if (id != null) {
          tracks = (await deezer.top(id))
              .where((t) => !playedSongs.contains(songKey(t['artist'] as String, t['title'] as String)))
              .take(topTracks)
              .toList();
        }
      } catch (_) {
        complete = false;
      }
    }
    artist['tracks'] = tracks;
  }

  // Songs: the songs played most lately that the model knows
  final songSeedsFound = <String, Item>{};
  for (final play in plays) {
    final key = songKey(play.artist, play.name);
    final entry = songSeedsFound.putIfAbsent(key, () => {'key': key, 'name': plainTitle(play.name), 'weight': 0.0});
    entry['weight'] = (entry['weight'] as double) + _weight(play.at, now);
  }
  final songSeeds = (songSeedsFound.values.where((s) => songModel.find(s['key'] as String) != null).toList()
        ..sort((a, b) => (b['weight'] as double).compareTo(a['weight'] as double)))
      .take(seedCount)
      .toList();
  final songRelated = {
    for (final seed in songSeeds)
      seed['key'] as String: [
        for (final j in songModel.neighbours(songModel.find(seed['key'] as String)!).take(relatedCount))
          {'key': songModel.keys[j], 'name': songModel.names[j], 'artist': songModel.artists[j], 'fans': songModel.listeners[j]},
      ],
  };
  final skip = {for (final a in artists) a['key'] as String};
  final lists = <String, List<Item>>{'new': [], 'known': []};
  final perArtist = <String, int>{};
  for (final song in score(songSeeds, songRelated, playedSongs)) {
    final names = creditParts(song['artist'] as String).map(artistMatch).toList();
    final known = names.any(playedArtists.contains);
    final target = lists[known ? 'known' : 'new']!;
    if (target.length >= songLimit || (perArtist[names.first] ?? 0) >= songsPerArtist) continue;
    if (!known && skip.contains(names.first)) continue;
    perArtist[names.first] = (perArtist[names.first] ?? 0) + 1;
    target.add(song);
    if (lists.values.every((l) => l.length >= songLimit)) break;
  }
  return {'at': now, 'complete': complete, 'artists': artists, ...lists};
}

/// The artists suggested each day are kept for the discovery report, the last [historyDays] days of them
const historyDays = 60;
const reportDays = 30;

/// A suggested artist among this many most played of the report's days has become a favorite
const favoriteTop = 10;

String dayKey(DateTime moment) {
  final local = moment.toLocal();
  String two(int n) => n.toString().padLeft(2, '0');
  return '${local.year}-${two(local.month)}-${two(local.day)}';
}

DateTime _dayStart(String day) => DateTime.parse(day); // a date alone parses as local midnight

/// The history with the day's suggested artists, a day worked out again keeping the newer ones
Map<String, List<String>> remember(Map<String, List<String>> history, List<String> names, DateTime now) {
  final oldest = _dayStart(dayKey(now)).subtract(const Duration(days: historyDays));
  return {
    for (final entry in history.entries)
      if (_dayStart(entry.key).isAfter(oldest)) entry.key: entry.value,
    dayKey(now): names,
  };
}

enum ReportState { favorite, listened, untried }

class ReportRow {
  final String name;
  final String day;
  final int plays;
  final ReportState state;

  const ReportRow(this.name, this.day, this.plays, this.state);
}

/// Which artists suggested in the last [reportDays] days were played from the day they were first suggested, as
/// the desktop app's recommend.report
class Report {
  final List<ReportRow> rows;

  /// The suggestions by day, newest first
  final List<(String, List<String>)> days;

  const Report(this.rows, this.days);

  int get listened => rows.where((r) => r.state != ReportState.untried).length;
  int get favorites => rows.where((r) => r.state == ReportState.favorite).length;

  factory Report.of(Map<String, List<String>> history, List<PlayRow> plays, DateTime now) {
    final start = _dayStart(dayKey(now)).subtract(const Duration(days: reportDays - 1));
    final days = history.keys.where((day) => !_dayStart(day).isBefore(start)).toList()..sort();
    final first = <String, (String, String)>{};
    for (final day in days) {
      for (final name in history[day]!) {
        first.putIfAbsent(artistMatch(name), () => (day, name));
      }
    }
    final solo = knownArtists(plays.map((p) => p.artist));
    final counts = <String, int>{};
    final times = <String, List<int>>{};
    for (final play in plays) {
      if (play.at < start.millisecondsSinceEpoch) continue;
      for (final part in credited(play.artist, solo)) {
        final key = artistMatch(part);
        counts[key] = (counts[key] ?? 0) + 1;
        (times[key] ??= []).add(play.at);
      }
    }
    final top = (counts.keys.toList()..sort((a, b) => counts[b]!.compareTo(counts[a]!))).take(favoriteTop).toSet();
    final rows = <ReportRow>[];
    for (final MapEntry(:key, value: (day, name)) in first.entries) {
      final since = _dayStart(day).millisecondsSinceEpoch;
      final after = (times[key] ?? const <int>[]).where((at) => at >= since).length;
      final state = after == 0
          ? ReportState.untried
          : top.contains(key)
              ? ReportState.favorite
              : ReportState.listened;
      rows.add(ReportRow(name, day, after, state));
    }
    rows.sort((a, b) {
      final order = a.state.index.compareTo(b.state.index);
      if (order != 0) return order;
      final played = b.plays.compareTo(a.plays);
      return played != 0 ? played : a.day.compareTo(b.day);
    });
    return Report(rows, [for (final day in days.reversed) (day, history[day]!)]);
  }
}

/// The suggestions on the page, without what is played since they were worked out
class Suggestions {
  final List<Item> artists;
  final List<Item> newSongs;
  final List<Item> knownSongs;
  final Report? report;

  const Suggestions(this.artists, this.newSongs, this.knownSongs, [this.report]);

  bool get isEmpty => artists.isEmpty && newSongs.isEmpty && knownSongs.isEmpty;

  factory Suggestions.of(Map<String, Object?> saved, List<PlayRow> plays, [Report? report]) {
    final playedArtists = heardArtists(plays);
    final playedSongs = heardSongs(plays);
    List<Item> items(String name) => ((saved[name] as List?) ?? const []).cast<Map>().map((m) => m.cast<String, Object?>()).toList();
    return Suggestions(
      [
        for (final artist in items('artists'))
          if (!playedArtists.contains(artistMatch(artist['name'] as String)))
            {
              ...artist,
              'tracks': [
                for (final track in (artist['tracks'] as List).cast<Map>())
                  if (!playedSongs.contains(songKey(track['artist'] as String, track['title'] as String))) track,
              ],
            },
      ],
      [for (final song in items('new')) if (!playedSongs.contains(loose(song['key'] as String))) song],
      [for (final song in items('known')) if (!playedSongs.contains(loose(song['key'] as String))) song],
      report,
    );
  }
}

List<PlayRow> playRows(List<Play> plays) =>
    [for (final p in plays) (artist: p.artist, name: p.name, at: p.playedAt.millisecondsSinceEpoch)];

const _savedKey = 'DISCOVER';
const _historyKey = 'DISCOVER_HISTORY';

/// The suggestions: the saved ones while they are fresh, else worked out again on a background isolate
Future<Suggestions> discover(List<Play> plays, {DateTime? now}) async {
  final rows = playRows(plays);
  final moment = (now ?? DateTime.now()).millisecondsSinceEpoch;
  final prefs = await SharedPreferences.getInstance();
  Map<String, Object?>? saved;
  try {
    saved = (jsonDecode(prefs.getString(_savedKey) ?? 'null') as Map?)?.cast<String, Object?>();
  } catch (_) {}
  final age = saved == null ? null : Duration(milliseconds: moment - (saved['at'] as int));
  final stale = age == null ||
      age >= discoverEvery ||
      age.isNegative ||
      (saved!['complete'] != true && age >= retryIncomplete);
  var history = <String, List<String>>{};
  try {
    history = (jsonDecode(prefs.getString(_historyKey) ?? '{}') as Map)
        .map((day, names) => MapEntry(day as String, (names as List).cast<String>()));
  } catch (_) {}
  List<String> names(Map<String, Object?> found) =>
      [for (final artist in (found['artists'] as List).cast<Map>()) artist['name'] as String];
  if (stale && rows.isNotEmpty) {
    final files = [for (final path in modelAssets) (await rootBundle.load(path)).buffer.asUint8List()];
    saved = await Isolate.run(() => workOut(files, rows, moment));
    await prefs.setString(_savedKey, jsonEncode(saved));
    history = remember(history, names(saved!), DateTime.fromMillisecondsSinceEpoch(moment));
    await prefs.setString(_historyKey, jsonEncode(history));
  } else if (saved != null && history.isEmpty) {
    // Suggestions saved before the history was kept start it, on the day they were worked out
    history = remember(history, names(saved), DateTime.fromMillisecondsSinceEpoch(saved['at'] as int));
    await prefs.setString(_historyKey, jsonEncode(history));
  }
  if (saved == null) return const Suggestions([], [], []);
  return Suggestions.of(saved, rows, Report.of(history, rows, DateTime.fromMillisecondsSinceEpoch(moment)));
}

/// One of the most alike songs or artists: a song's artist and title, or an artist's name with an empty title
typedef Alike = ({String artist, String title, String key});

/// What the models find most alike, best first: [] when the model does not know it
List<Alike> alikeIn(Model model, String key, int limit, {required bool songs}) {
  final index = model.find(key);
  if (index == null) return [];
  final seen = {loose(model.keys[index])};
  final found = <Alike>[];
  for (final j in model.neighbours(index)) {
    // The same song may be in the model twice, spelt with different punctuation
    if (!seen.add(loose(model.keys[j]))) continue;
    found.add(songs
        ? (artist: model.artists[j], title: model.names[j], key: loose(model.keys[j]))
        : (artist: model.names[j], title: '', key: loose(model.keys[j])));
    if (found.length == limit) break;
  }
  return found;
}

void _serveModels((SendPort, List<Uint8List>) start) {
  final (reply, files) = start;
  final artists = Model.parse(files[0], files[1], songs: false);
  final songs = Model.parse(files[2], files[3], songs: true);
  final requests = ReceivePort();
  reply.send(requests.sendPort);
  requests.listen((message) {
    final (songsAsked, key, limit, answer) = message as (bool, String, int, SendPort);
    answer.send(alikeIn(songsAsked ? songs : artists, key, limit, songs: songsAsked));
  });
}

/// The two models on a background isolate for the track and artist pages, loaded on first use and let go after
/// a while unused, as they take some 80 MB
class ModelWorker {
  static final instance = ModelWorker();
  static const idle = Duration(minutes: 2);

  Future<SendPort>? _port;
  Isolate? _isolate;
  Timer? _idle;

  Future<SendPort> _start() async {
    final files = [for (final path in modelAssets) (await rootBundle.load(path)).buffer.asUint8List()];
    final ready = ReceivePort();
    _isolate = await Isolate.spawn(_serveModels, (ready.sendPort, files));
    final port = await ready.first as SendPort;
    ready.close();
    return port;
  }

  Future<List<Alike>> _ask(bool songs, String key, int limit) async {
    _idle?.cancel();
    try {
      final port = await (_port ??= _start());
      final answer = ReceivePort();
      port.send((songs, key, limit, answer.sendPort));
      final found = await answer.first as List<Alike>;
      answer.close();
      return found;
    } finally {
      _idle = Timer(idle, () {
        _isolate?.kill();
        _isolate = null;
        _port = null;
      });
    }
  }

  Future<List<Alike>> songs(String artist, String title, {int limit = 12}) => _ask(true, songKey(artist, title), limit);

  Future<List<Alike>> artists(String name, {int limit = 12}) => _ask(false, artistMatch(name), limit);
}
