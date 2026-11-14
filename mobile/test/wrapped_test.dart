import 'package:flutter_test/flutter_test.dart';
import 'package:playlist_tracker/data/models.dart';
import 'package:playlist_tracker/data/stats.dart';
import 'package:playlist_tracker/screens/listening/wrapped_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';

Play play(String artist, String name, DateTime at) => Play(
      uid: '$artist|$name|$at',
      deviceId: 'pc',
      playedAt: at,
      artist: artist,
      name: name,
      album: 'Album',
      msPlayed: 180000,
    );

void main() {
  final october = [
    play('Old', 'Song', DateTime(2026, 10, 3, 20)),
  ];
  final november = [
    play('Band', 'One', DateTime(2026, 11, 2, 21)),
    play('Band', 'One', DateTime(2026, 11, 2, 21, 30)),
    play('Band', 'Two', DateTime(2026, 11, 5, 9)),
    play('Old', 'Song', DateTime(2026, 11, 7, 21)),
  ];
  final month = periodRange(Period.month, 0, DateTime(2026, 11, 20));

  test('the month in review counts the month\'s plays, its busiest day and hour and what was new', () {
    final data = WrappedData.of([...october, ...november], month);
    expect(data.summary.plays, 4);
    expect(data.summary.minutes, 12);
    expect(data.tracks.first.title, 'One');
    expect(data.artists.first.title, 'Band');
    expect(data.busiest, (DateTime(2026, 11, 2), 2));
    expect(data.daysListened, 3);
    expect(data.hours[21], 3);
    expect(data.discoveredTracks.map((d) => d.row.title), ['One', 'Two']);
    expect(data.discoveredArtists.map((d) => d.row.title), ['Band']);
    expect(data.firstMonth, isFalse);
    expect(WrappedData.of(november, month).firstMonth, isTrue);
  });

  test('the month before opens by itself once, only on the first days of a month', () async {
    SharedPreferences.setMockInitialValues({});
    final all = [...october, ...november];
    expect(await wrappedDue(all, DateTime(2026, 11, 5)), isNull);
    final due = await wrappedDue(all, DateTime(2026, 12, 1, 10));
    expect(due?.start, DateTime(2026, 11));
    expect(await wrappedDue(all, DateTime(2026, 12, 2)), isNull);
    // A month without plays has no summary
    expect(await wrappedDue(all, DateTime(2027, 1, 1)), isNull);
  });

  test('the notification is told which of the last and this month have plays', () async {
    SharedPreferences.setMockInitialValues({});
    await WrappedNotice.remember([...october, ...november], DateTime(2026, 11, 20));
    expect((await SharedPreferences.getInstance()).getString('PLAY_MONTHS'), '2026-10,2026-11');
    await WrappedNotice.remember([...october, ...november], DateTime(2026, 12, 1));
    expect((await SharedPreferences.getInstance()).getString('PLAY_MONTHS'), '2026-11');
  });
}
