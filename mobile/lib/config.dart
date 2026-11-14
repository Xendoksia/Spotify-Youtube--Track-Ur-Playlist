/// Supabase settings, given when the app is built or run:
/// `flutter run --dart-define-from-file=config.json` (config.json is kept out of git, see config.example.json).
/// Only the publishable key goes into the app; the secret key never does.
class Config {
  static const supabaseUrl = String.fromEnvironment('SUPABASE_URL');
  static const supabaseKey = String.fromEnvironment('SUPABASE_KEY');

  /// Where Supabase sends the browser back after the Google login. It must be in the Supabase project's
  /// Redirect URLs, and its scheme matches the intent filter in AndroidManifest.xml.
  static const loginRedirect = 'io.github.xendoksia.playlisttracker://login-callback';

  /// On a computer the browser comes back to this address instead, served by the app itself while logging in, as
  /// in the desktop app (account.py REDIRECT_URI); it is in the Redirect URLs too
  static const desktopLoginPort = 8889;
  static const desktopLoginRedirect = 'http://127.0.0.1:$desktopLoginPort/callback';

  static bool get configured => supabaseUrl.isNotEmpty && supabaseKey.isNotEmpty;
}
