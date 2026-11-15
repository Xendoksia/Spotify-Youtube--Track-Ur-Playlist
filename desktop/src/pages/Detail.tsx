/** The page of one track, artist or album (api/detail.py), with back / forward between the pages visited
 * and a close button back to the statistics. */

import { useCallback, useEffect, useRef, useState } from "react";
import { get } from "../api";
import BarList, { BarRow } from "../components/BarList";
import Card from "../components/Card";
import ColumnChart, { Bucket } from "../components/ColumnChart";
import Hero, { HeroData } from "../components/Hero";
import Icon from "../components/Icon";
import Picture from "../components/Picture";
import Tile, { TileData } from "../components/Tile";
import { useTexts } from "../i18n";
import { Column, useOpenDetail } from "../navigation";

export interface Visit {
  column: Column;
  key: string;
}

interface DetailData {
  kind: "track" | "artist" | "album";
  title: string;
  hero: HeroData & { subtitle_link: Visit | null };
  tiles: TileData[];
  timeline: { title: string; buckets: Bucket[] };
  tracks?: { title: string; rows: BarRow[]; pictures: boolean };
  progress?: { share: number; text: string };
  hours?: { title: string; buckets: Bucket[] };
  album?: { caption: string; key: string; title: string; image: string; heard: string; open: string } | null;
}

export function DetailToolbar({ title, canForward, onBack, onForward, onClose }: {
  title: string; canForward: boolean; onBack: () => void; onForward: () => void; onClose: () => void;
}) {
  return (
    <header className="toolbar">
      <button className="icon-button" onClick={onBack}><Icon name="back" /></button>
      <button className="icon-button" disabled={!canForward} onClick={onForward}><Icon name="forward" /></button>
      <h1 className="period-title">{title}</h1>
      <span className="spacer" />
      <button className="icon-button" onClick={onClose}><Icon name="close" /></button>
    </header>
  );
}

function AlbumProgress({ progress }: { progress: NonNullable<DetailData["progress"]> }) {
  // Starts empty and fills to the share, like the Tk window's Animation
  const [share, setShare] = useState(0);
  useEffect(() => {
    const frame = requestAnimationFrame(() => setShare(progress.share));
    return () => cancelAnimationFrame(frame);
  }, [progress.share]);
  return (
    <section className="tile progress">
      <span className="progress-text">{progress.text}</span>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${share * 100}%` }} />
      </div>
    </section>
  );
}

export default function Detail({ visit, onTitle }: { visit: Visit; onTitle: (title: string) => void }) {
  const { t } = useTexts();
  const open = useOpenDetail()!;
  const [data, setData] = useState<DetailData | null>(null);
  const [missing, setMissing] = useState(false);
  const latest = useRef(0);

  const load = useCallback(() => {
    const request = ++latest.current;
    get<{ page: DetailData | null }>("/api/detail", { column: visit.column, key: visit.key }).then((result) => {
      if (request !== latest.current) return;
      setData(result.page);
      setMissing(result.page === null);
      onTitle(result.page?.title ?? "");
    }, () => request === latest.current && setMissing(true));
  }, [visit.column, visit.key, onTitle]);

  useEffect(load, [load]);
  // Artist facts and album track lists are looked up in the background; the backend tells when they arrived
  useEffect(() => window.tracker.onEvent((message) => {
    if (message.event === "detail" || message.event === "synced" || message.event === "plays") load();
  }), [load]);

  const empty = t("stats.empty");
  if (missing) return <p className="empty">{empty}</p>;
  if (!data) return null;
  const link = data.hero.subtitle_link;
  const tracks = data.tracks && (
    <Card icon="tracks" title={data.tracks.title}>
      <BarList rows={data.tracks.rows} empty={empty} />
    </Card>
  );
  const timeline = (
    <Card icon="calendar" title={data.timeline.title}>
      <ColumnChart buckets={data.timeline.buckets} empty={empty} />
    </Card>
  );

  return (
    <div className="overview">
      <Hero data={data.hero} caption={data.hero.caption} empty={empty} round={data.kind === "artist"}
            large={data.kind === "album"} onSubtitle={link ? () => open(link.column, link.key) : undefined} />
      <div className="tiles">
        {data.tiles.map((tile) => <Tile key={tile.name} tile={tile} />)}
      </div>
      {data.kind === "album" && (
        <>
          {data.progress && <AlbumProgress progress={data.progress} />}
          {tracks}
          {timeline}
        </>
      )}
      {data.kind === "track" && (
        <>
          <div className="pair track-row">
            {data.album && (
              <section className="card album-card clickable" onClick={() => open("album", data.album!.key)}>
                <span className="hero-caption">{data.album.caption}</span>
                <div className="album-card-body">
                  <Picture src={data.album.image} alt={data.album.title} className="album-card-picture" />
                  <div className="album-card-text">
                    <span className="album-card-title">{data.album.title}</span>
                    <span className="muted">{data.album.heard}</span>
                    <span className="album-card-open">{data.album.open}</span>
                  </div>
                </div>
              </section>
            )}
            {data.hours && (
              <Card icon="clock" title={data.hours.title}>
                <ColumnChart buckets={data.hours.buckets} empty={empty} />
              </Card>
            )}
          </div>
          {timeline}
        </>
      )}
      {data.kind === "artist" && (
        <>
          {timeline}
          {tracks}
        </>
      )}
    </div>
  );
}
