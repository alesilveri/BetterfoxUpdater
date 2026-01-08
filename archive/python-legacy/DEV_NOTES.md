# Betterfox Updater – Dev Notes

## Stato attuale
- Stack: Python 3, PySide6 (Qt), requests, packaging.
- Entry UI/CLI: `app/main.py` (`python -m app`).
- Backend: `app/services/betterfox.py` (versioni, download con progress, backup zip+retention, chiusura/riavvio Firefox, tray toast, rete configurabile).
- UI: hero card + pulsanti rapidi (repo Betterfox, changelog), sezione rete (proxy/timeout/retry + test), badge stato, tema System/Light/Dark.
- Risorse: `app/resources/` (usa `betterfox.ico` se presente, `config_template.ini` come base).
- Build: `build_app.bat` (ricrea venv, output in `release_app/BetterfoxUpdater.exe`, log eventuali in `build_log.txt`).
- Legacy: `archive/legacy/` (vecchi script e codice).
- Config/log runtime: `%LOCALAPPDATA%/BetterfoxUpdater/config.ini` e `error.log` (default backup in `backups/` sotto la stessa cartella dati).

## Comandi rapidi
- Dev: `python -m pip install -r requirements.txt` → `python -m app`
- CLI headless: `python -m app --update --profile <path> --backup <path> --no-backup --no-restart`
- Build: `build_app.bat` (step verbosi; serve internet per installare PySide6).

## Funzioni chiave
- Tema System/Light/Dark con palette applicata all’avvio.
- Download user.js in streaming con progress bar deterministica.
- Tray icon (Mostra/Esci) e toast su [ok]/[err].
- Pulsanti utilità: apri log/config/backup/cartella dati/cartella release.
- Toggle auto-restart Firefox e auto-backup, compressione backup, retention configurabile.
- Rete configurabile (proxy, timeout, retry) con test download integrato.

## Idee backlog (da valutare/implementare)
- Scheduler: crea/rimuovi Attività Pianificata per check/update.
- Auto-check update app (version.json + link release) + notifica.
- Palette/accents custom e badge stato (verde/ambra) legati all’esito update.
- Modalità installer (MSI/NSIS) sopra l’exe.
- UI per scelta server Betterfox (branch) e opzioni rete avanzate (no-certificate, ecc).

## Per riprendere il filo
Vedi `AGENT.md` per routine, checklist release e backlog corrente.

## Note su build
- `build_app.bat` ricrea sempre la venv; PySide6 è pesante, lascia terminare il comando.
- Se fallisce, controlla `build_log.txt`.

## Percorsi utili
- Codice: `app/main.py`, `app/services/betterfox.py`
- Risorse: `app/resources/`
- Release: `release_app/BetterfoxUpdater.exe`
