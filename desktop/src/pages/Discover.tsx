/** The Discover section: artists and songs not played yet, picked from what is played (api/recommend.py). The
 * closest artist on top over its blurred photo, the other artists as tiles with their songs, then the songs by
 * new artists and the unplayed songs by artists played. Every song and artist opens its Spotify search. */

import { useCallback, useEffect, useRef, useState } from "react";
import { get, imageUrl } from "../api";
import Card from "../components/Card";
import Icon from "../components/Icon";
import Picture from "../components/Picture";
import { DiscoverSkeleton } from "../components/Skeleton";
import { useTexts } from "../i18n";

interface Track {
  title: string;
  subtitle: string;
  image: string;
  link: string;
}

interface Artist {
  title: string;
  subtitle: string;
  image: string;
  link: string;
  tracks: Track[];
}

interface Song extends Track {
  because: string;
  /** The page of the song's artist, for an artist played */
  artist_key: string | null;
}

interface DiscoverData {
  empty: string;
  loading: boolean;
  artists: Artist[];
  new_songs: Song[];
  known_songs: Song[];
}

function SpotifyLink({ href, label }: { href: string; label: string }) {
  return (
    <a className="icon-button discover-play" href={href} target="_blank" rel="noreferrer" title={label} aria-label={label}>
      <Icon name="play" />
    </a>
  );
}

/** The closest artist, large, with its songs */
function TopPick({ artist }: { artist: Artist }) {
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
          <a className="button accent spotify discover-top-open" href={artist.link} target="_blank" rel="noreferrer">
            <Icon name="play" />{t("discover.open_spotify")}
          </a>
        </div>
        {artist.tracks.length > 0 && (
          <ol className="discover-top-tracks">
            {artist.tracks.map((track) => (
              <li key={track.title}>
                <a href={track.link} target="_blank" rel="noreferrer" title={t("discover.open_spotify")}>
                  <Picture src={track.image} alt={track.title} className="discover-top-cover" />
                  <span className="discover-track-title">{track.title}</span>
                  <Icon name="play" className="discover-top-play" />
                </a>
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}

function ArtistTile({ artist, index }: { artist: Artist; index: number }) {
  const { t } = useTexts();
  return (
    <article className="discover-artist" style={{ animationDelay: `${index * 40}ms` }}>
      <a className="discover-artist-head" href={artist.link} target="_blank" rel="noreferrer"
         title={t("discover.open_spotify")}>
        <Picture src={artist.image} alt={artist.title} round className="discover-artist-photo" />
        <span className="discover-artist-name">{artist.title}</span>
      </a>
      <span className="discover-because" title={artist.subtitle}>{artist.subtitle}</span>
      {artist.tracks.length > 0 && (
        <ol className="discover-tracks">
          {artist.tracks.map((track) => (
            <li key={track.title}>
              <a href={track.link} target="_blank" rel="noreferrer" title={t("discover.open_spotify")}>
                <Icon name="play" />
                <span className="discover-track-title">{track.title}</span>
              </a>
            </li>
          ))}
        </ol>
      )}
    </article>
  );
}

function SongList({ title, summary, songs, openArtist }: {
  title: string; summary: string; songs: Song[]; openArtist: (key: string) => void;
}) {
  const { t } = useTexts();
  return (
    <Card icon="tracks" title={title} summary={summary}>
      {songs.length === 0 && <p className="empty">{t("discover.songs_none")}</p>}
      <ol className="discover-songs">
        {songs.map((song, index) => (
          <li key={`${song.subtitle}|${song.title}`} className="discover-song" style={{ animationDelay: `${index * 30}ms` }}>
            <Picture src={song.image} alt={song.title} className="discover-song-cover" />
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
            </div>
            <SpotifyLink href={song.link} label={t("discover.open_spotify")} />
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
  }, [hidden, load]);
  useEffect(() => window.tracker.onEvent((message) => {
    // What was still being looked up arrived
    if (message.event === "recommend") load();
    if (message.event === "plays" || message.event === "synced") stale.current = true;
  }), [load]);

  const [top, ...rest] = data?.artists ?? [];
  const empty = data && !data.artists.length && !data.new_songs.length && !data.known_songs.length;
  return (
    <div className="page discover" hidden={hidden}>
      <header className="discover-head">
        <div>
          <h1>{t("nav.discover")}</h1>
          <p className="muted">{t("discover.intro")}</p>
        </div>
        {data?.loading && <span className="discover-loading"><span className="discover-pulse" />{t("discover.loading")}</span>}
      </header>
      {!data && !failed && <DiscoverSkeleton />}
      {failed && !data && <p className="empty error">{t("discover.failed")}</p>}
      {empty && <p className="empty">{data.empty}</p>}
      {data && !empty && (
        <div className="overview">
          {top && <TopPick artist={top} />}
          {rest.length > 0 && (
            <Card icon="artists" title={t("discover.artists")} summary={t("discover.artists_summary")}>
              <div className="discover-grid">
                {rest.map((artist, index) => <ArtistTile key={artist.title} artist={artist} index={index} />)}
              </div>
            </Card>
          )}
          <div className="pair">
            <SongList title={t("discover.new_songs")} summary={t("discover.new_songs_summary")}
                      songs={data.new_songs} openArtist={openArtist} />
            <SongList title={t("discover.known_songs")} summary={t("discover.known_songs_summary")}
                      songs={data.known_songs} openArtist={openArtist} />
          </div>
        </div>
      )}
    </div>
  );
}
