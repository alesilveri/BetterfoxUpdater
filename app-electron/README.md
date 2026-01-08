# Betterfox Updater (Electron)

App Electron personale per aggiornare `user.js` di Betterfox con backup e percorso guidato.

## Comandi principali
- Dev: `npm run dev`
- Lint: `npm run lint`
- Build: `npm run build` (binari in `release/`)

## Struttura
- `src/` React UI.
- `electron/` main + preload (IPC) + icon.
- `public/` asset statici (banner/icon).

## Note
- Versione sorgente: `package.json` e `app.getVersion()` in UI.
- Legacy Python in `archive/python-legacy/`.