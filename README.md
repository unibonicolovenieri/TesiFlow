# TesiFlow

**TesiFlow** è un metodo di lavoro, con la struttura di cartelle che lo supporta, per scrivere una tesi di laurea tecnica **a partire dal codice sorgente** di un progetto, con l'aiuto di un agente di programmazione (Claude Code).

L'idea: la tesi non si scrive "da zero", ma si deriva da tre fonti verificabili (codice, documentazione, requisiti), e l'agente lavora un capitolo alla volta tenendo un diario che gli permette di riprendere esattamente da dove si era fermato.

> È una tecnologia di supporto: non sostituisce il tuo sforzo. Le scelte, la revisione e la responsabilità del testo restano tue.

## Come nasce

TesiFlow è stato ricavato dal lavoro di stesura di una tesi magistrale in Ingegneria Informatica, scritta insieme all'agente a partire dalla codebase di un tirocinio aziendale. Questa repository contiene **solo la struttura e il metodo**, non il contenuto di quella tesi.

## Struttura di una cartella di lavoro

```
tesi/
├── CLAUDE.md              # Istruzioni di stesura: ruolo, registro, regole sulle fonti, procedura
├── STATO_TESI.md          # Diario di lavorazione: unica memoria tra una sessione e l'altra
├── main.tex               # Preambolo, frontespizio, ordine dei capitoli
├── Chapter1.tex ...       # Un file per capitolo
├── references.bib         # Bibliografia
├── figs/                  # Figure
├── DOCUMENTAZIONE/        # Fonte primaria di verità sul lavoro svolto
├── SourceCode/            # Copia in sola lettura del codice
├── Requirements/          # Requisiti / materiale forniti da azienda o ente
├── HINTS/                 # Tesi approvate di altri: solo struttura e stile
├── SLIDES/                # Scaletta per la discussione
└── .claude/
    ├── CLAUDE.md          # Mappa stabile della cartella
    └── contesto/          # Sintesi di supporto (mappa del codice, lavoro svolto)
```

| Elemento | Ruolo |
|---|---|
| `CLAUDE.md` | Contiene le variabili della tesi (candidato, titolo, argomento, relatore, lingua, pagine) e le regole: registro formale e impersonale, divieto di inventare, uso delle fonti, riservatezza. |
| `STATO_TESI.md` | Indice dei capitoli con il loro stato, fonti usate per ciascuno, decisioni prese, domande aperte, registro delle sessioni, prossimo passo. |
| `DOCUMENTAZIONE/` | Ogni affermazione tecnica della tesi deve essere verificabile qui. |
| `SourceCode/` | Consultato solo per dettagli che la documentazione non chiarisce. Mai modificato. |
| `Requirements/` | Base del capitolo sui requisiti e della validazione (requisito → componente → prova). |
| `HINTS/` | Riferimento per organizzazione, registro e livello di dettaglio. I contenuti non si riprendono. |
| `SLIDES/` | Scaletta per la discussione, riallineata man mano che i capitoli vengono scritti. |

## Flusso di lavoro

1. **Preparazione.** Si compilano le variabili in `CLAUDE.md` e si copiano nelle cartelle codice, documentazione, requisiti e tesi di riferimento.
2. **Ricognizione.** L'agente mappa il progetto LaTeX, riassume i documenti, numera i requisiti (R1, R2, ...), estrae lo schema dei capitoli dagli `HINTS/` e propone un indice ragionato. Si procede solo dopo la conferma dell'utente.
3. **Un capitolo alla volta.** Per ciascun capitolo:
   - **scaletta**: fonti, requisiti toccati, domanda a cui risponde, sezioni;
   - **stesura** nel relativo `.tex`;
   - **verifica**: compilazione, riferimenti e citazioni risolti, nessun segnaposto, ogni affermazione riconducibile a una fonte;
   - **aggiornamento** di `STATO_TESI.md`;
   - **riscontro dell'utente** prima del capitolo successivo.
4. **Revisione.** Un capitolo approvato dal relatore si tratta in modo conservativo: si propone, non si riscrive.
5. **Discussione.** Le slide si derivano dai capitoli già scritti, con la fonte di ogni affermazione.

## Principi

- **Niente contenuto inventato.** Dati mancanti e riferimenti incerti diventano `TODO` e domande aperte, non testo plausibile.
- **Fonti separate per ruolo.** Codice e documentazione per il contenuto; requisiti per motivare e validare; tesi di riferimento solo per la forma.
- **Contributo personale esplicito.** Si distingue sempre ciò che esisteva da ciò che è stato realizzato.
- **Continuità tra sessioni.** Tutto ciò che non è nel file di stato è perso: lo si aggiorna dopo ogni unità di lavoro.
- **Riservatezza.** Eventuali vincoli aziendali (nomi interni, codice) si scrivono nelle regole e valgono per tesi e slide.
- **Consegna portabile.** I capitoli non dipendono da modifiche al preambolo né da pacchetti non standard, per compilare anche su Overleaf.

## Lo strumento `tesiflow` (CLI)

Automatizza la preparazione del workspace descritto sopra: scheletro LaTeX, istruzioni per l'agente e informazioni sul codice sorgente. La ricerca semantica (RAG) sul codice **non è inclusa**: chi ne ha bisogno può collegare lo strumento più adatto al proprio modello; nel frattempo l'agente usa la mappa statica del codice.

### Installazione

```bash
pipx install .            # oppure: pip install -e . in un ambiente virtuale (Python 3.11+)
```

**LaTeX in locale (obbligatorio per compilare).** `tesiflow init`, `doctor` e `build` verificano che siano presenti `latexmk`, `pdflatex`, `bibtex`, `makeindex` e i pacchetti usati dallo scheletro, e in caso contrario spiegano come installarli:

- macOS: `brew install --cask mactex-no-gui` (poi riapri il terminale)
- Debian/Ubuntu: `sudo apt install latexmk texlive-latex-extra texlive-fonts-recommended texlive-lang-italian texlive-science`

### Comandi

| Comando | Cosa fa |
|---|---|
| `tesiflow init <nome>` | Crea il workspace (interattivo, oppure con flag / `--config file.yaml` / `-y`), copia il codice in `SourceCode/` senza `.git` né artefatti (rispetta `.gitignore`), genera LaTeX, `CLAUDE.md`, `STATO_TESI.md`, istruzioni per capitolo, comandi `/ricognizione`, `/scaletta`, `/scrivi`, `/verifica`, `/revisione`, `/slide`, mappa del codice, repo git. Rieseguirlo non sovrascrive nulla. |
| `tesiflow build [--clean] [-v]` | `latexmk -pdf` + riepilogo di errori (con file:riga), riferimenti e citazioni non risolti, warning, `TODO` rimasti. |
| `tesiflow doctor` | Controlla compilatore LaTeX, variabili, cartelle, file mancanti, `CLAUDE.md`/frontespizio allineati a `tesiflow.yaml`, riservatezza, `SourceCode/`, istruzioni con campi TODO. |
| `tesiflow sync` | Riallinea `SourceCode/` alla sorgente originale, segnala le differenze in `STATO_TESI.md`, aggiorna la mappa. |
| `tesiflow map` | Rigenera `.claude/contesto/mappa-codebase.md` (linguaggi, alberatura, punti d'ingresso, dipendenze, simboli con righe). |
| `tesiflow instructions show / edit / profile <nome> / profiles` | Modifica guidata di registro, dettaglio, lunghezza, riservatezza e regole aggiuntive, senza editare il markdown. Rigenera `CLAUDE.md` conservando il blocco «Regole personalizzate». |
| `tesiflow regen` | Riallinea `CLAUDE.md` e frontespizio (blocco `TESIFLOW:META` di `main.tex`) a `tesiflow.yaml` e ricrea i file mancanti, senza toccare i capitoli. |

Profili disponibili: `triennale`, `magistrale`, `aziendale-riservato`. File modificati a mano e poi rigenerati vengono salvati prima in `.tesiflow/backup/`. `SourceCode/` è reso di sola lettura.

### Sviluppo

```bash
python3 -m venv .venv && .venv/bin/pip install -e . pytest && .venv/bin/pytest
```

## Requisiti

- [Claude Code](https://claude.com/claude-code)
- Una distribuzione LaTeX (`latexmk`, `pdflatex`, `bibtex`) oppure Overleaf
- Git, consigliato: un commit a fine di ogni blocco di lavoro

## Come iniziare

1. Copia la struttura di cartelle in una nuova directory e inizializza un repository git.
2. Compila le variabili in `CLAUDE.md`.
3. Inserisci codice, documentazione e requisiti nelle rispettive cartelle.
4. Avvia Claude Code nella cartella: la prima sessione parte dalla ricognizione.
