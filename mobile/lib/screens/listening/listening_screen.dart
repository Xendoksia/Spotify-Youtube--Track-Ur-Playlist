import 'package:flutter/material.dart';

import '../../data/models.dart';
import '../../data/stats.dart';
import '../../l10n/strings.dart';
import '../../state/data_store.dart';
import '../../theme/palette.dart';
import '../../widgets/artwork_image.dart';
import '../../widgets/cards.dart';
import '../../widgets/format.dart';
import 'detail_screen.dart';
import 'listening_chart.dart';
import 'period_bar.dart';

/// The statistics of the plays synced from the desktop app, by week, month, year or all time
class ListeningScreen extends StatefulWidget {
  final DataStore store;
  final Future<void> Function() onRefresh;

  const ListeningScreen({super.key, required this.store, required this.onRefresh});

  @override
  State<ListeningScreen> createState() => _ListeningScreenState();
}

class _ListeningScreenState extends State<ListeningScreen> {
  var _period = Period.month;
  var _offset = 0;
  var _recentShown = recentStep;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.store,
      builder: (context, _) {
        final store = widget.store;
        if (!store.loaded) {
          return Center(
            child: store.error != null
                ? MessageView(
                    icon: Icons.cloud_off,
                    text: context.t('load.failed', {'error': store.error!}),
                    action: context.t('load.retry'),
                    onAction: widget.onRefresh,
                  )
                : const CircularProgressIndicator(),
          );
        }
        return RefreshIndicator(
          onRefresh: widget.onRefresh,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: store.plays.isEmpty
                ? [MessageView(icon: Icons.headphones, text: context.t('stats.none_yet'))]
                : _content(context, store.plays),
          ),
        );
      },
    );
  }

  List<Widget> _content(BuildContext context, List<Play> all) {
    final now = DateTime.now();
    final range = periodRange(_period, _offset, now);
    final plays = playsIn(all, range);
    final summary = Summary.of(plays);
    final previous = previousSummary(all, _period, _offset, now);
    final tracks = topTracks(plays);
    final artists = topArtists(plays);
    final trackChange = rankChanges(all, _period, _offset, now, trackKeyOf);
    final artistChange = rankChanges(all, _period, _offset, now, artistKeyOf);
    const gap = SizedBox(height: 12);
    return [
      PeriodBar(
        period: _period,
        offset: _offset,
        range: range,
        onPeriod: (period) => setState(() {
          _period = period;
          _offset = 0;
        }),
        onOffset: (offset) => setState(() => _offset = offset),
      ),
      gap,
      // Rows rather than a grid with a fixed aspect ratio, so the tiles grow with the phone's font size
      Row(children: [
        Expanded(child: _tile(context, 'stats.plays', summary.plays, previous?.plays, context.number)),
        const SizedBox(width: 8),
        Expanded(child: _tile(context, 'stats.time', summary.minutes, previous?.minutes, context.minutes)),
      ]),
      const SizedBox(height: 8),
      Row(children: [
        Expanded(child: _tile(context, 'stats.tracks', summary.tracks, previous?.tracks, context.number)),
        const SizedBox(width: 8),
        Expanded(child: _tile(context, 'stats.artists', summary.artists, previous?.artists, context.number)),
      ]),
      gap,
      if (plays.isEmpty)
        MessageView(icon: Icons.music_off, text: context.t('stats.empty'))
      else ...[
        _trackHero(context, tracks.first, trackChange),
        const SizedBox(height: 8),
        _artistHero(context, artists.first, plays, artistChange),
        if (tracks.length > 1) ...[
          gap,
          SectionCard(
            title: context.t('stats.top_tracks'),
            child: RankedList(
              rows: tracks.sublist(1),
              firstRank: 2,
              change: trackChange,
              image: (row) => ArtworkImage.cover(
                  artist: row.artist, album: row.album, name: row.title, hero: heroTag(DetailKind.track, row.key, 1)),
              onTap: (row) => openDetail(context, widget.store, DetailTarget.ranked(DetailKind.track, row)),
            ),
          ),
        ],
        if (artists.length > 1) ...[
          gap,
          SectionCard(
            title: context.t('stats.top_artists'),
            child: RankedList(
              rows: artists.sublist(1),
              firstRank: 2,
              change: artistChange,
              image: (row) => ArtworkImage.artist(artist: row.artist, hero: heroTag(DetailKind.artist, row.key, 1)),
              onTap: (row) => openDetail(context, widget.store, DetailTarget.ranked(DetailKind.artist, row)),
            ),
          ),
        ],
        gap,
        SectionCard(
          title: context.t('stats.top_albums'),
          child: RankedList(
            rows: topAlbums(plays),
            image: (row) =>
                ArtworkImage.album(artist: row.artist, album: row.album, hero: heroTag(DetailKind.album, row.key, 1)),
            onTap: (row) => openDetail(context, widget.store, DetailTarget.ranked(DetailKind.album, row)),
          ),
        ),
        gap,
        SectionCard(
          title: context.t('stats.chart'),
          child: ListeningChart(period: _period, buckets: buckets(_period, range, plays)),
        ),
        gap,
        SectionCard(
          title: context.t('stats.hours'),
          child: ListeningChart(
            period: Period.all,
            plays: true,
            buckets: [
              for (final (hour, count) in playsPerHour(plays).indexed) Bucket(DateTime(2000, 1, 1, hour), 0, count),
            ],
            label: (context, start) => start.hour.toString().padLeft(2, '0'),
          ),
        ),
      ],
      gap,
      SectionCard(
        title: context.t('stats.recent'),
        child: _RecentPlays(
          plays: all,
          shown: _recentShown,
          onMore: () => setState(() => _recentShown += recentStep),
          onTap: (play) => openDetail(context, widget.store, DetailTarget.track(play)),
        ),
      ),
    ];
  }

  StatTile _tile(BuildContext context, String label, int value, int? before, String Function(int) format) {
    final change = before == null ? null : percentChange(value, before);
    String? note;
    if (change != null) {
      final arrow = change > 0 ? '▲' : change < 0 ? '▼' : '=';
      note = '$arrow ${context.t('stats.percent', {'value': change.abs()})}  ${context.t('stats.vs.${_period.name}')}';
    }
    return StatTile.count(label: context.t(label), count: value, format: format, note: note);
  }

  String _detail(BuildContext context, Ranked row) =>
      [context.plays(row.plays), if (row.minutes > 0) context.minutes(row.minutes)].join('  ·  ');

  Widget _trackHero(BuildContext context, Ranked top, RankChange? Function(String, int) change) => HeroCard(
        caption: context.t('stats.hero.track'),
        title: top.title,
        subtitle: top.artist,
        detail: _detail(context, top),
        change: changeText(context, change(top.key, 1), 1),
        image: ArtworkImage.cover(
            artist: top.artist, album: top.album, name: top.title, size: 88, hero: heroTag(DetailKind.track, top.key, 1)),
        onTap: () => openDetail(context, widget.store, DetailTarget.ranked(DetailKind.track, top)),
      );

  Widget _artistHero(BuildContext context, Ranked top, List<Play> plays, RankChange? Function(String, int) change) {
    final tracks = plays.where((p) => p.artistKey == top.key).map((p) => p.trackKey).toSet().length;
    return HeroCard(
      caption: context.t('stats.hero.artist'),
      title: top.title,
      subtitle: tracks == 1
          ? context.t('stats.different_tracks_one')
          : context.t('stats.different_tracks', {'count': context.number(tracks)}),
      detail: _detail(context, top),
      change: changeText(context, change(top.key, 1), 1),
      image: ArtworkImage.artist(artist: top.artist, size: 88, hero: heroTag(DetailKind.artist, top.key, 1)),
      onTap: () => openDetail(context, widget.store, DetailTarget.ranked(DetailKind.artist, top)),
    );
  }
}

/// How many recent plays show at first, and how many more each tap on "Show more" adds
const recentStep = 20;

/// The latest plays of any period, under their day
class _RecentPlays extends StatelessWidget {
  final List<Play> plays;

  /// How many of the latest plays show; [onMore] shows more
  final int shown;
  final VoidCallback onMore;
  final void Function(Play play) onTap;

  const _RecentPlays({required this.plays, required this.shown, required this.onMore, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final muted = Palette.of(context).muted;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final MapEntry(key: day, value: dayPlays) in byDay(plays, limit: shown)) ...[
          Padding(
            padding: const EdgeInsets.only(top: 8, bottom: 4),
            child: Text(context.day(day), style: TextStyle(color: muted, fontWeight: FontWeight.w600)),
          ),
          for (final play in dayPlays)
            InkWell(
              onTap: () => onTap(play),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  children: [
                    SizedBox(width: 48, child: Text(context.time(play.playedAt), style: TextStyle(color: muted))),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(play.name, maxLines: 1, overflow: TextOverflow.ellipsis),
                          Text(play.artist,
                              maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(color: muted, fontSize: 13)),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
        ],
        if (plays.length > shown)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: OutlinedButton(onPressed: onMore, child: Text(context.t('stats.recent_more'))),
          ),
      ],
    );
  }
}
