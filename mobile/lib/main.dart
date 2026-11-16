import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'app.dart';
import 'config.dart';
import 'data/genres.dart';
import 'data/now_playing.dart';
import 'data/repository.dart';
import 'state/app_controller.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initializeDateFormatting();
  // Supabase keeps the session on the phone, so the app opens logged in next time
  if (Config.configured) {
    await Supabase.initialize(url: Config.supabaseUrl, publishableKey: Config.supabaseKey);
  }
  final controller = AppController(Repository());
  await controller.load();
  // The artists' genres found earlier, for the genre cards
  await Genres.instance.load();
  runApp(PlaylistTrackerApp(controller: controller));
}

/// Run by PlaySender.kt in an engine without a screen while the app is closed: sends the plays recorded on the
/// phone with the session the app keeps, then says how it went so Android can end the job (or try again later).
@pragma('vm:entry-point')
Future<void> backgroundSend() async {
  WidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('playlist_tracker/background');
  try {
    if (!Config.configured) throw StateError('not configured');
    await Supabase.initialize(url: Config.supabaseUrl, publishableKey: Config.supabaseKey);
    final sent = await NowPlaying.send();
    await channel.invokeMethod('sent', sent);
  } catch (_) {
    await channel.invokeMethod('failed');
  }
}
