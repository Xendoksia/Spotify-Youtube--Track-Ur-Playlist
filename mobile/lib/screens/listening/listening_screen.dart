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
        Expanded(child: StatTile.count(label: context.t('stats.plays'), count: summary.plays, format: context.number)),
        const SizedBox(width: 8),
        Expanded(child: StatTile.count(label: context.t('stats.time'), count: summary.minutes, format: context.minutes)),
      ]),
      const SizedBox(height: 8),
      Row(children: [
        Expanded(child: StatTile.count(label: context.t('stats.tracks'), count: summary.tracks, format: context.number)),
        const SizedBox(width: 8),
        Expanded(
            child: StatTile.count(label: context.t('stats.artists'), count: summary.artists, format: context.number)),
      ]),
      gap,
      if (plays.isEmpty)
        MessageView(icon: Icons.music_off, text: context.t('stats.empty'))
      else ...[
        SectionCard(
          title: context.t('stats.chart'),
          child: ListeningChart(period: _period, buckets: buckets(_period, range, plays)),
        ),
        gap,
        SectionCard(
          title: context.t('stats.top_tracks'),
          child: RankedList(
            rows: topTracks(plays),
            change: rankChanges(all, _period, _offset, now, trackKeyOf),
            image: (row) => ArtworkImage.cover(
                artist: row.artist, album: row.album, name: row.title, hero: heroTag(DetailKind.track, row.key, 1)),
            onTap: (row) => openDetail(context, widget.store, DetailTarget.ranked(DetailKind.track, row)),
          ),
        ),
        gap,
        SectionCard(
          title: context.t('stats.top_artists'),
          child: RankedList(
            rows: topArtists(plays),
            change: rankChanges(all, _period, _offset, now, artistKeyOf),
            image: (row) => ArtworkImage.artist(artist: row.artist, hero: heroTag(DetailKind.artist, row.key, 1)),
            onTap: (row) => openDetail(context, widget.store, DetailTarget.ranked(DetailKind.artist, row)),
          ),
        ),
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
      ],
      gap,
      SectionCard(title: context.t('stats.recent'), child: _RecentPlays(
            plays: all,
            onTap: (play) => openDetail(context, widget.store, DetailTarget.track(play)),
          )),
    ];
  }
}

/// The latest plays of any period, under their day
class _RecentPlays extends StatelessWidget {
  final List<Play> plays;
  final void Function(Play play) onTap;

  const _RecentPlays({required this.plays, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final muted = Palette.of(context).muted;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final MapEntry(key: day, value: dayPlays) in byDay(plays)) ...[
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
      ],
    );
  }
}
