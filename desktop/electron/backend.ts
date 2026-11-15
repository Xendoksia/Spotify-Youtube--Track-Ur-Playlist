/**
 * The Python side of the app (playlist_tracker/backend.py): started with the window, it records listening,
 * checks playlists, syncs and serves the window's data on 127.0.0.1. It stops when this process ends,
 * as its stdin closes.
 */

import { ChildProcess, spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { EventEmitter } from "node:events";
import path from "node:path";
import readline from "node:readline";

export interface BackendEvent {
  event: string;
  [key: string]: unknown;
}

export interface Connection {
  base: string;
  token: string;
  /** False when another copy of the app is already recording */
  recording: boolean;
}

// The repository root, where the playlist_tracker package and the databases are
const ROOT = path.resolve(__dirname, "..", "..");

export class Backend extends EventEmitter {
  readonly token = randomBytes(24).toString("hex");
  private process: ChildProcess | null = null;
  connection: Connection | null = null;

  start(): Promise<Connection> {
    const python = process.env.PLAYLIST_TRACKER_PYTHON ?? "python";
    const child = spawn(python, ["-m", "playlist_tracker.backend"], {
      cwd: ROOT,
      env: { ...process.env, PLAYLIST_TRACKER_TOKEN: this.token, PYTHONIOENCODING: "utf-8" },
      windowsHide: true,
      stdio: ["pipe", "pipe", "pipe"],
    });
    this.process = child;
    child.stderr!.on("data", (data: Buffer) => process.stderr.write(data));

    return new Promise((resolve, reject) => {
      child.once("error", reject);
      child.once("exit", (code) => {
        this.process = null;
        reject(new Error(`The backend stopped (${code})`));
        this.emit("exit", code);
      });
      readline.createInterface({ input: child.stdout! }).on("line", (line) => {
        let message: BackendEvent;
        try {
          message = JSON.parse(line);
        } catch {
          return; // a stray print
        }
        if (message.event === "ready") {
          this.connection = {
            base: `http://127.0.0.1:${message.port}`,
            token: this.token,
            recording: Boolean(message.recording),
          };
          resolve(this.connection);
        } else {
          this.emit("event", message);
        }
      });
    });
  }

  async request<T>(route: string, body?: unknown): Promise<T> {
    if (!this.connection) throw new Error("The backend is not running");
    const response = await fetch(this.connection.base + route, {
      method: body === undefined ? "GET" : "POST",
      headers: { "X-Token": this.token, "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) throw new Error(`${route}: ${response.status}`);
    return (await response.json()) as T;
  }

  stop(): void {
    const child = this.process;
    if (!child) return;
    // Closing stdin lets the backend stop its threads and release the recording lock
    child.stdin!.end();
    setTimeout(() => child.exitCode === null && child.kill(), 3000).unref();
  }
}
