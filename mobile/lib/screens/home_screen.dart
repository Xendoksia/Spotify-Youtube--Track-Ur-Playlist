import 'dart:async';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../data/discover.dart';
import '../l10n/strings.dart';
import '../data/now_playing.dart';
import '../state/app_controller.dart';
import '../state/data_store.dart';
import '../widgets/mini_player.dart';
import '../widgets/sliding.dart';
import 'account_screen.dart';
import 'discover_screen.dart';
import 'listening/listening_screen.dart';
import 'playlists/playlists_screen.dart';

/// The logged-in app: listening, playlists, discover and the account, along the bottom
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with SingleTickerProviderStateMixin, WidgetsBindingObserver {
  late final DataStore _store;
  final _nowPlaying = NowPlaying();

  /// Sends the phone's plays while the app is open; they are also sent on every refresh
  Timer? _sending;
  var _recorded = false;
  var _page = 0;

  /// The Discover suggestions and the alike-songs models, readied a little after the app opens
  Timer? _ahead;

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
    WidgetsBinding.instance.addObserver(this);
    refresh().whenComplete(_readySoon);
    _askAccess();
  }

  /// A few seconds after the app opens, once the first page is drawn, the day's Discover suggestions are worked
  /// out on a background isolate and then the models of the track pages loaded, one after the other not to hold
  /// both at once, so that neither the Discover page nor a page's alike songs keep anyone waiting
  void _readySoon() {
    _ahead?.cancel();
    _ahead = Timer(const Duration(seconds: 4), () async {
      if (!mounted || !_store.loaded) return;
      await discover(_store.plays).then((_) {}, onError: (_) {});
      if (mounted) await ModelWorker.instance.warm().catchError((_) {});
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final inFront = state == AppLifecycleState.resumed;
    ModelWorker.instance.inFront(inFront);
    // Back after a while: a new day's suggestions, or the models let go in the background
    if (inFront) _readySoon();
  }

  /// After logging in, offer Android's notification access page, without which nothing played on the phone is
  /// recorded in the background; asked once per login, later it is in the account page
  Future<void> _askAccess() async {
    await _nowPlaying.checked;
    final prefs = await SharedPreferences.getInstance();
    if (_nowPlaying.hasAccess || (prefs.getBool('ACCESS_ASKED') ?? false) || !mounted) return;
    await prefs.setBool('ACCESS_ASKED', true);
    if (!mounted) return;
    final allow = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        icon: const Icon(Icons.notifications_active_outlined),
        title: Text(context.t('phone.ask')),
        content: Text(context.t('phone.ask_text')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: Text(context.t('phone.later'))),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: Text(context.t('phone.allow'))),
        ],
      ),
    );
    if (allow ?? false) await _nowPlaying.openSettings();
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
    WidgetsBinding.instance.removeObserver(this);
    _ahead?.cancel();
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
      DiscoverScreen(store: _store, onRefresh: refresh, active: _page == 2),
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
            BarItem(Icons.explore_outlined, Icons.explore, context.t('nav.discover')),
            BarItem(Icons.person_outline, Icons.person, context.t('nav.account')),
          ],
        ),
      ]),
    );
  }
}
