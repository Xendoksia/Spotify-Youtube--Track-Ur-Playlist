import 'package:flutter/material.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'app.dart';
import 'config.dart';
import 'data/genres.dart';
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
