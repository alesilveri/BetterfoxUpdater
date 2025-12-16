# Betterfox Updater - Changelog

## 0.1.0 (Electron)
- Nuova app Electron (React + Vite) con tema System/Light/Dark e palette dark pi├╣ profonda.
- Layout compatto: hero con status, azioni rapide, percorsi/backup essenziali, log e link rapidi senza spazi vuoti.
- Fetch Betterfox robusto (user agent, ultima data commit GitHub) e write user.js con versione aggiornata.
- Icona app dedicata (BrowserWindow, build electron-builder) e banner per la repo.
- README aggiornato: Electron come percorso principale, Python segnato come legacy.
- Cleanup repo e .gitignore per output Node/Electron.

## 4.2.0
- UI rinfrescata con hero card, badge di stato, pulsanti rapidi (cartella dati, release, changelog, repo Betterfox).
- Sezione rete dedicata: proxy configurabile, timeout e tentativi con applicazione live e test download.
- Persistenza impostazioni migliorata (backup, compressione, auto-backup/riavvio) e default cartella backup sotto dati app.
- Gestione percorsi più robusta (apri path solo se esiste) e log/ripristino palette invariato.
- Build/CLI invariati; versione applicazione aggiornata a 4.2.0.
- Aggiunta guida `AGENT.md` per mantenere contesto, routine e checklist release.
- Utilità rapide aggiuntive: apri profilo/user.js, pulisci log, la combo profili aggiorna il percorso selezionato.
- About dialog in UI e badge stato colorato; controllo spazio libero prima dei backup con log di warning.
- Script di build aggiornato per PyInstaller 6.17 (percorsi `--add-data` corretti) e build one-file verificata in `release_app/`.
- Fix crash all’avvio: l’area log ora è inizializzata prima dei pulsanti utilità (clear log).
- UI rinnovata (tab base/avanzate compatti), pulsanti con icone native, chip per versioni, palette più leggibile e log compatto.
- Layout ridisegnato: colonne base (azioni+percorsi+preferenze a sinistra, log/progress a destra) per evitare tagli e spazi vuoti su finestre piccole.
- Spaziatura affinata (log più alto, progress sottile, form più stretto) e palette charcoal/mint con bordi soft per una lettura più chiara.

## 3.0.0
- Nuova UI con layout a schede, status live e barra di avanzamento.
- Rilevamento profili Firefox migliorato, selezione rapida e memorizzazione impostazioni.
- Backup completo prima dell'aggiornamento con compressione opzionale e pulizia automatica.
- Controllo versioni remoto/locale, verifica rete e log thread-safe.
- Tema selezionabile (system/light/dark), icona app e percorso risorse compatibile con build freeze.

## Cronologia precedente (riassunto)
- Versioni 2.x: aggiunte retry HTTP, logging rotativo, rilevamento tema di sistema, gestione backup di base.
