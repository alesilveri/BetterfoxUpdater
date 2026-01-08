# Stato progetto

Stato: Cleanup e branding completati; CI/CD Electron pronto ma branch/commit e test locali bloccati da permessi Git e da npm (EPERM).

Fatto:
- Aggiunti template PR e issue (.github/).
- Tentati `npm ci` con `--no-audit --prefer-offline` (fallito per EPERM).

Decisioni:
- Release solo draft/prerelease (mai finali automatiche).
- Issue/PR template minimi per tenere il flusso ordinato.

Next:
- Sbloccare permessi su `.git/refs` per creare branch/commit/push/PR.
- Risolvere errore npm (EPERM spawn) e rieseguire `npm ci`, `npm run lint`, `npm run build`.
- Sostituire `docs/assets/screenshots/app.png` con screenshot reale.
