# Betterfox Updater - Legacy Agent Notes (Python)

Nota: questo documento e legacy. Lo sviluppo attivo e in `app-electron/`.

## Stato rapido
- Stack: Python 3, PySide6, requests, packaging.
- Entry: `python -m app` (GUI) o `python -m app --update --profile <path> --backup <path>` (headless).
- Build: `build_app.bat` -> `release_app/BetterfoxUpdater.exe`.
- Config dati utente: `%LOCALAPPDATA%/BetterfoxUpdater/` (config.ini, error.log, backups/).

## Routine (ciclo breve)
1) Lint: `python -m py_compile app/main.py app/services/betterfox.py`.
2) Smoke: avvia GUI, testa controlli base (versioni, update, backup).
3) Aggiorna `CHANGELOG.md` e note interne se tocchi UI o build.

## Checklist release (legacy)
- Aggiorna versione in `app/main.py`.
- Aggiorna `CHANGELOG.md`.
- `build_app.bat` senza errori; prova l'exe.
