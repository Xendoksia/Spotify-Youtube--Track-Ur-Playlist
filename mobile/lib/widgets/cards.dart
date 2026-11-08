import 'package:flutter/material.dart';

import '../data/stats.dart';
import '../l10n/strings.dart';
import '../theme/palette.dart';
import 'format.dart';

/// A card with a title, the building block of every page
class SectionCard extends StatelessWidget {
  final String title;
  final Widget child;
  final Widget? trailing;

  const SectionCard({super.key, required this.title, required this.child, this.trailing});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(children: [
              Expanded(child: Text(title, style: Theme.of(context).textTheme.titleMedium)),
              ?trailing,
            ]),
            const SizedBox(height: 12),
            child,
          ],
        ),
      ),
    );
  }
}

/// A number with its label, e.g. 128 plays
class StatTile extends StatelessWidget {
  final String label;
  final String value;

  /// A number counting from the one shown before to [count] (formatted by [format])
  final int? count;
  final String Function(int value)? format;

  const StatTile({super.key, required this.label, required this.value}) : count = null, format = null;

  const StatTile.count({super.key, required this.label, required int this.count, required this.format}) : value = '';

  @override
  Widget build(BuildContext context) {
    final style = Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w600);
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: TextStyle(color: Palette.of(context).muted, fontSize: 13)),
            const SizedBox(height: 4),
            if (count == null)
              Text(value, style: style)
            else
              TweenAnimationBuilder<double>(
                tween: Tween(end: count!.toDouble()),
                duration: changeDuration,
                curve: changeCurve,
                builder: (context, shown, _) => Text(format!(shown.round()), style: style),
              ),
          ],
        ),
      ),
    );
  }
}

/// A numbered top list with a bar showing each row's plays against the first's
class RankedList extends StatelessWidget {
  final List<Ranked> rows;

  /// The row's move against the previous period, shown under its number
  final RankChange? Function(String key, int rank)? change;

  /// The row's cover or photo, between its number and its title
  final Widget Function(Ranked row)? image;

  /// Opens the row's page
  final void Function(Ranked row)? onTap;

  const RankedList({super.key, required this.rows, this.change, this.image, this.onTap});

  Widget? _change(BuildContext context, Palette palette, RankChange? change) {
    if (change == null) return null;
    final (text, color) = switch (change.kind) {
      ChangeKind.up => ('▲${change.count}', palette.added),
      ChangeKind.down => ('▼${change.count}', palette.removed),
      ChangeKind.same => ('=', palette.muted),
      ChangeKind.fresh => (context.t('stats.change.new'), palette.playable),
      ChangeKind.back => ('↺', palette.muted),
    };
    return Text(text, style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w600));
  }

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final most = rows.isEmpty ? 1 : rows.first.plays;
    return Column(
      children: [
        for (final (index, row) in rows.indexed)
          InkWell(
            key: ValueKey(row.key),
            onTap: onTap == null ? null : () => onTap!(row),
            borderRadius: BorderRadius.circular(8),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Row(
                children: [
                  SizedBox(
                    width: 40,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('${index + 1}', style: TextStyle(color: palette.muted, fontWeight: FontWeight.w600)),
                        ?_change(context, palette, change?.call(row.key, index + 1)),
                      ],
                    ),
                  ),
                  if (image != null) ...[image!(row), const SizedBox(width: 12)],
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(row.title, maxLines: 1, overflow: TextOverflow.ellipsis),
                        if (row.subtitle.isNotEmpty)
                          Text(row.subtitle,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(color: palette.muted, fontSize: 13)),
                        const SizedBox(height: 4),
                        ClipRRect(
                          borderRadius: BorderRadius.circular(2),
                          child: TweenAnimationBuilder<double>(
                            tween: Tween(end: row.plays / most),
                            duration: changeDuration,
                            curve: changeCurve,
                            builder: (context, share, _) => LinearProgressIndicator(
                              value: share,
                              minHeight: 4,
                              color: palette.chart,
                              backgroundColor: palette.border,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 12),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(context.plays(row.plays)),
                      // Plays stored without a length have none to show, as in the desktop app
                      if (row.minutes > 0)
                        Text(context.minutes(row.minutes), style: TextStyle(color: palette.muted, fontSize: 13)),
                    ],
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}

/// A message in the middle of a page: nothing to show yet, or an error with a way to try again
class MessageView extends StatelessWidget {
  final IconData icon;
  final String text;
  final String? action;
  final VoidCallback? onAction;

  const MessageView({super.key, required this.icon, required this.text, this.action, this.onAction});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 40, color: Palette.of(context).muted),
          const SizedBox(height: 12),
          Text(text, textAlign: TextAlign.center),
          if (action != null) ...[
            const SizedBox(height: 16),
            FilledButton(onPressed: onAction, child: Text(action!)),
          ],
        ],
      ),
    );
  }
}
