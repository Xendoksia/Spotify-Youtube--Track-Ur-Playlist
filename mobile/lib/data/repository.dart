import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../config.dart';
import 'models.dart';

/// Reads what the desktop app synced to Supabase. Row level security gives every user only their own rows.
class Repository {
  /// Supabase returns at most this many rows per request (max_rows), so longer lists are read in pages
  static const pageSize = 1000;

  SupabaseClient get _db => Supabase.instance.client;

  Future<List<Play>> plays() async {
    final rows = await _all((from, to) => _db
        .from('plays')
        .select('uid,device_id,device_name,played_at,source,artist,name,album,ms_played')
        .order('played_at', ascending: false)
        .order('uid')
        .range(from, to));
    return rows.map(Play.fromRow).toList();
  }

  Future<List<TrackedPlaylist>> trackedPlaylists() async {
    final rows = await _db.from('tracked_playlists').select('service,playlist_id,name').eq('tracked', true);
    return rows.map(TrackedPlaylist.fromRow).toList()
      ..sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
  }

  Future<List<PlaylistEvent>> events() async {
    final rows = await _all((from, to) => _db
        .from('playlist_events')
        .select('uid,service,playlist_id,checked_at,event,name,artist,album')
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

  Future<void> logIn() async {
    if (!desktop) {
      await _db.auth.signInWithOAuth(OAuthProvider.google,
          redirectTo: Config.loginRedirect, authScreenLaunchMode: LaunchMode.externalApplication);
      return;
    }
    // A computer has no app link to come back through: the browser comes back to a page the app serves itself,
    // with the code that is traded for the session
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, Config.desktopLoginPort);
    try {
      await _db.auth.signInWithOAuth(OAuthProvider.google,
          redirectTo: Config.desktopLoginRedirect, authScreenLaunchMode: LaunchMode.externalApplication);
      await for (final request in server.timeout(const Duration(minutes: 3))) {
        final query = request.uri.queryParameters;
        if (request.uri.path != '/callback') {
          request.response.statusCode = HttpStatus.notFound;
          await request.response.close();
          continue;
        }
        final code = query['code'];
        request.response.headers.contentType = ContentType.html;
        request.response.write('<!doctype html><meta charset="utf-8"><title>Playlist Tracker</title>'
            '<body style="font-family:Segoe UI,sans-serif;text-align:center;padding-top:15vh">'
            '<h2>${code != null ? '&#10003;' : '&#10007;'} Playlist Tracker</h2>'
            '<p>${code != null ? 'You can close this tab.' : 'Login failed.'}</p></body>');
        await request.response.close();
        if (code != null) await _db.auth.exchangeCodeForSession(code);
        break;
      }
    } on TimeoutException {
      // Given up in the browser: nothing to do
    } finally {
      await server.close(force: true);
    }
  }

  /// Windows, macOS or Linux: logging in comes back to a local address instead of an app link
  static bool get desktop =>
      !kIsWeb &&
      const {TargetPlatform.windows, TargetPlatform.macOS, TargetPlatform.linux}.contains(defaultTargetPlatform);

  Future<void> logOut() => _db.auth.signOut();

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
