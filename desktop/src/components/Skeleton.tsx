/** Grey shapes in the layout of a page that is still being loaded, with a light sweeping over them, so the page
 * does not stand empty and then jump into place. */

/** A grey bar or block; a width as a share of the line, a height in pixels */
export function Bone({ width = "100%", height = 12, round = false }: {
  width?: string; height?: number; round?: boolean;
}) {
  return <span className={`bone${round ? " round" : ""}`} style={{ width, height }} />;
}

/** A card with a title and a few lines of different lengths */
export function CardSkeleton({ lines = 5, className = "" }: { lines?: number; className?: string }) {
  return (
    <section className={`card skeleton-card ${className}`} aria-hidden>
      <Bone width="38%" height={14} />
      {Array.from({ length: lines }, (_, index) => (
        <div key={index} className="skeleton-row">
          <Bone width="32px" height={32} />
          <div className="skeleton-text">
            <Bone width={`${78 - ((index * 17) % 40)}%`} />
            <Bone width={`${46 - ((index * 11) % 24)}%`} height={10} />
          </div>
        </div>
      ))}
    </section>
  );
}

function TilesSkeleton() {
  return (
    <div className="tiles" aria-hidden>
      {[0, 1, 2, 3].map((index) => (
        <div key={index} className="tile skeleton-tile">
          <Bone width="50%" height={10} />
          <Bone width="40%" height={26} />
        </div>
      ))}
    </div>
  );
}

function HeroSkeleton({ round = false, large = false }: { round?: boolean; large?: boolean }) {
  const size = large ? 120 : 96;
  return (
    <div className={`hero skeleton-hero${large ? " large" : ""}`} aria-hidden>
      <Bone width={`${size}px`} height={size} round={round} />
      <div className="skeleton-text">
        <Bone width="30%" height={10} />
        <Bone width="62%" height={large ? 30 : 20} />
        <Bone width="40%" />
      </div>
    </div>
  );
}

/** The statistics before the first answer: tiles, the two number ones and the two top lists */
export function OverviewSkeleton() {
  return (
    <div className="overview skeleton">
      <TilesSkeleton />
      <div className="pair">
        <HeroSkeleton />
        <HeroSkeleton round />
      </div>
      <div className="pair">
        <CardSkeleton />
        <CardSkeleton />
      </div>
    </div>
  );
}

/** A track, artist or album page before its answer */
export function DetailSkeleton() {
  return (
    <div className="overview skeleton">
      <HeroSkeleton large />
      <TilesSkeleton />
      <CardSkeleton lines={6} />
    </div>
  );
}

/** Days of plays before the list arrives */
export function ListSkeleton({ days = 2, rows = 5 }: { days?: number; rows?: number }) {
  return (
    <div className="skeleton skeleton-list" aria-hidden>
      {Array.from({ length: days }, (_, day) => (
        <CardSkeleton key={day} lines={rows} className="skeleton-day" />
      ))}
    </div>
  );
}

/** The Discover section before its answer: the closest artist, a row of artist tiles and the two song lists */
export function DiscoverSkeleton() {
  return (
    <div className="overview skeleton">
      <HeroSkeleton round large />
      <section className="card skeleton-card" aria-hidden>
        <Bone width="24%" height={14} />
        <div className="discover-grid">
          {[0, 1, 2, 3, 4].map((index) => (
            <div key={index} className="discover-artist skeleton-artist">
              <Bone width="88px" height={88} round />
              <Bone width="60%" />
              <Bone width="80%" height={10} />
            </div>
          ))}
        </div>
      </section>
      <div className="pair">
        <CardSkeleton lines={6} />
        <CardSkeleton lines={6} />
      </div>
    </div>
  );
}
