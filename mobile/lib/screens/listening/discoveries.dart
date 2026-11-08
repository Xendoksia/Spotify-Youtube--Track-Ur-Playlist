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

const discoveryCount = 5;
const forgottenDays = 30;
const forgottenMinPlays = 3;

/// Tracks and artists heard for the first time ever in the period, as the desktop app's discoveries card. Over all
/// time everything is new, so the tracks once played a lot but not lately take its place.
class Discoveries extends StatelessWidget {
  final DataStore store;
  final Period period;
  final DateRange range;

  /// The period's plays
  final List<Play> plays;

  const Discoveries({super.key, required this.store, required this.period, required this.range, required this.plays});

  @override
  Widget build(BuildContext context) => period == Period.all ? _forgotten(context) : _discoveries(context);

  Widget _discoveries(BuildContext context) {
    final all = store.plays;
    final tracks = newTracks(all, range);
    final artists = newArtists(all, range);
    final muted = Palette.of(context).muted;
    String summary;
    if (tracks.isEmpty && artists.isEmpty) {
      summary = context.t('stats.discoveries.none');
    } else {
      summary = context.t('stats.discoveries.summary',
          {'tracks': context.number(tracks.length), 'artists': context.number(artists.length)});
      if (plays.isNotEmpty) {
        final share = (tracks.fold<int>(0, (sum, d) => sum + d.row.plays) * 100 / plays.length).round();
        summary += '  ·  ${context.t('stats.discoveries.share', {
              'percent': context.t('stats.percent', {'value': share})
            })}';
      }
      final first = all.map((p) => p.playedAt).reduce((a, b) => a.isBefore(b) ? a : b);
      if (!first.isBefore(range.start)) summary += '\n${context.t('stats.discoveries.first_period')}';
    }
    return SectionCard(
      title: context.t('stats.discoveries'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(summary, style: TextStyle(color: muted, fontSize: 13)),
          if (tracks.isNotEmpty) ...[
            _heading(context, 'stats.new_tracks'),
            RankedList(
              rows: [for (final d in tracks.take(discoveryCount)) d.row],
              image: (row) => ArtworkImage.cover(artist: row.artist, album: row.album, name: row.title),
              onTap: (row) => openDetail(context, store, DetailTarget.ranked(DetailKind.track, row)),
            ),
          ],
          if (artists.isNotEmpty) ...[
            _heading(context, 'stats.new_artists'),
            RankedList(
              rows: [
                for (final d in artists.take(discoveryCount))
                  Ranked(d.row.key, d.row.title, _tracks(context, d.tracks), d.row.plays, d.row.minutes,
                      artist: d.row.artist),
              ],
              image: (row) => ArtworkImage.artist(artist: row.artist),
              onTap: (row) => openDetail(context, store, DetailTarget.artist(row.artist)),
            ),
          ],
        ],
      ),
    );
  }

  Widget _forgotten(BuildContext context) {
    final now = DateTime.now();
    final rows = forgotten(store.plays, now, days: forgottenDays, minPlays: forgottenMinPlays);
    final muted = Palette.of(context).muted;
    return SectionCard(
      title: context.t('stats.forgotten'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            context.t(rows.isEmpty ? 'stats.forgotten.none' : 'stats.forgotten.summary',
                {'days': forgottenDays, 'plays': forgottenMinPlays}),
            style: TextStyle(color: muted, fontSize: 13),
          ),
          if (rows.isNotEmpty) ...[
            const SizedBox(height: 8),
            RankedList(
              rows: [
                for (final d in rows)
                  Ranked(
                      d.row.key,
                      d.row.title,
                      '${d.row.artist}  ·  ${context.t('stats.forgotten.last', {
                            'date': context.date(d.at),
                            'days': context.number(now.difference(d.at).inDays)
                          })}',
                      d.row.plays,
                      d.row.minutes,
                      artist: d.row.artist,
                      album: d.row.album),
              ],
              image: (row) => ArtworkImage.cover(artist: row.artist, album: row.album, name: row.title),
              onTap: (row) => openDetail(context, store, DetailTarget.ranked(DetailKind.track, row)),
            ),
          ],
        ],
      ),
    );
  }

  static String _tracks(BuildContext context, int count) => count == 1
      ? context.t('stats.different_tracks_one')
      : context.t('stats.different_tracks', {'count': context.number(count)});

  static Widget _heading(BuildContext context, String key) => Padding(
        padding: const EdgeInsets.only(top: 12, bottom: 4),
        child: Text(context.t(key), style: const TextStyle(fontWeight: FontWeight.w600)),
      );
}
