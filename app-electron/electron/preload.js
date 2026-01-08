import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("bf", {
  checkVersions: (profilePath) => ipcRenderer.invoke("bf:check", profilePath),
  updateBetterfox: (payload) => ipcRenderer.invoke("bf:update", payload),
  backupProfile: (payload) => ipcRenderer.invoke("bf:backup", payload),
  listProfiles: () => ipcRenderer.invoke("bf:listProfiles"),
  chooseDir: () => ipcRenderer.invoke("bf:chooseDir"),
  openPath: (path) => ipcRenderer.invoke("bf:openPath", path),
  openUrl: (url) => ipcRenderer.invoke("bf:openUrl", url),
  getVersion: () => ipcRenderer.invoke("bf:getVersion"),
});