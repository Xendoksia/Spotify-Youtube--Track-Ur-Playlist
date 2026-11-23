import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../data/mood.dart';
import '../l10n/strings.dart';
import '../theme/palette.dart';
import 'format.dart';

const _inner = 0.35;
const _outer = 0.83;

/// The space left between two hours' slices, in radians
const _gap = 0.025;

/// The plays of the 24 hours as slices round a clock face, midnight at the top and noon at the bottom, each reaching
/// out as far as its count, in the page's color, as the desktop app's HourClock. The middle names the busiest hour,
/// or the hour a finger is on.
class HourClock extends StatefulWidget {
  final List<int> hours;

  const HourClock({super.key, required this.hours});

  @override
  State<HourClock> createState() => _HourClockState();
}

class _HourClockState extends State<HourClock> with SingleTickerProviderStateMixin {
  late final _opened = AnimationController(vsync: this, duration: const Duration(milliseconds: 600))..forward();
  int? _touched;

  @override
  void didUpdateWidget(HourClock old) {
    super.didUpdateWidget(old);
    if (!_same(old.hours, widget.hours)) {
      _opened.forward(from: 0);
      _touched = null;
    }
  }

  static bool _same(List<int> a, List<int> b) => a.length == b.length && a.indexed.every((e) => e.$2 == b[e.$1]);

  @override
  void dispose() {
    _opened.dispose();
    super.dispose();
  }

  /// The hour under the finger, or null in the middle and outside the face
  int? _hourAt(Offset at, double size) {
    final offset = at - Offset(size / 2, size / 2);
    final distance = offset.distance / (size / 2);
    if (distance < _inner || distance > 1) return null;
    final angle = (math.atan2(offset.dx, -offset.dy) + 2 * math.pi) % (2 * math.pi);
    return (angle / (2 * math.pi) * 24).floor() % 24;
  }

  @override
  Widget build(BuildContext context) {
    final hours = widget.hours;
    final palette = Palette.of(context);
    final most = hours.fold(0, math.max);
    if (most == 0) {
      return SizedBox(
        height: 120,
        child: Center(child: Text(context.t('stats.empty'), style: TextStyle(color: palette.muted))),
      );
    }
    final peak = hours.indexOf(most);
    final shown = _touched ?? peak;
    final color = MoodColor.of(context) ?? palette.chart;
    final text = Theme.of(context).colorScheme.onSurface;
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 260),
        child: AspectRatio(
          aspectRatio: 1,
          child: LayoutBuilder(
            builder: (context, constraints) {
              final size = constraints.maxWidth;
              void touch(Offset at) {
                final hour = _hourAt(at, size);
                if (hour != null && hour != _touched) setState(() => _touched = hour);
              }

              return GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTapDown: (d) => touch(d.localPosition),
                onPanStart: (d) => touch(d.localPosition),
                onPanUpdate: (d) => touch(d.localPosition),
                // A tap in the middle goes back to the busiest hour
                onTapUp: (d) {
                  if (_hourAt(d.localPosition, size) == null) setState(() => _touched = null);
                },
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    Positioned.fill(
                      child: RepaintBoundary(
                        child: CustomPaint(
                          painter: _ClockPainter(
                            hours: hours,
                            most: most,
                            shown: shown,
                            color: color,
                            grid: palette.border,
                            opened: _opened,
                          ),
                        ),
                      ),
                    ),
                    for (final hour in [0, 6, 12, 18])
                      Align(
                        alignment: Alignment(
                          math.sin(hour / 24 * 2 * math.pi) * 0.94,
                          -math.cos(hour / 24 * 2 * math.pi) * 0.94,
                        ),
                        child: Text(
                          hour.toString().padLeft(2, '0'),
                          style: TextStyle(fontSize: 11, color: palette.muted),
                        ),
                      ),
                    Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          '${shown.toString().padLeft(2, '0')}:00',
                          style: TextStyle(
                            fontSize: 22,
                            fontWeight: FontWeight.w600,
                            color: text,
                            fontFeatures: const [FontFeature.tabularFigures()],
                          ),
                        ),
                        Text(
                          _touched == null ? context.t('stats.clock.peak') : context.plays(hours[shown]),
                          style: TextStyle(fontSize: 11, color: palette.muted),
                        ),
                      ],
                    ),
                  ],
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}

class _ClockPainter extends CustomPainter {
  final List<int> hours;
  final int most;
  final int shown;
  final Color color;
  final Color grid;
  final Animation<double> opened;

  _ClockPainter({
    required this.hours,
    required this.most,
    required this.shown,
    required this.color,
    required this.grid,
    required this.opened,
  }) : super(repaint: opened);

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = size.width / 2;
    final inner = radius * _inner;
    final outer = radius * _outer;
    final ring = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1
      ..color = grid;
    canvas.drawCircle(center, outer, ring);
    final t = Curves.easeOutCubic.transform(opened.value);
    final step = 2 * math.pi / hours.length;
    canvas.save();
    // Opens out from a little smaller and turned back, as on the desktop app
    canvas.translate(center.dx, center.dy);
    canvas.rotate((t - 1) * 0.35);
    canvas.scale(0.85 + 0.15 * t);
    canvas.translate(-center.dx, -center.dy);
    for (final (hour, count) in hours.indexed) {
      final reach = count == 0 ? inner + 1.5 : inner + 3 + (outer - inner - 3) * count / most;
      // Angles from the top, clockwise, as Flutter's arcs start at three o'clock
      final a0 = hour * step + _gap - math.pi / 2;
      final sweep = step - 2 * _gap;
      final path = Path()
        ..arcTo(Rect.fromCircle(center: center, radius: reach), a0, sweep, true)
        ..arcTo(Rect.fromCircle(center: center, radius: inner), a0 + sweep, -sweep, false)
        ..close();
      final opacity = hour == shown ? 1.0 : 0.35 + 0.5 * count / most;
      canvas.drawPath(path, Paint()..color = color.withValues(alpha: opacity * t));
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(_ClockPainter old) =>
      old.shown != shown || old.color != color || old.most != most || old.hours != hours || old.grid != grid;
}
