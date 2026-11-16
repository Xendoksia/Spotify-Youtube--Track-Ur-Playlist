import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../data/artwork.dart';
import '../theme/palette.dart';

/// A cover or artist photo found on Deezer; the name's first letter until it comes, or when there is none
class ArtworkImage extends StatefulWidget {
  final Future<String?> Function(Artwork artwork) find;

  /// Which picture this is: the same for every image of it, so one already found shows at once
  final String which;

  /// Shown as its first letter in the placeholder
  final String name;
  final double size;

  /// Artists are round, covers square
  final bool round;

  /// Flies to the image with the same tag on the next page (a row's picture to its page's big one)
  final String? hero;

  /// The square's corners; by default rounded with its size
  final double? corner;

  const ArtworkImage({
    super.key,
    required this.find,
    required this.which,
    required this.name,
    this.size = 44,
    this.round = false,
    this.hero,
    this.corner,
  });

  ArtworkImage.cover(
      {Key? key,
      required String artist,
      required String album,
      required String name,
      double size = 44,
      String? hero,
      double? corner})
      : this(
            key: key,
            find: (a) => a.cover(artist, album, name),
            which: 'cover|$artist|$album|$name',
            name: album.isNotEmpty ? album : name,
            size: size,
            hero: hero,
            corner: corner);

  ArtworkImage.album({Key? key, required String artist, required String album, double size = 44, String? hero})
      : this(
            key: key,
            find: (a) => a.albumCover(artist, album),
            which: 'album|$artist|$album',
            name: album,
            size: size,
            hero: hero);

  /// A YouTube video's thumbnail, from YouTube's public image address (no account or key)
  ArtworkImage.video({Key? key, required String id, required String name, double size = 44, double? corner})
      : this(
            key: key,
            find: (_) async => RegExp(r'^[\w-]{6,20}$').hasMatch(id) ? 'https://i.ytimg.com/vi/$id/mqdefault.jpg' : null,
            which: 'video|$id',
            name: name,
            size: size,
            corner: corner);

  ArtworkImage.artist({Key? key, required String artist, double size = 44, String? hero})
      : this(
            key: key,
            find: (a) => a.artistPhoto(artist),
            which: 'artist|$artist',
            name: artist,
            size: size,
            round: true,
            hero: hero);

  @override
  State<ArtworkImage> createState() => _ArtworkImageState();
}

class _ArtworkImageState extends State<ArtworkImage> {
  /// The addresses found while the app runs: a page's big picture shows from its first frame, while it flies in
  static final _found = <String, String?>{};

  String? _url;

  @override
  void initState() {
    super.initState();
    _find();
  }

  @override
  void didUpdateWidget(ArtworkImage old) {
    super.didUpdateWidget(old);
    if (old.which != widget.which) _find();
  }

  void _find() {
    final which = widget.which;
    _url = _found[which];
    if (_found.containsKey(which)) return;
    widget.find(Artwork.instance).then((url) {
      _found[which] = url;
      if (mounted && widget.which == which && url != null) setState(() => _url = url);
    });
  }

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final placeholder = Container(
      color: palette.border,
      alignment: Alignment.center,
      child: Text(
        widget.name.trim().isEmpty ? '?' : widget.name.trim().characters.first.toUpperCase(),
        style: TextStyle(color: palette.muted, fontWeight: FontWeight.w600, fontSize: widget.size * 0.4),
      ),
    );
    // Decoded at full size (Deezer's are 500 px) for small and big alike, so the big one is already in memory
    final image = _url == null
        ? placeholder
        : CachedNetworkImage(
            imageUrl: _url!,
            fit: BoxFit.cover,
            fadeInDuration: const Duration(milliseconds: 200),
            placeholder: (_, _) => placeholder,
            errorWidget: (_, _, _) => placeholder,
          );
    final clipped = SizedBox.square(
      dimension: widget.size,
      child: widget.round
          ? ClipOval(child: image)
          : ClipRRect(borderRadius: BorderRadius.circular(widget.corner ?? widget.size * 0.12), child: image),
    );
    return widget.hero == null ? clipped : Hero(tag: widget.hero!, child: clipped);
  }
}

/// A picture decoded tiny and stretched over its box, which blurs it without a blur filter to draw on every frame
class BlurredPicture extends StatelessWidget {
  final String url;

  const BlurredPicture({super.key, required this.url});

  @override
  Widget build(BuildContext context) => Image(
        image: ResizeImage(CachedNetworkImageProvider(url), width: 12, height: 12),
        fit: BoxFit.cover,
        filterQuality: FilterQuality.medium,
        gaplessPlayback: true,
        errorBuilder: (_, _, _) => const SizedBox.shrink(),
      );
}
