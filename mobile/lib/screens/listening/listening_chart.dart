import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../../data/stats.dart';
import '../../theme/palette.dart';
import '../../widgets/format.dart';
import 'genre_cards.dart' show otherColor;

/// Minutes listened per day, month or year of the period; touching a bar shows its minutes
class ListeningChart extends StatelessWidget {
  final Period period;
  final List<Bucket> buckets;

  /// Plays instead of minutes, as on the detail pages
  final bool plays;

  /// Another name for a bar's day or month than the period's
  final String Function(BuildContext context, DateTime start)? label;

  /// The previous period's bars at the same places (null where it had no such day), drawn grey beside them
  final List<Bucket?>? previous;

  /// The names of the period and the previous one, for the legend over a comparison
  final (String, String)? legend;

  /// Each bar's number over it, drawn as the desktop app's timeline: wide columns without an axis or grid lines
  final bool values;

  const ListeningChart({
    super.key,
    required this.period,
    required this.buckets,
    this.plays = false,
    this.label,
    this.previous,
    this.legend,
    this.values = false,
  });

  /// Shown on the detail pages: plays per day or per month
  factory ListeningChart.detail({Key? key, required List<Bucket> buckets, required bool daily}) => ListeningChart(
    key: key,
    period: daily ? Period.month : Period.year,
    buckets: buckets,
    plays: true,
    label: daily ? null : (context, start) => context.dateFormat("MMM ''yy").format(start),
  );

  String _label(BuildContext context, DateTime start) =>
      label?.call(context, start) ??
      switch (period) {
        Period.week => context.dateFormat('E').format(start),
        Period.month => '${start.day}',
        Period.year => context.dateFormat('MMMMM').format(start),
        Period.all => '${start.year}',
      };

  /// About seven labels at most, so they do not run together
  bool _labelled(int index) {
    final every = buckets.length <= 12 && label == null ? 1 : (buckets.length / 7).ceil();
    return index % every == 0;
  }

  int _value(Bucket bucket) => plays ? bucket.plays : bucket.minutes;

  String _valueText(BuildContext context, int value) => plays ? context.plays(value) : context.minutes(value);

  /// A round step (1, 2, 5 × 10ⁿ) that splits the axis into about four parts
  static double _step(int most) {
    var step = 1.0;
    while (true) {
      for (final factor in const [1, 2, 5]) {
        if (most / (step * factor) <= 4) return step * factor;
      }
      step *= 10;
    }
  }

  /// The numbers shown over all the bars at once, as tooltips without a box. Compared, a day has one label over
  /// the taller of its two bars: with few bars its number above the previous period's grey one, with many (a
  /// month's days) its own number alone and smaller, so neighbours do not run together.
  BarTouchData _numbers(BuildContext context, Color muted, {required bool small}) {
    final text = Theme.of(context).colorScheme.onSurface;
    final size = small ? 8.0 : 10.0;
    return BarTouchData(
      enabled: false,
      touchTooltipData: BarTouchTooltipData(
        getTooltipColor: (_) => Colors.transparent,
        tooltipPadding: EdgeInsets.zero,
        tooltipMargin: 2,
        fitInsideHorizontally: true,
        getTooltipItem: (group, _, rod, rodIndex) {
          final style = TextStyle(fontSize: size, fontWeight: FontWeight.w600, color: text);
          final rods = group.barRods;
          if (previous == null || small) return BarTooltipItem(context.number(rods.last.toY.round()), style);
          return BarTooltipItem(
            context.number(rods.last.toY.round()),
            style,
            children: [
              TextSpan(
                text: '\n${context.number(rods.first.toY.round())}',
                style: TextStyle(fontSize: size, fontWeight: FontWeight.w400, color: muted),
              ),
            ],
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final previous = this.previous;
    final other = otherColor(context);
    var most = buckets.fold<int>(0, (m, b) => _value(b) > m ? _value(b) : m);
    for (final bucket in previous ?? const <Bucket?>[]) {
      if (bucket != null && _value(bucket) > most) most = _value(bucket);
    }
    int previousValue(int index) =>
        previous != null && index < previous.length && previous[index] != null ? _value(previous[index]!) : 0;
    final step = _step(most);
    final top = most == 0 ? step : (most / step).ceil() * step;
    // With the numbers on it, the chart looks as the desktop app's: wide columns with their numbers over them and
    // no axis or grid lines
    final look = values;
    // The numbers only where the desktop app shows them: a month's days are touched for theirs
    final numbered = values && buckets.length <= 12;
    const small = false;
    final stacked = previous != null;
    const height = 180.0;
    // The plot's height under the day labels, and the room its tallest label needs over the bars
    const plot = height - 26;
    final room = stacked ? 28.0 : 14.0;
    final chart = SizedBox(
      height: height,
      child: LayoutBuilder(
        builder: (context, constraints) {
          final slot = constraints.maxWidth / buckets.length;
          // Columns 3 apart, a compared day's two 2 apart, as on the desktop app; the detail pages keep theirs
          final width = !look
              ? (previous == null ? (buckets.length > 12 ? 6.0 : 16.0) : (buckets.length > 12 ? 3.5 : 9.0))
              : ((previous == null ? slot - 3 : (slot - 5) / 2).clamp(2.0, 40.0));
          final radius = look
              ? const BorderRadius.vertical(top: Radius.circular(4), bottom: Radius.circular(2))
              : const BorderRadius.vertical(top: Radius.circular(3));
          return BarChart(
            duration: changeDuration,
            curve: changeCurve,
            BarChartData(
              alignment: BarChartAlignment.spaceAround,
              maxY: !look
                  ? top
                  : most == 0
                  ? 1
                  : numbered
                  ? most / (1 - room / plot)
                  : most.toDouble(),
              borderData: FlBorderData(show: false),
              gridData: look
                  ? const FlGridData(show: false)
                  : FlGridData(
                      drawVerticalLine: false,
                      horizontalInterval: step,
                      getDrawingHorizontalLine: (_) => FlLine(color: palette.border, strokeWidth: 1),
                    ),
              titlesData: FlTitlesData(
                topTitles: const AxisTitles(),
                rightTitles: const AxisTitles(),
                leftTitles: look
                    ? const AxisTitles()
                    : AxisTitles(
                        sideTitles: SideTitles(
                          showTitles: true,
                          reservedSize: 40,
                          interval: step,
                          getTitlesWidget: (value, meta) => SideTitleWidget(
                            meta: meta,
                            child: Text(
                              context.number(value.round()),
                              style: TextStyle(fontSize: 11, color: palette.muted),
                            ),
                          ),
                        ),
                      ),
                bottomTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: true,
                    getTitlesWidget: (value, meta) {
                      final index = value.toInt();
                      if (index >= buckets.length || !_labelled(index)) return const SizedBox.shrink();
                      return SideTitleWidget(
                        meta: meta,
                        child: Text(
                          _label(context, buckets[index].start),
                          style: TextStyle(fontSize: 11, color: palette.muted),
                        ),
                      );
                    },
                  ),
                ),
              ),
              barTouchData: numbered
                  ? _numbers(context, palette.muted, small: small)
                  : BarTouchData(
                      touchTooltipData: BarTouchTooltipData(
                        getTooltipItem: (group, _, rod, rodIndex) {
                          final names = legend;
                          final value = _valueText(context, rod.toY.round());
                          final day = _label(context, buckets[group.x].start);
                          // Compared, the grey bar comes first: the day and both values under it
                          final text = previous == null || names == null
                              ? '$day\n$value'
                              : rodIndex == 0
                              ? '$day\n${names.$2}: $value'
                              : '${names.$1}: $value';
                          return BarTooltipItem(text, const TextStyle(color: Colors.white, fontSize: 12));
                        },
                      ),
                    ),
              barGroups: [
                for (final (index, bucket) in buckets.indexed)
                  BarChartGroupData(
                    x: index,
                    barsSpace: 2,
                    showingTooltipIndicators: !numbered
                        ? const []
                        : previous == null
                        ? const [0]
                        // A month's day shows only its own number, so it stands over its own bar
                        : [!small && previousValue(index) > _value(bucket) ? 0 : 1],
                    barRods: [
                      if (previous != null)
                        BarChartRodData(
                          toY: previousValue(index).toDouble(),
                          color: other,
                          width: width,
                          borderRadius: radius,
                        ),
                      BarChartRodData(
                        toY: _value(bucket).toDouble(),
                        color: palette.chart,
                        width: width,
                        borderRadius: radius,
                      ),
                    ],
                  ),
              ],
            ),
          );
        },
      ),
    );
    final names = legend;
    if (previous == null || names == null) return chart;
    Widget swatch(Color color, String name) => Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(3)),
        ),
        const SizedBox(width: 6),
        Text(name, style: TextStyle(fontSize: 12, color: palette.muted)),
      ],
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(spacing: 16, children: [swatch(palette.chart, names.$1), swatch(other, names.$2)]),
        const SizedBox(height: 12),
        chart,
      ],
    );
  }
}
