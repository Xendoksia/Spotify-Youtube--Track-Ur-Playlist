/// Listening statistics of a period, counted the same way as the desktop app's listening.py: a play counts once,
/// its minutes are the time it was listened to.
library;

import 'models.dart';

enum Period { week, month, year, all }

class DateRange {
  final DateTime start;
  final DateTime end;

  const DateRange(this.start, this.end);

  bool contains(DateTime moment) => !moment.isBefore(start) && moment.isBefore(end);
}

/// The local [start, end) of the current week (from Monday), month or year, or [offset] periods back from it
DateRange periodRange(Period period, int offset, DateTime now) {
  final day = DateTime(now.year, now.month, now.day);
  switch (period) {
    case Period.week:
      final start = DateTime(day.year, day.month, day.day - (day.weekday - 1) - 7 * offset);
      return DateRange(start, DateTime(start.year, start.month, start.day + 7));
    case Period.month:
      final start = DateTime(day.year, day.month - offset);
      return DateRange(start, DateTime(start.year, start.month + 1));
    case Period.year:
      final start = DateTime(day.year - offset);
      return DateRange(start, DateTime(start.year + 1));
    case Period.all:
      return DateRange(DateTime(2000), DateTime(day.year, day.month, day.day + 1));
  }
}

List<Play> playsIn(List<Play> plays, DateRange range) => plays.where((p) => range.contains(p.playedAt)).toList();

class Summary {
  final int plays;
  final int minutes;
  final int tracks;
  final int artists;

  const Summary(this.plays, this.minutes, this.tracks, this.artists);

  factory Summary.of(List<Play> plays) => Summary(
        plays.length,
        _minutes(plays),
        plays.map((p) => p.trackKey).toSet().length,
        plays.map((p) => p.artistKey).toSet().length,
      );
}

int _minutes(Iterable<Play> plays) => plays.fold<int>(0, (sum, p) => sum + p.msPlayed) ~/ 60000;

/// A row of a top list: a track, artist or album with how often and how long it was played
class Ranked {
  final String title;
  final String subtitle;
  final int plays;
  final int minutes;

  const Ranked(this.title, this.subtitle, this.plays, this.minutes);
}

/// The most played groups; ties go to the one played last, as in the desktop app
List<Ranked> _top(List<Play> plays, String Function(Play) groupKey, Ranked Function(List<Play>) rank, int limit) {
  final groups = <String, List<Play>>{};
  for (final play in plays) {
    groups.putIfAbsent(groupKey(play), () => []).add(play);
  }
  DateTime last(List<Play> group) => group.map((p) => p.playedAt).reduce((a, b) => a.isAfter(b) ? a : b);
  final ordered = groups.values.toList()
    ..sort((a, b) => a.length != b.length ? b.length.compareTo(a.length) : last(b).compareTo(last(a)));
  return ordered.take(limit).map(rank).toList();
}

List<Ranked> topTracks(List<Play> plays, {int limit = 10}) => _top(
    plays, (p) => p.trackKey, (g) => Ranked(g.first.name, g.first.artist, g.length, _minutes(g)), limit);

List<Ranked> topArtists(List<Play> plays, {int limit = 10}) => _top(plays, (p) => p.artistKey,
    (g) => Ranked(g.first.artist, '', g.length, _minutes(g)), limit);

/// Plays without an album name are left out
List<Ranked> topAlbums(List<Play> plays, {int limit = 10}) => _top(
    plays.where((p) => p.album.trim().isNotEmpty).toList(),
    (p) => '${p.artistKey}|${p.album.toLowerCase()}',
    (g) => Ranked(g.first.album, g.first.artist, g.length, _minutes(g)),
    limit);

/// One bar of the listening chart
class Bucket {
  final DateTime start;
  final int minutes;
  final int plays;

  const Bucket(this.start, this.minutes, this.plays);
}

/// The period split into bars: the days of a week or month, the months of a year, the years of all time (from
/// the first play's year)
List<Bucket> buckets(Period period, DateRange range, List<Play> plays) {
  final starts = <DateTime>[];
  switch (period) {
    case Period.week:
    case Period.month:
      for (var d = range.start; d.isBefore(range.end); d = DateTime(d.year, d.month, d.day + 1)) {
        starts.add(d);
      }
    case Period.year:
      for (var m = 1; m <= 12; m++) {
        starts.add(DateTime(range.start.year, m));
      }
    case Period.all:
      final first = plays.isEmpty ? range.end.year : plays.map((p) => p.playedAt.year).reduce((a, b) => a < b ? a : b);
      for (var y = first; y <= range.end.subtract(const Duration(days: 1)).year; y++) {
        starts.add(DateTime(y));
      }
  }
  return [
    for (var i = 0; i < starts.length; i++)
      () {
        final bucket = DateRange(starts[i], i + 1 < starts.length ? starts[i + 1] : range.end);
        final inside = plays.where((p) => bucket.contains(p.playedAt));
        return Bucket(starts[i], _minutes(inside), inside.length);
      }(),
  ];
}

/// The latest plays grouped by their local day, newest first
List<MapEntry<DateTime, List<Play>>> byDay(List<Play> plays, {int limit = 50}) {
  final days = <DateTime, List<Play>>{};
  final latest = [...plays]..sort((a, b) => b.playedAt.compareTo(a.playedAt));
  for (final play in latest.take(limit)) {
    days.putIfAbsent(DateTime(play.playedAt.year, play.playedAt.month, play.playedAt.day), () => []).add(play);
  }
  return days.entries.toList();
}

/// How many plays each device recorded, most first; plays without a device name count as "unknown"
List<MapEntry<String, int>> playsPerDevice(List<Play> plays) {
  final counts = <String, int>{};
  for (final play in plays) {
    final name = play.deviceName ?? '';
    counts[name] = (counts[name] ?? 0) + 1;
  }
  return counts.entries.toList()..sort((a, b) => b.value.compareTo(a.value));
}

/// A playlist's latest changes: when they were found and how many of each kind (the first check left out)
class LatestChanges {
  final DateTime at;
  final Map<EventKind, int> counts;

  const LatestChanges(this.at, this.counts);
}

LatestChanges? latestChanges(Iterable<PlaylistEvent> events) {
  final changes = events.where((e) => e.kind != EventKind.initial).toList();
  if (changes.isEmpty) return null;
  final at = changes.map((e) => e.checkedAt).reduce((a, b) => a.isAfter(b) ? a : b);
  final counts = <EventKind, int>{};
  for (final event in changes.where((e) => e.checkedAt == at)) {
    counts[event.kind] = (counts[event.kind] ?? 0) + 1;
  }
  return LatestChanges(at, counts);
}
