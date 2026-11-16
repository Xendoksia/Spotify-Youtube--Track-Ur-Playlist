import 'package:flutter/material.dart';

import '../../data/artwork.dart';
import '../../data/models.dart';
import '../../data/mood.dart';
import '../../data/stats.dart';
import '../../l10n/strings.dart';
import '../../state/data_store.dart';
import '../../theme/palette.dart';
import '../../widgets/artwork_image.dart';
import '../../widgets/cards.dart';
import '../../widgets/format.dart';
import 'listening_chart.dart';

/// Opens the page of a track, artist or album
void openDetail(BuildContext context, DataStore store, DetailTarget target, {int depth = 1}) {
  Navigator.of(context)
      .push(MaterialPageRoute(builder: (_) => DetailScreen(store: store, target: target, depth: depth)));
}

/// One track, artist or album over all time, as the desktop app's detail page: its totals, plays per day or
/// month, and its tracks and albums (an artist) or the album's track list (an album)
class DetailScreen extends StatefulWidget {
  final DataStore store;
  final DetailTarget target;

  /// Its place in the stack of pages, for the pictures' flights (see DetailTarget.hero)
  final int depth;

  const DetailScreen({super.key, required this.store, required this.target, this.depth = 1});

  @override
  State<DetailScreen> createState() => _DetailScreenState();
}

class _DetailScreenState extends State<DetailScreen> {
  /// Deezer's track list of an album page
  Future<List<(String, int)>?>? _tracklist;

  /// The page's picture, for the blurred copy behind it, and its color for the page
  String? _picture;
  final _mood = ValueNotifier<Mood?>(null);

  DetailTarget get target => widget.target;

  @override
  void initState() {
    super.initState();
    if (target.kind == DetailKind.album) _tracklist = Artwork.instance.tracklist(target.artist, target.album);
    _findPicture();
  }

  Future<void> _findPicture() async {
    final artwork = Artwork.instance;
    final url = await switch (target.kind) {
      DetailKind.track => artwork.cover(target.artist, target.album, target.title),
      DetailKind.artist => artwork.artistPhoto(target.artist),
      DetailKind.album => artwork.albumCover(target.artist, target.album),
    };
    if (url == null || !mounted) return;
    setState(() => _picture = url);
    final mood = await moodOf(url);
    if (mood != null && mounted) _mood.value = mood;
  }

  @override
  void dispose() {
    _mood.dispose();
    super.dispose();
  }

  int get _next => widget.depth + 1;

  void _open(DetailTarget other) => openDetail(context, widget.store, other, depth: _next);

  @override
  Widget build(BuildContext context) {
    final plays = target.playsIn(widget.store.plays);
    final detail = Detail.of(plays);
    const gap = SizedBox(height: 12);
    // The whole page in the color of its picture, as the statistics take their number one's
    return MoodWash(
      mood: _mood,
      reach: 0.7,
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(backgroundColor: Colors.transparent),
        body: ListView(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
          children: [
            _Header(
              target: target,
              hero: target.hero(widget.depth),
              onArtist: () => _open(DetailTarget.artist(target.artist)),
              tracklist: _tracklist,
              picture: _picture,
            ),
            gap,
            if (detail != null) ...[
              Row(children: [
                Expanded(child: StatTile(label: context.t('stats.plays'), value: context.number(detail.plays))),
                const SizedBox(width: 8),
                Expanded(child: StatTile(label: context.t('stats.time'), value: context.minutes(detail.minutes))),
              ]),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(child: StatTile(label: context.t('detail.first'), value: context.date(detail.first))),
                const SizedBox(width: 8),
                Expanded(child: StatTile(label: context.t('detail.last'), value: context.date(detail.last))),
              ]),
              gap,
            ],
            if (target.kind == DetailKind.track && target.album.isNotEmpty) ...[
              _AlbumLink(
                target: target,
                hero: DetailTarget.album(target.artist, target.album).hero(_next),
                onTap: () => _open(DetailTarget.album(target.artist, target.album)),
              ),
              gap,
            ],
            if (target.kind == DetailKind.album) ...[_albumTracks(context, plays), gap],
            _chart(context, plays),
            if (target.kind == DetailKind.artist) ...[
              gap,
              SectionCard(
                title: context.t('stats.top_tracks'),
                child: RankedList(
                  rows: topTracks(plays, limit: 15),
                  image: (row) => ArtworkImage.cover(
                      artist: row.artist, album: row.album, name: row.title, hero: heroTag(DetailKind.track, row.key, _next)),
                  onTap: (row) => _open(DetailTarget.ranked(DetailKind.track, row)),
                ),
              ),
              if (topAlbums(plays).isNotEmpty) ...[
                gap,
                SectionCard(
                  title: context.t('stats.top_albums'),
                  child: RankedList(
                    rows: topAlbums(plays),
                    image: (row) => ArtworkImage.album(
                        artist: row.artist, album: row.album, hero: heroTag(DetailKind.album, row.key, _next)),
                    onTap: (row) => _open(DetailTarget.ranked(DetailKind.album, row)),
                  ),
                ),
              ],
            ],
          ],
        ),
      ),
    );
  }

  Widget _chart(BuildContext context, List<Play> plays) {
    final (buckets, daily) = detailBuckets(plays, DateTime.now());
    return SectionCard(
      title: context.t(daily ? 'detail.per_day' : 'detail.per_month'),
      child: ListeningChart.detail(buckets: buckets, daily: daily),
    );
  }

  /// The album's tracks in album order once Deezer's list comes, the played ones until then
  Widget _albumTracks(BuildContext context, List<Play> plays) {
    return FutureBuilder<List<(String, int)>?>(
      future: _tracklist,
      builder: (context, snapshot) {
        final tracklist = snapshot.data;
        final rows = albumTracks(plays, tracklist);
        final heard = rows.where((row) => row.played != null).length;
        return SectionCard(
          title: tracklist == null
              ? context.t('detail.tracks')
              : context.t('detail.album_tracks', {'heard': context.number(heard), 'total': context.number(rows.length)}),
          child: Column(children: [
            for (final (index, row) in rows.indexed)
              _AlbumTrackRow(
                number: tracklist != null && index < tracklist.length ? index + 1 : null,
                track: row,
                onTap: row.played == null
                    ? null
                    : () => _open(DetailTarget(DetailKind.track, row.played!.key, row.played!.title,
                        artist: target.artist, album: target.album)),
              ),
          ]),
        );
      },
    );
  }
}

/// The big picture over a blurred copy of it, the kind, the name in large type rising in, and the artist under a
/// track or album, on a card in the picture's color
class _Header extends StatelessWidget {
  final DetailTarget target;
  final String hero;
  final VoidCallback onArtist;
  final Future<List<(String, int)>?>? tracklist;
  final String? picture;

  const _Header({required this.target, required this.hero, required this.onArtist, this.tracklist, this.picture});

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final mood = MoodColor.of(context);
    final theme = Theme.of(context);
    final surface = theme.colorScheme.surfaceContainer;
    // Light pages keep the blurred picture fainter, so the text over it stays readable
    final blur = theme.brightness == Brightness.dark ? 0.45 : 0.28;
    const size = 200.0;
    final image = switch (target.kind) {
      DetailKind.track =>
        ArtworkImage.cover(artist: target.artist, album: target.album, name: target.title, size: size, hero: hero),
      DetailKind.artist => ArtworkImage.artist(artist: target.artist, size: size, hero: hero),
      DetailKind.album => ArtworkImage.album(artist: target.artist, album: target.album, size: size, hero: hero),
    };
    final text = Column(
      children: [
        Text(
          context.t('detail.${target.kind.name}').toUpperCase(),
          style: TextStyle(color: palette.muted, fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 1.2),
        ),
        const SizedBox(height: 4),
        Text(
          target.title,
          textAlign: TextAlign.center,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: Theme.of(context)
              .textTheme
              .headlineMedium
              ?.copyWith(fontWeight: FontWeight.w700, letterSpacing: -0.5, height: 1.15),
        ),
        if (target.kind != DetailKind.artist)
          TextButton(
            onPressed: onArtist,
            child: Text(target.artist,
                style: TextStyle(color: mood ?? palette.chart, fontSize: 17, fontWeight: FontWeight.w600)),
          ),
        if (tracklist != null)
          FutureBuilder<List<(String, int)>?>(
            future: tracklist,
            builder: (context, snapshot) {
              final tracks = snapshot.data;
              if (tracks == null) return const SizedBox.shrink();
              final minutes = tracks.fold<int>(0, (sum, t) => sum + t.$2) ~/ 60000;
              return Text(
                context.t('detail.album_length', {'tracks': context.number(tracks.length), 'length': context.minutes(minutes)}),
                style: TextStyle(color: palette.muted),
              );
            },
          ),
      ],
    );
    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: mood == null ? surface : Color.lerp(surface, mood, 0.14),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: mood == null ? palette.border : Color.lerp(palette.border, mood, 0.4)!),
      ),
      child: Stack(children: [
        if (picture != null) Positioned.fill(child: Opacity(opacity: blur, child: BlurredPicture(url: picture!))),
        // As wide as the card, so the picture and the name sit in its middle
        Container(
          width: double.infinity,
          padding: const EdgeInsets.fromLTRB(20, 24, 20, 16),
          child: Column(children: [
            DecoratedBox(
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(target.kind == DetailKind.artist ? size : size * 0.12),
                boxShadow: const [BoxShadow(color: Color(0x66000000), blurRadius: 40, offset: Offset(0, 14))],
              ),
              child: image,
            ),
            const SizedBox(height: 18),
            // The name rises in after the picture landed
            TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: 1),
              duration: const Duration(milliseconds: 480),
              curve: const Interval(0.17, 1, curve: Curves.easeOutCubic),
              builder: (context, shown, child) => Opacity(
                opacity: shown,
                child: Transform.translate(offset: Offset(0, 14 * (1 - shown)), child: child),
              ),
              child: text,
            ),
          ]),
        ),
      ]),
    );
  }
}

/// On a track's page: its album, opening the album's page
class _AlbumLink extends StatelessWidget {
  final DetailTarget target;
  final String hero;
  final VoidCallback onTap;

  const _AlbumLink({required this.target, required this.hero, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(children: [
            ArtworkImage.album(artist: target.artist, album: target.album, size: 56, hero: hero),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(context.t('detail.album'), style: TextStyle(color: palette.muted, fontSize: 12)),
                Text(target.album, maxLines: 2, overflow: TextOverflow.ellipsis),
              ]),
            ),
            Text(context.t('detail.open_album'), style: TextStyle(color: palette.chart)),
            Icon(Icons.chevron_right, color: palette.chart),
          ]),
        ),
      ),
    );
  }
}

/// A track of the album: its number and length, and how often it was played ("—" and faded when never)
class _AlbumTrackRow extends StatelessWidget {
  final int? number;
  final AlbumTrack track;
  final VoidCallback? onTap;

  const _AlbumTrackRow({required this.number, required this.track, this.onTap});

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final played = track.played;
    final faded = played == null ? palette.muted : null;
    final length = track.lengthMs;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(children: [
          SizedBox(
            width: 32,
            child: Text(number == null ? '·' : '$number', style: TextStyle(color: palette.muted)),
          ),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(track.title, maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(color: faded)),
              if (length != null && length > 0)
                Text(context.length(length), style: TextStyle(color: palette.muted, fontSize: 13)),
            ]),
          ),
          const SizedBox(width: 12),
          Text(
            played == null ? '—' : context.plays(played.plays),
            style: TextStyle(color: faded),
          ),
        ]),
      ),
    );
  }
}
