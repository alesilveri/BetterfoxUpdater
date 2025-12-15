# Betterfox Updater - Changelog

## 4.2.0
- UI rinfrescata con hero card, badge di stato, pulsanti rapidi (cartella dati, release, changelog, repo Betterfox).
- Sezione rete dedicata: proxy configurabile, timeout e tentativi con applicazione live e test download.
- Persistenza impostazioni migliorata (backup, compressione, auto-backup/riavvio) e default cartella backup sotto dati app.
- Gestione percorsi più robusta (apri path solo se esiste) e log/ripristino palette invariato.
- Build/CLI invariati; versione applicazione aggiornata a 4.2.0.
- Aggiunta guida `AGENT.md` per mantenere contesto, routine e checklist release.
- Utilità rapide aggiuntive: apri profilo/user.js, pulisci log, la combo profili aggiorna il percorso selezionato.

## 3.0.0
- Nuova UI con layout a schede, status live e barra di avanzamento.
- Rilevamento profili Firefox migliorato, selezione rapida e memorizzazione impostazioni.
- Backup completo prima dell'aggiornamento con compressione opzionale e pulizia automatica.
- Controllo versioni remoto/locale, verifica rete e log thread-safe.
- Tema selezionabile (system/light/dark), icona app e percorso risorse compatibile con build freeze.

## Cronologia precedente (riassunto)
- Versioni 2.x: aggiunte retry HTTP, logging rotativo, rilevamento tema di sistema, gestione backup di base.
