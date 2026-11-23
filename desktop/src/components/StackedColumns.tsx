/** The genres over time (api/sections.py genre_shift): each column split into the shares of a few series, which
 * GenreRibbons ranks. */

export type Series = number | "other";

export interface StackedColumn {
  label: string;
  tooltip: string;
  segments: { series: Series; share: number }[];
}

export const seriesClass = (series: Series) => `series-${series}`;
