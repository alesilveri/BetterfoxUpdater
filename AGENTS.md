# Betterfox Updater — AGENTS

## Scopo e disclaimer
Betterfox Updater e una app Electron personale per aggiornare il file `user.js` di Betterfox con backup e controlli rapidi.
Non e affiliata a Betterfox o Mozilla/Firefox.

## Struttura cartelle
- `app-electron/` — progetto principale (Electron + React).
- `archive/python-legacy/` — versione Python legacy (solo riferimento).
- `archive/legacy/` — prototipi e script storici.
- `docs/` — documentazione, stato e asset.

## Comandi dev/build/test (Electron)
```bash
cd app-electron
npm ci
npm run dev
npm run lint
npm run build
```

## Convenzioni commit (Conventional Commits)
- Formato: `type(scope): messaggio`
- Tipi: `feat`, `fix`, `chore`, `docs`, `refactor`, `style`, `test`, `build`, `ci`

## Flusso release (solo draft/prerelease)
- CI: lint su PR/push.
- Build Windows: workflow manuale che produce artifact.
- Release: workflow manuale (eventualmente su tag `vX.Y.Z`) che crea **solo** draft o prerelease.
- Regola ferrea: **mai** pubblicare release finali automaticamente.

## Decision log (sintetico)
- 2025-12-22: Avvio pulizia repo, Electron come percorso principale.
- 2025-12-22: Aggiunti AGENTS/STATE, .editorconfig, .gitattributes e .gitignore aggiornato.
- 2025-12-22: Workflow GitHub Actions migrati su Electron (lint, build, release draft/prerelease).
- 2025-12-22: Branding aggiornato con nuovi asset in `docs/assets/` e icone app allineate.
- 2025-12-22: README prodotto + LICENSE MIT + CHANGELOG in stile Keep a Changelog.
- 2025-12-22: UI piu compatta con stati chiari, percorso guidato e versione app reale.
- 2025-12-22: Aggiunti template per PR e issue per rendere il flusso piu consistente.
