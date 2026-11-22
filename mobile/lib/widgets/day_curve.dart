import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../l10n/strings.dart';
import '../theme/palette.dart';
import 'format.dart';

/// The plays of the 24 hours as one soft curve in [color], over a faint band of night, dawn, day and dusk, with the
/// most played hour marked, as the desktop app's DayCurve. A tap picks an hour and keeps it (the same one again goes
/// back to the peak) and a sideways drag runs through the hours, a light tick at each, while the page still scrolls
class DayCurve extends StatefulWidget {
  /// Plays per hour, 0-23
  final List<int> hours;
  final Color color;

  const DayCurve({super.key, required this.hours, required this.color});

  @override
  State<DayCurve> createState() => _DayCurveState();
}

class _DayCurveState extends State<DayCurve> {
  static const height = 160.0;
  int? _touched;

  int get _peak {
    var peak = 0;
    for (var hour = 1; hour < 24; hour++) {
      if (widget.hours[hour] > widget.hours[peak]) peak = hour;
    }
    return peak;
  }

  int _hourAt(Offset at, double width) => (at.dx / width * 24).floor().clamp(0, 23);

  void _pick(int? hour) {
    if (hour == _touched) return;
    HapticFeedback.selectionClick();
    setState(() => _touched = hour);
  }

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final surface = Theme.of(context).colorScheme.surfaceContainer;
    final most = widget.hours.reduce(math.max);
    final shown = _touched ?? _peak;
    final label = _touched == null
        ? context.t('detail.hours.peak', {'hour': '${_peak.toString().padLeft(2, '0')}:00'})
        : '${shown.toString().padLeft(2, '0')}:00  ·  ${context.plays(widget.hours[shown])}';
    return Column(
      children: [
        LayoutBuilder(builder: (context, constraints) {
          final width = constraints.maxWidth;
          final x = (shown + 0.5) / 24 * width;
          final y = height - widget.hours[shown] / most * (height - _DayCurvePainter.top);
          return GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTapUp: (details) {
              final hour = _hourAt(details.localPosition, width);
              _pick(hour == _touched ? null : hour);
            },
            onHorizontalDragStart: (details) => _pick(_hourAt(details.localPosition, width)),
            onHorizontalDragUpdate: (details) => _pick(_hourAt(details.localPosition, width)),
            child: SizedBox(
              height: height,
              width: width,
              child: Stack(clipBehavior: Clip.none, children: [
                Positioned.fill(
                  child: CustomPaint(
                    painter: _DayCurvePainter(hours: widget.hours, color: widget.color, shown: shown),
                  ),
                ),
                Positioned(
                  left: x - 6,
                  top: y - 6,
                  child: Container(
                    width: 12,
                    height: 12,
                    decoration: BoxDecoration(
                      color: widget.color,
                      shape: BoxShape.circle,
                      border: Border.all(color: surface, width: 2),
                      boxShadow: [if (_touched == null) BoxShadow(color: widget.color.withValues(alpha: 0.3), spreadRadius: 4)],
                    ),
                  ),
                ),
                Positioned(
                  left: 0,
                  right: 0,
                  top: math.max(0, y - 36),
                  // Over the hour, leaning inward near an edge so it stays on the card
                  child: Align(
                    alignment: Alignment(x / width * 2 - 1, 0),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: surface,
                        borderRadius: BorderRadius.circular(999),
                        boxShadow: const [BoxShadow(color: Color(0x2E000000), blurRadius: 6, offset: Offset(0, 1))],
                      ),
                      child: Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                    ),
                  ),
                ),
              ]),
            ),
          );
        }),
        const SizedBox(height: 8),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            for (final (hour, icon) in const [
              (0, Icons.dark_mode_outlined),
              (6, Icons.wb_twilight_rounded),
              (12, Icons.wb_sunny_outlined),
              (18, Icons.wb_twilight_rounded),
              (24, Icons.dark_mode_outlined),
            ])
              Row(mainAxisSize: MainAxisSize.min, children: [
                Icon(icon, size: 13, color: palette.muted),
                const SizedBox(width: 3),
                Text(hour.toString().padLeft(2, '0'), style: TextStyle(color: palette.muted, fontSize: 11)),
              ]),
          ],
        ),
      ],
    );
  }
}

class _DayCurvePainter extends CustomPainter {
  static const top = 34.0;

  final List<int> hours;
  final Color color;
  final int shown;

  _DayCurvePainter({required this.hours, required this.color, required this.shown});

  @override
  void paint(Canvas canvas, Size size) {
    final most = hours.reduce(math.max);
    double x(int hour) => (hour + 0.5) / 24 * size.width;
    double y(int hour) => size.height - hours[(hour + 24) % 24] / most * (size.height - top);
    final whole = Offset.zero & size;

    // Night, dawn, noon, dusk and night again, faintly
    canvas.drawRRect(
      RRect.fromRectAndRadius(whole, const Radius.circular(10)),
      Paint()
        ..shader = const LinearGradient(colors: [
          Color(0x295B6EE1),
          Color(0x1AF2A65A),
          Color(0x1FF5D76E),
          Color(0x1AE0707A),
          Color(0x295B6EE1),
        ]).createShader(whole),
    );

    // The day goes round: the hours before midnight lead into the first ones, so the curve does not drop at the ends
    final points = [for (var hour = -2; hour <= 25; hour++) Offset(x(hour), y(hour))];
    double keep(double value) => value.clamp(top / 2, size.height);
    final line = Path()..moveTo(points[1].dx, points[1].dy);
    for (var i = 1; i < points.length - 2; i++) {
      final (p0, p1, p2, p3) = (points[i - 1], points[i], points[i + 1], points[i + 2]);
      line.cubicTo(p1.dx + (p2.dx - p0.dx) / 6, keep(p1.dy + (p2.dy - p0.dy) / 6), p2.dx - (p3.dx - p1.dx) / 6,
          keep(p2.dy - (p3.dy - p1.dy) / 6), p2.dx, p2.dy);
    }
    final area = Path.from(line)
      ..lineTo(x(24), size.height)
      ..lineTo(x(-1), size.height)
      ..close();
    canvas.save();
    canvas.clipRRect(RRect.fromRectAndRadius(whole, const Radius.circular(10)));
    canvas.drawPath(
      area,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [color.withValues(alpha: 0.5), color.withValues(alpha: 0.02)],
        ).createShader(whole),
    );
    canvas.drawPath(
      line,
      Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.5
        ..strokeJoin = StrokeJoin.round,
    );
    // A dashed guide from the marked hour down to the baseline
    final guide = Paint()
      ..color = color.withValues(alpha: 0.7)
      ..strokeWidth = 1;
    for (var dy = y(shown); dy < size.height; dy += 7) {
      canvas.drawLine(Offset(x(shown), dy), Offset(x(shown), math.min(dy + 3, size.height)), guide);
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(_DayCurvePainter old) => old.hours != hours || old.color != color || old.shown != shown;
}
