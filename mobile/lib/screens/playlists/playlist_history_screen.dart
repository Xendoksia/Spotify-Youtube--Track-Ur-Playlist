import 'package:flutter/material.dart';

import '../../data/models.dart';
import '../../l10n/strings.dart';
import '../../theme/palette.dart';
import '../../widgets/artwork_image.dart';
import '../../widgets/cards.dart';
import '../../widgets/event_badge.dart';
import '../../widgets/format.dart';

/// Every change the checks of one playlist found, newest first, as a card per day with the day's totals, as the
/// desktop app's history
class PlaylistHistoryScreen extends StatelessWidget {
  final TrackedPlaylist playlist;
  final List<PlaylistEvent> events;

  const PlaylistHistoryScreen({super.key, required this.playlist, required this.events});

  @override
  Widget build(BuildContext context) {
    final days = <DateTime, List<PlaylistEvent>>{};
    for (final event in [...events]..sort((a, b) => b.checkedAt.compareTo(a.checkedAt))) {
      final at = event.checkedAt;
      days.putIfAbsent(DateTime(at.year, at.month, at.day), () => []).add(event);
    }
    return Scaffold(
      appBar: AppBar(title: Text(playlist.name)),
      body: days.isEmpty
          ? Center(
              child: MessageView(icon: Icons.history, text: context.t('playlists.no_history')),
            )
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                for (final MapEntry(key: day, value: found) in days.entries)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: _DayCard(day: day, events: found, service: playlist.service),
                  ),
              ],
            ),
    );
  }
}

class _DayCard extends StatelessWidget {
  final DateTime day;
  final List<PlaylistEvent> events;
  final String service;

  const _DayCard({required this.day, required this.events, required this.service});

  @override
  Widget build(BuildContext context) {
    final counts = <EventKind, int>{};
    for (final event in events.where((e) => e.kind != EventKind.initial)) {
      counts[event.kind] = (counts[event.kind] ?? 0) + 1;
    }
    return SectionCard(
      title: context.day(day),
      trailing: Wrap(
        spacing: 4,
        children: [
          for (final MapEntry(key: kind, value: count) in counts.entries)
            EventBadge(
              kind: kind,
              text: kind == EventKind.added
                  ? '+$count'
                  : kind == EventKind.removed
                  ? '−$count'
                  : '$count',
            ),
        ],
      ),
      child: Column(
        children: [for (final event in events) _EventRow(event: event, service: service)],
      ),
    );
  }
}

/// A change: its time, the track's cover (faded once removed), name and artist, with a line in the event's color
/// along its edge
class _EventRow extends StatelessWidget {
  final PlaylistEvent event;
  final String service;

  const _EventRow({required this.event, required this.service});

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final color = palette.event(event.kind);
    final count = event.initialCount;
    final Widget picture = count != null
        ? Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(color: color.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(5)),
            child: Icon(Icons.flag_outlined, color: color, size: 20),
          )
        : service == 'youtube'
        ? ArtworkImage.video(id: event.uri, name: event.name, size: 40)
        : ArtworkImage.cover(artist: event.artist, album: event.album, name: event.name, size: 40);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(
              width: 3,
              decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(2)),
            ),
            const SizedBox(width: 10),
            SizedBox(
              width: 42,
              child: Center(
                child: Text(context.time(event.checkedAt), style: TextStyle(color: palette.muted, fontSize: 12)),
              ),
            ),
            Center(
              child: Opacity(opacity: event.kind == EventKind.removed ? 0.45 : 1, child: picture),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    count != null ? context.t('event.initial_count', {'count': count}) : event.name,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (count == null && event.artist.isNotEmpty)
                    Text(
                      event.artist,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(color: palette.muted, fontSize: 13),
                    ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Center(
              child: EventBadge(kind: event.kind, text: context.t('event.${event.kind.code}')),
            ),
          ],
        ),
      ),
    );
  }
}
