import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:gal/gal.dart';
import 'package:flutter/services.dart';
import 'package:share_plus/share_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../data/artwork.dart';
import '../../data/genres.dart';
import '../../data/models.dart';
import '../../data/mood.dart';
import '../../data/preview.dart';
import '../../data/stats.dart';
import '../../l10n/strings.dart';
import '../../state/data_store.dart';
import '../../theme/palette.dart';
import '../../widgets/artwork_image.dart';
import '../../widgets/format.dart';
import 'detail_screen.dart';
import 'genre_cards.dart' show capitalized;
import 'wrapped_stage.dart';
import 'wrapped_visuals.dart';

/// Days of the month on which the summary of the month before opens by itself, once, as in the desktop app
const wrappedDays = {1, 2};

/// A month in review, slide by slide, as the desktop app's monthly summary: time listened, the song and artist of
/// the month, the top five of each, discoveries, the busiest day and hour, genres and a closing summary
class WrappedData {
  static const top = 5;

  final DateRange range;
  final Summary summary;
  final List<Ranked> tracks;
  final List<Ranked> artists;
  final List<Discovered> discoveredTracks;
  final List<Discovered> discoveredArtists;

  /// Everything counts as new in the month recording began
  final bool firstMonth;
  final (DateTime, int)? busiest;
  final int daysListened;
  final List<int> hours;

  /// The three biggest genres with their share of the plays in percent
  final List<(String, int)> genres;

  /// The month's most played tracks, one per cover, for the wall behind the first slide
  final List<Ranked> wall;

  /// The month (or year) before, to say how this one compares; null when nothing was recorded then
  final Summary? previous;

  /// Plays per day of the month (per month of a year) for the calendar of dots
  final List<int> calendar;

  /// The most played artists of each of the biggest genres, for their photos
  final Map<String, List<Ranked>> genreArtists;

  WrappedData._(this.range, this.summary, this.tracks, this.artists, this.discoveredTracks, this.discoveredArtists,
      this.firstMonth, this.busiest, this.daysListened, this.hours, this.genres, this.wall, this.previous,
      this.calendar, this.genreArtists);

  factory WrappedData.of(List<Play> all, DateRange range) {
    final plays = playsIn(all, range);
    final artists = topArtists(plays, limit: 1 << 30);
    final genres = <String, int>{};
    final genreArtists = <String, List<Ranked>>{};
    for (final artist in artists) {
      final genre = Genres.instance.mainGenre(artist.key);
      if (genre == null) continue;
      genres[genre] = (genres[genre] ?? 0) + artist.plays;
      final their = genreArtists.putIfAbsent(genre, () => []);
      if (their.length < 4) their.add(artist);
    }
    final days = <DateTime, int>{};
    for (final play in plays) {
      final day = DateTime(play.playedAt.year, play.playedAt.month, play.playedAt.day);
      days[day] = (days[day] ?? 0) + 1;
    }
    final busiest = days.entries.fold<MapEntry<DateTime, int>?>(
        null, (best, day) => best == null || day.value > best.value ? day : best);
    final first = all.isEmpty ? null : all.map((p) => p.playedAt).reduce((a, b) => a.isBefore(b) ? a : b);
    final year = isYear(range);
    final before = playsIn(
        all,
        year
            ? DateRange(DateTime(range.start.year - 1), range.start)
            : DateRange(DateTime(range.start.year, range.start.month - 1), range.start));
    final covers = <String>{};
    final wall = [
      for (final track in topTracks(plays, limit: 60))
        if (covers.add('${track.artist}|${track.album.isEmpty ? track.title : track.album}')) track,
    ].take(21).toList();
    final calendar = year
        ? [for (var m = 1; m <= 12; m++) plays.where((p) => p.playedAt.month == m).length]
        : [
            for (var d = 1; d <= DateTime(range.start.year, range.start.month + 1, 0).day; d++)
              days[DateTime(range.start.year, range.start.month, d)] ?? 0,
          ];
    return WrappedData._(
      range,
      Summary.of(plays),
      topTracks(plays, limit: top),
      artists.take(top).toList(),
      newTracks(all, range),
      newArtists(all, range),
      first != null && !first.isBefore(range.start),
      busiest == null ? null : (busiest.key, busiest.value),
      days.length,
      playsPerHour(plays),
      (genres.entries.toList()..sort((a, b) => b.value.compareTo(a.value)))
          .take(3)
          .map((e) => (e.key, share(e.value, plays.length)))
          .toList(),
      wall,
      before.isEmpty ? null : Summary.of(before),
      calendar,
      genreArtists,
    );
  }
}

/// The summary to open by itself: on the first days of a month, the month before when it has plays and its summary
/// was not shown yet; in January the year before first
Future<DateRange?> wrappedDue(List<Play> all, DateTime now) async {
  if (!wrappedDays.contains(now.day)) return null;
  final prefs = await SharedPreferences.getInstance();
  for (final range in [
    if (now.month == DateTime.january) periodRange(Period.year, 1, now),
    periodRange(Period.month, 1, now),
  ]) {
    if (!all.any((p) => range.contains(p.playedAt))) continue;
    final setting = _shownSetting(range);
    if (prefs.getString(setting) == _key(range)) continue;
    await prefs.setString(setting, _key(range));
    return range;
  }
  return null;
}

/// A whole calendar year rather than a month
bool isYear(DateRange range) =>
    range.start.month == 1 && range.end.month == 1 && range.end.year == range.start.year + 1;

String _monthKey(DateTime month) => '${month.year}-${month.month.toString().padLeft(2, '0')}';

/// "2026" for a year, "2026-10" for a month, as WrappedNotice.kt
String _key(DateRange range) => isYear(range) ? '${range.start.year}' : _monthKey(range.start);

String _shownSetting(DateRange range) => isYear(range) ? 'WRAPPED_YEAR_SHOWN' : 'WRAPPED_SHOWN';

/// The phone's "your month in review is ready" notification (WrappedNotice.kt), sent on the first days of a month
/// while the app is closed, and in January one for the year. It is told here which months have plays; tapping it
/// opens the summary
class WrappedNotice {
  static const _channel = MethodChannel('playlist_tracker/wrapped');

  /// The month or year of a notification tapped while the app was open
  static final tapped = ValueNotifier<DateRange?>(null);

  /// The month ("2026-10") or year ("2026") of a notification
  static DateRange? range(Object? key) {
    final parts = key is String ? key.split('-').map(int.tryParse).toList() : const <int?>[];
    if (parts.isEmpty || parts.length > 2 || parts.contains(null)) return null;
    final start = DateTime(parts[0]!, parts.length == 2 ? parts[1]! : 1);
    return DateRange(start, parts.length == 2 ? DateTime(start.year, start.month + 1) : DateTime(start.year + 1));
  }

  static void listen() => _channel.setMethodCallHandler((call) async {
        if (call.method == 'tapped') tapped.value = range(call.arguments);
      });

  /// The summary of the notification the app was opened from, marked as seen
  static Future<DateRange?> takeTapped() async {
    try {
      final summary = range(await _channel.invokeMethod<String>('takeTapped'));
      if (summary != null) {
        await (await SharedPreferences.getInstance()).setString(_shownSetting(summary), _key(summary));
      }
      return summary;
    } on MissingPluginException {
      return null;
    }
  }

  /// The months with plays since the start of the year before, for the notification to know whether there is a
  /// summary of last month or last year
  static Future<void> remember(List<Play> all, DateTime now) async {
    final since = periodRange(Period.year, 1, now).start;
    final months = {for (final play in all) if (!play.playedAt.isBefore(since)) _monthKey(play.playedAt)};
    await (await SharedPreferences.getInstance()).setString('PLAY_MONTHS', months.join(','));
  }

  /// The summary was seen in the app: its notification goes
  static Future<void> cancel(String key) async {
    try {
      await _channel.invokeMethod('cancel', key);
    } on MissingPluginException {
      // Not on Android
    }
  }

  /// Asked once, on Android 13 and later
  static Future<void> askPermission() async {
    final prefs = await SharedPreferences.getInstance();
    if (prefs.getBool('NOTIFICATIONS_ASKED') ?? false) return;
    await prefs.setBool('NOTIFICATIONS_ASKED', true);
    try {
      await _channel.invokeMethod('askPermission');
    } on MissingPluginException {
      // Not on Android
    }
  }
}

/// The summaries ready and not seen yet, behind the bell on the listening page: last month's all through this
/// month and in January last year's too, so one whose notification was missed or swiped away is still there.
/// Opening one takes it out: besides opening by itself, this is the only way to a summary, to keep it special
class WrappedInbox extends ChangeNotifier {
  static final instance = WrappedInbox._();

  WrappedInbox._();

  var items = const <DateRange>[];

  Future<void> update(List<Play> all, DateTime now) async {
    final prefs = await SharedPreferences.getInstance();
    items = [
      for (final range in [
        if (now.month == DateTime.january) periodRange(Period.year, 1, now),
        periodRange(Period.month, 1, now),
      ])
        if (all.any((p) => range.contains(p.playedAt)) && prefs.getString(_shownSetting(range)) != _key(range)) range,
    ];
    notifyListeners();
  }

  /// Opened: out of the box, and its notification off the phone's
  Future<void> seen(DateRange range) async {
    final key = _key(range);
    if (!items.any((item) => _key(item) == key)) return;
    items = [for (final item in items) if (_key(item) != key) item];
    notifyListeners();
    await (await SharedPreferences.getInstance()).setString(_shownSetting(range), key);
    await WrappedNotice.cancel(key);
  }
}

/// The bell on the listening page, with the number of summaries waiting
class WrappedInboxButton extends StatelessWidget {
  final DataStore store;

  const WrappedInboxButton({super.key, required this.store});

  String _name(BuildContext context, DateRange range) =>
      isYear(range) ? '${range.start.year}' : context.dateFormat('MMMM y').format(range.start);

  void _show(BuildContext context) => showModalBottomSheet<void>(
        context: context,
        showDragHandle: true,
        builder: (sheet) => SafeArea(
          child: ListenableBuilder(
            listenable: WrappedInbox.instance,
            builder: (sheet, _) {
              final items = WrappedInbox.instance.items;
              return Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Padding(
                    padding: const EdgeInsets.fromLTRB(24, 0, 24, 8),
                    child: Text(context.t('inbox.title'), style: Theme.of(context).textTheme.titleLarge),
                  ),
                  if (items.isEmpty)
                    Padding(
                      padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
                      child: Text(context.t('inbox.empty'), style: TextStyle(color: Palette.of(context).muted)),
                    ),
                  for (final range in items)
                    ListTile(
                      contentPadding: const EdgeInsets.symmetric(horizontal: 24),
                      leading: Icon(Icons.auto_awesome, color: Palette.of(context).chart),
                      title: Text(context.t('wrapped.inbox.item', {'name': _name(context, range)})),
                      subtitle: Text(context.t(isYear(range) ? 'wrapped.inbox.detail.year' : 'wrapped.inbox.detail')),
                      onTap: () {
                        Navigator.of(sheet).pop();
                        openWrapped(context, store, range);
                      },
                    ),
                  const SizedBox(height: 8),
                ],
              );
            },
          ),
        ),
      );

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: WrappedInbox.instance,
        builder: (context, _) {
          final count = WrappedInbox.instance.items.length;
          return IconButton(
            tooltip: context.t('inbox.title'),
            visualDensity: VisualDensity.compact,
            onPressed: () => _show(context),
            icon: Badge.count(
              count: count,
              isLabelVisible: count > 0,
              backgroundColor: Palette.of(context).chart,
              child: Icon(count > 0 ? Icons.notifications : Icons.notifications_none),
            ),
          );
        },
      );
}

/// Opening a summary waiting in the box takes it out
void openWrapped(BuildContext context, DataStore store, DateRange month) {
  WrappedInbox.instance.seen(month);
  Navigator.of(context)
      .push(MaterialPageRoute(
          // The slides on their colored stage in white, whatever the app's theme: set above the screen so that every
          // slide's own lookups find it
          builder: (_) => Theme(
              data: stageTheme(buildTheme(Brightness.dark)), child: WrappedScreen(store: store, month: month)),
          fullscreenDialog: true));
}

class WrappedScreen extends StatefulWidget {
  final DataStore store;
  final DateRange month;

  const WrappedScreen({super.key, required this.store, required this.month});

  @override
  State<WrappedScreen> createState() => _WrappedScreenState();
}

class _WrappedScreenState extends State<WrappedScreen> with SingleTickerProviderStateMixin {
  /// How long a slide shows before the next comes by itself, unless held
  static const _slideTime = Duration(seconds: 9);

  final _pages = PageController();

  /// Kept out of the state so that turning a page, halfway through the swipe, redraws only the bars above
  final _index = ValueNotifier(0);

  /// Fills the bar of the slide showing, then turns to the next
  late final _timer = AnimationController(vsync: this, duration: _slideTime)
    ..addStatusListener((status) {
      if (status == AnimationStatus.completed) _go(_index.value + 1);
    });

  /// Held down (or a page opened from a slide over it): the slide stays
  final _paused = ValueNotifier(false);

  /// Worked out once: going over every play again at each page turn made the swipes stutter
  late final _data = WrappedData.of(widget.store.plays, widget.month);

  late final _year = isYear(widget.month);

  /// The month's color, from its song's cover, and the colors of the slides with a picture of their own
  double _baseHue = defaultHue;
  final _hues = <int, double>{};
  var _count = 0;

  /// The song's slide plays its 30 second preview, and the artist's slide the artist's song played most in the
  /// period, unless the sound is turned off
  var _sound = true;

  late final _artistSong = () {
    if (_data.artists.isEmpty) return null;
    final key = _data.artists.first.key;
    final theirs = playsIn(widget.store.plays, widget.month).where((p) => artistKeysOf(p).contains(key)).toList();
    final top = topTracks(theirs, limit: 1);
    return top.isEmpty ? null : (top.first.artist, top.first.title);
  }();

  (String, String)? _songOf(int index) {
    final track = _data.tracks.isEmpty ? null : _data.tracks.first;
    if (track != null && index == 1) return (track.artist, track.title);
    if (_data.artists.isNotEmpty && index == (track == null ? 1 : 2)) return _artistSong;
    return null;
  }

  void _playFor(int index) {
    final song = _sound ? _songOf(index) : null;
    if (song == null) {
      Preview.instance.stop();
    } else {
      Preview.instance.play(song.$1, song.$2);
    }
  }

  /// The year's wording of a text in a yearly summary: "Song of the year" for "Song of the month"
  String _of(String key) => _year ? '$key.year' : key;

  @override
  void initState() {
    super.initState();
    _timer.forward();
    _readColors();
  }

  Future<void> _readColors() async {
    final data = _data;
    Future<double?> hueOf(Future<String?> url) async {
      final found = await url;
      return found == null ? null : (await moodOf(found))?.hue;
    }

    final track = data.tracks.isEmpty ? null : data.tracks.first;
    final artist = data.artists.isEmpty ? null : data.artists.first;
    final trackHue = track == null ? null : await hueOf(Artwork.instance.cover(track.artist, track.album, track.title));
    final artistHue = artist == null ? null : await hueOf(Artwork.instance.artistPhoto(artist.artist));
    if (!mounted) return;
    setState(() {
      _baseHue = trackHue ?? artistHue ?? defaultHue;
      // The song's and the artist's slides in their own picture's color (the second and third when there)
      if (track != null && trackHue != null) _hues[1] = trackHue;
      if (artist != null && artistHue != null) _hues[track == null ? 1 : 2] = artistHue;
    });
  }

  double _hue(int index) => _hues[index] ?? slideHue(_baseHue, index);

  /// Each slide's drawing, to turn the one showing into a picture to share
  final _slideKeys = <int, GlobalKey>{};
  var _sharing = false;

  /// Asks whether to save the slide showing to the gallery or share it; the slide holds meanwhile
  Future<void> _chooseShare(String title) async {
    final wasPaused = _paused.value;
    _pause(true);
    final save = await showModalBottomSheet<bool>(
      context: context,
      showDragHandle: true,
      builder: (sheet) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.download),
              title: Text(context.t('wrapped.share.save')),
              onTap: () => Navigator.of(sheet).pop(true),
            ),
            ListTile(
              leading: const Icon(Icons.ios_share),
              title: Text(context.t('wrapped.share.send')),
              onTap: () => Navigator.of(sheet).pop(false),
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
    if (save != null) await _share(title, save: save);
    if (mounted && !wasPaused) _pause(false);
  }

  void _tell(String key) {
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(context.t(key))));
  }

  /// The slide showing as a story picture, saved to the gallery or handed to the phone's share sheet
  Future<void> _share(String title, {required bool save}) async {
    if (_sharing) return;
    _sharing = true;
    try {
      final index = _index.value;
      final boundary = _slideKeys[index]?.currentContext?.findRenderObject();
      if (boundary is! RenderRepaintBoundary) return;
      final slide = await boundary.toImage(pixelRatio: 3);
      // The first slide's wall of covers fills the whole picture
      final bytes = await storyImage(slide, _hue(index), title, fill: index == 0);
      slide.dispose();
      if (bytes == null) return;
      final name = 'playlist-tracker-${widget.month.start.year}-${widget.month.start.month}-${index + 1}';
      if (save) {
        try {
          if (!await Gal.hasPermission()) await Gal.requestPermission();
          await Gal.putImageBytes(bytes, name: name);
          _tell('wrapped.share.saved');
        } on GalException {
          _tell('wrapped.share.failed');
        }
      } else {
        await SharePlus.instance.share(ShareParams(
          files: [XFile.fromData(bytes, mimeType: 'image/png')],
          fileNameOverrides: ['$name.png'],
        ));
      }
    } finally {
      _sharing = false;
    }
  }

  void _go(int index) {
    if (index < 0 || index >= _count) return;
    _pages.animateToPage(index, duration: const Duration(milliseconds: 350), curve: Curves.easeOutCubic);
  }

  void _pause(bool paused) {
    _paused.value = paused;
    if (paused) {
      _timer.stop();
    } else if (!_timer.isCompleted) {
      _timer.forward();
    }
  }

  @override
  void dispose() {
    Preview.instance.stop();
    _pages.dispose();
    _index.dispose();
    _timer.dispose();
    _paused.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final data = _data;
    final month = _year ? '${widget.month.start.year}' : context.dateFormat('MMMM y').format(widget.month.start);
    // Each slide comes in its own way
    final slides = <(_Entrance, List<Widget> Function())>[
      (_Entrance.zoom, () => _intro(context, data)),
      if (data.tracks.isNotEmpty) (_Entrance.spin, () => _topTrack(context, data)),
      if (data.artists.isNotEmpty) (_Entrance.zoom, () => _topArtist(context, data)),
      if (data.tracks.length > 1)
        (_Entrance.fromRight, () => _topList(context, 'wrapped.tracks.caption', data.tracks, DetailKind.track)),
      if (data.artists.length > 1)
        (_Entrance.fromLeft, () => _topList(context, 'wrapped.artists.caption', data.artists, DetailKind.artist)),
      if (data.discoveredTracks.isNotEmpty) (_Entrance.pop, () => _discoveries(context, data)),
      if (data.summary.plays > 0) (_Entrance.rise, () => _rhythm(context, data)),
      if (data.genres.isNotEmpty) (_Entrance.fromRight, () => _genres(context, data)),
      if (data.summary.plays > 0) (_Entrance.zoom, () => _closing(context, data, month)),
    ];
    _count = slides.length;
    final muted = Colors.white.withValues(alpha: 0.72);
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light,
      child: Scaffold(
          backgroundColor: Colors.black,
          body: Stack(
            fit: StackFit.expand,
            children: [
              ValueListenableBuilder(
                valueListenable: _index,
                builder: (context, index, _) => StageBackdrop(hue: _hue(index)),
              ),
              SafeArea(
                child: Column(
                  children: [
                    Padding(
                      padding: const EdgeInsets.fromLTRB(10, 10, 10, 0),
                      child: ValueListenableBuilder(
                        valueListenable: _index,
                        builder: (context, index, _) => StoryBars(count: slides.length, index: index, progress: _timer),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.only(left: 20, right: 4),
                      child: Row(
                        children: [
                          Expanded(
                            child: Text(context.t('wrapped.title', {'month': month}),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(color: muted, fontWeight: FontWeight.w600)),
                          ),
                          ValueListenableBuilder(
                            valueListenable: _paused,
                            builder: (context, paused, _) => AnimatedOpacity(
                              opacity: paused ? 1 : 0,
                              duration: const Duration(milliseconds: 150),
                              child: Icon(Icons.pause, color: muted, size: 20),
                            ),
                          ),
                          IconButton(
                            tooltip: context.t(_sound ? 'wrapped.sound_off' : 'wrapped.sound_on'),
                            icon: Icon(_sound ? Icons.volume_up : Icons.volume_off, color: Colors.white),
                            onPressed: () {
                              setState(() => _sound = !_sound);
                              _playFor(_index.value);
                            },
                          ),
                          IconButton(
                            tooltip: context.t('wrapped.share'),
                            icon: const Icon(Icons.ios_share, color: Colors.white),
                            onPressed: () => _chooseShare(context.t('wrapped.title', {'month': month})),
                          ),
                          IconButton(
                            icon: const Icon(Icons.close, color: Colors.white),
                            onPressed: () => Navigator.of(context).pop(),
                          ),
                        ],
                      ),
                    ),
                    Expanded(
                      // A tap on the left third goes back and anywhere else on, as in stories, and holding keeps
                      // the slide. Pictures and rows that open a page take their own taps first
                      child: LayoutBuilder(
                        builder: (context, box) => GestureDetector(
                          behavior: HitTestBehavior.translucent,
                          onTapUp: (tap) => _go(_index.value + (tap.localPosition.dx < box.maxWidth / 3 ? -1 : 1)),
                          onLongPressStart: (_) => _pause(true),
                          onLongPressEnd: (_) => _pause(false),
                          child: PageView.builder(
                            controller: _pages,
                            itemCount: slides.length,
                            onPageChanged: (index) {
                              _index.value = index;
                              _playFor(index);
                              _timer.forward(from: 0);
                              if (_paused.value) _timer.stop();
                            },
                            // A slide shrinks and fades a little while it is swiped away
                            itemBuilder: (context, index) => AnimatedBuilder(
                              animation: _pages,
                              builder: (context, child) {
                                final page = _pages.hasClients && _pages.position.haveDimensions
                                    ? _pages.page!
                                    : _index.value.toDouble();
                                final away = (page - index).abs().clamp(0.0, 1.0);
                                return Opacity(
                                  opacity: 1 - away * 0.6,
                                  child: Transform.scale(scale: 1 - away * 0.12, child: child),
                                );
                              },
                              // Scaling and fading the slide reuses its last drawing instead of painting it again
                              // every frame
                              child: RepaintBoundary(
                                key: _slideKeys.putIfAbsent(index, GlobalKey.new),
                                child: _Slide(
                                key: ValueKey(index),
                                entrance: slides[index].$1,
                                background: index == 0 ? _wall(data) : null,
                                child: slides[index].$2()),
                              ),
                            ),
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

  // Building blocks

  Widget _caption(BuildContext context, String key, [Map<String, Object> args = const {}]) => Padding(
        padding: const EdgeInsets.only(bottom: 16),
        child: Text(context.t(key, args),
            textAlign: TextAlign.center,
            style: TextStyle(
                color: Palette.of(context).added, fontWeight: FontWeight.w700, fontSize: 15, letterSpacing: 1.2)),
      );

  Widget _big(BuildContext context, int value, String Function(int) text, {Color? color}) =>
      TweenAnimationBuilder<double>(
        tween: Tween(begin: 0, end: value.toDouble()),
        duration: const Duration(milliseconds: 1100),
        curve: Curves.easeOutCubic,
        builder: (context, shown, _) => Text(text(shown.round()),
            textAlign: TextAlign.center,
            style: Theme.of(context)
                .textTheme
                .displaySmall
                ?.copyWith(fontWeight: FontWeight.w700, color: color ?? Palette.of(context).chart)),
      );

  Widget _heading(BuildContext context, String text) => Text(text,
      textAlign: TextAlign.center,
      style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w600));

  Widget _body(BuildContext context, String text, {bool muted = true, double top = 8}) => Padding(
        padding: EdgeInsets.only(top: top),
        child: Text(text,
            textAlign: TextAlign.center,
            style: Theme.of(context)
                .textTheme
                .titleMedium
                ?.copyWith(color: muted ? Palette.of(context).muted : null, fontWeight: FontWeight.w400)),
      );

  /// A page opened from a slide stops its clock until it is closed
  Future<void> _open(DetailTarget target) async {
    _pause(true);
    await openDetail(context, widget.store, target);
    if (mounted) _pause(false);
  }

  // Slides

  /// A small rounded label on the stage, such as "≈ 41 hours"
  Widget _chip(BuildContext context, String text, {IconData? icon}) => Center(
        child: Container(
          margin: const EdgeInsets.only(top: 12),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.14),
            borderRadius: BorderRadius.circular(999),
            border: Border.all(color: Colors.white.withValues(alpha: 0.25)),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (icon != null) ...[Icon(icon, size: 16, color: Colors.white), const SizedBox(width: 6)],
              Flexible(
                child: Text(text,
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
              ),
            ],
          ),
        ),
      );

  /// The wall of the month's covers behind the first slide
  Widget _wall(WrappedData data) => CoverWall(covers: [
        for (final track in data.wall)
          (size) => ArtworkImage.cover(artist: track.artist, album: track.album, name: track.title, size: size),
      ]);

  List<Widget> _intro(BuildContext context, WrappedData data) {
    final summary = data.summary;
    final previous = data.previous;
    final hours = summary.minutes ~/ 60;
    // How this month compares with the one before, by time listened (by plays when lengths are missing)
    final (now, before) =
        previous != null && summary.minutes > 0 && previous.minutes > 0
            ? (summary.minutes, previous.minutes)
            : (summary.plays, previous?.plays ?? 0);
    final change = before > 0 ? ((now - before) * 100 / before).round() : 0;
    final previousName = _year
        ? '${data.range.start.year - 1}'
        : context.dateFormat('MMMM').format(DateTime(data.range.start.year, data.range.start.month - 1));
    return [
      _year
          ? _caption(context, 'wrapped.intro.caption.year', {'year': '${data.range.start.year}'})
          : _caption(context, 'wrapped.intro.caption', {'month': context.dateFormat('MMMM').format(data.range.start)}),
      if (summary.minutes > 0) ...[
        _big(context, summary.minutes, (m) => context.t('wrapped.minutes', {'minutes': context.number(m)})),
        _body(context, context.t('wrapped.intro.listened'), muted: false),
        if (hours >= 2) _chip(context, context.t('wrapped.hours', {'hours': context.number(hours)}), icon: Icons.schedule),
      ] else
        _big(context, summary.plays, context.plays),
      if (before > 0 && change.abs() >= 1)
        _chip(
          context,
          context.t(
            '${change > 0 ? 'wrapped.change.up' : 'wrapped.change.down'}${_year ? '.year' : ''}',
            {'value': context.number(change.abs()), 'previous': previousName},
          ),
          icon: change > 0 ? Icons.trending_up : Icons.trending_down,
        ),
      _body(
          context,
          context.t('wrapped.intro.detail', {
            'plays': context.plays(summary.plays),
            'tracks': context.number(summary.tracks),
            'artists': context.number(summary.artists),
          }),
          top: 20),
    ];
  }

  List<Widget> _topTrack(BuildContext context, WrappedData data) {
    final track = data.tracks.first;
    return [
      _caption(context, _of('wrapped.track.caption')),
      Center(
        child: GestureDetector(
          onTap: () => _open(DetailTarget.ranked(DetailKind.track, track)),
          child: SpinningRecord(
            size: 190,
            cover: ArtworkImage.cover(
                artist: track.artist, album: track.album, name: track.title, size: 190, corner: 16),
            label: ArtworkImage.cover(artist: track.artist, album: track.album, name: track.title, size: 64),
          ),
        ),
      ),
      const SizedBox(height: 20),
      _heading(context, track.title),
      _body(context, track.artist, top: 4),
      _big(context, track.plays, (n) => context.t('wrapped.times', {'count': context.number(n)})),
      if (track.minutes > 0) _chip(context, context.t('wrapped.track.time', {'time': context.minutes(track.minutes)}),
          icon: Icons.headphones),
    ];
  }

  List<Widget> _topArtist(BuildContext context, WrappedData data) {
    final artist = data.artists.first;
    final share = data.summary.plays == 0 ? 0.0 : artist.plays / data.summary.plays;
    return [
      _caption(context, _of('wrapped.artist.caption')),
      Center(
        child: GestureDetector(
          onTap: () => _open(DetailTarget.ranked(DetailKind.artist, artist)),
          child: ShareRing(share: share, size: 180, photo: ArtworkImage.artist(artist: artist.artist, size: 180)),
        ),
      ),
      _heading(context, artist.title),
      _body(context,
          [context.plays(artist.plays), if (artist.minutes > 0) context.minutes(artist.minutes)].join('  ·  '),
          muted: false),
      _chip(context, context.t('wrapped.artist.share', {'value': context.number((share * 100).round())}),
          icon: Icons.pie_chart_outline),
    ];
  }

  List<Widget> _topList(BuildContext context, String caption, List<Ranked> rows, DetailKind kind) => [
        _caption(context, caption),
        Podium(entries: [
          for (final row in rows)
            PodiumEntry(
              title: row.title,
              subtitle: kind == DetailKind.track ? row.artist : '',
              value: context.plays(row.plays),
              picture: (size) => kind == DetailKind.track
                  ? ArtworkImage.cover(artist: row.artist, album: row.album, name: row.title, size: size)
                  : ArtworkImage.artist(artist: row.artist, size: size),
              onTap: () => _open(DetailTarget.ranked(kind, row)),
            ),
        ]),
      ];

  List<Widget> _discoveries(BuildContext context, WrappedData data) => [
        _caption(context, 'wrapped.discoveries.caption'),
        if (data.discoveredArtists.isNotEmpty)
          FloatingBubbles(pictures: [
            for (final found in data.discoveredArtists)
              (size) => GestureDetector(
                    onTap: () => _open(DetailTarget.ranked(DetailKind.artist, found.row)),
                    child: ArtworkImage.artist(artist: found.row.artist, size: size),
                  ),
          ]),
        const SizedBox(height: 8),
        _big(context, data.discoveredTracks.length, (n) => context.t('wrapped.new_tracks', {'count': context.number(n)})),
        _body(context, context.t('wrapped.new_artists', {'count': context.number(data.discoveredArtists.length)}),
            muted: false),
        if (data.discoveredArtists.isNotEmpty)
          _chip(context, context.t('wrapped.top_new_artist', {'name': data.discoveredArtists.first.row.title}),
              icon: Icons.auto_awesome),
        if (data.firstMonth) _body(context, context.t('stats.discoveries.first_period'), top: 16),
      ];

  List<Widget> _rhythm(BuildContext context, WrappedData data) {
    final hours = data.hours;
    final peak = List.generate(24, (h) => h).reduce((a, b) => hours[b] > hours[a] ? b : a);
    String hour(int h) => '${(h % 24).toString().padLeft(2, '0')}:00';
    final now = DateTime.now();
    final end = data.range.end.isBefore(now) ? data.range.end : now;
    final days = end.difference(data.range.start).inDays + 1;
    final (busiest, busiestPlays) = data.busiest!;
    // Monday first, as the statistics' calendar
    final monday = DateTime(2024, 1, 1);
    final headers = _year
        ? const <String>[]
        : [for (var d = 0; d < 7; d++) context.dateFormat('EEEEE').format(monday.add(Duration(days: d)))];
    return [
      _caption(context, 'wrapped.rhythm.caption'),
      Center(
        child: HourClock(
          hours: hours,
          size: 240,
          center: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(hour(peak),
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
              Text(context.t('wrapped.peak_hour.short'),
                  style: TextStyle(color: Palette.of(context).muted, fontSize: 12)),
            ],
          ),
        ),
      ),
      const SizedBox(height: 12),
      Center(
        child: DotCalendar(
          counts: data.calendar,
          columns: _year ? 6 : 7,
          blank: _year ? 0 : data.range.start.weekday - 1,
          headers: headers,
        ),
      ),
      _body(
          context,
          context.t('wrapped.busiest', {
            'day': context.dateFormat(_year ? 'd MMMM' : 'd MMMM, EEEE').format(busiest),
            'plays': context.plays(busiestPlays),
          }),
          muted: false,
          top: 14),
      _body(
          context,
          context.t('wrapped.days_listened', {
            'active': context.number(data.daysListened),
            'days': context.number(days < data.daysListened ? data.daysListened : days),
          }),
          top: 6),
    ];
  }

  List<Widget> _genres(BuildContext context, WrappedData data) {
    final (name, percent) = data.genres.first;
    String share(int value) => context.t('stats.percent', {'value': value});
    return [
      _caption(context, 'wrapped.genres.caption'),
      GenreSpotlight(
        name: capitalized(name),
        share: context.t('wrapped.genre.share', {'value': share(percent)}),
        message: context.t(genreMessage(name, data.genres.length > 1 ? data.genres[1].$1 : null)),
        photos: [
          for (final artist in data.genreArtists[name] ?? const <Ranked>[])
            (size) => GestureDetector(
                  onTap: () => _open(DetailTarget.ranked(DetailKind.artist, artist)),
                  child: ArtworkImage.artist(artist: artist.artist, size: size),
                ),
        ],
        others: [
          for (final (other, value) in data.genres.skip(1)) (capitalized(other), value, share(value)),
        ],
      ),
    ];
  }

  List<Widget> _closing(BuildContext context, WrappedData data, String month) =>
      [_Poster(data: data, month: month, year: _year, open: _open)];
}

/// The closing slide: the month on one card, made to be looked at (or screenshotted) on its own
class _Poster extends StatelessWidget {
  /// How long the card's rows take to come in, one after another
  static const _rows = Duration(milliseconds: 1600);

  final WrappedData data;
  final String month;

  /// A year's card: "Your year at a glance", "Genre of the year"
  final bool year;
  final void Function(DetailTarget target) open;

  const _Poster({required this.data, required this.month, required this.year, required this.open});

  String _of(String key) => year ? '$key.year' : key;

  /// Fades and slides in its child once [order] of the card's rows have come in
  Widget _later(int order, Widget child) {
    final start = (order * 0.07).clamp(0.0, 0.7);
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: _rows,
      curve: Interval(start, (start + 0.3).clamp(0.0, 1.0), curve: Curves.easeOutCubic),
      builder: (context, shown, child) => Opacity(
        opacity: shown,
        child: Transform.translate(offset: Offset(0, 12 * (1 - shown)), child: child),
      ),
      child: child,
    );
  }

  /// The top three artists' photos, the first in front and bigger
  Widget _photos(BuildContext context) {
    final artists = data.artists.take(3).toList();
    if (artists.isEmpty) return const SizedBox();
    const big = 112.0, small = 76.0;
    Widget ring(Widget child) => Container(
          padding: const EdgeInsets.all(3),
          decoration: BoxDecoration(shape: BoxShape.circle, color: Colors.white.withValues(alpha: 0.85)),
          child: child,
        );
    Widget photo(int index, double size) => GestureDetector(
          onTap: () => open(DetailTarget.ranked(DetailKind.artist, artists[index])),
          child: ring(ArtworkImage.artist(artist: artists[index].artist, size: size)),
        );
    return SizedBox(
      height: big + 6,
      child: Stack(
        alignment: Alignment.center,
        children: [
          if (artists.length > 1) Transform.translate(offset: const Offset(-74, 14), child: photo(1, small)),
          if (artists.length > 2) Transform.translate(offset: const Offset(74, 14), child: photo(2, small)),
          photo(0, big),
        ],
      ),
    );
  }

  Widget _column(BuildContext context, String title, List<Ranked> rows, DetailKind kind, int first) {
    final muted = Palette.of(context).muted;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _later(first, Text(title, style: TextStyle(color: muted, fontSize: 12, fontWeight: FontWeight.w600))),
        const SizedBox(height: 6),
        for (final (index, row) in rows.indexed)
          _later(
            first + 1 + index,
            InkWell(
              onTap: () => open(DetailTarget.ranked(kind, row)),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: Row(
                  children: [
                    SizedBox(
                      width: 18,
                      child: Text('${index + 1}',
                          style: TextStyle(
                              color: index == 0 ? Palette.of(context).chart : muted, fontWeight: FontWeight.w700)),
                    ),
                    Expanded(
                      child: Text(row.title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(fontWeight: index == 0 ? FontWeight.w700 : FontWeight.w500)),
                    ),
                  ],
                ),
              ),
            ),
          ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final palette = Palette.of(context);
    final summary = data.summary;
    final big = Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800, height: 1.1);
    final label = TextStyle(color: palette.muted, fontSize: 12, fontWeight: FontWeight.w600);
    final genre = data.genres.isEmpty ? null : capitalized(data.genres.first.$1);
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 20),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: palette.border),
        // A pane of glass over the stage's color
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Colors.white.withValues(alpha: 0.16), Colors.black.withValues(alpha: 0.22)],
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _photos(context),
          const SizedBox(height: 14),
          _later(
            1,
            Text(month,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
          ),
          _later(
            1,
            Text(context.t(_of('wrapped.poster.caption')),
                textAlign: TextAlign.center, style: label.copyWith(letterSpacing: 1.5)),
          ),
          const SizedBox(height: 18),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                  child: _column(context, context.t('wrapped.artists.caption'), data.artists, DetailKind.artist, 2)),
              const SizedBox(width: 14),
              Expanded(child: _column(context, context.t('wrapped.tracks.caption'), data.tracks, DetailKind.track, 3)),
            ],
          ),
          const SizedBox(height: 18),
          _later(
            9,
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(context.t('wrapped.poster.minutes'), style: label),
                      TweenAnimationBuilder<double>(
                        tween: Tween(begin: 0, end: summary.minutes.toDouble()),
                        duration: _rows,
                        curve: const Interval(0.5, 1, curve: Curves.easeOutCubic),
                        builder: (context, shown, _) =>
                            Text(context.number(shown.round()), style: big?.copyWith(color: palette.chart)),
                      ),
                    ],
                  ),
                ),
                if (genre != null)
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(context.t(_of('wrapped.genre')), style: label),
                        Text(genre, maxLines: 2, overflow: TextOverflow.ellipsis, style: big?.copyWith(fontSize: 22)),
                      ],
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          _later(
            10,
            Text(
              [
                context.plays(summary.plays),
                context.t('wrapped.poster.tracks', {'count': context.number(summary.tracks)}),
                context.t('wrapped.poster.artists', {'count': context.number(summary.artists)}),
              ].join('  ·  '),
              textAlign: TextAlign.center,
              style: TextStyle(color: palette.muted, fontSize: 13),
            ),
          ),
        ],
      ),
    );
  }
}

/// How a slide's parts come in
enum _Entrance { rise, zoom, spin, fromLeft, fromRight, pop }

/// A slide's parts come in one after another when it first shows, each slide in its own way
class _Slide extends StatefulWidget {
  final _Entrance entrance;
  final List<Widget> child;

  /// Behind the slide's parts, filling it (the first slide's wall of covers)
  final Widget? background;

  const _Slide({super.key, required this.entrance, required this.child, this.background});

  @override
  State<_Slide> createState() => _SlideState();
}

class _SlideState extends State<_Slide> with SingleTickerProviderStateMixin {
  static const _part = 520;
  static const _step = 120;

  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    final total = _part + _step * (widget.child.length - 1).clamp(0, 20);
    _controller = AnimationController(vsync: this, duration: Duration(milliseconds: total))..forward();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Widget _enter(Widget part, int index) {
    final total = _controller.duration!.inMilliseconds;
    final start = (index * _step / total).clamp(0.0, 1.0);
    final end = ((index * _step + _part) / total).clamp(0.0, 1.0);
    Animation<double> curve(Curve curve) =>
        CurvedAnimation(parent: _controller, curve: Interval(start, end, curve: curve));
    Widget slide(Offset from) => SlideTransition(
        position: Tween(begin: from, end: Offset.zero).animate(curve(Curves.easeOutCubic)), child: part);
    Widget scale(double from, Curve how, Widget child) =>
        ScaleTransition(scale: Tween(begin: from, end: 1.0).animate(curve(how)), child: child);
    final moved = switch (widget.entrance) {
      _Entrance.rise => slide(const Offset(0, 0.25)),
      _Entrance.fromLeft => slide(const Offset(-0.35, 0)),
      _Entrance.fromRight => slide(const Offset(0.35, 0)),
      _Entrance.zoom => scale(0.6, Curves.easeOutBack, part),
      _Entrance.pop => scale(0.3, Curves.elasticOut, part),
      // The caption drops in, the picture turns in, the rest rises
      _Entrance.spin => index == 1
          ? RotationTransition(
              turns: Tween(begin: -0.08, end: 0.0).animate(curve(Curves.easeOutBack)),
              child: scale(0.5, Curves.easeOutBack, part))
          : slide(Offset(0, index == 0 ? -0.4 : 0.25)),
    };
    return FadeTransition(opacity: curve(Curves.easeOut), child: moved);
  }

  @override
  Widget build(BuildContext context) {
    final parts = Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [for (final (index, part) in widget.child.indexed) _enter(part, index)],
        ),
      ),
    );
    final background = widget.background;
    if (background == null) return parts;
    return Stack(
      fit: StackFit.expand,
      children: [
        FadeTransition(opacity: CurvedAnimation(parent: _controller, curve: Curves.easeOut), child: background),
        parts,
      ],
    );
  }
}
