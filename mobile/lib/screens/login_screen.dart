import 'package:flutter/material.dart';

import '../l10n/strings.dart';
import '../state/app_controller.dart';
import '../theme/palette.dart';

/// Log in with Google in the browser, with the same account as the desktop app
class LoginScreen extends StatefulWidget {
  /// False when the app was built without the Supabase settings: it says how to add them instead
  final bool configured;

  const LoginScreen({super.key, this.configured = true});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  String? _error;

  Future<void> _logIn() async {
    setState(() => _error = null);
    try {
      await AppScope.read(context).repository.logIn();
    } catch (e) {
      if (mounted) setState(() => _error = context.t('login.failed', {'error': e}));
    }
  }

  @override
  Widget build(BuildContext context) {
    final muted = Palette.of(context).muted;
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(32),
            child: Column(
              children: [
                Icon(Icons.queue_music_rounded, size: 72, color: serviceColors['spotify']),
                const SizedBox(height: 16),
                Text(context.t('app.title'), style: Theme.of(context).textTheme.headlineMedium),
                const SizedBox(height: 12),
                Text(
                  context.t(widget.configured ? 'login.lead' : 'login.not_configured'),
                  textAlign: TextAlign.center,
                  style: TextStyle(color: muted),
                ),
                if (widget.configured) ...[
                  const SizedBox(height: 32),
                  FilledButton.icon(
                    onPressed: _logIn,
                    icon: const Icon(Icons.login),
                    label: Text(context.t('login.google')),
                    style: FilledButton.styleFrom(minimumSize: const Size(260, 48)),
                  ),
                ],
                if (_error != null) ...[
                  const SizedBox(height: 16),
                  Text(_error!, textAlign: TextAlign.center, style: TextStyle(color: Palette.of(context).removed)),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
