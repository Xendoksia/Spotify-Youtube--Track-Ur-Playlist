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

/// The desktop app's tracking page on the phone: the last check and the tracks added lately at the top, the
/// playlists to track, then every change with filters
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
          if (store.playlists.isEmpty) ...[
            const _NoPlaylists(),
            _Lists(store: store),
          ] else ...[
            _Hero(store: store, events: events, nameOf: _playlistName),
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
              playlists: store.playlists
                  .where((p) => (_service == null || p.service == _service) && store.eventsOf(p).isNotEmpty)
                  .toList(),
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

/// The desktop app's last check and what it found (else the newest changes found), the tracks added lately, the
/// ones of that check marked new, and a button that asks the desktop app for a check
class _Hero extends StatelessWidget {
  final DataStore store;
  final List<PlaylistEvent> events;
  final String Function(PlaylistEvent) nameOf;

  const _Hero({required this.store, required this.events, required this.nameOf});

  Future<void> _check(BuildContext context) async {
    final messenger = ScaffoldMessenger.of(context);
    final sent = context.t('track.check.sent');
    final failed = context.t('track.check.failed');
    try {
      await store.requestCheck();
      messenger.showSnackBar(SnackBar(content: Text(sent)));
    } catch (_) {
      messenger.showSnackBar(SnackBar(content: Text(failed)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final status = store.playlistStatus;
    final changes = events.where((e) => e.kind != EventKind.initial).toList();
    final checkedAt = status.checkedAt;
    final newest = checkedAt ?? (changes.isEmpty ? events.firstOrNull?.checkedAt : changes.first.checkedAt);
    final check = newest == null
        ? <PlaylistEvent>[]
        : changes
            .where((e) => !e.checkedAt.isAfter(newest.add(const Duration(minutes: 1))) &&
                newest.difference(e.checkedAt) <= checkSpan)
            .toList();
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
    final caption = newest == null
        ? context.t('track.hero.first')
        : checkedAt != null
            ? context.t('track.hero.check_caption', {
                'day': _shortDay(context, checkedAt),
                'time': context.time(checkedAt),
                'count': context.number(status.checkedCount),
              })
            : context.t('track.hero.caption', {'day': _shortDay(context, newest), 'time': context.time(newest)});
    final title = added.isNotEmpty
        ? context.t('track.hero.new', {'count': context.number(added.length)})
        : check.isNotEmpty
            ? context.t('track.hero.changes', {'count': context.number(check.length)})
            : context.t('track.hero.none');
    final next = status.nextCheck;
    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 14, 14, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              caption.toUpperCase(),
              style: TextStyle(color: palette.muted, fontSize: 11, fontWeight: FontWeight.w600, letterSpacing: 0.8),
            ),
            const SizedBox(height: 4),
            Text(title, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
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
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                style: FilledButton.styleFrom(backgroundColor: serviceColors['spotify'], foregroundColor: Colors.white),
                onPressed: status.waiting || store.tracked.isEmpty ? null : () => _check(context),
                child: Text(status.waiting
                    ? context.t('track.check.waiting')
                    : context.t('track.check', {'count': context.number(store.tracked.length)})),
              ),
            ),
            if (next != null) ...[
              const SizedBox(height: 6),
              Row(
                children: [
                  Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(color: palette.added, shape: BoxShape.circle),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    context.t('track.auto.next', {
                      'time': next.day == DateTime.now().day
                          ? context.time(next)
                          : '${_shortDay(context, next)} ${context.time(next)}',
                    }),
                    style: TextStyle(color: palette.muted, fontSize: 12),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// The playlists: one to track by its link, the ones found in an account to track or not, and the tracked and
/// untracked ones with a switch each, opening their history. The desktop app takes the changes at its next sync
class _Lists extends StatefulWidget {
  final DataStore store;

  const _Lists({required this.store});

  @override
  State<_Lists> createState() => _ListsState();
}

class _ListsState extends State<_Lists> {
  final _link = TextEditingController();
  var _busy = false;

  @override
  void dispose() {
    _link.dispose();
    super.dispose();
  }

  Future<void> _run(Future<void> Function() action) async {
    final messenger = ScaffoldMessenger.of(context);
    final failed = context.t('track.check.failed');
    setState(() => _busy = true);
    try {
      await action();
    } catch (_) {
      messenger.showSnackBar(SnackBar(content: Text(failed)));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _add() async {
    final messenger = ScaffoldMessenger.of(context);
    final added = context.t('track.link.added');
    final bad = context.t('track.bad_link');
    await _run(() async {
      if (await widget.store.addLink(_link.text)) {
        _link.clear();
        messenger.showSnackBar(SnackBar(content: Text(added)));
      } else {
        messenger.showSnackBar(SnackBar(content: Text(bad)));
      }
    });
  }

  Widget _row(BuildContext context, TrackedPlaylist playlist) {
    final palette = Palette.of(context);
    final store = widget.store;
    final events = store.eventsOf(playlist)..sort((a, b) => b.checkedAt.compareTo(a.checkedAt));
    final changes = events.where((e) => e.kind != EventKind.initial);
    final newest = events.where((e) => e.kind == EventKind.added).firstOrNull;
    final meta = playlist.found
        ? context.t('track.found_in', {
            'service': serviceNames[playlist.service] ?? playlist.service,
            'day': _shortDay(context, playlist.foundAt ?? DateTime.now()),
          })
        : changes.isNotEmpty
            ? context.t('playlists.latest', {'date': _shortDay(context, changes.first.checkedAt)})
            : playlist.size != null
                ? context.t('track.size', {'count': context.number(playlist.size!)})
                : context.t('playlists.no_changes');
    return InkWell(
      borderRadius: BorderRadius.circular(8),
      onTap: events.isEmpty
          ? null
          : () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => PlaylistHistoryScreen(playlist: playlist, events: events)),
              ),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(
          children: [
            Opacity(
              opacity: playlist.tracked || playlist.found ? 1 : 0.55,
              child: newest == null
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
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(playlist.name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(fontWeight: playlist.tracked || playlist.found ? FontWeight.w600 : null)),
                  Row(
                    children: [
                      Container(
                        width: 8,
                        height: 8,
                        decoration: BoxDecoration(color: serviceColors[playlist.service], shape: BoxShape.circle),
                      ),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(meta,
                            maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(color: palette.muted, fontSize: 12)),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            if (!playlist.found)
              Switch(
                value: playlist.tracked,
                onChanged: _busy ? null : (on) => _run(() => store.setTracking(playlist, on)),
              ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final theme = Theme.of(context);
    final store = widget.store;
    final found = store.playlists.where((p) => p.found).toList();
    final tracked = store.tracked;
    final others = store.playlists.where((p) => !p.tracked && p.seen).toList();
    Text caption(String text, {Color? color}) => Text(text.toUpperCase(),
        style: TextStyle(color: color ?? palette.muted, fontSize: 11, fontWeight: FontWeight.w600, letterSpacing: 0.8));
    return SectionCard(
      title: context.t('track.lists'),
      trailing: Text(
        context.t('track.lists.count', {
          'count': context.number(store.playlists.length),
          'tracked': context.number(tracked.length),
        }),
        style: TextStyle(color: palette.muted, fontSize: 12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextField(
            controller: _link,
            enabled: !_busy,
            onSubmitted: (_) => _add(),
            decoration: InputDecoration(
              isDense: true,
              labelText: context.t('track.link.label'),
              hintText: context.t('track.link.placeholder'),
              prefixIcon: const Icon(Icons.link),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(999)),
              suffixIcon: Padding(
                padding: const EdgeInsets.all(4),
                child: FilledButton(
                  style: FilledButton.styleFrom(backgroundColor: serviceColors['spotify'], foregroundColor: Colors.white),
                  onPressed: _busy ? null : _add,
                  child: Text(context.t('track.link.add')),
                ),
              ),
            ),
          ),
          const SizedBox(height: 6),
          Text(context.t('track.found.auto'), style: TextStyle(color: palette.muted, fontSize: 12)),
          if (found.isNotEmpty) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
              decoration: BoxDecoration(
                color: theme.colorScheme.primaryContainer.withValues(alpha: 0.35),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: theme.colorScheme.primary.withValues(alpha: 0.45)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: caption(context.t('track.found.title', {'count': context.number(found.length)}),
                            color: theme.colorScheme.primary),
                      ),
                      if (found.length > 1) ...[
                        TextButton(
                          onPressed: _busy
                              ? null
                              : () => _run(() async {
                                    for (final p in found) {
                                      await store.setTracking(p, true);
                                    }
                                  }),
                          child: Text(context.t('track.found.track_all')),
                        ),
                        TextButton(
                          onPressed: _busy
                              ? null
                              : () => _run(() async {
                                    for (final p in found) {
                                      await store.setTracking(p, false);
                                    }
                                  }),
                          child: Text(context.t('track.found.skip_all')),
                        ),
                      ],
                    ],
                  ),
                  for (final playlist in found) ...[
                    _row(context, playlist),
                    Row(
                      children: [
                        Expanded(
                          child: FilledButton(
                            style: FilledButton.styleFrom(
                                backgroundColor: serviceColors['spotify'], foregroundColor: Colors.white),
                            onPressed: _busy ? null : () => _run(() => store.setTracking(playlist, true)),
                            child: Text(context.t('track.found.track')),
                          ),
                        ),
                        const SizedBox(width: 8),
                        OutlinedButton(
                          onPressed: _busy ? null : () => _run(() => store.setTracking(playlist, false)),
                          child: Text(context.t('track.found.skip')),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                  ],
                ],
              ),
            ),
          ],
          if (tracked.isNotEmpty) ...[
            const SizedBox(height: 12),
            caption(context.t('track.tracked', {'count': context.number(tracked.length)})),
            for (final playlist in tracked) _row(context, playlist),
          ],
          if (others.isNotEmpty) ...[
            Divider(color: palette.border, height: 20),
            caption(context.t('track.others', {'count': context.number(others.length)})),
            for (final playlist in others) _row(context, playlist),
          ],
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
