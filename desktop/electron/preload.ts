/** What the page may ask of the main process: the backend's address and its events. */

import { contextBridge, ipcRenderer, IpcRendererEvent } from "electron";

contextBridge.exposeInMainWorld("tracker", {
  backend: () => ipcRenderer.invoke("backend"),
  savePath: (name: string, filter: string) => ipcRenderer.invoke("save-path", name, filter),
  capture: (rect: { x: number; y: number; width: number; height: number }) => ipcRenderer.invoke("capture", rect),
  saveImage: (name: string, filter: string, dataUrl: string) => ipcRenderer.invoke("save-image", name, filter, dataUrl),
  onEvent: (listener: (message: unknown) => void) => {
    const handler = (_event: IpcRendererEvent, message: unknown) => listener(message);
    ipcRenderer.on("backend-event", handler);
    return () => ipcRenderer.removeListener("backend-event", handler);
  },
});
