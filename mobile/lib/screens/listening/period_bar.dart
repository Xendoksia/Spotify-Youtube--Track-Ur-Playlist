import 'package:flutter/material.dart';

import '../../data/mood.dart';
import '../../data/stats.dart';
import '../../l10n/strings.dart';
import '../../widgets/format.dart';
import '../../widgets/sliding.dart';

/// Week, month, year or all time, with arrows to go back and forward by one period
class PeriodBar extends StatelessWidget {
  final Period period;
  final int offset;
  final DateRange range;
  final ValueChanged<Period> onPeriod;
  final ValueChanged<int> onOffset;

  /// Beside the period buttons (the notifications' bell)
  final Widget? trailing;

  const PeriodBar({
    super.key,
    required this.period,
    required this.offset,
    required this.range,
    required this.onPeriod,
    required this.onOffset,
    this.trailing,
  });

  String _title(BuildContext context) {
    switch (period) {
      case Period.week:
        if (offset == 0) return context.t('period.this_week');
        final last = range.end.subtract(const Duration(days: 1));
        return '${context.dateFormat('d MMM').format(range.start)} – ${context.dateFormat('d MMM').format(last)}';
      case Period.month:
        return context.dateFormat('MMMM y').format(range.start);
      case Period.year:
        return '${range.start.year}';
      case Period.all:
        return context.t('period.all_time');
    }
  }

  @override
  Widget build(BuildContext context) {
    final mood = MoodColor.of(context);
    return Column(
      children: [
        Row(
          children: [
            Expanded(
              // The selected period in the color of the number one's cover, its mark sliding to a new one
              child: SlidingSegments<Period>(
                values: Period.values,
                selected: period,
                label: (p) => context.t('period.${p.name}'),
                onChanged: onPeriod,
                color: mood,
              ),
            ),
            ?trailing,
          ],
        ),
        if (period != Period.all)
          Row(
            children: [
              IconButton(onPressed: () => onOffset(offset + 1), icon: const Icon(Icons.chevron_left)),
              Expanded(
                child: Text(_title(context),
                    textAlign: TextAlign.center, style: Theme.of(context).textTheme.titleMedium),
              ),
              IconButton(
                onPressed: offset == 0 ? null : () => onOffset(offset - 1),
                icon: const Icon(Icons.chevron_right),
              ),
            ],
          ),
      ],
    );
  }
}
