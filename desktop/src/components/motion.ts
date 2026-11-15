import { useEffect, useRef, useState } from "react";

/** How long values take to move to new ones, as the Tk window's charts.Animation and the phone's changeDuration */
export const CHANGE_MS = 450;

const easeOut = (x: number) => 1 - (1 - x) ** 3;

/** The value counting from the one shown before to the new one */
export function useCountUp(target: number): number {
  const [shown, setShown] = useState(target);
  const from = useRef(target);
  useEffect(() => {
    const start = performance.now();
    const origin = from.current;
    let frame = 0;
    const step = (now: number) => {
      const progress = Math.min(1, (now - start) / CHANGE_MS);
      const value = origin + (target - origin) * easeOut(progress);
      from.current = value;
      setShown(value);
      if (progress < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [target]);
  return shown;
}
