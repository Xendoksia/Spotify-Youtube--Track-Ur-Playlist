import 'package:flutter/material.dart';

import '../../data/artwork.dart';
import '../../data/models.dart';
import '../../data/mood.dart';
import '../../data/stats.dart';
import '../../l10n/strings.dart';
import '../../state/data_store.dart';
import '../../theme/palette.dart';
import '../../widgets/artwork_image.dart';
import '../../widgets/cards.dart';
import '../../widgets/format.dart';
import '../../widgets/hour_clock.dart';
import '../../widgets/skeleton.dart';
import '../../widgets/sparkline.dart';
import 'collage_card.dart';
import 'detail_screen.dart';
import 'discoveries.dart';
import 'genre_cards.dart';
import 'listening_chart.dart';
import 'period_bar.dart';
import 'search_screen.dart';
import 'trends.dart';
import 'wrapped_screen.dart';

/// The statistics of the plays synced from the desktop app, by week, month, year or all time
class ListeningScreen extends StatefulWidget {
  final DataStore store;
  final Future<void> Function() onRefresh;

  const ListeningScreen({super.key, required this.store, required this.onRefresh});

  @override
  State<ListeningScreen> createState() => _ListeningScreenState();
}

class _ListeningScreenState extends State<ListeningScreen> {
  // Opens on the current week, as the desktop app does
  var _period = Period.week;
  var _offset = 0;
  var _recentShown = recentStep;
  var _wrappedChecked = false;

  /// The plays the summaries waiting behind the bell were last looked for in
  List<Play>? _inboxOf;

  /// The color of the period's number one cover (else of the number one artist's photo), and whose it is
  final _mood = ValueNotifier<Mood?>(null);
  String? _moodOf;

  /// Where the next period's content comes from: -1 from the left (an earlier period), 1 from the right, 0 rising
  /// (another kind of period)
  var _direction = 0;

  @override
  void initState() {
    super.initState();
    WrappedNotice.listen();
    WrappedNotice.tapped.addListener(_noticeTapped);
  }

  @override
  void dispose() {
    WrappedNotice.tapped.removeListener(_noticeTapped);
    _mood.dispose();
    super.dispose();
  }

  /// The summary notification tapped while the app was open
  void _noticeTapped() {
    final month = WrappedNotice.tapped.value;
    if (month == null || !widget.store.loaded) return;
    WrappedNotice.tapped.value = null;
    openWrapped(context, widget.store, month);
  }

  /// On the first days of a month the summary of the month before opens by itself, once, or the one of the
  /// notification the app was opened from
  void _checkWrapped() {
    if (_wrappedChecked) return;
    _wrappedChecked = true;
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      final plays = widget.store.plays;
      final now = DateTime.now();
      await WrappedNotice.remember(plays, now);
      final tapped = WrappedNotice.tapped.value;
      WrappedNotice.tapped.value = null;
      final month = tapped ?? await WrappedNotice.takeTapped() ?? await wrappedDue(plays, now);
      // After the summary opened by itself was marked as seen
      await WrappedInbox.instance.update(plays, now);
      _inboxOf = plays;
      if (!mounted) return;
      if (month != null) {
        openWrapped(context, widget.store, month);
      } else {
        // Not over the summary
        WrappedNotice.askPermission();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.store,
      builder: (context, _) {
        final store = widget.store;
        if (!store.loaded) {
          if (store.error == null) {
            return ListView(padding: const EdgeInsets.all(16), children: const [ListeningSkeleton()]);
          }
          return Center(
            child: MessageView(
              icon: Icons.cloud_off,
              text: context.t('load.failed', {'error': store.error!}),
              action: context.t('load.retry'),
              onAction: widget.onRefresh,
            ),
          );
        }
        if (store.plays.isNotEmpty) _checkWrapped();
        // New plays (a month's first, after a refresh) can bring a summary
        if (_inboxOf != null && !identical(_inboxOf, store.plays)) {
          _inboxOf = store.plays;
          WrappedInbox.instance.update(store.plays, DateTime.now());
        }
        final list = RefreshIndicator(
          onRefresh: widget.onRefresh,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: store.plays.isEmpty
                ? [MessageView(icon: Icons.headphones, text: context.t('stats.none_yet'))]
                : _content(context, store.plays),
          ),
        );
        // The page's accents glide to the new number one's color; a soft wash of it comes down from the top
        return MoodWash(mood: _mood, child: list);
      },
    );
  }

  List<Widget> _content(BuildContext context, List<Play> all) {
    final now = DateTime.now();
    final range = periodRange(_period, _offset, now);
    final plays = playsIn(all, range);
    final summary = Summary.of(plays);
    final previous = previousSummary(all, _period, _offset, now);
    final tracks = topTracks(plays);
    final artists = topArtists(plays);
    final trackChange = rankChanges(all, _period, _offset, now, trackKeyOf);
    final artistChange = rankChanges(all, _period, _offset, now, artistKeyOf);
    final days = trend(_period, range, plays, now);
    final previousTimeline = _period == Period.all ? null : previousBuckets(all, _period, _offset, now);
    final yearAgo = yearAgoMonth(now);
    final yearAgoPlays = playsIn(all, yearAgo);
    _findMood(tracks.firstOrNull, artists.firstOrNull);
    const gap = SizedBox(height: 12);
    return [
      PeriodBar(
        period: _period,
        offset: _offset,
        range: range,
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconButton(
              tooltip: context.t('search.placeholder'),
              icon: const Icon(Icons.search),
              onPressed: () =>
                  Navigator.of(context).push(MaterialPageRoute(builder: (_) => SearchScreen(store: widget.store))),
            ),
            WrappedInboxButton(store: widget.store),
          ],
        ),
        onPeriod: (period) => setState(() {
          _direction = 0;
          _period = period;
          _offset = 0;
        }),
        onOffset: (offset) => setState(() {
          _direction = offset > _offset ? -1 : 1;
          _offset = offset;
        }),
      ),
      gap,
      // Rows rather than a grid with a fixed aspect ratio, so the tiles grow with the phone's font size
      Row(
        children: [
          Expanded(
            child: _tile(context, 'stats.plays', summary.plays, previous?.plays, context.number, days, (s) => s.plays),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: _tile(
              context,
              'stats.time',
              summary.minutes,
              previous?.minutes,
              context.minutes,
              days,
              (s) => s.minutes,
            ),
          ),
        ],
      ),
      const SizedBox(height: 8),
      Row(
        children: [
          Expanded(
            child: _tile(
              context,
              'stats.tracks',
              summary.tracks,
              previous?.tracks,
              context.number,
              days,
              (s) => s.tracks,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: _tile(
              context,
              'stats.artists',
              summary.artists,
              previous?.artists,
              context.number,
              days,
              (s) => s.artists,
            ),
          ),
        ],
      ),
      gap,
      // The tiles count to the new numbers; the cards under them change with the period, each by itself:
      // straight in the list rather than in one column, so only the cards on the screen are built when the period
      // changes
      for (final (index, card)
          in (plays.isEmpty
                  ? [MessageView(icon: Icons.music_off, text: context.t('stats.empty'))]
                  : [
                      _trackHero(context, tracks.first, trackChange),
                      const SizedBox(height: 8),
                      _artistHero(context, artists.first, plays, artistChange),
                      if (tracks.length > 1) ...[
                        gap,
                        SectionCard(
                          title: context.t('stats.top_tracks'),
                          child: RankedList(
                            rows: tracks.sublist(1),
                            firstRank: 2,
                            change: trackChange,
                            image: (row) => ArtworkImage.cover(
                              artist: row.artist,
                              album: row.album,
                              name: row.title,
                              hero: heroTag(DetailKind.track, row.key, 1),
                            ),
                            onTap: (row) =>
                                openDetail(context, widget.store, DetailTarget.ranked(DetailKind.track, row)),
                          ),
                        ),
                      ],
                      if (artists.length > 1) ...[
                        gap,
                        SectionCard(
                          title: context.t('stats.top_artists'),
                          child: RankedList(
                            rows: artists.sublist(1),
                            firstRank: 2,
                            change: artistChange,
                            image: (row) =>
                                ArtworkImage.artist(artist: row.artist, hero: heroTag(DetailKind.artist, row.key, 1)),
                            onTap: (row) =>
                                openDetail(context, widget.store, DetailTarget.ranked(DetailKind.artist, row)),
                          ),
                        ),
                      ],
                      gap,
                      SectionCard(
                        title: context.t('stats.top_albums'),
                        child: RankedList(
                          rows: topAlbums(plays),
                          image: (row) => ArtworkImage.album(
                            artist: row.artist,
                            album: row.album,
                            hero: heroTag(DetailKind.album, row.key, 1),
                          ),
                          onTap: (row) => openDetail(context, widget.store, DetailTarget.ranked(DetailKind.album, row)),
                        ),
                      ),
                      gap,
                      SectionCard(
                        // Plays, as on the desktop app: per day of a week or month, per month of a year, per year of all
                        title: context.t(switch (_period) {
                          Period.week || Period.month => 'stats.per_day',
                          Period.year => 'stats.per_month',
                          Period.all => 'stats.per_year',
                        }),
                        child: ListeningChart(
                          period: _period,
                          plays: true,
                          buckets: buckets(_period, range, plays),
                          values: true,
                          previous: previousTimeline,
                          legend: previousTimeline == null
                              ? null
                              : (context.t('stats.this.${_period.name}'), context.t('stats.previous.${_period.name}')),
                        ),
                      ),
                      gap,
                      SectionCard(
                        title: context.t('stats.hours'),
                        child: HourClock(hours: playsPerHour(plays)),
                      ),
                      gap,
                      Discoveries(store: widget.store, period: _period, range: range, plays: plays),
                      gap,
                      DiversityCard(store: widget.store, period: _period, offset: _offset, range: range, plays: plays),
                      gap,
                      StreakCard(store: widget.store),
                      gap,
                      if (yearAgoPlays.isNotEmpty) ...[
                        YearAgoCard(
                          store: widget.store,
                          month: yearAgo.start,
                          plays: yearAgoPlays,
                          thisMonth: playsIn(all, periodRange(Period.month, 0, now)),
                        ),
                        gap,
                      ],
                      MilestonesCard(store: widget.store, range: range),
                      gap,
                      GenresCard(all: all, plays: plays),
                      gap,
                      GenreShiftCard(period: _period, range: range, plays: plays),
                      gap,
                      CollageCard(store: widget.store, plays: plays),
                    ])
              .indexed)
        card is SizedBox
            ? card
            : _Appear(key: ValueKey('$_period/$_offset/$index'), direction: _direction, child: card),
      gap,
      SectionCard(
        title: context.t('stats.recent'),
        child: _RecentPlays(
          plays: all,
          shown: _recentShown,
          onMore: () => setState(() => _recentShown += recentStep),
          onTap: (play) => openDetail(context, widget.store, DetailTarget.track(play)),
        ),
      ),
    ];
  }

  StatTile _tile(
    BuildContext context,
    String label,
    int value,
    int? before,
    String Function(int) format,
    Trend days,
    int Function(Summary) of,
  ) {
    final change = before == null ? null : percentChange(value, before);
    String? note;
    if (change != null) {
      final arrow = change > 0
          ? '▲'
          : change < 0
          ? '▼'
          : '=';
      note = '$arrow ${context.t('stats.percent', {'value': change.abs()})}  ${context.t('stats.vs.${_period.name}')}';
    }
    final when = context.dateFormat(switch (days.unit) {
      TrendUnit.day => 'd MMM',
      TrendUnit.month => 'MMM y',
      TrendUnit.year => 'y',
    });
    return StatTile.count(
      label: context.t(label),
      count: value,
      format: format,
      note: note,
      trend: [
        for (final (index, start) in days.starts.indexed)
          TrendPoint(of(days.values[index]), '${when.format(start)}  ·  ${format(of(days.values[index]))}'),
      ],
    );
  }

  /// Looks up the color of the number one's cover once per number one; grey covers keep the usual colors
  void _findMood(Ranked? track, Ranked? artist) {
    final which = track != null
        ? 'track|${track.key}'
        : artist != null
        ? 'artist|${artist.key}'
        : null;
    if (which == _moodOf) return;
    _moodOf = which;
    if (which == null) {
      _mood.value = null;
      return;
    }
    () async {
      Mood? found;
      final cover = track == null ? null : await Artwork.instance.cover(track.artist, track.album, track.title);
      if (cover != null) found = await moodOf(cover);
      if (found == null && artist != null) {
        final photo = await Artwork.instance.artistPhoto(artist.artist);
        if (photo != null) found = await moodOf(photo);
      }
      if (mounted && _moodOf == which) _mood.value = found;
    }();
  }

  String _detail(BuildContext context, Ranked row) =>
      [context.plays(row.plays), if (row.minutes > 0) context.minutes(row.minutes)].join('  ·  ');

  Widget _trackHero(BuildContext context, Ranked top, RankChange? Function(String, int) change) => HeroCard(
    caption: context.t('stats.hero.track'),
    title: top.title,
    subtitle: top.artist,
    detail: _detail(context, top),
    change: change(top.key, 1),
    image: ArtworkImage.cover(
      artist: top.artist,
      album: top.album,
      name: top.title,
      size: 88,
      hero: heroTag(DetailKind.track, top.key, 1),
    ),
    onTap: () => openDetail(context, widget.store, DetailTarget.ranked(DetailKind.track, top)),
  );

  Widget _artistHero(BuildContext context, Ranked top, List<Play> plays, RankChange? Function(String, int) change) {
    final tracks = plays.where((p) => p.artistKey == top.key).map((p) => p.trackKey).toSet().length;
    return HeroCard(
      caption: context.t('stats.hero.artist'),
      title: top.title,
      subtitle: tracks == 1
          ? context.t('stats.different_tracks_one')
          : context.t('stats.different_tracks', {'count': context.number(tracks)}),
      detail: _detail(context, top),
      change: change(top.key, 1),
      image: ArtworkImage.artist(artist: top.artist, size: 88, hero: heroTag(DetailKind.artist, top.key, 1)),
      onTap: () => openDetail(context, widget.store, DetailTarget.ranked(DetailKind.artist, top)),
    );
  }
}

/// A card of a period, sliding in from the side of the arrow that was tapped, or rising in for another kind of
/// period; only the card moves, never the whole page
class _Appear extends StatefulWidget {
  final int direction;
  final Widget child;

  const _Appear({super.key, required this.direction, required this.child});

  @override
  State<_Appear> createState() => _AppearState();
}

class _AppearState extends State<_Appear> with SingleTickerProviderStateMixin {
  late final _shown = AnimationController(vsync: this, duration: const Duration(milliseconds: 380))..forward();
  late final _curve = CurvedAnimation(parent: _shown, curve: Curves.easeOutCubic);
  late final _slide = Tween(
    begin: widget.direction == 0 ? const Offset(0, 0.06) : Offset(0.2 * widget.direction, 0),
    end: Offset.zero,
  ).animate(_curve);

  @override
  void dispose() {
    _curve.dispose();
    _shown.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => FadeTransition(
    opacity: _curve,
    child: SlideTransition(position: _slide, child: widget.child),
  );
}

/// How many recent plays show at first, and how many more each tap on "Show more" adds
const recentStep = 20;

/// The latest plays of any period, under their day
class _RecentPlays extends StatelessWidget {
  final List<Play> plays;

  /// How many of the latest plays show; [onMore] shows more
  final int shown;
  final VoidCallback onMore;
  final void Function(Play play) onTap;

  const _RecentPlays({required this.plays, required this.shown, required this.onMore, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final muted = Palette.of(context).muted;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final MapEntry(key: day, value: dayPlays) in byDay(plays, limit: shown)) ...[
          Padding(
            padding: const EdgeInsets.only(top: 8, bottom: 4),
            child: Text(
              context.day(day),
              style: TextStyle(color: muted, fontWeight: FontWeight.w600),
            ),
          ),
          for (final play in dayPlays)
            InkWell(
              onTap: () => onTap(play),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  children: [
                    SizedBox(
                      width: 48,
                      child: Text(context.time(play.playedAt), style: TextStyle(color: muted)),
                    ),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(play.name, maxLines: 1, overflow: TextOverflow.ellipsis),
                          Text(
                            play.artist,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(color: muted, fontSize: 13),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
        ],
        if (plays.length > shown)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: OutlinedButton(onPressed: onMore, child: Text(context.t('stats.recent_more'))),
          ),
      ],
    );
  }
}
