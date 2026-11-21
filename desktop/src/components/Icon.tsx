/** Windows' own icon font (Segoe Fluent Icons), with the code points the Tk window used (ui/theme.py). */

const GLYPHS = {
  back: "", forward: "", close: "",
  tracks: "", artists: "", calendar: "", clock: "",
  star: "", tag: "", history: "", disc: "",
  layers: "", area: "", flag: "", bell: "",
  list: "", account: "", sync: "", device: "", help: "", settings: "",
  music: "", check: "", link: "", add: "", download: "", play: "", pause: "",
} as const;

export type IconName = keyof typeof GLYPHS;

export default function Icon({ name, className = "" }: { name: IconName; className?: string }) {
  return <span className={`icon ${className}`} aria-hidden="true">{GLYPHS[name]}</span>;
}
