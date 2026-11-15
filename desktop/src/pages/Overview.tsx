import { useCallback, useEffect, useRef, useState } from "react";
import { get } from "../api";
import BarList, { BarRow } from "../components/BarList";
import Card from "../components/Card";
import ColumnChart, { Bucket } from "../components/ColumnChart";
import Hero, { HeroData } from "../components/Hero";
import Icon from "../components/Icon";
import Inbox from "../components/Inbox";
import Tile, { TileData } from "../components/Tile";
import { useTexts } from "../i18n";
import { Mood, moodStyle } from "../mood";
import { useOpenDetail } from "../navigation";
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
  /** The number one's color as OKLCH hue and chroma; the page sets the lightness for the theme */
  mood: Mood | null;
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

export default function Overview({ hidden, openSummary, inboxVersion }: {
  hidden: boolean; openSummary: (id: string) => void; inboxVersion: number;
}) {
  const { t } = useTexts();
  const [period, setPeriod] = useState<Period>("week");
  const [offset, setOffset] = useState(0);
  const [data, error, loadOverview] = usePeriodData<OverviewData>("/api/overview", period, offset);
  const [sections, , loadSections] = usePeriodData<SectionsData>("/api/sections", period, offset);
  const [genres, , loadGenres] = usePeriodData<GenresData>("/api/genres", period, offset);
  const openDetail = useOpenDetail()!;

  useEffect(() => {
    const loadAll = () => {
      loadOverview();
      loadSections();
      loadGenres();
    };
    // Genres are looked up in the background, and the backend tells when some arrived
    const stop = window.tracker.onEvent((message) => {
      if (message.event === "synced" || message.event === "plays") loadAll();
      else if (message.event === "genres") loadGenres();
    });
    const timer = offset === 0 ? window.setInterval(loadAll, REFRESH_MS) : 0;
    return () => {
      stop();
      window.clearInterval(timer);
    };
  }, [loadOverview, loadSections, loadGenres, offset]);

  const empty = t("stats.empty");
  const mood = data?.mood;
  return (
    // Kept while a detail page is open, so the statistics come back as they were left
    <div
      className={`page stats-page${mood ? " has-mood" : ""}`}
      style={moodStyle(mood)}
      hidden={hidden}
    >
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
        <span className="spacer" />
        <Inbox openSummary={openSummary} version={inboxVersion} />
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
  );
}
