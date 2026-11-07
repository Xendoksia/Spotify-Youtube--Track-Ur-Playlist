import 'dart:ui' show PlatformDispatcher;

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../data/repository.dart';
import '../l10n/strings.dart';

const themes = {'system': ThemeMode.system, 'light': ThemeMode.light, 'dark': ThemeMode.dark};

/// The language and theme, as the desktop app's LANGUAGE and THEME settings. Kept on the phone too, so the app
/// opens in them before it reaches Supabase.
class AppController extends ChangeNotifier {
  final Repository repository;
  late SharedPreferences _prefs;
  String language = 'en';
  String theme = 'system';

  AppController(this.repository);

  ThemeMode get themeMode => themes[theme]!;

  Future<void> load() async {
    _prefs = await SharedPreferences.getInstance();
    final phone = PlatformDispatcher.instance.locale.languageCode;
    language = _prefs.getString('LANGUAGE') ?? (languages.containsKey(phone) ? phone : 'en');
    theme = _prefs.getString('THEME') ?? 'system';
  }

  /// Take the settings synced from the account (after logging in and on every refresh)
  Future<void> syncSettings() async {
    final data = await repository.settings();
    await _apply(data['LANGUAGE'] as String?, data['THEME'] as String?);
  }

  /// Chosen here: shown at once and sent to the account for the other devices
  Future<void> choose({String? language, String? theme}) async {
    await _apply(language, theme);
    await repository.saveSettings({'LANGUAGE': this.language, 'THEME': this.theme});
  }

  Future<void> _apply(String? language, String? theme) async {
    var changed = false;
    if (language != null && languages.containsKey(language) && language != this.language) {
      this.language = language;
      await _prefs.setString('LANGUAGE', language);
      changed = true;
    }
    if (theme != null && themes.containsKey(theme) && theme != this.theme) {
      this.theme = theme;
      await _prefs.setString('THEME', theme);
      changed = true;
    }
    if (changed) notifyListeners();
  }
}

/// Gives the widgets below it the AppController and rebuilds them when the language or theme changes
class AppScope extends InheritedNotifier<AppController> {
  const AppScope({super.key, required AppController controller, required super.child})
      : super(notifier: controller);

  static AppController of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<AppScope>()!.notifier!;

  /// Without rebuilding on changes: for initState and button handlers
  static AppController read(BuildContext context) => context.getInheritedWidgetOfExactType<AppScope>()!.notifier!;
}
