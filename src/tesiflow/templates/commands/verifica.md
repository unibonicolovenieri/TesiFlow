---
description: Verifica di un capitolo
argument-hint: <capitolo>
---

Verifica il capitolo `$ARGUMENTS`.

1. Esegui `tesiflow build` e riporta errori, warning, riferimenti non risolti e `TODO` rimasti.
2. Controlla che ogni affermazione tecnica sia riconducibile a `DOCUMENTAZIONE/`, `SourceCode/` o `Requirements/`; elenca quelle senza fonte.
3. Controlla: figure introdotte nel testo, scelte con motivazione e alternative, risultati con numeri e limiti, contributo personale esplicito, riservatezza.
4. Non riscrivere: produci un elenco di problemi con posizione. Se tutto è a posto, imposta lo stato a «verificato» in `STATO_TESI.md`.
