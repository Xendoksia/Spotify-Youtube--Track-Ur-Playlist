/// Rows of choices whose selection mark slides to a newly chosen one instead of jumping there, as the desktop
/// app's Marker. Only the mark's transform moves.
library;

import 'package:flutter/material.dart';

import '../theme/palette.dart';

const _slide = Duration(milliseconds: 320);
const _slideCurve = Curves.easeOutCubic;

/// Equal segments in a rounded frame, with a filled thumb under the chosen one
class SlidingSegments<T> extends StatelessWidget {
  final List<T> values;
  final T selected;
  final String Function(T value) label;
  final ValueChanged<T> onChanged;

  /// The thumb's color; the theme's accent by default
  final Color? color;

  const SlidingSegments({
    super.key,
    required this.values,
    required this.selected,
    required this.label,
    required this.onChanged,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final theme = Theme.of(context);
    final thumb = color ?? theme.colorScheme.primary;
    final index = values.indexOf(selected);
    return Container(
      height: 40,
      padding: const EdgeInsets.all(3),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainer,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: palette.border),
      ),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final width = constraints.maxWidth / values.length;
          return Stack(
            children: [
              TweenAnimationBuilder<double>(
                tween: Tween(end: index.toDouble()),
                duration: _slide,
                curve: _slideCurve,
                builder: (context, at, child) => Transform.translate(offset: Offset(at * width, 0), child: child),
                child: Container(
                  width: width,
                  decoration: BoxDecoration(color: thumb, borderRadius: BorderRadius.circular(17)),
                ),
              ),
              Row(
                children: [
                  for (final (i, value) in values.indexed)
                    Expanded(
                      child: InkWell(
                        borderRadius: BorderRadius.circular(17),
                        onTap: i == index ? null : () => onChanged(value),
                        child: Center(
                          child: AnimatedDefaultTextStyle(
                            duration: _slide,
                            style: theme.textTheme.labelLarge!.copyWith(
                              color: i == index ? Colors.white : theme.colorScheme.onSurface,
                              fontWeight: i == index ? FontWeight.w700 : FontWeight.w500,
                            ),
                            child: Text(label(value), maxLines: 1, overflow: TextOverflow.fade, softWrap: false),
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ],
          );
        },
      ),
    );
  }
}

class BarItem {
  final IconData icon;
  final IconData selectedIcon;
  final String label;

  const BarItem(this.icon, this.selectedIcon, this.label);
}

/// The bottom bar, its highlight sliding under the chosen page's icon
class SlidingNavigationBar extends StatelessWidget {
  final List<BarItem> items;
  final int selected;
  final ValueChanged<int> onSelected;

  const SlidingNavigationBar({super.key, required this.items, required this.selected, required this.onSelected});

  static const _pill = Size(64, 32);

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final palette = Palette.of(context);
    final accent = theme.colorScheme.primary;
    return Material(
      color: theme.colorScheme.surfaceContainer,
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 68,
          child: LayoutBuilder(
            builder: (context, constraints) {
              final width = constraints.maxWidth / items.length;
              return Stack(
                children: [
                  TweenAnimationBuilder<double>(
                    tween: Tween(end: selected.toDouble()),
                    duration: _slide,
                    curve: _slideCurve,
                    builder: (context, at, child) =>
                        Transform.translate(offset: Offset(at * width + (width - _pill.width) / 2, 10), child: child),
                    child: Container(
                      width: _pill.width,
                      height: _pill.height,
                      decoration: BoxDecoration(
                        color: accent.withValues(alpha: 0.18),
                        borderRadius: BorderRadius.circular(16),
                      ),
                    ),
                  ),
                  Row(
                    children: [
                      for (final (i, item) in items.indexed)
                        Expanded(
                          child: InkResponse(
                            onTap: () => onSelected(i),
                            highlightShape: BoxShape.rectangle,
                            containedInkWell: true,
                            child: Column(
                              children: [
                                const SizedBox(height: 14),
                                Icon(
                                  i == selected ? item.selectedIcon : item.icon,
                                  color: i == selected ? accent : palette.muted,
                                  size: 24,
                                ),
                                const SizedBox(height: 10),
                                Text(
                                  item.label,
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: i == selected ? theme.colorScheme.onSurface : palette.muted,
                                    fontWeight: i == selected ? FontWeight.w700 : FontWeight.w500,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                    ],
                  ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }
}
