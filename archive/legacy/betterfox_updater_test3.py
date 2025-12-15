import os
import sys
import logging
import requests
from pathlib import Path
from shutil import copy2, rmtree
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import filedialog, Toplevel, StringVar
import re
import platform
import subprocess
import configparser
import time
import darkdetect
from ttkbootstrap import Style, ttk
from ttkbootstrap.constants import *
import threading
import ctypes
import json

if platform.system() == 'Windows':
    import winreg

# ================================================================
# CONFIGURAZIONE
# ================================================================
def get_base_path():
    """
    In modalità 'frozen' (Nuitka --onefile), puntiamo alla cartella dove risiede l'eseguibile.
    In modalità sviluppo, assumiamo la struttura del progetto e puntiamo alla cartella 'Progetto'.
    """
    if getattr(sys, 'frozen', False):
        exe_path = Path(sys.executable).resolve()
        return exe_path.parent
    else:
        return Path(__file__).resolve().parent.parent

def get_config_path():
    """Percorso di config.ini nella directory di esecuzione."""
    return get_base_path() / 'config.ini'

def load_configs():
    """Carica (o crea) config.ini."""
    config = configparser.ConfigParser()
    config_path = get_config_path()
    logging.debug(f"Caricamento config da: {config_path}")
    if config_path.exists():
        try:
            config.read(config_path)
            logging.debug(f"Configurazione caricata da: {config_path}")
        except Exception as e:
            logging.error(f"Errore durante la lettura di {config_path}: {e}")
    else:
        # Creazione di config.ini con valori predefiniti
        logging.debug(f"Config non trovato. Creazione di {config_path} con valori predefiniti.")
        config['Settings'] = {
            'profile_path': '',
            'theme': 'system',
            'backup_folder': ''
        }
        save_configs(config)
    return config

def save_configs(config):
    """Salva config.ini nella directory di esecuzione."""
    config_path = get_config_path()
    try:
        with open(config_path, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        logging.debug(f"Configurazione salvata in: {config_path}")
    except Exception as e:
        logging.error(f"Errore durante la scrittura di {config_path}: {e}")

BASE_DIR = get_base_path()
CACHE_FILE = BASE_DIR / "cache.json"

# Definizioni delle variabili mancanti
BETTERFOX_REPO_OWNER = "yokoffing"
BETTERFOX_REPO_NAME = "Betterfox"
RAW_USERJS_URL = f"https://raw.githubusercontent.com/{BETTERFOX_REPO_OWNER}/{BETTERFOX_REPO_NAME}/main/user.js"
GITHUB_COMMITS_API = f"https://api.github.com/repos/{BETTERFOX_REPO_OWNER}/{BETTERFOX_REPO_NAME}/commits?path=user.js&page=1&per_page=1"

# ================================================================
# CONFIGURAZIONE LOGGING CON HANDLER PERSONALIZZATO
# ================================================================
class ErrorFileHandler(logging.Handler):
    """Handler che scrive su file solo per errori, creando il file solo quando necessario."""
    def __init__(self, filename):
        super().__init__(level=logging.ERROR)
        self.filename = filename
        self.file = None

    def emit(self, record):
        if self.file is None:
            try:
                self.file = open(self.filename, 'a', encoding='utf-8')
            except Exception as e:
                # Se non riesce ad aprire il file, non fare nulla
                return
        msg = self.format(record)
        self.file.write(msg + '\n')
        self.file.flush()

    def close(self):
        if self.file:
            self.file.close()
        super().close()

# Rimuove qualsiasi configurazione di logging precedente
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Imposta il logger di base
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Formatter per i log
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# Aggiunge solo l'handler di errore
error_handler = ErrorFileHandler(BASE_DIR / "error.log")
error_handler.setFormatter(formatter)
logger.addHandler(error_handler)

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    print("Si è verificato un errore. Controlla error.log per maggiori dettagli.")
    sys.exit(1)

sys.excepthook = handle_exception

# ================================================================
# FUNZIONE PER TROVARE .ICO E .PNG DINAMICAMENTE
# ================================================================
def find_ico_in_resources():
    """
    Cerca dinamicamente un file .ico in 'resources'.
    """
    resources_dir = BASE_DIR / "resources"
    if not resources_dir.exists() or not resources_dir.is_dir():
        logging.debug("Cartella resources non trovata.")
        return None

    for file in resources_dir.iterdir():
        if file.is_file() and file.suffix.lower() == ".ico":
            logging.debug(f"Icona .ico trovata: {file}")
            return file
    logging.debug("Icona .ico non trovata nella cartella resources.")
    return None

def find_png_in_resources():
    """
    Cerca dinamicamente un file .png in 'resources'.
    """
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

# ================================================================
# FUNZIONI LOG
# ================================================================
def log_message(message_parts, clear=False):
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
        if first and (part[:1] in ["🦊","💾","🌐","🕒","🗂️","❌","✅","🔄","⚠️","📥","🎉","ℹ️"]):
            if not part.endswith(" "):
                part += " "
            first = False
        if tag:
            log_output.insert(END, part, tag)
        else:
            log_output.insert(END, part)
    log_output.insert(END, "\n")
    log_output.see(END)
    log_output.config(state='disabled')
    root.update_idletasks()

def clear_log():
    global last_message
    if 'log_output' in globals():
        log_output.config(state='normal')
        log_output.delete(1.0, END)
        log_output.config(state='disabled')
    last_message = ""

def return_to_main_info():
    clear_log()
    update_main_info()

def schedule_return_to_main_info(delay=5000):
    global after_id
    if after_id:
        root.after_cancel(after_id)
    after_id = root.after(delay, finish_update)

def finish_update():
    enable_buttons()
    return_to_main_info()

# ================================================================
# CONFIGURAZIONI E VARIABILI GLOBALI
# ================================================================
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

# ================================================================
# FUNZIONI UTILI
# ================================================================
def extract_version(content):
    match = re.search(r'// Betterfox(?: user\.js)? v?([\d\.]+)', content, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r'version[:=]\s*(\d+(?:\.\d+)*)', content, re.IGNORECASE)
    if match:
        return match.group(1)
    return None

def get_local_version(profile_path):
    userjs_path = profile_path / "user.js"
    if userjs_path.exists():
        try:
            with open(userjs_path, "r", encoding='utf-8') as f:
                version = extract_version(f.read())
                logging.debug(f"Versione locale trovata: {version}")
                return version
        except Exception as e:
            log_message([("❌ ", None), ("Errore durante la lettura di user.js: ", None), (str(e), 'error')])
    return None

def get_remote_version():
    try:
        response = requests.get(RAW_USERJS_URL, timeout=10)
        response.raise_for_status()
        content = response.text
        version = extract_version(content)
        logging.debug(f"Versione remota trovata: {version}")
        return version, content
    except Exception as e:
        log_message([("❌ ", None), ("Errore durante il recupero della versione remota: ", None), (str(e), 'error')])
        return None, None

def get_github_last_update():
    try:
        response = requests.get(GITHUB_COMMITS_API, timeout=10)
        response.raise_for_status()
        commits = response.json()
        if commits:
            commit_date = commits[0]["commit"]["committer"]["date"]
            dt = datetime.strptime(commit_date, "%Y-%m-%dT%H:%M:%SZ")
            logging.debug(f"Ultimo aggiornamento su GitHub: {dt}")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        log_message([("❌ ", None), ("Errore durante il recupero dell'ultimo aggiornamento da GitHub: ", None), (str(e), 'error')])
        pass
    return "Data non disponibile"

def get_firefox_version(profile_path=None):
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
            logging.debug(f"Versione Firefox trovata nel registro di sistema: {current_version}")
            return current_version
        except Exception as e:
            logging.error(f"Errore nel recupero della versione di Firefox dal registro: {e}")
            pass
        paths = [
            Path('C:/Program Files/Mozilla Firefox/firefox.exe'),
            Path('C:/Program Files (x86)/Mozilla Firefox/firefox.exe')
        ]
        for p in paths:
            if p.exists():
                try:
                    vout = subprocess.check_output([str(p), '-v'], stderr=subprocess.STDOUT, encoding='utf-8', errors='replace').decode()
                    v = re.search(r'Firefox\s+([\d\.]+)', vout)
                    if v:
                        version = v.group(1)
                        logging.debug(f"Versione Firefox trovata tramite comando: {version}")
                        return version
                except Exception as e:
                    logging.error(f"Errore nel recupero della versione di Firefox tramite comando: {e}")
    elif system_os == 'Darwin':
        fp = '/Applications/Firefox.app/Contents/MacOS/firefox'
        if Path(fp).exists():
            try:
                vout = subprocess.check_output([fp, '-v'], stderr=subprocess.STDOUT, encoding='utf-8', errors='replace').decode()
                v = re.search(r'Firefox\s+([\d\.]+)', vout)
                if v:
                    version = v.group(1)
                    logging.debug(f"Versione Firefox trovata su macOS: {version}")
                    return version
            except Exception as e:
                logging.error(f"Errore nel recupero della versione di Firefox su macOS: {e}")
    elif system_os == 'Linux':
        try:
            vout = subprocess.check_output(['firefox', '-v'], stderr=subprocess.STDOUT, encoding='utf-8', errors='replace').decode()
            v = re.search(r'Firefox\s+([\d\.]+)', vout)
            if v:
                version = v.group(1)
                logging.debug(f"Versione Firefox trovata su Linux: {version}")
                return version
        except Exception as e:
            logging.error(f"Errore nel recupero della versione di Firefox su Linux: {e}")
    return None

def get_default_firefox_profile():
    system_os = platform.system()
    if system_os == 'Windows':
        base_dir = Path(os.environ['APPDATA']) / 'Mozilla' / 'Firefox'
    elif system_os == 'Darwin':
        base_dir = Path.home() / 'Library' / 'Application Support' / 'Firefox'
    else:
        base_dir = Path.home() / '.mozilla' / 'firefox'

    pi = base_dir / 'profiles.ini'
    if not pi.exists():
        logging.warning(f"profiles.ini non trovato in: {pi}")
        return None

    cp = configparser.ConfigParser()
    cp.read(pi)

    profiles = []
    for s in cp.sections():
        if s.startswith('Profile'):
            p = cp.get(s, 'Path', fallback=None)
            is_rel = cp.get(s, 'IsRelative', fallback='1')
            if p:
                if is_rel == '1':
                    p = base_dir / p
                else:
                    p = Path(p)
                profiles.append(p.resolve())

    for p in profiles:
        for lf in ['lock', '.parentlock']:
            if (p / lf).exists():
                logging.debug(f"Profilo Firefox bloccato trovato: {p}")
                return p

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
                logging.error(f"Errore nel leggere times.json per {p}: {e}")
                continue
    if last_used_profile:
        logging.debug(f"Ultimo profilo usato trovato: {last_used_profile}")
        return last_used_profile
    if profiles:
        logging.debug(f"Primo profilo trovato: {profiles[0]}")
        return profiles[0]
    return None

# ================================================================
# FUNZIONI DI SUPPORTO PER IL TEMA
# ================================================================
def is_dark_theme():
    theme = config['Settings'].get('theme', 'system')
    if theme == 'system':
        return darkdetect.isDark()
    elif theme == 'darkly':
        return True
    else:
        return False

# ================================================================
# FUNZIONI DI BACKUP
# ================================================================
def ask_backup_folder():
    top = Toplevel(root)
    top.title("Backup Completo - Selezione Cartella")
    top.resizable(False, False)

    # Applica l'icona e il tema alla finestra di backup
    try:
        if ICON_PATH:
            if platform.system() == 'Windows':
                top.iconbitmap(str(ICON_PATH.resolve()))
                logging.debug(f"Iconbitmap impostata con: {ICON_PATH.resolve()}")

                if ICON_PNG_PATH:
                    icon_image = tk.PhotoImage(file=str(ICON_PNG_PATH.resolve()))
                    top.iconphoto(False, icon_image)
                    top.icon_image = icon_image
                    logging.debug(f"Iconphoto impostata con: {ICON_PNG_PATH.resolve()}")

                set_taskbar_icon(top, str(ICON_PATH.resolve()))
            else:
                if ICON_PNG_PATH:
                    icon_image = tk.PhotoImage(file=str(ICON_PNG_PATH.resolve()))
                    top.iconphoto(True, icon_image)
                    top.icon_image = icon_image
                    logging.debug(f"Iconphoto impostata su macOS/Linux con: {ICON_PNG_PATH.resolve()}")
    except Exception as e:
        logging.error(f"Errore nel caricamento dell'icona nella finestra di backup: {e}")
        log_message([("❌ ", None), ("Errore nel caricamento dell'icona nella finestra di backup: ", None), (str(e), 'error')])

    apply_title_bar_theme(top, dark=is_dark_theme())

    frame = ttk.Frame(top, padding=10)
    frame.pack(fill="x", expand=True)

    lbl_base = ttk.Label(frame, text="Seleziona la cartella base dove creare il backup completo:")
    lbl_base.grid(row=0, column=0, columnspan=3, pady=5, sticky="w")

    base_var = StringVar()
    base_entry = ttk.Entry(frame, textvariable=base_var, width=50)
    base_entry.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

    def browse_base():
        f = filedialog.askdirectory(title="Seleziona cartella base per backup completo")
        if f:
            base_var.set(f)
    browse_base_btn = ttk.Button(frame, text="Sfoglia...", command=browse_base)
    browse_base_btn.grid(row=1, column=2, padx=5, pady=5)

    lbl_sub = ttk.Label(frame, text="Inserisci il nome della cartella di backup da creare:")
    lbl_sub.grid(row=2, column=0, columnspan=3, pady=5, sticky="w")

    sub_var = StringVar()
    sub_entry = ttk.Entry(frame, textvariable=sub_var, width=50)
    sub_entry.grid(row=3, column=0, columnspan=3, padx=5, pady=5, sticky="ew")

    chosen_dir = []

    def confirm():
        base = base_var.get().strip()
        subname = sub_var.get().strip()
        if not base or not subname:
            chosen_dir.append(None)
            top.destroy()
            return
        base_path = Path(base)
        if not base_path.exists():
            try:
                base_path.mkdir(parents=True, exist_ok=True)
                logging.debug(f"Cartella base creata: {base_path}")
            except Exception as e:
                log_message([("❌ ", None), ("Errore durante la creazione della cartella base: ", None), (str(e), 'error')])
                chosen_dir.append(None)
                top.destroy()
                return

        final_path = base_path / subname
        if not final_path.exists():
            try:
                final_path.mkdir(parents=True, exist_ok=True)
                logging.debug(f"Cartella di backup creata: {final_path}")
            except Exception as e:
                log_message([("❌ ", None), ("Errore durante la creazione della cartella di backup: ", None), (str(e), 'error')])
                chosen_dir.append(None)
                top.destroy()
                return
        chosen_dir.append(str(final_path))
        top.destroy()

    def cancel():
        chosen_dir.append(None)
        top.destroy()

    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=4, column=0, columnspan=3, pady=10)
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
    if chosen_dir:
        return chosen_dir[0]
    else:
        return None

def select_backup_destination():
    folder = ask_backup_folder()
    if folder:
        config['Settings']['backup_folder'] = folder
        save_configs(config)
        logging.debug(f"Backup folder impostata su: {folder}")
    return folder

def full_backup_folder():
    return config['Settings'].get('backup_folder', '')

def full_backup_exists():
    bf = full_backup_folder()
    if not bf:
        return None
    bf_path = Path(bf)
    if not bf_path.exists():
        return None
    backups = [d for d in bf_path.iterdir() if d.is_dir() and d.name.startswith("full_profile_backup_")]
    if backups:
        backups = sorted(backups, key=lambda x: x.stat().st_mtime, reverse=True)
        for old_b in backups[1:]:
            try:
                rmtree(old_b)
                logging.debug(f"Backup vecchio rimosso: {old_b}")
            except Exception as e:
                logging.error(f"Errore nella rimozione del backup vecchio {old_b}: {e}")
        return backups[0]
    return None

def close_firefox():
    system_os = platform.system()
    logging.debug(f"Chiusura di Firefox su: {system_os}")
    if system_os == 'Windows':
        subprocess.run(['taskkill', '/F', '/IM', 'firefox.exe'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, encoding='utf-8', errors='replace')
    else:
        subprocess.run(['pkill', 'firefox'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, encoding='utf-8', errors='replace')
    time.sleep(1)

def copy_tree(src, dst):
    if platform.system() == 'Windows':
        src_str = str(src.resolve())
        dst_str = str(dst.resolve())
        # Assicurati che il percorso di origine termini con un backslash per copiare il contenuto
        if not src_str.endswith('\\'):
            src_str += '\\'
        try:
            # /E per copiare tutte le sottocartelle, inclusi quelli vuoti
            # /COPYALL per copiare tutte le informazioni del file
            # /R:0 per nessun tentativo di ripetizione in caso di errore
            # /W:0 per nessun attesa tra i tentativi
            result = subprocess.run(
                ['robocopy', src_str, dst_str, '/E', '/COPYALL', '/R:0', '/W:0'],
                shell=True,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            logging.debug(f"Copiato con robocopy: {src_str} -> {dst_str}")
            logging.debug(f"Robocopy output: {result.stdout}")
            logging.debug(f"Robocopy exit code: {result.returncode}")
            if result.returncode >= 8:
                raise subprocess.CalledProcessError(result.returncode, 'robocopy', output=result.stdout, stderr=result.stderr)
        except subprocess.CalledProcessError as e:
            logging.error(f"Errore durante la copia con robocopy: {e}")
            raise
    else:
        if not dst.exists():
            dst.mkdir(parents=True)
            logging.debug(f"Cartella creata: {dst}")
        for item in src.iterdir():
            if item.is_dir():
                copy_tree(item, dst / item.name)
            else:
                try:
                    copy2(str(item.resolve()), str((dst / item.name).resolve()))
                    logging.debug(f"File copiato: {item} -> {dst}")
                except Exception as e:
                    logging.error(f"Errore nel copiare {item} a {dst}: {e}")

def remove_old_backup_if_older_than_days(backup_path, days=90):
    name = backup_path.name
    try:
        date_str = name.replace("full_profile_backup_", "")
        backup_date = datetime.strptime(date_str, "%Y-%m-%d_%H-%M-%S")
        if datetime.now() - backup_date > timedelta(days=days):
            rmtree(backup_path)
            logging.debug(f"Backup rimosso per scadenza: {backup_path}")
            return False
        return True
    except Exception as e:
        logging.error(f"Errore nel parsing della data del backup {backup_path}: {e}")
        try:
            rmtree(backup_path)
            logging.debug(f"Backup rimosso per errore di parsing: {backup_path}")
        except Exception as e2:
            logging.error(f"Errore nella rimozione del backup {backup_path}: {e2}")
        return False

def ensure_backup_folder_exists():
    bf = full_backup_folder()
    if not bf:
        return select_backup_destination()
    bf_path = Path(bf)
    if not bf_path.exists():
        return select_backup_destination()
    return bf

def create_full_backup(profile_path):
    bf = ensure_backup_folder_exists()
    if not bf:
        log_message([("⚠️ ", None), ("Operazione annullata dall'utente o nessuna cartella backup fornita.", None)])
        return False

    bf_path = Path(bf)
    if not bf_path.exists():
        try:
            bf_path.mkdir(parents=True, exist_ok=True)
            logging.debug(f"Cartella di backup creata: {bf_path}")
        except Exception as e:
            log_message([("❌ ", None), ("Errore durante la creazione della cartella di backup: ", None), (str(e), 'error')])
            return False

    close_firefox()
    log_message([("🗂️ ", None), ("Eseguo un backup completo del profilo...", None)])
    time.sleep(1)

    existing = [d for d in bf_path.iterdir() if d.is_dir() and d.name.startswith("full_profile_backup_")]
    for ex in existing:
        try:
            rmtree(ex)
            logging.debug(f"Backup vecchio rimosso: {ex}")
        except Exception as e:
            logging.error(f"Errore nella rimozione del backup vecchio {ex}: {e}")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    full_backup_subdir = bf_path / f"full_profile_backup_{timestamp}"
    try:
        log_message([("📥 ", None), ("Copio i file del profilo nel backup...", None)])
        time.sleep(1)
        copy_tree(profile_path, full_backup_subdir)
        log_message([("✅ ", None), ("Backup completo creato in: ", None), (str(full_backup_subdir), 'highlight')])
        return True
    except Exception as e:
        log_message([("❌ ", None), ("Errore durante il backup completo del profilo: ", None), (str(e), 'error')])
        return False

def manual_full_backup():
    clear_log()
    profile_path = Path(profile_entry.get())
    if not profile_path.exists():
        log_message([("❌ ", None), ("Il profilo specificato non esiste.", None)])
        schedule_return_to_main_info()
        return
    if create_full_backup(profile_path):
        log_message([("✅ ", None), ("Backup completo eseguito con successo.", None)])
    schedule_return_to_main_info()

def manual_change_backup_folder():
    clear_log()
    folder = select_backup_destination()
    if folder:
        log_message([("✅ ", None), ("Cartella di backup completo impostata su: ", None), (folder, 'highlight')])
    else:
        log_message([("⚠️ ", None), ("Operazione annullata dall'utente.", None)])
    schedule_return_to_main_info()

def restore_backup(profile_path):
    clear_log()
    log_message([("🔄 ", None), ("Seleziona un backup semplice da ripristinare...", None)])
    backup_to_restore = filedialog.askdirectory(title="Seleziona un backup da ripristinare")
    if backup_to_restore:
        log_message([("🔄 ", None), ("Ripristino in corso...", None)])
        time.sleep(1)
        for file_name in ["user.js"]:
            backup_file = Path(backup_to_restore) / file_name
            if backup_file.exists():
                try:
                    copy2(str(backup_file.resolve()), str((profile_path / file_name).resolve()))
                    log_message([("✅ ", None), (file_name, 'highlight'), (" ripristinato con successo.", None)])
                except Exception as e:
                    log_message([("❌ ", None), ("Errore durante il ripristino di ", None), (file_name, 'highlight'), (": ", None), (str(e), 'error')])
    else:
        log_message([("⚠️ ", None), ("Operazione di ripristino annullata.", None)])
    schedule_return_to_main_info()

def restart_firefox():
    log_message([("🔄 ", None), ("Riavvio di Firefox in corso...", None)])
    time.sleep(1)
    system_os = platform.system()
    try:
        if system_os == 'Windows':
            # Utilizzo cmd /c start per lanciare firefox
            subprocess.Popen(['cmd', '/c', 'start', 'firefox'], shell=True, encoding='utf-8', errors='replace')
        elif system_os == 'Darwin':
            subprocess.Popen(['/Applications/Firefox.app/Contents/MacOS/firefox'], encoding='utf-8', errors='replace')
        else:
            subprocess.Popen(['firefox'], encoding='utf-8', errors='replace')
        log_message([("✅ ", None), ("Firefox riavviato con successo.", None)])
    except Exception as e:
        log_message([("❌ ", None), ("Errore durante il riavvio di Firefox: ", None), (str(e), 'error')])

def download_userjs(profile_path, remote_content, remote_version):
    log_message([("📥 ", None), ("Scarico il file ", None), ("user.js", 'highlight'), (" aggiornato...", None)])
    time.sleep(1)
    try:
        userjs_path = profile_path / 'user.js'
        with open(userjs_path, 'w', encoding='utf-8') as uf:
            uf.write(remote_content)
        log_message([("✅ ", None), ("File ", None), ("user.js", 'highlight'), (" aggiornato e salvato in: ", None), (str(userjs_path), 'highlight')])
        return True
    except Exception as e:
        log_message([("❌ ", None), ("Errore durante il download di ", None), ("user.js", 'highlight'), (": ", None), (str(e), 'error')])
        return False

def run_update(profile_path):
    disable_buttons()
    threading.Thread(target=run_update_thread, args=(profile_path,), daemon=True).start()

def run_update_thread(profile_path):
    clear_log()
    profile_path = Path(profile_path)
    if not profile_path.exists():
        log_message([("❌ ", None), ("Il profilo specificato non esiste.", None)])
        schedule_return_to_main_info()
        return

    firefox_version = get_firefox_version(profile_path)
    local_version = get_local_version(profile_path)
    remote_version, remote_content = get_remote_version()
    last_update = get_github_last_update()

    if last_update:
        log_message([("🕒 ", None), ("Ultimo aggiornamento di Betterfox su GitHub: ", None), (last_update, 'highlight')])

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
        bf = full_backup_exists()
        if bf:
            still_valid = remove_old_backup_if_older_than_days(bf, 90)
            if not still_valid:
                if not create_full_backup(profile_path):
                    schedule_return_to_main_info()
                    return
        else:
            if not create_full_backup(profile_path):
                schedule_return_to_main_info()
                return

    if needs_install or needs_update:
        if remote_content:
            if download_userjs(profile_path, remote_content, remote_version):
                if local_version:
                    log_message([("🎉 ", None), ("Betterfox è stato aggiornato alla versione ", None), (f"v{remote_version}", 'highlight'), ("!", None)])
                else:
                    log_message([("🎉 ", None), ("Betterfox è stato installato con successo alla versione ", None), (f"v{remote_version}", 'highlight'), ("!", None)])
                restart_firefox()
            else:
                log_message([("❌ ", None), ("Impossibile aggiornare Betterfox: errore nel download di user.js", None)])
        else:
            log_message([("❌ ", None), ("Impossibile scaricare il contenuto di user.js. Operazione annullata.", None)])
    else:
        log_message([("✅ ", None), ("Betterfox è già aggiornato all'ultima versione.", None)])

    schedule_return_to_main_info()

# ================================================================
# FUNZIONI DI GESTIONE PROFILE PATH
# ================================================================
def save_profile_path(path):
    config['Settings']['profile_path'] = path
    save_configs(config)
    logging.debug(f"Profile path salvato: {path}")

def load_profile_path():
    return config['Settings'].get('profile_path', '')

def change_backup_folder():
    clear_log()
    folder = select_backup_destination()
    if folder:
        log_message([("✅ ", None), ("Cartella di backup completo impostata su: ", None), (folder, 'highlight')])
    else:
        log_message([("⚠️ ", None), ("Operazione annullata dall'utente.", None)])
    schedule_return_to_main_info()

def select_profile():
    profile_path = filedialog.askdirectory(title="Seleziona la cartella del profilo Firefox")
    if profile_path:
        profile_entry.delete(0, tk.END)
        profile_entry.insert(0, profile_path)
        save_profile_path(profile_path)
        log_message([("✅ ", None), ("Profilo selezionato con successo.", None)])
    else:
        log_message([("⚠️ ", None), ("Operazione annullata dall'utente.", None)])
    schedule_return_to_main_info()

def exit_app():
    on_closing()

# ================================================================
# FUNZIONI DI GESTIONE TEMA
# ================================================================
def set_theme(theme_name):
    if theme_name == 'system':
        if darkdetect.isDark():
            actual_theme = 'darkly'
        else:
            actual_theme = 'flatly'
    else:
        actual_theme = theme_name
    try:
        style.theme_use(actual_theme)
        logging.debug(f"Applicato tema: {actual_theme}")
    except tk.TclError as e:
        log_message([("❌ ", None), ("Tema selezionato non valido: ", None), (theme_name, 'error')])
        logging.error(f"Errore nell'applicare il tema {theme_name}: {e}")
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
    bg_color = style.colors.inputbg
    menubar.config(bg=bg_color)
    logging.debug(f"Menubar color impostato su: {bg_color}")

def update_colors_based_on_theme():
    theme = style.theme_use()
    if theme == "darkly":
        log_output.configure(bg=style.colors.inputbg, fg='white', insertbackground='white')
        footer.configure(foreground='white')
    else:
        log_output.configure(bg=style.colors.inputbg, fg='black', insertbackground='black')
        footer.configure(foreground='black')
    logging.debug(f"Colori aggiornati in base al tema: {theme}")

def disable_buttons():
    update_button.config(state='disabled')
    logging.debug("Bottoni disabilitati.")

def enable_buttons():
    update_button.config(state='normal')
    logging.debug("Bottoni abilitati.")

def on_closing():
    global after_id
    if after_id is not None:
        root.after_cancel(after_id)
        after_id = None
    root.destroy()
    logging.debug("Applicazione chiusa.")

def reload_info():
    clear_log()
    update_main_info()

# ================================================================
# FUNZIONI PER IMPOSTARE L'ICONA DEL TASKBAR E LA TITLE BAR
# ================================================================
def apply_title_bar_theme(window, dark):
    """
    Imposta il tema della title bar utilizzando le API di Windows tramite ctypes.
    """
    if platform.system() != 'Windows':
        return

    try:
        window.update_idletasks()  # Assicura che la finestra sia aggiornata
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(1 if dark else 0)
        dwmapi = ctypes.windll.dwmapi
        result = dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value)
        )
        if result != 0:
            raise Exception(f"DwmSetWindowAttribute fallito con codice {result}")
        logging.debug(f"Titolo barra tema impostato su: {'Scuro' if dark else 'Chiaro'}")
    except Exception as e:
        logging.error(f"Errore nell'applicazione del tema alla barra del titolo: {e}")
        log_message([("❌ ", None), ("Errore nell'applicazione del tema alla barra del titolo: ", None), (str(e), 'error')])

def set_taskbar_icon(window, icon_path):
    """
    Imposta l'icona della taskbar utilizzando le API di Windows tramite ctypes.
    """
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
            raise Exception("LoadImageW failed.")

        hwnd = window.winfo_id()
        # WM_SETICON small
        ctypes.windll.user32.SendMessageW(hwnd, 0x80, 0, hicon)
        # WM_SETICON big
        ctypes.windll.user32.SendMessageW(hwnd, 0x80, 1, hicon)
        logging.debug("Icona della taskbar impostata correttamente.")
    except Exception as e:
        logging.error(f"Errore nell'impostare l'icona della taskbar: {e}")
        log_message([("❌ ", None), ("Errore nell'impostare l'icona della taskbar: ", None), (str(e), 'error')])

# ================================================================
# AVVIO DELL'APP
# ================================================================
root = tk.Tk()
saved_theme = config['Settings'].get('theme', 'system')
if saved_theme == 'system':
    if darkdetect.isDark():
        theme_name = "darkly"
    else:
        theme_name = "flatly"
else:
    theme_name = saved_theme

style = Style(theme=theme_name)
root.title("Betterfox Updater")
root.geometry("600x500")
root.resizable(False, False)

# Applica l'icona
try:
    if ICON_PATH:
        if platform.system() == 'Windows':
            root.iconbitmap(str(ICON_PATH.resolve()))
            logging.debug(f"Iconbitmap impostata con: {ICON_PATH.resolve()}")

            if ICON_PNG_PATH:
                icon_image = tk.PhotoImage(file=str(ICON_PNG_PATH.resolve()))
                root.iconphoto(False, icon_image)
                root.icon_image = icon_image
                logging.debug(f"Iconphoto impostata con: {ICON_PNG_PATH.resolve()}")

            set_taskbar_icon(root, str(ICON_PATH.resolve()))
        else:
            if ICON_PNG_PATH:
                icon_image = tk.PhotoImage(file=str(ICON_PNG_PATH.resolve()))
                root.iconphoto(True, icon_image)
                root.icon_image = icon_image
                logging.debug(f"Iconphoto impostata su macOS/Linux con: {ICON_PNG_PATH.resolve()}")
    else:
        logging.warning("Icona non trovata in resources.")
        log_message([("⚠️ ", None), ("Nessuna icona trovata nella cartella resources.", None)])
except Exception as e:
    logging.error(f"Errore nel caricamento dell'icona: {e}")
    log_message([("❌ ", None), ("Errore nel caricamento dell'icona: ", None), (str(e), 'error')])

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

profile_frame = ttk.Frame(root, padding=10)
profile_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
profile_frame.columnconfigure(1, weight=1)

profile_label = ttk.Label(profile_frame, text="Cartella del profilo Firefox:")
profile_label.grid(row=0, column=0, sticky="e", pady=2, padx=5)

profile_entry = ttk.Entry(profile_frame, width=40)
profile_entry.grid(row=0, column=1, padx=5, sticky="ew", pady=2)

browse_button = ttk.Button(profile_frame, text="Sfoglia...", command=select_profile, takefocus=False)
browse_button.grid(row=0, column=2, padx=5, pady=2)

button_frame = ttk.Frame(profile_frame)
button_frame.grid(row=1, column=0, columnspan=3, pady=10)

update_button = ttk.Button(button_frame, text="Avvia Aggiornamento", command=lambda: run_update(profile_entry.get()), takefocus=False)
update_button.grid(row=0, column=0, padx=5)

style.configure('TButton', focusthickness=0)

log_frame = ttk.Frame(root, padding=10)
log_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
log_frame.columnconfigure(0, weight=1)
log_frame.rowconfigure(0, weight=1)

log_output = tk.Text(log_frame, wrap=tk.WORD, state='disabled', font=('Segoe UI', 10), spacing1=2, spacing2=2, spacing3=2, bd=0, highlightthickness=0)
log_output.grid(row=0, column=0, sticky="nsew")
log_output.tag_config('highlight', foreground=style.colors.primary, font=('Segoe UI', 10, 'bold'))
log_output.tag_config('error', foreground='red')

footer = ttk.Label(root, text="Betterfox Updater © 2025")
footer.grid(row=2, column=0, pady=5)

saved_path = config['Settings'].get('profile_path', '')
if saved_path and Path(saved_path).exists():
    profile_entry.insert(0, saved_path)
    logging.debug(f"Profilo Firefox caricato: {saved_path}")
else:
    default_profile_path = get_default_firefox_profile()
    if default_profile_path and default_profile_path.exists():
        profile_entry.insert(0, str(default_profile_path))
        config['Settings']['profile_path'] = str(default_profile_path)
        save_configs(config)
        log_message([("ℹ️ ", None), (f"Profilo di default: {default_profile_path}", 'highlight')])
        logging.debug(f"Profilo di default impostato: {default_profile_path}")

def update_main_info():
    profile_path = profile_entry.get()
    if profile_path:
        profile_path = Path(profile_path)
        if not profile_path.exists():
            log_message([("❌ ", None), ("Il profilo specificato non esiste.", None)], clear=True)
            logging.warning(f"Profilo non esistente: {profile_path}")
            return
        firefox_version = get_firefox_version(profile_path)
        clear_log()
        if firefox_version:
            log_message([("🦊 ", None), ("Versione di Firefox: ", None), (firefox_version, 'highlight')])
        else:
            log_message([("❌ ", None), ("Impossibile rilevare la versione di Firefox.", None)])
        local_version = get_local_version(profile_path)
        remote_version, remote_content = get_remote_version()
        last_update = get_github_last_update()

        if local_version:
            log_message([("💾 ", None), ("Versione Betterfox locale: ", None), (f"v{local_version}", 'highlight')])
        else:
            log_message([("💾 ", None), ("Betterfox non risulta installato nel tuo profilo.", None)])
        if remote_version:
            log_message([("🌐 ", None), ("Versione Betterfox remota: ", None), (f"v{remote_version}", 'highlight')])
        else:
            log_message([("🌐 ", None), ("Versione Betterfox remota: Non disponibile", 'error')])

        if last_update and last_update != "Data non disponibile":
            log_message([("🕒 ", None), ("Ultimo aggiornamento su GitHub: ", None), (last_update, 'highlight')])
        else:
            log_message([("🕒 ", None), ("Ultimo aggiornamento su GitHub: Non disponibile", 'error')])

def initialize_app():
    apply_title_bar_theme(root, dark=is_dark_theme())
    update_main_info()
    logging.debug("Applicazione inizializzata.")

root.after(0, initialize_app)
root.protocol("WM_DELETE_WINDOW", on_closing)
update_colors_based_on_theme()
root.mainloop()
