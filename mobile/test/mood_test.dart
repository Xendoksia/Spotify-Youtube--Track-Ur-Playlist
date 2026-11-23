import 'package:flutter_test/flutter_test.dart';
import 'package:playlist_tracker/data/mood.dart';

void main() {
  test('a mostly red picture is red, a grey one has no color', () {
    final red = moodOfPixels([for (var i = 0; i < 90; i++) (200, 30, 40), for (var i = 0; i < 10; i++) (128, 128, 128)]);
    expect(red, isNotNull);
    expect(red!.hue, inInclusiveRange(15, 35));
    expect(red.chroma, lessThanOrEqualTo(0.16));
    expect(moodOfPixels([for (var i = 0; i < 100; i++) (120, 122, 125)]), isNull);
  });

  test("a picture's second color is another hue, else its greys", () {
    final two = moodOfPixels([for (var i = 0; i < 60; i++) (200, 30, 40), for (var i = 0; i < 40; i++) (30, 60, 200)]);
    expect(two!.hue2, inInclusiveRange(240, 290));
    final grey = moodOfPixels([for (var i = 0; i < 70; i++) (200, 30, 40), for (var i = 0; i < 30; i++) (180, 180, 180)]);
    expect(grey!.chroma2, lessThan(0.02));
  });

  test('a grey picture with a small colored logo colors only the curves', () {
    final pixels = [for (var i = 0; i < 97; i++) (150, 150, 150), for (var i = 0; i < 3; i++) (60, 160, 60)];
    expect(moodOfPixels(pixels), isNull);
    final curves = paletteOfPixels(pixels);
    expect(curves!.hue, inInclusiveRange(120, 160));
    expect(curves.chroma2, lessThan(0.02));
  });

  test('a color goes to OKLCH and back', () {
    final (lightness, chroma, hue) = oklch(30, 120, 220);
    final back = oklchColor(lightness, chroma, hue);
    expect((back.r * 255).round(), closeTo(30, 2));
    expect((back.g * 255).round(), closeTo(120, 2));
    expect((back.b * 255).round(), closeTo(220, 2));
  });
}
