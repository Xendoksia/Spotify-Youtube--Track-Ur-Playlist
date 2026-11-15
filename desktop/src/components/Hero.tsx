import Change, { RankChange } from "./Change";
import Picture from "./Picture";
import { imageUrl } from "../api";

export interface HeroData {
  key: string;
  caption: string;
  title: string;
  subtitle: string;
  detail: string;
  change: RankChange | null;
  image: string;
}

/** The number one track or artist of the period, over a blurred copy of its picture. */
export default function Hero({ data, caption, empty, round }: {
  data: HeroData | null; caption: string; empty: string; round: boolean;
}) {
  if (!data) {
    return (
      <section className="hero">
        <div className="hero-body">
          <span className="hero-caption">{caption}</span>
          <p className="empty">{empty}</p>
        </div>
      </section>
    );
  }
  return (
    <section className="hero">
      <div className="hero-backdrop" style={{ backgroundImage: `url("${imageUrl(data.image)}")` }} />
      <div className="hero-body">
        <Picture src={data.image} alt={data.title} round={round} className="hero-picture" />
        <div className="hero-text">
          <span className="hero-caption">{data.caption}</span>
          <span className="hero-title">{data.title}</span>
          <span className="hero-subtitle">{data.subtitle}</span>
          <span className="hero-detail">{data.detail}</span>
          <Change change={data.change} long />
        </div>
      </div>
    </section>
  );
}
