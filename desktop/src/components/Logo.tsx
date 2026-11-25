/** Songlog's logo, the listening notebook: a green notebook with a bookmark wearing headphones, in the theme's own
 * colors so it suits both themes (playlist_tracker/background.py icon_image draws the same on a dark tile for the
 * app icon). Small sizes leave out the pages and the spine, which would run together. */

export default function Logo({ size }: { size: number }) {
  const detailed = size >= 48;
  return (
    <svg className="logo" width={size} height={size} viewBox="0 0 120 120" aria-hidden="true">
      {detailed ? (
        <>
          <rect x="34" y="55" width="56" height="49" rx="6" fill="var(--text)" />
          <rect x="30" y="50" width="56" height="50" rx="7" fill="var(--chart)" />
          <rect x="30" y="50" width="10" height="50" rx="4" fill="color-mix(in srgb, var(--chart) 62%, black)" />
          <path d="M62 50 V80 L68 74 L74 80 V50 Z" fill="var(--series-3)" />
          <path d="M21 74 V60 A39 39 0 0 1 99 60 V74" fill="none" stroke="var(--text)" strokeWidth="8"
                strokeLinecap="round" />
          <rect x="11" y="64" width="18" height="32" rx="9" fill="var(--text)" />
          <rect x="91" y="64" width="18" height="32" rx="9" fill="var(--text)" />
        </>
      ) : (
        <>
          <rect x="30" y="50" width="60" height="52" rx="8" fill="var(--chart)" />
          <path d="M60 50 V82 L68 74 L76 82 V50 Z" fill="var(--series-3)" />
          <path d="M20 74 V60 A40 40 0 0 1 100 60 V74" fill="none" stroke="var(--text)" strokeWidth="12"
                strokeLinecap="round" />
          <rect x="8" y="62" width="22" height="34" rx="11" fill="var(--text)" />
          <rect x="90" y="62" width="22" height="34" rx="11" fill="var(--text)" />
        </>
      )}
    </svg>
  );
}
