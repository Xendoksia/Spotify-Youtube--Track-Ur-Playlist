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

/// Raised when the models change, so the saved suggestions are worked out again with them at once
const modelVersion = 4;

/// More artists and songs are worked out than shown, so one hidden or moved down by the fame setting gives its
/// place to the next
const artistPool = 30;
const songPool = 20;

/// The fame setting (DISCOVER_FAME) ranks by the square root of an artist's score, so the model's first few do not
/// always stay on top, times ten for each power of ten it is better known (or lesser known) than the middle of the
/// suggestions, at most [fameLimit] times either way
const fameDirection = {'known': 1, 'balanced': 0, 'lesser': -1};
const fameLimit = 5.0;

/// ListenBrainz's listener counts, in the model, are about a hundredth of Deezer's fan counts, and low for many
/// artists Deezer knows well (Turkish ones above all), so the larger of the two on one scale is taken
const listenersScale = 2.0;

/// An artist's Deezer fans are looked up again after this long
const fansEvery = Duration(days: 30);
const retryIncomplete = Duration(hours: 1);

/// Copies of the repository's models/ files (see pubspec.yaml)
const modelAssets = [
  'assets/models/artists.json.gz',
  'assets/models/artist_neighbours.i32.gz',
  'assets/models/songs.json.gz',
  'assets/models/song_neighbours.i32.gz',
  'assets/models/song_neighbours_rp3.i32.gz',
];

/// The song model's version 2 ranks with its knn and RP3beta tables and fuses the two lists' first [rrfTop] by
/// reciprocal rank, as recommend.fuse
const rrfK = 60;
const rrfTop = 50;

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

  /// The song model's RP3beta neighbours, null without that table
  final Int32List? _rp3;

  Model._(this.names, this.artists, this.keys, this.listeners, this._ids, this._width, this._byKey, this._rp3);

  static Int32List _table(Uint8List file) {
    final raw = Uint8List.fromList(gzip.decode(file));
    return raw.buffer.asInt32List(0, raw.length ~/ 4); // little-endian, as Android itself
  }

  factory Model.parse(Uint8List items, Uint8List neighbours, {required bool songs, Uint8List? rp3}) {
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
    final ids = _table(neighbours);
    final second = rp3 == null ? null : _table(rp3);
    return Model._(names, artists, keys, listeners, ids, list.isEmpty ? 0 : ids.length ~/ list.length, byKey,
        second != null && second.length == ids.length ? second : null);
  }

  int? find(String key) => _byKey[loose(key)];

  bool get hasRp3 => _rp3 != null;

  List<int> neighbours(int index) => _row(_ids, index);

  List<int> neighboursRp3(int index) => _row(_rp3!, index);

  List<int> _row(Int32List ids, int index) =>
      [for (var i = index * _width; i < (index + 1) * _width; i++) if (ids[i] >= 0) ids[i]];
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
    // What each seed added to the score, as recommend.score
    final added = [
      for (final name in because) [name, parts[best]![name]! * pow(decay, used[name]!).toDouble()],
    ]..sort((a, b) => (b[1] as double).compareTo(a[1] as double));
    ranked.add({...item, 'score': bestValue, 'because': because, 'shares': added});
    for (final name in parts[best]!.keys) {
      used[name] = used[name]! + 1;
    }
  }
  return ranked;
}

/// The ranked lists fused: each song gets 1 / (rrfK + place + 1) from each list's first [rrfTop] it is in, most
/// first, the more listened first on a tie, then the songs further down fused the same way over the whole lists.
/// A song keeps the first list's entry, with the seeds of both
List<Item> fuse(List<List<Item>> lists) {
  final found = <String, Item>{};
  final top = <String, double>{}, all = <String, double>{};
  for (final ranking in lists) {
    for (final (place, item) in ranking.indexed) {
      final key = item['key'] as String;
      final entry = found.putIfAbsent(key, () => {...item, 'because': <String>[]});
      final because = entry['because'] as List<String>;
      for (final name in (item['because'] as List).cast<String>()) {
        if (!because.contains(name)) because.add(name);
      }
      if (place < rrfTop) top[key] = (top[key] ?? 0) + 1 / (rrfK + place + 1);
      all[key] = (all[key] ?? 0) + 1 / (rrfK + place + 1);
    }
  }
  double value(String key) => top[key] ?? all[key]!;
  final keys = found.keys.toList()
    ..sort((a, b) {
      final tier = (top.containsKey(a) ? 0 : 1).compareTo(top.containsKey(b) ? 0 : 1);
      if (tier != 0) return tier;
      final order = value(b).compareTo(value(a));
      return order != 0 ? order : ((found[b]!['fans'] as int?) ?? 0).compareTo((found[a]!['fans'] as int?) ?? 0);
    });
  return [for (final key in keys) {...found[key]!, 'score': value(key)}];
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

  /// An artist on Deezer, (id, fans): of the results with the same name, the one with most fans
  Future<(int, int)?> artist(String name) async {
    final same = (await data('/search/artist', {'q': name, 'limit': '10'}))
        .where((r) => fold(r['name'] as String? ?? '') == fold(name))
        .toList();
    if (same.isEmpty) return null;
    same.sort((a, b) => ((b['nb_fan'] as num?) ?? 0).compareTo((a['nb_fan'] as num?) ?? 0));
    return ((same.first['id'] as num).toInt(), ((same.first['nb_fan'] as num?) ?? 0).toInt());
  }

  Future<int?> artistId(String name) async => (await artist(name))?.$1;

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

/// How well known an artist is, about 2 to 7: the larger of its Deezer fans and its ListenBrainz listeners on the
/// same scale, in powers of ten
double fame(int listeners, int fans) =>
    max(log(1 + fans) / ln10, log(1 + listeners) / ln10 + listenersScale);

/// The suggested artists to show: without the hidden ones (by key), in the model's order for the balanced setting,
/// else with their scores weighed toward the better or the lesser known
List<Item> pickArtists(List<Item> artists, int limit, {Set<String> hidden = const {}, String setting = 'balanced'}) {
  final left = [for (final a in artists) if (!hidden.contains(artistMatch(a['name'] as String))) a];
  final direction = fameDirection[setting] ?? 0;
  if (direction != 0 && left.isNotEmpty) {
    final known = {for (final a in left) a: fame((a['listeners'] as int?) ?? 0, (a['deezer_fans'] as int?) ?? 0)};
    final middle = (known.values.toList()..sort())[known.length ~/ 2];
    double weight(Item a) =>
        sqrt(max(0, ((a['score'] as num?) ?? 0).toDouble())) *
        pow(10, direction * (known[a]! - middle)).toDouble().clamp(1 / fameLimit, fameLimit);
    // Sorted with the place as the tie-break, so equal weights keep the model's order
    final place = {for (final (i, a) in left.indexed) a: i};
    left.sort((a, b) {
      final order = weight(b).compareTo(weight(a));
      return order != 0 ? order : place[a]!.compareTo(place[b]!);
    });
  }
  return left.take(limit).toList();
}

/// Everything worked out from the models: {at, complete, artists, new, known, fans}. [fans] are the Deezer fans
/// looked up before, by artist key, {fans, at}, given back with the new ones; the songs leave out the artists
/// shown, the first [artistLimit] not [hidden] in the [setting]'s order
Future<Map<String, Object?>> workOut(List<Uint8List> files, List<PlayRow> plays, int now,
    {Deezer? deezer, Map<String, Object?> fans = const {}, Set<String> hidden = const {}, String setting = 'balanced'}) async {
  deezer ??= Deezer();
  final knownFans = {...fans};
  final artistModel = Model.parse(files[0], files[1], songs: false);
  final songModel = Model.parse(files[2], files[3], songs: true, rp3: files.length > 4 ? files[4] : null);
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
          {'name': artistModel.names[j], 'fans': artistModel.listeners[j], 'listeners': artistModel.listeners[j]},
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
  final artists = score(seeds, relatedOf, playedArtists, limit: artistPool);
  for (final artist in artists) {
    final name = artist['name'] as String;
    if (artist['listeners'] == null) {
      final index = artistModel.find(fold(name));
      if (index != null) artist['listeners'] = artistModel.listeners[index];
    }
    if (artist['listeners'] == null) {
      // A Deezer related artist's fans are Deezer's own
      artist['deezer_fans'] = artist['fans'];
    } else {
      final kept = (knownFans[artistMatch(name)] as Map?)?.cast<String, Object?>();
      if (kept != null && now - (kept['at'] as int) < fansEvery.inMilliseconds) {
        artist['deezer_fans'] = kept['fans'];
      } else {
        try {
          final found = await deezer.artist(name);
          artist['deezer_fans'] = found?.$2 ?? 0;
          artist['id'] ??= found?.$1;
          knownFans[artistMatch(name)] = {'fans': artist['deezer_fans'], 'at': now};
        } catch (_) {
          complete = false;
        }
      }
    }
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
  List<Item> ranked(List<int> Function(int) table) => score(songSeeds, {
        for (final seed in songSeeds)
          seed['key'] as String: [
            for (final j in table(songModel.find(seed['key'] as String)!).take(relatedCount))
              {'key': songModel.keys[j], 'name': songModel.names[j], 'artist': songModel.artists[j], 'fans': songModel.listeners[j]},
          ],
      }, playedSongs);
  final knn = ranked(songModel.neighbours);
  final songRanked = songModel.hasRp3 ? fuse([knn, ranked(songModel.neighboursRp3)]) : knn;
  final skip = {for (final a in pickArtists(artists, artistLimit, hidden: hidden, setting: setting)) a['key'] as String};
  final lists = <String, List<Item>>{'new': [], 'known': []};
  final perArtist = <String, int>{};
  for (final song in songRanked) {
    final names = creditParts(song['artist'] as String).map(artistMatch).toList();
    final known = names.any(playedArtists.contains);
    final target = lists[known ? 'known' : 'new']!;
    if (target.length >= songPool || (perArtist[names.first] ?? 0) >= songsPerArtist) continue;
    if (!known && skip.contains(names.first)) continue;
    perArtist[names.first] = (perArtist[names.first] ?? 0) + 1;
    target.add(song);
    if (lists.values.every((l) => l.length >= songPool)) break;
  }
  return {'at': now, 'model': modelVersion, 'complete': complete, 'artists': artists, ...lists, 'fans': knownFans};
}

/// The seeds named in why a suggestion came, the rest together
const whyNamed = 4;

/// What each seed added to a suggestion's score, (name, share of the whole, rest), the largest [whyNamed] by name
/// and the rest together with an empty name and how many they are as the share's count
typedef Why = ({String name, double share, int rest});

List<Why> whyOf(Item item) {
  final shares = [
    for (final pair in (item['shares'] as List?) ?? const [])
      if (pair is List && pair.length == 2) (pair[0] as String, (pair[1] as num).toDouble()),
  ];
  final total = shares.fold(0.0, (sum, s) => sum + s.$2);
  if (total <= 0) return [];
  return [
    for (final (name, share) in shares.take(whyNamed)) (name: name, share: share / total, rest: 0),
    if (shares.length > whyNamed)
      (
        name: '',
        share: shares.skip(whyNamed).fold(0.0, (sum, s) => sum + s.$2) / total,
        rest: shares.length - whyNamed,
      ),
  ];
}

/// The artists suggested each day are kept for the discovery report, the last [historyDays] days of them
const historyDays = 60;
const reportDays = 30;

/// A suggested artist among this many most played of the report's days has become a favorite
const favoriteTop = 10;

/// The report is about this many of the artists suggested, the favorites and the played ones first
const reportRows = 5;

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
    return Report(rows.take(reportRows).toList(), [for (final day in days.reversed) (day, history[day]!)]);
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

  factory Suggestions.of(Map<String, Object?> saved, List<PlayRow> plays,
      {Report? report, List<Hidden> hidden = const [], String setting = 'balanced'}) {
    final playedArtists = heardArtists(plays);
    final playedSongs = heardSongs(plays);
    final hiddenSongs = {for (final h in hidden) if (h.kind == 'song') h.key};
    List<Item> items(String name) => ((saved[name] as List?) ?? const []).cast<Map>().map((m) => m.cast<String, Object?>()).toList();
    List<Item> songs(String name) => [
          for (final song in items(name))
            if (!playedSongs.contains(loose(song['key'] as String)) && !hiddenSongs.contains(loose(song['key'] as String)))
              song,
        ].take(songLimit).toList();
    final artists = [
      for (final artist in items('artists'))
        if (!playedArtists.contains(artistMatch(artist['name'] as String)))
          {
            ...artist,
            'tracks': [
              for (final track in (artist['tracks'] as List).cast<Map>())
                if (!playedSongs.contains(songKey(track['artist'] as String, track['title'] as String))) track,
            ],
          },
    ];
    return Suggestions(
      pickArtists(artists, artistLimit, hidden: {for (final h in hidden) if (h.kind == 'artist') h.key}, setting: setting),
      songs('new'),
      songs('known'),
      report,
    );
  }
}

/// A suggestion left out for good, as the desktop app's DISCOVER_HIDDEN: an artist by its artistMatch key or a
/// song by its loose model key, with the name shown in the list of hidden ones
typedef Hidden = ({String kind, String key, String name});

const hiddenSetting = 'DISCOVER_HIDDEN';
const fameSetting = 'DISCOVER_FAME';

List<Hidden> hiddenFrom(Object? list) => [
      if (list is List)
        for (final item in list.whereType<Map>())
          (kind: '${item['kind']}', key: '${item['key']}', name: '${item['name']}'),
    ];

List<Map<String, String>> hiddenJson(List<Hidden> hidden) =>
    [for (final h in hidden) {'kind': h.kind, 'key': h.key, 'name': h.name}];

/// The hidden suggestions and the fame setting kept on the phone
List<Hidden> readHidden(SharedPreferences prefs) {
  try {
    return hiddenFrom(jsonDecode(prefs.getString(hiddenSetting) ?? '[]'));
  } catch (_) {
    return [];
  }
}

String readFame(SharedPreferences prefs) {
  final setting = prefs.getString(fameSetting);
  return fameDirection.containsKey(setting) ? setting! : 'balanced';
}


List<PlayRow> playRows(List<Play> plays) =>
    [for (final p in plays) (artist: p.artist, name: p.name, at: p.playedAt.millisecondsSinceEpoch)];

/// The model files, read here and handed to an isolate: an isolate cannot read the app's assets itself
Future<List<Uint8List>> _readModels(Iterable<String> paths) async =>
    [for (final path in paths) (await rootBundle.load(path)).buffer.asUint8List()];

const _savedKey = 'DISCOVER';
const _historyKey = 'DISCOVER_HISTORY';
const _fansKey = 'DISCOVER_FANS';

Future<Suggestions>? _working;

/// The suggestions: the saved ones while they are fresh, else worked out again on a background isolate. Asked
/// again while they are being worked out, as when the page opens just after the app's start began them, the same
/// answer is waited for
Future<Suggestions> discover(List<Play> plays, {DateTime? now}) =>
    _working ??= _discover(plays, now).whenComplete(() => _working = null);

Future<Suggestions> _discover(List<Play> plays, DateTime? now) async {
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
      saved!['model'] != modelVersion ||
      (saved['complete'] != true && age >= retryIncomplete);
  var history = <String, List<String>>{};
  try {
    history = (jsonDecode(prefs.getString(_historyKey) ?? '{}') as Map)
        .map((day, names) => MapEntry(day as String, (names as List).cast<String>()));
  } catch (_) {}
  List<String> names(Map<String, Object?> found) =>
      [for (final artist in (found['artists'] as List).cast<Map>()) artist['name'] as String];
  final hidden = readHidden(prefs);
  final setting = readFame(prefs);
  final hiddenArtists = {for (final h in hidden) if (h.kind == 'artist') h.key};
  List<String> shown(Map<String, Object?> found) => [
        for (final artist in pickArtists((found['artists'] as List).cast<Map>().map((m) => m.cast<String, Object?>()).toList(),
            artistLimit,
            hidden: hiddenArtists, setting: setting))
          artist['name'] as String,
      ];
  if (stale && rows.isNotEmpty) {
    final files = await _readModels(modelAssets);
    Map<String, Object?> fans = {};
    try {
      fans = (jsonDecode(prefs.getString(_fansKey) ?? '{}') as Map).cast<String, Object?>();
    } catch (_) {}
    final found = await Isolate.run(() => workOut(files, rows, moment, fans: fans, hidden: hiddenArtists, setting: setting));
    await prefs.setString(_fansKey, jsonEncode(found.remove('fans')));
    saved = found;
    await prefs.setString(_savedKey, jsonEncode(saved));
    history = remember(history, shown(saved), DateTime.fromMillisecondsSinceEpoch(moment));
    await prefs.setString(_historyKey, jsonEncode(history));
  } else if (saved != null && history.isEmpty) {
    // Suggestions saved before the history was kept start it, on the day they were worked out
    history = remember(history, names(saved).take(artistLimit).toList(), DateTime.fromMillisecondsSinceEpoch(saved['at'] as int));
    await prefs.setString(_historyKey, jsonEncode(history));
  }
  if (saved == null) return const Suggestions([], [], []);
  return Suggestions.of(saved, rows,
      report: Report.of(history, rows, DateTime.fromMillisecondsSinceEpoch(moment)), hidden: hidden, setting: setting);
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

/// The song model finds mostly the same artist's songs alike, so a song's page takes at most this many of its own
/// artist's and of any other, and the rest from the artists most alike to its artist
const alikeSameArtist = 2;
const alikePerArtist = 2;

/// The model's songs of each artist (by its first artist's key), most listened first
Map<String, List<int>> songsByArtist(Model songs) {
  final found = <String, List<int>>{};
  for (var i = 0; i < songs.keys.length; i++) {
    (found[loose(songs.keys[i].split('|').first)] ??= []).add(i);
  }
  for (final list in found.values) {
    list.sort((a, b) => songs.listeners[b].compareTo(songs.listeners[a]));
  }
  return found;
}

/// The songs most alike to a song, as the desktop app's recommend.alike_songs: the song model's first
/// ([alikeSameArtist] of its own artist, [alikePerArtist] of each other), then the most listened unplayed song of
/// each artist the artist model finds most alike to its artist
List<Alike> alikeSongs(Model songs, Model artists, Map<String, List<int>> songsOf, String artist, String title,
    Set<String> played, int limit) {
  final own = artistMatch(creditParts(artist).first);
  final seen = {songKey(artist, title)};
  final per = <String, int>{};
  final found = <Alike>[];
  bool add(int j) {
    final key = loose(songs.keys[j]);
    final by = loose(songs.keys[j].split('|').first);
    if (seen.contains(key) || (per[by] ?? 0) >= (by == own ? alikeSameArtist : alikePerArtist)) return false;
    seen.add(key);
    per[by] = (per[by] ?? 0) + 1;
    found.add((artist: songs.artists[j], title: songs.names[j], key: key));
    return true;
  }

  final index = songs.find(songKey(artist, title));
  for (final j in index == null ? const <int>[] : songs.neighbours(index)) {
    if (found.length == limit) return found;
    add(j);
  }
  for (final other in alikeIn(artists, own, 50, songs: false)) {
    if (found.length == limit) break;
    final theirs = songsOf[other.key] ?? const <int>[];
    if ((per[other.key] ?? 0) > 0 || theirs.isEmpty) continue;
    final unplayed = theirs.where((j) => !played.contains(loose(songs.keys[j])));
    add(unplayed.isEmpty ? theirs.first : unplayed.first);
  }
  return found;
}

void _serveModels((SendPort, List<Uint8List>) start) {
  final (reply, files) = start;
  final artists = Model.parse(files[0], files[1], songs: false);
  final songs = Model.parse(files[2], files[3], songs: true);
  final songsOf = songsByArtist(songs);
  final requests = ReceivePort();
  reply.send(requests.sendPort);
  requests.listen((message) {
    final (artist, title, played, limit, answer) = message as (String, String, Set<String>, int, SendPort);
    answer.send(title.isEmpty
        ? alikeIn(artists, artistMatch(artist), limit, songs: false)
        : alikeSongs(songs, artists, songsOf, artist, title, played, limit));
  });
}

/// The two models on a background isolate for the track and artist pages, loaded ahead a little after the app
/// opens so that a page's first alike songs come at once, kept while the app is in front and let go after a while
/// in the background, as they take some 80 MB
class ModelWorker {
  /// The alike songs use the knn table alone, so the RP3beta one is not loaded here
  static final instance = ModelWorker();
  static const idle = Duration(minutes: 2);

  Future<SendPort>? _port;
  Isolate? _isolate;
  Timer? _idle;
  var _inFront = true;

  Future<SendPort> _start() async {
    final files = await _readModels(modelAssets.take(4));
    final ready = ReceivePort();
    _isolate = await Isolate.spawn(_serveModels, (ready.sendPort, files));
    final port = await ready.first as SendPort;
    ready.close();
    return port;
  }

  /// Load the models ahead, before a page asks
  Future<void> warm() async {
    _idle?.cancel();
    await (_port ??= _start());
    if (!_inFront) _letGoLater();
  }

  /// The app went to the background or came back: the models are let go after [idle] in the background
  void inFront(bool value) {
    _inFront = value;
    if (value) {
      _idle?.cancel();
    } else if (_port != null) {
      _letGoLater();
    }
  }

  void _letGoLater() {
    _idle?.cancel();
    _idle = Timer(idle, () {
      _isolate?.kill();
      _isolate = null;
      _port = null;
    });
  }

  Future<List<Alike>> _ask(String artist, String title, Set<String> played, int limit) async {
    _idle?.cancel();
    try {
      final port = await (_port ??= _start());
      final answer = ReceivePort();
      port.send((artist, title, played, limit, answer.sendPort));
      final found = await answer.first as List<Alike>;
      answer.close();
      return found;
    } finally {
      if (!_inFront) _letGoLater();
    }
  }

  /// [played] are the played songs' keys (songKey), so an alike artist's song is one not played yet
  Future<List<Alike>> songs(String artist, String title, Set<String> played, {int limit = 12}) =>
      _ask(artist, title, played, limit);

  Future<List<Alike>> artists(String name, {int limit = 12}) => _ask(name, '', const {}, limit);
}
