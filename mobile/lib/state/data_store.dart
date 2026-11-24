import 'package:flutter/foundation.dart';

import '../data/models.dart';
import '../data/repository.dart';
import '../data/stats.dart';

/// Everything the screens show, loaded from Supabase at once and again when the user pulls to refresh
class DataStore extends ChangeNotifier {
  final Repository repository;
  List<Play> plays = [];
  /// Every playlist the desktop app knows; [tracked] are the tracked ones
  List<TrackedPlaylist> playlists = [];
  List<PlaylistEvent> events = [];
  PlaylistStatus playlistStatus = const PlaylistStatus();
  bool loading = false;
  bool loaded = false;
  Object? error;

  /// When the plays were last loaded from the cloud
  DateTime? loadedAt;

  DataStore(this.repository);

  Future<void> refresh() async {
    loading = true;
    error = null;
    notifyListeners();
    try {
      final results = await Future.wait([repository.plays(), repository.playlists(), repository.events()]);
      plays = results[0] as List<Play>;
      rememberSoloArtists(plays);
      playlists = results[1] as List<TrackedPlaylist>;
      events = results[2] as List<PlaylistEvent>;
      playlistStatus = await _status();
      loaded = true;
      loadedAt = DateTime.now();
    } catch (e) {
      error = e;
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  List<TrackedPlaylist> get tracked => playlists.where((p) => p.tracked).toList();

  /// The desktop app's last check; empty until the server has its status table
  Future<PlaylistStatus> _status() async {
    try {
      return await repository.playlistStatus();
    } catch (_) {
      return const PlaylistStatus();
    }
  }

  /// Track a playlist or not, at once here and on the server
  Future<void> setTracking(TrackedPlaylist playlist, bool tracked) async {
    await repository.setTracking(playlist.service, playlist.playlistId, tracked);
    playlists = [
      for (final p in playlists)
        p == playlist
            ? TrackedPlaylist(service: p.service, playlistId: p.playlistId, name: p.name, tracked: tracked, size: p.size)
            : p,
    ];
    notifyListeners();
  }

  /// Track a playlist by its link; false when the link is no Spotify or YouTube playlist
  Future<bool> addLink(String link) async {
    final parsed = parsePlaylistLink(link);
    if (parsed == null) return false;
    final (service, playlistId) = parsed;
    final known = playlists.where((p) => p.service == service && p.playlistId == playlistId).firstOrNull;
    await repository.setTracking(service, playlistId, true);
    playlists = [
      for (final p in playlists)
        if (p != known) p,
      TrackedPlaylist(service: service, playlistId: playlistId, name: known?.name ?? playlistId, size: known?.size),
    ];
    notifyListeners();
    return true;
  }

  Future<void> requestCheck() async {
    await repository.requestCheck();
    playlistStatus = await _status();
    notifyListeners();
  }

  List<PlaylistEvent> eventsOf(TrackedPlaylist playlist) =>
      events.where((e) => e.service == playlist.service && e.playlistId == playlist.playlistId).toList();
}
