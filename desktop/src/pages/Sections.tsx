/** The overview's cards below the charts (api/sections.py): discoveries or forgotten tracks, diversity,
 * genres over time, milestones, genres and the album collage. */

import BarList, { BarRow } from "../components/BarList";
import Card from "../components/Card";
import Picture from "../components/Picture";
import StackedColumns, { Series, seriesClass, StackedColumn } from "../components/StackedColumns";

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
  milestones: {
    title: string; summary: string; empty: string; year_ago_title: string;
    items: { date: string; text: string; kind: string; column: string | null; key: string | null }[];
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
        <BarList rows={forgotten.tracks} empty={forgotten.empty} />
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
            <BarList rows={discoveries.tracks} empty={discoveries.empty} />
          </div>
          <div>
            <h3 className="column-title">{discoveries.artists_title}</h3>
            <BarList rows={discoveries.artists} empty={discoveries.empty} round />
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
          <BarList rows={data.artists} empty="" />
        </>
      )}
    </Card>
  );
}

export function GenreShift({ data }: { data: GenresData["shift"] | null }) {
  if (!data) return <section className="card" />;
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

export function Milestones({ data }: { data: SectionsData["milestones"] }) {
  return (
    <Card icon="flag" title={data.title} summary={data.summary}>
      <div className={data.year_ago.length ? "milestones split" : "milestones"}>
        <ul className="plain-list">
          {data.items.length === 0 && <li className="empty">{data.empty}</li>}
          {data.items.map((item, index) => (
            <li key={index} className="plain-row">
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
                <li key={item.key} className="plain-row">
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
  if (!data) return <section className="card" />;
  return (
    <Card icon="tag" title={data.title} summary={data.summary}>
      <BarList rows={data.rows} empty={data.empty} />
    </Card>
  );
}

export function Collage({ data }: { data: SectionsData["collage"] }) {
  if (!data.available) return null;
  return (
    <Card icon="disc" title={data.title} summary={data.summary}>
      {data.albums.length === 0 ? (
        <p className="empty">{data.empty}</p>
      ) : (
        <div className="collage" style={{ gridTemplateColumns: `repeat(${data.columns}, 1fr)` }}>
          {data.albums.map((album) => (
            <div key={album.key} className="collage-cell" title={`${album.title}\n${album.artist}\n${album.detail}`}>
              <Picture src={album.image} alt={album.title} className="collage-picture" />
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
