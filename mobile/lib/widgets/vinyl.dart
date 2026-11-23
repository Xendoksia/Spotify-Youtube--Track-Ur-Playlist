import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../data/stats.dart';
import '../l10n/strings.dart';
import '../theme/palette.dart';
import 'format.dart';

/// An album as a record, as the desktop app's Vinyl: its tracks in album order as slices going round clockwise, each
/// reaching out as far as it was played and an unheard one left as a thin groove, in the two colors of the cover,
/// with how many tracks were heard on the label. The slices open out one after another. A tap tells a slice's track
/// and a second tap on it opens the track
class Vinyl extends StatefulWidget {
  final List<AlbumTrack> tracks;

  /// Whether Deezer's track list is known, so the label can say how many of all the tracks were heard
  final bool complete;
  final Color color;
  final Color color2;
  final void Function(AlbumTrack track) onOpen;

  const Vinyl({
    super.key,
    required this.tracks,
    required this.complete,
    required this.color,
    required this.color2,
    required this.onOpen,
  });

  @override
  State<Vinyl> createState() => _VinylState();
}

class _VinylState extends State<Vinyl> with SingleTickerProviderStateMixin {
  late final _opening = AnimationController(vsync: this, duration: const Duration(milliseconds: 1400))..forward();
  int? _touched;

  @override
  void dispose() {
    _opening.dispose();
    super.dispose();
  }

  int _sliceAt(Offset at, Size size) {
    final dx = at.dx - size.width / 2;
    final dy = at.dy - size.height / 2;
    // Clockwise from the top, as the slices are drawn
    final angle = (math.atan2(dx, -dy) + 2 * math.pi) % (2 * math.pi);
    return (angle / (2 * math.pi) * widget.tracks.length).floor().clamp(0, widget.tracks.length - 1);
  }

  void _tap(int index) {
    final track = widget.tracks[index];
    if (index == _touched && track.played != null) {
      widget.onOpen(track);
      return;
    }
    HapticFeedback.selectionClick();
    setState(() => _touched = index);
  }

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final tracks = widget.tracks;
    if (tracks.isEmpty) return const SizedBox.shrink();
    final plays = [for (final track in tracks) track.played?.plays ?? 0];
    final most = plays.reduce(math.max);
    final best = plays.indexOf(most);
    final heard = plays.where((count) => count > 0).length;
    final shown = _touched;
    final line = shown != null
        ? '${shown + 1}. ${tracks[shown].title}  ·  '
              '${plays[shown] > 0 ? context.plays(plays[shown]) : context.t('detail.not_heard')}'
        : most > 0
        ? context.t('detail.vinyl.summary', {'number': context.number(best + 1), 'title': tracks[best].title})
        : '';
    final label = widget.complete ? '${context.number(heard)}/${context.number(tracks.length)}' : context.number(heard);
    return Column(
      children: [
        LayoutBuilder(
          builder: (context, constraints) {
            final side = math.min(constraints.maxWidth, 320.0);
            final size = Size(side, side);
            return GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTapUp: (details) => _tap(_sliceAt(details.localPosition, size)),
              child: SizedBox.fromSize(
                size: size,
                child: RepaintBoundary(
                  child: AnimatedBuilder(
                    animation: _opening,
                    builder: (context, _) => CustomPaint(
                      painter: _VinylPainter(
                        plays: plays,
                        best: best,
                        touched: shown,
                        color: widget.color,
                        color2: widget.color2,
                        disc: Theme.of(context).colorScheme.surface,
                        rim: Theme.of(context).colorScheme.surfaceContainer,
                        groove: palette.border,
                        muted: palette.muted,
                        opened: Curves.easeOutCubic.transform(_opening.value),
                      ),
                      child: Center(
                        child: FadeTransition(
                          opacity: CurvedAnimation(parent: _opening, curve: const Interval(0.8, 1)),
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(label, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
                              Text(
                                context.t('detail.vinyl.caption'),
                                style: TextStyle(color: palette.muted, fontSize: 11),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            );
          },
        ),
        const SizedBox(height: 8),
        Text(
          line,
          textAlign: TextAlign.center,
          style: TextStyle(color: palette.muted, fontSize: 13),
        ),
      ],
    );
  }
}

class _VinylPainter extends CustomPainter {
  static const gap = 0.035;

  final List<int> plays;
  final int best;
  final int? touched;
  final Color color;
  final Color color2;
  final Color disc;
  final Color rim;
  final Color groove;
  final Color muted;

  /// How far the slices have opened, 0 to 1
  final double opened;

  _VinylPainter({
    required this.plays,
    required this.best,
    required this.touched,
    required this.color,
    required this.color2,
    required this.disc,
    required this.rim,
    required this.groove,
    required this.muted,
    required this.opened,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    // The record's measures as on the desktop app, scaled to the space it has
    final scale = size.width / 320;
    final label = 46 * scale, inner = 60 * scale, outer = 132 * scale;
    final count = plays.length;
    final most = math.max(1, plays.reduce(math.max));
    final step = 2 * math.pi / count;

    canvas.drawCircle(center, outer + 4 * scale, Paint()..color = disc);
    final groovePaint = Paint()
      ..color = groove.withValues(alpha: 0.6)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;
    for (var r = inner + 8 * scale; r < outer; r += 10 * scale) {
      canvas.drawCircle(center, r, groovePaint);
    }

    final shader = RadialGradient(
      colors: [color2, color],
      stops: [inner / outer, 1],
    ).createShader(Rect.fromCircle(center: center, radius: outer));
    final numbers = TextPainter(textDirection: TextDirection.ltr);
    for (var i = 0; i < count; i++) {
      final a0 = i * step + gap, a1 = (i + 1) * step - gap;
      final reach = plays[i] > 0
          ? inner + 16 * scale + (outer - inner - 16 * scale) * math.sqrt(plays[i] / most)
          : inner + 5 * scale;
      // One after another round the record
      final own = (opened * 1.6 - i / count * 0.6).clamp(0.0, 1.0);
      final radius = inner + (reach - inner) * own;
      // Angles clockwise from the top, as Flutter measures them from the right
      final start = a0 - math.pi / 2, sweep = a1 - a0;
      final path = Path()
        ..arcTo(Rect.fromCircle(center: center, radius: radius), start, sweep, true)
        ..arcTo(Rect.fromCircle(center: center, radius: inner), start + sweep, -sweep, false)
        ..close();
      final lit = i == best || i == touched;
      canvas.drawPath(
        path,
        plays[i] > 0
            ? (Paint()
                ..shader = shader
                ..color = Colors.black.withValues(alpha: lit ? 1 : 0.8))
            : (Paint()..color = groove.withValues(alpha: 0.8)),
      );
      if (i == touched) {
        canvas.drawPath(
          path,
          Paint()
            ..color = color
            ..style = PaintingStyle.stroke
            ..strokeWidth = 1.5,
        );
      }
      // The track's number outside the record
      final middle = (a0 + a1) / 2;
      numbers.text = TextSpan(
        text: '${i + 1}',
        style: TextStyle(color: muted, fontSize: 10),
      );
      numbers.layout();
      final at = center + Offset(math.sin(middle), -math.cos(middle)) * (outer + 14 * scale);
      numbers.paint(canvas, at - Offset(numbers.width / 2, numbers.height / 2));
    }

    canvas.drawCircle(center, label + 10 * scale, Paint()..color = rim);
    canvas.drawCircle(center, label, Paint()..color = color.withValues(alpha: 0.2));
  }

  @override
  bool shouldRepaint(_VinylPainter old) =>
      old.plays != plays ||
      old.touched != touched ||
      old.color != color ||
      old.color2 != color2 ||
      old.opened != opened;
}
