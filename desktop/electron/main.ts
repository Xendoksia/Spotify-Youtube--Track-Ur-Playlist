/**
 * The desktop window: starts the Python backend, shows the React interface (src/) and keeps a tray icon,
 * so recording goes on after the window is closed. Quitting is done from the tray menu.
 */

import {
  app, BrowserWindow, dialog, ipcMain, Menu, nativeImage, nativeTheme, Notification, shell, Tray,
} from "electron";
import fs from "node:fs";
import path from "node:path";
import { Backend, BackendEvent, developmentLaunch, installedLaunch } from "./backend";

interface AppInfo {
  language: string;
  theme: "system" | "light" | "dark";
  close_to_tray: boolean;
  strings: Record<string, string>;
}

const DEV = process.argv.includes("--dev");
// Installed, the app keeps its data in a folder of its own (the earlier program's is copied there the first
// time); the window's own files (cache, storage) go in a folder inside it. PLAYLIST_TRACKER_DATA_DIR names another
// folder, for trying a build without touching the real data or the Windows startup entry. The folder keeps the app's
// first name, Playlist Tracker, so renaming it Songlog left everyone's data where it was
const CUSTOM_DATA_DIR = process.env.PLAYLIST_TRACKER_DATA_DIR;
const DATA_DIR = CUSTOM_DATA_DIR ?? path.join(app.getPath("appData"), "Playlist Tracker");
const APP_ID = "com.xendoksia.playlisttracker";
if (app.isPackaged) app.setPath("userData", path.join(DATA_DIR, "window"));
const MINIMIZED = process.argv.includes("--minimized");
// Opens with last month's summary, to look at it on any day (as app.py --summary)
const SUMMARY = process.argv.includes("--summary");
const ICON = path.join(__dirname, "..", "assets", "icon.ico");
// The window's background before the page draws, as the theme's (ui/theme.py "bg")
const BACKGROUND = { light: "#d3d8e0", dark: "#16181d" };
// The page draws the title bar itself in the theme's colors (Windows would paint it in the accent color); only the
// minimize, maximize and close buttons are Windows', on the page's background with the theme's text color.
// The page leaves this much room at the top (styles.css --title-bar)
const TITLE_BAR_HEIGHT = 36;
const SYMBOL = { light: "#1f2328", dark: "#e6e8eb" };

function titleBarOverlay(): Electron.TitleBarOverlayOptions {
  const dark = nativeTheme.shouldUseDarkColors;
  return { color: dark ? BACKGROUND.dark : BACKGROUND.light, symbolColor: dark ? SYMBOL.dark : SYMBOL.light,
           height: TITLE_BAR_HEIGHT };
}

const backend = new Backend();
let window: BrowserWindow | null = null;
let tray: Tray | null = null;
let info: AppInfo | null = null;
let recording = false;
let quitting = false;
let trayHintShown = false;

const t = (key: string) => info?.strings[key] ?? key;

/** How long a story page may take to load its slide before it is captured as it is */
const STORY_WAIT_MS = 10000;

async function storyPicture(id: string, slide: number): Promise<string> {
  // Off screen, so the window is not held to the screen's height and nothing shows
  const story = new BrowserWindow({
    width: 400,
    height: 400,
    show: false,
    frame: false,
    backgroundColor: "#000000",
    webPreferences: { preload: path.join(__dirname, "preload.js"), contextIsolation: true, sandbox: true, offscreen: true },
  });
  try {
    story.setContentSize(1080, 1920);
    const ready = new Promise<void>((resolve) => {
      const listener = (event: Electron.IpcMainEvent) => {
        if (event.sender !== story.webContents) return;
        ipcMain.removeListener("story-ready", listener);
        resolve();
      };
      ipcMain.on("story-ready", listener);
      setTimeout(() => {
        ipcMain.removeListener("story-ready", listener);
        resolve();
      }, STORY_WAIT_MS);
    });
    const search = `story=${encodeURIComponent(id)}&slide=${slide}`;
    if (DEV) await story.loadURL(`http://127.0.0.1:5173?${search}`);
    else await story.loadFile(path.join(__dirname, "..", "dist", "index.html"), { search });
    story.webContents.setZoomFactor(1.5);
    await ready;
    return (await story.webContents.capturePage()).toDataURL();
  } finally {
    story.destroy();
  }
}

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
    titleBarStyle: "hidden",
    titleBarOverlay: titleBarOverlay(),
    // Nor is the window's border in the Windows accent color
    accentColor: false,
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
  // Events that come before the window and the tray are there (a notification about copied data) wait for them
  const early: BackendEvent[] = [];
  let started = false;
  backend.on("event", (message: BackendEvent) => (started ? onBackendEvent(message) : early.push(message)));
  // How Windows starts the app at login, when that is turned on in the settings
  let launch = developmentLaunch(`"${process.execPath}" "${app.getAppPath()}" --minimized`);
  if (app.isPackaged) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
    launch = installedLaunch(DATA_DIR, CUSTOM_DATA_DIR ? "" : `"${process.execPath}" --minimized`);
  }
  const connection = await backend.start(launch);
  backend.on("exit", () => {
    if (!quitting) console.error("The backend stopped");
  });
  info = await backend.request<AppInfo>("/api/app");
  nativeTheme.themeSource = info.theme;
  if (connection.recording) {
    recording = (await backend.request<{ enabled: boolean }>("/api/recording")).enabled;
  }

  // A theme chosen in the settings or Windows switching between light and dark
  nativeTheme.on("updated", () => {
    window?.setTitleBarOverlay(titleBarOverlay());
    window?.setBackgroundColor(nativeTheme.shouldUseDarkColors ? BACKGROUND.dark : BACKGROUND.light);
  });
  ipcMain.handle("backend", () => backend.connection);
  // Where to save a file (the history as CSV): the chosen path, or null when cancelled
  ipcMain.handle("save-path", async (_event, name: string, filter: string) => {
    const result = await dialog.showSaveDialog(window!, {
      defaultPath: name,
      filters: [{ name: filter, extensions: [path.extname(name).slice(1)] }],
    });
    return result.canceled ? null : result.filePath;
  });
  // A summary slide as a story picture (1080 x 1920 PNG): the page lays the slide out alone at 720 x 1280 in a
  // hidden window drawn at one and a half times, says when its pictures are in, and the window is captured
  ipcMain.handle("story", (_event, id: string, slide: number) => storyPicture(id, slide));
  // A picture saved where the person chooses (true) or not saved (false)
  ipcMain.handle("save-image", async (_event, name: string, filter: string, dataUrl: string) => {
    const result = await dialog.showSaveDialog(window!, { defaultPath: name, filters: [{ name: filter, extensions: ["png"] }] });
    if (result.canceled || !result.filePath) return false;
    await fs.promises.writeFile(result.filePath, nativeImage.createFromDataURL(dataUrl).toPNG());
    return true;
  });
  tray = new Tray(ICON);
  tray.setToolTip(t("app.title"));
  tray.on("click", showWindow);
  updateTrayMenu();
  window = createWindow();
  started = true;
  early.forEach(onBackendEvent);
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  // The same as the installer's, so notifications carry the app's name and icon
  app.setAppUserModelId(APP_ID);
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
