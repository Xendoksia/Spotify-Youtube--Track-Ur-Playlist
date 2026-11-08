import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../../data/stats.dart';
import '../../theme/palette.dart';
import '../../widgets/format.dart';

/// Minutes listened per day, month or year of the period; touching a bar shows its minutes
class ListeningChart extends StatelessWidget {
  final Period period;
  final List<Bucket> buckets;

  /// Plays instead of minutes, as on the detail pages
  final bool plays;

  /// Another name for a bar's day or month than the period's
  final String Function(BuildContext context, DateTime start)? label;

  const ListeningChart({super.key, required this.period, required this.buckets, this.plays = false, this.label});

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

  String _valueText(BuildContext context, int value) =>
      plays ? context.plays(value) : context.minutes(value);

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

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final most = buckets.fold<int>(0, (m, b) => _value(b) > m ? _value(b) : m);
    final width = buckets.length > 12 ? 6.0 : 16.0;
    final step = _step(most);
    return SizedBox(
      height: 180,
      child: BarChart(
        duration: changeDuration,
        curve: changeCurve,
        BarChartData(
          maxY: most == 0 ? step : (most / step).ceil() * step,
          borderData: FlBorderData(show: false),
          gridData: FlGridData(
            drawVerticalLine: false,
            horizontalInterval: step,
            getDrawingHorizontalLine: (_) => FlLine(color: palette.border, strokeWidth: 1),
          ),
          titlesData: FlTitlesData(
            topTitles: const AxisTitles(),
            rightTitles: const AxisTitles(),
            leftTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 40,
                interval: step,
                getTitlesWidget: (value, meta) => SideTitleWidget(
                  meta: meta,
                  child: Text(context.number(value.round()), style: TextStyle(fontSize: 11, color: palette.muted)),
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
                    child: Text(_label(context, buckets[index].start),
                        style: TextStyle(fontSize: 11, color: palette.muted)),
                  );
                },
              ),
            ),
          ),
          barTouchData: BarTouchData(
            touchTooltipData: BarTouchTooltipData(
              getTooltipItem: (group, _, rod, _) => BarTooltipItem(
                '${_label(context, buckets[group.x].start)}\n${_valueText(context, rod.toY.round())}',
                const TextStyle(color: Colors.white, fontSize: 12),
              ),
            ),
          ),
          barGroups: [
            for (final (index, bucket) in buckets.indexed)
              BarChartGroupData(x: index, barRods: [
                BarChartRodData(
                  toY: _value(bucket).toDouble(),
                  color: palette.chart,
                  width: width,
                  borderRadius: const BorderRadius.vertical(top: Radius.circular(3)),
                ),
              ]),
          ],
        ),
      ),
    );
  }
}
