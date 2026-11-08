import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../data/artwork.dart';
import '../theme/palette.dart';

/// A cover or artist photo found on Deezer; the name's first letter until it comes, or when there is none
class ArtworkImage extends StatefulWidget {
  final Future<String?> Function(Artwork artwork) find;

  /// Shown as its first letter in the placeholder
  final String name;
  final double size;

  /// Artists are round, covers square
  final bool round;

  const ArtworkImage({super.key, required this.find, required this.name, this.size = 44, this.round = false});

  ArtworkImage.cover(
      {Key? key, required String artist, required String album, required String name, double size = 44})
      : this(key: key, find: (a) => a.cover(artist, album, name), name: album.isNotEmpty ? album : name, size: size);

  ArtworkImage.album({Key? key, required String artist, required String album, double size = 44})
      : this(key: key, find: (a) => a.albumCover(artist, album), name: album, size: size);

  ArtworkImage.artist({Key? key, required String artist, double size = 44})
      : this(key: key, find: (a) => a.artistPhoto(artist), name: artist, size: size, round: true);

  @override
  State<ArtworkImage> createState() => _ArtworkImageState();
}

class _ArtworkImageState extends State<ArtworkImage> {
  late Future<String?> _url;

  @override
  void initState() {
    super.initState();
    _url = widget.find(Artwork.instance);
  }

  @override
  void didUpdateWidget(ArtworkImage old) {
    super.didUpdateWidget(old);
    if (old.name != widget.name) _url = widget.find(Artwork.instance);
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
    final pixels = (widget.size * MediaQuery.devicePixelRatioOf(context)).round();
    final image = FutureBuilder<String?>(
      future: _url,
      builder: (context, snapshot) {
        final url = snapshot.data;
        if (url == null) return placeholder;
        return CachedNetworkImage(
          imageUrl: url,
          memCacheWidth: pixels,
          fit: BoxFit.cover,
          fadeInDuration: const Duration(milliseconds: 200),
          placeholder: (_, _) => placeholder,
          errorWidget: (_, _, _) => placeholder,
        );
      },
    );
    return SizedBox.square(
      dimension: widget.size,
      child: widget.round
          ? ClipOval(child: image)
          : ClipRRect(borderRadius: BorderRadius.circular(widget.size * 0.12), child: image),
    );
  }
}
