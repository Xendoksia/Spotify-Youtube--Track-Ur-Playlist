import 'package:flutter/material.dart';

import '../../data/artwork.dart';
import '../../data/models.dart';
import '../../data/stats.dart';
import '../../l10n/strings.dart';
import '../../state/data_store.dart';
import '../../theme/palette.dart';
import '../../widgets/artwork_image.dart';
import '../../widgets/cards.dart';
import 'detail_screen.dart';

/// The period's most played album covers in a grid, as the desktop app's collage; a cover opens its album
class CollageCard extends StatefulWidget {
  static const columns = 3;
  static const gap = 4.0;

  final DataStore store;

  /// The period's plays
  final List<Play> plays;

  const CollageCard({super.key, required this.store, required this.plays});

  @override
  State<CollageCard> createState() => _CollageCardState();
}

class _CollageCardState extends State<CollageCard> {
  static const _count = CollageCard.columns * CollageCard.columns;

  /// Twice as many as fit, as some are left out for sharing a cover with another
  var _albums = <Ranked>[];
  List<Ranked>? _kept;
  var _keys = '';

  @override
  void initState() {
    super.initState();
    _update();
  }

  @override
  void didUpdateWidget(CollageCard old) {
    super.didUpdateWidget(old);
    _update();
  }

  void _update() {
    _albums = topAlbums(widget.plays, limit: _count * 2);
    final keys = _albums.map((a) => a.key).join('\n');
    if (keys == _keys) return;
    _keys = keys;
    _kept = null;
    _distinct(keys);
  }

  /// A single and the album it is from often share their cover: the later one of the same artist is left out.
  /// Different artists are never compared, as the desktop app does.
  Future<void> _distinct(String keys) async {
    final albums = _albums;
    final covers = await Future.wait(albums.map((a) => Artwork.instance.albumCover(a.artist, a.album)));
    if (!mounted || keys != _keys) return;
    final seen = <String>{};
    final kept = <Ranked>[];
    for (final (index, album) in albums.indexed) {
      final cover = covers[index];
      if (cover != null && !seen.add('${textKey(album.artist)}|$cover')) continue;
      kept.add(album);
      if (kept.length == _count) break;
    }
    setState(() => _kept = kept);
  }

  @override
  Widget build(BuildContext context) {
    final albums = (_kept ?? _albums).take(_count).toList();
    return SectionCard(
      title: context.t('stats.collage'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(context.t('stats.collage.summary'), style: TextStyle(color: Palette.of(context).muted, fontSize: 13)),
          const SizedBox(height: 12),
          if (albums.isEmpty)
            Text(context.t('stats.empty'), style: TextStyle(color: Palette.of(context).muted))
          else
            LayoutBuilder(builder: (context, constraints) {
              const columns = CollageCard.columns;
              final side = (constraints.maxWidth - CollageCard.gap * (columns - 1)) / columns;
              return Wrap(
                spacing: CollageCard.gap,
                runSpacing: CollageCard.gap,
                children: [
                  for (final album in albums)
                    GestureDetector(
                      onTap: () =>
                          openDetail(context, widget.store, DetailTarget.ranked(DetailKind.album, album)),
                      child: ArtworkImage.album(artist: album.artist, album: album.album, size: side),
                    ),
                ],
              );
            }),
        ],
      ),
    );
  }
}
