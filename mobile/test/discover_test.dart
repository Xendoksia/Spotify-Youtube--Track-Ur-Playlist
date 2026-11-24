import 'dart:convert';
import 'dart:io' show File, gzip;
import 'dart:typed_data';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:playlist_tracker/data/discover.dart';

final now = DateTime.utc(2026, 11, 20, 12).millisecondsSinceEpoch;

PlayRow play(String artist, String name, {int hoursAgo = 26}) =>
    (artist: artist, name: name, at: now - hoursAgo * Duration.millisecondsPerHour);

List<Uint8List> files(List<Map<String, Object>> items, List<List<int>> neighbours) {
  final ids = Int32List.fromList([for (final row in neighbours) ...[...row, -1, -1, -1].take(3)]);
  return [
    Uint8List.fromList(gzip.encode(utf8.encode(jsonEncode(items)))),
    Uint8List.fromList(gzip.encode(ids.buffer.asUint8List())),
  ];
}

/// Metallica is alike to Megadeth and Slayer, Göksel to Sertab Erener. One is alike to Megadeth's Symphony of
/// Destruction, Metallica's Fade to Black and the played Enter Sandman.
final models = [
  ...files([
    {'name': 'Metallica', 'key': 'metallica', 'listeners': 900},
    {'name': 'Megadeth', 'key': 'megadeth', 'listeners': 500},
    {'name': 'Slayer', 'key': 'slayer', 'listeners': 400},
    {'name': 'Göksel', 'key': 'goksel', 'listeners': 300},
    {'name': 'Sertab Erener', 'key': 'sertab erener', 'listeners': 200},
  ], [[1, 2], [0], [0], [4], [3]]),
  ...files([
    {'artist': 'Metallica', 'title': 'One', 'key': 'metallica|one', 'listeners': 90},
    {'artist': 'Megadeth', 'title': 'Symphony of Destruction', 'key': 'megadeth|symphony of destruction', 'listeners': 50},
    {'artist': 'Metallica', 'title': 'Fade to Black', 'key': 'metallica|fade to black', 'listeners': 70},
    {'artist': 'Metallica', 'title': 'Enter Sandman', 'key': 'metallica|enter sandman', 'listeners': 95},
    {'artist': 'Slayer', 'title': 'Raining Blood', 'key': 'slayer|raining blood', 'listeners': 40},
    {'artist': 'Metallica', 'title': 'Fade To Black!', 'key': 'metallica|fade to black!', 'listeners': 10},
  ], [[1, 2, 3], [0], [0], [0], [1], [0]]),
];

class NoDeezer extends Deezer {
  var asked = 0;
  NoDeezer() : super((url) async => {'data': []});

  @override
  Future<List<Map<String, dynamic>>> data(String path, [Map<String, String>? query]) async {
    asked++;
    return [];
  }
}

void main() {
  test('unplayed artists with their unplayed songs, and Deezer is not asked for what the model knows', () async {
    final deezer = NoDeezer();
    final found = await workOut(models, [play('Metallica', 'One - Remastered')], now, deezer: deezer);
    final artists = (found['artists'] as List).cast<Map>();
    expect(artists.map((a) => a['name']), ['Megadeth', 'Slayer']);
    expect((artists[1]['tracks'] as List).first['title'], 'Raining Blood');
    expect(deezer.asked, 0);
    expect(found['complete'], true);
  });

  test('songs leave out played ones, spelt any way, and split new and known artists', () async {
    final found = await workOut(models, [play('Metallica', 'One'), play('Metallica', 'Enter Sandman')], now,
        deezer: NoDeezer());
    // Megadeth is suggested as an artist already, so its song is not repeated among the new artists' songs
    expect((found['new'] as List), isEmpty);
    expect((found['known'] as List).map((s) => s['name']), ['Fade to Black']);
  });

  test('what is played after the suggestions were worked out is left out', () async {
    final saved = await workOut(models, [play('Metallica', 'One')], now, deezer: NoDeezer());
    final shown = Suggestions.of(saved, [play('Metallica', 'One'), play('Slayer', 'South of Heaven'),
        play('Metallica', "Fade to Black")]);
    expect(shown.artists.map((a) => a['name']), ['Megadeth']);
    expect(shown.knownSongs.map((s) => s['name']), ['Enter Sandman']);
  });

  test('the report: favorites, played and untried from the day an artist was suggested', () {
    final suggested = DateTime.fromMillisecondsSinceEpoch(now);
    final history = remember({'2026-09-01': ['Too old']}, ['Megadeth', 'Slayer'], suggested);
    expect(history.keys, [dayKey(suggested)]);
    final day = DateTime.parse(dayKey(suggested)).millisecondsSinceEpoch;
    final report = Report.of(history, [
      (artist: 'Slayer', name: 'Raining Blood', at: day - Duration.millisecondsPerHour), // before: not counted
      (artist: 'Megadeth', name: 'Symphony of Destruction', at: day + Duration.millisecondsPerDay),
    ], suggested.add(const Duration(days: 2)));
    expect(report.rows.map((r) => (r.name, r.state, r.plays)),
        [('Megadeth', ReportState.favorite, 1), ('Slayer', ReportState.untried, 0)]);
    expect((report.listened, report.favorites, report.days.length), (1, 1, 1));
  });

  test('alike songs skip the song itself and one spelt twice, and an unknown one has none', () {
    final songs = Model.parse(models[2], models[3], songs: true);
    expect(alikeIn(songs, songKey('Metallica', 'One - Remastered'), 12, songs: true).map((s) => s.title),
        ['Symphony of Destruction', 'Fade to Black', 'Enter Sandman']);
    final artists = Model.parse(models[0], models[1], songs: false);
    expect(alikeIn(artists, artistMatch('Göksel'), 12, songs: false).map((a) => a.artist), ['Sertab Erener']);
    expect(alikeIn(artists, artistMatch('Nobody'), 12, songs: false), isEmpty);
  });

  test('a key without punctuation', () {
    expect(loose("what i’ve done"), loose("what i've done"));
    expect(songKey('Linkin Park, Jay-Z', "What I've Done - Remastered"), 'linkin park|what i ve done');
  });

  test("the app's models are the same as the repository's", () {
    for (final path in modelAssets) {
      final repository = File(path.replaceFirst('assets/', '../'));
      expect(File(path).readAsBytesSync(), repository.readAsBytesSync(),
          reason: 'copy ${repository.path} to mobile/$path after the models are refreshed');
    }
  });

  testWidgets('the models are bundled with the app', (tester) async {
    for (final path in modelAssets) {
      expect((await rootBundle.load(path)).lengthInBytes, greaterThan(1000000), reason: path);
    }
  });
}
