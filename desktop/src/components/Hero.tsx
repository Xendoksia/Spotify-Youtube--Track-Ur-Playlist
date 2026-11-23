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

/** An artist of a track's artist line, with the key of their page (null for one without a page) */
export interface ArtistLink {
  name: string;
  key: string | null;
}

/** The number one track or artist of the period, or the subject of a detail page, over a blurred copy of
 * its picture. onClick opens its page; given artists, each of them with a page opens it from the artist line. */
export default function Hero({ data, caption, empty, round, large = false, onClick, artists, onArtist }: {
  data: HeroData | null; caption: string; empty: string; round: boolean; large?: boolean;
  onClick?: () => void; artists?: ArtistLink[]; onArtist?: (key: string) => void;
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
          {artists?.length && onArtist ? (
            <span className="hero-subtitle hero-artists">
              {artists.map((artist, index) => (
                <span key={`${artist.name}${index}`}>
                  {index > 0 && ", "}
                  {artist.key ? (
                    <button className="link" onClick={(event) => {
                      event.stopPropagation();
                      onArtist(artist.key!);
                    }}>
                      {artist.name}
                    </button>
                  ) : artist.name}
                </span>
              ))}
            </span>
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
