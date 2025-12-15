# Betterfox Updater

Applicazione desktop (PySide6) per aggiornare Betterfox (user.js) con backup automatico, controllo versioni e modalità headless. CI/CD GitHub già pronta con build Windows e release draft.

## Funzioni
- UI moderna con tema System/Light/Dark, hero card e badge di stato colorato.
- Download user.js con barra di avanzamento, check versioni locale/remota/GitHub commit.
- Backup profilo con zip opzionale, retention, controllo spazio libero e riavvio Firefox facoltativo.
- Sezione rete: proxy, timeout, retry, test download integrato.
- Tray icon (Mostra/Esci) e toast per successi/errori.
- Pulsanti rapidi: apri log/config/backup/profilo/user.js/cartella dati/release, pulisci log, About.
- CLI headless: `python -m app --update --profile <path> --backup <path> --no-backup --no-restart`.

## Requisiti
- Python 3.10+ su Windows (per l exe serve solo Windows).

## Setup sviluppo
```bash
python -m pip install -r requirements.txt
python -m app
```

## Build locale (exe)
Su Windows:
```bat
build_app.bat
```
Output: `release_app/BetterfoxUpdater.exe` (icona inclusa se presente in `app/resources/betterfox.ico`).

## CI/CD
- `.github/workflows/lint.yml`: py_compile su push/PR verso main.
- `.github/workflows/windows-build.yml`: manuale (workflow_dispatch), genera exe e artifact.
- `.github/workflows/release.yml`: manuale con input `version`, builda su Windows e crea bozza di release con exe allegata.

## Config e dati runtime
- `%LOCALAPPDATA%/BetterfoxUpdater/config.ini` e `error.log`
- Backup di default in `%LOCALAPPDATA%/BetterfoxUpdater/backups`
- Template config: `app/resources/config_template.ini`

## Script utili
- `tools/bump_version.py <version> --title "nota"`: aggiorna `APP_VERSION` e crea sezione changelog se manca.

## Note design
UI PySide6 con palette Fusion custom, badge di stato colorato e utilità rapide. Grafica minimale ma leggibile; pronta a skin personalizzata se serve.

## Backlog breve
- Scheduler (attività pianificata) per aggiornamenti automatici.
- Auto-update app (check versione json remoto + notifica) e palette/accents custom.
- Installer NSIS/MSI sopra l exe PyInstaller.
```