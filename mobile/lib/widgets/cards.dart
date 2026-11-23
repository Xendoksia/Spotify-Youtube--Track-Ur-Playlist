import 'package:flutter/material.dart';

import '../data/mood.dart';
import '../data/stats.dart';
import '../l10n/strings.dart';
import '../theme/palette.dart';
import 'format.dart';
import 'sparkline.dart';

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
            Row(
              children: [
                Expanded(child: Text(title, style: Theme.of(context).textTheme.titleMedium)),
                ?trailing,
              ],
            ),
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

  /// The change against the previous period, under the number
  final String? note;

  /// The value per day (or month) of the period, drawn as a line under it
  final List<TrendPoint>? trend;

  const StatTile({super.key, required this.label, required this.value, this.note})
    : count = null,
      format = null,
      trend = null;

  const StatTile.count({
    super.key,
    required this.label,
    required int this.count,
    required this.format,
    this.note,
    this.trend,
  }) : value = '';

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
            if (note != null) ...[
              const SizedBox(height: 2),
              Text(note!, style: TextStyle(color: Palette.of(context).muted, fontSize: 12)),
            ],
            if (trend != null) Sparkline(points: trend!),
          ],
        ),
      ),
    );
  }
}

/// A share as a rounded bar that grows to it, in one color or running from [colors].$1 into [colors].$2
class ShareBar extends StatelessWidget {
  final double share;
  final double height;
  final Color color;
  final (Color, Color)? colors;
  final Color background;

  const ShareBar({
    super.key,
    required this.share,
    required this.color,
    required this.background,
    this.colors,
    this.height = 4,
  });

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(height / 2),
      child: TweenAnimationBuilder<double>(
        tween: Tween(end: share),
        duration: changeDuration,
        curve: changeCurve,
        builder: (context, share, _) => Container(
          height: height,
          color: background,
          alignment: Alignment.centerLeft,
          child: FractionallySizedBox(
            widthFactor: share.clamp(0.0, 1.0),
            heightFactor: 1,
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: colors == null ? color : null,
                gradient: colors == null ? null : LinearGradient(colors: [colors!.$2, colors!.$1]),
                borderRadius: BorderRadius.circular(height / 2),
              ),
            ),
          ),
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

  /// The first row's number: 2 under a card showing the number one
  final int firstRank;

  /// The bars' two colors on a page with a picture (its first and second), else the charts' green
  final (Color, Color)? colors;

  const RankedList({
    super.key,
    required this.rows,
    this.change,
    this.image,
    this.onTap,
    this.firstRank = 1,
    this.colors,
  });

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
                        Text(
                          '${index + firstRank}',
                          style: TextStyle(color: palette.muted, fontWeight: FontWeight.w600),
                        ),
                        if (change?.call(row.key, index + firstRank) case final moved?)
                          Padding(
                            padding: const EdgeInsets.only(top: 2),
                            child: ChangePill(change: moved),
                          ),
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
                          Text(
                            row.subtitle,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(color: palette.muted, fontSize: 13),
                          ),
                        const SizedBox(height: 4),
                        ShareBar(
                          share: row.plays / most,
                          color: palette.chart,
                          colors: colors,
                          background: palette.border,
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
          if (action != null) ...[const SizedBox(height: 16), FilledButton(onPressed: onAction, child: Text(action!))],
        ],
      ),
    );
  }
}

/// A rank change as a small pill tinted in its color, with a chevron or a return arrow and the count, as the
/// desktop app's Change
class ChangePill extends StatelessWidget {
  final RankChange change;

  const ChangePill({super.key, required this.change});

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final color = switch (change.kind) {
      ChangeKind.up => palette.added,
      ChangeKind.down => palette.removed,
      ChangeKind.fresh => palette.playable,
      ChangeKind.same || ChangeKind.back => palette.muted,
    };
    final icon = switch (change.kind) {
      ChangeKind.up => Icons.keyboard_arrow_up_rounded,
      ChangeKind.down => Icons.keyboard_arrow_down_rounded,
      ChangeKind.back => Icons.replay_rounded,
      _ => null,
    };
    final label = switch (change.kind) {
      ChangeKind.up || ChangeKind.down => '${change.count}',
      ChangeKind.same => '–',
      ChangeKind.fresh => context.t('stats.change.new'),
      ChangeKind.back => '',
    };
    return Container(
      height: 18,
      constraints: const BoxConstraints(minWidth: 24),
      padding: EdgeInsets.symmetric(horizontal: icon == null ? 6 : 5),
      decoration: BoxDecoration(color: color.withValues(alpha: 0.16), borderRadius: BorderRadius.circular(9)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          if (icon != null) Icon(icon, size: 13, color: color),
          if (label.isNotEmpty)
            Text(
              label,
              style: TextStyle(
                color: color,
                fontSize: 11,
                fontWeight: FontWeight.w700,
                height: 1,
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
        ],
      ),
    );
  }
}

/// What a number one's rank change means, beside its pill ("#3 in the previous period")
String changeNote(BuildContext context, RankChange change, int rank) => switch (change.kind) {
  ChangeKind.same => context.t('stats.change.same'),
  ChangeKind.fresh => context.t('stats.change.new_long'),
  ChangeKind.back => context.t('stats.change.back_long'),
  ChangeKind.up || ChangeKind.down => context.t('stats.change.was', {
    'rank': rank + (change.kind == ChangeKind.up ? change.count : -change.count),
  }),
};

/// The number one track or artist of the period, large with its picture, as the desktop app's hero cards
class HeroCard extends StatelessWidget {
  final String caption;
  final String title;
  final String subtitle;
  final String detail;

  /// The move against the previous period, shown as a pill with what it means
  final RankChange? change;
  final Widget image;
  final VoidCallback onTap;

  const HeroCard({
    super.key,
    required this.caption,
    required this.title,
    required this.subtitle,
    required this.detail,
    this.change,
    required this.image,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final theme = Theme.of(context);
    final mood = MoodColor.of(context);
    return Card(
      clipBehavior: Clip.antiAlias,
      // The edge takes the color of the number one's cover
      shape: mood == null
          ? null
          : RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: BorderSide(color: Color.lerp(palette.border, mood, 0.45)!),
            ),
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            children: [
              image,
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      caption.toUpperCase(),
                      style: TextStyle(
                        color: palette.muted,
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        letterSpacing: 0.8,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700),
                    ),
                    if (subtitle.isNotEmpty)
                      Text(
                        subtitle,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(color: palette.muted),
                      ),
                    const SizedBox(height: 4),
                    Text(detail, style: const TextStyle(fontSize: 13)),
                    if (change case final moved?)
                      Padding(
                        padding: const EdgeInsets.only(top: 6),
                        child: Row(
                          children: [
                            ChangePill(change: moved),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                changeNote(context, moved, 1),
                                maxLines: 2,
                                style: TextStyle(color: palette.muted, fontSize: 12, fontWeight: FontWeight.w600),
                              ),
                            ),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
