import { imageUrl } from "../api";
import Change, { RankChange } from "./Change";
import Picture from "./Picture";

export interface HeroData {
  key?: string;
  caption: string;
  title: string;
  subtitle: string;
  detail: string;
  change?: RankChange | null;
  image: string;
  /** A sentence or two about the artist or the album's length, on detail pages */
  about?: string;
}

/** The number one track or artist of the period, or the subject of a detail page, over a blurred copy of
 * its picture. onClick opens its page; onSubtitle the artist's page from the artist line. */
export default function Hero({ data, caption, empty, round, large = false, onClick, onSubtitle }: {
  data: HeroData | null; caption: string; empty: string; round: boolean; large?: boolean;
  onClick?: () => void; onSubtitle?: () => void;
}) {
  if (!data) {
    return (
      <section className="hero">
        <div className="hero-body">
          <div className="hero-text">
            <span className="hero-caption">{caption}</span>
            <p className="empty">{empty}</p>
          </div>
        </div>
      </section>
    );
  }
  return (
    <section className={`hero${onClick ? " clickable" : ""}${large ? " large" : ""}`} onClick={onClick}>
      <div className="hero-backdrop" style={{ backgroundImage: `url("${imageUrl(data.image)}")` }} />
      <div className="hero-body">
        <Picture src={data.image} alt={data.title} round={round} className="hero-picture" />
        <div className="hero-text">
          <span className="hero-caption">{data.caption}</span>
          <span className="hero-title">{data.title}</span>
          {onSubtitle ? (
            <button className="hero-subtitle link" onClick={(event) => {
              event.stopPropagation();
              onSubtitle();
            }}>
              {data.subtitle}
            </button>
          ) : (
            <span className="hero-subtitle">{data.subtitle}</span>
          )}
          <span className="hero-detail">{data.detail}</span>
          {data.about && <span className="hero-about">{data.about}</span>}
          {data.change !== undefined && <Change change={data.change} long />}
        </div>
      </div>
    </section>
  );
}
