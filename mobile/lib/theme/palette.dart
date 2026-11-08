/// The desktop app's colors (playlist_tracker/ui/theme.py), so both look like one app.
library;

import 'package:flutter/material.dart';

import '../data/models.dart';

class Palette extends ThemeExtension<Palette> {
  final Color muted;
  final Color border;
  final Color chart;
  final Color added;
  final Color removed;
  final Color unplayable;
  final Color playable;
  final Color initial;

  const Palette({
    required this.muted,
    required this.border,
    required this.chart,
    required this.added,
    required this.removed,
    required this.unplayable,
    required this.playable,
    required this.initial,
  });

  static const light = Palette(
    muted: Color(0xFF555D6A),
    border: Color(0xFFC3C9D2),
    chart: Color(0xFF14853F),
    added: Color(0xFF14702F),
    removed: Color(0xFFB42222),
    unplayable: Color(0xFF8A4F00),
    playable: Color(0xFF1258AD),
    initial: Color(0xFF585F6A),
  );

  static const dark = Palette(
    muted: Color(0xFF9AA1AB),
    border: Color(0xFF30343C),
    chart: Color(0xFF2EA043),
    added: Color(0xFF3FB950),
    removed: Color(0xFFF85149),
    unplayable: Color(0xFFD29922),
    playable: Color(0xFF58A6FF),
    initial: Color(0xFF8B949E),
  );

  Color event(EventKind kind) => switch (kind) {
        EventKind.added => added,
        EventKind.removed => removed,
        EventKind.unplayable => unplayable,
        EventKind.playableAgain => playable,
        EventKind.initial => initial,
      };

  static Palette of(BuildContext context) => Theme.of(context).extension<Palette>()!;

  @override
  Palette copyWith() => this;

  @override
  Palette lerp(Palette? other, double t) => t < 0.5 || other == null ? this : other;
}

/// The services' accent colors (ui/services.py)
const serviceColors = {'spotify': Color(0xFF1AA34A), 'youtube': Color(0xFFE62117)};
const serviceNames = {'spotify': 'Spotify', 'youtube': 'YouTube'};

/// How long values take to move to new ones, as the desktop app's charts.Animation
const changeDuration = Duration(milliseconds: 450);
const changeCurve = Curves.easeOutCubic;

ThemeData buildTheme(Brightness brightness) {
  final dark = brightness == Brightness.dark;
  final background = dark ? const Color(0xFF16181D) : const Color(0xFFD3D8E0);
  final surface = dark ? const Color(0xFF1F2228) : const Color(0xFFE2E6EC);
  final scheme = ColorScheme.fromSeed(
    seedColor: dark ? const Color(0xFF4C8DFF) : const Color(0xFF1F5FD6),
    brightness: brightness,
  ).copyWith(
    primary: dark ? const Color(0xFF4C8DFF) : const Color(0xFF1F5FD6),
    surface: background,
    surfaceContainer: surface,
    surfaceContainerHighest: dark ? const Color(0xFF2A2E36) : const Color(0xFFD8DDE4),
    onSurface: dark ? const Color(0xFFE6E8EB) : const Color(0xFF1F2328),
  );
  final palette = dark ? Palette.dark : Palette.light;
  return ThemeData(
    colorScheme: scheme,
    scaffoldBackgroundColor: background,
    extensions: [palette],
    cardTheme: CardThemeData(
      color: surface,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: palette.border),
      ),
    ),
    navigationBarTheme: NavigationBarThemeData(backgroundColor: surface),
    appBarTheme: AppBarTheme(backgroundColor: background, scrolledUnderElevation: 0),
    pageTransitionsTheme: const PageTransitionsTheme(builders: {
      TargetPlatform.android: FadeForwardsPageTransitionsBuilder(),
    }),
  );
}
