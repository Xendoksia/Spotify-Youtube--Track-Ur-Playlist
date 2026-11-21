/// The pictures that fill the summary's slides: a wall of the month's covers, a record turning out of its sleeve,
/// a ring of the artist's share, floating bubbles, a clock of the hours and a calendar of dots.
///
/// They stay smooth by moving only drawings that are kept (each moving part sits in its own RepaintBoundary and is
/// only shifted or turned), and what has to be painted again (the rings, the clock) is small and short.
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';

/// A tilted wall of covers behind a slide, its rows gliding slowly in turns, darker in the middle so the text over
/// it stays readable
class CoverWall extends StatefulWidget {
  final List<Widget Function(double size)> covers;

  const CoverWall({super.key, required this.covers});

  @override
  State<CoverWall> createState() => _CoverWallState();
}

class _CoverWallState extends State<CoverWall> with SingleTickerProviderStateMixin {
  static const _size = 96.0;
  static const _gap = 10.0;
  static const _rows = 6;

  late final _glide = AnimationController(vsync: this, duration: const Duration(seconds: 60))..repeat();

  @override
  void dispose() {
    _glide.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final covers = widget.covers;
    if (covers.isEmpty) return const SizedBox();
    const step = _size + _gap;
    return ClipRect(
      child: Stack(
        fit: StackFit.expand,
        children: [
          OverflowBox(
            maxWidth: double.infinity,
            maxHeight: double.infinity,
            child: Transform.rotate(
              angle: -0.2,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  for (var row = 0; row < _rows; row++)
                    Padding(
                      padding: const EdgeInsets.only(bottom: _gap),
                      child: _row(row, step),
                    ),
                ],
              ),
            ),
          ),
          // Darker in the middle, where the slide's text is
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: RadialGradient(
                radius: 0.9,
                colors: [Color(0xCC000000), Color(0x66000000)],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _row(int row, double step) {
    final covers = widget.covers;
    // Each row starts further along the covers, so neighbouring rows do not repeat each other
    const count = 7;
    final items = [for (var i = 0; i < count * 2; i++) covers[(row * 3 + i) % covers.length]];
    final width = count * step;
    final cached = RepaintBoundary(
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          for (final cover in items) Padding(padding: const EdgeInsets.only(right: _gap), child: cover(_size)),
        ],
      ),
    );
    return SizedBox(
      width: width,
      height: _size,
      child: OverflowBox(
        alignment: Alignment.centerLeft,
        maxWidth: double.infinity,
        child: AnimatedBuilder(
          animation: _glide,
          // Every other row glides the other way, by one set of covers per turn so that it loops without a jump
          builder: (context, child) {
            final shift = (_glide.value * (row.isEven ? 1 : -1) + row * 0.37) % 1;
            return Transform.translate(offset: Offset(-shift * width, 0), child: child);
          },
          child: cached,
        ),
      ),
    );
  }
}

/// The song's cover with its record sliding out from behind it and turning
class SpinningRecord extends StatefulWidget {
  final Widget cover;
  final Widget label;
  final double size;

  const SpinningRecord({super.key, required this.cover, required this.label, this.size = 200});

  @override
  State<SpinningRecord> createState() => _SpinningRecordState();
}

class _SpinningRecordState extends State<SpinningRecord> with TickerProviderStateMixin {
  late final _spin = AnimationController(vsync: this, duration: const Duration(milliseconds: 2400))..repeat();
  late final _out = AnimationController(vsync: this, duration: const Duration(milliseconds: 1100));

  @override
  void initState() {
    super.initState();
    Future.delayed(const Duration(milliseconds: 450), () {
      if (mounted) _out.forward();
    });
  }

  @override
  void dispose() {
    _spin.dispose();
    _out.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final size = widget.size;
    final disc = size * 0.94;
    final reach = size * 0.36;
    final record = RepaintBoundary(
      child: SizedBox.square(
        dimension: disc,
        child: Stack(
          alignment: Alignment.center,
          children: [
            const Positioned.fill(child: CustomPaint(painter: _GroovesPainter())),
            ClipOval(child: SizedBox.square(dimension: disc * 0.36, child: widget.label)),
            Container(
              width: disc * 0.04,
              height: disc * 0.04,
              decoration: const BoxDecoration(shape: BoxShape.circle, color: Color(0xFF111111)),
            ),
          ],
        ),
      ),
    );
    return SizedBox(
      width: size + reach,
      height: size,
      child: Stack(
        clipBehavior: Clip.none,
        alignment: Alignment.centerLeft,
        children: [
          AnimatedBuilder(
            animation: _out,
            builder: (context, child) => Transform.translate(
              offset: Offset((size - disc) / 2 + reach * Curves.easeOutBack.transform(_out.value), 0),
              child: child,
            ),
            child: RotationTransition(turns: _spin, child: record),
          ),
          // The light on the record stays still while it turns
          AnimatedBuilder(
            animation: _out,
            builder: (context, child) => Transform.translate(
              offset: Offset((size - disc) / 2 + reach * Curves.easeOutBack.transform(_out.value), 0),
              child: child,
            ),
            child: IgnorePointer(
              child: SizedBox.square(dimension: disc, child: const CustomPaint(painter: _SheenPainter())),
            ),
          ),
          Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(size * 0.08),
              boxShadow: const [BoxShadow(color: Color(0x66000000), blurRadius: 24, offset: Offset(6, 10))],
            ),
            child: widget.cover,
          ),
        ],
      ),
    );
  }
}

class _GroovesPainter extends CustomPainter {
  const _GroovesPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = size.width / 2;
    canvas.drawCircle(center, radius, Paint()..color = const Color(0xFF0E0E10));
    final groove = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.7;
    for (var r = radius * 0.4; r < radius * 0.97; r += 3.2) {
      groove.color = Colors.white.withValues(alpha: ((r * 7).round() % 3 == 0) ? 0.09 : 0.04);
      canvas.drawCircle(center, r, groove);
    }
  }

  @override
  bool shouldRepaint(_GroovesPainter old) => false;
}

class _SheenPainter extends CustomPainter {
  const _SheenPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    canvas.drawCircle(
      rect.center,
      size.width / 2,
      Paint()
        ..shader = SweepGradient(
          colors: [
            Colors.white.withValues(alpha: 0),
            Colors.white.withValues(alpha: 0.13),
            Colors.white.withValues(alpha: 0),
            Colors.white.withValues(alpha: 0),
            Colors.white.withValues(alpha: 0.1),
            Colors.white.withValues(alpha: 0),
          ],
          stops: const [0.05, 0.13, 0.22, 0.55, 0.63, 0.72],
        ).createShader(rect),
    );
  }

  @override
  bool shouldRepaint(_SheenPainter old) => false;
}

/// A round photo in a ring that fills to [share] (0 to 1) once, with soft rings beating out of it
class ShareRing extends StatefulWidget {
  final Widget photo;
  final double share;
  final double size;

  const ShareRing({super.key, required this.photo, required this.share, this.size = 200});

  @override
  State<ShareRing> createState() => _ShareRingState();
}

class _ShareRingState extends State<ShareRing> with TickerProviderStateMixin {
  late final _fill = AnimationController(vsync: this, duration: const Duration(milliseconds: 1400));
  late final _beat = AnimationController(vsync: this, duration: const Duration(milliseconds: 2600))..repeat();

  @override
  void initState() {
    super.initState();
    Future.delayed(const Duration(milliseconds: 350), () {
      if (mounted) _fill.forward();
    });
  }

  @override
  void dispose() {
    _fill.dispose();
    _beat.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final size = widget.size;
    final outer = size + 110;
    return SizedBox.square(
      dimension: outer,
      child: Stack(
        alignment: Alignment.center,
        children: [
          Positioned.fill(
            child: RepaintBoundary(child: CustomPaint(painter: _BeatPainter(_beat, size / 2 + 14))),
          ),
          SizedBox.square(
            dimension: size + 28,
            child: RepaintBoundary(
              child: CustomPaint(
                painter: _ArcPainter(CurvedAnimation(parent: _fill, curve: Curves.easeOutCubic), widget.share),
              ),
            ),
          ),
          RepaintBoundary(child: widget.photo),
        ],
      ),
    );
  }
}

class _ArcPainter extends CustomPainter {
  final Animation<double> progress;
  final double share;

  _ArcPainter(this.progress, this.share) : super(repaint: progress);

  @override
  void paint(Canvas canvas, Size size) {
    final rect = (Offset.zero & size).deflate(4);
    final line = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 6
      ..strokeCap = StrokeCap.round;
    canvas.drawArc(rect, 0, 2 * math.pi, false, line..color = Colors.white.withValues(alpha: 0.18));
    final sweep = 2 * math.pi * share.clamp(0.0, 1.0) * progress.value;
    if (sweep > 0) canvas.drawArc(rect, -math.pi / 2, sweep, false, line..color = Colors.white);
  }

  @override
  bool shouldRepaint(_ArcPainter old) => old.share != share;
}

class _BeatPainter extends CustomPainter {
  final Animation<double> beat;
  final double from;

  _BeatPainter(this.beat, this.from) : super(repaint: beat);

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final reach = size.width / 2 - from;
    final ring = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;
    for (final offset in [0.0, 0.5]) {
      final t = (beat.value + offset) % 1;
      ring.color = Colors.white.withValues(alpha: 0.35 * (1 - t));
      canvas.drawCircle(center, from + reach * Curves.easeOut.transform(t), ring);
    }
  }

  @override
  bool shouldRepaint(_BeatPainter old) => false;
}

/// Pictures that pop up one after another around the middle and then float gently
class FloatingBubbles extends StatefulWidget {
  final List<Widget Function(double size)> pictures;
  final double height;

  const FloatingBubbles({super.key, required this.pictures, this.height = 280});

  @override
  State<FloatingBubbles> createState() => _FloatingBubblesState();
}

class _FloatingBubblesState extends State<FloatingBubbles> with TickerProviderStateMixin {
  /// Where each bubble sits, as shares of the box, and its size
  static const _spots = [
    (0.5, 0.45, 104.0),
    (0.16, 0.25, 70.0),
    (0.84, 0.27, 76.0),
    (0.12, 0.72, 62.0),
    (0.86, 0.72, 66.0),
    (0.34, 0.88, 50.0),
    (0.66, 0.89, 54.0),
    (0.5, 0.1, 46.0),
  ];

  late final _float = AnimationController(vsync: this, duration: const Duration(seconds: 5))..repeat();
  late final _pop = AnimationController(vsync: this, duration: const Duration(milliseconds: 1600))..forward();

  @override
  void dispose() {
    _float.dispose();
    _pop.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final pictures = widget.pictures.take(_spots.length).toList();
    return SizedBox(
      height: widget.height,
      child: LayoutBuilder(
        // Floating and bouncing in, a bubble may reach a little past the box
        builder: (context, box) => Stack(
          clipBehavior: Clip.none,
          children: [
            for (final (index, picture) in pictures.indexed)
              Builder(builder: (context) {
                final (x, y, size) = _spots[index];
                final start = (index * 0.09).clamp(0.0, 0.6);
                final pop = CurvedAnimation(
                    parent: _pop, curve: Interval(start, (start + 0.4).clamp(0.0, 1.0), curve: Curves.elasticOut));
                return Positioned(
                  left: box.maxWidth * x - size / 2,
                  top: widget.height * y - size / 2,
                  child: AnimatedBuilder(
                    animation: _float,
                    builder: (context, child) => Transform.translate(
                      offset: Offset(0, 5 * math.sin(2 * math.pi * _float.value + index * 1.3)),
                      child: child,
                    ),
                    child: ScaleTransition(
                      scale: pop,
                      child: RepaintBoundary(
                        child: Container(
                          padding: const EdgeInsets.all(2.5),
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: Colors.white.withValues(alpha: 0.85),
                            boxShadow: const [BoxShadow(color: Color(0x55000000), blurRadius: 14, offset: Offset(0, 6))],
                          ),
                          child: picture(size - 5),
                        ),
                      ),
                    ),
                  ),
                );
              }),
          ],
        ),
      ),
    );
  }
}

/// The day's 24 hours as bars round a clock, growing in once, the busiest one bright, with [center] in the middle
class HourClock extends StatefulWidget {
  final List<int> hours;
  final Widget center;
  final double size;

  const HourClock({super.key, required this.hours, required this.center, this.size = 250});

  @override
  State<HourClock> createState() => _HourClockState();
}

class _HourClockState extends State<HourClock> with SingleTickerProviderStateMixin {
  late final _grow = AnimationController(vsync: this, duration: const Duration(milliseconds: 1500))..forward();

  @override
  void dispose() {
    _grow.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => SizedBox.square(
        dimension: widget.size,
        child: Stack(
          alignment: Alignment.center,
          children: [
            Positioned.fill(
              child: RepaintBoundary(
                child: CustomPaint(
                  painter: _ClockPainter(_grow, widget.hours, Theme.of(context).textTheme.labelSmall!),
                ),
              ),
            ),
            widget.center,
          ],
        ),
      );
}

class _ClockPainter extends CustomPainter {
  final Animation<double> grow;
  final List<int> hours;
  final TextStyle label;

  _ClockPainter(this.grow, this.hours, this.label) : super(repaint: grow);

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final outer = size.width / 2 - 18;
    final inner = outer * 0.48;
    final most = hours.fold(1, math.max);
    final peak = List.generate(24, (h) => h).reduce((a, b) => hours[b] > hours[a] ? b : a);
    final bar = Paint()
      ..strokeCap = StrokeCap.round
      ..strokeWidth = (2 * math.pi * inner / 24) * 0.62;
    canvas.drawCircle(
        center,
        inner - 6,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1
          ..color = Colors.white.withValues(alpha: 0.2));
    for (var h = 0; h < 24; h++) {
      // The bars grow one after another round the clock
      final start = h / 24 * 0.5;
      final t = Curves.easeOutCubic.transform(((grow.value - start) / 0.5).clamp(0.0, 1.0));
      final angle = -math.pi / 2 + h / 24 * 2 * math.pi + math.pi / 24;
      final direction = Offset(math.cos(angle), math.sin(angle));
      final length = 4 + (outer - inner - 4) * hours[h] / most;
      bar.color = h == peak ? Colors.white : Colors.white.withValues(alpha: 0.4);
      canvas.drawLine(center + direction * inner, center + direction * (inner + length * t), bar);
    }
    for (final h in [0, 6, 12, 18]) {
      final angle = -math.pi / 2 + h / 24 * 2 * math.pi;
      final text = TextPainter(
        text: TextSpan(
            text: h.toString().padLeft(2, '0'), style: label.copyWith(color: Colors.white.withValues(alpha: 0.6))),
        textDirection: TextDirection.ltr,
      )..layout();
      final at = center + Offset(math.cos(angle), math.sin(angle)) * (outer + 10);
      text.paint(canvas, at - Offset(text.width / 2, text.height / 2));
    }
  }

  @override
  bool shouldRepaint(_ClockPainter old) => old.hours != hours;
}

/// A calendar of dots, one per day (or per month of a year), each as big as its plays, popping in one after
/// another; [blank] empty places before the first (the weekday the month starts on), the busiest one ringed
class DotCalendar extends StatefulWidget {
  final List<int> counts;
  final int columns;
  final int blank;
  final List<String> headers;

  const DotCalendar({super.key, required this.counts, this.columns = 7, this.blank = 0, this.headers = const []});

  @override
  State<DotCalendar> createState() => _DotCalendarState();
}

class _DotCalendarState extends State<DotCalendar> with SingleTickerProviderStateMixin {
  late final _pop = AnimationController(vsync: this, duration: const Duration(milliseconds: 1400))..forward();

  @override
  void dispose() {
    _pop.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final rows = ((widget.blank + widget.counts.length) / widget.columns).ceil();
    const cell = 30.0;
    final muted = Colors.white.withValues(alpha: 0.6);
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (widget.headers.isNotEmpty)
          SizedBox(
            width: cell * widget.columns,
            child: Row(
              children: [
                for (final header in widget.headers)
                  SizedBox(
                    width: cell,
                    child: Text(header,
                        textAlign: TextAlign.center,
                        style: TextStyle(color: muted, fontSize: 11, fontWeight: FontWeight.w600)),
                  ),
              ],
            ),
          ),
        SizedBox(
          width: cell * widget.columns,
          height: cell * rows,
          child: RepaintBoundary(
            child: CustomPaint(painter: _DotsPainter(_pop, widget.counts, widget.columns, widget.blank, cell)),
          ),
        ),
      ],
    );
  }
}

class _DotsPainter extends CustomPainter {
  final Animation<double> pop;
  final List<int> counts;
  final int columns;
  final int blank;
  final double cell;

  _DotsPainter(this.pop, this.counts, this.columns, this.blank, this.cell) : super(repaint: pop);

  @override
  void paint(Canvas canvas, Size size) {
    final most = counts.fold(1, math.max);
    final busiest = counts.indexOf(most);
    final dot = Paint();
    final ring = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5
      ..color = Colors.white;
    for (var i = 0; i < counts.length; i++) {
      final place = blank + i;
      final center = Offset((place % columns + 0.5) * cell, (place ~/ columns + 0.5) * cell);
      final start = i / counts.length * 0.6;
      final t = Curves.easeOutBack.transform(((pop.value - start) / 0.4).clamp(0.0, 1.0));
      if (counts[i] == 0) {
        dot.color = Colors.white.withValues(alpha: 0.16);
        canvas.drawCircle(center, 2.5 * t, dot);
        continue;
      }
      final radius = (3.5 + 9 * math.sqrt(counts[i] / most)) * t;
      dot.color = Colors.white.withValues(alpha: 0.35 + 0.6 * counts[i] / most);
      canvas.drawCircle(center, radius, dot);
      if (i == busiest) canvas.drawCircle(center, cell / 2 - 1, ring..color = Colors.white.withValues(alpha: t));
    }
  }

  @override
  bool shouldRepaint(_DotsPainter old) => old.counts != counts;
}


/// One place on a podium or below it
class PodiumEntry {
  final String title;
  final String subtitle;
  final String value;
  final Widget Function(double size) picture;
  final VoidCallback onTap;

  const PodiumEntry(
      {required this.title, required this.subtitle, required this.value, required this.picture, required this.onTap});
}

/// The top three on steps, the first in the middle and highest with a crown, rising one after another from the
/// third; the fourth and fifth come in below
class Podium extends StatefulWidget {
  final List<PodiumEntry> entries;

  const Podium({super.key, required this.entries});

  @override
  State<Podium> createState() => _PodiumState();
}

class _PodiumState extends State<Podium> with SingleTickerProviderStateMixin {
  late final _rise = AnimationController(vsync: this, duration: const Duration(milliseconds: 1700))..forward();

  @override
  void dispose() {
    _rise.dispose();
    super.dispose();
  }

  Animation<double> _part(double start, double end, Curve curve) =>
      CurvedAnimation(parent: _rise, curve: Interval(start, end, curve: curve));

  Widget _step(BuildContext context, int rank) {
    final entry = widget.entries[rank];
    final first = rank == 0;
    // The third rises first and the first last
    final start = const [0.3, 0.15, 0.0][rank];
    final size = first ? 112.0 : 82.0;
    final height = const [120.0, 86.0, 64.0][rank];
    final muted = Colors.white.withValues(alpha: 0.72);
    return Expanded(
      child: GestureDetector(
        onTap: entry.onTap,
        behavior: HitTestBehavior.opaque,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            FadeTransition(
              opacity: _part(start + 0.25, start + 0.5, Curves.easeOut),
              child: SlideTransition(
                position: Tween(begin: const Offset(0, -0.6), end: Offset.zero)
                    .animate(_part(start + 0.25, start + 0.6, Curves.easeOutBack)),
                child: Column(
                  children: [
                    if (first) const Text('👑', style: TextStyle(fontSize: 26)),
                    Container(
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        boxShadow: [
                          if (first) BoxShadow(color: Colors.white.withValues(alpha: 0.35), blurRadius: 28),
                        ],
                      ),
                      child: RepaintBoundary(child: entry.picture(size)),
                    ),
                    const SizedBox(height: 8),
                    Text(entry.title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        textAlign: TextAlign.center,
                        style: TextStyle(fontWeight: FontWeight.w700, fontSize: first ? 15 : 13, height: 1.15)),
                    if (entry.subtitle.isNotEmpty)
                      Text(entry.subtitle,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          textAlign: TextAlign.center,
                          style: TextStyle(color: muted, fontSize: 12)),
                    const SizedBox(height: 8),
                  ],
                ),
              ),
            ),
            ScaleTransition(
              alignment: Alignment.bottomCenter,
              scale: _part(start, start + 0.45, Curves.easeOutCubic),
              child: Container(
                height: height,
                margin: const EdgeInsets.symmetric(horizontal: 4),
                decoration: BoxDecoration(
                  borderRadius: const BorderRadius.vertical(top: Radius.circular(14)),
                  border: Border.all(color: Colors.white.withValues(alpha: first ? 0.55 : 0.3)),
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [
                      Colors.white.withValues(alpha: first ? 0.34 : 0.2),
                      Colors.white.withValues(alpha: 0.04),
                    ],
                  ),
                ),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text('${rank + 1}',
                        style: TextStyle(fontSize: first ? 40 : 30, fontWeight: FontWeight.w800, height: 1)),
                    Text(entry.value, style: TextStyle(color: muted, fontSize: 12, fontWeight: FontWeight.w600)),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final entries = widget.entries;
    final muted = Colors.white.withValues(alpha: 0.72);
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            if (entries.length > 1) _step(context, 1) else const Spacer(),
            _step(context, 0),
            if (entries.length > 2) _step(context, 2) else const Spacer(),
          ],
        ),
        Container(height: 1, color: Colors.white.withValues(alpha: 0.3)),
        const SizedBox(height: 12),
        for (var rank = 3; rank < entries.length; rank++)
          FadeTransition(
            opacity: _part(0.65 + (rank - 3) * 0.1, 0.9 + (rank - 3) * 0.1, Curves.easeOut),
            child: SlideTransition(
              position: Tween(begin: const Offset(0, 0.4), end: Offset.zero)
                  .animate(_part(0.65 + (rank - 3) * 0.1, 0.95 + (rank - 3) * 0.05, Curves.easeOutCubic)),
              child: InkWell(
                onTap: entries[rank].onTap,
                borderRadius: BorderRadius.circular(12),
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 4),
                  child: Row(
                    children: [
                      SizedBox(
                        width: 28,
                        child: Text('${rank + 1}', style: TextStyle(color: muted, fontWeight: FontWeight.w800)),
                      ),
                      entries[rank].picture(42),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(entries[rank].title,
                                maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
                            if (entries[rank].subtitle.isNotEmpty)
                              Text(entries[rank].subtitle,
                                  maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(color: muted, fontSize: 12)),
                          ],
                        ),
                      ),
                      Text(entries[rank].value, style: TextStyle(color: muted, fontWeight: FontWeight.w600)),
                    ],
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }
}

/// A genre's family, by words in its name, for its sigil and its message to the listener; the desktop app's
/// api/wrapped.py genre_family follows the same list
String genreFamily(String genre) {
  final name = genre.toLowerCase();
  bool has(List<String> words) => words.any(name.contains);
  if (has(['turkish', 'türk', 'anatolian', 'arabesk'])) return 'turkish';
  if (has(['metal', 'core', 'djent', 'grind'])) return 'metal';
  if (has(['hip hop', 'hip-hop', 'rap', 'trap', 'drill'])) return 'hiphop';
  if (has(['rock', 'grunge', 'punk', 'emo', 'alternative', 'indie'])) return 'rock';
  if (has(['electro', 'house', 'techno', 'edm', 'trance', 'dubstep', 'synth', 'dance', 'drum and bass'])) {
    return 'electronic';
  }
  if (has(['pop'])) return 'pop';
  if (has(['jazz', 'blues', 'soul', 'funk', 'r&b'])) return 'jazz';
  if (has(['classical', 'soundtrack', 'ambient', 'lo-fi', 'lofi', 'piano', 'score'])) return 'calm';
  if (has(['folk', 'country', 'acoustic', 'singer-songwriter'])) return 'folk';
  if (has(['latin', 'reggaeton', 'salsa', 'bachata'])) return 'latin';
  return 'other';
}

/// Pairs of genres with a word of their own, whichever of the two is bigger
const _genrePairs = {
  'metalcore|nu metal': 'metalcore_numetal',
  'metalcore|post-hardcore': 'metalcore_posthardcore',
  'alternative rock|nu metal': 'numetal_altrock',
  'alternative rock|post-grunge': 'altrock_postgrunge',
  'hard rock|heavy metal': 'hardrock_heavymetal',
  'hip hop|trap': 'hiphop_trap',
};

/// Pairs of families with a word of their own (in alphabetical order)
const _familyPairs = {
  'metal|rock', 'electronic|metal', 'metal|pop', 'hiphop|metal', 'pop|rock', 'electronic|rock', 'hiphop|rock',
  'folk|rock', 'electronic|pop', 'hiphop|pop', 'electronic|hiphop', 'hiphop|jazz', 'rock|turkish', 'pop|turkish',
  'metal|metal', 'rock|rock',
};

/// The text key of the word to the listener of [first] and [second], the two biggest genres: one for the pair when
/// there is, else for the first genre's family
String genreMessage(String first, String? second) {
  if (second != null) {
    final names = [first.toLowerCase(), second.toLowerCase()]..sort();
    if (_genrePairs[names.join('|')] case final pair?) return 'wrapped.genre.combo.$pair';
    final families = [genreFamily(first), genreFamily(second)]..sort();
    final key = families.join('|');
    if (_familyPairs.contains(key)) return 'wrapped.genre.combo.${families.join('_')}';
  }
  return 'wrapped.genre.say.${genreFamily(first)}';
}

/// A number from 0 to 1 that looks random but is the same for the same [i] and [seed], on the phone and the
/// desktop alike
double _noise(int i, int seed) {
  final v = math.sin(i * 12.9898 + seed * 78.233) * 43758.5453;
  return v - v.floorToDouble();
}

/// A ring drawn in the manner of a genre family round its middle: sharp spikes for metal, thick bars for rock,
/// stepped bars for electronic music, bouncing dots for pop, soft waves for jazz and calm music, an eight pointed
/// star for Turkish music
class _SigilPainter extends CustomPainter {
  final String family;

  const _SigilPainter(this.family);

  @override
  void paint(Canvas canvas, Size size) {
    final c = size.center(Offset.zero);
    final inner = size.width * 0.37;
    final reach = size.width * 0.12;
    final white = Paint()..color = Colors.white;
    final line = Paint()
      ..color = Colors.white
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    Offset at(double angle, double radius) => c + Offset(math.cos(angle), math.sin(angle)) * radius;
    final seed = family.length;
    switch (family) {
      case 'metal':
        // Jagged spikes of every length
        const count = 44;
        final path = Path();
        for (var i = 0; i < count; i++) {
          final a = i / count * 2 * math.pi;
          final half = math.pi / count * 0.8;
          final tip = inner + reach * (0.35 + 0.65 * _noise(i, seed));
          path
            ..moveTo(at(a - half, inner).dx, at(a - half, inner).dy)
            ..lineTo(at(a, tip).dx, at(a, tip).dy)
            ..lineTo(at(a + half, inner).dx, at(a + half, inner).dy)
            ..close();
        }
        canvas.drawPath(path, white);
      case 'rock':
        const count = 26;
        line.strokeWidth = size.width * 0.03;
        for (var i = 0; i < count; i++) {
          final a = i / count * 2 * math.pi;
          canvas.drawLine(at(a, inner + 3), at(a, inner + 3 + reach * (0.3 + 0.7 * _noise(i, seed))), line);
        }
      case 'electronic':
        // Bars that climb in steps, with a dotted ring inside
        const count = 36;
        line
          ..strokeWidth = size.width * 0.022
          ..strokeCap = StrokeCap.butt;
        for (var i = 0; i < count; i++) {
          final a = i / count * 2 * math.pi;
          final steps = 1 + (_noise(i, seed) * 4).floor();
          canvas.drawLine(at(a, inner + 4), at(a, inner + 4 + reach * steps / 4), line);
        }
        for (var i = 0; i < 72; i++) {
          canvas.drawCircle(at(i / 72 * 2 * math.pi, inner - 1), 1, white);
        }
      case 'hiphop':
        const count = 14;
        line.strokeWidth = size.width * 0.06;
        for (var i = 0; i < count; i++) {
          final a = i / count * 2 * math.pi;
          canvas.drawLine(at(a, inner + 6), at(a, inner + 6 + reach * (0.2 + 0.5 * _noise(i, seed))), line);
        }
        line.strokeWidth = 2;
        canvas.drawCircle(c, inner + 1, line);
        canvas.drawCircle(c, inner + reach + 8, line..color = Colors.white.withValues(alpha: 0.5));
      case 'pop':
        const count = 20;
        for (var i = 0; i < count; i++) {
          final a = i / count * 2 * math.pi;
          final r = size.width * (0.015 + 0.03 * _noise(i, seed));
          canvas.drawCircle(at(a, inner + reach * 0.55 + 6 * math.sin(i * 1.7)), r, white);
        }
      case 'jazz' || 'calm' || 'latin':
        // Waves round the ring, softer for calm music
        final waves = family == 'calm' ? 6 : family == 'latin' ? 14 : 9;
        for (final (k, alpha) in [(0, 1.0), (1, 0.45)]) {
          final path = Path();
          for (var s = 0; s <= 240; s++) {
            final a = s / 240 * 2 * math.pi;
            final r = inner + reach * (0.45 + 0.35 * math.sin(a * waves + k * 1.2)) + k * 6;
            final p = at(a, r);
            s == 0 ? path.moveTo(p.dx, p.dy) : path.lineTo(p.dx, p.dy);
          }
          canvas.drawPath(
              path,
              line
                ..strokeWidth = 2.5
                ..color = Colors.white.withValues(alpha: alpha));
        }
      case 'turkish':
        // An eight pointed star of two squares, with a ring of small dots
        line.strokeWidth = 2.5;
        for (final turn in [0.0, math.pi / 4]) {
          final path = Path();
          for (var i = 0; i < 4; i++) {
            final p = at(turn + i * math.pi / 2, inner + reach * 0.95);
            i == 0 ? path.moveTo(p.dx, p.dy) : path.lineTo(p.dx, p.dy);
          }
          canvas.drawPath(path..close(), line);
        }
        for (var i = 0; i < 32; i++) {
          canvas.drawCircle(at(i / 32 * 2 * math.pi, inner + reach + 6), 1.6, white);
        }
      case 'folk':
        const count = 12;
        for (var i = 0; i < count; i++) {
          final a = i / count * 2 * math.pi;
          canvas.save();
          canvas.translate(at(a, inner + reach * 0.55).dx, at(a, inner + reach * 0.55).dy);
          canvas.rotate(a);
          canvas.drawOval(Rect.fromCenter(center: Offset.zero, width: reach * 0.95, height: reach * 0.38), white);
          canvas.restore();
        }
      default:
        // The grooves of a record
        line.strokeWidth = 1.5;
        for (var k = 0; k < 5; k++) {
          canvas.drawCircle(c, inner + 4 + k * reach / 5, line..color = Colors.white.withValues(alpha: 1 - k * 0.17));
        }
    }
  }

  @override
  bool shouldRepaint(_SigilPainter old) => old.family != family;
}

/// A genre's sigil round [child] (its top artist's photo), turning slowly and beating, faster for heavier music;
/// still when [still]
class GenreSigil extends StatefulWidget {
  final String family;
  final double size;
  final Widget? child;
  final bool still;

  const GenreSigil({super.key, required this.family, this.size = 200, this.child, this.still = false});

  @override
  State<GenreSigil> createState() => _GenreSigilState();
}

class _GenreSigilState extends State<GenreSigil> with TickerProviderStateMixin {
  late final _turn = AnimationController(vsync: this, duration: const Duration(seconds: 40));
  late final _beat = AnimationController(
      vsync: this,
      duration: Duration(milliseconds: switch (widget.family) {
        'metal' => 520,
        'electronic' || 'hiphop' => 700,
        'rock' || 'pop' || 'latin' => 900,
        _ => 1800,
      }));

  @override
  void initState() {
    super.initState();
    if (!widget.still) {
      _turn.repeat();
      _beat.repeat(reverse: true);
    }
  }

  @override
  void dispose() {
    _turn.dispose();
    _beat.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final size = widget.size;
    final ring = RepaintBoundary(
      child: SizedBox.square(dimension: size, child: CustomPaint(painter: _SigilPainter(widget.family))),
    );
    return SizedBox.square(
      dimension: size,
      child: Stack(
        alignment: Alignment.center,
        children: [
          if (widget.still)
            ring
          else
            ScaleTransition(
              scale: Tween(begin: 1.0, end: 1.05).animate(CurvedAnimation(parent: _beat, curve: Curves.easeInOut)),
              child: RotationTransition(turns: _turn, child: ring),
            ),
          if (widget.child != null) ClipOval(child: SizedBox.square(dimension: size * 0.66, child: widget.child)),
        ],
      ),
    );
  }
}

/// The biggest genre in the spotlight: its sigil round its top artist, its name, its other artists, a word to its
/// listener, and the next genres below it with bars that fill once
class GenreSpotlight extends StatefulWidget {
  final String name;
  final String share;
  final String message;
  final List<Widget Function(double size)> photos;

  /// The next genres: name, share in percent and its text
  final List<(String, int, String)> others;

  const GenreSpotlight(
      {super.key,
      required this.name,
      required this.share,
      required this.message,
      required this.photos,
      required this.others});

  @override
  State<GenreSpotlight> createState() => _GenreSpotlightState();
}

class _GenreSpotlightState extends State<GenreSpotlight> with SingleTickerProviderStateMixin {
  late final _in = AnimationController(vsync: this, duration: const Duration(milliseconds: 1800))..forward();

  @override
  void dispose() {
    _in.dispose();
    super.dispose();
  }

  Animation<double> _part(double start, double end, Curve curve) =>
      CurvedAnimation(parent: _in, curve: Interval(start.clamp(0.0, 1.0), end.clamp(0.0, 1.0), curve: curve));

  @override
  Widget build(BuildContext context) {
    final muted = Colors.white.withValues(alpha: 0.72);
    final photos = widget.photos;
    final rest = photos.skip(1).take(3).toList();
    const photo = 48.0;
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        ScaleTransition(
          scale: _part(0, 0.45, Curves.elasticOut),
          child: GenreSigil(
            family: genreFamily(widget.name),
            size: 210,
            child: photos.isEmpty ? null : photos.first(139),
          ),
        ),
        const SizedBox(height: 10),
        FadeTransition(
          opacity: _part(0.15, 0.45, Curves.easeOut),
          child: Text(widget.name,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w800, height: 1.05)),
        ),
        FadeTransition(
          opacity: _part(0.2, 0.5, Curves.easeOut),
          child: Text(widget.share, style: TextStyle(color: muted, fontWeight: FontWeight.w600, fontSize: 15)),
        ),
        if (rest.isNotEmpty) ...[
          const SizedBox(height: 12),
          // Its other artists side by side, overlapping a little, coming in one after another
          SizedBox(
            height: photo,
            width: photo + (rest.length - 1) * (photo - 12),
            child: Stack(
              children: [
                for (final (index, picture) in rest.indexed)
                  Positioned(
                    left: index * (photo - 12),
                    child: ScaleTransition(
                      scale: _part(0.3 + index * 0.08, 0.6 + index * 0.08, Curves.easeOutBack),
                      child: Container(
                        padding: const EdgeInsets.all(2),
                        decoration: BoxDecoration(shape: BoxShape.circle, color: Colors.white.withValues(alpha: 0.85)),
                        child: picture(photo - 4),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ],
        const SizedBox(height: 16),
        FadeTransition(
          opacity: _part(0.45, 0.7, Curves.easeOut),
          child: SlideTransition(
            position:
                Tween(begin: const Offset(0, 0.3), end: Offset.zero).animate(_part(0.45, 0.75, Curves.easeOutCubic)),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: Colors.white.withValues(alpha: 0.22)),
              ),
              child: Text('“${widget.message}”',
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, fontStyle: FontStyle.italic)),
            ),
          ),
        ),
        const SizedBox(height: 18),
        for (final (index, (name, percent, text)) in widget.others.indexed)
          FadeTransition(
            opacity: _part(0.6 + index * 0.1, 0.85 + index * 0.1, Curves.easeOut),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 5),
              child: Row(
                children: [
                  GenreSigil(family: genreFamily(name), size: 34, still: true),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(name,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(fontWeight: FontWeight.w600)),
                            ),
                            Text(text, style: TextStyle(color: muted, fontWeight: FontWeight.w600)),
                          ],
                        ),
                        const SizedBox(height: 5),
                        // The bar fills once (a small repaint, only while it grows)
                        Container(
                          height: 6,
                          clipBehavior: Clip.antiAlias,
                          decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.18), borderRadius: BorderRadius.circular(3)),
                          alignment: Alignment.centerLeft,
                          child: AnimatedBuilder(
                            animation: _in,
                            builder: (context, _) => FractionallySizedBox(
                              widthFactor: (percent / 100).clamp(0.0, 1.0) *
                                  Curves.easeOutCubic
                                      .transform(((_in.value - 0.65 - index * 0.1) / 0.3).clamp(0.0, 1.0)),
                              child: const ColoredBox(color: Colors.white),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}
