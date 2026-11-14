import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../data/genres.dart';
import '../../data/models.dart';
import '../../data/stats.dart';
import '../../l10n/strings.dart';
import '../../state/data_store.dart';
import '../../theme/palette.dart';
import '../../widgets/artwork_image.dart';
import '../../widgets/cards.dart';
import '../../widgets/format.dart';
import 'detail_screen.dart';
import 'genre_cards.dart' show capitalized;
import 'listening_chart.dart';

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

  WrappedData._(this.range, this.summary, this.tracks, this.artists, this.discoveredTracks, this.discoveredArtists,
      this.firstMonth, this.busiest, this.daysListened, this.hours, this.genres);

  factory WrappedData.of(List<Play> all, DateRange range) {
    final plays = playsIn(all, range);
    final artists = topArtists(plays, limit: 1 << 30);
    final genres = <String, int>{};
    for (final artist in artists) {
      final genre = Genres.instance.mainGenre(artist.key);
      if (genre != null) genres[genre] = (genres[genre] ?? 0) + artist.plays;
    }
    final days = <DateTime, int>{};
    for (final play in plays) {
      final day = DateTime(play.playedAt.year, play.playedAt.month, play.playedAt.day);
      days[day] = (days[day] ?? 0) + 1;
    }
    final busiest = days.entries.fold<MapEntry<DateTime, int>?>(
        null, (best, day) => best == null || day.value > best.value ? day : best);
    final first = all.isEmpty ? null : all.map((p) => p.playedAt).reduce((a, b) => a.isBefore(b) ? a : b);
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

void openWrapped(BuildContext context, DataStore store, DateRange month) => Navigator.of(context)
    .push(MaterialPageRoute(builder: (_) => WrappedScreen(store: store, month: month), fullscreenDialog: true));

class WrappedScreen extends StatefulWidget {
  final DataStore store;
  final DateRange month;

  const WrappedScreen({super.key, required this.store, required this.month});

  @override
  State<WrappedScreen> createState() => _WrappedScreenState();
}

class _WrappedScreenState extends State<WrappedScreen> {
  final _pages = PageController();

  /// Kept out of the state so that turning a page, halfway through the swipe, redraws only the dots below
  final _index = ValueNotifier(0);

  /// Worked out once: going over every play again at each page turn made the swipes stutter
  late final _data = WrappedData.of(widget.store.plays, widget.month);

  late final _year = isYear(widget.month);

  /// The year's wording of a text in a yearly summary: "Song of the year" for "Song of the month"
  String _of(String key) => _year ? '$key.year' : key;

  @override
  void dispose() {
    _pages.dispose();
    _index.dispose();
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
    final last = slides.length - 1;
    void go(int index) =>
        _pages.animateToPage(index, duration: const Duration(milliseconds: 350), curve: Curves.easeOutCubic);
    return Scaffold(
      appBar: AppBar(
        title: Text(context.t('wrapped.title', {'month': month})),
        leading: IconButton(icon: const Icon(Icons.close), onPressed: () => Navigator.of(context).pop()),
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: PageView.builder(
                controller: _pages,
                itemCount: slides.length,
                onPageChanged: (index) => _index.value = index,
                // A slide shrinks and fades a little while it is swiped away
                itemBuilder: (context, index) => AnimatedBuilder(
                  animation: _pages,
                  builder: (context, child) {
                    final page =
                        _pages.hasClients && _pages.position.haveDimensions ? _pages.page! : _index.value.toDouble();
                    final away = (page - index).abs().clamp(0.0, 1.0);
                    return Opacity(
                      opacity: 1 - away * 0.6,
                      child: Transform.scale(scale: 1 - away * 0.12, child: child),
                    );
                  },
                  // Scaling and fading the slide reuses its last drawing instead of painting it again every frame
                  child: RepaintBoundary(
                    child: _Slide(key: ValueKey(index), entrance: slides[index].$1, child: slides[index].$2()),
                  ),
                ),
              ),
            ),
            ValueListenableBuilder(
              valueListenable: _index,
              builder: (context, index, _) => Padding(
                padding: const EdgeInsets.fromLTRB(8, 0, 8, 8),
                child: Row(
                  children: [
                    IconButton(onPressed: index > 0 ? () => go(index - 1) : null, icon: const Icon(Icons.chevron_left)),
                    Expanded(
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          for (var i = 0; i < slides.length; i++)
                            AnimatedContainer(
                              duration: changeDuration,
                              curve: changeCurve,
                              margin: const EdgeInsets.symmetric(horizontal: 3),
                              width: i == index ? 18 : 7,
                              height: 7,
                              decoration: BoxDecoration(
                                color: i == index ? Palette.of(context).chart : Palette.of(context).border,
                                borderRadius: BorderRadius.circular(4),
                              ),
                            ),
                        ],
                      ),
                    ),
                    IconButton(
                        onPressed: index < last ? () => go(index + 1) : null, icon: const Icon(Icons.chevron_right)),
                  ],
                ),
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

  void _open(DetailTarget target) => openDetail(context, widget.store, target);

  // Slides

  List<Widget> _intro(BuildContext context, WrappedData data) {
    final summary = data.summary;
    return [
      _year
          ? _caption(context, 'wrapped.intro.caption.year', {'year': '${data.range.start.year}'})
          : _caption(context, 'wrapped.intro.caption', {'month': context.dateFormat('MMMM').format(data.range.start)}),
      if (summary.minutes > 0) ...[
        _big(context, summary.minutes, (m) => context.t('wrapped.minutes', {'minutes': context.number(m)})),
        _body(context, context.t('wrapped.intro.listened'), muted: false),
      ] else
        _big(context, summary.plays, context.plays),
      _body(
          context,
          context.t('wrapped.intro.detail', {
            'plays': context.plays(summary.plays),
            'tracks': context.number(summary.tracks),
            'artists': context.number(summary.artists),
          }),
          top: 16),
    ];
  }

  List<Widget> _topTrack(BuildContext context, WrappedData data) {
    final track = data.tracks.first;
    return [
      _caption(context, _of('wrapped.track.caption')),
      Center(
        child: GestureDetector(
          onTap: () => _open(DetailTarget.ranked(DetailKind.track, track)),
          child: ArtworkImage.cover(artist: track.artist, album: track.album, name: track.title, size: 200),
        ),
      ),
      const SizedBox(height: 16),
      _heading(context, track.title),
      _body(context, track.artist, top: 4),
      _body(context, context.t('wrapped.times', {'count': context.number(track.plays)}), muted: false, top: 16),
    ];
  }

  List<Widget> _topArtist(BuildContext context, WrappedData data) {
    final artist = data.artists.first;
    return [
      _caption(context, _of('wrapped.artist.caption')),
      Center(
        child: GestureDetector(
          onTap: () => _open(DetailTarget.ranked(DetailKind.artist, artist)),
          child: ArtworkImage.artist(artist: artist.artist, size: 200),
        ),
      ),
      const SizedBox(height: 16),
      _heading(context, artist.title),
      _body(context,
          [context.plays(artist.plays), if (artist.minutes > 0) context.minutes(artist.minutes)].join('  ·  '),
          muted: false),
    ];
  }

  List<Widget> _topList(BuildContext context, String caption, List<Ranked> rows, DetailKind kind) => [
        _caption(context, caption),
        RankedList(
          rows: rows,
          image: (row) => kind == DetailKind.track
              ? ArtworkImage.cover(artist: row.artist, album: row.album, name: row.title)
              : ArtworkImage.artist(artist: row.artist),
          onTap: (row) => _open(DetailTarget.ranked(kind, row)),
        ),
      ];

  List<Widget> _discoveries(BuildContext context, WrappedData data) => [
        _caption(context, 'wrapped.discoveries.caption'),
        _big(context, data.discoveredTracks.length, (n) => context.t('wrapped.new_tracks', {'count': context.number(n)})),
        _body(context, context.t('wrapped.new_artists', {'count': context.number(data.discoveredArtists.length)}),
            muted: false),
        if (data.discoveredArtists.isNotEmpty)
          _body(context, context.t('wrapped.top_new_artist', {'name': data.discoveredArtists.first.row.title}), top: 16),
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
    return [
      _caption(context, 'wrapped.rhythm.caption'),
      _body(
          context,
          context.t('wrapped.busiest', {
            'day': context.dateFormat('d MMMM, EEEE').format(busiest),
            'plays': context.plays(busiestPlays),
          }),
          muted: false,
          top: 0),
      const SizedBox(height: 16),
      _heading(context, '${hour(peak)} – ${hour(peak + 1)}'),
      _body(context, context.t('wrapped.peak_hour'), top: 4),
      const SizedBox(height: 16),
      ListeningChart(
        period: Period.all,
        plays: true,
        buckets: [for (final (h, count) in hours.indexed) Bucket(DateTime(2000, 1, 1, h), 0, count)],
        label: (context, start) => start.hour.toString().padLeft(2, '0'),
      ),
      _body(
          context,
          context.t('wrapped.days_listened', {
            'active': context.number(data.daysListened),
            'days': context.number(days < data.daysListened ? data.daysListened : days),
          }),
          top: 16),
    ];
  }

  List<Widget> _genres(BuildContext context, WrappedData data) => [
        _caption(context, 'wrapped.genres.caption'),
        for (final (index, (name, percent)) in data.genres.indexed)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: index == 0
                ? _big(context, percent,
                    (v) => '${capitalized(name)}  ${context.t('stats.percent', {'value': v})}')
                : TweenAnimationBuilder<double>(
                    tween: Tween(begin: 0, end: percent.toDouble()),
                    duration: const Duration(milliseconds: 1100),
                    curve: Curves.easeOutCubic,
                    builder: (context, shown, _) => Text(
                      '${capitalized(name)}  ${context.t('stats.percent', {'value': shown.round()})}',
                      textAlign: TextAlign.center,
                      style: Theme.of(context)
                          .textTheme
                          .headlineSmall
                          ?.copyWith(color: Palette.of(context).muted, fontWeight: FontWeight.w600),
                    ),
                  ),
          ),
      ];

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
          decoration: BoxDecoration(shape: BoxShape.circle, color: Theme.of(context).colorScheme.surface),
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
    final surface = Theme.of(context).colorScheme.surface;
    final summary = data.summary;
    final big = Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800, height: 1.1);
    final label = TextStyle(color: palette.muted, fontSize: 12, fontWeight: FontWeight.w600);
    final genre = data.genres.isEmpty ? null : capitalized(data.genres.first.$1);
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 20),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: palette.chart.withValues(alpha: 0.35)),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color.lerp(palette.chart, surface, 0.55)!, Color.lerp(palette.chart, surface, 0.88)!, surface],
          stops: const [0, 0.45, 1],
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

  const _Slide({super.key, required this.entrance, required this.child});

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
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [for (final (index, part) in widget.child.indexed) _enter(part, index)],
        ),
      ),
    );
  }
}
