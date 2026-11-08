import 'package:flutter/material.dart';

import '../l10n/strings.dart';
import '../data/now_playing.dart';
import '../state/app_controller.dart';
import '../state/data_store.dart';
import '../widgets/mini_player.dart';
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
    refresh();
  }

  /// Load the data and the settings chosen on other devices
  Future<void> refresh() async {
    final controller = AppScope.read(context);
    await Future.wait([_store.refresh(), controller.syncSettings().catchError((_) {})]);
  }

  @override
  void dispose() {
    _store.dispose();
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
        NavigationBar(
          selectedIndex: _page,
          onDestinationSelected: (page) {
            if (page == _page) return;
            setState(() => _page = page);
            _shown.forward(from: 0);
          },
          destinations: [
            NavigationDestination(icon: const Icon(Icons.headphones_outlined), selectedIcon: const Icon(Icons.headphones),
                label: context.t('nav.listening')),
            NavigationDestination(icon: const Icon(Icons.queue_music_outlined),
                selectedIcon: const Icon(Icons.queue_music), label: context.t('nav.playlists')),
            NavigationDestination(icon: const Icon(Icons.person_outline), selectedIcon: const Icon(Icons.person),
                label: context.t('nav.account')),
          ],
        ),
      ]),
    );
  }
}
