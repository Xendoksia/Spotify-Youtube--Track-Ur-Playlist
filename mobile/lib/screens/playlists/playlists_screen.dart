import 'package:flutter/material.dart';

import '../../data/models.dart';
import '../../data/stats.dart';
import '../../l10n/strings.dart';
import '../../state/data_store.dart';
import '../../theme/palette.dart';
import '../../widgets/cards.dart';
import '../../widgets/event_badge.dart';
import '../../widgets/format.dart';
import 'playlist_history_screen.dart';

/// The playlists tracked in the desktop app, by service, with the changes its last check found
class PlaylistsScreen extends StatelessWidget {
  final DataStore store;
  final Future<void> Function() onRefresh;

  const PlaylistsScreen({super.key, required this.store, required this.onRefresh});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: store,
      builder: (context, _) {
        if (!store.loaded) {
          return Center(
            child: store.error != null
                ? MessageView(
                    icon: Icons.cloud_off,
                    text: context.t('load.failed', {'error': store.error!}),
                    action: context.t('load.retry'),
                    onAction: onRefresh,
                  )
                : const CircularProgressIndicator(),
          );
        }
        return RefreshIndicator(
          onRefresh: onRefresh,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (store.playlists.isEmpty) MessageView(icon: Icons.queue_music, text: context.t('playlists.empty')),
              for (final service in serviceNames.keys)
                if (store.playlists.any((p) => p.service == service)) ...[
                  Padding(
                    padding: const EdgeInsets.only(top: 8, bottom: 8),
                    child: Text(serviceNames[service]!,
                        style: Theme.of(context)
                            .textTheme
                            .titleMedium
                            ?.copyWith(color: serviceColors[service], fontWeight: FontWeight.w600)),
                  ),
                  for (final playlist in store.playlists.where((p) => p.service == service))
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: _PlaylistCard(playlist: playlist, events: store.eventsOf(playlist)),
                    ),
                ],
            ],
          ),
        );
      },
    );
  }
}

class _PlaylistCard extends StatelessWidget {
  final TrackedPlaylist playlist;
  final List<PlaylistEvent> events;

  const _PlaylistCard({required this.playlist, required this.events});

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final latest = latestChanges(events);
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => Navigator.of(context).push(MaterialPageRoute(
          builder: (_) => PlaylistHistoryScreen(playlist: playlist, events: events),
        )),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(playlist.name, style: Theme.of(context).textTheme.titleSmall),
                    const SizedBox(height: 6),
                    if (latest == null)
                      Text(context.t('playlists.no_changes'), style: TextStyle(color: palette.muted, fontSize: 13))
                    else ...[
                      Text(context.t('playlists.latest', {'date': context.dateTime(latest.at)}),
                          style: TextStyle(color: palette.muted, fontSize: 13)),
                      const SizedBox(height: 6),
                      Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        children: [
                          for (final MapEntry(key: kind, value: count) in latest.counts.entries)
                            EventBadge(kind: kind, text: '$count ${context.t('event.${kind.code}').toLowerCase()}'),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
              Icon(Icons.chevron_right, color: palette.muted),
            ],
          ),
        ),
      ),
    );
  }
}
