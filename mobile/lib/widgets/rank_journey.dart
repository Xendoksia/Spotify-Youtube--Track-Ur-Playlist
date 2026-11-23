import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../data/stats.dart';
import '../l10n/strings.dart';
import '../theme/palette.dart';
import 'format.dart';

/// A track's place among all tracks day by day (or month by month) as a line that draws itself from left to right
/// in the two colors of its cover, the first place at the top, over a fill of its plays so far, as the desktop app's
/// RankJourney. The top ten is shaded and its best place and the day it first reached the top ten are marked. A tap
/// picks a day and keeps it (the same one again goes back) and a sideways drag runs through them
class RankJourney extends StatefulWidget {
  final List<JourneyPoint> points;
  final bool daily;
  final Color color;
  final Color color2;

  const RankJourney({super.key, required this.points, required this.daily, required this.color, required this.color2});

  @override
  State<RankJourney> createState() => _RankJourneyState();
}

class _RankJourneyState extends State<RankJourney> with SingleTickerProviderStateMixin {
  static const height = 170.0;
  static const ticksWidth = 30.0;
  static const topPlaces = 10;

  late final _reveal = AnimationController(vsync: this, duration: const Duration(milliseconds: 1300))..forward();
  int? _touched;

  @override
  void dispose() {
    _reveal.dispose();
    super.dispose();
  }

  List<int> get _ranked => [
    for (var i = 0; i < widget.points.length; i++)
      if (widget.points[i].rank != null) i,
  ];

  int _at(Offset at, double width) {
    final index = (at.dx / width * widget.points.length).floor().clamp(0, widget.points.length - 1);
    // Before its first play there is no place to show: the first played day instead
    return widget.points[index].rank == null ? _ranked.first : index;
  }

  void _pick(int? index) {
    if (index == _touched) return;
    HapticFeedback.selectionClick();
    setState(() => _touched = index);
  }

  String _when(BuildContext context, DateTime start) =>
      context.dateFormat(widget.daily ? 'd MMMM' : 'MMMM y').format(start);

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final surface = Theme.of(context).colorScheme.surfaceContainer;
    final points = widget.points;
    final ranked = _ranked;
    if (ranked.isEmpty) return const SizedBox.shrink();
    final first = points[ranked.first];
    final last = points[ranked.last];
    // The best place, the latest of equal ones, and the first day in the top ten when that is a day of its own
    var best = ranked.first;
    for (final i in ranked) {
      if (points[i].rank! <= points[best].rank!) best = i;
    }
    int? top;
    for (final i in ranked) {
      if (points[i].rank! <= topPlaces) {
        top = i;
        break;
      }
    }
    if (top == best || top == ranked.first) top = null;
    final scale = _Scale(math.max(50, points.map((p) => p.rank ?? 1).reduce(math.max) * 1.15), height);
    final summaryKey = last.rank! < first.rank!
        ? 'detail.journey.up'
        : last.rank! > first.rank!
        ? 'detail.journey.down'
        : 'detail.journey.same';
    final summary = context.t(summaryKey, {
      'start': context.number(first.rank!),
      'now': context.number(last.rank!),
      'plays': context.plays(last.plays),
    });
    final count = points.length;
    final every = count > 16 ? (count / 8).ceil() : 1;
    final late = CurvedAnimation(parent: _reveal, curve: const Interval(0.85, 1));

    final marks = _touched != null
        ? [
            (
              _touched!,
              '${_when(context, points[_touched!].start)}  ·  '
                  '${context.t('detail.journey.rank', {'rank': context.number(points[_touched!].rank!)})}  ·  '
                  '${context.plays(points[_touched!].plays)}',
              false,
            ),
          ]
        : [
            (best, context.t('detail.journey.best', {'rank': context.number(points[best].rank!)}), false),
            if (top != null) (top, context.t('detail.journey.top', {'when': _when(context, points[top].start)}), true),
          ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(summary, style: TextStyle(color: palette.muted, fontSize: 13)),
        const SizedBox(height: 12),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              width: ticksWidth,
              height: height,
              child: Stack(
                clipBehavior: Clip.none,
                children: [
                  for (final tick in scale.ticks)
                    Positioned(
                      right: 6,
                      top: scale.y(tick) - 7,
                      child: Text('${context.number(tick)}.', style: TextStyle(color: palette.muted, fontSize: 11)),
                    ),
                ],
              ),
            ),
            Expanded(
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final width = constraints.maxWidth;
                  double x(int i) => (i + 0.5) / count * width;
                  return GestureDetector(
                    behavior: HitTestBehavior.opaque,
                    onTapUp: (details) {
                      final index = _at(details.localPosition, width);
                      _pick(index == _touched ? null : index);
                    },
                    onHorizontalDragStart: (details) => _pick(_at(details.localPosition, width)),
                    onHorizontalDragUpdate: (details) => _pick(_at(details.localPosition, width)),
                    child: SizedBox(
                      width: width,
                      height: height,
                      child: Stack(
                        clipBehavior: Clip.none,
                        children: [
                          Positioned.fill(
                            child: RepaintBoundary(
                              child: AnimatedBuilder(
                                animation: _reveal,
                                builder: (context, _) => CustomPaint(
                                  painter: _JourneyPainter(
                                    points: points,
                                    scale: scale,
                                    color: widget.color,
                                    color2: widget.color2,
                                    grid: palette.border,
                                    band: palette.muted,
                                    touched: _touched,
                                    progress: Curves.easeInOutCubic.transform(_reveal.value),
                                  ),
                                ),
                              ),
                            ),
                          ),
                          Positioned(
                            left: 6,
                            top: scale.y(topPlaces) - 17,
                            child: FadeTransition(
                              opacity: late,
                              child: Text(
                                context.t('detail.journey.band', {'places': topPlaces}),
                                style: TextStyle(color: palette.muted, fontSize: 11),
                              ),
                            ),
                          ),
                          Positioned(
                            right: 6,
                            bottom: 4,
                            child: FadeTransition(
                              opacity: late,
                              child: Text(
                                context.plays(last.plays),
                                style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                              ),
                            ),
                          ),
                          for (final (index, text, below) in marks) ...[
                            Positioned(
                              left: x(index) - 6,
                              top: scale.y(points[index].rank!) - 6,
                              child: FadeTransition(
                                opacity: _touched == null ? late : kAlwaysCompleteAnimation,
                                child: Container(
                                  width: 12,
                                  height: 12,
                                  decoration: BoxDecoration(
                                    color: widget.color,
                                    shape: BoxShape.circle,
                                    border: Border.all(color: surface, width: 2),
                                  ),
                                ),
                              ),
                            ),
                            Positioned(
                              left: 0,
                              right: 0,
                              top: below
                                  ? scale.y(points[index].rank!) + 10
                                  : math.max(-8, scale.y(points[index].rank!) - 34),
                              // Over (or under) the day, leaning inward near an edge so it stays on the card
                              child: FadeTransition(
                                opacity: _touched == null ? late : kAlwaysCompleteAnimation,
                                child: Align(
                                  alignment: Alignment(x(index) / width * 2 - 1, 0),
                                  child: Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                    decoration: BoxDecoration(
                                      color: surface,
                                      borderRadius: BorderRadius.circular(999),
                                      boxShadow: const [
                                        BoxShadow(color: Color(0x2E000000), blurRadius: 6, offset: Offset(0, 1)),
                                      ],
                                    ),
                                    child: Text(
                                      text,
                                      style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
        Padding(
          padding: const EdgeInsets.only(left: ticksWidth),
          child: Row(
            children: [
              for (var i = 0; i < count; i++)
                Expanded(
                  child: Text(
                    i % every == 0
                        ? (widget.daily ? '${points[i].start.day}' : context.dateFormat('MMM').format(points[i].start))
                        : '',
                    textAlign: TextAlign.center,
                    softWrap: false,
                    overflow: TextOverflow.visible,
                    style: TextStyle(color: palette.muted, fontSize: 11),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

/// Places on a square root scale with the first at the top, so a climb from 140th to 5th and one from 5th to 1st
/// both show without the top ten taking half the chart; it reaches at least the 50th place
class _Scale {
  static const top = 34.0;
  static const bottom = 8.0;
  static const _ticks = [1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500];

  final double lowest;
  final double height;

  _Scale(num lowest, this.height) : lowest = lowest.toDouble();

  double y(num rank) => top + math.sqrt(rank - 1) / math.sqrt(lowest - 1) * (height - top - bottom);

  /// The places marked beside the chart, leaving out ones that would crowd the one above
  List<int> get ticks {
    final shown = <int>[];
    for (final tick in _ticks.where((t) => t <= lowest)) {
      if (shown.isEmpty || y(tick) - y(shown.last) > 18) shown.add(tick);
    }
    return shown;
  }
}

class _JourneyPainter extends CustomPainter {
  /// The plays' fill rises to this share of the chart's height
  static const playsReach = 0.85;

  final List<JourneyPoint> points;
  final _Scale scale;
  final Color color;
  final Color color2;
  final Color grid;
  final Color band;
  final int? touched;

  /// How much is drawn, 0 to 1 from the left
  final double progress;

  _JourneyPainter({
    required this.points,
    required this.scale,
    required this.color,
    required this.color2,
    required this.grid,
    required this.band,
    required this.touched,
    required this.progress,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final count = points.length;
    double x(int i) => (i + 0.5) / count * size.width;
    final whole = Offset.zero & size;

    // The top ten, faintly shaded, and dotted lines at the marked places
    canvas.drawRRect(
      RRect.fromLTRBR(0, scale.y(1) - 4, size.width, scale.y(10), const Radius.circular(6)),
      Paint()..color = band.withValues(alpha: 0.1),
    );
    final gridPaint = Paint()
      ..color = grid
      ..strokeWidth = 1;
    for (final tick in scale.ticks.skip(1)) {
      final dy = scale.y(tick);
      for (var dx = 0.0; dx < size.width; dx += 7) {
        canvas.drawLine(Offset(dx, dy), Offset(math.min(dx + 2, size.width), dy), gridPaint);
      }
    }

    final drawn = [
      for (var i = 0; i < count; i++)
        if (points[i].rank != null) i,
    ];
    if (drawn.isEmpty) return;
    final most = math.max(1, points.map((p) => p.plays).reduce(math.max));
    double playsY(int plays) => size.height - plays / most * (size.height - _Scale.top) * playsReach;

    canvas.save();
    canvas.clipRect(Rect.fromLTWH(0, -4, size.width * progress, size.height + 8));
    // Its plays so far as the fill behind
    final fill = Path()..moveTo(x(drawn.first), size.height);
    for (final i in drawn) {
      fill.lineTo(x(i), playsY(points[i].plays));
    }
    fill
      ..lineTo(x(drawn.last), size.height)
      ..close();
    canvas.drawPath(
      fill,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [color.withValues(alpha: 0.4), color.withValues(alpha: 0.02)],
        ).createShader(whole),
    );
    // Its place, from the cover's second color into its first
    final line = Path();
    for (final (n, i) in drawn.indexed) {
      final at = Offset(x(i), scale.y(points[i].rank!));
      n == 0 ? line.moveTo(at.dx, at.dy) : line.lineTo(at.dx, at.dy);
    }
    canvas.drawPath(
      line,
      Paint()
        ..shader = LinearGradient(colors: [color2, color]).createShader(whole)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.5
        ..strokeJoin = StrokeJoin.round
        ..strokeCap = StrokeCap.round,
    );
    canvas.restore();

    // A dashed guide from the picked day down to the baseline
    if (touched case final touched?) {
      final guide = Paint()
        ..color = color.withValues(alpha: 0.7)
        ..strokeWidth = 1;
      for (var dy = scale.y(points[touched].rank!); dy < size.height; dy += 7) {
        canvas.drawLine(Offset(x(touched), dy), Offset(x(touched), math.min(dy + 3, size.height)), guide);
      }
    }
  }

  @override
  bool shouldRepaint(_JourneyPainter old) =>
      old.points != points ||
      old.color != color ||
      old.color2 != color2 ||
      old.touched != touched ||
      old.progress != progress;
}
