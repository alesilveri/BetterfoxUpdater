import configparser
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, Callable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from packaging.version import parse as parse_version


OWNER = "yokoffing"
REPO = "Betterfox"
RAW_URL = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main/user.js"
COMMITS_API = f"https://api.github.com/repos/{OWNER}/{REPO}/commits"
VERSION_RE = re.compile(r"// Betterfox(?: user\.js)? v?([\d\.]+)", re.I)


@dataclass
class AppPaths:
    base: Path
    config: Path
    log_file: Path
    resources: Path


class Settings:
    DEFAULTS = {
        "Settings": {
            "profile_path": "",
            "backup_folder": "",
            "theme": "system",
            "auto_restart": "yes",
            "auto_backup": "yes",
            "compress_backup": "yes",
            "retention_days": "60",
        },
        "Network": {
            "proxy": "",
            "timeout": "12",
            "retries": "3",
        },
        "UI": {
            "theme": "system",
        },
        "AppUpdate": {
            "version_url": "",
            "release_page": "",
        },
    }

    def __init__(self, paths: AppPaths):
        self.paths = paths
        self.cfg = configparser.ConfigParser(interpolation=None)
        tmpl = Path(__file__).resolve().parent.parent / "resources" / "config_template.ini"
        for candidate in (tmpl, paths.config):
            if candidate.exists():
                self.cfg.read(candidate, encoding="utf-8")
        for section, defaults in self.DEFAULTS.items():
            if section not in self.cfg:
                self.cfg[section] = {}
            for key, value in defaults.items():
                self.cfg[section].setdefault(key, value)
        if not self.cfg["Settings"].get("backup_folder"):
            self.cfg["Settings"]["backup_folder"] = str(paths.base / "backups")
        self.save()

    def save(self):
        with open(self.paths.config, "w", encoding="utf-8") as f:
            self.cfg.write(f)

    def get(self, section: str, key: Optional[str] = None, default: str = "") -> str:
        """Compat: get('theme') -> Settings, get('Network','timeout'). Ritorna default se vuoto."""
        if key is None:
            val = self.cfg["Settings"].get(section, default)
        else:
            val = self.cfg.get(section, key, fallback=default)
        if val is None or str(val).strip() == "":
            return default
        return val

    def set(self, section_or_key: str, key: Optional[str] = None, value: Optional[str] = None):
        """Compatibile con set('theme', 'dark') o set('Network', 'timeout', '15')."""
        if value is None:
            target_section = "Settings"
            target_key = section_or_key
            val = key or ""
        else:
            target_section = section_or_key
            target_key = key or section_or_key
            val = value
        if target_section not in self.cfg:
            self.cfg[target_section] = {}
        self.cfg[target_section][target_key] = val
        self.save()


class BetterfoxService:
    def __init__(self, paths: AppPaths, logger: logging.Logger, settings: Settings | None = None):
        self.paths = paths
        self.logger = logger
        self.cache = {"time": None, "last": "n/d"}
        self.timeout = 12
        self.retries = 3
        self.proxy: dict[str, str] | None = None
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "BetterfoxUpdater"})
        net_section = settings.cfg["Network"] if settings else None
        if net_section:
            try:
                self.timeout = int(net_section.get("timeout", "12") or "12")
            except Exception:
                self.timeout = 12
            try:
                self.retries = int(net_section.get("retries", "3") or "3")
            except Exception:
                self.retries = 3
            proxy = net_section.get("proxy", "").strip()
            if proxy:
                self.proxy = {"http": proxy, "https": proxy}
        self._apply_network()

    def _apply_network(self):
        retries = Retry(total=self.retries, backoff_factor=0.6, status_forcelist=[500, 502, 503, 504], raise_on_status=False)
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.proxies = {}
        if self.proxy:
            self.session.proxies.update(self.proxy)

    def update_network(self, proxy: str, timeout: int, retries: int):
        self.timeout = timeout
        self.retries = retries
        self.proxy = {"http": proxy, "https": proxy} if proxy else None
        self._apply_network()

    # Versioning
    def extract_version(self, txt: str) -> Optional[str]:
        m = VERSION_RE.search(txt)
        if m:
            return m.group(1)
        fallback = re.search(r"version[:=]\s*(\d+(?:\.\d+)*)", txt, re.I)
        return fallback.group(1) if fallback else None

    def get_remote(self) -> tuple[Optional[str], str]:
        try:
            r = self.session.get(RAW_URL, timeout=self.timeout)
            r.raise_for_status()
            txt = r.text
            return self.extract_version(txt), txt
        except Exception as exc:
            self.logger.error("remote fetch: %s", exc)
            return None, ""

    def fetch_userjs_with_progress(self, progress_cb: Callable[[int, int], None]) -> tuple[Optional[str], str]:
        """Scarica user.js con callback di avanzamento (chunk)."""
        try:
            r = self.session.get(RAW_URL, stream=True, timeout=self.timeout)
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            buf = bytearray()
            for chunk in r.iter_content(8192):
                if not chunk:
                    continue
                buf.extend(chunk)
                progress_cb(len(chunk), total)
            txt = buf.decode("utf-8", errors="replace")
            return self.extract_version(txt), txt
        except Exception as exc:
            self.logger.error("download user.js: %s", exc)
            return None, ""

    def get_last_commit(self) -> str:
        now = datetime.now()
        if self.cache["time"] and now - self.cache["time"] < timedelta(minutes=5):
            return self.cache["last"]
        try:
            r = self.session.get(f"{COMMITS_API}?path=user.js&per_page=1", timeout=8)
            r.raise_for_status()
            iso = r.json()[0]["commit"]["committer"]["date"]
            dt = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")
            val = dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as exc:
            self.logger.error("last commit: %s", exc)
            val = "n/d"
        self.cache.update(time=now, last=val)
        return val

    def get_local_version(self, profile: Path) -> Optional[str]:
        f = profile / "user.js"
        if not f.exists():
            return None
        try:
            return self.extract_version(f.read_text("utf-8"))
        except Exception as exc:
            self.logger.error("local version: %s", exc)
            return None

    def needs_update(self, local: Optional[str], remote: Optional[str]) -> bool:
        if not remote:
            return False
        if not local:
            return True
        try:
            return parse_version(remote) > parse_version(local)
        except Exception:
            return True

    # Profile discovery
    def profiles_base(self) -> Path:
        if sys.platform.startswith("win"):
            return Path(os.getenv("APPDATA", "")) / "Mozilla" / "Firefox"
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "Firefox"
        return Path.home() / ".mozilla" / "firefox"

    def discover_profiles(self) -> list[Path]:
        ini = self.profiles_base() / "profiles.ini"
        if not ini.exists():
            return []
        cp = configparser.ConfigParser()
        cp.read(ini)
        found: list[Path] = []
        base = self.profiles_base()
        for s in cp.sections():
            if not s.startswith("Profile"):
                continue
            path = cp.get(s, "Path", fallback="")
            rel = cp.get(s, "IsRelative", fallback="1") == "1"
            target = (base / path) if rel else Path(path)
            target = target.resolve()
            if target.exists():
                found.append(target)
        found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return found

    def get_firefox_version(self, profile: Optional[Path] = None) -> str:
        if profile:
            cmp_ini = profile / "compatibility.ini"
            if cmp_ini.exists():
                cp = configparser.ConfigParser()
                cp.read(cmp_ini)
                for sec in ("Application", "App"):
                    if sec in cp and "Version" in cp[sec]:
                        return cp[sec]["Version"]
        cmd = ["firefox", "-v"]
        if sys.platform.startswith("win"):
            cmd = ["cmd", "/c", "for %I in (\"%ProgramFiles%\\Mozilla Firefox\\firefox.exe\") do @echo %~nxi"]
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
            m = re.search(r"(\d+(\.\d+)+)", out)
            return m.group(1) if m else "n/d"
        except Exception as exc:
            self.logger.error("fx version: %s", exc)
            return "n/d"

    # Backup
    def close_firefox(self):
        if sys.platform.startswith("win"):
            subprocess.run(["taskkill", "/F", "/IM", "firefox.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["pkill", "firefox"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def backup_profile(self, profile: Path, dest: Path, compress: bool, retention_days: int, log: Callable[[str], None]):
        dest.mkdir(parents=True, exist_ok=True)
        size = self._profile_size(profile)
        free_bytes = self._free_bytes(dest)
        if free_bytes < size * 1.2:
            log(f"[warn] Spazio libero limitato ({free_bytes//(1024*1024)} MB) vs profilo ({size//(1024*1024)} MB)")
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        target = dest / f"profile_backup_{ts}"
        log(f"[backup] In corso -> {target}")
        self._copy_tree(profile, target)
        if compress:
            import shutil
            zip_path = target.with_suffix(".zip")
            shutil.make_archive(str(target), "zip", root_dir=str(target))
            shutil.rmtree(target)
            target = zip_path
            log(f"[backup] Compresso -> {zip_path.name}")
        self._cleanup(dest, retention_days)
        log("[ok] Backup completato")
        return target

    def _copy_tree(self, src: Path, dst: Path):
        if sys.platform.startswith("win"):
            cmd = ["robocopy", str(src), str(dst), "/E", "/COPYALL", "/R:1", "/W:1"]
            res = subprocess.run(cmd, capture_output=True)
            if res.returncode <= 7:
                return
        import shutil
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir(parents=True, exist_ok=True)
        for item in src.rglob("*"):
            target = dst / item.relative_to(src)
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)

    def _cleanup(self, backup_dir: Path, retention_days: int):
        now = datetime.now()
        for item in backup_dir.iterdir():
            age = (now - datetime.fromtimestamp(item.stat().st_mtime)).days
            if age > retention_days:
                if item.is_dir():
                    import shutil
                    shutil.rmtree(item)
                else:
                    item.unlink(missing_ok=True)

    def _profile_size(self, profile: Path) -> int:
        total = 0
        for p in profile.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    continue
        return total

    def _free_bytes(self, path: Path) -> int:
        import shutil
        usage = shutil.disk_usage(path)
        return usage.free

    def launch_firefox(self):
        cmd = ["firefox"]
        shell = False
        if sys.platform.startswith("win"):
            cmd = ["cmd", "/c", "start", "firefox"]
            shell = True
        subprocess.Popen(cmd, shell=shell, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
