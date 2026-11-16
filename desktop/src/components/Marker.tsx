/** The highlight of the selected item in the sidebar or a row of tabs, sliding to a newly selected item instead
 * of jumping there. Only its transform moves, on the graphics card: moving the pages themselves dropped frames
 * on the laptop's graphics, so the change of section shows here and the page comes at once. */

import { useLayoutEffect, useRef } from "react";

/** Put inside the row; it follows the row's child with the class "selected" (`watch` changes when that does).
 * `underline` stretches a line to the item's width, otherwise the marker takes the item's size. */
export default function Marker({ watch, underline = false }: { watch: unknown; underline?: boolean }) {
  const marker = useRef<HTMLSpanElement>(null);

  useLayoutEffect(() => {
    const element = marker.current;
    const row = element?.parentElement;
    if (!element || !row) return;
    // Slides to a newly selected item; the first place, and a new one after a resize, are taken at once
    const place = (slide: boolean) => {
      const target = row.querySelector<HTMLElement>(":scope > .selected");
      // Hidden, or nothing selected: placed when there is something to point at
      if (!target || !target.offsetWidth) {
        element.classList.remove("shown");
        return;
      }
      const jump = !slide || !element.classList.contains("shown");
      if (jump) element.classList.remove("sliding");
      const { offsetLeft: x, offsetTop: y, offsetWidth: width, offsetHeight: height } = target;
      if (underline) {
        element.style.transform = `translate(${x}px, ${y + height - 2}px) scaleX(${width / 100})`;
      } else {
        element.style.width = `${width}px`;
        element.style.height = `${height}px`;
        element.style.transform = `translate(${x}px, ${y}px)`;
      }
      element.classList.add("shown");
      if (jump) {
        // Takes the place before the transition is back
        element.getBoundingClientRect();
        element.classList.add("sliding");
      }
    };
    place(true);
    // The row resized or was shown again
    const observer = new ResizeObserver(() => place(false));
    observer.observe(row);
    return () => observer.disconnect();
  }, [watch, underline]);

  return <span ref={marker} className={`marker${underline ? " underline" : ""}`} aria-hidden />;
}
