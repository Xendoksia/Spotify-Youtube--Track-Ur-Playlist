import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../data/models.dart';
import '../../l10n/strings.dart';
import '../../state/data_store.dart';
import '../../theme/palette.dart';
import '../../widgets/artwork_image.dart';
import '../../widgets/cards.dart';
import '../../widgets/event_badge.dart';
import '../../widgets/format.dart';
import '../../widgets/skeleton.dart';
import '../discover_screen.dart' show openInSpotify;
import 'playlist_history_screen.dart';

/// How many changes show at first, and how many more each "Show more" adds
const changesStep = 20;

/// Changes found this close to the newest one count as one check
const checkSpan = Duration(minutes: 30);

/// The playlists tracked in the desktop app as its tracking page: the last changes found and the tracks added
/// lately at the top, the playlists, then every change with filters
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
          if (store.error == null) {
            return ListView(padding: const EdgeInsets.all(16), children: const [PlaylistsSkeleton()]);
          }
          return Center(
            child: MessageView(
              icon: Icons.cloud_off,
              text: context.t('load.failed', {'error': store.error!}),
              action: context.t('load.retry'),
              onAction: onRefresh,
            ),
          );
        }
        return _Tracking(store: store, onRefresh: onRefresh);
      },
    );
  }
}

class _Tracking extends StatefulWidget {
  final DataStore store;
  final Future<void> Function() onRefresh;

  const _Tracking({required this.store, required this.onRefresh});

  @override
  State<_Tracking> createState() => _TrackingState();
}

class _TrackingState extends State<_Tracking> {
  final _search = TextEditingController();
  var _query = '';
  String? _service;
  TrackedPlaylist? _playlist;
  EventKind? _kind;
  var _shown = changesStep;

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  void _filter(VoidCallback change) => setState(() {
        change();
        _shown = changesStep;
      });

  String _playlistName(PlaylistEvent event) =>
      widget.store.playlists
          .where((p) => p.service == event.service && p.playlistId == event.playlistId)
          .firstOrNull
          ?.name ??
      '';

  bool _matches(PlaylistEvent e) {
    if (_service != null && e.service != _service) return false;
    if (_playlist != null && (e.service != _playlist!.service || e.playlistId != _playlist!.playlistId)) return false;
    final q = _query.trim().toLowerCase();
    return q.isEmpty || [e.name, e.artist, _playlistName(e)].any((field) => field.toLowerCase().contains(q));
  }

  @override
  Widget build(BuildContext context) {
    final store = widget.store;
    final events = [...store.events]..sort((a, b) => b.checkedAt.compareTo(a.checkedAt));
    final filtered = events.where(_matches).toList();
    final counts = {for (final kind in EventKind.values) kind: filtered.where((e) => e.kind == kind).length};
    final shown = _kind == null ? filtered : filtered.where((e) => e.kind == _kind).toList();
    final anyFilter = _query.isNotEmpty || _service != null || _playlist != null || _kind != null;
    final services = {for (final p in store.playlists) p.service}.toList()..sort();
    return RefreshIndicator(
      onRefresh: widget.onRefresh,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (store.playlists.isEmpty)
            const _NoPlaylists()
          else ...[
            if (events.isNotEmpty) _Hero(events: events, nameOf: _playlistName),
            const SizedBox(height: 12),
            _Lists(store: store),
            const SizedBox(height: 20),
            Text(context.t('track.changes'), style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            _FilterBar(
              search: _search,
              onSearch: (text) => _filter(() => _query = text),
              services: services,
              service: _service,
              onService: (service) => _filter(() {
                _service = service;
                _playlist = null;
              }),
              playlists: store.playlists.where((p) => _service == null || p.service == _service).toList(),
              playlist: _playlist,
              onPlaylist: (playlist) => _filter(() => _playlist = playlist),
              counts: counts,
              all: filtered.length,
              kind: _kind,
              onKind: (kind) => _filter(() => _kind = kind),
            ),
            const SizedBox(height: 12),
            if (shown.isEmpty)
              MessageView(
                icon: Icons.filter_alt_off,
                text: anyFilter ? context.t('track.no_results') : context.t('playlists.no_changes'),
                action: anyFilter ? context.t('track.clear') : null,
                onAction: () => _filter(() {
                  _search.clear();
                  _query = '';
                  _service = null;
                  _playlist = null;
                  _kind = null;
                }),
              )
            else ...[
              for (final day in _days(shown.take(_shown)))
                Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: _DayCard(day: day.key, events: day.value, nameOf: _playlistName),
                ),
              if (shown.length > _shown)
                Center(
                  child: OutlinedButton(
                    onPressed: () => setState(() => _shown += changesStep),
                    child: Text(context.t('track.more', {'count': context.number(shown.length - _shown)})),
                  ),
                ),
            ],
          ],
        ],
      ),
    );
  }
}

/// The events by local day, newest first
List<MapEntry<DateTime, List<PlaylistEvent>>> _days(Iterable<PlaylistEvent> events) {
  final days = <DateTime, List<PlaylistEvent>>{};
  for (final event in events) {
    final at = event.checkedAt;
    days.putIfAbsent(DateTime(at.year, at.month, at.day), () => []).add(event);
  }
  return days.entries.toList();
}

/// "Today", "Yesterday" or "20 Nov"
String _shortDay(BuildContext context, DateTime moment) {
  final now = DateTime.now();
  final days = DateTime(now.year, now.month, now.day).difference(DateTime(moment.year, moment.month, moment.day)).inDays;
  if (days == 0) return context.t('day.today');
  if (days == 1) return context.t('day.yesterday');
  return context.dateFormat('d MMM').format(moment);
}

Widget _picture(PlaylistEvent track, double size) => track.service == 'youtube'
    ? ArtworkImage.video(id: track.uri, name: track.name, size: size, corner: 8)
    : ArtworkImage.cover(artist: track.artist, album: track.album, name: track.name, size: size, corner: 8);

Future<void> _open(PlaylistEvent track) async {
  if (track.service == 'youtube') {
    await launchUrl(Uri.parse('https://www.youtube.com/watch?v=${Uri.encodeComponent(track.uri)}'),
        mode: LaunchMode.externalApplication);
  } else {
    await openInSpotify(track.artist, track.name);
  }
}

/// The newest changes found, as one check, and the tracks added lately, the ones of that check marked new
class _Hero extends StatelessWidget {
  final List<PlaylistEvent> events;
  final String Function(PlaylistEvent) nameOf;

  const _Hero({required this.events, required this.nameOf});

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final changes = events.where((e) => e.kind != EventKind.initial).toList();
    final newest = (changes.isEmpty ? events : changes).first.checkedAt;
    final check = changes.where((e) => newest.difference(e.checkedAt) <= checkSpan).toList();
    final added = check.where((e) => e.kind == EventKind.added).toList();
    final byPlaylist = <String, List<PlaylistEvent>>{};
    for (final e in check) {
      byPlaylist.putIfAbsent(nameOf(e), () => []).add(e);
    }
    final detail = [
      for (final MapEntry(key: name, value: found) in byPlaylist.entries)
        found.length == 1 && found.first.kind == EventKind.added
            ? context.t('track.hero.added_to', {'name': name, 'track': found.first.name})
            : context.t('track.hero.changed', {'name': name, 'count': context.number(found.length)}),
    ].join(', ');
    final recent = <PlaylistEvent>[];
    final seen = <String>{};
    for (final e in events) {
      if (e.kind != EventKind.added || !seen.add('${e.name}|${e.artist}'.toLowerCase())) continue;
      recent.add(e);
      if (recent.length == 6) break;
    }
    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 14, 14, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              context.t('track.hero.caption', {'day': _shortDay(context, newest), 'time': context.time(newest)})
                  .toUpperCase(),
              style: TextStyle(color: palette.muted, fontSize: 11, fontWeight: FontWeight.w600, letterSpacing: 0.8),
            ),
            const SizedBox(height: 4),
            Text(
              added.isNotEmpty
                  ? context.t('track.hero.new', {'count': context.number(added.length)})
                  : context.t('track.hero.changes', {'count': context.number(check.length)}),
              style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700),
            ),
            if (detail.isNotEmpty) Text(detail, style: const TextStyle(fontSize: 13)),
            if (recent.isNotEmpty) ...[
              const SizedBox(height: 12),
              SizedBox(
                height: 150,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  itemCount: recent.length,
                  separatorBuilder: (_, _) => const SizedBox(width: 12),
                  itemBuilder: (context, index) {
                    final track = recent[index];
                    final fresh = added.contains(track);
                    return InkWell(
                      borderRadius: BorderRadius.circular(8),
                      onTap: () => _open(track),
                      child: SizedBox(
                        width: 100,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Stack(
                              children: [
                                DecoratedBox(
                                  position: DecorationPosition.foreground,
                                  decoration: BoxDecoration(
                                    borderRadius: BorderRadius.circular(8),
                                    border: fresh ? Border.all(color: palette.added, width: 2) : null,
                                  ),
                                  child: _picture(track, 100),
                                ),
                                if (fresh)
                                  Positioned(
                                    left: 6,
                                    bottom: 6,
                                    child: EventBadge(kind: EventKind.added, text: context.t('track.recent.new')),
                                  ),
                              ],
                            ),
                            const SizedBox(height: 6),
                            Text(track.name,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                            Text(
                              '${_shortDay(context, track.checkedAt)} · ${track.artist}',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(color: palette.muted, fontSize: 12),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// The tracked playlists, each opening its own history; tracking is changed in the desktop app
class _Lists extends StatelessWidget {
  final DataStore store;

  const _Lists({required this.store});

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    return SectionCard(
      title: context.t('track.lists'),
      trailing: Text(context.number(store.playlists.length), style: TextStyle(color: palette.muted)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (final playlist in store.playlists)
            Builder(builder: (context) {
              final events = store.eventsOf(playlist)..sort((a, b) => b.checkedAt.compareTo(a.checkedAt));
              final changes = events.where((e) => e.kind != EventKind.initial);
              final newest = events.where((e) => e.kind == EventKind.added).firstOrNull;
              return InkWell(
                borderRadius: BorderRadius.circular(8),
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => PlaylistHistoryScreen(playlist: playlist, events: events)),
                ),
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Row(
                    children: [
                      newest == null
                          ? Container(
                              width: 40,
                              height: 40,
                              decoration: BoxDecoration(
                                color: (serviceColors[playlist.service] ?? palette.muted).withValues(alpha: 0.14),
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: Icon(Icons.queue_music, size: 20, color: serviceColors[playlist.service]),
                            )
                          : _picture(newest, 40),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(playlist.name,
                                maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
                            Row(
                              children: [
                                Container(
                                  width: 8,
                                  height: 8,
                                  decoration: BoxDecoration(color: serviceColors[playlist.service], shape: BoxShape.circle),
                                ),
                                const SizedBox(width: 6),
                                Expanded(
                                  child: Text(
                                    changes.isEmpty
                                        ? context.t('playlists.no_changes')
                                        : context.t('playlists.latest', {'date': _shortDay(context, changes.first.checkedAt)}),
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(color: palette.muted, fontSize: 12),
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                      Icon(Icons.chevron_right, color: palette.muted),
                    ],
                  ),
                ),
              );
            }),
          const SizedBox(height: 4),
          Text(context.t('track.tracked_hint'), style: TextStyle(color: palette.muted, fontSize: 12)),
        ],
      ),
    );
  }
}

/// Search, service, playlist and the kinds of change with their counts
class _FilterBar extends StatelessWidget {
  final TextEditingController search;
  final ValueChanged<String> onSearch;
  final List<String> services;
  final String? service;
  final ValueChanged<String?> onService;
  final List<TrackedPlaylist> playlists;
  final TrackedPlaylist? playlist;
  final ValueChanged<TrackedPlaylist?> onPlaylist;
  final Map<EventKind, int> counts;
  final int all;
  final EventKind? kind;
  final ValueChanged<EventKind?> onKind;

  const _FilterBar({
    required this.search,
    required this.onSearch,
    required this.services,
    required this.service,
    required this.onService,
    required this.playlists,
    required this.playlist,
    required this.onPlaylist,
    required this.counts,
    required this.all,
    required this.kind,
    required this.onKind,
  });

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    Widget dot(Color color) =>
        Container(width: 8, height: 8, decoration: BoxDecoration(color: color, shape: BoxShape.circle));
    Widget chip({required String label, required int count, required bool selected, required VoidCallback? onTap, Color? color}) =>
        Padding(
          padding: const EdgeInsets.only(right: 6),
          child: FilterChip(
            selected: selected,
            showCheckmark: false,
            onSelected: onTap == null ? null : (_) => onTap(),
            avatar: color == null ? null : dot(color),
            label: Text('$label  ${context.number(count)}'),
          ),
        );
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              controller: search,
              onChanged: onSearch,
              decoration: InputDecoration(
                isDense: true,
                prefixIcon: const Icon(Icons.search),
                hintText: context.t('track.search'),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(999)),
                suffixIcon: search.text.isEmpty
                    ? null
                    : IconButton(
                        tooltip: context.t('track.clear'),
                        icon: const Icon(Icons.close),
                        onPressed: () {
                          search.clear();
                          onSearch('');
                        },
                      ),
              ),
            ),
            const SizedBox(height: 8),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  if (services.length > 1)
                    Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: SegmentedButton<String>(
                        showSelectedIcon: false,
                        segments: [
                          ButtonSegment(value: '', label: Text(context.t('track.service_all'))),
                          for (final s in services)
                            ButtonSegment(value: s, label: Text(serviceNames[s] ?? s), icon: dot(serviceColors[s] ?? palette.muted)),
                        ],
                        selected: {service ?? ''},
                        onSelectionChanged: (value) => onService(value.first.isEmpty ? null : value.first),
                      ),
                    ),
                  PopupMenuButton<TrackedPlaylist?>(
                    tooltip: context.t('track.playlist_all'),
                    onSelected: onPlaylist,
                    itemBuilder: (context) => [
                      PopupMenuItem(value: null, child: Text(context.t('track.playlist_all'))),
                      for (final p in playlists) PopupMenuItem(value: p, child: Text(p.name)),
                    ],
                    child: Chip(
                      avatar: const Icon(Icons.queue_music, size: 18),
                      label: Text(playlist?.name ?? context.t('track.playlist_all')),
                      backgroundColor: playlist == null ? null : Theme.of(context).colorScheme.secondaryContainer,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 4),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  chip(label: context.t('track.kind_all'), count: all, selected: kind == null, onTap: () => onKind(null)),
                  for (final k in EventKind.values)
                    chip(
                      label: context.t('event.${k.code}'),
                      count: counts[k] ?? 0,
                      selected: kind == k,
                      color: palette.event(k),
                      onTap: (counts[k] ?? 0) == 0 && kind != k ? null : () => onKind(kind == k ? null : k),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _DayCard extends StatelessWidget {
  final DateTime day;
  final List<PlaylistEvent> events;
  final String Function(PlaylistEvent) nameOf;

  const _DayCard({required this.day, required this.events, required this.nameOf});

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final counts = <EventKind, int>{};
    for (final e in events) {
      counts[e.kind] = (counts[e.kind] ?? 0) + 1;
    }
    final summary = [
      for (final MapEntry(key: kind, value: count) in counts.entries)
        context.t('track.count.${kind.code}', {'count': context.number(count)}),
    ].join(', ');
    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 12, 14, 6),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text.rich(TextSpan(children: [
              TextSpan(text: context.day(day), style: const TextStyle(fontWeight: FontWeight.w600)),
              TextSpan(text: '   $summary', style: TextStyle(color: palette.muted, fontSize: 12)),
            ])),
            const SizedBox(height: 4),
            for (final e in events)
              Container(
                padding: const EdgeInsets.symmetric(vertical: 6),
                decoration: BoxDecoration(border: Border(top: BorderSide(color: palette.border))),
                child: Row(
                  children: [
                    if (e.kind == EventKind.initial)
                      Container(
                        width: 36,
                        height: 36,
                        decoration: BoxDecoration(color: palette.border, borderRadius: BorderRadius.circular(6)),
                      )
                    else
                      _picture(e, 36),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            e.kind == EventKind.initial
                                ? context.t('event.initial_count', {'count': e.initialCount ?? 0})
                                : e.name,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontWeight: FontWeight.w600),
                          ),
                          Text(
                            [if (e.artist.isNotEmpty) e.artist, nameOf(e)].join(' · '),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(color: palette.muted, fontSize: 12),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 8),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        EventBadge(kind: e.kind, text: context.t('event.${e.kind.code}')),
                        const SizedBox(height: 2),
                        Text(context.time(e.checkedAt), style: TextStyle(color: palette.muted, fontSize: 11)),
                      ],
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
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
