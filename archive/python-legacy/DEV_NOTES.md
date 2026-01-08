# Betterfox Updater - Legacy Dev Notes (Python)

Nota: documento legacy. Lo sviluppo attivo e in `app-electron/`.

## Stato attuale
- Stack: Python 3, PySide6 (Qt), requests, packaging.
- Entry UI/CLI: `app/main.py` (`python -m app`).
- Backend: `app/services/betterfox.py` (versioni, download, backup, retention).
- Build: `build_app.bat` (output in `release_app/BetterfoxUpdater.exe`).

## Comandi rapidi
- Dev: `python -m pip install -r requirements.txt` + `python -m app`
- CLI headless: `python -m app --update --profile <path> --backup <path> --no-backup --no-restart`
- Build: `build_app.bat`

## Percorsi utili
- Codice: `app/main.py`, `app/services/betterfox.py`
- Risorse: `app/resources/`
- Release: `release_app/BetterfoxUpdater.exe`
