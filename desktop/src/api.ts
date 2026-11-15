/** The Python backend's API (playlist_tracker/api/server.py), reached through the address preload.ts gives. */

export interface Connection {
  base: string;
  token: string;
  recording: boolean;
}

export interface BackendEvent {
  event: string;
  [key: string]: unknown;
}

declare global {
  interface Window {
    tracker: {
      backend: () => Promise<Connection>;
      onEvent: (listener: (message: BackendEvent) => void) => () => void;
    };
  }
}

let connection: Connection | null = null;

export async function connect(): Promise<Connection> {
  connection ??= await window.tracker.backend();
  return connection;
}

export async function get<T>(route: string, params: Record<string, string | number> = {}): Promise<T> {
  const { base, token } = await connect();
  const query = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)]));
  const response = await fetch(`${base}${route}${query.size ? `?${query}` : ""}`, { headers: { "X-Token": token } });
  if (!response.ok) throw new Error(`${route}: ${response.status}`);
  return (await response.json()) as T;
}

/** The address of an image route such as /api/cover?..., with the token an <img> cannot send as a header */
export function imageUrl(route: string): string {
  if (!connection) return "";
  return `${connection.base}${route}${route.includes("?") ? "&" : "?"}token=${connection.token}`;
}
