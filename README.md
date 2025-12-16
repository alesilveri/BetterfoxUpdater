# Betterfox Updater

![banner](app-electron/public/banner.svg)

App desktop (Electron + React) per tenere `user.js` di Betterfox sempre allineato: UI compatta, backup sicuri, percorsi chiari. Tema System/Light/Dark, icona dedicata (Start menu/Taskbar/Tray) e banner aggiornato.

## Cosa c'e dentro
- Controllo versioni: locale, remoto e ultima data commit Betterfox.
- Aggiorna `user.js` con backup automatico opzionale e retention giorni.
- Rilevamento profili Firefox, scelta cartella backup, link rapidi a repo/changelog/release.
- Tema System/Light/Dark, log leggibile, azioni rapide senza fronzoli.

## Uso rapido
1) `cd app-electron && npm install`  
2) Dev: `npm run dev` (parte Vite + Electron)  
3) In app: scegli profilo Firefox, cartella backup, premi **Aggiorna Betterfox**.  

## Build
```bash
cd app-electron
npm run build
```
Trovi i binari in `app-electron/release/` (configurato con electron-builder).

## Versioni e release
- Versione Electron corrente: `1.0.0` (vedi `CHANGELOG.md`).
- Per ora niente release pubblica: testiamo in locale (`npm run dev` / `npm run build`) finche tutto gira senza schermo nero.
- Il canale Python e legacy in `archive/python-legacy/` (tenuto solo come riferimento).

## Note
- Richiede Firefox chiuso per copiare/scrivere `user.js`.
- I dati (config/log) sono gestiti da Electron; i backup restano dove li imposti tu.
- Progetto personale: UI pensata per essere semplice, niente funzioni superflue. Titoli e testi sono chiari per chi non e tecnico.
