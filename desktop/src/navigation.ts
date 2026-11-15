/** Opening the page of a track, artist or album from anywhere in the statistics. */

import { createContext, useContext } from "react";

export type Column = "track_key" | "artist_key" | "album";

export type OpenDetail = (column: Column, key: string) => void;

export const OpenDetailContext = createContext<OpenDetail | null>(null);

/** The opener of the page shown around the caller; null outside the statistics */
export const useOpenDetail = () => useContext(OpenDetailContext);
