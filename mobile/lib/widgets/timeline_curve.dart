import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../data/stats.dart';
import '../l10n/strings.dart';
import '../theme/palette.dart';
import 'format.dart';

/// An artist's plays over time as a curve that draws itself from left to right in the two colors of their picture,
/// with the most played day or month marked and the last days against the days before them as an arrow over it, as
/// the desktop app's TimelineCurve. A tap picks a day and keeps it (the same one again goes back to the peak) and a
/// sideways drag runs through them, as on the hours' curve
class TimelineCurve extends StatefulWidget {
  final List<Bucket> buckets;
  final bool daily;
  final RecentTrend? trend;
  final Color color;
  final Color color2;

  const TimelineCurve({
    super.key,
    required this.buckets,
    required this.daily,
    required this.trend,
    required this.color,
    required this.color2,
  });

  @override
  State<TimelineCurve> createState() => _TimelineCurveState();
}

class _TimelineCurveState extends State<TimelineCurve> with TickerProviderStateMixin {
  static const height = 170.0;
  // The curve draws itself, then the marked day and the arrow come in and the arrow nods twice
  late final _reveal = AnimationController(vsync: this, duration: const Duration(milliseconds: 1300))..forward();
  late final _nod = AnimationController(vsync: this, duration: const Duration(milliseconds: 1800));
  int? _touched;

  @override
  void initState() {
    super.initState();
    _reveal.addStatusListener((status) {
      if (status == AnimationStatus.completed) _nod.forward();
    });
  }

  @override
  void dispose() {
    _reveal.dispose();
    _nod.dispose();
    super.dispose();
  }

  int get _peak {
    final buckets = widget.buckets;
    var peak = 0;
    // The latest of equal ones, as the desktop app
    for (var i = 1; i < buckets.length; i++) {
      if (buckets[i].plays >= buckets[peak].plays) peak = i;
    }
    return peak;
  }

  int _at(Offset at, double width) =>
      (at.dx / width * widget.buckets.length).floor().clamp(0, widget.buckets.length - 1);

  void _pick(int? index) {
    if (index == _touched) return;
    HapticFeedback.selectionClick();
    setState(() => _touched = index);
  }

  String _when(BuildContext context, DateTime start) =>
      context.dateFormat(widget.daily ? 'd MMMM' : 'MMMM y').format(start);

  Widget _trend(BuildContext context) {
    final trend = widget.trend!;
    final palette = Palette.of(context);
    final days = {'days': trendDays};
    final before = trend.before;
    final up = before != null && trend.recent > before;
    final down = before != null && trend.recent < before;
    final against = before == null
        ? null
        : before == 0
        ? context.t('detail.trend.none_before', days)
        : trend.recent == before
        ? context.t('detail.trend.same', days)
        : context.t('detail.trend.against', days);
    final text = [
      context.t('detail.trend.recent', {...days, 'plays': context.plays(trend.recent)}),
      ?against,
    ].join('  ·  ');
    final color = up ? palette.added : palette.removed;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Wrap(
        crossAxisAlignment: WrapCrossAlignment.center,
        spacing: 8,
        runSpacing: 4,
        children: [
          if (up || down)
            FadeTransition(
              opacity: CurvedAnimation(parent: _reveal, curve: const Interval(0.85, 1)),
              child: Container(
                padding: const EdgeInsets.fromLTRB(7, 2, 10, 2),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    AnimatedBuilder(
                      animation: _nod,
                      // Two small nods the way the arrow points
                      builder: (context, child) => Transform.translate(
                        offset: Offset(0, (up ? -3 : 3) * math.sin(math.pi * (_nod.value * 2 % 1))),
                        child: child,
                      ),
                      child: Icon(
                        up ? Icons.arrow_upward_rounded : Icons.arrow_downward_rounded,
                        size: 14,
                        color: color,
                      ),
                    ),
                    const SizedBox(width: 3),
                    Text(
                      context.t('stats.percent', {
                        'value': context.number(((trend.recent - before) * 100 / before).abs().round()),
                      }),
                      style: TextStyle(color: color, fontSize: 13, fontWeight: FontWeight.w600),
                    ),
                  ],
                ),
              ),
            ),
          Text(text, style: TextStyle(color: palette.muted, fontSize: 13)),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final surface = Theme.of(context).colorScheme.surfaceContainer;
    final buckets = widget.buckets;
    final most = buckets.map((b) => b.plays).reduce(math.max);
    final count = buckets.length;
    final shown = _touched ?? _peak;
    final label = _touched == null
        ? context.t(widget.daily ? 'detail.timeline.peak_day' : 'detail.timeline.peak', {
            'when': _when(context, buckets[shown].start),
          })
        : '${_when(context, buckets[shown].start)}  ·  ${context.plays(buckets[shown].plays)}';
    final every = count > 16 ? (count / 8).ceil() : 1;
    final late = CurvedAnimation(parent: _reveal, curve: const Interval(0.85, 1));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (widget.trend != null) _trend(context),
        LayoutBuilder(
          builder: (context, constraints) {
            final width = constraints.maxWidth;
            final x = (shown + 0.5) / count * width;
            final y = height - (most == 0 ? 0 : buckets[shown].plays / most) * (height - _TimelinePainter.top);
            return GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTapUp: (details) {
                final index = _at(details.localPosition, width);
                _pick(index == _touched ? null : index);
              },
              onHorizontalDragStart: (details) => _pick(_at(details.localPosition, width)),
              onHorizontalDragUpdate: (details) => _pick(_at(details.localPosition, width)),
              child: SizedBox(
                height: height,
                width: width,
                child: Stack(
                  clipBehavior: Clip.none,
                  children: [
                    Positioned.fill(
                      child: RepaintBoundary(
                        child: AnimatedBuilder(
                          animation: _reveal,
                          builder: (context, _) => CustomPaint(
                            painter: _TimelinePainter(
                              plays: [for (final b in buckets) b.plays],
                              color: widget.color,
                              color2: widget.color2,
                              grid: palette.border,
                              shown: _reveal.isCompleted ? shown : null,
                              progress: Curves.easeInOutCubic.transform(_reveal.value),
                            ),
                          ),
                        ),
                      ),
                    ),
                    Positioned(
                      left: x - 6,
                      top: y - 6,
                      child: FadeTransition(
                        opacity: late,
                        child: Container(
                          width: 12,
                          height: 12,
                          decoration: BoxDecoration(
                            color: widget.color,
                            shape: BoxShape.circle,
                            border: Border.all(color: surface, width: 2),
                            boxShadow: [
                              if (_touched == null)
                                BoxShadow(color: widget.color.withValues(alpha: 0.3), spreadRadius: 4),
                            ],
                          ),
                        ),
                      ),
                    ),
                    Positioned(
                      left: 0,
                      right: 0,
                      top: math.max(0, y - 36),
                      // Over the day, leaning inward near an edge so it stays on the card
                      child: FadeTransition(
                        opacity: late,
                        child: Align(
                          alignment: Alignment(x / width * 2 - 1, 0),
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                            decoration: BoxDecoration(
                              color: surface,
                              borderRadius: BorderRadius.circular(999),
                              boxShadow: const [
                                BoxShadow(color: Color(0x2E000000), blurRadius: 6, offset: Offset(0, 1)),
                              ],
                            ),
                            child: Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
        const SizedBox(height: 6),
        Row(
          children: [
            for (var i = 0; i < count; i++)
              Expanded(
                child: Text(
                  i % every == 0
                      ? (widget.daily ? '${buckets[i].start.day}' : context.dateFormat('MMM').format(buckets[i].start))
                      : '',
                  textAlign: TextAlign.center,
                  softWrap: false,
                  overflow: TextOverflow.visible,
                  style: TextStyle(color: palette.muted, fontSize: 11),
                ),
              ),
          ],
        ),
      ],
    );
  }
}

class _TimelinePainter extends CustomPainter {
  static const top = 34.0;

  final List<int> plays;
  final Color color;
  final Color color2;
  final Color grid;
  final int? shown;

  /// How much of the curve is drawn, 0 to 1 from the left
  final double progress;

  _TimelinePainter({
    required this.plays,
    required this.color,
    required this.color2,
    required this.grid,
    required this.shown,
    required this.progress,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final most = math.max(1, plays.reduce(math.max));
    final count = plays.length;
    double x(int i) => (i + 0.5) / count * size.width;
    double y(int i) => size.height - plays[i] / most * (size.height - top);
    final whole = Offset.zero & size;

    // A few faint dotted lines across
    final gridPaint = Paint()
      ..color = grid
      ..strokeWidth = 1;
    for (final part in const [0.25, 0.5, 0.75]) {
      final dy = top + (size.height - top) * part;
      for (var dx = 0.0; dx < size.width; dx += 7) {
        canvas.drawLine(Offset(dx, dy), Offset(math.min(dx + 2, size.width), dy), gridPaint);
      }
    }

    // The line runs on flat to both edges, so it does not end in the air half a column in
    final points = [
      Offset(0, y(0)),
      Offset(0, y(0)),
      for (var i = 0; i < count; i++) Offset(x(i), y(i)),
      Offset(size.width, y(count - 1)),
      Offset(size.width, y(count - 1)),
    ];
    double keep(double value) => value.clamp(top / 2, size.height);
    final line = Path()..moveTo(points[1].dx, points[1].dy);
    for (var i = 1; i < points.length - 2; i++) {
      final (p0, p1, p2, p3) = (points[i - 1], points[i], points[i + 1], points[i + 2]);
      line.cubicTo(
        p1.dx + (p2.dx - p0.dx) / 6,
        keep(p1.dy + (p2.dy - p0.dy) / 6),
        p2.dx - (p3.dx - p1.dx) / 6,
        keep(p2.dy - (p3.dy - p1.dy) / 6),
        p2.dx,
        p2.dy,
      );
    }
    final area = Path.from(line)
      ..lineTo(size.width, size.height)
      ..lineTo(0, size.height)
      ..close();

    canvas.save();
    canvas.clipRect(Rect.fromLTWH(0, -4, size.width * progress, size.height + 8));
    canvas.drawPath(
      area,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [color.withValues(alpha: 0.5), color.withValues(alpha: 0.02)],
        ).createShader(whole),
    );
    // From the picture's second color on the left into its first
    canvas.drawPath(
      line,
      Paint()
        ..shader = LinearGradient(
          colors: [color2.withValues(alpha: 0.8), color],
          stops: const [0, 0.7],
        ).createShader(whole)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.5
        ..strokeJoin = StrokeJoin.round
        ..strokeCap = StrokeCap.round,
    );
    canvas.restore();

    // A dashed guide from the marked day down to the baseline
    if (shown case final shown?) {
      final guide = Paint()
        ..color = color.withValues(alpha: 0.7)
        ..strokeWidth = 1;
      for (var dy = y(shown); dy < size.height; dy += 7) {
        canvas.drawLine(Offset(x(shown), dy), Offset(x(shown), math.min(dy + 3, size.height)), guide);
      }
    }
  }

  @override
  bool shouldRepaint(_TimelinePainter old) =>
      old.plays != plays ||
      old.color != color ||
      old.color2 != color2 ||
      old.shown != shown ||
      old.progress != progress;
}
