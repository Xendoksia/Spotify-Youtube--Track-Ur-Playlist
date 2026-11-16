/// Grey shapes in the layout of a page that is still being loaded, with a light sweeping over them, so the page
/// does not stand empty and then jump into place, as the desktop app's Skeleton.
library;

import 'package:flutter/material.dart';

import '../theme/palette.dart';

/// Runs the one sweep all the bones under it share
class Skeleton extends StatefulWidget {
  final Widget child;

  const Skeleton({super.key, required this.child});

  @override
  State<Skeleton> createState() => _SkeletonState();
}

class _SkeletonState extends State<Skeleton> with SingleTickerProviderStateMixin {
  late final _sweep = AnimationController(vsync: this, duration: const Duration(milliseconds: 1400))..repeat();

  @override
  void dispose() {
    _sweep.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => _Sweep(animation: _sweep, child: widget.child);
}

class _Sweep extends InheritedWidget {
  final Animation<double> animation;

  const _Sweep({required this.animation, required super.child});

  @override
  bool updateShouldNotify(_Sweep old) => old.animation != animation;
}

/// A grey bar or block; [widthFactor] is its share of the line
class Bone extends StatelessWidget {
  final double? width;
  final double? widthFactor;
  final double height;
  final bool round;

  const Bone({super.key, this.width, this.widthFactor, this.height = 12, this.round = false});

  @override
  Widget build(BuildContext context) {
    final sweep = context.dependOnInheritedWidgetOfExactType<_Sweep>()?.animation;
    final color = Palette.of(context).border.withValues(alpha: 0.7);
    final highlight = Theme.of(context).brightness == Brightness.dark
        ? Colors.white.withValues(alpha: 0.07)
        : Colors.white.withValues(alpha: 0.45);
    Widget bone = ClipRRect(
      borderRadius: BorderRadius.circular(round ? height : 6),
      child: SizedBox(
        width: width,
        height: height,
        child: Stack(
          fit: StackFit.expand,
          children: [
            ColoredBox(color: color),
            if (sweep != null)
              // Only the light's transform moves
              AnimatedBuilder(
                animation: sweep,
                builder: (context, child) =>
                    FractionalTranslation(translation: Offset(-1 + 2 * sweep.value, 0), child: child),
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [highlight.withValues(alpha: 0), highlight, highlight.withValues(alpha: 0)],
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
    if (widthFactor != null) {
      bone = FractionallySizedBox(widthFactor: widthFactor, alignment: Alignment.centerLeft, child: bone);
    }
    return bone;
  }
}

/// A card with a title and a few rows of a picture and two lines of different lengths
class CardSkeleton extends StatelessWidget {
  final int lines;

  const CardSkeleton({super.key, this.lines = 5});

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Bone(widthFactor: 0.38, height: 14),
          for (var i = 0; i < lines; i++) ...[
            const SizedBox(height: 14),
            Row(
              children: [
                const Bone(width: 40, height: 40),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Bone(widthFactor: (78 - (i * 17) % 40) / 100),
                      const SizedBox(height: 8),
                      Bone(widthFactor: (46 - (i * 11) % 24) / 100, height: 10),
                    ],
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    ),
  );
}

class _TileSkeleton extends StatelessWidget {
  const _TileSkeleton();

  @override
  Widget build(BuildContext context) => const Card(
    child: Padding(
      padding: EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Bone(widthFactor: 0.5, height: 10),
          SizedBox(height: 10),
          Bone(widthFactor: 0.45, height: 24),
          SizedBox(height: 12),
          Bone(height: 30),
        ],
      ),
    ),
  );
}

class _HeroSkeleton extends StatelessWidget {
  final bool round;

  const _HeroSkeleton({this.round = false});

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Row(
        children: [
          Bone(width: 88, height: 88, round: round),
          const SizedBox(width: 14),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Bone(widthFactor: 0.3, height: 10),
                SizedBox(height: 10),
                Bone(widthFactor: 0.7, height: 20),
                SizedBox(height: 10),
                Bone(widthFactor: 0.45),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}

/// The statistics before the plays came: the period bar, the tiles, the two number ones and a top list
class ListeningSkeleton extends StatelessWidget {
  const ListeningSkeleton({super.key});

  @override
  Widget build(BuildContext context) => const Skeleton(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Bone(height: 40, round: true),
        SizedBox(height: 18),
        Center(child: Bone(width: 140, height: 18)),
        SizedBox(height: 18),
        Row(
          children: [
            Expanded(child: _TileSkeleton()),
            SizedBox(width: 8),
            Expanded(child: _TileSkeleton()),
          ],
        ),
        SizedBox(height: 8),
        Row(
          children: [
            Expanded(child: _TileSkeleton()),
            SizedBox(width: 8),
            Expanded(child: _TileSkeleton()),
          ],
        ),
        SizedBox(height: 12),
        _HeroSkeleton(),
        SizedBox(height: 8),
        _HeroSkeleton(round: true),
        SizedBox(height: 12),
        CardSkeleton(),
      ],
    ),
  );
}

/// The playlists before they came: a service's name and a few cards
class PlaylistsSkeleton extends StatelessWidget {
  const PlaylistsSkeleton({super.key});

  @override
  Widget build(BuildContext context) => Skeleton(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Padding(padding: EdgeInsets.symmetric(vertical: 12), child: Bone(widthFactor: 0.25, height: 16)),
        for (var i = 0; i < 4; i++)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Row(
                  children: [
                    const Bone(width: 72, height: 72),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Bone(widthFactor: (70 - i * 13 % 30) / 100, height: 14),
                          const SizedBox(height: 8),
                          const Bone(widthFactor: 0.55, height: 10),
                          const SizedBox(height: 12),
                          const Bone(width: 80, height: 18, round: true),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
      ],
    ),
  );
}
