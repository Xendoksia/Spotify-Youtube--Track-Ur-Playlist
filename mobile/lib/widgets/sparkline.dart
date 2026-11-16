import 'package:flutter/material.dart';

import '../data/mood.dart';
import '../theme/palette.dart';

class TrendPoint {
  final int value;

  /// The day (or month) and its value, shown while the finger is on the point
  final String label;

  const TrendPoint(this.value, this.label);
}

const _height = 34.0;

/// Room above the highest point and below the lowest, so the line and the dot are not cut off
const _pad = 3.0;

/// A tile's value over the days (or months) of the period as a thin line over a soft area, as the desktop app's
/// Sparkline; it draws itself in when the values change, and holding a finger on it shows each point's value.
/// Nothing is drawn for fewer than two points.
class Sparkline extends StatefulWidget {
  final List<TrendPoint> points;

  const Sparkline({super.key, required this.points});

  @override
  State<Sparkline> createState() => _SparklineState();
}

class _SparklineState extends State<Sparkline> with SingleTickerProviderStateMixin {
  late final _drawn = AnimationController(vsync: this, duration: const Duration(milliseconds: 700))..forward();
  int? _touched;

  @override
  void didUpdateWidget(Sparkline old) {
    super.didUpdateWidget(old);
    final values = widget.points.map((p) => p.value).toList();
    final before = old.points.map((p) => p.value).toList();
    if (values.length != before.length || !values.indexed.every((e) => e.$2 == before[e.$1])) {
      _drawn.forward(from: 0);
      _touched = null;
    }
  }

  @override
  void dispose() {
    _drawn.dispose();
    super.dispose();
  }

  void _touch(Offset at, double width) {
    final count = widget.points.length;
    final index = (at.dx / width * (count - 1)).round().clamp(0, count - 1);
    if (index != _touched) setState(() => _touched = index);
  }

  @override
  Widget build(BuildContext context) {
    final points = widget.points;
    if (points.length < 2) return const SizedBox.shrink();
    final color = MoodColor.of(context) ?? Palette.of(context).chart;
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth;
        final touched = _touched;
        return GestureDetector(
          behavior: HitTestBehavior.opaque,
          onHorizontalDragStart: (d) => _touch(d.localPosition, width),
          onHorizontalDragUpdate: (d) => _touch(d.localPosition, width),
          onHorizontalDragEnd: (_) => setState(() => _touched = null),
          onTapDown: (d) => _touch(d.localPosition, width),
          onTapUp: (_) => setState(() => _touched = null),
          onTapCancel: () => setState(() => _touched = null),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              SizedBox(
                height: 16,
                child: touched == null
                    ? null
                    : Align(
                        alignment: Alignment(touched / (points.length - 1) * 2 - 1, 0),
                        child: Text(
                          points[touched].label,
                          maxLines: 1,
                          style: TextStyle(fontSize: 11, color: color, fontWeight: FontWeight.w600),
                        ),
                      ),
              ),
              SizedBox(
                height: _height,
                child: RepaintBoundary(
                  child: CustomPaint(
                    painter: _SparklinePainter(
                      values: [for (final p in points) p.value],
                      color: color,
                      drawn: _drawn,
                      touched: touched,
                    ),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _SparklinePainter extends CustomPainter {
  final List<int> values;
  final Color color;
  final Animation<double> drawn;
  final int? touched;

  _SparklinePainter({required this.values, required this.color, required this.drawn, this.touched})
    : super(repaint: drawn);

  @override
  void paint(Canvas canvas, Size size) {
    final most = values.fold(1, (a, b) => a > b ? a : b);
    double x(int i) => i * size.width / (values.length - 1);
    double y(int v) => _pad + (size.height - 2 * _pad) * (1 - v / most);
    final line = Path()..moveTo(0, y(values.first));
    for (var i = 1; i < values.length; i++) {
      line.lineTo(x(i), y(values[i]));
    }
    final area = Path.from(line)
      ..lineTo(size.width, size.height)
      ..lineTo(0, size.height)
      ..close();
    final t = Curves.easeOutCubic.transform(drawn.value);
    canvas.save();
    // Drawn in from the left
    canvas.clipRect(Rect.fromLTWH(0, 0, size.width * t + 4, size.height));
    canvas.drawPath(
      area,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [color.withValues(alpha: 0.22), color.withValues(alpha: 0)],
        ).createShader(Offset.zero & size),
    );
    canvas.drawPath(
      line,
      Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2
        ..strokeJoin = StrokeJoin.round
        ..strokeCap = StrokeCap.round,
    );
    canvas.restore();
    final shown = touched ?? values.length - 1;
    if (touched != null) {
      canvas.drawLine(
        Offset(x(shown), 0),
        Offset(x(shown), size.height),
        Paint()
          ..color = color.withValues(alpha: 0.5)
          ..strokeWidth = 1,
      );
    }
    if (t > 0.95 || touched != null) {
      canvas.drawCircle(Offset(x(shown), y(values[shown])), 3.5, Paint()..color = color);
    }
  }

  @override
  bool shouldRepaint(_SparklinePainter old) => old.values != values || old.color != color || old.touched != touched;
}
