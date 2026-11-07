import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'config.dart';
import 'l10n/strings.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
import 'state/app_controller.dart';
import 'theme/palette.dart';

class PlaylistTrackerApp extends StatelessWidget {
  final AppController controller;

  const PlaylistTrackerApp({super.key, required this.controller});

  @override
  Widget build(BuildContext context) {
    return AppScope(
      controller: controller,
      child: ListenableBuilder(
        listenable: controller,
        builder: (context, _) => MaterialApp(
          title: translate(controller.language, 'app.title'),
          debugShowCheckedModeBanner: false,
          theme: buildTheme(Brightness.light),
          darkTheme: buildTheme(Brightness.dark),
          themeMode: controller.themeMode,
          locale: Locale(controller.language),
          supportedLocales: [for (final code in languages.keys) Locale(code)],
          localizationsDelegates: GlobalMaterialLocalizations.delegates,
          home: Config.configured ? const _AuthGate() : const LoginScreen(configured: false),
        ),
      ),
    );
  }
}

/// The login screen while logged out, the app once logged in (the login comes back from the browser)
class _AuthGate extends StatelessWidget {
  const _AuthGate();

  @override
  Widget build(BuildContext context) {
    final auth = Supabase.instance.client.auth;
    return StreamBuilder<AuthState>(
      stream: auth.onAuthStateChange,
      builder: (context, _) {
        final user = auth.currentUser;
        return user == null ? const LoginScreen() : HomeScreen(key: ValueKey(user.id));
      },
    );
  }
}
