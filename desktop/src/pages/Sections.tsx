/** The overview's cards below the charts (api/sections.py): discoveries or forgotten tracks, diversity,
 * genres over time, milestones, genres and the album collage. */

import BarList, { BarRow } from "../components/BarList";
import Card from "../components/Card";
import Picture from "../components/Picture";
import Sigil from "../components/Sigil";
import { Column, useOpenDetail } from "../navigation";
import StackedColumns, { Series, seriesClass, StackedColumn } from "../components/StackedColumns";
import { CardSkeleton } from "../components/Skeleton";

export interface SectionsData {
  discoveries: {
    title: string; summary: string; empty: string; tracks_title: string; artists_title: string;
    tracks: BarRow[]; artists: BarRow[];
  } | null;
  forgotten: { title: string; summary: string; empty: string; tracks: BarRow[] } | null;
  diversity: {
    title: string; top_title: string; verdict: string;
    values: { label: string; value: number; text: string }[]; artists: BarRow[];
  };
  streak: {
    title: string; value: string; unit: string; longest: string;
    hint: string; record: boolean;
    genre: {
      family: string; headline: string; level_up: string | null; level: string | null; say: string | null;
      road: { labels: string[]; share: number } | null; next: string;
    } | null;
    stars: { label: string; column: Column; key: string; title: string; plays: string; image: string; round: boolean }[];
  };
  milestones: {
    title: string; summary: string; empty: string; year_ago_title: string;
    items: { date: string; text: string; kind: string; column: Column | null; key: string | null }[];
    year_ago: { rank: number; key: string; text: string }[];
  };
  collage: {
    title: string; summary: string; empty: string; columns: number; available: boolean;
    albums: { key: string; title: string; artist: string; detail: string; image: string }[];
  };
}

export interface GenresData {
  genres: { title: string; summary: string; empty: string; waiting: number; rows: BarRow[] };
  shift: {
    title: string; summary: string; empty: string;
    legend: { series: Series; text: string }[]; columns: StackedColumn[];
  };
}

export function Discoveries({ data }: { data: SectionsData }) {
  if (data.forgotten) {
    const forgotten = data.forgotten;
    return (
      <Card icon="history" title={forgotten.title} summary={forgotten.summary}>
        <BarList rows={forgotten.tracks} empty={forgotten.empty} column="track_key" />
      </Card>
    );
  }
  const discoveries = data.discoveries!;
  return (
    <Card icon="star" title={discoveries.title} summary={discoveries.summary}>
      {(discoveries.tracks.length > 0 || discoveries.artists.length > 0) && (
        <div className="pair inner">
          <div>
            <h3 className="column-title">{discoveries.tracks_title}</h3>
            <BarList rows={discoveries.tracks} empty={discoveries.empty} column="track_key" />
          </div>
          <div>
            <h3 className="column-title">{discoveries.artists_title}</h3>
            <BarList rows={discoveries.artists} empty={discoveries.empty} round column="artist_key" />
          </div>
        </div>
      )}
    </Card>
  );
}

export function Diversity({ data }: { data: SectionsData["diversity"] }) {
  return (
    <Card icon="layers" title={data.title}>
      {data.values.length > 0 && (
        <div className="figures">
          {data.values.map((value) => (
            <div key={value.label} className="figure">
              <span className="figure-label">{value.label}</span>
              <span className="figure-value">{value.text}</span>
            </div>
          ))}
        </div>
      )}
      {data.verdict && <p className="verdict">{data.verdict}</p>}
      {data.artists.length > 0 && (
        <>
          <h3 className="column-title">{data.top_title}</h3>
          <BarList rows={data.artists} empty="" column="artist_key" />
        </>
      )}
    </Card>
  );
}

export function GenreShift({ data }: { data: GenresData["shift"] | null }) {
  if (!data) return <CardSkeleton />;
  return (
    <Card icon="area" title={data.title} summary={data.summary}>
      {data.legend.length > 0 && (
        <div className="legend">
          {data.legend.map((item) => (
            <span key={item.series} className="legend-item">
              <span className={`swatch ${seriesClass(item.series)}`} />
              {item.text}
            </span>
          ))}
        </div>
      )}
      <StackedColumns columns={data.columns} empty={data.empty} />
    </Card>
  );
}

/** The run as a road between the step behind it, the next one and the one after, with a flame that slides to
 * the day the run is on (the next step is where the card says something more) */
function StreakRoad({ road }: { road: { labels: string[]; share: number } }) {
  // The stops sit evenly, and the flame between the first two as far as the run has come
  const gap = road.labels.length === 3 ? 50 : 100;
  const reached = road.share * gap;
  return (
    <div className="road-line">
      <span className="road-fill" style={{ width: `${reached}%` }} />
      <span className="road-flame" style={{ left: `${reached}%` }}>{"\u{1F525}"}</span>
      {road.labels.map((label, index) => (
        <span key={index} className={`road-stop${index === 0 ? " passed" : index === 1 ? " next" : ""}`}
              style={{ left: `${index * gap}%` }}>
          <span className="road-dot" />
          <span className="road-label">{label}</span>
        </span>
      ))}
    </div>
  );
}

/** The days in a row with a play, the longest run and the road to the next step; a word of its own only on a
 * step or a new record (api/sections.py streak_card) */
export function Streak({ data }: { data: SectionsData["streak"] }) {
  const open = useOpenDetail();
  return (
    <Card icon="calendar" title={data.title} summary={data.longest}>
      <div className="streak">
        <div className="streak-count">
          <span className="streak-value">{data.value}</span>
          <span className="streak-unit">{data.unit}</span>
        </div>
      </div>
      <p className={`streak-hint${data.record ? " record" : ""}`}>{data.hint}</p>
      {data.genre && (
        <div className={`streak-level${data.genre.level_up ? " special" : ""}`}>
          <div className="streak-level-head">
            <span className="streak-sigil"><Sigil family={data.genre.family} size={60} /></span>
            <span className="streak-level-text">
              <strong className="streak-title">{data.genre.headline}</strong>
              {data.genre.level_up && <strong className="streak-special">{data.genre.level_up}</strong>}
              {data.genre.level && <span className="streak-rank">{data.genre.level}</span>}
              {data.genre.say && <span>{data.genre.say}</span>}
            </span>
          </div>
          <div className="streak-road">
            {data.genre.road && <StreakRoad road={data.genre.road} />}
            <p className="muted road-text">{data.genre.next}</p>
          </div>
        </div>
      )}
      {data.stars.length > 0 && (
        <div className="streak-stars">
          {data.stars.map((star) => (
            <button key={star.column} className="streak-star clickable" onClick={() => open?.(star.column, star.key)}>
              <Picture src={star.image} alt={star.title} round={star.round} className="streak-picture" />
              <span className="streak-star-text">
                <span className="muted">{star.label}</span>
                <strong>{star.title}</strong>
              </span>
              <span className="muted">{star.plays}</span>
            </button>
          ))}
        </div>
      )}
    </Card>
  );
}

export function Milestones({ data }: { data: SectionsData["milestones"] }) {
  const open = useOpenDetail();
  return (
    <Card icon="flag" title={data.title} summary={data.summary}>
      <div className={data.year_ago.length ? "milestones split" : "milestones"}>
        <ul className="plain-list">
          {data.items.length === 0 && <li className="empty">{data.empty}</li>}
          {data.items.map((item, index) => (
            <li key={index} className={`plain-row${item.column ? " clickable" : ""}`}
                onClick={item.column && open ? () => open(item.column!, item.key!) : undefined}>
              <span className="plain-left">{item.date}</span>
              <span>{item.text}</span>
            </li>
          ))}
        </ul>
        {data.year_ago.length > 0 && (
          <div>
            <h3 className="column-title">{data.year_ago_title}</h3>
            <ul className="plain-list">
              {data.year_ago.map((item) => (
                <li key={item.key} className="plain-row clickable" onClick={() => open?.("track_key", item.key)}>
                  <span className="plain-left">{item.rank}.</span>
                  <span>{item.text}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Card>
  );
}

export function Genres({ data }: { data: GenresData["genres"] | null }) {
  if (!data) return <CardSkeleton />;
  return (
    <Card icon="tag" title={data.title} summary={data.summary}>
      <BarList rows={data.rows} empty={data.empty} />
    </Card>
  );
}

export function Collage({ data }: { data: SectionsData["collage"] }) {
  const open = useOpenDetail();
  if (!data.available) return null;
  return (
    <Card icon="disc" title={data.title} summary={data.summary}>
      {data.albums.length === 0 ? (
        <p className="empty">{data.empty}</p>
      ) : (
        <div className="collage" style={{ gridTemplateColumns: `repeat(${data.columns}, 1fr)` }}>
          {data.albums.map((album) => (
            <div key={album.key} className="collage-cell clickable" title={`${album.title}\n${album.artist}\n${album.detail}`}
                 onClick={() => open?.("album", album.key)}>
              <Picture src={album.image} alt={album.title} className="collage-picture" />
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
