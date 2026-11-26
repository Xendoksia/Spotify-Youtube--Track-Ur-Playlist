/** The Discover section: artists and songs not played yet, picked from what is played (api/recommend.py). The
 * closest artist on top over its blurred photo, the other artists as tiles with their songs, then the songs by
 * new artists and the unplayed songs by artists played. Every song and artist opens in the Spotify app, where
 * playing it is recorded, rather than in the browser, and every song's 30 second preview plays in the window. */

import { CSSProperties, useCallback, useEffect, useRef, useState } from "react";
import { get, imageUrl, post } from "../api";
import Card from "../components/Card";
import Icon from "../components/Icon";
import Picture from "../components/Picture";
import { DiscoverSkeleton } from "../components/Skeleton";
import { useTexts } from "../i18n";
import { stopPreview, usePreview } from "../preview";
import { openSpotify } from "../spotify";

interface Track {
  title: string;
  subtitle: string;
  image: string;
  link: string;
}

/** What one of the artists or songs played added to a suggestion, share of the whole */
interface Why {
  name: string;
  share: number;
  text: string;
  rest?: boolean;
}

interface Artist {
  key: string;
  why: Why[];
  title: string;
  subtitle: string;
  image: string;
  link: string;
  tracks: Track[];
}

interface Song extends Track {
  key: string;
  why: Why[];
  because: string;
  /** Shown when Deezer has no cover for the song */
  artist_image: string;
  /** The page of the song's artist, for an artist played */
  artist_key: string | null;
}

interface ReportRow {
  title: string;
  image: string;
  state: "favorite" | "listened" | "untried";
  state_text: string;
  detail: string;
  /** The artist's page, for one played since */
  artist_key: string | null;
}

interface Report {
  title: string;
  summary: string;
  suggested: number;
  listened: number;
  favorites: number;
  rows: ReportRow[];
}

type Fame = "known" | "balanced" | "lesser";
const FAMES: Fame[] = ["known", "balanced", "lesser"];

interface Hidden {
  kind: "artist" | "song";
  key: string;
  name: string;
}

/** Leaves an artist or a song out of the suggestions for good */
type Hide = (hidden: Hidden) => void;

interface DiscoverData {
  empty: string;
  why: string;
  loading: boolean;
  fame: Fame;
  hidden: Hidden[];
  artists: Artist[];
  new_songs: Song[];
  known_songs: Song[];
  report: Report | null;
}


function SpotifyLink({ href, label, artist, title }: { href: string; label: string; artist: string; title: string }) {
  return (
    <a className="icon-button discover-play" href={href} target="_blank" rel="noreferrer" title={label} aria-label={label}
       onClick={openSpotify(artist, title)}>
      <Icon name="link" />
    </a>
  );
}

/** Plays or stops the song's 30 second preview, with a ring filling as it plays */
function PreviewButton({ artist, title, className = "" }: { artist: string; title: string; className?: string }) {
  const { t } = useTexts();
  const { state, progress, toggle } = usePreview(artist, title);
  const label = t(state === "none" ? "discover.preview_none" : state === "idle" ? "discover.preview" : "discover.preview_stop");
  return (
    <button className={`preview-button ${state} ${className}`} title={label} aria-label={label}
            disabled={state === "none"} style={{ "--progress": progress } as CSSProperties}
            onClick={(event) => { event.preventDefault(); event.stopPropagation(); toggle(); }}>
      <Icon name={state === "playing" || state === "loading" ? "pause" : "play"} />
    </button>
  );
}

/** The seeds' shares of a suggestion as one bar, each a step fainter, named on hover */
function WhyBar({ why }: { why: Why[] }) {
  if (!why.length) return null;
  return (
    <span className="why-bar" title={why.map((w) => `${w.name} ${w.text}`).join("\n")} aria-hidden>
      {why.map((w, index) => (
        <span key={w.name} className={w.rest ? "rest" : ""}
              style={{ flexGrow: w.share, opacity: w.rest ? undefined : 1 - index * 0.18 }} />
      ))}
    </span>
  );
}

/** The seeds' shares with their names, for the top pick */
function WhyList({ title, why }: { title: string; why: Why[] }) {
  if (!why.length) return null;
  return (
    <div className="why-list">
      <span className="hero-caption">{title}</span>
      <WhyBar why={why} />
      <ol>
        {why.map((w) => (
          <li key={w.name} className={w.rest ? "muted" : ""}><span>{w.name}</span><span className="muted">{w.text}</span></li>
        ))}
      </ol>
    </div>
  );
}

function HideButton({ hidden, onHide, className = "" }: { hidden: Hidden; onHide: Hide; className?: string }) {
  const { t } = useTexts();
  return (
    <button className={`icon-button discover-hide ${className}`} title={t("discover.hide")} aria-label={t("discover.hide")}
            onClick={(event) => { event.preventDefault(); event.stopPropagation(); onHide(hidden); }}>
      <Icon name="hide" />
    </button>
  );
}

/** The closest artist, large, with its songs */
function TopPick({ artist, onHide, whyTitle }: { artist: Artist; onHide: Hide; whyTitle: string }) {
  const { t } = useTexts();
  return (
    <section className="hero discover-top">
      <div className="hero-backdrop" style={{ backgroundImage: `url("${imageUrl(artist.image)}")` }} />
      <div className="hero-body">
        <Picture src={artist.image} alt={artist.title} round className="hero-picture" />
        <div className="hero-text">
          <span className="hero-caption">{t("discover.top_pick")}</span>
          <span className="hero-title">{artist.title}</span>
          <span className="hero-detail">{artist.subtitle}</span>
          <WhyList title={whyTitle} why={artist.why} />
          <a className="button accent spotify discover-top-open" href={artist.link} target="_blank" rel="noreferrer"
             onClick={openSpotify(artist.title)}>
            <Icon name="play" />{t("discover.open_spotify")}
          </a>
        </div>
        <HideButton hidden={{ kind: "artist", key: artist.key, name: artist.title }} onHide={onHide} className="on-hero" />
        {artist.tracks.length > 0 && (
          <ol className="discover-top-tracks">
            {artist.tracks.map((track) => (
              <li key={track.title}>
                <a href={track.link} target="_blank" rel="noreferrer" title={t("discover.open_spotify")}
                   onClick={openSpotify(track.subtitle, track.title)}>
                  <Picture src={track.image} alt={track.title} className="discover-top-cover" />
                  <span className="discover-track-title">{track.title}</span>
                </a>
                <PreviewButton artist={track.subtitle} title={track.title} />
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}

function ArtistTile({ artist, index, onHide }: { artist: Artist; index: number; onHide: Hide }) {
  const { t } = useTexts();
  return (
    <article className="discover-artist" style={{ animationDelay: `${index * 40}ms` }}>
      <HideButton hidden={{ kind: "artist", key: artist.key, name: artist.title }} onHide={onHide} className="corner" />
      <a className="discover-artist-head" href={artist.link} target="_blank" rel="noreferrer"
         title={t("discover.open_spotify")} onClick={openSpotify(artist.title)}>
        <Picture src={artist.image} alt={artist.title} round className="discover-artist-photo" />
        <span className="discover-artist-name">{artist.title}</span>
      </a>
      <span className="discover-because" title={artist.subtitle}>{artist.subtitle}</span>
      <WhyBar why={artist.why} />
      {artist.tracks.length > 0 && (
        <ol className="discover-tracks">
          {artist.tracks.map((track) => (
            <li key={track.title}>
              <PreviewButton artist={track.subtitle} title={track.title} className="small" />
              <a href={track.link} target="_blank" rel="noreferrer" title={t("discover.open_spotify")}
                 onClick={openSpotify(track.subtitle, track.title)}>
                <span className="discover-track-title">{track.title}</span>
              </a>
            </li>
          ))}
        </ol>
      )}
    </article>
  );
}

function SongList({ title, summary, songs, openArtist, onHide }: {
  title: string; summary: string; songs: Song[]; openArtist: (key: string) => void; onHide: Hide;
}) {
  const { t } = useTexts();
  return (
    <Card icon="tracks" title={title} summary={summary}>
      {songs.length === 0 && <p className="empty">{t("discover.songs_none")}</p>}
      <ol className="discover-songs">
        {songs.map((song, index) => (
          <li key={`${song.subtitle}|${song.title}`} className="discover-song" style={{ animationDelay: `${index * 30}ms` }}>
            <Picture src={song.image} fallback={song.artist_image} alt={song.title} className="discover-song-cover" />
            <div className="discover-song-text">
              <span className="discover-song-title">{song.title}</span>
              {song.artist_key ? (
                <button className="link discover-song-artist" title={t("discover.open_artist")}
                        onClick={() => openArtist(song.artist_key!)}>
                  {song.subtitle}
                </button>
              ) : (
                <span className="discover-song-artist">{song.subtitle}</span>
              )}
              <span className="discover-because" title={song.because}>{song.because}</span>
              <WhyBar why={song.why} />
            </div>
            <div className="discover-song-actions">
              <PreviewButton artist={song.subtitle} title={song.title} />
              <SpotifyLink href={song.link} label={t("discover.open_spotify")} artist={song.subtitle} title={song.title} />
              <HideButton hidden={{ kind: "song", key: song.key, name: `${song.subtitle} · ${song.title}` }} onHide={onHide} />
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}

/** Which of the artists suggested in the last 30 days were played since */
// The report's rows, the played ones first
const REPORT_ROWS = 5;

function DiscoveryReport({ report, openArtist }: { report: Report; openArtist: (key: string) => void }) {
  const { t } = useTexts();
  const rows = report.rows.slice(0, REPORT_ROWS);
  return (
    <Card icon="star" title={report.title}>
      <div className="report-score">
        <span className="report-number">{report.listened}</span>
        <span className="muted">/ {report.suggested}</span>
        <p className="muted">{report.summary}</p>
      </div>
      <div className="report-meter" aria-hidden>
        {report.rows.map((row) => <span key={row.title} className={row.state} />)}
      </div>
      <ol className="report-rows">
        {rows.map((row) => (
          <li key={row.title}>
            <button className="report-row"
                    title={row.artist_key ? t("discover.open_artist") : t("discover.open_spotify")}
                    onClick={(event) => row.artist_key ? openArtist(row.artist_key) : openSpotify(row.title)(event)}>
              <Picture src={row.image} alt={row.title} round className="report-photo" />
              <span className="report-text">
                <span className="report-name">{row.title}</span>
                <span className="muted">{row.detail}</span>
              </span>
              <span className={`report-state ${row.state}`}>{row.state_text}</span>
            </button>
          </li>
        ))}
      </ol>
    </Card>
  );
}

export default function Discover({ hidden, openArtist }: { hidden: boolean; openArtist: (key: string) => void }) {
  const { t } = useTexts();
  const [data, setData] = useState<DiscoverData | null>(null);
  const [failed, setFailed] = useState(false);
  // New plays change the suggestions: asked again when the section is shown next, not while it is read
  const stale = useRef(true);

  const load = useCallback(() => {
    stale.current = false;
    get<DiscoverData>("/api/recommend").then((found) => {
      setData(found);
      setFailed(false);
    }, () => setFailed(true));
  }, []);
  useEffect(() => {
    if (!hidden && stale.current) load();
    // A preview stops when the section is left
    if (hidden) stopPreview();
  }, [hidden, load]);
  useEffect(() => window.tracker.onEvent((message) => {
    // What was still being looked up arrived
    if (message.event === "recommend") load();
    if (message.event === "plays" || message.event === "synced") stale.current = true;
  }), [load]);

  // The suggestion just hidden, to take back for a while
  const [note, setNote] = useState<Hidden | null>(null);
  useEffect(() => {
    if (!note) return;
    const timer = window.setTimeout(() => setNote(null), 8000);
    return () => window.clearTimeout(timer);
  }, [note]);
  const hide: Hide = (hidden) => {
    setNote(hidden);
    post("/api/recommend/hide", hidden).then(load, load);
  };
  const show = (hidden: Hidden) => {
    setNote(null);
    post("/api/recommend/show", hidden).then(load, load);
  };
  const chooseFame = (fame: Fame) => {
    setData((now) => now && { ...now, fame });
    post("/api/recommend/fame", { fame }).then(load, load);
  };

  const [top, ...rest] = data?.artists ?? [];
  const empty = data && !data.artists.length && !data.new_songs.length && !data.known_songs.length;
  return (
    <div className="page discover" hidden={hidden}>
      <header className="discover-head">
        <div>
          <h1>{t("discover.heading")}</h1>
          <p className="muted">{t("discover.intro")}</p>
        </div>
        <div className="discover-head-side">
          {data?.loading && <span className="discover-loading"><span className="discover-pulse" />{t("discover.loading")}</span>}
          {data && (
            <div className="segmented discover-fame" role="radiogroup" aria-label={t("discover.fame")} title={t("discover.fame")}>
              {FAMES.map((fame) => (
                <button key={fame} role="radio" aria-checked={data.fame === fame}
                        className={data.fame === fame ? "selected" : ""} onClick={() => chooseFame(fame)}>
                  {t(`discover.fame.${fame}`)}
                </button>
              ))}
            </div>
          )}
        </div>
      </header>
      {note && (
        <div className="discover-note" role="status">
          <Icon name="hide" />
          <span>{t("discover.hidden_note", { name: note.name })}</span>
          <button className="button" onClick={() => show(note)}>{t("discover.undo")}</button>
        </div>
      )}
      {!data && !failed && <DiscoverSkeleton />}
      {failed && !data && <p className="empty error">{t("discover.failed")}</p>}
      {empty && <p className="empty">{data.empty}</p>}
      {data && !empty && (
        <div className="overview">
          {top && <TopPick artist={top} onHide={hide} whyTitle={data.why} />}
          {rest.length > 0 && (
            <Card icon="artists" title={t("discover.artists")} summary={t("discover.artists_summary")}>
              <div className="discover-grid">
                {rest.map((artist, index) => <ArtistTile key={artist.title} artist={artist} index={index} onHide={hide} />)}
              </div>
            </Card>
          )}
          <div className="pair">
            <SongList title={t("discover.new_songs")} summary={t("discover.new_songs_summary")}
                      songs={data.new_songs} openArtist={openArtist} onHide={hide} />
            <SongList title={t("discover.known_songs")} summary={t("discover.known_songs_summary")}
                      songs={data.known_songs} openArtist={openArtist} onHide={hide} />
          </div>
          {data.report && <DiscoveryReport report={data.report} openArtist={openArtist} />}
          {data.hidden.length > 0 && (
            <Card icon="hide" title={t("discover.hidden_title")} summary={t("discover.hidden_summary")}>
              <ul className="discover-hidden">
                {data.hidden.map((hidden) => (
                  <li key={`${hidden.kind}|${hidden.key}`}>
                    <button className="discover-hidden-chip" onClick={() => show(hidden)}>
                      <Icon name={hidden.kind === "artist" ? "artists" : "music"} />{hidden.name}
                    </button>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
