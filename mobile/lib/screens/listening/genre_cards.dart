import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../../data/genres.dart';
import '../../data/models.dart';
import '../../data/stats.dart';
import '../../l10n/strings.dart';
import '../../theme/palette.dart';
import '../../widgets/cards.dart';
import '../../widgets/format.dart';

const genreCount = 8;

/// The desktop app's categorical colors (charts.SERIES) and its "other" color
List<Color> seriesColors(BuildContext context) => Theme.of(context).brightness == Brightness.dark
    ? const [Color(0xFF3987E5), Color(0xFFD95926), Color(0xFF199E70), Color(0xFFC98500)]
    : const [Color(0xFF2A78D6), Color(0xFFEB6834), Color(0xFF1BAF7A), Color(0xFFEDA100)];

Color otherColor(BuildContext context) =>
    Theme.of(context).brightness == Brightness.dark ? const Color(0xFF4A505A) : const Color(0xFFB6BBC3);

String capitalized(String name) => name.isEmpty ? name : name[0].toUpperCase() + name.substring(1);

/// Share of the period's plays per genre, as the desktop app's genres card; it fills in as the genres arrive
class GenresCard extends StatelessWidget {
  final List<Play> all;
  final List<Play> plays;

  const GenresCard({super.key, required this.all, required this.plays});

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: Genres.instance,
        builder: (context, _) {
          final result = genreShares(all, plays);
          final muted = Palette.of(context).muted;
          String percent(int value) => context.t('stats.percent', {'value': value});
          final names = [for (final genre in result.genres) capitalized(genre.name)];
          final parts = [
            if (names.isNotEmpty)
              context.t('stats.genres.summary.${names.length.clamp(1, 3)}', {
                'first': names[0],
                if (names.length > 1) 'second': names[1],
                if (names.length > 2) 'third': names[2],
                'count': context.number(names.length),
              }),
            if (result.waiting > 0) context.t('stats.genres.loading', {'count': context.number(result.waiting)}),
          ];
          return SectionCard(
            title: context.t('stats.genres'),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (parts.isNotEmpty) Text(parts.join('  ·  '), style: TextStyle(color: muted, fontSize: 13)),
                const SizedBox(height: 8),
                if (result.genres.isEmpty)
                  Text(context.t('stats.genres.none'), style: TextStyle(color: muted))
                else
                  RankedList(
                    rows: [
                      for (final genre in result.genres.take(genreCount))
                        Ranked(genre.name, capitalized(genre.name),
                            '${percent(share(genre.plays, result.total))}  ·  ${genre.artists.take(3).join(', ')}',
                            genre.plays, 0),
                    ],
                  ),
              ],
            ),
          );
        },
      );
}

/// How the share of the period's main genres changed over it, as the desktop app's GenreShift: per day of a week,
/// per week of a month, per month of a year or of all time (per year past three years). The four biggest genres get
/// a color, the rest is "other"; plays by artists of unknown genre are left out.
class GenreShiftCard extends StatelessWidget {
  static const shown = 4;
  static const maxMonths = 36;

  final Period period;
  final DateRange range;

  /// The period's plays
  final List<Play> plays;

  const GenreShiftCard({super.key, required this.period, required this.range, required this.plays});

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: Genres.instance,
        builder: (context, _) {
          final genres = Genres.instance;
          final now = DateTime.now();
          final first = plays.isEmpty ? now : plays.map((p) => p.playedAt).reduce((a, b) => a.isBefore(b) ? a : b);
          final yearly = period == Period.all && (now.year - first.year) * 12 + now.month - first.month >= maxMonths;
          DateTime bucketOf(DateTime moment) {
            final day = DateTime(moment.year, moment.month, moment.day);
            if (yearly) return DateTime(day.year);
            return switch (period) {
              Period.week => day,
              // A week begins on Monday, or on the 1st when the month begins in the middle of it
              Period.month => () {
                  final monday = DateTime(day.year, day.month, day.day - (day.weekday - 1));
                  return monday.month == day.month ? monday : DateTime(day.year, day.month);
                }(),
              _ => DateTime(day.year, day.month),
            };
          }

          // Every bucket of the period up to today, also the ones without plays; all time starts at the first play
          final keys = <DateTime>[];
          var day = period == Period.all ? DateTime(first.year, first.month, first.day) : range.start;
          final last = range.end.isBefore(now) ? range.end : DateTime(now.year, now.month, now.day + 1);
          while (day.isBefore(last)) {
            final key = bucketOf(day);
            if (!keys.contains(key)) keys.add(key);
            day = DateTime(day.year, day.month, day.day + 1);
          }

          final buckets = <DateTime, Map<String, int>>{};
          final totals = <String, int>{};
          var known = 0;
          for (final play in plays) {
            final genre = genres.mainGenre(play.artistKey);
            if (genre == null) continue;
            known++;
            final bucket = buckets.putIfAbsent(bucketOf(play.playedAt), () => {});
            bucket[genre] = (bucket[genre] ?? 0) + 1;
            totals[genre] = (totals[genre] ?? 0) + 1;
          }
          final top = (totals.entries.toList()..sort((a, b) => b.value.compareTo(a.value)))
              .take(shown)
              .map((e) => e.key)
              .toList();
          final colors = seriesColors(context);
          final other = otherColor(context);
          final muted = Palette.of(context).muted;
          String percent(int value) => context.t('stats.percent', {'value': value});
          final others = known - top.fold<int>(0, (sum, name) => sum + totals[name]!);
          final unit = yearly ? 'year' : period.name;

          String label(DateTime key) {
            if (yearly) return '${key.year}';
            return switch (period) {
              Period.week => context.dateFormat('E').format(key),
              Period.month => context.dateFormat('d MMM').format(key),
              Period.year => context.dateFormat('MMMMM').format(key),
              Period.all => context.dateFormat("MMM ''yy").format(key),
            };
          }

          return SectionCard(
            title: context.t('stats.genre_shift'),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (known > 0)
                  Text(context.t('stats.genre_shift.summary', {'unit': context.t('stats.genre_shift.unit.$unit')}),
                      style: TextStyle(color: muted, fontSize: 13)),
                const SizedBox(height: 8),
                if (known == 0)
                  Text(context.t('stats.genres.none'), style: TextStyle(color: muted))
                else ...[
                  Wrap(spacing: 14, runSpacing: 4, children: [
                    for (final (index, name) in top.indexed)
                      _legend(colors[index], '${capitalized(name)}  ${percent(share(totals[name]!, known))}'),
                    if (others > 0)
                      _legend(other, '${context.t('stats.genre_shift.other')}  ${percent(share(others, known))}'),
                  ]),
                  const SizedBox(height: 12),
                  SizedBox(
                    height: 170,
                    child: BarChart(BarChartData(
                      maxY: 1,
                      borderData: FlBorderData(show: false),
                      gridData: const FlGridData(show: false),
                      barTouchData: BarTouchData(enabled: false),
                      titlesData: FlTitlesData(
                        topTitles: const AxisTitles(),
                        rightTitles: const AxisTitles(),
                        leftTitles: const AxisTitles(),
                        bottomTitles: AxisTitles(
                          sideTitles: SideTitles(
                            showTitles: true,
                            getTitlesWidget: (value, meta) {
                              final index = value.toInt();
                              final every = keys.length <= 7 ? 1 : (keys.length / 6).ceil();
                              if (index >= keys.length || index % every != 0) return const SizedBox.shrink();
                              return SideTitleWidget(
                                meta: meta,
                                child: Text(label(keys[index]), style: TextStyle(fontSize: 11, color: muted)),
                              );
                            },
                          ),
                        ),
                      ),
                      barGroups: [
                        for (final (index, key) in keys.indexed) _column(index, buckets[key] ?? {}, top, colors, other,
                            keys.length > 12 ? 8.0 : 18.0),
                      ],
                    )),
                  ),
                ],
              ],
            ),
          );
        },
      );

  static BarChartGroupData _column(
      int x, Map<String, int> genres, List<String> top, List<Color> colors, Color other, double width) {
    final total = genres.values.fold<int>(0, (sum, plays) => sum + plays);
    final items = <BarChartRodStackItem>[];
    var from = 0.0;
    if (total > 0) {
      final parts = [
        for (final (index, name) in top.indexed) ((genres[name] ?? 0) / total, colors[index]),
        ((total - top.fold<int>(0, (sum, name) => sum + (genres[name] ?? 0))) / total, other),
      ];
      for (final (part, color) in parts) {
        if (part == 0) continue;
        items.add(BarChartRodStackItem(from, from + part, color));
        from += part;
      }
    }
    return BarChartGroupData(x: x, barRods: [
      BarChartRodData(
        toY: total > 0 ? 1 : 0,
        width: width,
        rodStackItems: items,
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(3),
      ),
    ]);
  }

  static Widget _legend(Color color, String text) => Row(mainAxisSize: MainAxisSize.min, children: [
        Container(width: 10, height: 10, decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(2))),
        const SizedBox(width: 6),
        Text(text, style: const TextStyle(fontSize: 13)),
      ]);
}
