import 'dart:async';

import 'package:flutter/material.dart';

import '../data/now_playing.dart';
import '../data/stats.dart';
import '../l10n/strings.dart';
import '../screens/listening/detail_screen.dart';
import '../state/data_store.dart';
import '../theme/palette.dart';
import 'artwork_image.dart';
import 'format.dart';

/// A strip above the bottom bar with the song Spotify plays on the phone, as the desktop app's mini player:
/// cover, title, artist, the time into the song with a progress line. Tapping it opens the song's page once
/// it has plays.
class MiniPlayer extends StatefulWidget {
  final NowPlaying nowPlaying;
  final DataStore store;

  const MiniPlayer({super.key, required this.nowPlaying, required this.store});

  @override
  State<MiniPlayer> createState() => _MiniPlayerState();
}

class _MiniPlayerState extends State<MiniPlayer> {
  /// Moves the clock on each second while the song plays
  Timer? _tick;

  @override
  void initState() {
    super.initState();
    widget.nowPlaying.addListener(_changed);
    _changed();
  }

  void _changed() {
    final playing = widget.nowPlaying.song?.playing ?? false;
    if (playing && _tick == null) {
      _tick = Timer.periodic(const Duration(seconds: 1), (_) => setState(() {}));
    } else if (!playing) {
      _tick?.cancel();
      _tick = null;
    }
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    widget.nowPlaying.removeListener(_changed);
    _tick?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final song = widget.nowPlaying.song;
    return AnimatedSize(
      duration: changeDuration,
      curve: changeCurve,
      alignment: Alignment.bottomCenter,
      child: song == null ? const SizedBox(width: double.infinity) : _strip(context, song),
    );
  }

  Widget _strip(BuildContext context, Song song) {
    final palette = Palette.of(context);
    final theme = Theme.of(context);
    final position = song.positionAtTime(DateTime.now());
    final duration = song.duration;
    final time = position == null
        ? ''
        : duration == null
            ? context.length(position)
            : '${context.length(position)} / ${context.length(duration)}';
    final state = song.playing ? palette.added : palette.muted;
    final hasPage = widget.store.plays.any((p) => p.trackKey == song.trackKey);
    return Material(
      color: theme.colorScheme.surfaceContainer,
      child: InkWell(
        onTap: hasPage
            ? () => openDetail(context, widget.store,
                DetailTarget(DetailKind.track, song.trackKey, song.title, artist: song.artist, album: song.album))
            : null,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Divider(height: 1, thickness: 1, color: palette.border),
            LinearProgressIndicator(
              value: position != null && duration != null && duration > 0 ? position / duration : 0,
              minHeight: 3,
              color: palette.chart,
              backgroundColor: palette.border,
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
              child: Row(
                children: [
                  ArtworkImage.cover(artist: song.artist, album: song.album, name: song.title, size: 44),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(song.title,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontWeight: FontWeight.w600)),
                        Text(
                          song.album.isEmpty ? song.artist : '${song.artist}  ·  ${song.album}',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(color: palette.muted, fontSize: 13),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 12),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(time, style: const TextStyle(fontFeatures: [FontFeature.tabularFigures()])),
                      Row(mainAxisSize: MainAxisSize.min, children: [
                        Icon(song.playing ? Icons.play_arrow : Icons.pause, size: 16, color: state),
                        const SizedBox(width: 2),
                        Text(context.t(song.playing ? 'mini.playing' : 'mini.paused'),
                            style: TextStyle(color: state, fontSize: 13)),
                      ]),
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
