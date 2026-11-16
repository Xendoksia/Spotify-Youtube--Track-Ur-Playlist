import 'package:flutter/material.dart';

import '../../data/models.dart';
import '../../data/stats.dart';
import '../../l10n/strings.dart';
import '../../state/data_store.dart';
import '../../theme/palette.dart';
import '../../widgets/artwork_image.dart';
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
        final now = DateTime.now();
        return RefreshIndicator(
          onRefresh: onRefresh,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (store.playlists.isEmpty) const _NoPlaylists(),
              for (final service in serviceNames.keys)
                if (store.playlists.any((p) => p.service == service)) ...[
                  Padding(
                    padding: const EdgeInsets.only(top: 8, bottom: 8),
                    child: Text(
                      serviceNames[service]!,
                      style: Theme.of(context).textTheme.titleMedium
                          ?.copyWith(color: serviceColors[service], fontWeight: FontWeight.w600),
                    ),
                  ),
                  for (final playlist in store.playlists.where((p) => p.service == service))
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: _PlaylistCard(playlist: playlist, events: store.eventsOf(playlist), now: now),
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
  final DateTime now;

  const _PlaylistCard({required this.playlist, required this.events, required this.now});

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final latest = latestChanges(events);
    final newest = newestTracks(events);
    final days = dailyChanges(events, now);
    final muted = TextStyle(color: palette.muted, fontSize: 13);
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => PlaylistHistoryScreen(playlist: playlist, events: events),
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  _Mosaic(service: playlist.service, tracks: newest),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          playlist.name,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w600),
                        ),
                        if (newest.isNotEmpty)
                          Text(
                            context.t('playlists.newest', {
                              'track': newest.first.artist.isEmpty
                                  ? newest.first.name
                                  : '${newest.first.name} — ${newest.first.artist}',
                            }),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: muted,
                          ),
                        const SizedBox(height: 6),
                        if (latest == null)
                          Text(context.t('playlists.no_changes'), style: muted)
                        else ...[
                          Text(context.t('playlists.latest', {'date': context.dateTime(latest.at)}), style: muted),
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
              if (days != null) ...[const SizedBox(height: 12), _Activity(days: days)],
            ],
          ),
        ),
      ),
    );
  }
}

/// A square of the covers of the playlist's four newest albums (YouTube: video thumbnails), as on the desktop
/// app's cards; the service's mark until there are any
class _Mosaic extends StatelessWidget {
  final String service;
  final List<PlaylistEvent> tracks;

  const _Mosaic({required this.service, required this.tracks});

  static const size = 72.0;

  Widget _picture(PlaylistEvent track, double side) => service == 'youtube'
      ? ArtworkImage.video(id: track.uri, name: track.name, size: side, corner: 0)
      : ArtworkImage.cover(artist: track.artist, album: track.album, name: track.name, size: side, corner: 0);

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final color = serviceColors[service] ?? palette.muted;
    final Widget content;
    if (tracks.isEmpty) {
      content = Container(
        color: color.withValues(alpha: 0.14),
        alignment: Alignment.center,
        child: Icon(Icons.queue_music, color: color, size: 32),
      );
    } else if (tracks.length == 1) {
      content = _picture(tracks.first, size);
    } else {
      const side = size / 2;
      content = Wrap(
        children: [
          for (var i = 0; i < 4; i++)
            i < tracks.length ? _picture(tracks[i], side) : Container(width: side, height: side, color: palette.border),
        ],
      );
    }
    // The pictures' own corners are covered by the square's
    return ClipRRect(
      borderRadius: BorderRadius.circular(10),
      child: SizedBox.square(dimension: size, child: content),
    );
  }
}

/// The tracks added (up, green) and removed (down, red) per day over the last 30 days, with the totals; holding
/// a finger on a day gives its counts
class _Activity extends StatefulWidget {
  final List<DayChanges> days;

  const _Activity({required this.days});

  @override
  State<_Activity> createState() => _ActivityState();
}

class _ActivityState extends State<_Activity> {
  int? _touched;

  void _touch(Offset at, double width) {
    final index = (at.dx / width * widget.days.length).floor().clamp(0, widget.days.length - 1);
    if (index != _touched) setState(() => _touched = index);
  }

  void _release() => setState(() => _touched = null);

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final days = widget.days;
    final added = days.fold(0, (sum, d) => sum + d.added);
    final removed = days.fold(0, (sum, d) => sum + d.removed);
    final touched = _touched;
    const small = TextStyle(fontSize: 12, fontWeight: FontWeight.w600);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        LayoutBuilder(
          builder: (context, constraints) => GestureDetector(
            behavior: HitTestBehavior.opaque,
            onHorizontalDragStart: (d) => _touch(d.localPosition, constraints.maxWidth),
            onHorizontalDragUpdate: (d) => _touch(d.localPosition, constraints.maxWidth),
            onHorizontalDragEnd: (_) => _release(),
            onTapDown: (d) => _touch(d.localPosition, constraints.maxWidth),
            onTapUp: (_) => _release(),
            onTapCancel: _release,
            child: SizedBox(
              height: 40,
              child: CustomPaint(
                painter: _ActivityPainter(
                  days: days,
                  added: palette.added,
                  removed: palette.removed,
                  line: palette.border,
                  touched: touched,
                ),
              ),
            ),
          ),
        ),
        const SizedBox(height: 6),
        Row(
          children: [
            if (touched == null) ...[
              Text('+${context.number(added)}', style: small.copyWith(color: palette.added)),
              const SizedBox(width: 8),
              Text('−${context.number(removed)}', style: small.copyWith(color: palette.removed)),
              const Spacer(),
              Text(
                context.t('playlists.last_days', {'count': activityDays}),
                style: TextStyle(color: palette.muted, fontSize: 12),
              ),
            ] else
              Text(
                context.t('playlists.day_changes', {
                  'day': context.dateFormat('d MMM').format(days[touched].day),
                  'added': days[touched].added,
                  'removed': days[touched].removed,
                }),
                style: small.copyWith(color: palette.muted),
              ),
          ],
        ),
      ],
    );
  }
}

class _ActivityPainter extends CustomPainter {
  final List<DayChanges> days;
  final Color added;
  final Color removed;
  final Color line;
  final int? touched;

  _ActivityPainter({required this.days, required this.added, required this.removed, required this.line, this.touched});

  @override
  void paint(Canvas canvas, Size size) {
    final middle = size.height / 2;
    final most = days.fold(1, (m, d) => [m, d.added, d.removed].reduce((a, b) => a > b ? a : b));
    final slot = size.width / days.length;
    final bar = (slot * 0.62).clamp(2.0, 10.0);
    canvas.drawLine(Offset(0, middle), Offset(size.width, middle), Paint()..color = line);
    for (final (i, day) in days.indexed) {
      final faded = touched != null && touched != i;
      final x = i * slot + (slot - bar) / 2;
      final radius = Radius.circular(bar / 2);
      if (day.added > 0) {
        final height = (middle - 1) * day.added / most;
        canvas.drawRRect(
          RRect.fromRectAndCorners(Rect.fromLTWH(x, middle - height, bar, height), topLeft: radius, topRight: radius),
          Paint()..color = faded ? added.withValues(alpha: 0.35) : added,
        );
      }
      if (day.removed > 0) {
        final height = (middle - 1) * day.removed / most;
        canvas.drawRRect(
          RRect.fromRectAndCorners(Rect.fromLTWH(x, middle, bar, height), bottomLeft: radius, bottomRight: radius),
          Paint()..color = faded ? removed.withValues(alpha: 0.35) : removed,
        );
      }
    }
  }

  @override
  bool shouldRepaint(_ActivityPainter old) =>
      old.days != days || old.touched != touched || old.added != added || old.line != line;
}

/// No playlists yet: a small drawing of playlist cards over the hint, as on the desktop app
class _NoPlaylists extends StatelessWidget {
  const _NoPlaylists();

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 48, 24, 24),
      child: Column(
        children: [
          SizedBox(
            width: 160,
            height: 110,
            child: CustomPaint(
              painter: _CardsDrawing(
                card: Theme.of(context).colorScheme.surfaceContainer,
                edge: palette.border,
                line: palette.muted.withValues(alpha: 0.35),
                accent: serviceColors['spotify']!,
              ),
            ),
          ),
          const SizedBox(height: 20),
          Text(
            context.t('playlists.empty'),
            textAlign: TextAlign.center,
            style: TextStyle(color: palette.muted),
          ),
        ],
      ),
    );
  }
}

class _CardsDrawing extends CustomPainter {
  final Color card;
  final Color edge;
  final Color line;
  final Color accent;

  _CardsDrawing({required this.card, required this.edge, required this.line, required this.accent});

  @override
  void paint(Canvas canvas, Size size) {
    const height = 34.0;
    for (var i = 0; i < 3; i++) {
      // The back cards narrower, peeking out above the front one
      final inset = (2 - i) * 12.0;
      final top = i * 30.0 + 4;
      final rect = RRect.fromRectAndRadius(
        Rect.fromLTWH(inset, top, size.width - 2 * inset, height),
        const Radius.circular(8),
      );
      canvas.drawRRect(rect, Paint()..color = card);
      canvas.drawRRect(
        rect,
        Paint()
          ..color = edge
          ..style = PaintingStyle.stroke,
      );
      final square = Rect.fromLTWH(inset + 7, top + 7, height - 14, height - 14);
      canvas.drawRRect(
        RRect.fromRectAndRadius(square, const Radius.circular(4)),
        Paint()..color = i == 2 ? accent.withValues(alpha: 0.7) : line,
      );
      final paint = Paint()
        ..color = line
        ..strokeWidth = 4
        ..strokeCap = StrokeCap.round;
      final left = square.right + 8;
      canvas.drawLine(Offset(left, top + 12), Offset(size.width - inset - 30, top + 12), paint);
      canvas.drawLine(Offset(left, top + 22), Offset(size.width - inset - 54, top + 22), paint);
    }
  }

  @override
  bool shouldRepaint(_CardsDrawing old) => old.card != card || old.line != line;
}
