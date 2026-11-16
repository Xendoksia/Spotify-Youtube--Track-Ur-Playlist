import 'dart:async';

import 'package:flutter/material.dart';

import '../l10n/strings.dart';
import '../data/now_playing.dart';
import '../state/app_controller.dart';
import '../state/data_store.dart';
import '../widgets/mini_player.dart';
import '../widgets/sliding.dart';
import 'account_screen.dart';
import 'listening/listening_screen.dart';
import 'playlists/playlists_screen.dart';

/// The logged-in app: listening, playlists and the account, along the bottom
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with SingleTickerProviderStateMixin {
  late final DataStore _store;
  final _nowPlaying = NowPlaying();

  /// Sends the phone's plays while the app is open; they are also sent on every refresh
  Timer? _sending;
  var _recorded = false;
  var _page = 0;

  /// The page chosen along the bottom fades in, rising a little
  late final _shown = AnimationController(vsync: this, duration: const Duration(milliseconds: 250), value: 1);
  late final _fade = CurvedAnimation(parent: _shown, curve: Curves.easeOut);
  late final _rise = Tween(begin: const Offset(0, 0.02), end: Offset.zero).animate(_fade);

  @override
  void initState() {
    super.initState();
    final controller = AppScope.read(context);
    _store = DataStore(controller.repository);
    _sending = Timer.periodic(const Duration(minutes: 1), (_) => _sendPlays());
    _nowPlaying.addListener(_songChanged);
    refresh();
  }

  /// Send the phone's plays, then load the data and the settings chosen on other devices
  Future<void> refresh() async {
    final controller = AppScope.read(context);
    await _nowPlaying.sendPlays().catchError((_) => 0);
    await Future.wait([_store.refresh(), controller.syncSettings().catchError((_) {})]);
  }

  /// A song just recorded shows in the lists at once
  void _songChanged() {
    final recorded = _nowPlaying.song?.recorded ?? false;
    if (recorded && !_recorded) _sendPlays();
    _recorded = recorded;
  }

  Future<void> _sendPlays() async {
    final sent = await _nowPlaying.sendPlays().catchError((_) => 0);
    if (sent > 0 && mounted) await _store.refresh();
  }

  @override
  void dispose() {
    _store.dispose();
    _sending?.cancel();
    _nowPlaying.removeListener(_songChanged);
    _nowPlaying.dispose();
    _fade.dispose();
    _shown.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      ListeningScreen(store: _store, onRefresh: refresh),
      PlaylistsScreen(store: _store, onRefresh: refresh),
      AccountScreen(store: _store, nowPlaying: _nowPlaying),
    ];
    return Scaffold(
      body: SafeArea(
        child: FadeTransition(
          opacity: _fade,
          child: SlideTransition(position: _rise, child: IndexedStack(index: _page, children: pages)),
        ),
      ),
      bottomNavigationBar: Column(mainAxisSize: MainAxisSize.min, children: [
        MiniPlayer(nowPlaying: _nowPlaying, store: _store),
        SlidingNavigationBar(
          selected: _page,
          onSelected: (page) {
            if (page == _page) return;
            setState(() => _page = page);
            _shown.forward(from: 0);
          },
          items: [
            BarItem(Icons.headphones_outlined, Icons.headphones, context.t('nav.listening')),
            BarItem(Icons.queue_music_outlined, Icons.queue_music, context.t('nav.playlists')),
            BarItem(Icons.person_outline, Icons.person, context.t('nav.account')),
          ],
        ),
      ]),
    );
  }
}
