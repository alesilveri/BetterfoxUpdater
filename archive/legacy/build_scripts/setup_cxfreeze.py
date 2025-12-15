import sys
import os
from cx_Freeze import setup, Executable

# -------------------------------------------------
# Configurazione Generale
# -------------------------------------------------
# Nome del progetto e versione
PROJECT_NAME = "ProjectA"  # Modifica con il nome del progetto
VERSION = "1.0"

# Percorsi
SRC_DIR = "src"
RESOURCES_DIR = "resources"

# Script principale
MAIN_SCRIPT = os.path.join(SRC_DIR, "main.py")  # Modifica se necessario

# Icona
ICON_PATH = os.path.join(RESOURCES_DIR, "icon.ico")  # Assicurati che esista

# Verifica che il main script esista
if not os.path.exists(MAIN_SCRIPT):
    raise FileNotFoundError(f"Lo script principale non esiste: {MAIN_SCRIPT}")

# Verifica che l'icona esista
if not os.path.exists(ICON_PATH):
    ICON_PATH = None  # Opzionale: Imposta a None se l'icona non esiste

# Opzioni di build
build_exe_options = {
    "packages": [
        "os", "sys", "logging", "requests", "pathlib", "shutil", "datetime",
        "tkinter", "re", "platform", "subprocess", "configparser", "time",
        "darkdetect", "ttkbootstrap", "threading", "ctypes", "json"
    ],
    "include_files": [
        (RESOURCES_DIR, "resources")  # Include la directory resources
    ],
    "include_msvcr": True,  # Include le DLL di Visual C++
    "excludes": [],  # Aggiungi pacchetti da escludere se necessario
    "optimize": 2,  # Livello di ottimizzazione
}

# Base dell'eseguibile
base = "Win32GUI" if sys.platform == "win32" else None

# Creazione dell'Executable
executables = [
    Executable(
        script=MAIN_SCRIPT,
        base=base,
        icon=ICON_PATH,
        target_name=f"{PROJECT_NAME}.exe"
    )
]

# Setup di cx-Freeze
setup(
    name=PROJECT_NAME,
    version=VERSION,
    description=f"{PROJECT_NAME} Application",
    options={"build_exe": build_exe_options},
    executables=executables
)
