import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../data/stats.dart';
import '../l10n/strings.dart';
import '../state/app_controller.dart';
import '../state/data_store.dart';
import '../theme/palette.dart';
import '../widgets/cards.dart';
import '../widgets/format.dart';

/// The logged-in user, the devices that recorded plays, the language and theme (shared by all devices), log out
class AccountScreen extends StatelessWidget {
  final DataStore store;

  const AccountScreen({super.key, required this.store});

  @override
  Widget build(BuildContext context) {
    final controller = AppScope.of(context);
    final user = Supabase.instance.client.auth.currentUser!;
    final metadata = user.userMetadata ?? {};
    final name = (metadata['full_name'] ?? metadata['name'] ?? '') as String;
    final avatar = (metadata['avatar_url'] ?? metadata['picture']) as String?;
    final muted = Palette.of(context).muted;
    const gap = SizedBox(height: 12);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                CircleAvatar(
                  radius: 28,
                  backgroundImage: avatar != null ? NetworkImage(avatar) : null,
                  child: avatar == null ? Text(name.isEmpty ? '?' : name[0].toUpperCase()) : null,
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (name.isNotEmpty) Text(name, style: Theme.of(context).textTheme.titleMedium),
                      Text(user.email ?? '', style: TextStyle(color: muted)),
                      Text(
                        context.t('account.member_since',
                            {'date': context.dateFormat('yMMMd').format(DateTime.parse(user.createdAt).toLocal())}),
                        style: TextStyle(color: muted, fontSize: 13),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
        gap,
        ListenableBuilder(
          listenable: store,
          builder: (context, _) => SectionCard(
            title: context.t('account.devices'),
            child: Column(
              children: [
                for (final MapEntry(key: device, value: count) in playsPerDevice(store.plays))
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.computer),
                    title: Text(device.isEmpty ? context.t('account.device_unknown') : device),
                    trailing: Text(context.plays(count)),
                  ),
              ],
            ),
          ),
        ),
        gap,
        SectionCard(
          title: context.t('account.appearance'),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _Choice(
                label: context.t('account.language'),
                value: controller.language,
                options: languages,
                onChanged: (language) => controller.choose(language: language),
              ),
              _Choice(
                label: context.t('account.theme'),
                value: controller.theme,
                options: {for (final key in themes.keys) key: context.t('theme.$key')},
                onChanged: (theme) => controller.choose(theme: theme),
              ),
              const SizedBox(height: 4),
              Text(context.t('account.synced_note'), style: TextStyle(color: muted, fontSize: 13)),
            ],
          ),
        ),
        gap,
        OutlinedButton.icon(
          onPressed: () => controller.repository.logOut(),
          icon: const Icon(Icons.logout),
          label: Text(context.t('account.logout')),
        ),
      ],
    );
  }
}

class _Choice extends StatelessWidget {
  final String label;
  final String value;
  final Map<String, String> options;
  final ValueChanged<String> onChanged;

  const _Choice({required this.label, required this.value, required this.options, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(child: Text(label)),
        DropdownButton<String>(
          value: value,
          underline: const SizedBox.shrink(),
          items: [
            for (final MapEntry(:key, value: text) in options.entries) DropdownMenuItem(value: key, child: Text(text)),
          ],
          onChanged: (chosen) {
            if (chosen != null) onChanged(chosen);
          },
        ),
      ],
    );
  }
}
