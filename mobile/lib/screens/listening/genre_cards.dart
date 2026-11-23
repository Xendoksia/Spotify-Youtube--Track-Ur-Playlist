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
          final muted = Palette.of(context).muted;
          String percent(int value) => context.t('stats.percent', {'value': value});
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
                  SizedBox(
                    height: 30.0 * top.length + 40,
                    child: CustomPaint(
                      size: Size.infinite,
                      painter: _RibbonsPainter(
                        labels: [for (final key in keys) label(key)],
                        places: [
                          for (final key in keys)
                            if (buckets[key] case final genres?)
                              // The biggest share first, the bigger genre of the period on a tie
                              (top.indexed.toList()..sort((a, b) {
                                    final byShare = (genres[b.$2] ?? 0).compareTo(genres[a.$2] ?? 0);
                                    return byShare != 0 ? byShare : a.$1.compareTo(b.$1);
                                  }))
                                  .map((e) => e.$1)
                                  .toList()
                            else
                              null,
                        ],
                        names: [
                          for (final name in top) '${capitalized(name)}  ${percent(share(totals[name]!, known))}',
                        ],
                        colors: colors,
                        text: Theme.of(context).colorScheme.onSurface,
                        muted: muted,
                        ring: Theme.of(context).colorScheme.surfaceContainer,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          );
        },
      );
}

/// The main genres' places in each column (the day of a week, the week of a month, the month of a year) as thick
/// ribbons in their colors, the first place at the top, so a genre that overtakes another crosses over it, as the
/// desktop app's GenreRibbons. Columns without a known genre are passed over, and the names stand at the ribbons'
/// ends with the genre's share of the period.
class _RibbonsPainter extends CustomPainter {
  final List<String> labels;

  /// Each column's genres (their index in [names]) from the first place down, or null for a column without any
  final List<List<int>?> places;
  final List<String> names;
  final List<Color> colors;
  final Color text;
  final Color muted;

  /// The card's color, round the dots so a crossing ribbon is cut cleanly
  final Color ring;

  _RibbonsPainter({
    required this.labels,
    required this.places,
    required this.names,
    required this.colors,
    required this.text,
    required this.muted,
    required this.ring,
  });

  TextPainter _text(String value, TextStyle style, double width) =>
      TextPainter(text: TextSpan(text: value, style: style), textDirection: TextDirection.ltr, maxLines: 1, ellipsis: '…')
        ..layout(maxWidth: width);

  @override
  void paint(Canvas canvas, Size size) {
    final heard = [for (final (index, order) in places.indexed) if (order != null) index];
    if (heard.isEmpty || names.isEmpty) return;
    const left = 16.0, top = 10.0, bottom = 26.0;
    final nameStyle = TextStyle(color: text, fontSize: 12, fontWeight: FontWeight.w600);
    final nameWidth = names.map((n) => _text(n, nameStyle, double.infinity).width).reduce((a, b) => a > b ? a : b);
    final right = (nameWidth + 14).clamp(0.0, size.width * 0.42);
    final plot = size.width - left - right;
    final row = names.length > 1 ? (size.height - top - bottom) / (names.length - 1) : 0.0;
    double x(int index) => left + (index + 0.5) / places.length * plot;
    double y(int place) => top + place * row;

    final placeStyle = TextStyle(color: muted, fontSize: 11);
    for (var place = 0; place < names.length; place++) {
      final number = _text('${place + 1}', placeStyle, left);
      number.paint(canvas, Offset(left - 8 - number.width, y(place) - number.height / 2));
    }
    final every = places.length <= 7 ? 1 : (places.length / 6).ceil();
    for (var index = 0; index < labels.length; index += every) {
      final label = _text(labels[index], placeStyle, plot / labels.length * every + 8);
      label.paint(canvas, Offset(x(index) - label.width / 2, size.height - label.height));
    }

    for (var genre = 0; genre < names.length; genre++) {
      final points = [for (final index in heard) Offset(x(index), y(places[index]!.indexOf(genre)))];
      final color = colors[genre % colors.length];
      if (points.length > 1) {
        canvas.drawPath(
          _smooth(points),
          Paint()
            ..color = color
            ..style = PaintingStyle.stroke
            ..strokeWidth = 8
            ..strokeCap = StrokeCap.round
            ..strokeJoin = StrokeJoin.round,
        );
      }
      for (final point in points) {
        canvas.drawCircle(point, 5.5, Paint()..color = ring);
        canvas.drawCircle(point, 4, Paint()..color = color);
      }
      final name = _text(names[genre], nameStyle, right - 10);
      name.paint(canvas, Offset(points.last.dx + 10, points.last.dy - name.height / 2));
    }
  }

  /// A soft line through the points (Catmull-Rom as cubic Béziers), as the desktop app's smooth()
  static Path _smooth(List<Offset> points) {
    final p = [points.first, ...points, points.last];
    final path = Path()..moveTo(p[1].dx, p[1].dy);
    for (var i = 1; i < p.length - 2; i++) {
      final c1 = p[i] + (p[i + 1] - p[i - 1]) / 6;
      final c2 = p[i + 1] - (p[i + 2] - p[i]) / 6;
      path.cubicTo(c1.dx, c1.dy, c2.dx, c2.dy, p[i + 1].dx, p[i + 1].dy);
    }
    return path;
  }

  @override
  bool shouldRepaint(_RibbonsPainter old) =>
      old.labels != labels || old.places != places || old.names != names || old.colors != colors || old.text != text;
}
