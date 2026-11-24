import 'package:shared_preferences/shared_preferences.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../config.dart';
import 'models.dart';

/// Reads what the desktop app synced to Supabase. Row level security gives every user only their own rows.
class Repository {
  /// Supabase returns at most this many rows per request (max_rows), so longer lists are read in pages
  static const pageSize = 1000;

  SupabaseClient get _db => Supabase.instance.client;

  /// How many plays the cloud held at the last load, before those two devices recorded together counted once
  int cloudPlays = 0;

  Future<List<Play>> plays() async {
    final rows = await _all((from, to) => _db
        .from('plays')
        .select('uid,device_id,device_name,played_at,source,artist,name,album,ms_played')
        .order('played_at', ascending: false)
        .order('uid')
        .range(from, to));
    cloudPlays = rows.length;
    // A play the computer and the phone both recorded counts once, as on the desktop app
    return withoutDuplicates(rows.map(Play.fromRow).toList());
  }

  /// Every playlist the desktop app knows: tracked, found in an account, or neither
  Future<List<TrackedPlaylist>> playlists() async {
    final rows = await _db.from('tracked_playlists').select('service,playlist_id,name,tracked,seen,size,found_at');
    return rows.map(TrackedPlaylist.fromRow).toList()
      ..sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
  }

  /// Track a playlist or not; the desktop app takes it at its next sync, the latest change winning. A playlist
  /// added by link has no name until the desktop app checks it
  Future<void> setTracking(String service, String playlistId, bool tracked, {String? name}) async {
    await _db.from('tracked_playlists').upsert({
      'user_id': _db.auth.currentUser!.id,
      'service': service,
      'playlist_id': playlistId,
      'name': ?name,
      'tracked': tracked,
      'seen': true,
      'changed_at': utcStamp(DateTime.now()),
    }, onConflict: 'user_id,service,playlist_id');
  }

  Future<PlaylistStatus> playlistStatus() async =>
      PlaylistStatus.fromRow(await _db.from('playlist_status').select().maybeSingle());

  /// Ask the desktop app to check the tracked playlists, which it does at its next sync
  Future<void> requestCheck() async {
    await _db.from('playlist_status').upsert({
      'user_id': _db.auth.currentUser!.id,
      'check_requested_at': DateTime.now().toUtc().toIso8601String(),
    }, onConflict: 'user_id');
  }

  Future<List<PlaylistEvent>> events() async {
    final rows = await _all((from, to) => _db
        .from('playlist_events')
        .select('uid,service,playlist_id,checked_at,event,name,artist,album,uri')
        .order('checked_at', ascending: false)
        .order('uid')
        .range(from, to));
    return rows.map(PlaylistEvent.fromRow).nonNulls.toList();
  }

  /// The language and theme the user chose on any device: {"LANGUAGE": "tr", "THEME": "dark"}
  Future<Map<String, dynamic>> settings() async {
    final row = await _db.from('settings').select('data').maybeSingle();
    return (row?['data'] as Map<String, dynamic>?) ?? {};
  }

  /// Save settings chosen here; the latest change wins on every device
  Future<void> saveSettings(Map<String, dynamic> data) async {
    await _db.from('settings').upsert({
      'user_id': _db.auth.currentUser!.id,
      'data': data,
      'changed_at': utcStamp(DateTime.now()),
    }, onConflict: 'user_id');
  }

  Future<void> logIn() => _db.auth.signInWithOAuth(OAuthProvider.google,
      redirectTo: Config.loginRedirect, authScreenLaunchMode: LaunchMode.externalApplication);

  /// Log out; the next login asks for the notification access again if it is still not given
  Future<void> logOut() async {
    await (await SharedPreferences.getInstance()).remove('ACCESS_ASKED');
    await _db.auth.signOut();
  }

  Future<List<Map<String, dynamic>>> _all(
      PostgrestTransformBuilder<List<Map<String, dynamic>>> Function(int from, int to) page) async {
    final rows = <Map<String, dynamic>>[];
    while (true) {
      final batch = await page(rows.length, rows.length + pageSize - 1);
      rows.addAll(batch);
      if (batch.length < pageSize) return rows;
    }
  }
}
