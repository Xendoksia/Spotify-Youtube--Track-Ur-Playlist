/// The summary's stage: a backdrop in each slide's color with soft lights drifting over it, and the story bars
/// that fill while a slide shows.
library;

import 'dart:math' as math;
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import '../../data/mood.dart';
import '../../theme/palette.dart';

/// The hue a slide without a picture of its own takes: the month's color turned a little further each slide,
/// so the slides never look alike
double slideHue(double base, int index) => (base + index * 47) % 360;

/// The hue of the backdrop when the month has no colored cover: a deep violet
const defaultHue = 285.0;

/// The stage's colors for one hue, worked out once per hue (the drifting lights repaint every frame)
class _StageColors {
  final Color top;
  final Color bottom;
  final List<Color> lights;

  _StageColors(double hue)
      : top = oklchColor(0.42, 0.13, hue),
        bottom = oklchColor(0.2, 0.07, hue + 30),
        lights = [
          oklchColor(0.64, 0.17, hue + 50).withValues(alpha: 0.55),
          oklchColor(0.56, 0.16, hue - 60).withValues(alpha: 0.45),
          oklchColor(0.72, 0.12, hue + 150).withValues(alpha: 0.22),
        ];

  static final _cache = <int, _StageColors>{};

  /// Hues a degree apart look the same, so a glide between two slides computes at most a few dozen
  static _StageColors of(double hue) => _cache.putIfAbsent(hue.round() % 360, () => _StageColors(hue.roundToDouble()));
}

/// The backdrop glides to a new slide's hue the short way round the color wheel while its lights drift on
class StageBackdrop extends StatefulWidget {
  final double hue;

  const StageBackdrop({super.key, required this.hue});

  @override
  State<StageBackdrop> createState() => _StageBackdropState();
}

class _StageBackdropState extends State<StageBackdrop> with SingleTickerProviderStateMixin {
  late final _drift = AnimationController(vsync: this, duration: const Duration(seconds: 26))..repeat();

  /// The hue with whole turns added so that gliding to the next one takes the short way
  late double _target = widget.hue;

  @override
  void didUpdateWidget(StageBackdrop old) {
    super.didUpdateWidget(old);
    final turn = ((widget.hue - _target) % 360 + 540) % 360 - 180;
    _target += turn;
  }

  @override
  void dispose() {
    _drift.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => RepaintBoundary(
        child: TweenAnimationBuilder<double>(
          tween: Tween(end: _target),
          duration: const Duration(milliseconds: 700),
          curve: Curves.easeInOut,
          builder: (context, hue, _) => CustomPaint(
            painter: _BackdropPainter(_StageColors.of(hue % 360), _drift),
            size: Size.infinite,
          ),
        ),
      );
}

class _BackdropPainter extends CustomPainter {
  final _StageColors colors;
  final Animation<double> drift;

  _BackdropPainter(this.colors, this.drift) : super(repaint: drift);

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    canvas.drawRect(
        rect,
        Paint()
          ..shader = LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [colors.top, colors.bottom],
          ).createShader(rect));
    final turn = drift.value * 2 * math.pi;
    final radius = size.longestSide * 0.5;
    for (final (index, color) in colors.lights.indexed) {
      // Each light circles its own spot at its own pace
      final phase = index * 2.1;
      final speed = index == 1 ? -1 : 1;
      final center = Offset(
        size.width * (0.5 + 0.38 * math.sin(speed * turn + phase)),
        size.height * (0.45 + 0.3 * math.cos(speed * turn * (index + 1) / 2 + phase)),
      );
      canvas.drawCircle(
          center,
          radius,
          Paint()
            ..shader = RadialGradient(colors: [color, color.withValues(alpha: 0)])
                .createShader(Rect.fromCircle(center: center, radius: radius)));
    }
  }

  @override
  bool shouldRepaint(_BackdropPainter old) => old.colors != colors;
}

/// The bars over the slides, one per slide: those seen are full and the one showing fills with [progress]
class StoryBars extends StatelessWidget {
  final int count;
  final int index;
  final Animation<double> progress;

  const StoryBars({super.key, required this.count, required this.index, required this.progress});

  @override
  Widget build(BuildContext context) => RepaintBoundary(
        child: Row(
          children: [
            for (var i = 0; i < count; i++)
              Expanded(
                child: Container(
                  height: 3,
                  margin: const EdgeInsets.symmetric(horizontal: 2),
                  clipBehavior: Clip.antiAlias,
                  decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.28), borderRadius: BorderRadius.circular(2)),
                  child: i == index
                      ? AnimatedBuilder(
                          animation: progress,
                          builder: (context, _) => FractionallySizedBox(
                              alignment: Alignment.centerLeft,
                              widthFactor: progress.value,
                              child: const ColoredBox(color: Colors.white)),
                        )
                      : FractionallySizedBox(
                          alignment: Alignment.centerLeft,
                          widthFactor: i < index ? 1 : 0,
                          child: const ColoredBox(color: Colors.white)),
                ),
              ),
          ],
        ),
      );
}

/// The app's dark theme with white text and accents, for the slides on their colored stage
ThemeData stageTheme(ThemeData dark) {
  const white = Colors.white;
  return dark.copyWith(
    extensions: [
      Palette(
        muted: white.withValues(alpha: 0.72),
        border: white.withValues(alpha: 0.24),
        chart: white,
        added: white.withValues(alpha: 0.88),
        removed: Palette.dark.removed,
        unplayable: Palette.dark.unplayable,
        playable: Palette.dark.playable,
        initial: white.withValues(alpha: 0.6),
      ),
    ],
  );
}

/// A slide as a story picture (1080 x 1920) to share: the stage in the slide's hue with its lights held still, the
/// slide in the middle and the summary's name with the app's under it. A slide with a picture behind it ([fill],
/// the first one's wall of covers) covers the whole picture instead, darker under the names so they stay readable
Future<Uint8List?> storyImage(ui.Image slide, double hue, String title, {bool fill = false}) async {
  const size = Size(1080, 1920);
  final recorder = ui.PictureRecorder();
  final canvas = Canvas(recorder, Offset.zero & size);
  final colors = _StageColors.of(hue);
  final rect = Offset.zero & size;
  canvas.drawRect(
      rect,
      Paint()
        ..shader = LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [colors.top, colors.bottom])
            .createShader(rect));
  for (final (index, color) in colors.lights.indexed) {
    final center = Offset(size.width * const [0.2, 0.85, 0.55][index], size.height * const [0.15, 0.8, 0.45][index]);
    final radius = size.height * 0.5;
    canvas.drawCircle(
        center,
        radius,
        Paint()
          ..shader = RadialGradient(colors: [color, color.withValues(alpha: 0)])
              .createShader(Rect.fromCircle(center: center, radius: radius)));
  }
  // The slide as big as it fits between a margin and the footer, or over all of it, cut at the edges
  final area = fill ? rect : Rect.fromLTWH(48, 120, size.width - 96, size.height - 120 - 260);
  final scale = (fill ? math.max : math.min)(area.width / slide.width, area.height / slide.height);
  final drawn = Size(slide.width * scale, slide.height * scale);
  canvas.drawImageRect(
    slide,
    Rect.fromLTWH(0, 0, slide.width.toDouble(), slide.height.toDouble()),
    Rect.fromCenter(center: area.center, width: drawn.width, height: drawn.height),
    Paint()..filterQuality = FilterQuality.high,
  );
  if (fill) {
    final shade = Rect.fromLTWH(0, size.height - 420, size.width, 420);
    canvas.drawRect(
        shade,
        Paint()
          ..shader = LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [colors.bottom.withValues(alpha: 0), colors.bottom.withValues(alpha: 0.95)],
          ).createShader(shade));
  }
  var bottom = size.height - 110;
  for (final (text, style) in [
    ('Songlog', const TextStyle(color: Colors.white, fontSize: 40, fontWeight: FontWeight.w800)),
    (title, TextStyle(color: Colors.white.withValues(alpha: 0.75), fontSize: 32, fontWeight: FontWeight.w600)),
  ]) {
    final painter = TextPainter(text: TextSpan(text: text, style: style), textDirection: TextDirection.ltr)
      ..layout(maxWidth: size.width - 96);
    bottom -= painter.height;
    painter.paint(canvas, Offset((size.width - painter.width) / 2, bottom));
    bottom -= 10;
  }
  final image = await recorder.endRecording().toImage(size.width.toInt(), size.height.toInt());
  final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
  image.dispose();
  return bytes?.buffer.asUint8List();
}
