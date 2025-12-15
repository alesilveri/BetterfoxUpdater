# Betterfox Updater – Agent Playbook

Questa guida serve a non perdere il contesto tra sessioni e a mantenere l'app aggiornata e professionale.

## Stato rapido
- Stack: Python 3, PySide6, requests, packaging.
- Entry: `python -m app` (GUI) o `python -m app --update --profile <path> --backup <path>` (headless).
- Build: `build_app.bat` → `release_app/BetterfoxUpdater.exe`.
- Config dati utente: `%LOCALAPPDATA%/BetterfoxUpdater/` (config.ini, error.log, backups/).

## Routine (ciclo breve)
1) Pull/aggiorna repo locale (se git presente).  
2) Esegui lint veloce: `python -m py_compile app/main.py app/services/betterfox.py`.  
3) Run smoke: avvia GUI, testa “Controlla versioni”, “Aggiorna”, “Backup” con un profilo di test; verifica progress e tray.  
4) Se tocchi rete: prova “Test download” nella UI.  
5) Aggiorna `CHANGELOG.md` e `DEV_NOTES.md` per ogni modifica visibile.

## CI/CD
- `lint.yml`: py_compile su push/PR verso main.
- `windows-build.yml`: workflow_dispatch (manuale) per generare l’exe e caricarla come artifact.
- `release.yml`: workflow_dispatch con input `version` → build Windows + bozza release con exe allegata.

## Checklist release
- [ ] Aggiorna `APP_VERSION` in `app/main.py` (usa `python tools/bump_version.py <version>`).
- [ ] Aggiorna `CHANGELOG.md` voce nuova (lo script crea la sezione se manca).
- [ ] Aggiorna `requirements.txt` se lib nuove.
- [ ] `build_app.bat` senza errori; prova l'exe almeno una volta.
- [ ] Verifica icona `betterfox.ico` inclusa in `app/resources/`.
- [ ] Controlla che config/template siano allineati (`app/resources/config_template.ini`).

## Backlog attuale (riprendere da qui)
- Scheduler: task pianificata Windows per aggiornare Betterfox in automatico (UI toggle + CLI).
- Auto-update app: check `version.json` remoto + link release.
- Palette/accents custom e badge stato verde/ambra.
- Installer (NSIS/MSI) sopra l'exe PyInstaller.
- Opzioni rete avanzate: bypass cert, scelta branch Betterfox.

## Note operative
- Non rimuovere file in `archive/legacy/` (storia vecchio codice).
- Evita reset distruttivi; se serve pulizia, sposta in `archive/`.
- Mantieni ASCII nei file; commenti solo dove non ovvio.

## Comandi veloci
- Dev deps: `python -m pip install -r requirements.txt`
- GUI: `python -m app`
- CLI update: `python -m app --update --profile <path> --backup <path> --no-backup --no-restart`
- Build: `build_app.bat`
