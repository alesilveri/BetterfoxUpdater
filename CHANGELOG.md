# Changelog

All notable changes to this project will be documented in this file.
This project follows Keep a Changelog and Semantic Versioning.

## [Unreleased]
### Added
- Percorso guidato con step chiari e stato riavvio Firefox.
- Badge versione app reale (da `app.getVersion()`).
- `docs/` con asset, `AGENTS.md` e `docs/STATE.md` allineati.

### Changed
- UI piu guidata con stati (Pronto/In corso/Errore) e log piu leggibili.
- Tipografia e tema rifiniti con accento teal/cyan.
- README aggiornato in stile prodotto personale e disclaimer esplicito.

## [1.0.1]
### Changed
- Icona app rinfrescata (mint scuro) e banner riallineato.
- Pulizia asset superflui e repo snellita (Python legacy archiviato).
- Patch versioning per rilasci successivi.

## [1.0.0]
### Added
- Nuova app Electron (React + Vite) con tema System/Light/Dark.
- Layout compatto: hero con status, azioni rapide, percorsi/backup essenziali, log e link rapidi.
- Fetch Betterfox robusto (user agent, ultima data commit GitHub) e write user.js con versione aggiornata.
- Icona app dedicata (BrowserWindow, build electron-builder) e banner per la repo.
- README aggiornato: Electron come percorso principale, Python segnato come legacy.

## [4.2.0]
### Added
- UI rinfrescata con hero card, badge di stato, pulsanti rapidi e link Betterfox.
- Sezione rete con proxy/timeout/tentativi e test download.
- Persistenza impostazioni migliorata (backup, compressione, auto-backup/riavvio).
- About dialog e badge stato colorato.

### Fixed
- Crash all'avvio: area log inizializzata prima dei pulsanti utility.

## [3.0.0]
### Added
- Nuova UI con layout a schede, status live e barra di avanzamento.
- Rilevamento profili Firefox migliorato, selezione rapida e memorizzazione impostazioni.
- Backup completo prima dell'aggiornamento con pulizia automatica.

## [2.x]
### Added
- Retry HTTP, logging rotativo, rilevamento tema di sistema e gestione backup di base.