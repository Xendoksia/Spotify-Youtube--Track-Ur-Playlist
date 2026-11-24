/** Opening an artist, or one of their songs, in the Spotify app through the backend (api/recommend.py), where
 * playing it is recorded, rather than in the browser. */

import type { MouseEvent } from "react";
import { post } from "./api";

/** A click handler for a link whose href stays the Spotify search, for its address on hover */
export function openSpotify(artist: string, title = "") {
  return (event?: MouseEvent) => {
    event?.preventDefault();
    post("/api/recommend/open", { artist, title }).catch(() => {});
  };
}
