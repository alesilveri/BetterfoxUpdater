# Betterfox Updater

![Betterfox Updater banner](docs/assets/banner.svg)

![CI](https://github.com/alesilveri/BetterfoxUpdater/actions/workflows/lint.yml/badge.svg)
![Windows Build](https://github.com/alesilveri/BetterfoxUpdater/actions/workflows/windows-build.yml/badge.svg)
![Release](https://github.com/alesilveri/BetterfoxUpdater/actions/workflows/release.yml/badge.svg)

App Electron personale per allineare `user.js` di Betterfox con backup sicuri e percorsi guidati.

## Download
- Vai nelle [Releases](https://github.com/alesilveri/BetterfoxUpdater/releases): trovi solo **draft** o **prerelease** (nessuna release finale automatica).

## Come si usa (3 step)
1) Seleziona il profilo Firefox.
2) Imposta la cartella backup (consigliato).
3) Esegui update e riavvia Firefox.

## Dev (Electron)
```bash
cd app-electron
npm ci
npm run dev
```

## Build
```bash
cd app-electron
npm run build
```

## Screenshot
![App screenshot](docs/assets/screenshots/app.png)

## Note importanti
- Progetto principale: `app-electron/`.
- Legacy Python archiviato in `archive/python-legacy/` (solo riferimento).

## Disclaimer
Betterfox Updater non e affiliato a Betterfox o Mozilla/Firefox.

## License
MIT
