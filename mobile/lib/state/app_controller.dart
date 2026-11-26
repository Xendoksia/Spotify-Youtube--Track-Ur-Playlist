import 'dart:convert';
import 'dart:ui' show PlatformDispatcher;

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../data/discover.dart';
import '../data/repository.dart';
import '../l10n/strings.dart';

const themes = {'system': ThemeMode.system, 'light': ThemeMode.light, 'dark': ThemeMode.dark};

/// The language and theme, as the desktop app's LANGUAGE and THEME settings, and the Discover page's hidden
/// suggestions and fame setting (DISCOVER_HIDDEN, DISCOVER_FAME). Kept on the phone too, so the app opens in them
/// before it reaches Supabase.
class AppController extends ChangeNotifier {
  final Repository repository;
  late SharedPreferences _prefs;
  String language = 'en';
  String theme = 'system';

  /// Raised when the Discover settings change, here or on another device, for the page to show them
  int discoverRevision = 0;

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
    var changed = false;
    if (data.containsKey(hiddenSetting)) {
      final hidden = jsonEncode(hiddenJson(hiddenFrom(data[hiddenSetting])));
      if (hidden != (_prefs.getString(hiddenSetting) ?? '[]')) {
        await _prefs.setString(hiddenSetting, hidden);
        changed = true;
      }
    }
    final fame = data[fameSetting];
    if (fame is String && fameDirection.containsKey(fame) && fame != readFame(_prefs)) {
      await _prefs.setString(fameSetting, fame);
      changed = true;
    }
    if (changed) _discoverChanged();
  }

  /// Chosen here: shown at once and sent to the account for the other devices
  Future<void> choose({String? language, String? theme}) async {
    await _apply(language, theme);
    await _save();
  }

  List<Hidden> get hidden => readHidden(_prefs);

  String get fame => readFame(_prefs);

  /// Leave a suggestion out for good, or suggest it again
  Future<void> hide(Hidden hidden) =>
      _setHidden([...this.hidden.where((h) => h.kind != hidden.kind || h.key != hidden.key), hidden]);

  Future<void> show(Hidden hidden) =>
      _setHidden(this.hidden.where((h) => h.kind != hidden.kind || h.key != hidden.key).toList());

  Future<void> chooseFame(String fame) async {
    await _prefs.setString(fameSetting, fame);
    _discoverChanged();
    await _save().catchError((_) {});
  }

  Future<void> _setHidden(List<Hidden> hidden) async {
    await _prefs.setString(hiddenSetting, jsonEncode(hiddenJson(hidden)));
    _discoverChanged();
    await _save().catchError((_) {});
  }

  void _discoverChanged() {
    discoverRevision++;
    notifyListeners();
  }

  /// Every synced setting, so saving one keeps the others the other devices chose
  Future<void> _save() => repository.saveSettings({
        'LANGUAGE': language,
        'THEME': theme,
        hiddenSetting: hiddenJson(hidden),
        fameSetting: fame,
      });

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
