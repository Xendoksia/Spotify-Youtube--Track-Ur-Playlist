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

  test('the card has a word only on a step or the day a record is first beaten', () {
    // 1 to 3, a gap, then 5 to 7 is a step but not a record (the same length as before)
    final step = streakOf(on([1, 2, 3, 19, 20, 21]), now);
    expect((step.longest, step.before, step.milestone, step.record, step.special), (3, 3, true, false, true));
    // 1 to 3, a gap, then 18 to 21: four days beat three for the first time today
    final record = streakOf(on([1, 2, 3, 18, 19, 20, 21]), now);
    expect((record.record, record.milestone), (true, false));
    // A day later the record goes on but says nothing more
    final next = streakOf(on([1, 2, 3, 17, 18, 19, 20, 21]), now);
    expect((next.record, next.special), (false, false));
    // Without a play today there is nothing to celebrate yet
    expect(streakOf(on([18, 19, 20]), now).special, false);
  });
}
