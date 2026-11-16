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

  test('a color goes to OKLCH and back', () {
    final (lightness, chroma, hue) = oklch(30, 120, 220);
    final back = oklchColor(lightness, chroma, hue);
    expect((back.r * 255).round(), closeTo(30, 2));
    expect((back.g * 255).round(), closeTo(120, 2));
    expect((back.b * 255).round(), closeTo(220, 2));
  });
}
