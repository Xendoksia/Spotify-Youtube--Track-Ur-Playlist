import 'package:flutter/material.dart';

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

/// The milestones reached in the period with how far the next count of plays is, and the top tracks of the same
/// time a year earlier once there are plays from then, as the desktop app's milestones card
class MilestonesCard extends StatelessWidget {
  static const shown = 8;
  static const yearAgo = 3;

  final DataStore store;
  final Period period;
  final DateRange range;

  const MilestonesCard({super.key, required this.store, required this.period, required this.range});

  @override
  Widget build(BuildContext context) {
    final all = store.plays;
    final muted = Palette.of(context).muted;
    final step = nextTotalStep(all.length);
    final reached = milestones(all).where((m) => range.contains(m.at)).take(shown).toList();
    final ago = period == Period.all
        ? <Ranked>[]
        : topTracks(playsIn(all, DateRange(yearBack(range.start), yearBack(range.end))), limit: yearAgo);
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
          for (final milestone in reached)
            _row(context, _date(context, milestone.at), _text(context, milestone), _open(context, milestone)),
          if (ago.isNotEmpty) ...[
            Padding(
              padding: const EdgeInsets.only(top: 12, bottom: 4),
              child: Text(context.t('stats.year_ago'), style: const TextStyle(fontWeight: FontWeight.w600)),
            ),
            for (final (index, track) in ago.indexed)
              _row(context, '${index + 1}.', '${track.title}  ·  ${track.artist}  ·  ${context.plays(track.plays)}',
                  () => openDetail(context, store, DetailTarget.ranked(DetailKind.track, track))),
          ],
        ],
      ),
    );
  }

  Widget _row(BuildContext context, String left, String text, VoidCallback? onTap) => InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 5),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(
                width: 64,
                child: Text(left, style: TextStyle(color: Palette.of(context).muted, fontSize: 13)),
              ),
              Expanded(child: Text(text)),
            ],
          ),
        ),
      );

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

/// The days in a row with a play up to today, the longest run, and the last two weeks as dots. Only on a step
/// (3, 7, 14 days and on) or a new record does it say something more, in the manner of the run's main genre
class StreakCard extends StatelessWidget {
  final DataStore store;

  const StreakCard({super.key, required this.store});

  /// The family of the genre most played during the run, by its artists' main genres
  static String _family(List<Play> all, DateTime start) {
    final weights = <String, int>{};
    for (final play in all) {
      if (play.playedAt.isBefore(start)) continue;
      final genre = Genres.instance.mainGenre(play.artistKey);
      if (genre == null) continue;
      final family = genreFamily(genre);
      weights[family] = (weights[family] ?? 0) + 1;
    }
    if (weights.isEmpty) return 'other';
    return weights.entries.reduce((a, b) => b.value > a.value ? b : a).key;
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

  /// The run's title in the manner of its genre, with the genre's sigil and a line; on the day of a new title or
  /// a new record it stands out with a word for the day
  Widget _level(BuildContext context, Streak streak, String family) {
    final palette = Palette.of(context);
    final level = streakLevel(streak.current);
    final card = Row(
      children: [
        ColorFiltered(
          colorFilter: ColorFilter.mode(palette.chart, BlendMode.srcIn),
          child: GenreSigil(family: family, size: 56),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (streak.special)
                Text(
                  streak.record
                      ? context.t('stats.streak.record', {'days': context.number(streak.current)})
                      : context.t('stats.streak.level_up'),
                  style: TextStyle(color: palette.chart, fontWeight: FontWeight.w800, fontSize: 13),
                ),
              Text(context.t('stats.streak.level', {'level': level}),
                  style: TextStyle(color: palette.muted, fontSize: 12, fontWeight: FontWeight.w600)),
              Text(context.t('stats.streak.$family.$level'),
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
              const SizedBox(height: 2),
              Text(context.t('stats.streak.$family.$level.say')),
            ],
          ),
        ),
      ],
    );
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: palette.chart.withValues(alpha: streak.special ? 0.16 : 0.07),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: palette.chart.withValues(alpha: streak.special ? 0.55 : 0.2)),
      ),
      child: card,
    );
  }

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final all = store.plays;
    final streak = streakOf(all, DateTime.now());
    final during = streak.start == null ? const <Play>[] : all.where((p) => !p.playedAt.isBefore(streak.start!)).toList();
    final song = topTracks(during, limit: 1);
    final artist = topArtists(during, limit: 1);
    final days = streak.current;
    final next = streakNextLevel(days);
    final family = days == 0 ? 'other' : _family(all, streak.start!);
    final big = Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800, color: palette.chart);
    return SectionCard(
      title: context.t('stats.streak'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
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
          const SizedBox(height: 14),
          if (days >= streakLevels.first) _level(context, streak, family),
          const SizedBox(height: 14),
          if (next != null) ...[
            StreakRoad(days: days),
            const SizedBox(height: 8),
          ],
          Text(
            next == null
                ? context.t('stats.streak.top')
                : days < streakLevels.first
                    ? context.t('stats.streak.first')
                    : next - days == 1
                        ? context.t('stats.streak.next_tomorrow')
                        : context.t('stats.streak.next', {
                            'days': context.number(next),
                            'left': context.number(next - days),
                          }),
            style: TextStyle(color: palette.muted, fontSize: 13),
          ),
          const SizedBox(height: 8),
          // What carried the run
          if (song.isNotEmpty) _star(context, context.t('stats.streak.song'), song.first, DetailKind.track),
          if (artist.isNotEmpty) _star(context, context.t('stats.streak.artist'), artist.first, DetailKind.artist),
          const SizedBox(height: 8),
          if (!streak.special)
            Text(
              context.t(days == 0
                  ? 'stats.streak.none'
                  : streak.today
                      ? 'stats.streak.going'
                      : 'stats.streak.keep'),
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
        ],
      ),
    );
  }
}

/// The run as a road between the level behind it, the next one and the one after, with a flame that slides to
/// the day the run is on; the next stop is where the next title opens
class StreakRoad extends StatelessWidget {
  final int days;

  const StreakRoad({super.key, required this.days});

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final level = streakLevel(days);
    final from = level == 0 ? 0 : streakLevels[level - 1];
    final next = streakNextLevel(days)!;
    final after = streakNextLevel(next);
    // The stops sit evenly, and the flame between the first two as far as the run has come
    final gap = after == null ? 1.0 : 0.5;
    final share = (days - from) / (next - from);
    final stops = [(from, 0.0), (next, gap), if (after != null) (after, 1.0)];
    return SizedBox(
      height: 64,
      child: LayoutBuilder(
        builder: (context, box) {
          const inset = 14.0;
          final width = box.maxWidth - inset * 2;
          return TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: share * gap),
            duration: const Duration(milliseconds: 1100),
            curve: Curves.easeOutCubic,
            builder: (context, reached, _) => Stack(
              clipBehavior: Clip.none,
              children: [
                // The road, filled up to the flame
                Positioned(
                  left: inset,
                  right: inset,
                  top: 30,
                  child: Container(
                    height: 6,
                    decoration: BoxDecoration(color: palette.border, borderRadius: BorderRadius.circular(3)),
                  ),
                ),
                Positioned(
                  left: inset,
                  top: 30,
                  child: Container(
                    width: width * reached,
                    height: 6,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(3),
                      gradient: LinearGradient(colors: [palette.chart.withValues(alpha: 0.5), palette.chart]),
                    ),
                  ),
                ),
                for (final (step, at) in stops)
                  Positioned(
                    left: inset + width * at - 22,
                    top: 23,
                    width: 44,
                    child: Column(
                      children: [
                        Container(
                          width: 20,
                          height: 20,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: step <= days ? palette.chart : Theme.of(context).colorScheme.surface,
                            border: Border.all(color: step == next ? palette.chart : palette.border, width: 2.5),
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(context.number(step),
                            style: TextStyle(
                                fontSize: 12,
                                fontWeight: step == next ? FontWeight.w800 : FontWeight.w500,
                                color: step == next ? null : palette.muted)),
                      ],
                    ),
                  ),
                Positioned(
                  left: inset + width * reached - 14,
                  top: 0,
                  child: const Text('\u{1F525}', style: TextStyle(fontSize: 24)),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
