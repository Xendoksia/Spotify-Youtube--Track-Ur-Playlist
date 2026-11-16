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

int _ms(Iterable<Play> plays) => plays.fold<int>(0, (sum, p) => sum + p.msPlayed);
int _minutes(Iterable<Play> plays) => _ms(plays) ~/ 60000;

/// A row of a top list: a track, artist or album with how often and how long it was played
class Ranked {
  final String key;
  final String title;
  final String subtitle;
  final int plays;
  final int minutes;

  /// The artist and album of its first play, for its picture
  final String artist;
  final String album;

  const Ranked(this.key, this.title, this.subtitle, this.plays, this.minutes, {this.artist = '', this.album = ''});
}

String trackKeyOf(Play play) => play.trackKey;
String artistKeyOf(Play play) => play.artistKey;
String albumKeyOf(Play play) => '${play.artistKey}|${play.album.toLowerCase()}';

/// The plays grouped by key, most played first; ties go to the one listened to longer, then to the one played
/// last, as in the desktop app
List<MapEntry<String, List<Play>>> _ordered(List<Play> plays, String Function(Play) keyOf) {
  final groups = <String, List<Play>>{};
  for (final play in plays) {
    groups.putIfAbsent(keyOf(play), () => []).add(play);
  }
  DateTime last(List<Play> group) => group.map((p) => p.playedAt).reduce((a, b) => a.isAfter(b) ? a : b);
  return groups.entries.toList()
    ..sort((a, b) {
      if (a.value.length != b.value.length) return b.value.length.compareTo(a.value.length);
      final time = _ms(b.value).compareTo(_ms(a.value));
      return time != 0 ? time : last(b.value).compareTo(last(a.value));
    });
}

List<Ranked> _top(List<Play> plays, String Function(Play) keyOf, String Function(Play) title,
        String Function(Play) subtitle, int limit) =>
    _ordered(plays, keyOf)
        .take(limit)
        .map((e) => Ranked(e.key, title(e.value.first), subtitle(e.value.first), e.value.length, _minutes(e.value),
            artist: e.value.first.artist, album: e.value.first.album))
        .toList();

List<Ranked> topTracks(List<Play> plays, {int limit = 10}) =>
    _top(plays, trackKeyOf, (p) => p.name, (p) => p.artist, limit);

List<Ranked> topArtists(List<Play> plays, {int limit = 10}) =>
    _top(plays, artistKeyOf, (p) => p.artist, (p) => '', limit);

/// Plays without an album name are left out
List<Ranked> topAlbums(List<Play> plays, {int limit = 10}) =>
    _top(plays.where((p) => p.album.trim().isNotEmpty).toList(), albumKeyOf, (p) => p.album, (p) => p.artist, limit);

/// How a row's rank compares with the whole previous period
enum ChangeKind { up, down, same, fresh, back }

class RankChange {
  final ChangeKind kind;

  /// Places moved up or down
  final int count;

  const RankChange(this.kind, [this.count = 0]);
}

/// Returns change(key, rank), as the desktop app's _rank_changes: ▲▼ against the previous period's rank; one not
/// in the previous period is new (never heard before) or back. Songs heard before recording began look new too,
/// so new and back are only told apart once the whole previous period was recorded. Nothing for all time.
RankChange? Function(String key, int rank) rankChanges(
    List<Play> all, Period period, int offset, DateTime now, String Function(Play) keyOf) {
  if (period == Period.all) return (_, _) => null;
  final range = periodRange(period, offset, now);
  final previousRange = periodRange(period, offset + 1, now);
  final previous = {
    for (final (index, entry) in _ordered(playsIn(all, previousRange), keyOf).indexed) entry.key: index + 1,
  };
  final known = all.where((p) => p.playedAt.isBefore(range.start)).map(keyOf).toSet();
  final first = all.isEmpty ? null : all.map((p) => p.playedAt).reduce((a, b) => a.isBefore(b) ? a : b);
  final recordedBefore = first != null && !first.isAfter(previousRange.start);
  return (key, rank) {
    final before = previous[key];
    if (before == null) {
      if (!recordedBefore) return null;
      return RankChange(known.contains(key) ? ChangeKind.back : ChangeKind.fresh);
    }
    if (before == rank) return const RankChange(ChangeKind.same);
    return RankChange(before > rank ? ChangeKind.up : ChangeKind.down, (before - rank).abs());
  };
}

/// What a detail page shows: one track, artist or album
enum DetailKind { track, artist, album }

class DetailTarget {
  final DetailKind kind;
  final String key;

  /// The track's, artist's or album's name
  final String title;
  final String artist;
  final String album;

  const DetailTarget(this.kind, this.key, this.title, {this.artist = '', this.album = ''});

  factory DetailTarget.track(Play play) =>
      DetailTarget(DetailKind.track, play.trackKey, play.name, artist: play.artist, album: play.album);

  factory DetailTarget.artist(String artist) =>
      DetailTarget(DetailKind.artist, textKey(artist), artist, artist: artist);

  factory DetailTarget.album(String artist, String album) =>
      DetailTarget(DetailKind.album, '${textKey(artist)}|${album.toLowerCase()}', album, artist: artist, album: album);

  /// A row of a top list of this kind
  factory DetailTarget.ranked(DetailKind kind, Ranked row) => DetailTarget(kind, row.key, row.title,
      artist: row.artist, album: kind == DetailKind.album ? row.title : row.album);

  String Function(Play) get keyOf => switch (kind) {
        DetailKind.track => trackKeyOf,
        DetailKind.artist => artistKeyOf,
        DetailKind.album => albumKeyOf,
      };

  List<Play> playsIn(List<Play> plays) => plays.where((p) => keyOf(p) == key).toList();

  /// The tag of its picture flying to its page; [depth] is the page's place in the stack (1 = opened from the
  /// listening page), so a page's big picture never flies into a row of the page opened from it
  String hero(int depth) => heroTag(kind, key, depth);
}

String heroTag(DetailKind kind, String key, int depth) => '${kind.name}:$key@$depth';

/// The totals of a track, artist or album over all time
class Detail {
  final int plays;
  final int minutes;
  final DateTime first;
  final DateTime last;

  const Detail(this.plays, this.minutes, this.first, this.last);

  static Detail? of(List<Play> plays) {
    if (plays.isEmpty) return null;
    final times = plays.map((p) => p.playedAt);
    return Detail(plays.length, _minutes(plays), times.reduce((a, b) => a.isBefore(b) ? a : b),
        times.reduce((a, b) => a.isAfter(b) ? a : b));
  }
}

/// A detail page's chart covers at least two weeks, so a track heard only lately does not fill it with two huge
/// columns, and goes by month when it would have more days than this; as in the desktop app
const detailMinDays = 14;
const detailDailyLimit = 62;

/// The plays of a detail page per day (daily: true) or per month, from its first play to today
(List<Bucket>, bool daily) detailBuckets(List<Play> plays, DateTime now) {
  final today = DateTime(now.year, now.month, now.day);
  final first = plays.map((p) => p.playedAt).fold(today, (a, b) => b.isBefore(a) ? b : a);
  var start = DateTime(first.year, first.month, first.day);
  final earliest = DateTime(today.year, today.month, today.day - (detailMinDays - 1));
  if (earliest.isBefore(start)) start = earliest;
  final end = DateTime(today.year, today.month, today.day + 1);
  final daily = end.difference(start).inDays <= detailDailyLimit;
  final starts = <DateTime>[
    if (daily)
      for (var d = start; d.isBefore(end); d = DateTime(d.year, d.month, d.day + 1)) d
    else
      for (var m = DateTime(start.year, start.month); m.isBefore(end); m = DateTime(m.year, m.month + 1)) m,
  ];
  return (
    [
      for (var i = 0; i < starts.length; i++)
        () {
          final range = DateRange(starts[i], i + 1 < starts.length ? starts[i + 1] : end);
          final inside = plays.where((p) => range.contains(p.playedAt));
          return Bucket(starts[i], _minutes(inside), inside.length);
        }(),
    ],
    daily,
  );
}

/// A track of an album's page: from Deezer's track list (with its length) and/or from the plays
class AlbumTrack {
  final String title;
  final int? lengthMs;
  final Ranked? played;

  const AlbumTrack(this.title, this.lengthMs, this.played);
}

/// The album's tracks in album order with their plays; tracks are the same apart from version notes. Played
/// tracks the list does not have (bonus tracks, other editions) come after. Without a list, the played ones.
List<AlbumTrack> albumTracks(List<Play> albumPlays, List<(String, int)>? tracklist) {
  String same(String title) => textKey(plainTitle(title));
  final left = topTracks(albumPlays, limit: 1 << 30);
  final rows = <AlbumTrack>[];
  for (final (title, ms) in tracklist ?? const <(String, int)>[]) {
    final match = left.where((r) => same(r.title) == same(title)).firstOrNull;
    if (match != null) left.remove(match);
    rows.add(AlbumTrack(title, ms, match));
  }
  return rows..addAll(left.map((r) => AlbumTrack(r.title, null, r)));
}

/// Drop version notes such as " - Remastered 2026" or " (Deluxe)" that other catalogs spell differently
String plainTitle(String name) {
  final plain = name.split(' - ').first.replaceAll(RegExp(r'\s*(\(.*?\)|\[.*?\])'), '').trim();
  return plain.isEmpty ? name : plain;
}

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

/// How a tile's trend line is split: by day, month or year
enum TrendUnit { day, month, year }

/// The tiles' values per day, month or year of the period up to now, for their trend lines
class Trend {
  final TrendUnit unit;
  final List<DateTime> starts;
  final List<Summary> values;

  const Trend(this.unit, this.starts, this.values);
}

/// As the desktop app's trend_points: days for a week, a month or under two months, else months, years past three
/// years. All time starts at the first play.
Trend trend(Period period, DateRange range, List<Play> plays, DateTime now) {
  var start = range.start;
  if (period == Period.all && plays.isNotEmpty) {
    final first = plays.map((p) => p.playedAt).reduce((a, b) => a.isBefore(b) ? a : b);
    start = DateTime(first.year, first.month, first.day);
  }
  final last = (now.isBefore(range.end) ? now : range.end).subtract(const Duration(seconds: 1));
  final starts = <DateTime>[];
  TrendUnit unit;
  if (period == Period.week || period == Period.month || last.difference(start).inDays < 62) {
    unit = TrendUnit.day;
    for (var d = start; !d.isAfter(last); d = DateTime(d.year, d.month, d.day + 1)) {
      starts.add(d);
    }
  } else {
    unit = TrendUnit.month;
    for (var m = DateTime(start.year, start.month); !m.isAfter(last); m = DateTime(m.year, m.month + 1)) {
      starts.add(m);
    }
    if (starts.length > 36) {
      unit = TrendUnit.year;
      starts
        ..clear()
        ..addAll([for (var y = start.year; y <= last.year; y++) DateTime(y)]);
    }
  }
  final groups = List.generate(starts.length, (_) => <Play>[]);
  for (final play in plays) {
    if (play.playedAt.isBefore(start) || play.playedAt.isAfter(last)) continue;
    final at = play.playedAt;
    final index = switch (unit) {
      // Rounded, as days across a clock change are 23 or 25 hours long
      TrendUnit.day => (DateTime(at.year, at.month, at.day).difference(start).inHours / 24).round(),
      TrendUnit.month => (at.year - start.year) * 12 + at.month - start.month,
      TrendUnit.year => at.year - start.year,
    };
    if (index >= 0 && index < groups.length) groups[index].add(play);
  }
  return Trend(unit, starts, [for (final group in groups) Summary.of(group)]);
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

/// The summary of the previous period to compare with, as the desktop app's tiles: while the current period
/// still runs, only the same stretch of the previous one. Nothing for all time.
Summary? previousSummary(List<Play> all, Period period, int offset, DateTime now) {
  if (period == Period.all) return null;
  final range = periodRange(period, offset, now);
  final previous = periodRange(period, offset + 1, now);
  var end = previous.end;
  if (offset == 0) {
    final stretch = previous.start.add(now.difference(range.start));
    if (stretch.isBefore(end)) end = stretch;
  }
  return Summary.of(playsIn(all, DateRange(previous.start, end)));
}

/// The change from before to now in whole percent, or null with nothing before to compare with
int? percentChange(int now, int before) => before == 0 ? null : ((now - before) * 100 / before).round();

/// Plays per local hour of the day, 0-23
List<int> playsPerHour(List<Play> plays) {
  final hours = List.filled(24, 0);
  for (final play in plays) {
    hours[play.playedAt.hour]++;
  }
  return hours;
}

/// A track or artist heard for the first time ever in a period, or one not played lately
class Discovered {
  final Ranked row;

  /// Its very first play (a discovery) or its last one (forgotten)
  final DateTime at;

  /// An artist's different tracks in the period
  final int tracks;

  const Discovered(this.row, this.at, {this.tracks = 0});
}

DateTime _earliest(Iterable<Play> plays) => plays.map((p) => p.playedAt).reduce((a, b) => a.isBefore(b) ? a : b);
DateTime _latest(Iterable<Play> plays) => plays.map((p) => p.playedAt).reduce((a, b) => a.isAfter(b) ? a : b);

/// Tracks or artists whose very first recorded play falls in the period, most played in it first, as the desktop
/// app's new_tracks / new_artists
List<Discovered> _firstHeard(List<Play> all, DateRange range, String Function(Play) keyOf,
    Ranked Function(String key, List<Play> plays) row) {
  final everything = <String, List<Play>>{};
  for (final play in all) {
    everything.putIfAbsent(keyOf(play), () => []).add(play);
  }
  final found = <Discovered>[];
  final ms = <String, int>{};
  everything.forEach((key, plays) {
    final first = _earliest(plays);
    if (!range.contains(first)) return;
    final inside = plays.where((p) => range.contains(p.playedAt)).toList();
    ms[key] = _ms(inside);
    found.add(Discovered(row(key, inside), first, tracks: inside.map((p) => p.trackKey).toSet().length));
  });
  return found
    ..sort((a, b) {
      if (a.row.plays != b.row.plays) return b.row.plays.compareTo(a.row.plays);
      final time = ms[b.row.key]!.compareTo(ms[a.row.key]!);
      return time != 0 ? time : b.at.compareTo(a.at);
    });
}

List<Discovered> newTracks(List<Play> all, DateRange range) => _firstHeard(all, range, trackKeyOf,
    (key, plays) => Ranked(key, plays.first.name, plays.first.artist, plays.length, _minutes(plays),
        artist: plays.first.artist, album: plays.first.album));

List<Discovered> newArtists(List<Play> all, DateRange range) => _firstHeard(all, range, artistKeyOf,
    (key, plays) => Ranked(key, plays.first.artist, '', plays.length, _minutes(plays), artist: plays.first.artist));

/// Tracks played at least [minPlays] times but not once in the last [days] days, most played first
List<Discovered> forgotten(List<Play> all, DateTime now, {int days = 30, int minPlays = 3, int limit = 10}) {
  final since = now.subtract(Duration(days: days));
  final found = <Discovered>[];
  for (final MapEntry(:key, value: plays) in _ordered(all, trackKeyOf)) {
    if (plays.length < minPlays) break;
    final last = _latest(plays);
    if (!last.isBefore(since)) continue;
    found.add(Discovered(
        Ranked(key, plays.first.name, plays.first.artist, plays.length, _minutes(plays),
            artist: plays.first.artist, album: plays.first.album),
        last));
  }
  return found.take(limit).toList();
}

/// How varied a period's listening was, as the desktop app's listening.diversity: its plays, different tracks and
/// artists, the plays of its five most played artists and the plays of tracks heard for the first time in it
class Diversity {
  final int plays;
  final int tracks;
  final int artists;
  final int top5;
  final int fresh;

  const Diversity(this.plays, this.tracks, this.artists, this.top5, this.fresh);

  factory Diversity.of(List<Play> all, DateRange range) {
    final plays = playsIn(all, range);
    final top5 = _ordered(plays, artistKeyOf).take(5).fold<int>(0, (sum, e) => sum + e.value.length);
    final firsts = <String, DateTime>{};
    for (final play in all) {
      final first = firsts[play.trackKey];
      if (first == null || play.playedAt.isBefore(first)) firsts[play.trackKey] = play.playedAt;
    }
    final fresh = plays.where((p) => range.contains(firsts[p.trackKey]!)).length;
    final summary = Summary.of(plays);
    return Diversity(plays.length, summary.tracks, summary.artists, top5, fresh);
  }
}

/// part of whole in whole percent, 0 of nothing
int share(int part, int whole) => whole == 0 ? 0 : (100 * part / whole).round();

/// Counts worth marking: of all plays, of one artist's plays and of one track's plays (listening.py)
const totalSteps = [100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000];
const artistSteps = [10, 25, 50, 100, 250, 500, 1000];
const trackSteps = [10, 25, 50, 100, 250];

enum MilestoneKind { total, artist, track, met, start }

class Milestone {
  final MilestoneKind kind;
  final DateTime at;
  final int count;
  final String name;
  final String artist;
  final String key;

  const Milestone(this.kind, this.at, this.count, {this.name = '', this.artist = '', this.key = ''});
}

/// Every milestone so far, newest first, as the desktop app's listening.milestones: the 100th play, an artist's
/// 25th play, a track's 10th play, the day an artist who now has 10 plays was first heard, the start of recording
List<Milestone> milestones(List<Play> all) {
  final plays = [...all]..sort((a, b) => a.playedAt.compareTo(b.playedAt));
  final found = <Milestone>[];
  if (plays.isNotEmpty) found.add(Milestone(MilestoneKind.start, plays.first.playedAt, 0));
  final artistPlays = <String, int>{};
  final trackPlays = <String, int>{};
  final firstHeard = <String, Play>{};
  for (final (index, play) in plays.indexed) {
    if (totalSteps.contains(index + 1)) found.add(Milestone(MilestoneKind.total, play.playedAt, index + 1));
    final artist = artistPlays[play.artistKey] = (artistPlays[play.artistKey] ?? 0) + 1;
    if (artist == 1) firstHeard[play.artistKey] = play;
    if (artistSteps.contains(artist)) {
      found.add(Milestone(MilestoneKind.artist, play.playedAt, artist, name: play.artist, key: play.artistKey));
    }
    final track = trackPlays[play.trackKey] = (trackPlays[play.trackKey] ?? 0) + 1;
    if (trackSteps.contains(track)) {
      found.add(Milestone(MilestoneKind.track, play.playedAt, track,
          name: play.name, artist: play.artist, key: play.trackKey));
    }
  }
  firstHeard.forEach((key, play) {
    final count = artistPlays[key]!;
    if (count >= artistSteps.first) {
      found.add(Milestone(MilestoneKind.met, play.playedAt, count, name: play.artist, key: key));
    }
  });
  return found..sort((a, b) => b.at.compareTo(a.at));
}

/// The next count of all plays worth marking and how many plays are left to it
(int, int)? nextTotalStep(int plays) {
  for (final step in totalSteps) {
    if (step > plays) return (step, step - plays);
  }
  return null;
}

/// The same moment a year earlier (29 February becomes the 28th)
DateTime yearBack(DateTime moment) {
  final back = DateTime(moment.year - 1, moment.month, moment.day, moment.hour, moment.minute);
  return back.month == moment.month ? back : DateTime(moment.year - 1, moment.month, 28, moment.hour, moment.minute);
}
