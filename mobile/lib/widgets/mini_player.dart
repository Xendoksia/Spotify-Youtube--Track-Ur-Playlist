import 'dart:async';

import 'package:flutter/material.dart';

import '../data/artwork.dart';
import '../data/mood.dart';
import '../data/now_playing.dart';
import '../data/stats.dart';
import '../l10n/strings.dart';
import '../screens/listening/detail_screen.dart';
import '../state/data_store.dart';
import '../theme/palette.dart';
import 'artwork_image.dart';
import 'format.dart';

/// The strip's cover and the large view's share this, so it flies between them
const _coverHero = 'now-playing-cover';

/// A strip above the bottom bar with the song Spotify plays on the phone, as the desktop app's mini player:
/// cover, title, artist, the time into the song with a progress line and small dancing bars while it plays,
/// tinted with the cover's color. A new song slides in. Tapping it opens the song large (NowPlayingScreen).
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

  /// The color of the song's cover, and whose it is
  Mood? _mood;
  String? _moodOf;

  @override
  void initState() {
    super.initState();
    widget.nowPlaying.addListener(_changed);
    _changed();
  }

  void _changed() {
    final song = widget.nowPlaying.song;
    final playing = song?.playing ?? false;
    if (playing && _tick == null) {
      _tick = Timer.periodic(const Duration(seconds: 1), (_) => setState(() {}));
    } else if (!playing) {
      _tick?.cancel();
      _tick = null;
    }
    if (song != null && song.trackKey != _moodOf) _findMood(song);
    if (mounted) setState(() {});
  }

  Future<void> _findMood(Song song) async {
    final which = _moodOf = song.trackKey;
    final cover = await Artwork.instance.cover(song.artist, song.album, song.title);
    final found = cover == null ? null : await moodOf(cover);
    if (mounted && _moodOf == which) setState(() => _mood = found);
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

  void _open(BuildContext context, Song song) {
    Navigator.of(context).push(
      PageRouteBuilder<void>(
        transitionDuration: const Duration(milliseconds: 420),
        reverseTransitionDuration: const Duration(milliseconds: 340),
        pageBuilder: (_, _, _) => NowPlayingScreen(nowPlaying: widget.nowPlaying, store: widget.store, mood: _mood),
        transitionsBuilder: (_, _, _, child) => child,
      ),
    );
  }

  Widget _strip(BuildContext context, Song song) {
    final palette = Palette.of(context);
    final theme = Theme.of(context);
    final surface = theme.colorScheme.surfaceContainer;
    final mood = _mood?.color(theme.brightness) ?? palette.chart;
    final position = song.positionAtTime(DateTime.now());
    final duration = song.duration;
    final time = position == null
        ? ''
        : duration == null
        ? context.length(position)
        : '${context.length(position)} / ${context.length(duration)}';
    return TweenAnimationBuilder<Color?>(
      tween: ColorTween(end: mood),
      duration: const Duration(milliseconds: 600),
      builder: (context, color, _) => Material(
        color: surface,
        child: Ink(
          decoration: BoxDecoration(
            gradient: LinearGradient(stops: const [0, 0.55], colors: [Color.lerp(surface, color, 0.22)!, surface]),
          ),
          child: InkWell(
            onTap: () => _open(context, song),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Divider(height: 1, thickness: 1, color: palette.border),
                LinearProgressIndicator(
                  value: position != null && duration != null && duration > 0 ? position / duration : 0,
                  minHeight: 3,
                  color: color,
                  backgroundColor: palette.border,
                ),
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
                  child: Row(
                    children: [
                      Hero(
                        tag: _coverHero,
                        child: SongSwitcher(
                          song: song,
                          child: _Cover(song: song, size: 46),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: SongSwitcher(
                          song: song,
                          delay: true,
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                song.title,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(fontWeight: FontWeight.w600),
                              ),
                              Text(
                                song.album.isEmpty ? song.artist : '${song.artist}  ·  ${song.album}',
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(color: palette.muted, fontSize: 13),
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Text(
                            time,
                            style: TextStyle(color: palette.muted, fontFeatures: const [FontFeature.tabularFigures()]),
                          ),
                          const SizedBox(height: 2),
                          _State(song: song, color: song.playing ? color! : palette.muted),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// The dancing bars and "Playing" or "Paused", with "recorded" once the play is stored
class _State extends StatelessWidget {
  final Song song;
  final Color color;

  const _State({required this.song, required this.color});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Equalizer(playing: song.playing, color: color),
        const SizedBox(width: 6),
        Text(
          context.t(song.playing ? 'mini.playing' : 'mini.paused') + (song.recorded ? context.t('mini.recorded') : ''),
          style: TextStyle(color: color, fontSize: 13),
        ),
      ],
    );
  }
}

class _Cover extends StatelessWidget {
  final Song song;
  final double size;

  const _Cover({required this.song, required this.size});

  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: BoxDecoration(
      borderRadius: BorderRadius.circular(size * 0.14),
      boxShadow: const [BoxShadow(color: Color(0x4D000000), blurRadius: 8, offset: Offset(0, 2))],
    ),
    child: ArtworkImage.cover(
      artist: song.artist,
      album: song.album,
      name: song.title,
      size: size,
      corner: size * 0.14,
    ),
  );
}

/// Its child keyed by the song: a new one slides in from the right while the old one fades
class SongSwitcher extends StatelessWidget {
  final Song song;
  final Widget child;

  /// The text comes a little after the cover
  final bool delay;

  const SongSwitcher({super.key, required this.song, required this.child, this.delay = false});

  @override
  Widget build(BuildContext context) => AnimatedSwitcher(
    duration: const Duration(milliseconds: 400),
    switchInCurve: delay ? const Interval(0.15, 1, curve: Curves.easeOutCubic) : Curves.easeOutCubic,
    layoutBuilder: (current, previous) => Stack(alignment: Alignment.centerLeft, children: [...previous, ?current]),
    transitionBuilder: (shown, animation) => FadeTransition(
      opacity: animation,
      child: SlideTransition(
        position: Tween(begin: const Offset(0.08, 0), end: Offset.zero).animate(animation),
        child: shown,
      ),
    ),
    child: KeyedSubtree(key: ValueKey(song.trackKey), child: child),
  );
}

/// Three bars that dance while the song plays and rest when it is paused; they grow by scaling, which only
/// repaints them
class Equalizer extends StatefulWidget {
  final bool playing;
  final Color color;
  final double height;

  const Equalizer({super.key, required this.playing, required this.color, this.height = 12});

  @override
  State<Equalizer> createState() => _EqualizerState();
}

class _EqualizerState extends State<Equalizer> with TickerProviderStateMixin {
  static const _speeds = [900, 700, 1100];
  static const _starts = [0.0, 0.43, 0.55];

  late final _bars = [
    for (final (i, ms) in _speeds.indexed)
      AnimationController(
        vsync: this,
        duration: Duration(milliseconds: ms),
        value: _starts[i],
      ),
  ];

  @override
  void initState() {
    super.initState();
    _run();
  }

  @override
  void didUpdateWidget(Equalizer old) {
    super.didUpdateWidget(old);
    if (old.playing != widget.playing) _run();
  }

  void _run() {
    for (final bar in _bars) {
      if (widget.playing) {
        bar.repeat(reverse: true);
      } else {
        bar.animateTo(0, duration: const Duration(milliseconds: 250));
      }
    }
  }

  @override
  void dispose() {
    for (final bar in _bars) {
      bar.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return RepaintBoundary(
      child: SizedBox(
        height: widget.height,
        child: Row(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            for (final (i, bar) in _bars.indexed) ...[
              if (i > 0) SizedBox(width: widget.height / 6),
              AnimatedBuilder(
                animation: bar,
                builder: (context, child) => Transform.scale(
                  scaleY: 0.25 + 0.75 * Curves.easeInOut.transform(bar.value),
                  alignment: Alignment.bottomCenter,
                  child: child,
                ),
                child: Container(
                  width: widget.height / 4,
                  height: widget.height,
                  decoration: BoxDecoration(color: widget.color, borderRadius: BorderRadius.circular(1)),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// The playing song large, as the desktop app's NowPlayingView: its cover (flown in from the strip) over a
/// blurred copy of it, the title, artist and album, the progress with its times, and a way to the song's page
/// once it has plays. Tapping outside, the cross or back closes it.
class NowPlayingScreen extends StatefulWidget {
  final NowPlaying nowPlaying;
  final DataStore store;
  final Mood? mood;

  const NowPlayingScreen({super.key, required this.nowPlaying, required this.store, this.mood});

  @override
  State<NowPlayingScreen> createState() => _NowPlayingScreenState();
}

class _NowPlayingScreenState extends State<NowPlayingScreen> {
  Timer? _tick;
  String? _cover;
  String? _coverOf;
  Mood? _mood;

  @override
  void initState() {
    super.initState();
    _mood = widget.mood;
    widget.nowPlaying.addListener(_changed);
    _tick = Timer.periodic(const Duration(milliseconds: 500), (_) {
      if (widget.nowPlaying.song?.playing ?? false) setState(() {});
    });
    _changed();
  }

  void _changed() {
    final song = widget.nowPlaying.song;
    // Nothing plays any more: the view closes with the strip
    if (song == null) {
      if (mounted) Navigator.of(context).maybePop();
      return;
    }
    if (song.trackKey != _coverOf) _findCover(song);
    if (mounted) setState(() {});
  }

  Future<void> _findCover(Song song) async {
    final which = _coverOf = song.trackKey;
    final url = await Artwork.instance.cover(song.artist, song.album, song.title);
    final mood = url == null ? null : await moodOf(url);
    if (!mounted || _coverOf != which) return;
    setState(() {
      _cover = url;
      _mood = mood;
    });
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
    if (song == null) return const SizedBox.shrink();
    final route = ModalRoute.of(context)!.animation!;
    // The backdrop comes in quickly, the parts after it while the cover flies
    final shade = CurvedAnimation(
      parent: route,
      curve: const Interval(0, 0.35, curve: Curves.easeOut),
    );
    final parts = CurvedAnimation(
      parent: route,
      curve: const Interval(0.3, 1, curve: Curves.easeOutCubic),
    );
    final mood = _mood?.color(Brightness.dark) ?? Palette.dark.chart;
    final position = song.positionAtTime(DateTime.now());
    final duration = song.duration;
    final hasPage = widget.store.plays.any((p) => p.trackKey == song.trackKey);
    final size = MediaQuery.sizeOf(context);
    final coverSize = (size.width - 64).clamp(160.0, 340.0);
    Widget part(Widget child) => FadeTransition(
      opacity: parts,
      child: SlideTransition(
        position: Tween(begin: const Offset(0, 0.25), end: Offset.zero).animate(parts),
        child: child,
      ),
    );
    const white = Colors.white;
    final soft = white.withValues(alpha: 0.72);
    return Material(
      type: MaterialType.transparency,
      child: GestureDetector(
        onTap: () => Navigator.of(context).maybePop(),
        child: Stack(
          fit: StackFit.expand,
          children: [
            FadeTransition(
              opacity: shade,
              child: _Backdrop(url: _cover, mood: mood),
            ),
            SafeArea(
              child: Stack(
                children: [
                  Positioned(
                    left: 8,
                    top: 8,
                    child: FadeTransition(
                      opacity: parts,
                      child: IconButton(
                        onPressed: () => Navigator.of(context).maybePop(),
                        icon: const Icon(Icons.keyboard_arrow_down_rounded, color: white, size: 32),
                      ),
                    ),
                  ),
                  Center(
                    child: SingleChildScrollView(
                      padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 24),
                      child: GestureDetector(
                        // Taps on the content itself do not close the view
                        onTap: () {},
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            part(
                              Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Equalizer(playing: song.playing, color: white),
                                  const SizedBox(width: 8),
                                  Text(
                                    context.t('mini.now').toUpperCase(),
                                    style: TextStyle(
                                      color: soft,
                                      fontSize: 12,
                                      fontWeight: FontWeight.w700,
                                      letterSpacing: 1.2,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(height: 20),
                            Hero(
                              tag: _coverHero,
                              child: SongSwitcher(
                                song: song,
                                child: _Cover(song: song, size: coverSize),
                              ),
                            ),
                            const SizedBox(height: 24),
                            part(
                              SongSwitcher(
                                song: song,
                                delay: true,
                                child: SizedBox(
                                  width: coverSize,
                                  child: Column(
                                    children: [
                                      Text(
                                        song.title,
                                        textAlign: TextAlign.center,
                                        maxLines: 2,
                                        overflow: TextOverflow.ellipsis,
                                        style: const TextStyle(color: white, fontSize: 22, fontWeight: FontWeight.w700),
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        song.artist,
                                        textAlign: TextAlign.center,
                                        style: TextStyle(color: soft, fontSize: 16),
                                      ),
                                      if (song.album.isNotEmpty)
                                        Text(
                                          song.album,
                                          textAlign: TextAlign.center,
                                          maxLines: 1,
                                          overflow: TextOverflow.ellipsis,
                                          style: TextStyle(color: white.withValues(alpha: 0.5), fontSize: 14),
                                        ),
                                    ],
                                  ),
                                ),
                              ),
                            ),
                            const SizedBox(height: 24),
                            part(
                              SizedBox(
                                width: coverSize,
                                child: Column(
                                  children: [
                                    ClipRRect(
                                      borderRadius: BorderRadius.circular(2),
                                      child: LinearProgressIndicator(
                                        value: position != null && duration != null && duration > 0
                                            ? position / duration
                                            : 0,
                                        minHeight: 4,
                                        color: white,
                                        backgroundColor: white.withValues(alpha: 0.2),
                                      ),
                                    ),
                                    const SizedBox(height: 6),
                                    Row(
                                      children: [
                                        Text(
                                          position == null ? '' : context.length(position),
                                          style: TextStyle(color: soft, fontSize: 12),
                                        ),
                                        const Spacer(),
                                        Text(
                                          duration == null ? '' : context.length(duration),
                                          style: TextStyle(color: soft, fontSize: 12),
                                        ),
                                      ],
                                    ),
                                  ],
                                ),
                              ),
                            ),
                            const SizedBox(height: 12),
                            part(
                              Text(
                                context.t(song.playing ? 'mini.playing' : 'mini.paused') +
                                    (song.recorded ? context.t('mini.recorded') : ''),
                                style: TextStyle(color: soft),
                              ),
                            ),
                            if (hasPage) ...[
                              const SizedBox(height: 20),
                              part(
                                FilledButton(
                                  style: FilledButton.styleFrom(
                                    backgroundColor: white,
                                    foregroundColor: Colors.black87,
                                  ),
                                  onPressed: () {
                                    final navigator = Navigator.of(context);
                                    navigator.pop();
                                    navigator.push(
                                      MaterialPageRoute(
                                        builder: (_) => DetailScreen(
                                          store: widget.store,
                                          target: DetailTarget(
                                            DetailKind.track,
                                            song.trackKey,
                                            song.title,
                                            artist: song.artist,
                                            album: song.album,
                                          ),
                                        ),
                                      ),
                                    );
                                  },
                                  child: Text(context.t('mini.open_page')),
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),
                    ),
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

/// The cover decoded tiny and stretched over the screen, which blurs it without a blur filter to draw on every
/// frame, darkened so white text reads on it; the cover's color until it comes
class _Backdrop extends StatelessWidget {
  final String? url;
  final Color mood;

  const _Backdrop({required this.url, required this.mood});

  @override
  Widget build(BuildContext context) {
    final base = Color.lerp(Colors.black, mood, 0.45)!;
    return Stack(
      fit: StackFit.expand,
      children: [
        ColoredBox(color: base),
        if (url != null) BlurredPicture(url: url!),
        const DecoratedBox(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [Color(0x80000000), Color(0xB3000000)],
            ),
          ),
        ),
      ],
    );
  }
}
