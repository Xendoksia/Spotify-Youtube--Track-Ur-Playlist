/// The color of a picture: the hue its vivid parts share most, as the desktop app's artwork.mood, in OKLCH so the
/// lightness can be set per theme.
library;

import 'dart:async';
import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/widgets.dart';

class Mood {
  final double hue;
  final double chroma;

  const Mood(this.hue, this.chroma);

  /// The color at the theme's lightness, darker on light pages so white text stays readable on it
  Color color(Brightness brightness) => oklchColor(brightness == Brightness.dark ? 0.56 : 0.5, chroma, hue);
}

const _bins = 24;
final _moods = <String, Future<Mood?>>{};

/// The mood of the picture at [url], read from a small copy of the cached image
Future<Mood?> moodOf(String url) => _moods[url] ??= () async {
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
    return moodOfPixels([
      for (var i = 0; i + 3 < bytes.lengthInBytes; i += 4)
        (bytes.getUint8(i), bytes.getUint8(i + 1), bytes.getUint8(i + 2)),
    ]);
  } catch (_) {
    _moods.remove(url);
    return null;
  }
}();

/// The most common vivid hue of the pixels, or null for a grey picture
Mood? moodOfPixels(List<(int, int, int)> pixels) {
  // Per hue: weight, sin and cos of the hue, highest chroma, pixels
  final bins = List.generate(_bins, (_) => [0.0, 0.0, 0.0, 0.0, 0.0]);
  for (final (r, g, b) in pixels) {
    final (lightness, chroma, hue) = oklch(r, g, b);
    // Near black, white or grey pixels say little about the picture's color
    if (chroma < 0.04 || lightness <= 0.2 || lightness >= 0.92) continue;
    final slot = bins[(hue / 360 * _bins).floor() % _bins];
    slot[0] += chroma;
    slot[1] += chroma * math.sin(hue * math.pi / 180);
    slot[2] += chroma * math.cos(hue * math.pi / 180);
    slot[3] = math.max(slot[3], chroma);
    slot[4] += 1;
  }
  double around(int i) => [-1, 0, 1].fold(0.0, (sum, d) => sum + bins[(i + d) % _bins][0]);
  // A hue and its two neighbours together, so a color split over two bins still wins
  var best = 0;
  for (var i = 1; i < _bins; i++) {
    if (around(i) > around(best)) best = i;
  }
  final group = [
    for (final d in [-1, 0, 1]) bins[(best + d) % _bins],
  ];
  final count = group.fold(0.0, (sum, slot) => sum + slot[4]);
  // A few colored pixels in a grey picture are not its color
  if (pixels.isEmpty || count / pixels.length <= 0.06) return null;
  final sin = group.fold(0.0, (sum, slot) => sum + slot[1]);
  final cos = group.fold(0.0, (sum, slot) => sum + slot[2]);
  final hue = (math.atan2(sin, cos) * 180 / math.pi) % 360;
  final chroma = math.min(0.16, group.map((slot) => slot[3]).reduce(math.max));
  return Mood(hue, chroma);
}

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
