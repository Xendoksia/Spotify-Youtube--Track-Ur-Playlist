import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../../data/stats.dart';
import '../../theme/palette.dart';
import '../../widgets/format.dart';

/// Minutes listened per day, month or year of the period; touching a bar shows its minutes
class ListeningChart extends StatelessWidget {
  final Period period;
  final List<Bucket> buckets;

  const ListeningChart({super.key, required this.period, required this.buckets});

  String _label(BuildContext context, DateTime start) => switch (period) {
        Period.week => context.dateFormat('E').format(start),
        Period.month => '${start.day}',
        Period.year => context.dateFormat('MMMMM').format(start),
        Period.all => '${start.year}',
      };

  /// A month has too many days to label each bar
  bool _labelled(int index) => period != Period.month || index % 5 == 0;

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
    final most = buckets.fold<int>(0, (m, b) => b.minutes > m ? b.minutes : m);
    final width = buckets.length > 12 ? 6.0 : 16.0;
    final step = _step(most);
    return SizedBox(
      height: 180,
      child: BarChart(
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
                '${_label(context, buckets[group.x].start)}\n${context.minutes(rod.toY.round())}',
                const TextStyle(color: Colors.white, fontSize: 12),
              ),
            ),
          ),
          barGroups: [
            for (final (index, bucket) in buckets.indexed)
              BarChartGroupData(x: index, barRods: [
                BarChartRodData(
                  toY: bucket.minutes.toDouble(),
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
