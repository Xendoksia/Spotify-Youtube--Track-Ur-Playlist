/** The app's icon: a green circle with three bars (playlist_tracker/background.py icon_image draws the same). */

const BARS = [0.34, 0.52, 0.26];

export default function Logo({ size }: { size: number }) {
  const bar = 12;
  const gap = 7;
  const left = (100 - 3 * bar - 2 * gap) / 2;
  return (
    <svg className="logo" width={size} height={size} viewBox="0 0 100 100" aria-hidden="true">
      <circle cx="50" cy="50" r="50" fill="#1aa34a" />
      {BARS.map((height, index) => (
        <rect key={index} x={left + index * (bar + gap)} y={50 - height * 50} width={bar} height={height * 100}
              rx={bar / 2} fill="white" />
      ))}
    </svg>
  );
}
