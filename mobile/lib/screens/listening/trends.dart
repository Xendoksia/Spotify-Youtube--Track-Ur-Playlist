import 'package:flutter/material.dart';

import '../../data/mood.dart';
import '../../data/genres.dart';
import '../../data/models.dart';
import '../../data/stats.dart';
import '../../l10n/strings.dart';
import '../../state/data_store.dart';
import '../../theme/palette.dart';
import '../../widgets/artwork_image.dart';
import '../../widgets/cards.dart';
import '../../widgets/format.dart';
import 'wrapped_visuals.dart' show GenreSigil;
import 'detail_screen.dart';

/// How varied the period's listening was, as the desktop app's diversity card: the share of its five most played
/// artists, of different tracks and of new tracks, sentences comparing it with the period before, and those five
/// artists with their share of the plays
class DiversityCard extends StatelessWidget {
  /// Points of difference in the new tracks' share that count as more or less discovery
  static const change = 5;
  static const focused = 70;
  static const wide = 40;

  final DataStore store;
  final Period period;
  final int offset;
  final DateRange range;

  /// The period's plays
  final List<Play> plays;

  const DiversityCard(
      {super.key,
      required this.store,
      required this.period,
      required this.offset,
      required this.range,
      required this.plays});

  @override
  Widget build(BuildContext context) {
    final all = store.plays;
    final now = Diversity.of(all, range);
    String percent(int value) => context.t('stats.percent', {'value': value});
    final top5 = share(now.top5, now.plays);
    final fresh = share(now.fresh, now.plays);
    final sentences = <String>[];
    // Over all time every track is new, so there is nothing to compare
    if (period != Period.all) {
      final previous = periodRange(period, offset + 1, DateTime.now());
      final first = all.map((p) => p.playedAt).reduce((a, b) => a.isBefore(b) ? a : b);
      // Only once the whole period before was recorded, or everything in it would look new
      if (!first.isAfter(previous.start)) {
        final before = Diversity.of(all, previous);
        if (before.plays > 0) {
          final beforeFresh = share(before.fresh, before.plays);
          final key = fresh - beforeFresh >= change
              ? 'more_new'
              : beforeFresh - fresh >= change
                  ? 'more_familiar'
                  : 'same';
          sentences.add(context.t('stats.diversity.$key', {'before': percent(beforeFresh), 'now': percent(fresh)}));
        }
      }
    }
    if (top5 >= focused && now.artists > 5) {
      sentences.add(context.t('stats.diversity.focused'));
    } else if (top5 <= wide) {
      sentences.add(context.t('stats.diversity.wide'));
    }
    final artists = topArtists(plays, limit: 5);
    return SectionCard(
      title: context.t('stats.diversity'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // A label on two lines must not push its value below the others
          IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Expanded(child: _value(context, 'stats.diversity.top5', percent(top5))),
                Expanded(child: _value(context, 'stats.diversity.variety', percent(share(now.tracks, now.plays)))),
                if (period != Period.all) Expanded(child: _value(context, 'stats.diversity.new', percent(fresh))),
              ],
            ),
          ),
          if (sentences.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(sentences.join(' ')),
          ],
          Padding(
            padding: const EdgeInsets.only(top: 16, bottom: 4),
            child: Text(context.t('stats.diversity.top_artists'), style: const TextStyle(fontWeight: FontWeight.w600)),
          ),
          RankedList(
            rows: [
              for (final row in artists)
                Ranked(row.key, row.title, percent(share(row.plays, now.plays)), row.plays, row.minutes,
                    artist: row.artist),
            ],
            onTap: (row) => openDetail(context, store, DetailTarget.artist(row.artist)),
          ),
        ],
      ),
    );
  }

  static Widget _value(BuildContext context, String label, String value) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(context.t(label), style: TextStyle(color: Palette.of(context).muted, fontSize: 12)),
          const SizedBox(height: 2),
          Text(value, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w600)),
        ],
      );
}

/// The milestones reached in the period with how far the next count of plays is, as the desktop app's milestones
/// card
class MilestonesCard extends StatelessWidget {
  static const shown = 8;

  final DataStore store;
  final DateRange range;

  const MilestonesCard({super.key, required this.store, required this.range});

  @override
  Widget build(BuildContext context) {
    final all = store.plays;
    final muted = Palette.of(context).muted;
    final step = nextTotalStep(all.length);
    final reached = milestones(all).where((m) => range.contains(m.at)).take(shown).toList();
    return SectionCard(
      title: context.t('stats.milestones'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (step != null)
            Text(context.t('stats.milestones.next', {'count': context.number(step.$1), 'left': context.number(step.$2)}),
                style: TextStyle(color: muted, fontSize: 13)),
          const SizedBox(height: 8),
          if (reached.isEmpty) Text(context.t('stats.milestones.none'), style: TextStyle(color: muted)),
          // A timeline: a dot on a line for each, the date once for the ones of the same day
          for (final (index, milestone) in reached.indexed)
            _row(
              context,
              index > 0 && _date(context, reached[index - 1].at) == _date(context, milestone.at)
                  ? ''
                  : _date(context, milestone.at),
              _text(context, milestone),
              _open(context, milestone),
              first: index == 0,
              last: index == reached.length - 1,
            ),
        ],
      ),
    );
  }

  /// One milestone on the timeline: its date, its dot on the line in the page's color and its words, as the
  /// desktop app's card
  Widget _row(BuildContext context, String left, String text, VoidCallback? onTap,
      {required bool first, required bool last}) {
    final palette = Palette.of(context);
    final color = MoodColor.of(context) ?? palette.chart;
    final line = Color.lerp(palette.border, color, 0.35)!;
    final card = Theme.of(context).colorScheme.surfaceContainer;
    return InkWell(
      onTap: onTap,
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SizedBox(
              width: 56,
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 5),
                child: Text(left, textAlign: TextAlign.right, style: TextStyle(color: palette.muted, fontSize: 13)),
              ),
            ),
            SizedBox(
              width: 28,
              child: Stack(
                alignment: Alignment.topCenter,
                children: [
                  Positioned(
                    top: first ? 12 : 0,
                    bottom: last ? null : 0,
                    height: last ? (first ? 0 : 12) : null,
                    child: Container(width: 2, color: line),
                  ),
                  Positioned(
                    top: 6,
                    child: Container(
                      width: 12,
                      height: 12,
                      decoration: BoxDecoration(
                        color: color,
                        shape: BoxShape.circle,
                        border: Border.all(color: card, width: 2),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 5),
                child: Text(text),
              ),
            ),
          ],
        ),
      ),
    );
  }

  static String _date(BuildContext context, DateTime at) =>
      context.dateFormat(at.year == DateTime.now().year ? 'd MMM' : 'd MMM y').format(at);

  static String _text(BuildContext context, Milestone m) {
    final count = context.number(m.count);
    return switch (m.kind) {
      MilestoneKind.total => context.t('stats.milestones.total', {'count': count}),
      MilestoneKind.artist => context.t('stats.milestones.artist', {'name': m.name, 'count': count}),
      MilestoneKind.track => context.t('stats.milestones.track', {'name': m.name, 'artist': m.artist, 'count': count}),
      MilestoneKind.met => context.t('stats.milestones.met', {'name': m.name, 'plays': context.plays(m.count)}),
      MilestoneKind.start => context.t('stats.milestones.start'),
    };
  }

  VoidCallback? _open(BuildContext context, Milestone m) => switch (m.kind) {
        MilestoneKind.artist || MilestoneKind.met => () => openDetail(context, store, DetailTarget.artist(m.name)),
        MilestoneKind.track => () =>
            openDetail(context, store, DetailTarget.track(store.plays.firstWhere((p) => p.trackKey == m.key))),
        _ => null,
      };
}

/// The tracks and artists played most in the same month a year earlier, each with where it stands this month in
/// words beside it, as the desktop app's card. It is only built when there were plays then
class YearAgoCard extends StatelessWidget {
  static const shown = 3;

  final DataStore store;

  /// The month's first day
  final DateTime month;

  /// That month's plays
  final List<Play> plays;

  /// This month's plays
  final List<Play> thisMonth;

  const YearAgoCard(
      {super.key, required this.store, required this.month, required this.plays, required this.thisMonth});

  @override
  Widget build(BuildContext context) {
    final muted = Palette.of(context).muted;
    final tracksNow = topTracks(thisMonth, limit: 1 << 30).map((r) => r.key).toList();
    final artistsNow = topArtists(thisMonth, limit: 1 << 30).map((r) => r.key).toList();
    return SectionCard(
      title: context.t('stats.year_ago'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(context.t('stats.year_ago.summary', {'month': context.dateFormat('MMMM y').format(month)}),
              style: TextStyle(color: muted, fontSize: 13)),
          const SizedBox(height: 12),
          Text(context.t('stats.year_ago.tracks'), style: const TextStyle(fontWeight: FontWeight.w600)),
          for (final track in topTracks(plays, limit: shown)) _row(context, track, DetailKind.track, tracksNow),
          const SizedBox(height: 12),
          Text(context.t('stats.year_ago.artists'), style: const TextStyle(fontWeight: FontWeight.w600)),
          for (final artist in topArtists(plays, limit: shown)) _row(context, artist, DetailKind.artist, artistsNow),
        ],
      ),
    );
  }

  /// Where a track or artist stands in this month's plays, [ranked] most played first
  Widget _status(BuildContext context, String key, List<String> ranked) {
    final palette = Palette.of(context);
    final status = ranked.take(shown).contains(key) ? 'top' : ranked.contains(key) ? 'still' : 'gone';
    return Text(
      context.t('stats.year_ago.$status', {'count': shown}),
      style: TextStyle(
        color: status == 'top' ? palette.added : palette.muted.withValues(alpha: status == 'gone' ? 0.65 : 1),
        fontSize: 12,
        fontWeight: status == 'top' ? FontWeight.w600 : FontWeight.normal,
      ),
    );
  }

  Widget _row(BuildContext context, Ranked row, DetailKind kind, List<String> ranked) => InkWell(
        onTap: () => openDetail(context, store, DetailTarget.ranked(kind, row)),
        borderRadius: BorderRadius.circular(10),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 6),
          child: Row(
            children: [
              kind == DetailKind.track
                  ? ArtworkImage.cover(artist: row.artist, album: row.album, name: row.title, size: 42)
                  : ArtworkImage.artist(artist: row.artist, size: 42),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(row.title,
                        maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
                    if (row.subtitle.isNotEmpty)
                      Text(row.subtitle,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(color: Palette.of(context).muted, fontSize: 13)),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              _status(context, row.key, ranked),
            ],
          ),
        ),
      );
}

/// Two streaks on one card: days in a row with any play (with the longest run and the song and artist that
/// carried it), and below it, apart, days in a row of one genre, which earns titles in its manner at 3, 7, 14, 30
/// and 100 days with a road to the next one
class StreakCard extends StatelessWidget {
  final DataStore store;

  const StreakCard({super.key, required this.store});

  /// The genre family with the longest run going on now, by its artists' main genres (most plays in the run if
  /// two are as long); null without a genre run
  static GenreStreak? _genreStreak(List<Play> all, DateTime now) {
    final days = <String, Set<DateTime>>{};
    for (final play in all) {
      final genre = Genres.instance.mainGenre(play.artistKey);
      if (genre == null) continue;
      days.putIfAbsent(genreFamily(genre), () => {}).add(DateTime(play.playedAt.year, play.playedAt.month, play.playedAt.day));
    }
    GenreStreak? best;
    for (final MapEntry(key: family, value: played) in days.entries) {
      final run = currentRun(played, now);
      if (run.current == 0) continue;
      if (best == null || run.current > best.days || (run.current == best.days && family != 'other' && best.family == 'other')) {
        best = GenreStreak(family, run.current, run.today);
      }
    }
    return best;
  }

  /// The run's most played song or artist, with its picture, opening its page
  Widget _star(BuildContext context, String label, Ranked row, DetailKind kind) {
    final muted = Palette.of(context).muted;
    return InkWell(
      onTap: () => openDetail(context, store, DetailTarget.ranked(kind, row)),
      borderRadius: BorderRadius.circular(10),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(
          children: [
            kind == DetailKind.track
                ? ArtworkImage.cover(artist: row.artist, album: row.album, name: row.title, size: 42)
                : ArtworkImage.artist(artist: row.artist, size: 42),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label, style: TextStyle(color: muted, fontSize: 12)),
                  Text(kind == DetailKind.track ? '${row.title}  ·  ${row.artist}' : row.title,
                      maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
                ],
              ),
            ),
            Text(context.plays(row.plays), style: TextStyle(color: muted, fontSize: 13)),
          ],
        ),
      ),
    );
  }

  /// The genre's run: how long it has gone on with the genre's sigil, its message for the level reached, and the
  /// road to the next message; on the day a new one opens it stands out
  Widget _genre(BuildContext context, GenreStreak genre) {
    final palette = Palette.of(context);
    final level = streakLevel(genre.days);
    final next = streakNextLevel(genre.days);
    final levelUp = genre.today && streakLevels.contains(genre.days);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: palette.chart.withValues(alpha: levelUp ? 0.16 : 0.07),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: palette.chart.withValues(alpha: levelUp ? 0.55 : 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              ColorFiltered(
                colorFilter: ColorFilter.mode(palette.chart, BlendMode.srcIn),
                child: GenreSigil(family: genre.family, size: 56),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      context.t('stats.streak.genre', {
                        'days': context.number(genre.days),
                        'genre': context.t('stats.streak.genre.${genre.family}'),
                      }),
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
                    ),
                    if (levelUp)
                      Text(context.t('stats.streak.level_up'),
                          style: TextStyle(color: palette.chart, fontWeight: FontWeight.w800, fontSize: 13)),
                    if (level > 0) ...[
                      const SizedBox(height: 6),
                      Text(context.t('stats.streak.${genre.family}.$level.say'), style: const TextStyle(fontSize: 15)),
                    ],
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          StreakRoad(days: genre.days),
          const SizedBox(height: 4),
          Text(
            next == null
                ? context.t('stats.streak.top')
                : level == 0
                    ? context.t('stats.streak.first')
                    : next - genre.days == 1
                        ? context.t('stats.streak.next_tomorrow')
                        : context.t('stats.streak.next', {
                            'days': context.number(next),
                            'left': context.number(next - genre.days),
                          }),
            style: TextStyle(color: palette.muted, fontSize: 13),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final all = store.plays;
    final now = DateTime.now();
    final streak = streakOf(all, now);
    final days = streak.current;
    final genre = days == 0 ? null : _genreStreak(all, now);
    final during = streak.start == null ? const <Play>[] : all.where((p) => !p.playedAt.isBefore(streak.start!)).toList();
    final song = topTracks(during, limit: 1);
    final artist = topArtists(during, limit: 1);
    final big = Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800, color: palette.chart);
    return SectionCard(
      title: context.t('stats.streak'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Days in a row with any play
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(context.number(days), style: big),
              const SizedBox(width: 8),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Text(context.t(days == 1 ? 'stats.streak.day_one' : 'stats.streak.days')),
                ),
              ),
              if (streak.longest > 0)
                Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Text(context.t('stats.streak.longest', {'days': context.number(streak.longest)}),
                      style: TextStyle(color: palette.muted, fontSize: 13)),
                ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            streak.record
                ? context.t('stats.streak.record', {'days': context.number(days)})
                : context.t(days == 0
                    ? 'stats.streak.none'
                    : streak.today
                        ? 'stats.streak.going'
                        : 'stats.streak.keep'),
            style: TextStyle(fontWeight: FontWeight.w600, color: streak.record ? palette.chart : null),
          ),
          // Days in a row of one genre, apart
          if (genre != null) ...[
            const SizedBox(height: 16),
            _genre(context, genre),
          ],
          const SizedBox(height: 8),
          // What carried the run
          if (song.isNotEmpty) _star(context, context.t('stats.streak.song'), song.first, DetailKind.track),
          if (artist.isNotEmpty) _star(context, context.t('stats.streak.artist'), artist.first, DetailKind.artist),
        ],
      ),
    );
  }
}

/// A genre family's run going on now
class GenreStreak {
  final String family;
  final int days;
  final bool today;

  const GenreStreak(this.family, this.days, this.today);
}

/// The whole ladder of levels as a road, each stop a title, with a flame that slides to where the run is: the stops
/// passed are filled and the next one, where the next title opens, is ringed
class StreakRoad extends StatelessWidget {
  final int days;

  const StreakRoad({super.key, required this.days});

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final last = streakLevels.length - 1;
    final next = streakLevel(days);
    return SizedBox(
      height: 62,
      child: LayoutBuilder(
        builder: (context, box) {
          const inset = 12.0;
          final width = box.maxWidth - inset * 2;
          return TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: streakPlace(days) / last),
            duration: const Duration(milliseconds: 1200),
            curve: Curves.easeOutCubic,
            builder: (context, reached, _) => Stack(
              clipBehavior: Clip.none,
              children: [
                Positioned(
                  left: inset,
                  right: inset,
                  top: 30,
                  child: Container(
                    height: 5,
                    decoration: BoxDecoration(color: palette.border, borderRadius: BorderRadius.circular(3)),
                  ),
                ),
                Positioned(
                  left: inset,
                  top: 30,
                  child: Container(
                    width: width * reached,
                    height: 5,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(3),
                      gradient: LinearGradient(colors: [palette.chart.withValues(alpha: 0.5), palette.chart]),
                    ),
                  ),
                ),
                for (final (index, step) in streakLevels.indexed)
                  Positioned(
                    left: inset + width * index / last - 18,
                    top: 24,
                    width: 36,
                    child: Column(
                      children: [
                        Container(
                          width: 16,
                          height: 16,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: step <= days ? palette.chart : Theme.of(context).colorScheme.surface,
                            border: Border.all(color: index == next ? palette.chart : palette.border, width: 2.5),
                          ),
                        ),
                        const SizedBox(height: 3),
                        Text(context.number(step),
                            style: TextStyle(
                                fontSize: 11,
                                fontWeight: index == next ? FontWeight.w800 : FontWeight.w500,
                                color: index == next ? null : palette.muted)),
                      ],
                    ),
                  ),
                Positioned(
                  left: inset + width * reached - 12,
                  top: 0,
                  child: const Text('\u{1F525}', style: TextStyle(fontSize: 20)),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
