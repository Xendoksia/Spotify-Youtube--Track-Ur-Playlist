import 'package:flutter/material.dart';

import '../../data/models.dart';
import '../../l10n/strings.dart';
import '../../theme/palette.dart';
import '../../widgets/cards.dart';
import '../../widgets/event_badge.dart';
import '../../widgets/format.dart';

/// Every change the checks of one playlist found, newest first, grouped by check
class PlaylistHistoryScreen extends StatelessWidget {
  final TrackedPlaylist playlist;
  final List<PlaylistEvent> events;

  const PlaylistHistoryScreen({super.key, required this.playlist, required this.events});

  @override
  Widget build(BuildContext context) {
    final checks = <DateTime, List<PlaylistEvent>>{};
    for (final event in [...events]..sort((a, b) => b.checkedAt.compareTo(a.checkedAt))) {
      checks.putIfAbsent(event.checkedAt, () => []).add(event);
    }
    return Scaffold(
      appBar: AppBar(title: Text(playlist.name)),
      body: checks.isEmpty
          ? Center(child: MessageView(icon: Icons.history, text: context.t('playlists.no_history')))
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                for (final MapEntry(key: at, value: found) in checks.entries)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: SectionCard(
                      title: context.dateTime(at),
                      child: Column(children: [for (final event in found) _EventRow(event: event)]),
                    ),
                  ),
              ],
            ),
    );
  }
}

class _EventRow extends StatelessWidget {
  final PlaylistEvent event;

  const _EventRow({required this.event});

  @override
  Widget build(BuildContext context) {
    final muted = Palette.of(context).muted;
    final count = event.initialCount;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          EventBadge(kind: event.kind, text: context.t('event.${event.kind.code}')),
          const SizedBox(width: 10),
          Expanded(
            child: count != null
                ? Text(context.t('event.initial_count', {'count': count}))
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(event.name),
                      if (event.artist.isNotEmpty)
                        Text(event.artist, style: TextStyle(color: muted, fontSize: 13)),
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}
