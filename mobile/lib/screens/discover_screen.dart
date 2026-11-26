import 'dart:math' show max;

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../data/artwork.dart';
import '../data/discover.dart';
import '../data/preview.dart';
import '../data/stats.dart';
import '../l10n/strings.dart';
import '../state/app_controller.dart';
import '../state/data_store.dart';
import '../theme/palette.dart';
import '../widgets/artwork_image.dart';
import '../widgets/cards.dart';
import '../widgets/format.dart';
import '../widgets/skeleton.dart';
import 'listening/detail_screen.dart';

const _spotifyGreen = Color(0xFF1AA34A);

/// Open an artist, or one of their songs, in the Spotify app, where playing it is recorded (the phone records
/// what Spotify plays); in the browser when the app is not installed
Future<void> openInSpotify(String artist, [String title = '']) async {
  final query = [artist, title].where((w) => w.isNotEmpty).join(' ');
  try {
    if (await launchUrl(Uri.parse('spotify:search:${Uri.encodeComponent(query)}'),
        mode: LaunchMode.externalApplication)) {
      return;
    }
  } catch (_) {}
  await launchUrl(Uri.parse('https://open.spotify.com/search/${Uri.encodeComponent(query)}'),
      mode: LaunchMode.externalApplication);
}

String _because(BuildContext context, List<String> names, {bool songs = false}) => switch (names.length) {
  1 => context.t('recommend.because_one', {'first': names[0]}),
  2 => context.t('recommend.because_two', {'first': names[0], 'second': names[1]}),
  _ => context.t(songs ? 'recommend.because_more_songs' : 'recommend.because_more',
      {'first': names[0], 'second': names[1], 'count': names.length - 2}),
};

List<String> _names(Item item) => (item['because'] as List).cast<String>();

/// The seeds' shares of a suggestion as one bar, each a step fainter
class _WhyBar extends StatelessWidget {
  final List<Why> why;
  final double height;

  const _WhyBar({required this.why, this.height = 5});

  @override
  Widget build(BuildContext context) {
    if (why.isEmpty) return const SizedBox.shrink();
    final accent = Theme.of(context).colorScheme.primary;
    final palette = Palette.of(context);
    return ClipRRect(
      borderRadius: BorderRadius.circular(height / 2),
      child: SizedBox(
        height: height,
        child: Row(
          children: [
            for (final (index, w) in why.indexed) ...[
              if (index > 0) const SizedBox(width: 2),
              Expanded(
                flex: max(1, (w.share * 1000).round()),
                child: ColoredBox(
                  color: w.rest > 0 ? palette.border : accent.withValues(alpha: 1 - index * 0.18),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// The seeds' shares with their names, for the top pick
class _WhyList extends StatelessWidget {
  final List<Why> why;

  const _WhyList({required this.why});

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(context.t('discover.why').toUpperCase(),
            style: TextStyle(color: palette.muted, fontSize: 11, fontWeight: FontWeight.w600, letterSpacing: 0.8)),
        const SizedBox(height: 6),
        _WhyBar(why: why, height: 8),
        const SizedBox(height: 6),
        for (final w in why)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 1),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    w.rest > 0 ? context.t('discover.why_rest', {'count': context.number(w.rest)}) : w.name,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: 13, color: w.rest > 0 ? palette.muted : null),
                  ),
                ),
                Text(context.t('discover.why_share', {'value': context.number((w.share * 100).round())}),
                    style: TextStyle(fontSize: 13, color: palette.muted, fontFeatures: const [FontFeature.tabularFigures()])),
              ],
            ),
          ),
      ],
    );
  }
}

/// The menu of a suggestion: leave it out for good
class _HideMenu extends StatelessWidget {
  final Hidden hidden;
  final double size;

  const _HideMenu({required this.hidden, this.size = 20});

  @override
  Widget build(BuildContext context) => PopupMenuButton<void>(
        icon: Icon(Icons.more_vert, size: size, color: Palette.of(context).muted),
        padding: EdgeInsets.zero,
        tooltip: context.t('discover.hide'),
        itemBuilder: (_) => [
          PopupMenuItem(
            onTap: () => _hide(context, hidden),
            child: ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.visibility_off_outlined),
              title: Text(context.t('discover.hide')),
            ),
          ),
        ],
      );
}

/// Hide a suggestion, the next one taking its place, with a moment to take it back
void _hide(BuildContext context, Hidden hidden) {
  final controller = AppScope.read(context);
  final messenger = ScaffoldMessenger.of(context);
  final note = context.t('discover.hidden_note', {'name': hidden.name});
  final undo = context.t('discover.undo');
  controller.hide(hidden);
  messenger
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(
      content: Text(note),
      action: SnackBarAction(label: undo, onPressed: () => controller.show(hidden)),
    ));
}

/// The Discover page, as the desktop app's: artists and songs not played yet, picked by the models from what is
/// played. Worked out once a day, ahead a little after the app opens (HomeScreen), and what is played since is
/// taken out at once.
class DiscoverScreen extends StatefulWidget {
  final DataStore store;
  final Future<void> Function() onRefresh;

  /// Whether the page is the one on display: the page asks for the suggestions then
  final bool active;

  const DiscoverScreen({super.key, required this.store, required this.onRefresh, required this.active});

  @override
  State<DiscoverScreen> createState() => _DiscoverScreenState();
}

class _DiscoverScreenState extends State<DiscoverScreen> {
  Suggestions? _found;
  Object? _error;
  var _working = false;
  var _plays = -1;
  int? _revision;

  @override
  void initState() {
    super.initState();
    widget.store.addListener(_update);
    _update();
  }

  /// The hidden suggestions or the fame setting changed, here or on another device
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final revision = AppScope.of(context).discoverRevision;
    if (_revision != null && revision != _revision) {
      _plays = -1;
      _update();
    }
    _revision = revision;
  }

  @override
  void didUpdateWidget(DiscoverScreen old) {
    super.didUpdateWidget(old);
    if (widget.active && !old.active) _update();
    // A preview stops when the tab is left
    if (!widget.active && old.active) Preview.instance.stop();
  }

  @override
  void dispose() {
    widget.store.removeListener(_update);
    Preview.instance.stop();
    super.dispose();
  }

  /// Asked again when the plays change, which also takes out what was played since
  Future<void> _update() async {
    final store = widget.store;
    if (_working && _plays == -1 && _found != null) {
      // Asked again by a settings change while working: once more when done
      _again = true;
      return;
    }
    if (!widget.active || !store.loaded || _working || store.plays.length == _plays) return;
    _working = true;
    try {
      final found = await discover(store.plays);
      _plays = store.plays.length;
      if (mounted) {
        setState(() {
          _found = found;
          _error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = e);
    } finally {
      _working = false;
      if (_again) {
        _again = false;
        _plays = -1;
        _update();
      }
    }
  }

  var _again = false;

  @override
  Widget build(BuildContext context) {
    final found = _found;
    final palette = Palette.of(context);
    final theme = Theme.of(context);
    return RefreshIndicator(
      onRefresh: widget.onRefresh,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(context.t('discover.heading'), style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700)),
          const SizedBox(height: 2),
          Text(context.t('discover.intro'), style: TextStyle(color: palette.muted)),
          const SizedBox(height: 16),
          if (found == null && _error != null)
            MessageView(icon: Icons.cloud_off, text: context.t('discover.failed'))
          else if (found == null)
            const _DiscoverSkeleton()
          else if (found.isEmpty)
            MessageView(icon: Icons.explore_outlined, text: context.t('recommend.none'))
          else ...[
            Align(
              alignment: Alignment.centerLeft,
              child: SegmentedButton<String>(
                showSelectedIcon: false,
                style: const ButtonStyle(visualDensity: VisualDensity.compact),
                segments: [
                  for (final fame in famePower.keys)
                    ButtonSegment(
                        value: fame, label: Text(context.t('discover.fame.$fame'), maxLines: 1, softWrap: false)),
                ],
                selected: {AppScope.of(context).fame},
                onSelectionChanged: (chosen) => AppScope.read(context).chooseFame(chosen.first),
              ),
            ),
            const SizedBox(height: 12),
            if (found.artists.isNotEmpty) _TopPick(artist: found.artists.first),
            if (found.artists.length > 1) ...[
              const SizedBox(height: 20),
              Text(context.t('discover.artists'), style: theme.textTheme.titleMedium),
              Text(context.t('discover.artists_summary'), style: TextStyle(color: palette.muted, fontSize: 13)),
              const SizedBox(height: 10),
              SizedBox(
                height: 246,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  clipBehavior: Clip.none,
                  itemCount: found.artists.length - 1,
                  separatorBuilder: (_, _) => const SizedBox(width: 10),
                  itemBuilder: (context, index) => _ArtistCard(artist: found.artists[index + 1]),
                ),
              ),
            ],
            const SizedBox(height: 20),
            _SongList(
              title: context.t('discover.new_songs'),
              summary: context.t('discover.new_songs_summary'),
              songs: found.newSongs,
            ),
            const SizedBox(height: 12),
            _SongList(
              title: context.t('discover.known_songs'),
              summary: context.t('discover.known_songs_summary'),
              songs: found.knownSongs,
              onArtist: (artist) => openDetail(context, widget.store, DetailTarget.artist(artist)),
            ),
            if (found.report case final report? when report.rows.isNotEmpty) ...[
              const SizedBox(height: 12),
              _ReportCard(
                report: report,
                onArtist: (artist) => openDetail(context, widget.store, DetailTarget.artist(artist)),
              ),
            ],
            if (AppScope.of(context).hidden case final hidden when hidden.isNotEmpty) ...[
              const SizedBox(height: 12),
              SectionCard(
                title: context.t('discover.hidden_title'),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(context.t('discover.hidden_summary'), style: TextStyle(color: palette.muted, fontSize: 13)),
                    const SizedBox(height: 10),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        for (final item in hidden)
                          ActionChip(
                            avatar: Icon(item.kind == 'artist' ? Icons.person_outline : Icons.music_note_outlined, size: 16),
                            label: Text(item.name),
                            onPressed: () => AppScope.read(context).show(item),
                          ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ],
        ],
      ),
    );
  }
}

/// The closest artist, large over its blurred photo, with its songs
class _TopPick extends StatelessWidget {
  final Item artist;

  const _TopPick({required this.artist});

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final theme = Theme.of(context);
    final name = artist['name'] as String;
    final tracks = (artist['tracks'] as List).cast<Map>();
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Stack(
        children: [
          Positioned.fill(
            child: FutureBuilder<String?>(
              future: Artwork.instance.artistPhoto(name),
              builder: (context, photo) => photo.data == null
                  ? const SizedBox.shrink()
                  : Opacity(
                      opacity: theme.brightness == Brightness.dark ? 0.4 : 0.28,
                      child: BlurredPicture(url: photo.data!),
                    ),
            ),
          ),
          Positioned(
            top: 4,
            right: 4,
            child: _HideMenu(hidden: (kind: 'artist', key: artistMatch(name), name: name)),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    ArtworkImage.artist(artist: name, size: 96),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            context.t('discover.top_pick').toUpperCase(),
                            style: TextStyle(
                                color: palette.muted, fontSize: 11, fontWeight: FontWeight.w600, letterSpacing: 0.8),
                          ),
                          const SizedBox(height: 2),
                          Text(name,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700)),
                          const SizedBox(height: 2),
                          Text(_because(context, _names(artist)), maxLines: 2, style: const TextStyle(fontSize: 13)),
                        ],
                      ),
                    ),
                  ],
                ),
                if (whyOf(artist) case final why when why.isNotEmpty) ...[
                  const SizedBox(height: 14),
                  _WhyList(why: why),
                ],
                const SizedBox(height: 12),
                for (final track in tracks)
                  _TrackRow(artist: track['artist'] as String, title: track['title'] as String),
                const SizedBox(height: 8),
                FilledButton.icon(
                  style: FilledButton.styleFrom(backgroundColor: _spotifyGreen, foregroundColor: Colors.white),
                  onPressed: () => openInSpotify(name),
                  icon: const Icon(Icons.play_arrow_rounded),
                  label: Text(context.t('discover.open_spotify')),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Plays or stops a song's 30 second preview, with a ring filling as it plays
class _PreviewButton extends StatelessWidget {
  final String artist;
  final String title;
  final double size;

  const _PreviewButton({required this.artist, required this.title, this.size = 36});

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final accent = Theme.of(context).colorScheme.primary;
    final preview = Preview.instance;
    return ListenableBuilder(
      listenable: preview,
      builder: (context, _) {
        final state = preview.stateOf(artist, title);
        final active = state == PreviewState.playing || state == PreviewState.loading;
        return Tooltip(
          message: context.t(switch (state) {
            PreviewState.none => 'discover.preview_none',
            PreviewState.idle => 'discover.preview',
            _ => 'discover.preview_stop',
          }),
          child: InkResponse(
            radius: size * 0.7,
            onTap: state == PreviewState.none ? null : () => preview.toggle(artist, title),
            child: SizedBox.square(
              dimension: size,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  SizedBox.square(
                    dimension: size - 6,
                    child: CircularProgressIndicator(
                      value: state == PreviewState.loading ? null : preview.progressOf(artist, title),
                      strokeWidth: 2,
                      color: accent,
                      backgroundColor: palette.muted.withValues(alpha: 0.25),
                    ),
                  ),
                  Icon(active ? Icons.pause_rounded : Icons.play_arrow_rounded,
                      size: size * 0.5,
                      color: state == PreviewState.none
                          ? palette.muted.withValues(alpha: 0.35)
                          : active
                              ? accent
                              : palette.muted),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

/// One of the top pick's songs: its cover and title, opening it in Spotify, and its preview
class _TrackRow extends StatelessWidget {
  final String artist;
  final String title;

  const _TrackRow({required this.artist, required this.title});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Material(
        color: Theme.of(context).colorScheme.surface.withValues(alpha: 0.6),
        borderRadius: BorderRadius.circular(10),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: () => openInSpotify(artist, title),
          child: Padding(
            padding: const EdgeInsets.all(6),
            child: Row(
              children: [
                ArtworkImage.cover(artist: artist, album: '', name: title, size: 40),
                const SizedBox(width: 10),
                Expanded(child: Text(title, maxLines: 1, overflow: TextOverflow.ellipsis)),
                _PreviewButton(artist: artist, title: title),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// A suggested artist in the row: photo, name, why, and their songs
class _ArtistCard extends StatelessWidget {
  final Item artist;

  const _ArtistCard({required this.artist});

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final name = artist['name'] as String;
    final tracks = (artist['tracks'] as List).cast<Map>();
    return SizedBox(
      width: 156,
      child: Card(
        margin: EdgeInsets.zero,
        clipBehavior: Clip.antiAlias,
        child: Stack(
          children: [
            Positioned.fill(
              child: InkWell(
                onTap: () => openInSpotify(name),
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(10, 14, 10, 8),
                  child: Column(
                    children: [
                      ArtworkImage.artist(artist: name, size: 80),
                      const SizedBox(height: 8),
                      Text(name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          textAlign: TextAlign.center,
                          style: const TextStyle(fontWeight: FontWeight.w600)),
                      const SizedBox(height: 2),
                      Text(_because(context, _names(artist)),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          textAlign: TextAlign.center,
                          style: TextStyle(color: palette.muted, fontSize: 11)),
                      const SizedBox(height: 6),
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        child: _WhyBar(why: whyOf(artist), height: 4),
                      ),
                      const Spacer(),
                      for (final track in tracks.take(2))
                        InkWell(
                          borderRadius: BorderRadius.circular(6),
                          onTap: () => openInSpotify(track['artist'] as String, track['title'] as String),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(vertical: 4, horizontal: 2),
                            child: Row(
                              children: [
                                _PreviewButton(artist: track['artist'] as String, title: track['title'] as String, size: 26),
                                const SizedBox(width: 2),
                                Expanded(
                                  child: Text(track['title'] as String,
                                      maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12)),
                                ),
                              ],
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ),
            Positioned(
              top: 0,
              right: 0,
              child: _HideMenu(hidden: (kind: 'artist', key: artistMatch(name), name: name), size: 18),
            ),
          ],
        ),
      ),
    );
  }
}

/// Songs by new artists, or unplayed songs by artists played, whose artist opens their page
class _SongList extends StatelessWidget {
  final String title;
  final String summary;
  final List<Item> songs;
  final void Function(String artist)? onArtist;

  const _SongList({required this.title, required this.summary, required this.songs, this.onArtist});

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    return SectionCard(
      title: title,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(summary, style: TextStyle(color: palette.muted, fontSize: 13)),
          const SizedBox(height: 8),
          if (songs.isEmpty) Text(context.t('discover.songs_none'), style: TextStyle(color: palette.muted)),
          for (final song in songs)
            InkWell(
              borderRadius: BorderRadius.circular(8),
              onTap: () => openInSpotify(song['artist'] as String, song['name'] as String),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Row(
                  children: [
                    ArtworkImage.cover(artist: song['artist'] as String, album: '', name: song['name'] as String, size: 48),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(song['name'] as String,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontWeight: FontWeight.w600)),
                          GestureDetector(
                            onTap: onArtist == null ? null : () => onArtist!(song['artist'] as String),
                            child: Text(
                              song['artist'] as String,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(
                                fontSize: 13,
                                decoration: onArtist == null ? null : TextDecoration.underline,
                                decorationColor: palette.muted,
                              ),
                            ),
                          ),
                          Text(_because(context, _names(song), songs: true),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(color: palette.muted, fontSize: 12)),
                          const SizedBox(height: 4),
                          FractionallySizedBox(widthFactor: 0.6, child: _WhyBar(why: whyOf(song), height: 4)),
                        ],
                      ),
                    ),
                    _PreviewButton(artist: song['artist'] as String, title: song['name'] as String, size: 40),
                    _HideMenu(
                      hidden: (
                        kind: 'song',
                        key: loose(song['key'] as String),
                        name: '${song['artist']} · ${song['name']}',
                      ),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// Which of the artists suggested in the last 30 days were played since
class _ReportCard extends StatelessWidget {
  final Report report;
  final void Function(String artist) onArtist;

  const _ReportCard({required this.report, required this.onArtist});

  @override
  Widget build(BuildContext context) {
    final rows = report.rows;
    final palette = Palette.of(context);
    final theme = Theme.of(context);
    final accent = palette.chart;
    String day(String key) => context.dateFormat('d MMM').format(DateTime.parse(key));
    var summary = context.t('discover.report.summary',
        {'listened': context.number(report.listened), 'suggested': context.number(report.rows.length)});
    if (report.favorites > 0) {
      summary += context.t('discover.report.favorites', {'count': context.number(report.favorites)});
    }
    Color stateColor(ReportState state) => switch (state) {
      ReportState.favorite => Color.lerp(accent, theme.colorScheme.onSurface, 0.35)!,
      ReportState.listened => accent,
      ReportState.untried => palette.border,
    };
    return SectionCard(
      title: context.t('discover.report.title'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(context.number(report.listened),
                  style: theme.textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w600, height: 1)),
              const SizedBox(width: 6),
              Text('/ ${context.number(report.rows.length)}', style: TextStyle(color: palette.muted)),
            ],
          ),
          const SizedBox(height: 4),
          Text(summary, style: TextStyle(color: palette.muted, fontSize: 13)),
          const SizedBox(height: 10),
          Row(children: [
            for (final row in report.rows)
              Expanded(
                child: Container(
                  height: 8,
                  margin: const EdgeInsets.symmetric(horizontal: 2),
                  decoration: BoxDecoration(color: stateColor(row.state), borderRadius: BorderRadius.circular(3)),
                ),
              ),
          ]),
          const SizedBox(height: 8),
          for (final row in rows)
            InkWell(
              borderRadius: BorderRadius.circular(8),
              onTap: () => row.plays > 0 ? onArtist(row.name) : openInSpotify(row.name),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Row(
                  children: [
                    ArtworkImage.artist(artist: row.name, size: 36),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(row.name,
                              maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
                          Text(
                            row.plays > 0
                                ? context.t('discover.report.plays', {'count': context.number(row.plays)})
                                : context.t('discover.report.since', {'day': day(row.day)}),
                            style: TextStyle(color: palette.muted, fontSize: 12),
                          ),
                        ],
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 2),
                      decoration: BoxDecoration(
                        color: row.state == ReportState.untried
                            ? palette.border.withValues(alpha: 0.5)
                            : accent.withValues(alpha: row.state == ReportState.favorite ? 0.3 : 0.16),
                        borderRadius: BorderRadius.circular(99),
                      ),
                      child: Text(
                        context.t('discover.report.${row.state.name}'),
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: row.state == ReportState.untried ? palette.muted : palette.added,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _DiscoverSkeleton extends StatelessWidget {
  const _DiscoverSkeleton();

  @override
  Widget build(BuildContext context) {
    return const Skeleton(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Card(
            child: Padding(
              padding: EdgeInsets.all(16),
              child: Row(children: [
                Bone(width: 96, height: 96, round: true),
                SizedBox(width: 16),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Bone(widthFactor: 0.4, height: 10),
                    SizedBox(height: 8),
                    Bone(widthFactor: 0.7, height: 22),
                    SizedBox(height: 8),
                    Bone(widthFactor: 0.9),
                  ]),
                ),
              ]),
            ),
          ),
          SizedBox(height: 16),
          CardSkeleton(lines: 4),
          SizedBox(height: 12),
          CardSkeleton(lines: 4),
        ],
      ),
    );
  }
}
