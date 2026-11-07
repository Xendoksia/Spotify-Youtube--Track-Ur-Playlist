import 'package:flutter/foundation.dart';

import '../data/models.dart';
import '../data/repository.dart';

/// Everything the screens show, loaded from Supabase at once and again when the user pulls to refresh
class DataStore extends ChangeNotifier {
  final Repository repository;
  List<Play> plays = [];
  List<TrackedPlaylist> playlists = [];
  List<PlaylistEvent> events = [];
  bool loading = false;
  bool loaded = false;
  Object? error;

  DataStore(this.repository);

  Future<void> refresh() async {
    loading = true;
    error = null;
    notifyListeners();
    try {
      final results = await Future.wait([repository.plays(), repository.trackedPlaylists(), repository.events()]);
      plays = results[0] as List<Play>;
      playlists = results[1] as List<TrackedPlaylist>;
      events = results[2] as List<PlaylistEvent>;
      loaded = true;
    } catch (e) {
      error = e;
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  List<PlaylistEvent> eventsOf(TrackedPlaylist playlist) => events
      .where((e) => e.service == playlist.service && e.playlistId == playlist.playlistId)
      .toList();
}
