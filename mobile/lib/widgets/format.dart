import 'package:flutter/widgets.dart';
import 'package:intl/intl.dart';

import '../l10n/strings.dart';
import '../state/app_controller.dart';

extension Formats on BuildContext {
  String get _locale => AppScope.of(this).language;

  /// 75 → "1 h 15 min"
  String minutes(int minutes) => minutes < 60
      ? t('minutes', {'minutes': minutes})
      : t('hours', {'hours': minutes ~/ 60, 'minutes': minutes % 60});

  String number(int value) => NumberFormat.decimalPattern(_locale).format(value);

  /// "1 play", "3 plays"
  String plays(int count) => t(count == 1 ? 'stats.plays_one' : 'stats.plays_count', {'count': number(count)});

  /// Today, yesterday, or the date with its weekday
  String day(DateTime day) {
    final today = DateTime.now();
    final difference = DateTime(today.year, today.month, today.day).difference(day).inDays;
    if (difference == 0) return t('day.today');
    if (difference == 1) return t('day.yesterday');
    return DateFormat.MMMMEEEEd(_locale).format(day);
  }

  String time(DateTime moment) => DateFormat.Hm(_locale).format(moment);

  String dateTime(DateTime moment) => DateFormat.yMMMd(_locale).add_Hm().format(moment);

  String date(DateTime moment) => DateFormat.yMMMd(_locale).format(moment);

  /// A track's length: 214000 ms → "3:34"
  String length(int ms) {
    final seconds = ms ~/ 1000;
    return '${seconds ~/ 60}:${(seconds % 60).toString().padLeft(2, '0')}';
  }

  DateFormat dateFormat(String pattern) => DateFormat(pattern, _locale);
}
