# Betterfox Updater (Electron)

UI moderna per aggiornare `user.js` di Betterfox: controlla versione locale/remota, scarica l'ultima build, fa backup del profilo e segue il tema di sistema.

## Comandi principali
- Dev: `npm run dev` (Vite + Electron)
- Lint: `npm run lint`
- Build: `npm run build`  -> binari in `release/`

## Funzioni
- Versioni: locale, remoto, ultima data commit GitHub.
- Aggiorna `user.js` e logga l'esito; backup opzionale con retention.
- Rileva profili Firefox, scelta cartella backup, link rapidi a repo/changelog/release.
- Tema System/Light/Dark; icona app (taskbar/tray/start).

## Struttura
- `src/` React + theme CSS.
- `electron/` main + preload (IPC), icon.
- `public/` banner e asset statici.

## Note
- Chiudi Firefox prima di aggiornare o fare backup.
- Versione corrente: `1.0.0` (vedi changelog a repo root).
- Il percorso Python e legacy in `archive/python-legacy/`; lo sviluppo attivo e qui.
