import { app, BrowserWindow, ipcMain, dialog, shell, Tray, Menu } from "electron";
import fs from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import https from "https";

const __dirname = dirname(fileURLToPath(import.meta.url));
const isDev = process.env.NODE_ENV === "development";
const USERJS_URL = "https://raw.githubusercontent.com/yokoffing/Betterfox/main/user.js";
const COMMITS_URL = "https://api.github.com/repos/yokoffing/Betterfox/commits?path=user.js&per_page=1";
const APP_ID = "com.betterfox.updater";
const ICON_PATH = join(__dirname, "icon.ico");

function fetchText(url) {
  return new Promise((resolve, reject) => {
    https
      .get(
        url,
        {
          headers: {
            "User-Agent": "Betterfox-Updater",
            Accept: "text/plain,application/json;q=0.9",
          },
        },
        (res) => {
          if (res.statusCode && res.statusCode >= 400) {
            reject(new Error(`HTTP ${res.statusCode}`));
            return;
          }
          let data = "";
          res.on("data", (chunk) => (data += chunk));
          res.on("end", () => resolve(data));
        }
      )
      .on("error", reject);
  });
}

function fetchJson(url) {
  return fetchText(url).then((txt) => JSON.parse(txt));
}

function parseVersion(content) {
  const re = /Betterfox(?: user\.js)? v?([\d.]+)/i;
  const m = content.match(re);
  if (m && m[1]) return `v${m[1]}`;
  const fallback = content.match(/version[:=]\s*(\d+(?:\.\d+)*)/i);
  return fallback ? `v${fallback[1]}` : "n/d";
}

function getLocalVersion(profilePath) {
  try {
    const userjs = fs.readFileSync(join(profilePath, "user.js"), "utf-8");
    return parseVersion(userjs);
  } catch {
    return "n/d";
  }
}

function listFirefoxProfiles() {
  try {
    const appData = process.env.APPDATA || "";
    const iniPath = join(appData, "Mozilla", "Firefox", "profiles.ini");
    if (!fs.existsSync(iniPath)) return [];
    const content = fs.readFileSync(iniPath, "utf-8");
    const lines = content.split(/\r?\n/);
    const profiles = [];
    let current = {};
    for (const line of lines) {
      if (line.startsWith("[Profile") || line.startsWith("[Install")) {
        current = {};
      } else if (line.startsWith("Name=")) {
        current.name = line.replace("Name=", "").trim();
      } else if (line.startsWith("Path=")) {
        const rel = line.replace("Path=", "").trim();
        const abs = join(appData, "Mozilla", "Firefox", rel);
        current.path = abs;
      }
      if (current.name && current.path && !profiles.find((p) => p.path === current.path)) {
        profiles.push(current);
        current = {};
      }
    }
    return profiles;
  } catch {
    return [];
  }
}

async function getRemoteMeta() {
  try {
    const [raw, commits] = await Promise.all([fetchText(USERJS_URL), fetchJson(COMMITS_URL)]);
    const version = parseVersion(raw);
    let commitDate = "n/d";
    if (Array.isArray(commits) && commits[0]?.commit?.committer?.date) {
      commitDate = commits[0].commit.committer.date.replace("T", " ").replace("Z", "");
    }
    return { version, commitDate, content: raw };
  } catch (err) {
    return { version: "n/d", commitDate: "n/d", content: "" };
  }
}

function createWindow() {
  app.setName("Betterfox Updater");
  app.setAppUserModelId(APP_ID);

  const win = new BrowserWindow({
    width: 1080,
    height: 720,
    minWidth: 960,
    minHeight: 640,
    title: "Betterfox Updater",
    backgroundColor: "#0c1116",
    icon: ICON_PATH,
    webPreferences: {
      preload: join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Tray per accesso rapido
  const tray = new Tray(ICON_PATH);
  const menu = Menu.buildFromTemplate([
    { label: "Mostra finestra", click: () => win.show() },
    { type: "separator" },
    { label: "Esci", click: () => app.quit() },
  ]);
  tray.setToolTip("Betterfox Updater");
  tray.setContextMenu(menu);
  tray.on("click", () => win.show());

  if (isDev) {
    win.loadURL("http://localhost:5173/");
  } else {
    win.loadFile(join(__dirname, "..", "dist", "index.html"));
  }
}

ipcMain.handle("bf:check", async (_evt, profilePath) => {
  const meta = await getRemoteMeta();
  const local = profilePath ? getLocalVersion(profilePath) : "n/d";
  const firefox = "n/d";
  return { local, remote: meta.version, github: meta.commitDate, firefox };
});

ipcMain.handle("bf:listProfiles", () => listFirefoxProfiles());

ipcMain.handle("bf:update", async (_evt, payload) => {
  const { profilePath } = payload || {};
  if (!profilePath) {
    return { ok: false, log: ["[err] Profilo non impostato"] };
  }
  try {
    const meta = await getRemoteMeta();
    if (!meta.content) throw new Error("Download non riuscito");
    fs.writeFileSync(join(profilePath, "user.js"), meta.content, "utf-8");
    return {
      ok: true,
      log: [`[ok] Betterfox aggiornato a ${meta.version}`],
      version: getLocalVersion(profilePath),
    };
  } catch (err) {
    return { ok: false, log: [`[err] Update: ${err.message}`] };
  }
});

ipcMain.handle("bf:backup", async (_evt, payload) => {
  const { profilePath, destPath, retentionDays = 60 } = payload || {};
  if (!profilePath || !destPath) {
    return { ok: false, log: ["[err] Profilo o cartella backup mancante"] };
  }
  try {
    if (!fs.existsSync(destPath)) fs.mkdirSync(destPath, { recursive: true });
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const targetDir = join(destPath, `backup-${stamp}`);
    fs.cpSync(profilePath, targetDir, { recursive: true });
    // retention cleanup
    const entries = fs.readdirSync(destPath).filter((f) => f.startsWith("backup-"));
    for (const name of entries) {
      const full = join(destPath, name);
      const stat = fs.statSync(full);
      const ageDays = (Date.now() - stat.mtimeMs) / (1000 * 60 * 60 * 24);
      if (ageDays > retentionDays) {
        fs.rmSync(full, { recursive: true, force: true });
      }
    }
    return { ok: true, log: [`[ok] Backup creato: ${targetDir}`] };
  } catch (err) {
    return { ok: false, log: [`[err] Backup: ${err.message}`] };
  }
});

ipcMain.handle("bf:chooseDir", async () => {
  const res = await dialog.showOpenDialog({ properties: ["openDirectory"] });
  if (res.canceled || res.filePaths.length === 0) return null;
  return res.filePaths[0];
});

ipcMain.handle("bf:openPath", async (_evt, path) => {
  if (!path) return false;
  await shell.openPath(path);
  return true;
});

ipcMain.handle("bf:openUrl", async (_evt, url) => {
  if (!url) return false;
  await shell.openExternal(url);
  return true;
});

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
