/** What the page may ask of the main process: the backend's address and its events. */

import { contextBridge, ipcRenderer, IpcRendererEvent } from "electron";

contextBridge.exposeInMainWorld("tracker", {
  backend: () => ipcRenderer.invoke("backend"),
  onEvent: (listener: (message: unknown) => void) => {
    const handler = (_event: IpcRendererEvent, message: unknown) => listener(message);
    ipcRenderer.on("backend-event", handler);
    return () => ipcRenderer.removeListener("backend-event", handler);
  },
});
