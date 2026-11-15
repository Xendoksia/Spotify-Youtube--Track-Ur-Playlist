/**
 * The desktop window: starts the Python backend, shows the React interface (src/) and keeps a tray icon,
 * so recording goes on after the window is closed. Quitting is done from the tray menu.
 */

import { app, BrowserWindow, dialog, ipcMain, Menu, nativeTheme, Notification, shell, Tray } from "electron";
import fs from "node:fs";
import path from "node:path";
import { Backend, BackendEvent } from "./backend";

interface AppInfo {
  language: string;
  theme: "system" | "light" | "dark";
  close_to_tray: boolean;
  strings: Record<string, string>;
}

const DEV = process.argv.includes("--dev");
const MINIMIZED = process.argv.includes("--minimized");
// Opens with last month's summary, to look at it on any day (as app.py --summary)
const SUMMARY = process.argv.includes("--summary");
const ICON = path.join(__dirname, "..", "assets", "icon.ico");
// The window's background before the page draws, as the theme's (ui/theme.py "bg")
const BACKGROUND = { light: "#d3d8e0", dark: "#16181d" };

const backend = new Backend();
let window: BrowserWindow | null = null;
let tray: Tray | null = null;
let info: AppInfo | null = null;
let recording = false;
let quitting = false;
let trayHintShown = false;

const t = (key: string) => info?.strings[key] ?? key;

function createWindow(): BrowserWindow {
  const created = new BrowserWindow({
    width: 1440,
    height: 940,
    minWidth: 960,
    minHeight: 640,
    show: false,
    title: t("app.title"),
    icon: ICON,
    autoHideMenuBar: true,
    backgroundColor: nativeTheme.shouldUseDarkColors ? BACKGROUND.dark : BACKGROUND.light,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      sandbox: true,
    },
  });
  created.removeMenu();
  created.on("page-title-updated", (event) => event.preventDefault());
  // Links open in the browser, never inside the app
  created.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("https://")) shell.openExternal(url);
    return { action: "deny" };
  });
  created.on("close", (event) => {
    // Closing quits when running in the tray is turned off in the settings
    if (quitting || !tray) return;
    if (info && !info.close_to_tray) {
      quit();
      return;
    }
    // Closing hides the window to the tray, so recording goes on
    event.preventDefault();
    created.hide();
    if (!trayHintShown && Notification.isSupported()) {
      trayHintShown = true;
      new Notification({ title: t("app.title"), body: t("tray.hint"), icon: ICON }).show();
    }
  });
  created.once("ready-to-show", () => {
    if (MINIMIZED) return;
    // Shown without taking the focus while a screenshot is taken
    if (process.env.PLAYLIST_TRACKER_SCREENSHOT) created.showInactive();
    else created.show();
  });
  // For checking the interface: PLAYLIST_TRACKER_SCREENSHOT=file.png saves the page a while after it loads, then quits
  const screenshot = process.env.PLAYLIST_TRACKER_SCREENSHOT;
  if (screenshot) {
    // The window opens under the mouse of whoever uses the computer meanwhile: their clicks must not count
    created.setIgnoreMouseEvents(true);
    created.webContents.once("did-finish-load", () => {
      setTimeout(async () => {
        // PLAYLIST_TRACKER_SCREENSHOT_JS runs in the page first, e.g. to click something
        if (process.env.PLAYLIST_TRACKER_SCREENSHOT_JS) {
          await created.webContents.executeJavaScript(process.env.PLAYLIST_TRACKER_SCREENSHOT_JS);
          await new Promise((resolve) => setTimeout(resolve, Number(process.env.PLAYLIST_TRACKER_SCREENSHOT_WAIT ?? 3000)));
        }
        if (process.env.PLAYLIST_TRACKER_SCREENSHOT_SCROLL) {
          await created.webContents.executeJavaScript(
            `document.querySelector(".content").scrollTop = ${Number(process.env.PLAYLIST_TRACKER_SCREENSHOT_SCROLL)}`);
          await new Promise((resolve) => setTimeout(resolve, 500));
        }
        fs.writeFileSync(screenshot, (await created.webContents.capturePage()).toPNG());
        quit();
      }, Number(process.env.PLAYLIST_TRACKER_SCREENSHOT_DELAY ?? 5000));
    });
  }
  if (DEV) {
    created.loadURL(`http://127.0.0.1:5173${SUMMARY ? "?summary" : ""}`);
  } else {
    created.loadFile(path.join(__dirname, "..", "dist", "index.html"), SUMMARY ? { search: "summary" } : {});
  }
  return created;
}

function showWindow(): void {
  if (!window) return;
  if (window.isMinimized()) window.restore();
  window.show();
  window.focus();
}

function updateTrayMenu(): void {
  if (!tray) return;
  const items: Electron.MenuItemConstructorOptions[] = [{ label: t("tray.open"), click: showWindow }];
  if (backend.connection?.recording) {
    items.push({
      label: t("tray.pause"),
      type: "checkbox",
      checked: !recording,
      click: (item) => setRecording(!item.checked),
    });
  }
  items.push({ type: "separator" }, { label: t("tray.quit"), click: quit });
  tray.setContextMenu(Menu.buildFromTemplate(items));
}

async function setRecording(enabled: boolean): Promise<void> {
  try {
    const result = await backend.request<{ enabled: boolean }>("/api/recording", { enabled });
    recording = result.enabled;
  } catch (error) {
    console.error(error);
  }
  updateTrayMenu();
}

function onBackendEvent(message: BackendEvent): void {
  switch (message.event) {
    case "show":
      showWindow();
      break;
    case "notify":
      if (Notification.isSupported()) {
        // A click shows the window, where a summary that is ready opens by itself
        const notification = new Notification({ title: t("app.title"), body: String(message.message), icon: ICON });
        notification.on("click", showWindow);
        notification.show();
      }
      break;
    case "appearance":
    case "settings":
      // New texts for the tray menu, the theme and whether closing keeps running in the tray
      backend.request<AppInfo>("/api/app").then((fresh) => {
        info = fresh;
        nativeTheme.themeSource = fresh.theme;
        tray?.setToolTip(t("app.title"));
        updateTrayMenu();
      }, console.error);
      break;
    case "recording":
      recording = Boolean(message.enabled);
      updateTrayMenu();
      break;
  }
  window?.webContents.send("backend-event", message);
}

function quit(): void {
  quitting = true;
  app.quit();
}

async function start(): Promise<void> {
  const connection = await backend.start();
  backend.on("event", onBackendEvent);
  backend.on("exit", () => {
    if (!quitting) console.error("The backend stopped");
  });
  info = await backend.request<AppInfo>("/api/app");
  nativeTheme.themeSource = info.theme;
  if (connection.recording) {
    recording = (await backend.request<{ enabled: boolean }>("/api/recording")).enabled;
  }

  ipcMain.handle("backend", () => backend.connection);
  // Where to save a file (the history as CSV): the chosen path, or null when cancelled
  ipcMain.handle("save-path", async (_event, name: string, filter: string) => {
    const result = await dialog.showSaveDialog(window!, {
      defaultPath: name,
      filters: [{ name: filter, extensions: [path.extname(name).slice(1)] }],
    });
    return result.canceled ? null : result.filePath;
  });
  tray = new Tray(ICON);
  tray.setToolTip(t("app.title"));
  tray.on("click", showWindow);
  updateTrayMenu();
  window = createWindow();
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.setAppUserModelId("PlaylistTracker");
  app.on("second-instance", showWindow);
  app.on("before-quit", () => {
    quitting = true;
    backend.stop();
  });
  // The tray keeps the app running with no window open
  app.on("window-all-closed", () => {});
  app.whenReady().then(start).catch((error) => {
    console.error(error);
    app.quit();
  });
}
