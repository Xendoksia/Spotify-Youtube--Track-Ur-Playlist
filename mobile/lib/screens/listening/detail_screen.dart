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
import '../../widgets/day_curve.dart';
import '../../widgets/format.dart';
import '../../widgets/rank_journey.dart';
import '../../widgets/timeline_curve.dart';
import '../../widgets/vinyl.dart';
import 'listening_chart.dart';

/// Opens the page of a track, artist or album
Future<void> openDetail(BuildContext context, DataStore store, DetailTarget target, {int depth = 1}) {
  return Navigator.of(context).push(
    MaterialPageRoute(
      builder: (_) => DetailScreen(store: store, target: target, depth: depth),
    ),
  );
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

  /// The two colors of the page's curves, which a mostly grey picture's logo still gives (paletteOf)
  final _palette = ValueNotifier<Mood?>(null);

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
    final palette = await paletteOf(url);
    if (palette != null && mounted) _palette.value = palette;
  }

  @override
  void dispose() {
    _mood.dispose();
    _palette.dispose();
    super.dispose();
  }

  int get _next => widget.depth + 1;

  /// The curves' two colors: the picture's, or the charts' green with a soft grey for a picture without any color
  (Color, Color) _curveColors(BuildContext context) {
    final palette = Palette.of(context);
    final brightness = Theme.of(context).brightness;
    final colors = _palette.value;
    if (colors == null) return (palette.chart, Color.lerp(palette.muted, palette.chart, 0.15)!);
    return (colors.color(brightness), colors.color2(brightness));
  }

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
        body: ValueListenableBuilder<Mood?>(
          valueListenable: _palette,
          builder: (context, _, _) => ListView(
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
                Row(
                  children: [
                    Expanded(
                      child: StatTile(label: context.t('stats.plays'), value: context.number(detail.plays)),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: StatTile(label: context.t('stats.time'), value: context.minutes(detail.minutes)),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: StatTile(label: context.t('detail.first'), value: context.date(detail.first)),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: StatTile(label: context.t('detail.last'), value: context.date(detail.last)),
                    ),
                  ],
                ),
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
              if (target.kind == DetailKind.track && plays.isNotEmpty) ...[
                _hours(context, plays),
                gap,
                _highlights(context, plays),
                gap,
                _weekdays(context, plays),
                gap,
              ],
              if (target.kind == DetailKind.album) ...[_albumVinyl(context, plays), gap, _albumTracks(context, plays)],
              if (target.kind != DetailKind.album) _chart(context, plays),
              if (target.kind == DetailKind.artist) ...[
                gap,
                SectionCard(
                  title: context.t('stats.top_tracks'),
                  child: RankedList(
                    rows: topTracks(plays, limit: 15),
                    image: (row) => ArtworkImage.cover(
                      artist: row.artist,
                      album: row.album,
                      name: row.title,
                      hero: heroTag(DetailKind.track, row.key, _next),
                    ),
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
                        artist: row.artist,
                        album: row.album,
                        hero: heroTag(DetailKind.album, row.key, _next),
                      ),
                      onTap: (row) => _open(DetailTarget.ranked(DetailKind.album, row)),
                    ),
                  ),
                ],
              ],
            ],
          ),
        ),
      ),
    );
  }

  /// When the track is played: the curve of its hours, with the part of the day it is mostly played in
  Widget _hours(BuildContext context, List<Play> plays) {
    final hours = playsPerHour(plays);
    final part = dayPart(hours);
    final (color, color2) = _curveColors(context);
    return SectionCard(
      title: context.t('detail.track_hours'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            context.t(part == null ? 'detail.hours.spread' : 'detail.hours.$part'),
            style: TextStyle(color: Palette.of(context).muted, fontSize: 13),
          ),
          const SizedBox(height: 12),
          DayCurve(hours: hours, color: color, color2: color2),
        ],
      ),
    );
  }

  /// The track's place among all tracks, the day it was played most and its most days in a row
  Widget _highlights(BuildContext context, List<Play> plays) {
    final palette = Palette.of(context);
    final color = _curveColors(context).$1;
    final ranked = topTracks(widget.store.plays, limit: 1 << 30);
    final rank = ranked.indexWhere((row) => row.key == plays.first.trackKey) + 1;
    final (day, count) = bestDay(plays)!;
    final run = longestRun(plays.map((p) => p.playedAt));
    Widget row(IconData icon, String label, String value) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(color: color.withValues(alpha: 0.18), borderRadius: BorderRadius.circular(12)),
            child: Icon(icon, size: 20, color: color),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: TextStyle(color: palette.muted, fontSize: 13)),
                Text(value, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
              ],
            ),
          ),
        ],
      ),
    );
    return SectionCard(
      title: context.t('detail.highlights'),
      child: Column(
        children: [
          if (rank > 0)
            row(
              Icons.star_rounded,
              context.t('detail.highlights.rank'),
              context.t('detail.highlights.rank_value', {
                'rank': context.number(rank),
                'total': context.number(ranked.length),
              }),
            ),
          row(
            Icons.calendar_today_rounded,
            context.t('detail.highlights.best_day'),
            '${context.dateFormat('d MMMM y').format(day)}  ·  ${context.plays(count)}',
          ),
          row(
            Icons.flag_rounded,
            context.t('detail.highlights.run'),
            context.t(run == 1 ? 'detail.highlights.day_one' : 'detail.highlights.days', {'days': context.number(run)}),
          ),
        ],
      ),
    );
  }

  /// Plays per day of the week, the day played most on standing out in the page's color
  Widget _weekdays(BuildContext context, List<Play> plays) {
    final palette = Palette.of(context);
    final color = _curveColors(context).$1;
    final days = playsPerWeekday(plays);
    final most = days.reduce((a, b) => a > b ? a : b);
    var peak = 0;
    for (var day = 1; day < 7; day++) {
      if (days[day] > days[peak]) peak = day;
    }
    // 2 November 2026 is a Monday: the names of the week's days from it, in the app's language
    String name(int day, String pattern) => context.dateFormat(pattern).format(DateTime(2026, 11, 2 + day));
    TextStyle label(int day) => TextStyle(
      color: day == peak ? null : palette.muted,
      fontSize: 12,
      fontWeight: day == peak ? FontWeight.w700 : FontWeight.normal,
    );
    return SectionCard(
      title: context.t('detail.weekdays'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            context.t('detail.weekdays.peak', {'day': name(peak, 'EEEE')}),
            style: TextStyle(color: palette.muted, fontSize: 13),
          ),
          const SizedBox(height: 12),
          SizedBox(
            height: 150,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                for (var day = 0; day < 7; day++)
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 4),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.end,
                        children: [
                          Text(days[day] > 0 ? context.number(days[day]) : '', style: label(day)),
                          const SizedBox(height: 4),
                          Container(
                            height: 4 + 96 * (most == 0 ? 0 : days[day] / most),
                            decoration: BoxDecoration(
                              color: day == peak ? color : color.withValues(alpha: 0.4),
                              borderRadius: BorderRadius.circular(10),
                            ),
                          ),
                          const SizedBox(height: 6),
                          Text(name(day, 'EEE'), style: label(day)),
                        ],
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _chart(BuildContext context, List<Play> plays) {
    final now = DateTime.now();
    if (target.kind == DetailKind.track && plays.isNotEmpty) {
      // The track's place among all tracks over the fill of its plays so far, in the cover's two colors
      final (points, daily) = journeyOf(widget.store.plays, plays.first.trackKey, now);
      final (color, color2) = _curveColors(context);
      return SectionCard(
        title: context.t('detail.journey'),
        child: RankJourney(points: points, daily: daily, color: color, color2: color2),
      );
    }
    final (buckets, daily) = detailBuckets(plays, now);
    if (target.kind == DetailKind.artist && plays.isNotEmpty) {
      // An artist's plays as a curve that draws itself in the picture's two colors, with how the last week went
      final began = widget.store.plays.map((p) => p.playedAt).reduce((a, b) => b.isBefore(a) ? b : a);
      final (color, color2) = _curveColors(context);
      return SectionCard(
        title: context.t(daily ? 'detail.per_day' : 'detail.per_month'),
        child: TimelineCurve(
          buckets: buckets,
          daily: daily,
          trend: trendOf(plays, began, now),
          color: color,
          color2: color2,
        ),
      );
    }
    return SectionCard(
      title: context.t(daily ? 'detail.per_day' : 'detail.per_month'),
      child: ListeningChart.detail(buckets: buckets, daily: daily),
    );
  }

  /// The album's tracks in album order once Deezer's list comes, the played ones until then
  /// The album as a record of its tracks in album order, each slice as long as it was played
  Widget _albumVinyl(BuildContext context, List<Play> plays) {
    return FutureBuilder<List<(String, int)>?>(
      future: _tracklist,
      builder: (context, snapshot) {
        final (color, color2) = _curveColors(context);
        return SectionCard(
          title: context.t('detail.vinyl'),
          child: Vinyl(
            tracks: albumTracks(plays, snapshot.data),
            complete: snapshot.data != null,
            color: color,
            color2: color2,
            onOpen: (track) => _open(
              DetailTarget(
                DetailKind.track,
                track.played!.key,
                track.played!.title,
                artist: target.artist,
                album: target.album,
              ),
            ),
          ),
        );
      },
    );
  }

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
              : context.t('detail.album_tracks', {
                  'heard': context.number(heard),
                  'total': context.number(rows.length),
                }),
          child: Column(
            children: [
              for (final (index, row) in rows.indexed)
                _AlbumTrackRow(
                  number: tracklist != null && index < tracklist.length ? index + 1 : null,
                  track: row,
                  onTap: row.played == null
                      ? null
                      : () => _open(
                          DetailTarget(
                            DetailKind.track,
                            row.played!.key,
                            row.played!.title,
                            artist: target.artist,
                            album: target.album,
                          ),
                        ),
                ),
            ],
          ),
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
      DetailKind.track => ArtworkImage.cover(
        artist: target.artist,
        album: target.album,
        name: target.title,
        size: size,
        hero: hero,
      ),
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
          style: Theme.of(context).textTheme.headlineMedium
              ?.copyWith(fontWeight: FontWeight.w700, letterSpacing: -0.5, height: 1.15),
        ),
        if (target.kind != DetailKind.artist)
          TextButton(
            onPressed: onArtist,
            child: Text(
              target.artist,
              style: TextStyle(color: mood ?? palette.chart, fontSize: 17, fontWeight: FontWeight.w600),
            ),
          ),
        if (tracklist != null)
          FutureBuilder<List<(String, int)>?>(
            future: tracklist,
            builder: (context, snapshot) {
              final tracks = snapshot.data;
              if (tracks == null) return const SizedBox.shrink();
              final minutes = tracks.fold<int>(0, (sum, t) => sum + t.$2) ~/ 60000;
              return Text(
                context.t('detail.album_length', {
                  'tracks': context.number(tracks.length),
                  'length': context.minutes(minutes),
                }),
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
      child: Stack(
        children: [
          if (picture != null)
            Positioned.fill(
              child: Opacity(
                opacity: blur,
                child: BlurredPicture(url: picture!),
              ),
            ),
          // As wide as the card, so the picture and the name sit in its middle
          Container(
            width: double.infinity,
            padding: const EdgeInsets.fromLTRB(20, 24, 20, 16),
            child: Column(
              children: [
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
              ],
            ),
          ),
        ],
      ),
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
          child: Row(
            children: [
              ArtworkImage.album(artist: target.artist, album: target.album, size: 56, hero: hero),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(context.t('detail.album'), style: TextStyle(color: palette.muted, fontSize: 12)),
                    Text(target.album, maxLines: 2, overflow: TextOverflow.ellipsis),
                  ],
                ),
              ),
              Text(context.t('detail.open_album'), style: TextStyle(color: palette.chart)),
              Icon(Icons.chevron_right, color: palette.chart),
            ],
          ),
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
        child: Row(
          children: [
            SizedBox(
              width: 32,
              child: Text(number == null ? '·' : '$number', style: TextStyle(color: palette.muted)),
            ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    track.title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(color: faded),
                  ),
                  if (length != null && length > 0)
                    Text(context.length(length), style: TextStyle(color: palette.muted, fontSize: 13)),
                ],
              ),
            ),
            const SizedBox(width: 12),
            Text(played == null ? '—' : context.plays(played.plays), style: TextStyle(color: faded)),
          ],
        ),
      ),
    );
  }
}
