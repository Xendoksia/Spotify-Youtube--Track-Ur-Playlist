/// The colors of a picture: the hue its vivid parts share most and a second one, as the desktop app's artwork.mood, in OKLCH so the
/// lightness can be set per theme.
library;

import 'dart:async';
import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

class Mood {
  final double hue;
  final double chroma;

  /// The picture's second color: another hue, or its greys as a faintly tinted grey, or null (the first is then
  /// turned a little), as the desktop app's artwork._colors
  final double? hue2;
  final double? chroma2;

  /// Extra lightness for yellows, which look like mustard and mud at the others' lightness
  final double lift;

  const Mood(this.hue, this.chroma, {this.hue2, this.chroma2, this.lift = 0});

  double _lightness(Brightness brightness) => (brightness == Brightness.dark ? 0.56 : 0.5) + lift;

  /// The color at the theme's lightness, darker on light pages so white text stays readable on it
  Color color(Brightness brightness) => oklchColor(_lightness(brightness), chroma, hue);

  /// The second color, a little lighter, for the two-tone curves
  Color color2(Brightness brightness) =>
      oklchColor(_lightness(brightness) + 0.1, chroma2 ?? chroma, hue2 ?? (hue + 55) % 360);
}

const _bins = 24;
// A second color: a hue at least this many bins from the first with this share of its weight, else the greys and
// whites when they cover this much of the picture
const _secondApart = 3;
const _secondShare = 0.15;
const _neutralShare = 0.2;
const _neutralChroma = 0.015;
// A mostly grey picture still lends its few colored pixels (a logo, a title) to the curves from this share
const _accentShare = 0.01;
const _moodShare = 0.06;

final _analyses = <String, Future<_Analysis?>>{};

/// The picture's vivid pixels per hue (weight, sin and cos of the hue, highest chroma, pixels), its light enough grey
/// and white pixels and all its pixels
class _Analysis {
  final List<List<double>> bins;
  final int neutral;
  final int total;

  _Analysis(this.bins, this.neutral, this.total);

  factory _Analysis.of(List<(int, int, int)> pixels) {
    final bins = List.generate(_bins, (_) => [0.0, 0.0, 0.0, 0.0, 0.0]);
    var neutral = 0;
    for (final (r, g, b) in pixels) {
      final (lightness, chroma, hue) = oklch(r, g, b);
      // Near black, white or grey pixels say little about the picture's color
      if (chroma < 0.04 || lightness <= 0.2 || lightness >= 0.92) {
        // Greys and whites can still be its second color, near black would vanish on the dark page
        if (lightness > 0.35) neutral++;
        continue;
      }
      final slot = bins[(hue / 360 * _bins).floor() % _bins];
      slot[0] += chroma;
      slot[1] += chroma * math.sin(hue * math.pi / 180);
      slot[2] += chroma * math.cos(hue * math.pi / 180);
      slot[3] = math.max(slot[3], chroma);
      slot[4] += 1;
    }
    return _Analysis(bins, neutral, pixels.length);
  }

  double _around(int i) => [-1, 0, 1].fold(0.0, (sum, d) => sum + bins[(i + d) % _bins][0]);

  List<List<double>> _group(int i) => [
    for (final d in [-1, 0, 1]) bins[(i + d) % _bins],
  ];

  static double _hueOf(List<List<double>> group) =>
      (math.atan2(group.fold(0.0, (sum, s) => sum + s[1]), group.fold(0.0, (sum, s) => sum + s[2])) * 180 / math.pi) %
      360;

  static double _chromaOf(List<List<double>> group) => math.min(0.16, group.map((slot) => slot[3]).reduce(math.max));

  /// The colors, or null when the first covers no more than [leastShare] of the picture
  Mood? colors(double leastShare) {
    // A hue and its two neighbours together, so a color split over two bins still wins
    var best = 0;
    for (var i = 1; i < _bins; i++) {
      if (_around(i) > _around(best)) best = i;
    }
    final group = _group(best);
    final count = group.fold(0.0, (sum, slot) => sum + slot[4]);
    if (total == 0 || count / total <= leastShare) return null;
    final hue = _hueOf(group);
    int? second;
    for (var i = 0; i < _bins; i++) {
      final apart = math.min((i - best) % _bins, (best - i) % _bins);
      if (apart >= _secondApart && (second == null || _around(i) > _around(second))) second = i;
    }
    double? hue2, chroma2;
    if (second != null && _around(second) >= _around(best) * _secondShare) {
      hue2 = _hueOf(_group(second));
      chroma2 = _chromaOf(_group(second));
    } else if (neutral / total >= _neutralShare) {
      hue2 = hue;
      chroma2 = _neutralChroma;
    }
    return Mood(hue, _chromaOf(group), hue2: hue2, chroma2: chroma2, lift: _lift(hue));
  }
}

/// How much lighter a yellow or olive hue is shown than the others
double _lift(double hue) => 0.14 * math.max(0.0, 1 - (hue - 95).abs() / 55);

Future<_Analysis?> _analyse(String url) => _analyses[url] ??= () async {
  try {
    final provider = ResizeImage(CachedNetworkImageProvider(url), width: 40, height: 40);
    final done = Completer<ui.Image>();
    final stream = provider.resolve(ImageConfiguration.empty);
    late final ImageStreamListener listener;
    listener = ImageStreamListener(
      (info, _) {
        if (!done.isCompleted) done.complete(info.image.clone());
        stream.removeListener(listener);
      },
      onError: (error, _) {
        if (!done.isCompleted) done.completeError(error);
        stream.removeListener(listener);
      },
    );
    stream.addListener(listener);
    final image = await done.future.timeout(const Duration(seconds: 20));
    final bytes = await image.toByteData(format: ui.ImageByteFormat.rawRgba);
    image.dispose();
    if (bytes == null) return null;
    return _Analysis.of([
      for (var i = 0; i + 3 < bytes.lengthInBytes; i += 4)
        (bytes.getUint8(i), bytes.getUint8(i + 1), bytes.getUint8(i + 2)),
    ]);
  } catch (_) {
    _analyses.remove(url);
    return null;
  }
}();

/// The mood of the picture at [url], read from a small copy of the cached image
Future<Mood?> moodOf(String url) async => (await _analyse(url))?.colors(_moodShare);

/// The two colors of a page's curves: as [moodOf], but a mostly grey picture's few colored pixels count, with its
/// greys as the second color. Null for a picture without any color
Future<Mood?> paletteOf(String url) async => (await _analyse(url))?.colors(_accentShare);

/// The most common vivid hue of the pixels and their second color, or null for a grey picture
Mood? moodOfPixels(List<(int, int, int)> pixels) => _Analysis.of(pixels).colors(_moodShare);

/// The curves' colors of the pixels, as [paletteOf]
Mood? paletteOfPixels(List<(int, int, int)> pixels) => _Analysis.of(pixels).colors(_accentShare);

double _linear(int c) {
  final v = c / 255;
  return v <= 0.04045 ? v / 12.92 : math.pow((v + 0.055) / 1.055, 2.4).toDouble();
}

double _cbrt(double v) => v < 0 ? -math.pow(-v, 1 / 3).toDouble() : math.pow(v, 1 / 3).toDouble();

/// sRGB to OKLCH: (lightness, chroma, hue in degrees)
(double, double, double) oklch(int red, int green, int blue) {
  final r = _linear(red), g = _linear(green), b = _linear(blue);
  final l = _cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  final m = _cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  final s = _cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  final lightness = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s;
  final a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s;
  final bb = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s;
  return (lightness, math.sqrt(a * a + bb * bb), (math.atan2(bb, a) * 180 / math.pi) % 360);
}

/// OKLCH to an sRGB color; the chroma is lowered until the color fits in sRGB
Color oklchColor(double lightness, double chroma, double hue) {
  for (var c = chroma; ; c -= 0.005) {
    final a = math.max(c, 0) * math.cos(hue * math.pi / 180);
    final b = math.max(c, 0) * math.sin(hue * math.pi / 180);
    final l = math.pow(lightness + 0.3963377774 * a + 0.2158037573 * b, 3);
    final m = math.pow(lightness - 0.1055613458 * a - 0.0638541728 * b, 3);
    final s = math.pow(lightness - 0.0894841775 * a - 1.2914855480 * b, 3);
    final rgb = [
      4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
      -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
      -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    ];
    if (c <= 0 || rgb.every((v) => v >= -0.0001 && v <= 1.0001)) {
      int channel(double v) {
        final x = v.clamp(0.0, 1.0);
        final encoded = x <= 0.0031308 ? 12.92 * x : 1.055 * math.pow(x, 1 / 2.4) - 0.055;
        return (encoded * 255).round().clamp(0, 255);
      }

      return Color.fromARGB(255, channel(rgb[0]), channel(rgb[1]), channel(rgb[2]));
    }
  }
}

/// The color of the period's number one cover, for the statistics' accents; null keeps the usual ones
class MoodColor extends InheritedWidget {
  final Color? color;

  const MoodColor({super.key, required this.color, required super.child});

  static Color? of(BuildContext context) => context.dependOnInheritedWidgetOfExactType<MoodColor>()?.color;

  @override
  bool updateShouldNotify(MoodColor old) => old.color != color;
}

/// A soft wash of [mood]'s color from the top of a page, which also gives the page its accents (MoodColor); without
/// a mood the page stays plain. A new mood repaints only the wash and rebuilds the accents once, at once: the page
/// under it is left alone, and nothing page-sized animates (a gliding wash and rebuilding the statistics during a
/// period's slide made it stutter, as on the desktop app).
class MoodWash extends StatelessWidget {
  final ValueListenable<Mood?> mood;
  final Widget child;

  /// How far down the wash reaches, as a share of the page
  final double reach;

  const MoodWash({super.key, required this.mood, required this.child, this.reach = 0.6});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final dark = theme.brightness == Brightness.dark;
    final background = theme.colorScheme.surface;
    return ValueListenableBuilder<Mood?>(
      valueListenable: mood,
      child: RepaintBoundary(child: child),
      builder: (context, mood, child) {
        final color = mood?.color(theme.brightness);
        return MoodColor(
          color: color,
          child: DecoratedBox(
            decoration: BoxDecoration(
              // Pages over it are see-through, so without a mood it still paints the plain background
              color: color == null ? background : null,
              gradient: color == null
                  ? null
                  : LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      stops: [0, reach],
                      colors: [Color.lerp(background, color, dark ? 0.15 : 0.12)!, background],
                    ),
            ),
            child: child,
          ),
        );
      },
    );
  }
}
