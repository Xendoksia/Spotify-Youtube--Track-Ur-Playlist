import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:playlist_tracker/data/models.dart';
import 'package:playlist_tracker/data/repository.dart';
import 'package:playlist_tracker/screens/listening/listening_screen.dart';
import 'package:playlist_tracker/screens/playlists/playlists_screen.dart';
import 'package:playlist_tracker/state/app_controller.dart';
import 'package:playlist_tracker/state/data_store.dart';
import 'package:playlist_tracker/theme/palette.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'stats_test.dart' show event, play;

/// The screens are drawn from a store filled by hand, without Supabase
Future<void> pump(WidgetTester tester, Widget Function(DataStore) screen, {String language = 'en'}) async {
  SharedPreferences.setMockInitialValues({'LANGUAGE': language});
  final controller = AppController(Repository());
  await controller.load();
  final now = DateTime.now();
  final store = DataStore(controller.repository)
    ..loaded = true
    ..plays = [
      play('Artist', 'First song', now.subtract(const Duration(hours: 1))),
      play('Artist', 'First song', now.subtract(const Duration(days: 1))),
      play('Other', 'Second song', now.subtract(const Duration(days: 2)), album: 'Record'),
    ]
    ..playlists = [TrackedPlaylist(service: 'spotify', playlistId: 'p1', name: 'Road trip')]
    ..events = [event(EventKind.removed, now)];
  await tester.pumpWidget(AppScope(
    controller: controller,
    child: MaterialApp(
      theme: buildTheme(Brightness.light),
      locale: Locale(language),
      supportedLocales: const [Locale('en'), Locale('tr')],
      localizationsDelegates: GlobalMaterialLocalizations.delegates,
      home: Scaffold(body: screen(store)),
    ),
  ));
  await tester.pumpAndSettle();
}

Future<void> noRefresh() async {}

void main() {
  setUpAll(() => initializeDateFormatting());

  testWidgets('listening shows the totals and the top tracks', (tester) async {
    await pump(tester, (store) => ListeningScreen(store: store, onRefresh: noRefresh));
    expect(find.text('Plays'), findsOneWidget);
    // The screen opens on the current week, which on a Monday holds only one of the plays: all time holds them all
    await tester.tap(find.text('All time'));
    await tester.pumpAndSettle();
    // Further down the page
    await tester.scrollUntilVisible(find.text('Top tracks'), 300, scrollable: find.byType(Scrollable).first);
    expect(find.text('First song'), findsWidgets);
  });

  testWidgets('all time has no arrows', (tester) async {
    await pump(tester, (store) => ListeningScreen(store: store, onRefresh: noRefresh));
    expect(find.byIcon(Icons.chevron_left), findsOneWidget);
    await tester.tap(find.text('All time'));
    await tester.pumpAndSettle();
    expect(find.byIcon(Icons.chevron_left), findsNothing);
  });

  testWidgets('playlists show their latest changes and open their history', (tester) async {
    await pump(tester, (store) => PlaylistsScreen(store: store, onRefresh: noRefresh), language: 'tr');
    expect(find.text('Road trip'), findsOneWidget);
    expect(find.text('1 silindi'), findsOneWidget);
    await tester.tap(find.text('Road trip'));
    await tester.pumpAndSettle();
    expect(find.text('Silindi'), findsOneWidget);
    expect(find.text('Song'), findsOneWidget);
  });
}
