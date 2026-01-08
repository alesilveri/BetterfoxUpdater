# Changelog

All notable changes to this project will be documented in this file.
The format is based on Keep a Changelog and this project adheres to Semantic Versioning.

## [Unreleased]
### Changed
- Icona legacy Betterfox ripristinata (app/tray/build) e banner leggero senza artefatti.
- UI piu leggera: hero con stato e progress, azioni e percorsi compatti, log con link essenziali.
- Tema System/Light/Dark ripulito; nome app allineato a "Betterfox Companion".
- Release pubblica sospesa finche l'app non parte senza schermo nero.

## [1.0.1]
### Changed
- Icona app rinfrescata (mint scuro) e banner riallineato con CTA visibile.
- Pulizia asset superflui e repo snellita (Python legacy archiviato).
- Patch versioning per rilasci successivi.

## [1.0.0]
### Added
- Nuova app Electron (React + Vite) con tema System/Light/Dark.
- Layout compatto: hero con status, azioni rapide, percorsi e backup essenziali.
- Fetch Betterfox robusto (user agent, ultima data commit GitHub) e write user.js con versione aggiornata.
- Icona app dedicata (BrowserWindow, build electron-builder) e banner per la repo.
- README aggiornato: Electron come percorso principale, Python segnato come legacy.
- Cleanup repo e .gitignore per output Node/Electron.

## [4.2.0]
### Added
- Controlli rete (proxy, timeout, retry) con test download integrato.
- Persistenza impostazioni migliorata (backup, compressione, auto-backup/riavvio).
- Script di build aggiornato per PyInstaller 6.17.
- About dialog, badge stato e controlli spazio libero prima dei backup.
- Utility rapide: apri profilo/user.js, pulisci log.

### Changed
- UI rinnovata con layout piu compatto e palette piu leggibile.

## [3.0.0]
### Added
- Nuova UI con layout a schede, status live e barra di avanzamento.
- Rilevamento profili Firefox migliorato e memorizzazione impostazioni.
- Backup completo prima dell'aggiornamento con compressione opzionale e pulizia automatica.
- Tema selezionabile (system/light/dark) e tray icon.

## [2.x]
### Added
- Retry HTTP, logging rotativo, rilevamento tema di sistema, gestione backup di base.
