import 'package:flutter/material.dart';

import '../../data/discover.dart';
import '../../data/models.dart';
import '../../data/stats.dart';
import '../../l10n/strings.dart';
import '../../theme/palette.dart';
import '../../widgets/artwork_image.dart';
import '../../widgets/cards.dart';
import '../discover_screen.dart' show openInSpotify;

/// What the suggestion models find most alike to a track or an artist, as on the desktop app's pages: the played
/// ones dimmed and opening their page, the others opening in Spotify. Nothing when the model does not know it.
class AlikeCard extends StatefulWidget {
  final DetailTarget target;
  final List<Play> plays;
  final void Function(DetailTarget target) onOpen;

  const AlikeCard({super.key, required this.target, required this.plays, required this.onOpen});

  @override
  State<AlikeCard> createState() => _AlikeCardState();
}

class _AlikeCardState extends State<AlikeCard> {
  late final Future<List<Alike>> _found = widget.target.kind == DetailKind.track
      ? ModelWorker.instance.songs(widget.target.artist, widget.target.title,
          {for (final play in widget.plays) songKey(play.artist, play.name)})
      : ModelWorker.instance.artists(widget.target.artist);

  @override
  Widget build(BuildContext context) {
    final songs = widget.target.kind == DetailKind.track;
    return FutureBuilder<List<Alike>>(
      future: _found,
      builder: (context, found) {
        final rows = found.data ?? const [];
        if (rows.isEmpty) return const SizedBox.shrink();
        // The played songs and artists by their model key, to open their page
        final playedSongs = {for (final play in widget.plays) songKey(play.artist, play.name): play};
        final playedArtists = {
          for (final play in widget.plays)
            for (final part in creditParts(play.artist)) artistMatch(part): part,
        };
        final palette = Palette.of(context);
        return Padding(
          padding: const EdgeInsets.only(top: 12),
          child: SectionCard(
            title: context.t(songs ? 'detail.alike.track' : 'detail.alike.artist'),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  context.t(songs ? 'detail.alike.track_summary' : 'detail.alike.artist_summary',
                      {'name': widget.target.title}),
                  style: TextStyle(color: palette.muted, fontSize: 13),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  height: songs ? 176 : 150,
                  child: ListView.separated(
                    scrollDirection: Axis.horizontal,
                    itemCount: rows.length,
                    separatorBuilder: (_, _) => const SizedBox(width: 12),
                    itemBuilder: (context, index) {
                      final row = rows[index];
                      final play = songs ? playedSongs[row.key] : null;
                      final artist = songs ? null : playedArtists[row.key];
                      final played = play != null || artist != null;
                      return SizedBox(
                        width: 112,
                        child: InkWell(
                          borderRadius: BorderRadius.circular(10),
                          onTap: () {
                            if (play != null) {
                              widget.onOpen(DetailTarget.track(play));
                            } else if (artist != null) {
                              widget.onOpen(DetailTarget.artist(artist));
                            } else {
                              openInSpotify(row.artist, row.title);
                            }
                          },
                          child: Column(
                            crossAxisAlignment: songs ? CrossAxisAlignment.start : CrossAxisAlignment.center,
                            children: [
                              Opacity(
                                opacity: played ? 0.55 : 1,
                                child: songs
                                    ? ArtworkImage.cover(artist: row.artist, album: '', name: row.title, size: 112)
                                    : ArtworkImage.artist(artist: row.artist, size: 88),
                              ),
                              const SizedBox(height: 6),
                              Text(songs ? row.title : row.artist,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  textAlign: songs ? TextAlign.start : TextAlign.center,
                                  style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                              if (songs)
                                Text(row.artist,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(color: palette.muted, fontSize: 12)),
                              if (played)
                                Text(context.t(songs ? 'detail.alike.played_song' : 'detail.alike.played_artist'),
                                    style: TextStyle(color: palette.muted, fontSize: 11, fontWeight: FontWeight.w600)),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
