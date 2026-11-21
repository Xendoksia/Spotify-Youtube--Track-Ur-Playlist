import 'package:flutter_test/flutter_test.dart';
import 'package:playlist_tracker/data/models.dart';
import 'package:playlist_tracker/data/stats.dart';

import 'stats_test.dart' show play;

void main() {
  final now = DateTime(2026, 11, 21, 18);
  List<Play> on(List<int> days) => [for (final day in days) play('A', 'Song $day', DateTime(2026, 11, day, 12))];

  test('a streak runs back from today, or from yesterday while today has no play yet', () {
    final today = streakOf(on([18, 19, 20, 21]), now);
    expect((today.current, today.today, today.start), (4, true, DateTime(2026, 11, 18)));
    final yesterday = streakOf(on([18, 19, 20]), now);
    expect((yesterday.current, yesterday.today), (3, false));
    expect(streakOf(on([10, 11]), now).current, 0);
    expect(streakOf(on([20, 21]), now).recent, [...List.filled(12, false), true, true]);
  });

  test('the card marks only the day of a new title or the day a record is first beaten', () {
    // 1 to 3, a gap, then 19 to 21 earns the first title but is no record (the same length as before)
    final step = streakOf(on([1, 2, 3, 19, 20, 21]), now);
    expect((step.longest, step.before, step.levelUp, step.record, step.special), (3, 3, true, false, true));
    // 1 to 3, a gap, then 18 to 21: four days beat three for the first time today
    final record = streakOf(on([1, 2, 3, 18, 19, 20, 21]), now);
    expect((record.record, record.levelUp), (true, false));
    // A day later the record goes on but says nothing more
    final next = streakOf(on([1, 2, 3, 17, 18, 19, 20, 21]), now);
    expect((next.record, next.special), (false, false));
    // Without a play today there is nothing to celebrate yet
    expect(streakOf(on([18, 19, 20]), now).special, false);
  });

  test('titles come at 3, 7, 14, 30 and 100 days', () {
    expect([for (final days in [0, 2, 3, 6, 7, 18, 30, 99, 100, 400]) streakLevel(days)], [0, 0, 1, 1, 2, 3, 4, 4, 5, 5]);
    expect([for (final days in [0, 3, 18, 99, 100]) streakNextLevel(days)], [3, 7, 30, 100, null]);
  });
}
