"""
===============================================================================
Changelog
===============================================================================
v1.0 (2024-01-15)
  - Prima implementazione dell'updater di Betterfox con funzioni basilari
    (individuazione profilo Firefox, download user.js, backup base).

v2.0 (2025-01-10)
  - Interfaccia grafica più compatta
  - Barra di avanzamento durante l'aggiornamento
  - Layout più moderno per la selezione del profilo Firefox
  - Selezione cartella backup semplificata
  - Miglioramenti generali di commenti e ottimizzazioni di codice

v2.1 (2025-01-15)
  - Ottimizzazioni di avvio per maggiore fluidità dell’interfaccia
  - Riduzione di alcune pause superflue (time.sleep)
  - Creazione offline dell’interfaccia e successiva deiconifica

v2.2 (2025-01-20)
  - Gestione dei backup più avanzata:
    * Rimozione dopo 60 giorni
    * Compressione (zip) tra 30 e 60 giorni
  - Finestra di selezione cartella backup semplificata:
    * L’utente sceglie la cartella base
    * Creazione automatica (o personalizzabile) di una sottocartella “BetterfoxBackups”
    * Al suo interno i backup “full_profile_backup_...” con timestamp
"""

import os
import sys
import logging
import requests
from pathlib import Path
from shutil import copy2, rmtree, make_archive
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import filedialog, Toplevel, StringVar
import re
import platform
import subprocess
import configparser
import time
import threading
import ctypes
import json

# Prova a importare darkdetect; se non presente, fallback su Windows
try:
    import darkdetect
except ModuleNotFoundError:
    class DarkDetectFallback:
        @staticmethod
        def isDark():
            if platform.system() == "Windows":
                try:
                    import winreg
                    key = winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
                    )
                    value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                    winreg.CloseKey(key)
                    return value == 0  # 0 = Dark, 1 = Light
                except Exception:
                    return False
            return False
    darkdetect = DarkDetectFallback()

from ttkbootstrap import Style, ttk
from ttkbootstrap.constants import *

if platform.system() == 'Windows':
    import winreg


# =============================================================================
# CONFIGURAZIONE E GESTIONE FILE DI CONFIGURAZIONE
# =============================================================================
def get_base_path():
    """Percorso base dell'app (cartella eseguibile o cartella padre, se in dev)."""
    if getattr(sys, 'frozen', False):
        exe_path = Path(sys.executable).resolve()
        return exe_path.parent
    else:
        return Path(__file__).resolve().parent.parent

def get_config_path():
    """Percorso del file config.ini."""
    return get_base_path() / 'config.ini'

def load_configs():
    """
    Carica il file config.ini, o ne crea uno con valori di default
    se non esiste.
    """
    config = configparser.ConfigParser()
    config_path = get_config_path()
    logging.debug(f"Caricamento config da: {config_path}")
    if config_path.exists():
        try:
            config.read(config_path)
            logging.debug("Configurazione caricata con successo.")
        except Exception as e:
            logging.error(f"Errore durante la lettura di {config_path}: {e}")
    else:
        logging.debug("Nessun file config trovato. Creazione predefinita.")
        config['Settings'] = {
            'profile_path': '',
            'theme': 'system',
            'backup_folder': ''
        }
        save_configs(config)
    return config

def save_configs(config):
    """Salva il file di configurazione (config.ini)."""
    config_path = get_config_path()
    try:
        with open(config_path, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        logging.debug(f"Configurazione salvata in: {config_path}")
    except Exception as e:
        logging.error(f"Errore durante la scrittura di {config_path}: {e}")

BASE_DIR = get_base_path()
CACHE_FILE = BASE_DIR / "cache.json"

# =============================================================================
# REPO BETTERFOX
# =============================================================================
BETTERFOX_REPO_OWNER = "yokoffing"
BETTERFOX_REPO_NAME = "Betterfox"
RAW_USERJS_URL = f"https://raw.githubusercontent.com/{BETTERFOX_REPO_OWNER}/{BETTERFOX_REPO_NAME}/main/user.js"
GITHUB_COMMITS_API = f"https://api.github.com/repos/{BETTERFOX_REPO_OWNER}/{BETTERFOX_REPO_NAME}/commits?path=user.js&page=1&per_page=1"

# =============================================================================
# LOGGING E HANDLER
# =============================================================================
class ErrorFileHandler(logging.Handler):
    """
    Handler per scrivere su file solo i messaggi di livello ERROR.
    Lo crea solo al primo errore.
    """
    def __init__(self, filename):
        super().__init__(level=logging.ERROR)
        self.filename = filename
        self.file = None

    def emit(self, record):
        if self.file is None:
            try:
                self.file = open(self.filename, 'a', encoding='utf-8')
            except Exception:
                return
        msg = self.format(record)
        self.file.write(msg + '\n')
        self.file.flush()

    def close(self):
        if self.file:
            self.file.close()
        super().close()

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
error_handler = ErrorFileHandler(BASE_DIR / "error.log")
error_handler.setFormatter(formatter)
logger.addHandler(error_handler)

def handle_exception(exc_type, exc_value, exc_traceback):
    """
    Gestione eccezioni non catturate:
      - Se KeyboardInterrupt, usa handler di default
      - Altrimenti logga e termina
    """
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    print("Si è verificato un errore. Controlla error.log per dettagli.")
    sys.exit(1)

sys.excepthook = handle_exception

# =============================================================================
# FUNZIONI PER ICONE .ico E .png IN 'resources'
# =============================================================================
def find_ico_in_resources():
    """Cerca un file .ico in 'resources'."""
    resources_dir = BASE_DIR / "resources"
    if not resources_dir.exists() or not resources_dir.is_dir():
        logging.debug("Cartella 'resources' non trovata.")
        return None
    for file in resources_dir.iterdir():
        if file.is_file() and file.suffix.lower() == ".ico":
            logging.debug(f"Icona .ico trovata: {file}")
            return file
    logging.debug("Icona .ico non trovata in 'resources'.")
    return None

def find_png_in_resources():
    """Cerca un file .png in 'resources'."""
    resources_dir = BASE_DIR / "resources"
    if not resources_dir.exists() or not resources_dir.is_dir():
        return None
    for file in resources_dir.iterdir():
        if file.is_file() and file.suffix.lower() == ".png":
            logging.debug(f"Icona .png trovata: {file}")
            return file
    return None

ICON_PATH = find_ico_in_resources()
ICON_PNG_PATH = find_png_in_resources()

# =============================================================================
# LOG NELL'INTERFACCIA GRAFICA
# =============================================================================
def log_message(message_parts, clear=False):
    """
    Inserisce testo nel widget di log. 
    'message_parts' è una lista di tuple (testo, tag).
    Se clear=True, prima cancella il log.
    """
    global messages_displayed, last_message
    messages_displayed = True
    if 'log_output' not in globals():
        return

    message_text = ''.join(part for part, _ in message_parts)
    if message_text == last_message and not clear:
        return

    last_message = message_text
    if clear:
        clear_log()

    log_output.config(state='normal')
    first = True
    for part, tag in message_parts:
        # Aggiungo uno spazio se c’è un’emoji all’inizio
        if first and (part[:1] in ["🦊","💾","🌐","🕒","🗂️","❌","✅","🔄","⚠️","📥","🎉","ℹ️"]):
            if not part.endswith(" "):
                part += " "
            first = False
        if tag:
            log_output.insert(tk.END, part, tag)
        else:
            log_output.insert(tk.END, part)
    log_output.insert(tk.END, "\n")
    log_output.see(tk.END)
    log_output.config(state='disabled')

def clear_log():
    """Pulisce il log."""
    global last_message
    if 'log_output' in globals():
        log_output.config(state='normal')
        log_output.delete(1.0, tk.END)
        log_output.config(state='disabled')
    last_message = ""

def return_to_main_info():
    """Ripristina la vista principale delle informazioni."""
    clear_log()
    update_main_info()

def schedule_return_to_main_info(delay=5000):
    """Chiama finish_update() dopo 'delay' ms."""
    global after_id
    if after_id:
        root.after_cancel(after_id)
    after_id = root.after(delay, finish_update)

def finish_update():
    """Ripristina l’UI dopo un’operazione, abilitando i pulsanti e nascondendo la progress bar."""
    enable_buttons()
    hide_progress_bar()
    return_to_main_info()

config = load_configs()
if 'Settings' not in config:
    config['Settings'] = {
        'profile_path': '',
        'theme': 'system',
        'backup_folder': ''
    }
    save_configs(config)

after_id = None
last_message = ""
messages_displayed = False
progress_bar = None  # Per la barra di avanzamento

# =============================================================================
# FUNZIONI PER ESTRARRE VERSIONI / INFO
# =============================================================================
def extract_version(content):
    """Estrae la versione di Betterfox dal testo."""
    match = re.search(r'// Betterfox(?: user\.js)? v?([\d\.]+)', content, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r'version[:=]\s*(\d+(?:\.\d+)*)', content, re.IGNORECASE)
    if match:
        return match.group(1)
    return None

def get_local_version(profile_path):
    """Recupera la versione locale di Betterfox dal file user.js."""
    userjs_path = profile_path / "user.js"
    if userjs_path.exists():
        try:
            with open(userjs_path, "r", encoding='utf-8') as f:
                version = extract_version(f.read())
                logging.debug(f"Versione locale: {version}")
                return version
        except Exception as e:
            log_message([("❌", None), ("Errore lettura user.js: ", None), (str(e), 'error')])
    return None

def get_remote_version():
    """Ottiene versione e contenuto user.js dal repo GitHub."""
    try:
        response = requests.get(RAW_USERJS_URL, timeout=10)
        response.raise_for_status()
        content = response.text
        version = extract_version(content)
        logging.debug(f"Versione remota: {version}")
        return version, content
    except Exception as e:
        log_message([("❌", None), ("Errore recupero versione remota: ", None), (str(e), 'error')])
        return None, None

def get_github_last_update():
    """Restituisce data dell'ultimo commit su user.js nel repo GitHub."""
    try:
        response = requests.get(GITHUB_COMMITS_API, timeout=10)
        response.raise_for_status()
        commits = response.json()
        if commits:
            commit_date = commits[0]["commit"]["committer"]["date"]
            dt = datetime.strptime(commit_date, "%Y-%m-%dT%H:%M:%SZ")
            logging.debug(f"Ultimo aggiornamento GitHub: {dt}")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        log_message([("❌", None), ("Errore recupero ultimo update GitHub: ", None), (str(e), 'error')])
    return "Data non disponibile"

def get_firefox_version(profile_path=None):
    """
    Recupera la versione di Firefox:
      - Se profile_path è dato, prova da compatibility.ini
      - Su Windows cerca nel registro e path noti
      - Su macOS/Linux path/comandi
    """
    system_os = platform.system()
    if profile_path:
        ci = profile_path / "compatibility.ini"
        if ci.exists():
            cp = configparser.ConfigParser()
            cp.read(ci)
            if 'Application' in cp and 'Version' in cp['Application']:
                return cp['Application']['Version']
            elif 'App' in cp and 'Version' in cp['App']:
                return cp['App']['Version']

    if system_os == 'Windows':
        try:
            reg_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Mozilla\Mozilla Firefox")
            current_version, _ = winreg.QueryValueEx(reg_key, "CurrentVersion")
            winreg.CloseKey(reg_key)
            logging.debug(f"Versione Firefox da registro: {current_version}")
            return current_version
        except Exception as e:
            logging.error(f"Errore lettura versione Firefox da registro: {e}")
        paths = [
            Path('C:/Program Files/Mozilla Firefox/firefox.exe'),
            Path('C:/Program Files (x86)/Mozilla Firefox/firefox.exe')
        ]
        for p in paths:
            if p.exists():
                try:
                    vout = subprocess.check_output([str(p), '-v'], stderr=subprocess.STDOUT,
                                                   encoding='utf-8', errors='replace')
                    v = re.search(r'Firefox\s+([\d\.]+)', vout)
                    if v:
                        version = v.group(1)
                        logging.debug(f"Versione Firefox via comando: {version}")
                        return version
                except Exception as e:
                    logging.error(f"Errore recupero versione Firefox via comando: {e}")

    elif system_os == 'Darwin':
        fp = '/Applications/Firefox.app/Contents/MacOS/firefox'
        if Path(fp).exists():
            try:
                vout = subprocess.check_output([fp, '-v'], stderr=subprocess.STDOUT,
                                               encoding='utf-8', errors='replace')
                v = re.search(r'Firefox\s+([\d\.]+)', vout)
                if v:
                    version = v.group(1)
                    logging.debug(f"Versione Firefox macOS: {version}")
                    return version
            except Exception as e:
                logging.error(f"Errore recupero versione Firefox macOS: {e}")

    elif system_os == 'Linux':
        try:
            vout = subprocess.check_output(['firefox', '-v'], stderr=subprocess.STDOUT,
                                           encoding='utf-8', errors='replace')
            v = re.search(r'Firefox\s+([\d\.]+)', vout)
            if v:
                version = v.group(1)
                logging.debug(f"Versione Firefox Linux: {version}")
                return version
        except Exception as e:
            logging.error(f"Errore recupero versione Firefox Linux: {e}")

    return None

def get_default_firefox_profile():
    """
    Cerca il profilo di default di Firefox (bloccato o ultimo usato).
    """
    system_os = platform.system()
    if system_os == 'Windows':
        base_dir = Path(os.environ['APPDATA']) / 'Mozilla' / 'Firefox'
    elif system_os == 'Darwin':
        base_dir = Path.home() / 'Library' / 'Application Support' / 'Firefox'
    else:
        base_dir = Path.home() / '.mozilla' / 'firefox'

    pi = base_dir / 'profiles.ini'
    if not pi.exists():
        logging.warning(f"profiles.ini non trovato: {pi}")
        return None

    cp = configparser.ConfigParser()
    cp.read(pi)
    profiles = []
    for s in cp.sections():
        if s.startswith('Profile'):
            p = cp.get(s, 'Path', fallback=None)
            is_rel = cp.get(s, 'IsRelative', fallback='1')
            if p:
                p = (base_dir / p) if is_rel == '1' else Path(p)
                profiles.append(p.resolve())

    # Profilo bloccato
    for p in profiles:
        for lf in ['lock', '.parentlock']:
            if (p / lf).exists():
                logging.debug(f"Profilo bloccato: {p}")
                return p

    # Ultimo profilo usato
    last_used_profile = None
    last_used_time = None
    for p in profiles:
        tj = p / 'times.json'
        if tj.exists():
            try:
                with open(tj, 'r') as f:
                    td = json.load(f)
                    lu = td.get('created', 0)
                    if last_used_time is None or lu > last_used_time:
                        last_used_time = lu
                        last_used_profile = p
            except Exception as e:
                logging.error(f"Errore lettura times.json per {p}: {e}")
                continue

    if last_used_profile:
        logging.debug(f"Ultimo profilo usato: {last_used_profile}")
        return last_used_profile
    if profiles:
        logging.debug(f"Primo profilo trovato: {profiles[0]}")
        return profiles[0]
    return None

# =============================================================================
# GESTIONE TEMA
# =============================================================================
def is_dark_theme():
    """Determina se usare il tema scuro (darkdetect o 'darkly')."""
    theme = config['Settings'].get('theme', 'system')
    if theme == 'system':
        return darkdetect.isDark()
    elif theme == 'darkly':
        return True
    else:
        return False

# =============================================================================
# FINESTRA PER SELEZIONARE LA CARTELLA BASE E NOMINARE (OPZIONALE) LA CARTELLA BACKUP
# =============================================================================
def ask_backup_folder():
    """
    Chiede all'utente:
      - La cartella base
      - (Opzionale) un nome per la cartella di destinazione (default: BetterfoxBackups).
    Verrà creata/usiata una cartella "BetterfoxBackups" (o personalizzata) nella path base selezionata.
    """
    top = Toplevel(root)
    top.title("Imposta Cartella Backup Completo")
    top.resizable(False, False)

    try:
        if ICON_PATH:
            if platform.system() == 'Windows':
                top.iconbitmap(str(ICON_PATH.resolve()))
                if ICON_PNG_PATH:
                    icon_image = tk.PhotoImage(file=str(ICON_PNG_PATH.resolve()))
                    top.iconphoto(False, icon_image)
                    top.icon_image = icon_image
                set_taskbar_icon(top, str(ICON_PATH.resolve()))
            else:
                if ICON_PNG_PATH:
                    icon_image = tk.PhotoImage(file=str(ICON_PNG_PATH.resolve()))
                    top.iconphoto(True, icon_image)
                    top.icon_image = icon_image
    except Exception as e:
        logging.error(f"Errore icona finestra backup: {e}")

    apply_title_bar_theme(top, dark=is_dark_theme())

    frame = ttk.Frame(top, padding=10)
    frame.pack(fill="x", expand=True)

    lbl_base = ttk.Label(frame, text="Seleziona la cartella base dove salvare i backup:")
    lbl_base.grid(row=0, column=0, columnspan=2, sticky="w")

    base_var = StringVar()
    base_entry = ttk.Entry(frame, textvariable=base_var, width=50)
    base_entry.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

    def browse_base():
        f = filedialog.askdirectory(title="Seleziona cartella base per i backup Betterfox")
        if f:
            base_var.set(f)

    browse_btn = ttk.Button(frame, text="Sfoglia", command=browse_base)
    browse_btn.grid(row=1, column=1, padx=5, pady=5)

    lbl_sub = ttk.Label(frame, text="Nome cartella destinazione (opzionale, default=BetterfoxBackups):")
    lbl_sub.grid(row=2, column=0, columnspan=2, sticky="w", pady=(5,0))

    sub_var = StringVar()
    sub_entry = ttk.Entry(frame, textvariable=sub_var, width=50)
    sub_entry.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

    chosen_dir = []

    def confirm():
        base = base_var.get().strip()
        sub = sub_var.get().strip()
        if not base:
            chosen_dir.append(None)
            top.destroy()
            return

        base_path = Path(base)
        if not base_path.exists():
            try:
                base_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                log_message([("❌", None), ("Errore creazione cartella base: ", None), (str(e), 'error')])
                chosen_dir.append(None)
                top.destroy()
                return

        if not sub:
            sub = "BetterfoxBackups"
        final_path = base_path / sub
        if not final_path.exists():
            try:
                final_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                log_message([("❌", None), ("Errore creazione cartella destinazione: ", None), (str(e), 'error')])
                chosen_dir.append(None)
                top.destroy()
                return

        chosen_dir.append(str(final_path))
        top.destroy()

    def cancel():
        chosen_dir.append(None)
        top.destroy()

    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=4, column=0, columnspan=2, pady=10)

    confirm_btn = ttk.Button(btn_frame, text="Conferma", command=confirm)
    confirm_btn.grid(row=0, column=0, padx=5)
    cancel_btn = ttk.Button(btn_frame, text="Annulla", command=cancel)
    cancel_btn.grid(row=0, column=1, padx=5)

    def on_close():
        if not chosen_dir:
            chosen_dir.append(None)
        top.destroy()

    top.protocol("WM_DELETE_WINDOW", on_close)
    top.wait_window(top)

    return chosen_dir[0] if chosen_dir else None

def select_backup_destination():
    """
    Avvia la finestra di selezione per la cartella base e il nome
    della cartella di destinazione backup (default: BetterfoxBackups).
    """
    folder = ask_backup_folder()
    if folder:
        config['Settings']['backup_folder'] = folder
        save_configs(config)
        logging.debug(f"Backup folder impostata su: {folder}")
    return folder

# =============================================================================
# GESTIONE DEI BACKUP (CREAZIONE, COMPRESSIONE, RIMOZIONE VECCHI)
# =============================================================================
def full_backup_folder():
    """Ritorna la cartella di backup Betterfox dal file di config."""
    return config['Settings'].get('backup_folder', '')

def compress_backup_folder(backup_path):
    """
    Comprimi la cartella 'backup_path' in .zip, poi rimuovi la cartella originale.
    Se lo zip esiste già, non ricomprime.
    """
    zip_file = backup_path.with_suffix(".zip")
    if zip_file.exists():
        logging.debug(f"Backup già compresso in: {zip_file}")
        return False
    try:
        make_archive(str(backup_path), 'zip', root_dir=str(backup_path))
        rmtree(backup_path)
        logging.debug(f"Backup compresso e cartella rimossa: {backup_path}")
        return True
    except Exception as e:
        logging.error(f"Errore compressione {backup_path}: {e}")
        return False

def handle_old_backup(backup_path):
    """
    Gestisce un singolo backup:
      - Se è .zip ed è oltre 60 giorni, lo rimuove
      - Se è cartella con >60 giorni, rimuove
      - Se è cartella con 30<=giorni<60, comprime
    """
    try:
        if backup_path.suffix.lower() == ".zip":
            base_name = backup_path.stem
            if "full_profile_backup_" in base_name:
                date_str = base_name.replace("full_profile_backup_", "")
                try:
                    backup_date = datetime.strptime(date_str, "%Y-%m-%d_%H-%M-%S")
                except:
                    logging.error(f"Parsing data fallito: {backup_path}")
                    backup_path.unlink(missing_ok=True)
                    return
                age_days = (datetime.now() - backup_date).days
                if age_days >= 60:
                    backup_path.unlink(missing_ok=True)
                    logging.debug(f"Backup .zip vecchio rimosso: {backup_path}")
            return

        if backup_path.is_dir():
            name = backup_path.name
            if not name.startswith("full_profile_backup_"):
                return
            date_str = name.replace("full_profile_backup_", "")
            backup_date = datetime.strptime(date_str, "%Y-%m-%d_%H-%M-%S")
            age_days = (datetime.now() - backup_date).days
            if age_days >= 60:
                rmtree(backup_path)
                logging.debug(f"Backup cartella rimossa: {backup_path}")
            elif age_days >= 30:
                compress_backup_folder(backup_path)

    except Exception as e:
        logging.error(f"handle_old_backup error: {backup_path} - {e}")

def clean_backup_folder():
    """
    Scandisce la cartella di backup e comprime/rimuove i backup in base all'età:
      - Oltre 60 giorni -> rimozione
      - Tra 30 e 60 giorni -> compressione
      - Sotto 30 giorni -> nulla
    """
    bf = full_backup_folder()
    if not bf:
        return
    bf_path = Path(bf)
    if not bf_path.exists():
        return
    for item in bf_path.iterdir():
        handle_old_backup(item)

def close_firefox():
    """Termina Firefox su Windows/macOS/Linux."""
    system_os = platform.system()
    logging.debug(f"Chiudo Firefox su: {system_os}")
    if system_os == 'Windows':
        subprocess.run(['taskkill', '/F', '/IM', 'firefox.exe'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       encoding='utf-8', errors='replace')
    else:
        subprocess.run(['pkill', 'firefox'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       encoding='utf-8', errors='replace')
    time.sleep(0.3)

def fallback_copy_tree(src, dst):
    """Copia ricorsivamente src in dst come fallback se robocopy fallisce."""
    if not dst.exists():
        dst.mkdir(parents=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            fallback_copy_tree(item, target)
        else:
            try:
                copy2(item, target)
            except Exception as e:
                logging.error(f"Errore copia fallback {item} -> {target}: {e}")
                raise

def copy_tree(src, dst):
    """Copia ricorsivamente la cartella src in dst (robocopy su Windows con fallback)."""
    if platform.system() == 'Windows':
        src_str = str(src.resolve())
        dst_str = str(dst.resolve())
        if not src_str.endswith('\\'):
            src_str += '\\'
        try:
            result = subprocess.run(
                ['robocopy', src_str, dst_str, '/E', '/COPYALL', '/R:0', '/W:0'],
                shell=True, capture_output=True, text=True,
                encoding='utf-8', errors='replace'
            )
            if result.returncode >= 8:
                if result.returncode == 16:
                    logging.warning("Robocopy code 16, fallback al copia nativa.")
                    fallback_copy_tree(src, dst)
                else:
                    raise subprocess.CalledProcessError(
                        result.returncode, 'robocopy',
                        output=result.stdout, stderr=result.stderr
                    )
        except Exception as e:
            logging.error(f"Errore copia con robocopy: {e}")
            raise
    else:
        if not dst.exists():
            dst.mkdir(parents=True)
        for item in src.iterdir():
            target = dst / item.name
            if item.is_dir():
                copy_tree(item, target)
            else:
                try:
                    copy2(item, target)
                except Exception as e:
                    logging.error(f"Errore copia {item} -> {target}: {e}")

def ensure_backup_folder_exists():
    """
    Verifica che esista la cartella di backup configurata.
    Altrimenti apre la finestra per selezionarla.
    """
    bf = full_backup_folder()
    if not bf:
        return select_backup_destination()
    bf_path = Path(bf)
    if not bf_path.exists():
        return select_backup_destination()
    return bf

def create_full_backup(profile_path):
    """
    Esegue un backup completo del profilo:
      - Verifica/crea la cartella di backup
      - Chiude Firefox
      - Pulisce i backup vecchi (compattando o rimuovendo)
      - Crea un nuovo backup in full_profile_backup_TIMESTAMP
    """
    bf = ensure_backup_folder_exists()
    if not bf:
        log_message([("⚠️", None), ("Nessuna cartella di backup fornita o operazione annullata.", None)])
        return False

    bf_path = Path(bf)
    if not bf_path.exists():
        try:
            bf_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            log_message([("❌", None), ("Errore creazione cartella backup: ", None), (str(e), 'error')])
            return False

    close_firefox()
    log_message([("🗂️", None), ("Eseguo backup completo del profilo...", None)])
    time.sleep(0.3)

    # Pulizia vecchi backup
    clean_backup_folder()

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_subdir = bf_path / f"full_profile_backup_{timestamp}"
    try:
        log_message([("📥", None), ("Copia dei file del profilo...", None)])
        time.sleep(0.3)
        copy_tree(profile_path, backup_subdir)
        log_message([("✅", None), ("Backup completo creato in: ", None), (str(backup_subdir), 'highlight')])
        return True
    except Exception as e:
        log_message([("❌", None), ("Errore durante backup completo: ", None), (str(e), 'error')])
        return False

def manual_full_backup():
    """Avvio manuale di backup completo."""
    clear_log()
    profile_path = Path(profile_entry.get())
    if not profile_path.exists():
        log_message([("❌", None), ("Il profilo specificato non esiste.", None)])
        schedule_return_to_main_info()
        return
    if create_full_backup(profile_path):
        log_message([("✅", None), ("Backup completo eseguito con successo.", None)])
    schedule_return_to_main_info()

def manual_change_backup_folder():
    """Permette di cambiare la cartella di backup."""
    clear_log()
    folder = select_backup_destination()
    if folder:
        log_message([("✅", None), ("Cartella di backup impostata su: ", None), (folder, 'highlight')])
    else:
        log_message([("⚠️", None), ("Operazione annullata.", None)])
    schedule_return_to_main_info()

def restore_backup(profile_path):
    """Ripristina user.js da un backup semplice selezionato."""
    clear_log()
    log_message([("🔄", None), ("Seleziona un backup semplice da ripristinare...", None)])
    backup_to_restore = filedialog.askdirectory(title="Seleziona un backup da ripristinare")
    if backup_to_restore:
        log_message([("🔄", None), ("Ripristino in corso...", None)])
        time.sleep(0.3)
        for file_name in ["user.js"]:
            backup_file = Path(backup_to_restore) / file_name
            if backup_file.exists():
                try:
                    copy2(backup_file.resolve(), (profile_path / file_name).resolve())
                    log_message([("✅", None), (file_name, 'highlight'), (" ripristinato con successo.", None)])
                except Exception as e:
                    log_message([("❌", None), ("Errore ripristino ", None), (file_name, 'highlight'), (": ", None), (str(e), 'error')])
    else:
        log_message([("⚠️", None), ("Operazione di ripristino annullata.", None)])
    schedule_return_to_main_info()

# =============================================================================
# BARRA DI AVANZAMENTO
# =============================================================================
def show_progress_bar():
    """Mostra e avvia la progress bar in modalità indeterminate."""
    progress_bar.grid(row=2, column=0, columnspan=3, pady=5, sticky="ew")
    progress_bar.start(10)

def hide_progress_bar():
    """Ferma e nasconde la progress bar."""
    progress_bar.stop()
    progress_bar.grid_remove()

# =============================================================================
# OPERAZIONI DI AGGIORNAMENTO
# =============================================================================
def restart_firefox():
    """Riavvia Firefox su Windows/macOS/Linux."""
    log_message([("🔄", None), ("Riavvio di Firefox...", None)])
    time.sleep(0.3)
    system_os = platform.system()
    try:
        if system_os == 'Windows':
            subprocess.Popen(['cmd', '/c', 'start', 'firefox'], shell=True, encoding='utf-8', errors='replace')
        elif system_os == 'Darwin':
            subprocess.Popen(['/Applications/Firefox.app/Contents/MacOS/firefox'], encoding='utf-8', errors='replace')
        else:
            subprocess.Popen(['firefox'], encoding='utf-8', errors='replace')
        log_message([("✅", None), ("Firefox riavviato con successo.", None)])
    except Exception as e:
        log_message([("❌", None), ("Errore nel riavvio di Firefox: ", None), (str(e), 'error')])

def download_userjs(profile_path, remote_content, remote_version):
    """Scarica e salva user.js aggiornato nel profilo."""
    log_message([("📥", None), ("Scarico user.js aggiornato...", None)])
    time.sleep(0.3)
    try:
        userjs_path = profile_path / 'user.js'
        with open(userjs_path, 'w', encoding='utf-8') as uf:
            uf.write(remote_content)
        log_message([("✅", None), ("File user.js salvato in: ", None), (str(userjs_path), 'highlight')])
        return True
    except Exception as e:
        log_message([("❌", None), ("Errore download user.js: ", None), (str(e), 'error')])
        return False

def run_update(profile_path):
    """Avvia l'aggiornamento in un thread, mostra la progress bar e disabilita pulsanti."""
    disable_buttons()
    clear_log()
    show_progress_bar()
    threading.Thread(target=run_update_thread, args=(profile_path,), daemon=True).start()

def run_update_thread(profile_path):
    """
    Thread di aggiornamento:
      - Verifica versioni
      - Se serve, esegue backup completo
      - Scarica e sostituisce user.js
      - Riavvia Firefox
    """
    p = Path(profile_path)
    if not p.exists():
        log_message([("❌", None), ("Il profilo specificato non esiste.", None)])
        schedule_return_to_main_info()
        return

    firefox_version = get_firefox_version(p)
    local_version = get_local_version(p)
    remote_version, remote_content = get_remote_version()
    last_update = get_github_last_update()

    if last_update:
        log_message([("🕒", None), ("Ultimo aggiornamento su GitHub: ", None), (last_update, 'highlight')])

    needs_install = (local_version is None and remote_version is not None)
    needs_update = False
    if remote_version and remote_version != "Unknown":
        if local_version:
            try:
                lv = tuple(map(int, local_version.split('.')))
                rv = tuple(map(int, remote_version.split('.')))
                if rv > lv:
                    needs_update = True
            except:
                needs_update = True
        else:
            needs_update = True

    if needs_install or needs_update:
        # Pulisce e crea un full backup se necessario
        bf_path = full_backup_folder()
        if bf_path:
            clean_backup_folder()
        if not create_full_backup(p):
            schedule_return_to_main_info()
            return

    if needs_install or needs_update:
        if remote_content:
            if download_userjs(p, remote_content, remote_version):
                if local_version:
                    log_message([("🎉", None),
                                 ("Betterfox aggiornato alla versione ", None),
                                 (f"v{remote_version}", 'highlight'), ("!", None)])
                else:
                    log_message([("🎉", None),
                                 ("Betterfox installato alla versione ", None),
                                 (f"v{remote_version}", 'highlight'), ("!", None)])
                restart_firefox()
            else:
                log_message([("❌", None), ("Impossibile scaricare user.js remoto.", None)])
        else:
            log_message([("❌", None), ("Contenuto user.js remoto non disponibile.", None)])
    else:
        log_message([("✅", None), ("Betterfox è già aggiornato all'ultima versione.", None)])

    schedule_return_to_main_info()

# =============================================================================
# GESTIONE PROFILO
# =============================================================================
def save_profile_path(path):
    """Salva il percorso del profilo in config.ini."""
    config['Settings']['profile_path'] = path
    save_configs(config)
    logging.debug(f"Profilo salvato: {path}")

def change_backup_folder():
    """Permette di cambiare la cartella di backup."""
    clear_log()
    folder = select_backup_destination()
    if folder:
        log_message([("✅", None), ("Cartella di backup impostata su: ", None), (folder, 'highlight')])
    else:
        log_message([("⚠️", None), ("Operazione annullata dall'utente.", None)])
    schedule_return_to_main_info()

def select_profile():
    """Finestra di dialogo per selezionare la cartella del profilo Firefox."""
    profile_path = filedialog.askdirectory(title="Seleziona cartella profilo Firefox")
    if profile_path:
        profile_entry.delete(0, tk.END)
        profile_entry.insert(0, profile_path)
        save_profile_path(profile_path)
        log_message([("✅", None), ("Profilo selezionato con successo.", None)])
    else:
        log_message([("⚠️", None), ("Operazione annullata dall'utente.", None)])
    schedule_return_to_main_info()

def exit_app():
    """Chiusura dell'applicazione."""
    on_closing()

# =============================================================================
# TEMA E INTERFACCIA
# =============================================================================
def set_theme(theme_name):
    """Imposta il tema (system/darkly/flatly)."""
    if theme_name == 'system':
        actual_theme = 'darkly' if darkdetect.isDark() else 'flatly'
    else:
        actual_theme = theme_name
    try:
        style.theme_use(actual_theme)
        logging.debug(f"Tema selezionato: {actual_theme}")
    except tk.TclError as e:
        log_message([("❌", None), ("Tema non valido: ", None), (theme_name, 'error')])
        logging.error(f"Errore tema {theme_name}: {e}")
        schedule_return_to_main_info()
        return

    config['Settings']['theme'] = theme_name
    save_configs(config)
    update_menu_style()
    update_colors_based_on_theme()
    apply_title_bar_theme(root, dark=is_dark_theme())
    if ICON_PATH:
        set_taskbar_icon(root, str(ICON_PATH.resolve()))
    schedule_return_to_main_info()

def update_menu_style():
    """Aggiorna il colore di sfondo della menubar."""
    bg_color = style.colors.inputbg
    menubar.config(bg=bg_color)

def update_colors_based_on_theme():
    """Aggiorna i colori del log e del footer in base al tema."""
    theme = style.theme_use()
    if theme == "darkly":
        log_output.configure(bg=style.colors.inputbg, fg='white', insertbackground='white')
        footer.configure(foreground='white')
    else:
        log_output.configure(bg=style.colors.inputbg, fg='black', insertbackground='black')
        footer.configure(foreground='black')

def disable_buttons():
    """Disabilita i pulsanti principali (Aggiornamento, Sfoglia)."""
    update_button.config(state='disabled')
    browse_button.config(state='disabled')

def enable_buttons():
    """Riabilita i pulsanti."""
    update_button.config(state='normal')
    browse_button.config(state='normal')

def on_closing():
    """Chiude l'applicazione, annullando callback pendenti."""
    global after_id
    if after_id is not None:
        root.after_cancel(after_id)
        after_id = None
    root.destroy()
    logging.debug("Applicazione chiusa.")

def reload_info():
    """Pulisce il log e aggiorna le info principali."""
    clear_log()
    update_main_info()

# =============================================================================
# TITOLO FINESTRA E ICONA TASKBAR (SOLO WINDOWS)
# =============================================================================
def apply_title_bar_theme(window, dark):
    """Applica il tema scuro/chiaro alla title bar di Windows, se disponibile."""
    if platform.system() != 'Windows':
        return
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(1 if dark else 0)
        dwmapi = ctypes.windll.dwmapi
        result = dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value), ctypes.sizeof(value)
        )
        if result != 0:
            raise Exception(f"DwmSetWindowAttribute fallito con codice {result}")
    except Exception as e:
        logging.error(f"Errore impostazione tema title bar: {e}")

def set_taskbar_icon(window, icon_path):
    """Imposta l'icona della taskbar su Windows tramite ctypes."""
    if platform.system() != 'Windows':
        return
    try:
        hicon = ctypes.windll.user32.LoadImageW(
            None,
            icon_path,
            1,  # IMAGE_ICON
            0,
            0,
            0x00000010  # LR_LOADFROMFILE
        )
        if hicon == 0:
            raise Exception("LoadImageW fallita.")
        hwnd = window.winfo_id()
        ctypes.windll.user32.SendMessageW(hwnd, 0x80, 0, hicon)  # WM_SETICON small
        ctypes.windll.user32.SendMessageW(hwnd, 0x80, 1, hicon)  # WM_SETICON big
    except Exception as e:
        logging.error(f"Errore impostazione icona taskbar: {e}")

# =============================================================================
# CREAZIONE E AVVIO INTERFACCIA
# =============================================================================
root = tk.Tk()
root.withdraw()  # Costruzione UI offscreen

root.title("Betterfox Updater v2.2")
root.geometry("500x420")
root.resizable(False, False)

saved_theme = config['Settings'].get('theme', 'system')
if saved_theme == 'system':
    theme_name = "darkly" if darkdetect.isDark() else "flatly"
else:
    theme_name = saved_theme

style = Style(theme=theme_name)

# Icona
try:
    if ICON_PATH:
        if platform.system() == 'Windows':
            root.iconbitmap(str(ICON_PATH.resolve()))
            if ICON_PNG_PATH:
                icon_image = tk.PhotoImage(file=str(ICON_PNG_PATH.resolve()))
                root.iconphoto(False, icon_image)
                root.icon_image = icon_image
            set_taskbar_icon(root, str(ICON_PATH.resolve()))
        else:
            if ICON_PNG_PATH:
                icon_image = tk.PhotoImage(file=str(ICON_PNG_PATH.resolve()))
                root.iconphoto(True, icon_image)
                root.icon_image = icon_image
    else:
        logging.warning("Nessuna icona .ico trovata in resources.")
except Exception as e:
    logging.error(f"Errore caricamento icona principale: {e}")

menubar = tk.Menu(root, bg=style.colors.inputbg)
options_menu = tk.Menu(menubar, tearoff=0, bg=style.colors.inputbg)
theme_menu = tk.Menu(options_menu, tearoff=0, bg=style.colors.inputbg)
backup_menu = tk.Menu(options_menu, tearoff=0, bg=style.colors.inputbg)

theme_menu.add_command(label="Sistema", command=lambda: set_theme('system'))
theme_menu.add_command(label="Chiaro", command=lambda: set_theme("flatly"))
theme_menu.add_command(label="Scuro", command=lambda: set_theme("darkly"))
options_menu.add_cascade(label="Tema", menu=theme_menu)

backup_menu.add_command(label="Esegui Backup Completo", command=manual_full_backup)
backup_menu.add_command(label="Ripristina Backup", command=lambda: restore_backup(Path(profile_entry.get())))
backup_menu.add_command(label="Cambia Cartella Backup Completo", command=manual_change_backup_folder)
options_menu.add_cascade(label="Backup", menu=backup_menu)

options_menu.add_command(label="Ricarica Informazioni", command=reload_info)
options_menu.add_separator()
options_menu.add_command(label="Esci", command=exit_app)
menubar.add_cascade(label="Opzioni", menu=options_menu)
root.config(menu=menubar)

root.grid_rowconfigure(1, weight=1)
root.grid_columnconfigure(0, weight=1)

profile_labelframe = ttk.Labelframe(root, text="Profilo Firefox", padding=10)
profile_labelframe.grid(row=0, column=0, sticky="ew", padx=10, pady=(10,5))
profile_labelframe.columnconfigure(1, weight=1)

profile_label = ttk.Label(profile_labelframe, text="Cartella profilo:")
profile_label.grid(row=0, column=0, sticky="e", pady=2, padx=5)

profile_entry = ttk.Entry(profile_labelframe, width=40)
profile_entry.grid(row=0, column=1, padx=5, sticky="ew", pady=2)

browse_button = ttk.Button(profile_labelframe, text="Sfoglia", command=select_profile, takefocus=False)
browse_button.grid(row=0, column=2, padx=5, pady=2)

button_frame = ttk.Frame(profile_labelframe)
button_frame.grid(row=1, column=0, columnspan=3, pady=(10,5))

update_button = ttk.Button(button_frame, text="Avvia Aggiornamento",
                           command=lambda: run_update(profile_entry.get()), takefocus=False)
update_button.grid(row=0, column=0, padx=5)

log_frame = ttk.Frame(root, padding=10)
log_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
log_frame.columnconfigure(0, weight=1)
log_frame.rowconfigure(0, weight=1)

log_output = tk.Text(
    log_frame,
    wrap=tk.WORD,
    state='disabled',
    font=('Segoe UI', 10),
    spacing1=2,
    spacing2=2,
    spacing3=2,
    bd=0,
    highlightthickness=0
)
log_output.grid(row=0, column=0, sticky="nsew")
log_output.tag_config('highlight', foreground=style.colors.primary, font=('Segoe UI', 10, 'bold'))
log_output.tag_config('error', foreground='red')

progress_bar = ttk.Progressbar(profile_labelframe, orient="horizontal", mode="indeterminate")
progress_bar.grid_remove()

footer = ttk.Label(root, text="Betterfox Updater v2.2")
footer.grid(row=2, column=0, pady=(5,10))

style.configure('TButton', focusthickness=0)

saved_path = config['Settings'].get('profile_path', '')
if saved_path and Path(saved_path).exists():
    profile_entry.insert(0, saved_path)
else:
    default_profile_path = get_default_firefox_profile()
    if default_profile_path and default_profile_path.exists():
        profile_entry.insert(0, str(default_profile_path))
        config['Settings']['profile_path'] = str(default_profile_path)
        save_configs(config)

def update_main_info():
    """
    Mostra le informazioni principali:
      - Versione Firefox
      - Versione Betterfox locale/remota
      - Ultimo aggiornamento su GitHub
    """
    profile_path = profile_entry.get()
    clear_log()
    if profile_path:
        p = Path(profile_path)
        if not p.exists():
            log_message([("❌", None), ("Il profilo specificato non esiste.", None)], clear=False)
            logging.warning(f"Profilo non esistente: {p}")
            return

        # Info Firefox
        firefox_version = get_firefox_version(p)
        if firefox_version:
            log_message([("🦊", None), ("Versione di Firefox: ", None), (firefox_version, 'highlight')])
        else:
            log_message([("❌", None), ("Impossibile rilevare la versione di Firefox.", None)])

        local_version = get_local_version(p)
        remote_version, _ = get_remote_version()
        last_update = get_github_last_update()

        if local_version:
            log_message([("💾", None), ("Versione Betterfox locale: ", None), (f"v{local_version}", 'highlight')])
        else:
            log_message([("💾", None), ("Betterfox non risulta installato nel profilo.", None)])

        if remote_version:
            log_message([("🌐", None), ("Versione Betterfox remota: ", None), (f"v{remote_version}", 'highlight')])
        else:
            log_message([("🌐", None), ("Versione Betterfox remota: Non disponibile", 'error')])

        if last_update and last_update != "Data non disponibile":
            log_message([("🕒", None), ("Ultimo aggiornamento su GitHub: ", None), (last_update, 'highlight')])
        else:
            log_message([("🕒", None), ("Ultimo aggiornamento GitHub: Non disponibile", 'error')])

def initialize_app():
    """Applica tema, aggiorna info e mostra la finestra (deiconify)."""
    apply_title_bar_theme(root, dark=is_dark_theme())
    update_main_info()
    update_colors_based_on_theme()
    logging.debug("Applicazione inizializzata.")
    root.deiconify()

root.after(0, initialize_app)
root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()
