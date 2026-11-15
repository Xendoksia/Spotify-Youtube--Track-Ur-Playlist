import { useCallback, useEffect, useRef, useState } from "react";
import { get } from "../api";
import BarList, { BarRow } from "../components/BarList";
import Card from "../components/Card";
import ColumnChart, { Bucket } from "../components/ColumnChart";
import Hero, { HeroData } from "../components/Hero";
import Icon from "../components/Icon";
import Tile, { TileData } from "../components/Tile";
import { useTexts } from "../i18n";
import { Column, OpenDetailContext } from "../navigation";
import Detail, { DetailToolbar, Visit } from "./Detail";
import { Collage, Discoveries, Diversity, Genres, GenresData, GenreShift, Milestones, SectionsData } from "./Sections";

type Period = "week" | "month" | "year" | "all";
const PERIODS: Period[] = ["week", "month", "year", "all"];
// New plays are recorded while the window is open, so the current period is counted again now and then
const REFRESH_MS = 60_000;

interface OverviewData {
  period: Period;
  offset: number;
  title: string;
  can_previous: boolean;
  can_next: boolean;
  tiles: TileData[];
  track_hero: HeroData | null;
  artist_hero: HeroData | null;
  top_tracks: BarRow[];
  top_artists: BarRow[];
  timeline: { title: string; buckets: Bucket[] };
  hours: { title: string; buckets: Bucket[] };
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
  // The detail pages visited since the statistics were left, and the one on display (-1: the statistics)
  const [visits, setVisits] = useState<Visit[]>([]);
  const [index, setIndex] = useState(-1);
  const [detailTitle, setDetailTitle] = useState("");
  const statisticsScroll = useRef(0);

  const scroller = () => document.querySelector(".content");
  const openDetail = useCallback((column: Column, key: string) => {
    if (index < 0) statisticsScroll.current = scroller()?.scrollTop ?? 0;
    // Opening a page drops the pages that were ahead of the current one
    setVisits((before) => [...before.slice(0, index + 1), { column, key }]);
    setIndex(index + 1);
    scroller()?.scrollTo(0, 0);
  }, [index]);
  const closeDetail = () => {
    setVisits([]);
    setIndex(-1);
    requestAnimationFrame(() => scroller()?.scrollTo(0, statisticsScroll.current));
  };
  const step = (direction: number) => {
    // Back from the first page returns to the statistics
    if (index + direction < 0) closeDetail();
    else if (index + direction < visits.length) {
      setIndex(index + direction);
      scroller()?.scrollTo(0, 0);
    }
  };

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
  const visit = index >= 0 ? visits[index] : null;
  return (
    <OpenDetailContext.Provider value={openDetail}>
    {visit && (
      <div className="page">
        <DetailToolbar title={detailTitle} canForward={index < visits.length - 1}
                       onBack={() => step(-1)} onForward={() => step(1)} onClose={closeDetail} />
        <Detail key={`${visit.column}:${visit.key}`} visit={visit} onTitle={setDetailTitle} />
      </div>
    )}
    {/* Kept while a detail page is open, so the statistics come back as they were left */}
    <div className="page" hidden={visit !== null}>
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
            {data.tiles.map((tile) => <Tile key={tile.name} tile={tile} />)}
          </div>
          <div className="pair">
            <Hero data={data.track_hero} caption={t("stats.hero.track")} empty={empty} round={false}
                  onClick={data.track_hero ? () => openDetail("track_key", data.track_hero!.key!) : undefined} />
            <Hero data={data.artist_hero} caption={t("stats.hero.artist")} empty={empty} round
                  onClick={data.artist_hero ? () => openDetail("artist_key", data.artist_hero!.key!) : undefined} />
          </div>
          <div className="pair">
            <Card icon="tracks" title={t("stats.top_tracks")}>
              <BarList rows={data.top_tracks} empty={empty} column="track_key" />
            </Card>
            <Card icon="artists" title={t("stats.top_artists")}>
              <BarList rows={data.top_artists} empty={empty} round column="artist_key" />
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
    </OpenDetailContext.Provider>
  );
}
