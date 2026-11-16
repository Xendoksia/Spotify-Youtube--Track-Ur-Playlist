import 'package:flutter_test/flutter_test.dart';
import 'package:playlist_tracker/data/models.dart';
import 'package:playlist_tracker/data/stats.dart';

Play play(String artist, String name, DateTime at, {int minutes = 3, String album = 'Album', String? device}) =>
    Play(
      uid: '$artist|$name|$at',
      deviceId: device ?? 'pc',
      deviceName: device,
      playedAt: at,
      artist: artist,
      name: name,
      album: album,
      msPlayed: minutes * 60000,
    );

PlaylistEvent event(EventKind kind, DateTime at, {String name = 'Song'}) => PlaylistEvent(
      uid: '$kind|$at|$name',
      service: 'spotify',
      playlistId: 'p1',
      checkedAt: at,
      kind: kind,
      name: name,
      artist: 'A',
      album: '',
    );

void main() {
  group('keys', () {
    test('case and spacing do not make a different track', () {
      expect(play('The  Band', 'Song', DateTime(2026)).trackKey, play('the band', 'SONG ', DateTime(2026)).trackKey);
    });

    test('times are written like the desktop app writes them', () {
      expect(utcStamp(DateTime.utc(2026, 11, 7, 9, 5, 3, 397, 814)), '2026-11-07T09:05:03.397814Z');
      expect(utcStamp(DateTime.utc(2026, 1, 2)), '2026-01-02T00:00:00.000000Z');
    });
  });

  group('periods', () {
    final now = DateTime(2026, 11, 7, 15, 30); // a Saturday

    test('a week starts on Monday', () {
      final range = periodRange(Period.week, 0, now);
      expect(range.start, DateTime(2026, 11, 2));
      expect(range.end, DateTime(2026, 11, 9));
      expect(periodRange(Period.week, 1, now).start, DateTime(2026, 10, 26));
    });

    test('months go back across years', () {
      final range = periodRange(Period.month, 11, now);
      expect(range.start, DateTime(2025, 12));
      expect(range.end, DateTime(2026, 1));
    });

    test('a year and all time', () {
      expect(periodRange(Period.year, 1, now).start, DateTime(2025));
      expect(periodRange(Period.all, 0, now).end, DateTime(2026, 11, 8));
    });
  });

  group('statistics', () {
    final plays = [
      play('A', 'One', DateTime(2026, 11, 2, 10)),
      play('a', 'one', DateTime(2026, 11, 3, 10)),
      play('B', 'Two', DateTime(2026, 11, 4, 10), minutes: 4, album: ''),
      play('C', 'Three', DateTime(2026, 11, 5, 10)),
    ];

    test('the summary counts plays, minutes and different tracks and artists', () {
      final summary = Summary.of(plays);
      expect([summary.plays, summary.minutes, summary.tracks, summary.artists], [4, 13, 3, 3]);
    });

    test('top lists order by plays, then by listening time, then by the latest play', () {
      expect(topTracks(plays).map((r) => (r.title, r.plays)), [('One', 2), ('Two', 1), ('Three', 1)]);
      expect(topArtists(plays, limit: 2).map((r) => r.title), ['A', 'B']);
      final even = [...plays, play('D', 'Four', DateTime(2026, 11, 1, 10), minutes: 4)];
      expect(topTracks(even).map((r) => r.title), ['One', 'Two', 'Four', 'Three']);
    });

    test('plays without an album are left out of the top albums', () {
      expect(topAlbums(plays).map((r) => r.subtitle), ['A', 'C']);
    });

    test('a week has a bar for each day', () {
      final range = periodRange(Period.week, 0, DateTime(2026, 11, 7));
      final bars = buckets(Period.week, range, plays);
      expect(bars.length, 7);
      expect(bars.map((b) => b.minutes), [3, 3, 4, 3, 0, 0, 0]);
    });

    test('a year has a bar for each month and all time one for each year', () {
      final now = DateTime(2026, 11, 7);
      expect(buckets(Period.year, periodRange(Period.year, 0, now), plays).length, 12);
      final years = buckets(Period.all, periodRange(Period.all, 0, now), [...plays, play('D', 'Old', DateTime(2024, 5))]);
      expect(years.map((b) => b.start.year), [2024, 2025, 2026]);
    });

    test('recent plays are grouped by day, newest first', () {
      final days = byDay([...plays, play('D', 'Late', DateTime(2026, 11, 5, 22))]);
      expect(days.first.key, DateTime(2026, 11, 5));
      expect(days.first.value.map((p) => p.name), ['Late', 'Three']);
    });

    test('plays are counted per device', () {
      final counts = playsPerDevice([...plays, play('D', 'Phone', DateTime(2026), device: 'Pixel')]);
      expect(counts.first, isA<MapEntry<String, int>>().having((e) => e.value, 'plays', 4));
      expect(counts.last.key, 'Pixel');
    });
  });

  group('playlist changes', () {
    test('the latest check that found changes, counted by kind', () {
      final latest = latestChanges([
        event(EventKind.initial, DateTime(2026, 11, 1), name: '20 tracks recorded'),
        event(EventKind.added, DateTime(2026, 11, 2)),
        event(EventKind.removed, DateTime(2026, 11, 4)),
        event(EventKind.removed, DateTime(2026, 11, 4), name: 'Other'),
        event(EventKind.unplayable, DateTime(2026, 11, 4), name: 'Third'),
      ])!;
      expect(latest.at, DateTime(2026, 11, 4));
      expect(latest.counts, {EventKind.removed: 2, EventKind.unplayable: 1});
    });

    test('only the first check is no change', () {
      expect(latestChanges([event(EventKind.initial, DateTime(2026))]), isNull);
      expect(event(EventKind.initial, DateTime(2026), name: '20 tracks recorded').initialCount, 20);
    });

    test('rows of unknown kinds are skipped', () {
      final row = {
        'uid': 'e1', 'service': 'spotify', 'playlist_id': 'p1', 'checked_at': '2026-11-07T10:00:00+03:00',
        'event': 'SOMETHING_NEW', 'name': 'Song', 'artist': 'A', 'album': '',
      };
      expect(PlaylistEvent.fromRow(row), isNull);
      expect(PlaylistEvent.fromRow({...row, 'event': 'REMOVED'})!.checkedAt, DateTime.utc(2026, 11, 7, 7).toLocal());
    });
  });

  group('rank changes', () {
    final now = DateTime(2026, 11, 20);

    test('compare with the whole previous month', () {
      final all = [
        play('A', 'One', DateTime(2026, 9, 5)),
        play('A', 'Two', DateTime(2026, 10, 1)),
        play('A', 'Two', DateTime(2026, 10, 2)),
        play('A', 'One', DateTime(2026, 10, 3)),
        play('A', 'One', DateTime(2026, 11, 1)),
        play('A', 'One', DateTime(2026, 11, 2)),
        play('A', 'Two', DateTime(2026, 11, 3)),
        play('A', 'Old', DateTime(2026, 11, 4)),
        play('A', 'New', DateTime(2026, 11, 5)),
      ];
      final change = rankChanges(all, Period.month, 0, now, trackKeyOf);
      final key = play('A', 'One', now).trackKey;
      expect(change(key, 1)!.kind, ChangeKind.up);
      expect(change(key, 1)!.count, 1);
      expect(change(play('A', 'Two', now).trackKey, 2)!.kind, ChangeKind.down);
      expect(change(play('A', 'New', now).trackKey, 3)!.kind, ChangeKind.fresh);
    });

    test('one heard before the previous period is back', () {
      final all = [
        play('A', 'Old', DateTime(2026, 9, 5)),
        play('A', 'Other', DateTime(2026, 10, 5)),
        play('A', 'Old', DateTime(2026, 11, 5)),
      ];
      final change = rankChanges(all, Period.month, 0, now, trackKeyOf);
      expect(change(play('A', 'Old', now).trackKey, 1)!.kind, ChangeKind.back);
    });

    test('new and back are not told apart before the previous period was recorded in full', () {
      final all = [play('A', 'Other', DateTime(2026, 10, 15)), play('A', 'One', DateTime(2026, 11, 5))];
      final change = rankChanges(all, Period.month, 0, now, trackKeyOf);
      expect(change(play('A', 'One', now).trackKey, 1), isNull);
    });

    test('same place, and nothing for all time', () {
      final all = [play('A', 'One', DateTime(2026, 10, 1)), play('A', 'One', DateTime(2026, 11, 1))];
      expect(rankChanges(all, Period.month, 0, now, trackKeyOf)(play('A', 'One', now).trackKey, 1)!.kind,
          ChangeKind.same);
      expect(rankChanges(all, Period.all, 0, now, trackKeyOf)(play('A', 'One', now).trackKey, 1), isNull);
    });
  });

  group('detail pages', () {
    test('a target finds its own plays, case and spacing aside', () {
      final all = [
        play('Band', 'One', DateTime(2026, 11, 1), album: 'Record'),
        play('band ', 'ONE', DateTime(2026, 11, 2), album: 'record'),
        play('Band', 'Two', DateTime(2026, 11, 3), album: 'Record'),
        play('Other', 'One', DateTime(2026, 11, 4), album: 'Record'),
      ];
      expect(DetailTarget.track(all.first).playsIn(all), hasLength(2));
      expect(DetailTarget.artist('BAND').playsIn(all), hasLength(3));
      expect(DetailTarget.album('Band', 'Record').playsIn(all), hasLength(3));
      final top = topAlbums(all).first;
      expect(DetailTarget.ranked(DetailKind.album, top).playsIn(all), hasLength(3));
    });

    test('totals over all time', () {
      final detail = Detail.of([
        play('A', 'One', DateTime(2026, 11, 3), minutes: 4),
        play('A', 'One', DateTime(2026, 11, 1), minutes: 2),
      ])!;
      expect((detail.plays, detail.minutes, detail.first, detail.last), (2, 6, DateTime(2026, 11, 1), DateTime(2026, 11, 3)));
      expect(Detail.of([]), isNull);
    });

    test('the chart covers at least two weeks by day, and goes by month after 62 days', () {
      final now = DateTime(2026, 11, 8, 12);
      final (recent, daily) = detailBuckets([play('A', 'One', DateTime(2026, 11, 7))], now);
      expect(daily, isTrue);
      expect(recent, hasLength(14));
      expect(recent.last.start, DateTime(2026, 11, 8));
      expect(recent[recent.length - 2].plays, 1);
      final (old, byDay) = detailBuckets([play('A', 'One', DateTime(2026, 6, 15))], now);
      expect(byDay, isFalse);
      expect(old.first.start, DateTime(2026, 6));
      expect(old, hasLength(6));
      expect(old.first.plays, 1);
    });

    test("an album's tracks follow the track list, version notes aside, and unlisted played ones come after", () {
      final plays = [
        play('A', 'Two - Remastered', DateTime(2026, 11, 1)),
        play('A', 'Two - Remastered', DateTime(2026, 11, 2)),
        play('A', 'Bonus', DateTime(2026, 11, 3)),
      ];
      final rows = albumTracks(plays, [('One', 180000), ('Two', 200000)]);
      expect(rows.map((r) => (r.title, r.played?.plays)), [('One', null), ('Two', 2), ('Bonus', 1)]);
      expect(albumTracks(plays, null).map((r) => r.title), ['Two - Remastered', 'Bonus']);
    });
  });

  group('comparing periods', () {
    test('a running month is compared with the same stretch of the previous one', () {
      final now = DateTime(2026, 11, 8, 12);
      final plays = [
        play('A', 'One', DateTime(2026, 11, 2)),
        play('A', 'One', DateTime(2026, 10, 3)),
        play('A', 'Two', DateTime(2026, 10, 5)),
        play('B', 'Late', DateTime(2026, 10, 20)),
      ];
      final before = previousSummary(plays, Period.month, 0, now)!;
      expect((before.plays, before.tracks, before.artists), (2, 2, 1));
      expect(previousSummary(plays, Period.month, 1, now)!.plays, 0);
      expect(previousSummary(plays, Period.all, 0, now), isNull);
    });

    test('the change is in whole percent, none without anything before', () {
      expect(percentChange(150, 100), 50);
      expect(percentChange(2, 3), -33);
      expect(percentChange(5, 0), isNull);
    });

    test('plays are counted by their local hour', () {
      final hours = playsPerHour([
        play('A', 'One', DateTime(2026, 11, 2, 9, 30)),
        play('A', 'One', DateTime(2026, 11, 3, 9, 5)),
        play('A', 'One', DateTime(2026, 11, 3, 23, 59)),
      ]);
      expect((hours.length, hours[9], hours[23], hours[0]), (24, 2, 1, 0));
    });
  });

  group('discoveries', () {
    final plays = [
      play('A', 'Old', DateTime(2026, 10, 1)),
      play('A', 'Old', DateTime(2026, 11, 3)),
      play('A', 'New', DateTime(2026, 11, 4)),
      play('B', 'Fresh', DateTime(2026, 11, 5)),
      play('B', 'Fresh', DateTime(2026, 11, 6)),
    ];
    final november = DateRange(DateTime(2026, 11), DateTime(2026, 12));

    test('only what was first heard in the period is new, most played first', () {
      expect(newTracks(plays, november).map((d) => (d.row.title, d.row.plays)), [('Fresh', 2), ('New', 1)]);
      final artists = newArtists(plays, november);
      expect(artists.map((d) => (d.row.title, d.tracks, d.at)), [('B', 1, DateTime(2026, 11, 5))]);
    });

    test('forgotten tracks were played often but not lately', () {
      final often = [
        for (var day = 1; day <= 4; day++) play('C', 'Loved', DateTime(2026, 9, day)),
        for (var day = 1; day <= 2; day++) play('C', 'Liked', DateTime(2026, 9, day)),
        for (var day = 1; day <= 3; day++) play('C', 'Recent', DateTime(2026, 11, day)),
      ];
      final rows = forgotten(often, DateTime(2026, 11, 8));
      expect(rows.map((d) => (d.row.title, d.row.plays, d.at)), [('Loved', 4, DateTime(2026, 9, 4))]);
    });
  });

  group('diversity and milestones', () {
    test('the top five artists, different tracks and new tracks are counted', () {
      final plays = [
        play('A', 'Old', DateTime(2026, 10, 1)),
        play('A', 'Old', DateTime(2026, 11, 2)),
        play('A', 'New', DateTime(2026, 11, 3)),
        for (final artist in ['B', 'C', 'D', 'E', 'F']) play(artist, 'Song', DateTime(2026, 11, 4)),
      ];
      final d = Diversity.of(plays, DateRange(DateTime(2026, 11), DateTime(2026, 12)));
      expect((d.plays, d.tracks, d.artists, d.top5, d.fresh), (7, 7, 6, 6, 6));
      expect(share(6, 7), 86);
    });

    test('counts worth marking are found in the order they were reached, newest first', () {
      final plays = [
        for (var i = 0; i < 100; i++) play(i < 10 ? 'A' : 'B$i', i < 10 ? 'Hit' : 'Song$i', DateTime(2026, 11, 1, 0, i)),
      ];
      final found = milestones(plays);
      expect(found.first.kind, MilestoneKind.total);
      expect(found.first.count, 100);
      final kinds = found.map((m) => (m.kind, m.count)).toSet();
      expect(kinds, containsAll([(MilestoneKind.artist, 10), (MilestoneKind.track, 10), (MilestoneKind.met, 10),
          (MilestoneKind.start, 0)]));
      expect(nextTotalStep(100), (250, 150));
      expect(yearBack(DateTime(2028, 2, 29)), DateTime(2027, 2, 28));
    });
  });

  group('trend', () {
    test('a month is split into its days up to today', () {
      final now = DateTime(2026, 11, 16, 12);
      final range = periodRange(Period.month, 0, now);
      final plays = [
        play('A', 'One', DateTime(2026, 11, 1, 9)),
        play('A', 'Two', DateTime(2026, 11, 1, 23)),
        play('B', 'Three', DateTime(2026, 11, 16, 8)),
      ];
      final days = trend(Period.month, range, plays, now);
      expect(days.unit, TrendUnit.day);
      expect(days.starts.length, 16);
      expect(days.values.first.plays, 2);
      expect(days.values.first.tracks, 2);
      expect(days.values.last.artists, 1);
      expect(days.values[5].plays, 0);
    });

    test('all time goes by month from the first play, by year past three years', () {
      final now = DateTime(2026, 11, 16);
      final range = periodRange(Period.all, 0, now);
      final months = trend(Period.all, range, [play('A', 'One', DateTime(2026, 3, 5))], now);
      expect(months.unit, TrendUnit.month);
      expect(months.starts.first, DateTime(2026, 3));
      expect(months.starts.length, 9);
      final years = trend(Period.all, range, [play('A', 'One', DateTime(2021, 3, 5))], now);
      expect(years.unit, TrendUnit.year);
      expect(years.starts.length, 6);
      expect(years.values.first.plays, 1);
    });
  });
}
