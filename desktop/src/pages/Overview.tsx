import { useCallback, useEffect, useRef, useState } from "react";
import { get } from "../api";
import BarList, { BarRow } from "../components/BarList";
import Card from "../components/Card";
import ColumnChart, { Bucket } from "../components/ColumnChart";
import Hero, { HeroData } from "../components/Hero";
import Icon from "../components/Icon";
import { useCountUp } from "../components/motion";
import { useTexts } from "../i18n";
import { Collage, Discoveries, Diversity, Genres, GenresData, GenreShift, Milestones, SectionsData } from "./Sections";

type Period = "week" | "month" | "year" | "all";
const PERIODS: Period[] = ["week", "month", "year", "all"];
// New plays are recorded while the window is open, so the current period is counted again now and then
const REFRESH_MS = 60_000;

interface Tile {
  name: "plays" | "time" | "tracks" | "artists";
  label: string;
  value: number;
  text: string;
  delta: { text: string; kind: "up" | "down" | "same" } | null;
}

interface OverviewData {
  period: Period;
  offset: number;
  title: string;
  can_previous: boolean;
  can_next: boolean;
  tiles: Tile[];
  track_hero: HeroData | null;
  artist_hero: HeroData | null;
  top_tracks: BarRow[];
  top_artists: BarRow[];
  timeline: { title: string; buckets: Bucket[] };
  hours: { title: string; buckets: Bucket[] };
}

function TileView({ tile }: { tile: Tile }) {
  const { number, duration } = useTexts();
  const shown = useCountUp(tile.value);
  return (
    <section className="tile">
      <span className="tile-label">{tile.label}</span>
      <span className="tile-value">{tile.name === "time" ? duration(shown) : number(shown)}</span>
      <span className={`tile-delta delta-${tile.delta?.kind ?? "none"}`}>{tile.delta?.text ?? " "}</span>
    </section>
  );
}

/** The route's answer for the period; an answer for a period clicked past meanwhile is dropped. */
function usePeriodData<T>(route: string, period: Period, offset: number): [T | null, string | null, () => void] {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const latest = useRef(0);
  const load = useCallback(() => {
    const request = ++latest.current;
    get<T>(route, { period, offset }).then(
      (result) => {
        if (request === latest.current) {
          setData(result);
          setError(null);
        }
      },
      (reason) => request === latest.current && setError(String(reason)),
    );
  }, [route, period, offset]);
  useEffect(load, [load]);
  return [data, error, load];
}

export default function Overview() {
  const { t } = useTexts();
  const [period, setPeriod] = useState<Period>("week");
  const [offset, setOffset] = useState(0);
  const [data, error, loadOverview] = usePeriodData<OverviewData>("/api/overview", period, offset);
  const [sections, , loadSections] = usePeriodData<SectionsData>("/api/sections", period, offset);
  const [genres, , loadGenres] = usePeriodData<GenresData>("/api/genres", period, offset);

  useEffect(() => {
    const loadAll = () => {
      loadOverview();
      loadSections();
      loadGenres();
    };
    // Genres are looked up in the background, and the backend tells when some arrived
    const stop = window.tracker.onEvent((message) => {
      if (message.event === "synced") loadAll();
      else if (message.event === "genres") loadGenres();
    });
    const timer = offset === 0 ? window.setInterval(loadAll, REFRESH_MS) : 0;
    return () => {
      stop();
      window.clearInterval(timer);
    };
  }, [loadOverview, loadSections, loadGenres, offset]);

  const empty = t("stats.empty");
  return (
    <div className="page">
      <header className="toolbar">
        <div className="segmented" role="tablist">
          {PERIODS.map((name) => (
            <button
              key={name}
              role="tab"
              aria-selected={period === name}
              className={period === name ? "selected" : ""}
              onClick={() => {
                setPeriod(name);
                setOffset(0);
              }}
            >
              {t(`stats.period.${name}`)}
            </button>
          ))}
        </div>
        <button className="icon-button" disabled={!data?.can_previous} onClick={() => setOffset(offset + 1)}>
          <Icon name="back" />
        </button>
        <button className="icon-button" disabled={!data?.can_next} onClick={() => setOffset(Math.max(0, offset - 1))}>
          <Icon name="forward" />
        </button>
        <h1 className="period-title">{data?.title}</h1>
      </header>

      {error && <p className="error">{error}</p>}
      {data && (
        <div className="overview">
          <div className="tiles">
            {data.tiles.map((tile) => <TileView key={tile.name} tile={tile} />)}
          </div>
          <div className="pair">
            <Hero data={data.track_hero} caption={t("stats.hero.track")} empty={empty} round={false} />
            <Hero data={data.artist_hero} caption={t("stats.hero.artist")} empty={empty} round />
          </div>
          <div className="pair">
            <Card icon="tracks" title={t("stats.top_tracks")}>
              <BarList rows={data.top_tracks} empty={empty} />
            </Card>
            <Card icon="artists" title={t("stats.top_artists")}>
              <BarList rows={data.top_artists} empty={empty} round />
            </Card>
          </div>
          <div className="pair charts">
            <Card icon="calendar" title={data.timeline.title}>
              <ColumnChart buckets={data.timeline.buckets} empty={empty} />
            </Card>
            <Card icon="clock" title={data.hours.title}>
              <ColumnChart buckets={data.hours.buckets} empty={empty} />
            </Card>
          </div>
          {sections && (
            <>
              <Discoveries data={sections} />
              <div className="pair">
                <Diversity data={sections.diversity} />
                <GenreShift data={genres?.shift ?? null} />
              </div>
              <Milestones data={sections.milestones} />
              <div className="pair">
                <Genres data={genres?.genres ?? null} />
                <Collage data={sections.collage} />
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
