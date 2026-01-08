# Stato progetto

Stato: repo riallineata a Electron con documentazione e UI aggiornate; lint/build OK su branch `chore/session-2026-01-08`.

Fatto:
- Creati `docs/` + `AGENTS.md`, aggiunti asset base (banner/icon) e .editorconfig/.gitattributes/.gitignore aggiornati.
- UI guidata con step, stati (Pronto/In corso/Errore), versione app reale e log piu chiari.
- IPC aggiornato (getVersion, messaggi errori piu umani) e README/CHANGELOG riallineati.
- Test eseguiti: `npm run lint`, `npm run build`.

Problemi/Blocchi:
- Screenshot reale mancante in `docs/assets/screenshots/` (da catturare manualmente).

Decisioni:
- Release solo draft/prerelease (mai finali automatiche).

Next:
- Aggiungere screenshot reale app e aggiornare README.
- Verificare UX in-app su profili reali e backup con retention.