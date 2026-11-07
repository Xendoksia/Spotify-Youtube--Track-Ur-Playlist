import 'package:flutter/material.dart';

import '../l10n/strings.dart';
import '../state/app_controller.dart';
import '../state/data_store.dart';
import 'account_screen.dart';
import 'listening/listening_screen.dart';
import 'playlists/playlists_screen.dart';

/// The logged-in app: listening, playlists and the account, along the bottom
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late final DataStore _store;
  var _page = 0;

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
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      ListeningScreen(store: _store, onRefresh: refresh),
      PlaylistsScreen(store: _store, onRefresh: refresh),
      AccountScreen(store: _store),
    ];
    return Scaffold(
      body: SafeArea(child: IndexedStack(index: _page, children: pages)),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _page,
        onDestinationSelected: (page) => setState(() => _page = page),
        destinations: [
          NavigationDestination(icon: const Icon(Icons.headphones_outlined), selectedIcon: const Icon(Icons.headphones),
              label: context.t('nav.listening')),
          NavigationDestination(icon: const Icon(Icons.queue_music_outlined),
              selectedIcon: const Icon(Icons.queue_music), label: context.t('nav.playlists')),
          NavigationDestination(icon: const Icon(Icons.person_outline), selectedIcon: const Icon(Icons.person),
              label: context.t('nav.account')),
        ],
      ),
    );
  }
}
