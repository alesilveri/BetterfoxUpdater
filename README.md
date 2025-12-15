# Betterfox Updater (desktop app)

Aggiorna Betterfox (user.js) in un click, con backup di sicurezza e controlli di versione. Pensata per uso personale, semplice da usare, pronta al rilascio.

## Cosa fa (in breve)
- Scarica l’ultimo `user.js` Betterfox e mostra versione locale/remota/ultimo commit.
- Backup automatico del profilo (zip opzionale, retention) con avviso se lo spazio è poco.
- Riavvio Firefox opzionale dopo l’update.
- Tema System/Light/Dark, badge di stato colorati, tray con toast per esiti.
- Rete configurabile (proxy/timeout/retry) e test download integrato.
- Utility rapide: apri log, config, backup, profilo, `user.js`, cartella dati/release, pulisci log, About.
- Modalità headless: `python -m app --update --profile <path> --backup <path> [--no-backup] [--no-restart]`.

## Come si usa (GUI)
1. Avvia `python -m app` (oppure l’exe buildata).
2. Seleziona il profilo Firefox (rilevato automaticamente se possibile).
3. (Facoltativo) scegli cartella backup e opzioni (zip, retention).
4. Premi **Aggiorna**. Segui la barra di avanzamento e il badge di stato.

## Setup rapido (sviluppo)
```bash
python -m pip install -r requirements.txt
python -m app
```

## Build locale (exe Windows)
```bat
build_app.bat
```
Troverai `release_app/BetterfoxUpdater.exe` (usa l’icona se presente in `app/resources/betterfox.ico`).

## CI/CD già pronta
- `.github/workflows/lint.yml`: py_compile su push/PR.
- `.github/workflows/windows-build.yml`: workflow manuale → exe come artifact.
- `.github/workflows/release.yml`: workflow manuale con input `version` → bozza release con exe allegata.

## Dove salva i dati
- Config/log: `%LOCALAPPDATA%/BetterfoxUpdater/` (`config.ini`, `error.log`)
- Backup: `%LOCALAPPDATA%/BetterfoxUpdater/backups` (di default)
- Template config: `app/resources/config_template.ini`

## Strumenti
- `tools/bump_version.py <version> --title "nota"` aggiorna `APP_VERSION` e aggiunge la sezione al changelog.

## Backlog (idee vicine)
- Scheduler per aggiornamenti automatici (Attività pianificata).
- Auto-update app (check remoto e notifica).
- Installer NSIS/MSI sopra l’exe PyInstaller.
