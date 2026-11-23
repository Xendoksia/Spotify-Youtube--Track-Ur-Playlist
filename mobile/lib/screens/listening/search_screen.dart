import 'dart:async';

import 'package:flutter/material.dart';

import '../../data/search.dart';
import '../../data/stats.dart';
import '../../l10n/strings.dart';
import '../../state/data_store.dart';
import '../../theme/palette.dart';
import '../../widgets/artwork_image.dart';
import '../../widgets/format.dart';
import 'detail_screen.dart';

/// Searching the recorded tracks, artists and albums, as the desktop app's search box: the search runs once typing
/// pauses (or at once on the keyboard's search key), and a result opens its page
class SearchScreen extends StatefulWidget {
  final DataStore store;

  const SearchScreen({super.key, required this.store});

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  /// How long typing has to pause before the search runs
  static const pause = Duration(milliseconds: 400);

  final _text = TextEditingController();
  Timer? _timer;
  SearchResults? _results;

  @override
  void dispose() {
    _timer?.cancel();
    _text.dispose();
    super.dispose();
  }

  void _run() {
    _timer?.cancel();
    setState(() => _results = searchPlays(widget.store.plays, _text.text));
  }

  void _typed(String _) {
    _timer?.cancel();
    _timer = Timer(pause, _run);
  }

  void _open(DetailKind kind, Ranked row) => openDetail(context, widget.store, DetailTarget.ranked(kind, row));

  Widget _group(BuildContext context, String title, DetailKind kind, List<Ranked> rows) {
    final palette = Palette.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
          child: Text(
            title.toUpperCase(),
            style: TextStyle(color: palette.muted, fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 0.8),
          ),
        ),
        for (final row in rows)
          ListTile(
            leading: switch (kind) {
              DetailKind.track => ArtworkImage.cover(
                artist: row.artist,
                album: row.album,
                name: row.title,
                hero: heroTag(kind, row.key, 1),
              ),
              DetailKind.artist => ArtworkImage.artist(artist: row.title, hero: heroTag(kind, row.key, 1)),
              DetailKind.album => ArtworkImage.album(
                artist: row.artist,
                album: row.title,
                hero: heroTag(kind, row.key, 1),
              ),
            },
            title: Text(row.title, maxLines: 1, overflow: TextOverflow.ellipsis),
            subtitle: kind == DetailKind.artist
                ? null
                : Text(
                    row.artist,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(color: palette.muted),
                  ),
            trailing: Text(context.plays(row.plays), style: TextStyle(color: palette.muted, fontSize: 13)),
            onTap: () => _open(kind, row),
          ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final results = _results;
    return Scaffold(
      appBar: AppBar(
        titleSpacing: 0,
        title: TextField(
          controller: _text,
          autofocus: true,
          textInputAction: TextInputAction.search,
          decoration: InputDecoration(hintText: context.t('search.placeholder'), border: InputBorder.none),
          onChanged: _typed,
          onSubmitted: (_) => _run(),
        ),
        actions: [
          if (_text.text.isNotEmpty || results != null)
            IconButton(
              icon: const Icon(Icons.close),
              onPressed: () {
                _timer?.cancel();
                _text.clear();
                setState(() => _results = null);
              },
            ),
        ],
      ),
      body: results == null
          ? const SizedBox.shrink()
          : results.isEmpty
          ? Padding(
              padding: const EdgeInsets.all(24),
              child: Text(context.t('search.none'), style: TextStyle(color: palette.muted)),
            )
          : ListView(
              padding: const EdgeInsets.only(bottom: 24),
              children: [
                if (results.tracks.isNotEmpty)
                  _group(context, context.t('search.tracks'), DetailKind.track, results.tracks),
                if (results.artists.isNotEmpty)
                  _group(context, context.t('search.artists'), DetailKind.artist, results.artists),
                if (results.albums.isNotEmpty)
                  _group(context, context.t('search.albums'), DetailKind.album, results.albums),
              ],
            ),
    );
  }
}
