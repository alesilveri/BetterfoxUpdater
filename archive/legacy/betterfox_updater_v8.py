#!/usr/bin/env python3
# =============================================================================
"""
===============================================================================
Changelog
===============================================================================
v2.4 (2025‑07‑30)
  - UI thread‑safe (queue.Queue), fix scroll bug
  - Session+Retry per HTTP, caching GitHub 5'
  - Version compare con packaging.version
  - Età backup calcolata con datetime.fromtimestamp()
  - Robocopy/fallback, compressione e pulizia backup
  - Molti helper (resource_path, needs_update, extract_version)
  - Logger rotativo, config centralizzata
"""
# =============================================================================

import os
import sys
import re
import json
import time
import threading
import logging
import configparser
import ctypes
import subprocess

from pathlib import Path
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from shutil import rmtree, make_archive, copy2
from queue import Queue, Empty

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from packaging.version import parse as parse_version

import tkinter as tk
from tkinter import filedialog, Toplevel, StringVar, messagebox
from ttkbootstrap import Style, ttk
from ttkbootstrap.constants import *

# -----------------------------------------------------------------------------
# Dark mode detect
# -----------------------------------------------------------------------------
try:
    import darkdetect
    _is_dark = darkdetect.isDark
except ImportError:
    def _is_dark() -> bool:
        if sys.platform.startswith("win"):
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
                )
                v, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                winreg.CloseKey(key)
                return v == 0
            except:
                return False
        return False

# -----------------------------------------------------------------------------
# Paths & resources
# -----------------------------------------------------------------------------
APP = "BetterfoxUpdater"
HOME = Path(os.getenv("LOCALAPPDATA" if sys.platform.startswith("win") else "HOME", "."))
BASE = HOME / APP
BASE.mkdir(parents=True, exist_ok=True)
CFG = BASE / "config.ini"
LOGF = BASE / "error.log"
RES = Path(__file__).parent / "resources"

def resource_path(rel: str) -> Path:
    """Restituisce il Path della risorsa rel_path, dev vs frozen."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent
    p = base / rel
    return p if p.exists() else (base.parent / rel if (base.parent / rel).exists() else p)

# -----------------------------------------------------------------------------
# Config load/save
# -----------------------------------------------------------------------------
cfg = configparser.ConfigParser(interpolation=None)
if CFG.exists():
    cfg.read(CFG, encoding="utf-8")
if "Settings" not in cfg:
    cfg["Settings"] = {"profile_path": "", "theme": "system", "backup_folder": ""}
    with open(CFG, "w", encoding="utf-8") as f:
        cfg.write(f)
def save_cfg():
    with open(CFG, "w", encoding="utf-8") as f:
        cfg.write(f)

# -----------------------------------------------------------------------------
# Logger
# -----------------------------------------------------------------------------
logger = logging.getLogger(APP)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    fh = RotatingFileHandler(LOGF, maxBytes=300_000, backupCount=3, encoding="utf-8")
    fh.setLevel(logging.ERROR)
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(ch)

# -----------------------------------------------------------------------------
# HTTP session + retry
# -----------------------------------------------------------------------------
session = requests.Session()
retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500,502,503,504])
session.mount("https://", HTTPAdapter(max_retries=retries))
UA = {"User-Agent": APP}

# -----------------------------------------------------------------------------
# Repo constants
# -----------------------------------------------------------------------------
OWNER, REPO = "yokoffing", "Betterfox"
RAW_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/user.js"
COMMITS_API = f"https://api.github.com/repos/{OWNER}/{REPO}/commits"
VER_RE = re.compile(r"// Betterfox(?: user\.js)? v?([\d\.]+)", re.I)

# -----------------------------------------------------------------------------
# Version utilities
# -----------------------------------------------------------------------------
def extract_version(txt: str | None) -> str | None:
    if not txt:
        return None
    m = VER_RE.search(txt)
    if m:
        return m.group(1)
    m2 = re.search(r"version[:=]\s*(\d+(?:\.\d+)*)", txt, re.I)
    return m2.group(1) if m2 else None

def get_local_version(profile: Path) -> str | None:
    f = profile / "user.js"
    if not f.exists():
        return None
    try:
        return extract_version(f.read_text("utf-8"))
    except Exception as e:
        logger.error(f"read local version: {e}")
        return None

def get_remote_version() -> tuple[str|None, str]:
    try:
        r = session.get(RAW_URL, headers=UA, timeout=10); r.raise_for_status()
        txt = r.text
        return extract_version(txt), txt
    except Exception as e:
        logger.error(f"fetch remote version: {e}")
        return None, ""

_gh_cache = {"time": None, "val": None}
def get_github_last_update() -> str:
    now = datetime.now()
    if _gh_cache["time"] and now - _gh_cache["time"] < timedelta(minutes=5):
        return _gh_cache["val"]
    try:
        r = session.get(f"{COMMITS_API}?path=user.js&per_page=1", headers=UA, timeout=10)
        r.raise_for_status()
        iso = r.json()[0]["commit"]["committer"]["date"]
        dt = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")
        val = dt.strftime("%Y-%m-%d %H:%M:%S")
        logger.debug(f"Ultimo aggiornamento GitHub: {val}")
        _gh_cache.update(time=now, val=val)
        return val
    except Exception as e:
        logger.error(f"fetch last update: {e}")
    _gh_cache.update(time=now, val="n/d")
    return "n/d"

def needs_update(local: str|None, remote: str|None) -> bool:
    if not remote:
        return False
    if not local:
        return True
    try:
        return parse_version(remote) > parse_version(local)
    except Exception:
        return True

# -----------------------------------------------------------------------------
# Firefox version & profile
# -----------------------------------------------------------------------------
def get_firefox_version(profile: Path | None = None) -> str:
    if profile:
        ci = profile / "compatibility.ini"
        if ci.exists():
            cp = configparser.ConfigParser()
            cp.read(ci)
            for s in ("Application", "App"):
                if s in cp and "Version" in cp[s]:
                    return cp[s]["Version"]
    cmd = ["firefox", "-v"]
    if sys.platform.startswith("win"):
        cmd = ["cmd","/c","for %I in (\"%ProgramFiles%\\Mozilla Firefox\\firefox.exe\") do @echo %~nxi"]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        m = re.search(r"(\d+\.\d+(\.\d+)*)", out)
        return m.group(1) if m else "n/d"
    except Exception as e:
        logger.error(f"firefox version: {e}")
        return "n/d"

def get_default_firefox_profile() -> Path | None:
    base = {
        "win32": Path(os.getenv("APPDATA",""))/"Mozilla"/"Firefox",
        "darwin": Path.home()/"Library"/"Application Support"/"Firefox"
    }.get(sys.platform, Path.home()/".mozilla"/"firefox")
    ini = base / "profiles.ini"
    if not ini.exists():
        logger.warning(f"profiles.ini non trovato: {ini}")
        return None
    cp = configparser.ConfigParser()
    cp.read(ini)
    profiles = []
    for s in cp.sections():
        if s.startswith("Profile"):
            p = cp.get(s, "Path", fallback="")
            rel = cp.get(s, "IsRelative", fallback="1")
            path = (base / p if rel=="1" else Path(p)).resolve()
            profiles.append(path)
    # locked profile
    for p in profiles:
        if any((p/f).exists() for f in ("lock", ".parentlock")):
            return p
    # last used via times.json
    last, lm = None, 0
    for p in profiles:
        tj = p/"times.json"
        if tj.exists():
            try:
                j = json.loads(tj.read_text())
                c = j.get("created",0)
                if c > lm:
                    lm, last = c, p
            except: pass
    return last or (profiles[0] if profiles else None)

# -----------------------------------------------------------------------------
# Theme helpers
# -----------------------------------------------------------------------------
def is_dark_theme() -> bool:
    th = cfg["Settings"].get("theme","system")
    return _is_dark() if th=="system" else th.lower().startswith("dark")

# -----------------------------------------------------------------------------
# Backup & restore
# -----------------------------------------------------------------------------
def full_backup_folder() -> Path | None:
    p = cfg["Settings"].get("backup_folder","")
    return Path(p) if p else None

def copy_tree(src: Path, dst: Path):
    if sys.platform.startswith("win"):
        cmd = ["robocopy", str(src), str(dst), "/E","/COPYALL","/R:1","/W:1"]
        res = subprocess.run(cmd, capture_output=True)
        if res.returncode <= 7:
            return
    if dst.exists():
        rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)
    for it in src.rglob("*"):
        tg = dst/it.relative_to(src)
        if it.is_dir(): tg.mkdir(parents=True, exist_ok=True)
        else: copy2(it, tg)

def compress_backup_folder(p: Path):
    zipf = p.with_suffix(".zip")
    if zipf.exists(): return
    make_archive(str(p), "zip", root_dir=str(p))
    rmtree(p)

def clean_backup_folder():
    bf = full_backup_folder()
    if not bf or not bf.exists(): return
    for it in bf.iterdir():
        age = (datetime.now() - datetime.fromtimestamp(it.stat().st_mtime)).days
        if age >= 60:
            it.unlink(missing_ok=True) if it.is_file() else rmtree(it)
        elif age >= 30 and it.is_dir():
            compress_backup_folder(it)

def close_firefox():
    if sys.platform.startswith("win"):
        subprocess.run(["taskkill","/F","/IM","firefox.exe"], stdout=subprocess.DEVNULL)
    else:
        subprocess.run(["pkill","firefox"], stdout=subprocess.DEVNULL)
    time.sleep(0.3)

def create_full_backup(profile: Path, log_cb) -> bool:
    bf = full_backup_folder()
    if not bf:
        log_cb("⚠️ Nessuna cartella di backup configurata."); return False
    bf.mkdir(parents=True, exist_ok=True)
    close_firefox(); clean_backup_folder()
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dest = bf/f"full_profile_backup_{ts}"
    log_cb(f"📥 Backup in corso → {dest}"); copy_tree(profile, dest)
    log_cb("✅ Backup creato."); return True

# -----------------------------------------------------------------------------
# UI log & progress
# -----------------------------------------------------------------------------
_uiq = Queue()
def ui_log(m: str): _uiq.put(m)
def _append(m: str):
    log_output.config(state="normal")
    tag = "error" if m.startswith("❌") else None
    log_output.insert(tk.END, m + "\n", tag)
    log_output.see(tk.END)
    log_output.config(state="disabled")

def poll_ui():
    try:
        while True:
            _append(_uiq.get_nowait())
    except Empty:
        pass
    root.after(100, poll_ui)

def show_progress(total: int):
    progress_bar.configure(mode="determinate", maximum=total, value=0)
    progress_bar.grid()

def step_progress(n: int):
    progress_bar["value"] += n
    if progress_bar["value"] >= progress_bar["maximum"]:
        progress_bar.grid_remove()

# -----------------------------------------------------------------------------
# Update logic
# -----------------------------------------------------------------------------
def download_userjs(profile: Path, txt: str) -> bool:
    try:
        (profile/"user.js").write_text(txt, "utf-8")
        return True
    except Exception as e:
        ui_log(f"❌ Scrittura user.js: {e}")
        return False

def restart_firefox_ui():
    ui_log("🔄 Riavvio Firefox…"); close_firefox()
    cmd = ["firefox"]; shell = False
    if sys.platform.startswith("win"):
        cmd = ["cmd","/c","start","firefox"]; shell = True
    subprocess.Popen(cmd, shell=shell)
    ui_log("✅ Firefox riavviato.")

def run_update(p: str):
    disable_buttons(); clear_log(); ui_log("🦊 Avvio aggiornamento…")
    threading.Thread(target=_update_thread, args=(Path(p),), daemon=True).start()

def _update_thread(profile: Path):
    if not profile.exists():
        ui_log("❌ Profilo non valido."); enable_buttons(); return

    lv = get_local_version(profile)
    rv, content = get_remote_version()
    ui_log(f"💾 Locale: {lv or 'n/d'}  🌐 Remoto: {rv or 'n/d'}")
    ui_log(f"🕒 GitHub: {get_github_last_update()}")

    if not needs_update(lv, rv):
        ui_log("✅ Già aggiornato."); enable_buttons(); return

    if create_full_backup(profile, ui_log):
        threading.Thread(
            target=lambda: compress_backup_folder(full_backup_folder()/f"full_profile_backup_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"),
            daemon=True
        ).start()

    try:
        r = session.get(RAW_URL, headers=UA, stream=True, timeout=15); r.raise_for_status()
        total = int(r.headers.get("content-length", 0)); show_progress(total)
        buf = bytearray()
        for ch in r.iter_content(8192):
            if ch:
                buf.extend(ch)
                step_progress(len(ch))
        txt = buf.decode("utf-8", errors="replace")
        if download_userjs(profile, txt):
            ui_log(f"🎉 Betterfox v{rv} installato."); restart_firefox_ui()
        else:
            ui_log("❌ Download fallito.")
    except Exception as e:
        ui_log(f"❌ Errore download: {e}")

    enable_buttons()

# -----------------------------------------------------------------------------
# Theme & icon
# -----------------------------------------------------------------------------
def apply_icon_to_window(win: tk.Tk | tk.Toplevel):
    ico = None; png = None
    rd = resource_path("resources")
    if rd.exists():
        for f in rd.iterdir():
            if f.suffix.lower() == ".ico" and ico is None:
                ico = f
            if f.suffix.lower() == ".png" and png is None:
                png = f
    try:
        if ico and sys.platform.startswith("win"):
            win.iconbitmap(str(ico))
        elif png:
            img = tk.PhotoImage(file=str(png)); win.iconphoto(True, img); win.icon_image = img
    except Exception as e:
        logger.error(f"apply_icon: {e}")

def set_theme(t: str):
    actual = t if t!="system" else ("darkly" if _is_dark() else "flatly")
    try: style.theme_use(actual)
    except: ui_log(f"❌ Tema non valido: {t}")
    cfg["Settings"]["theme"] = t; save_cfg(); apply_title_bar(); schedule_refresh_info()

def apply_title_bar():
    if sys.platform.startswith("win"):
        dark = is_dark_theme()
        val = ctypes.c_int(1 if dark else 0)
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                                                    ctypes.byref(val), ctypes.sizeof(val))

# -----------------------------------------------------------------------------
# UI Setup
# -----------------------------------------------------------------------------
root = tk.Tk(); root.withdraw()
saved = cfg["Settings"].get("theme","system")
theme = saved if saved!="system" else ("darkly" if _is_dark() else "flatly")
style = Style(theme=theme)
apply_title_bar(); apply_icon_to_window(root)

# Menu
menubar = tk.Menu(root)
opt = tk.Menu(menubar, tearoff=0)
thm = tk.Menu(opt, tearoff=0)
for t in ("system","flatly","darkly"):
    thm.add_command(label=t.capitalize(), command=lambda t=t: set_theme(t))
opt.add_cascade(label="Tema", menu=thm); opt.add_separator()
opt.add_command(label="Esci", command=root.destroy)
menubar.add_cascade(label="Opzioni", menu=opt)
root.config(menu=menubar)

# Profile frame
frm = ttk.Labelframe(root, text="Profilo Firefox", padding=10)
frm.grid(row=0, column=0, sticky="ew", padx=10, pady=(10,5))
frm.columnconfigure(1, weight=1)
ttk.Label(frm, text="Cartella profilo:").grid(row=0, column=0, sticky="e")
profile_var = StringVar(value=cfg["Settings"].get("profile_path",""))
ent = ttk.Entry(frm, textvariable=profile_var, width=40)
ent.grid(row=0, column=1, sticky="ew", padx=5)
def choose_profile():
    d = filedialog.askdirectory(title="Seleziona profilo Firefox")
    if d:
        profile_var.set(d); cfg["Settings"]["profile_path"]=d; save_cfg(); ui_log("✅ Profilo salvato")
ttk.Button(frm, text="Sfoglia", command=choose_profile).grid(row=0, column=2, padx=5)
ttk.Button(frm, text="Avvia Aggiornamento", command=lambda: run_update(profile_var.get())).grid(
    row=1, column=0, columnspan=3, pady=(10,0)
)

# Log frame
lf = ttk.Frame(root, padding=10)
lf.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
lf.rowconfigure(0, weight=1); lf.columnconfigure(0, weight=1)
log_output = tk.Text(lf, state="disabled", wrap=tk.WORD, height=12, bd=0, highlightthickness=0)
log_output.grid(row=0, column=0, sticky="nsew")
scrollbar = ttk.Scrollbar(lf, command=log_output.yview)
scrollbar.grid(row=0, column=1, sticky="ns")
log_output.configure(font=("Segoe UI",10), yscrollcommand=scrollbar.set)
log_output.tag_config("error", foreground="red")

# Progress bar
progress_bar = ttk.Progressbar(frm, orient="horizontal", mode="determinate")
progress_bar.grid_remove()

def clear_log():
    log_output.config(state="normal"); log_output.delete("1.0", tk.END); log_output.config(state="disabled")
def disable_buttons():
    for w in frm.winfo_children():
        if isinstance(w, ttk.Button): w.config(state="disabled")
def enable_buttons():
    for w in frm.winfo_children():
        if isinstance(w, ttk.Button): w.config(state="normal")

def schedule_refresh_info():
    root.after(1000, show_main_info)
def show_main_info():
    clear_log(); p = Path(profile_var.get())
    if p.exists():
        ui_log(f"🦊 Firefox: {get_firefox_version(p)}")
        lv = get_local_version(p); ui_log(f"💾 Locale: {lv or 'n/d'}")
        rv, _ = get_remote_version(); ui_log(f"🌐 Remoto: {rv or 'n/d'}")
        ui_log(f"🕒 GitHub: {get_github_last_update()}")
    else:
        ui_log("❌ Profilo non valido.")

root.grid_rowconfigure(1, weight=1); root.grid_columnconfigure(0, weight=1)
root.after(100, poll_ui)
root.after(0, lambda: [root.deiconify(), schedule_refresh_info()])
root.mainloop()
