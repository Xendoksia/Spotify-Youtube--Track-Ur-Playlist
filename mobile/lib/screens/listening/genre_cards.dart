import 'package:fl_chart/fl_chart.dart';
import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../data/genres.dart';
import '../../data/models.dart';
import '../../data/mood.dart';
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
  static const ringCount = 6;
  static const webAxes = 6;

  /// The families the web always shows enough of to make a shape, when the period has fewer
  static const webDefaults = ['metal', 'rock', 'pop'];

  final List<Play> all;
  final List<Play> plays;

  /// The previous period's plays, whose families the web outlines; null for all time
  final List<Play>? previous;
  final Period period;

  const GenresCard({super.key, required this.all, required this.plays, required this.period, this.previous});

  /// The share of each genre family of the plays by genre, as the desktop app's family_shares
  static Map<String, double> _families(Map<String, int> plays) {
    final total = plays.values.fold<int>(0, (a, b) => a + b);
    final families = <String, double>{};
    if (total == 0) return families;
    for (final MapEntry(key: name, value: count) in plays.entries) {
      final family = genreFamily(name);
      families[family] = (families[family] ?? 0) + count / total;
    }
    return families;
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: Genres.instance,
        builder: (context, _) {
          final result = genreShares(all, plays);
          final muted = Palette.of(context).muted;
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
                else ...[
                  _ring(context, result.genres, result.known),
                  const SizedBox(height: 20),
                  _web(context, {for (final genre in result.genres) genre.name: genre.plays}, previous, period),
                ],
              ],
            ),
          );
        },
      );
}

/// The ring of the biggest genres and the rest in the genres' colors, the biggest named in the middle, with the
/// slices' names and shares beside it, as the desktop app's GenreRing
Widget _ring(BuildContext context, List<GenreShare> genres, int known) {
  // The genres' four colors and two more, as the desktop app's --series-4 and --series-5
  final colors = [
    ...seriesColors(context),
    ...Theme.of(context).brightness == Brightness.dark
        ? const [Color(0xFF9B6FE8), Color(0xFFE0628F)]
        : const [Color(0xFF8A5CD6), Color(0xFFD1477A)],
  ];
  final palette = Palette.of(context);
  String percent(int value) => context.t('stats.percent', {'value': value});
  final rest = genres.skip(GenresCard.ringCount).fold<int>(0, (sum, genre) => sum + genre.plays);
  final slices = [
    for (final (index, genre) in genres.take(GenresCard.ringCount).indexed)
      (colors[index], capitalized(genre.name), genre.plays),
    if (rest > 0) (otherColor(context), context.t('stats.genre_shift.other'), rest),
  ];
  return Row(
    children: [
      SizedBox(
        width: 132,
        height: 132,
        child: Stack(
          alignment: Alignment.center,
          children: [
            Positioned.fill(
              child: CustomPaint(
                painter: _RingPainter([for (final (color, _, plays) in slices) (color, plays / known)]),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 30),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(slices.first.$2,
                      maxLines: 2,
                      textAlign: TextAlign.center,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                  Text(percent(share(slices.first.$3, known)), style: TextStyle(fontSize: 11, color: palette.muted)),
                ],
              ),
            ),
          ],
        ),
      ),
      const SizedBox(width: 16),
      Expanded(
        child: Column(
          children: [
            for (final (color, name, plays) in slices)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: Row(
                  children: [
                    Container(
                      width: 10,
                      height: 10,
                      decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(3)),
                    ),
                    const SizedBox(width: 8),
                    Expanded(child: Text(name, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13))),
                    Text(percent(share(plays, known)), style: TextStyle(fontSize: 13, color: palette.muted)),
                  ],
                ),
              ),
          ],
        ),
      ),
    ],
  );
}

class _RingPainter extends CustomPainter {
  /// Each slice's color and share of the circle
  final List<(Color, double)> slices;

  _RingPainter(this.slices);

  @override
  void paint(Canvas canvas, Size size) {
    const width = 22.0;
    final rect = Rect.fromCircle(center: size.center(Offset.zero), radius: size.shortestSide / 2 - width / 2);
    final gap = slices.length > 1 ? 0.03 : 0.0;
    var angle = -math.pi / 2;
    for (final (color, part) in slices) {
      final sweep = part * 2 * math.pi;
      if (sweep > gap) {
        canvas.drawArc(
          rect,
          angle + gap / 2,
          sweep - gap,
          false,
          Paint()
            ..color = color
            ..style = PaintingStyle.stroke
            ..strokeWidth = width,
        );
      }
      angle += sweep;
    }
  }

  @override
  bool shouldRepaint(_RingPainter old) => old.slices != slices;
}

/// The genre families' weight as a web, the period's shape in the page's color over the previous period's dashed
/// outline, as the desktop app's FamilyWeb. The distance from the middle grows with the square root of the share,
/// so a family of a few percent still shows beside one of half the plays.
Widget _web(BuildContext context, Map<String, int> plays, List<Play>? previous, Period period) {
  final palette = Palette.of(context);
  final now = GenresCard._families(plays);
  var before = <String, double>{};
  if (previous != null && previous.isNotEmpty) {
    final counts = <String, int>{};
    for (final artist in topArtists(previous, limit: 1 << 30)) {
      if (Genres.instance.mainGenre(artist.key) case final genre?) {
        counts[genre] = (counts[genre] ?? 0) + artist.plays;
      }
    }
    before = GenresCard._families(counts);
  }
  final names = ({...now.keys, ...before.keys}..remove('other')).toList()
    ..sort((a, b) {
      final byNow = (now[b] ?? 0).compareTo(now[a] ?? 0);
      return byNow != 0 ? byNow : (before[b] ?? 0).compareTo(before[a] ?? 0);
    });
  final axes = names.take(GenresCard.webAxes).toList();
  for (final name in GenresCard.webDefaults) {
    if (axes.length >= 3) break;
    if (!axes.contains(name)) axes.add(name);
  }
  final color = MoodColor.of(context) ?? palette.chart;
  final compared = before.isNotEmpty;
  Widget swatch(Widget mark, String name) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [mark, const SizedBox(width: 6), Text(name, style: TextStyle(fontSize: 12, color: palette.muted))],
  );
  return Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      if (compared)
        Wrap(spacing: 16, children: [
          swatch(
            Container(
              width: 10,
              height: 10,
              decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(3)),
            ),
            context.t('stats.this.${period.name}'),
          ),
          swatch(
            Container(
              width: 10,
              height: 10,
              decoration: BoxDecoration(
                border: Border.all(color: palette.muted, width: 1.5),
                borderRadius: BorderRadius.circular(3),
              ),
            ),
            context.t('stats.previous.${period.name}'),
          ),
        ]),
      SizedBox(
        height: 220,
        width: double.infinity,
        child: CustomPaint(
          painter: _WebPainter(
            names: [for (final name in axes) context.t('stats.family.$name')],
            now: [for (final name in axes) now[name] ?? 0],
            before: compared ? [for (final name in axes) before[name] ?? 0] : null,
            color: color,
            grid: palette.border,
            muted: palette.muted,
          ),
        ),
      ),
    ],
  );
}

class _WebPainter extends CustomPainter {
  final List<String> names;
  final List<double> now;
  final List<double>? before;
  final Color color;
  final Color grid;
  final Color muted;

  _WebPainter({
    required this.names,
    required this.now,
    required this.before,
    required this.color,
    required this.grid,
    required this.muted,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = size.shortestSide / 2 - 26;
    final most = [...now, ...?before].fold<double>(0.01, math.max);
    Offset point(int index, double part) {
      final angle = index / names.length * 2 * math.pi;
      final r = radius * math.sqrt(part / most);
      return center + Offset(r * math.sin(angle), -r * math.cos(angle));
    }

    Path shape(List<double> parts) {
      final path = Path()..moveTo(point(0, parts[0]).dx, point(0, parts[0]).dy);
      for (var i = 1; i < parts.length; i++) {
        path.lineTo(point(i, parts[i]).dx, point(i, parts[i]).dy);
      }
      return path..close();
    }

    final line = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1
      ..color = grid;
    for (final ring in const [0.25, 0.5, 1.0]) {
      canvas.drawPath(shape(List.filled(names.length, ring * most)), line);
    }
    for (var i = 0; i < names.length; i++) {
      final end = point(i, most);
      canvas.drawLine(center, end, line);
      final label = TextPainter(
        text: TextSpan(text: names[i], style: TextStyle(fontSize: 11, color: muted)),
        textDirection: TextDirection.ltr,
      )..layout();
      // Just past the spoke's end, leaning away from the middle
      final at = center + (end - center) * 1.14;
      final dx = at.dx < center.dx - 4 ? -label.width : at.dx > center.dx + 4 ? 0.0 : -label.width / 2;
      label.paint(canvas, Offset(at.dx + dx, at.dy - label.height / 2));
    }
    if (before case final previous?) {
      final dashed = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5
        ..color = muted;
      for (final metric in shape(previous).computeMetrics()) {
        for (var d = 0.0; d < metric.length; d += 8) {
          canvas.drawPath(metric.extractPath(d, math.min(d + 4, metric.length)), dashed);
        }
      }
    }
    final web = shape(now);
    canvas.drawPath(web, Paint()..color = color.withValues(alpha: 0.3));
    canvas.drawPath(
      web,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2
        ..strokeJoin = StrokeJoin.round
        ..color = color,
    );
    for (var i = 0; i < names.length; i++) {
      canvas.drawCircle(point(i, now[i]), 3.5, Paint()..color = color);
    }
  }

  @override
  bool shouldRepaint(_WebPainter old) =>
      old.names != names || old.now != now || old.before != before || old.color != color;
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
