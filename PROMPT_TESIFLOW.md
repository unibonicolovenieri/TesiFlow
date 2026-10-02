# Prompt: costruire TesiFlow

## Ruolo

Sei un ingegnere software senior. Devi progettare e realizzare **TesiFlow**, uno strumento (CLI, con eventuale interfaccia web locale in una seconda fase) che permette di ottenere la **stesura completa di una tesi in LaTeX a partire da una code base**, lavorando insieme a un agente di programmazione (Claude Code o equivalente).

Il file `README.md` di questa repository descrive già il metodo e la struttura di cartelle: va rispettato ed esteso, non contraddetto.

## Obiettivo

Lo strumento deve offrire quattro funzioni principali:

1. **Creazione del workspace** di tesi, con dentro la code base su cui è stato svolto il lavoro.
2. **Scheletro LaTeX completo** della tesi, pronto da compilare.
3. **Sistema di istruzioni per l'agente** che scrive (file `CLAUDE.md`, file di stato, regole, procedura).
4. **RAG sulla code base**, per interrogare il codice senza doverlo rileggere ogni volta.

## 1. Creazione del workspace

Comando: `tesiflow init <nome-tesi>`

- Chiede (in modo interattivo, o tramite flag/file `tesiflow.yaml`) le variabili della tesi: candidato, titolo, argomento, azienda/ente, ateneo, relatore, correlatore, anno accademico, lingua, pagine target, eventuali vincoli di riservatezza.
- Chiede la sorgente della code base: percorso locale, URL git, oppure archivio (`.zip`, `.tar.*`). Il codice viene copiato (o clonato) in `SourceCode/`, **senza `.git` annidato e senza artefatti di build** (`node_modules`, `build`, `dist`, `__pycache__`, binari, ecc.; rispettare `.gitignore` e un elenco di esclusioni configurabile).
- `SourceCode/` è **di sola lettura per l'agente**: mai modificato. Se il codice cambia, esiste `tesiflow sync` per riallinearlo e segnalare in `STATO_TESI.md` cosa è cambiato.
- Crea la struttura di cartelle seguente e inizializza un repository git:

```
<nome-tesi>/
├── tesiflow.yaml          # Configurazione e variabili della tesi
├── CLAUDE.md              # Istruzioni di stesura per l'agente (generato dal template)
├── STATO_TESI.md          # Diario di lavorazione: unica memoria tra sessioni
├── main.tex               # Preambolo, frontespizio, ordine dei capitoli
├── Abstract_It.tex / Abstract_Eng.tex
├── Acknowledgment.tex, Dedica.tex, Nomenclature.tex
├── Chapter1.tex ... ChapterN.tex, Conclusion.tex
├── references.bib
├── .latexmkrc
├── figs/
├── DOCUMENTAZIONE/        # Fonte primaria di verità sul lavoro svolto
├── SourceCode/            # Copia in sola lettura della code base
├── Requirements/          # Requisiti / materiale di azienda o ente
├── HINTS/                 # Tesi di riferimento: solo struttura e stile
├── SLIDES/                # Scaletta per la discussione
└── .claude/
    ├── CLAUDE.md          # Mappa stabile della cartella
    ├── contesto/          # mappa-codebase.md, lavoro-svolto.md
    └── rag/               # Indice RAG (vedi sezione 4), escluso da git
```

## 2. Scheletro LaTeX

Prendere come modello la tesi di riferimento (`newdir/Tesi_Venieri_Nicolò`, già usata come fonte di ispirazione):

- `main.tex` con classe `book` (11pt, a4paper, twoside), `babel` (lingua principale + inglese per l'abstract), `geometry` con margini 25 mm, interlinea 1.5, `lmodern`, `microtype`, pacchetti per matematica, grafica (`graphicx`, `subcaption`, `tikz`), tabelle (`booktabs`), listati (`listings`), bibliografia, indici (`toc`, `lof`, `lot`, nomenclatura).
- Ordine: frontespizio, dedica, ringraziamenti, abstract (lingua + inglese), indici, capitoli, conclusioni, bibliografia.
- Frontespizio compilato automaticamente dalle variabili di `tesiflow.yaml`.
- Capitoli generati come **file separati** con un segnaposto minimo (titolo + commento sullo scopo), con elenco predefinito modificabile: Introduzione, Contesto e stato dell'arte, Requisiti e analisi, Progettazione/Architettura, Implementazione, Validazione e risultati, Conclusioni.
- I capitoli **non devono dipendere da modifiche al preambolo né da pacchetti non standard**, per compilare anche su Overleaf.
- Comando `tesiflow build` (wrapper di `latexmk -pdf`) che compila e riassume errori, warning, riferimenti non risolti e `TODO` rimasti.

## 3. Sistema di istruzioni per l'agente

Il cuore del metodo. Lo strumento genera da template (con le variabili sostituite) e mantiene questi file:

### `CLAUDE.md` (radice)

Sezioni obbligatorie, sul modello di quello della tesi di riferimento:

- **Variabili** (`{CANDIDATO}`, `{TITOLO_TESI}`, `{ARGOMENTO}`, `{AZIENDA}`, `{ATENEO}`, `{RELATORE}`, `{CORRELATORE}`, `{ANNO_ACCADEMICO}`, `{PAGINE_TARGET}`, `{LINGUA}`).
- **Ruolo**: ingegnere senior e correlatore accademico; registro formale e impersonale; termini tecnici standard non tradotti.
- **Ruolo di ogni cartella e regole sulle fonti**: `DOCUMENTAZIONE/` per il contenuto, `SourceCode/` solo per dettagli non chiariti dalla documentazione, `Requirements/` per motivare e validare, `HINTS/` solo per forma e stile (mai contenuti).
- **Procedura di lavoro**: all'avvio leggere per intero `STATO_TESI.md` e riassumere in due righe; ricognizione iniziale se non fatta; poi un capitolo alla volta con scaletta → stesura → verifica (compilazione, riferimenti, nessun segnaposto, ogni affermazione riconducibile a una fonte) → aggiornamento dello stato → riscontro dell'utente.
- **Regole di contenuto**: apertura e raccordo di ogni capitolo; titoli descrittivi; figure introdotte nel testo; tabelle al posto di lunghi elenchi; listati brevi; scelte progettuali con motivazione e alternative scartate; risultati con numeri, condizioni e limiti.
- **Divieti**: niente contenuto inventato; dati mancanti e riferimenti incerti diventano `TODO` e "Domande aperte"; bibliografia solo con riferimenti certi, altrimenti `\cite{TODO-...}`.
- **Contributo personale esplicito**: distinguere ciò che esisteva da ciò che è stato realizzato.
- **Riservatezza**: vincoli aziendali validi per tesi e slide.
- **Uso del RAG**: prima di aprire file di `SourceCode/`, interrogare l'indice con `tesiflow ask` / `tesiflow search`; citare sempre i percorsi e le righe restituiti.
- **Continuità tra sessioni**: regole di aggiornamento di `STATO_TESI.md` (sezione "In corso" prima delle operazioni lunghe, aggiornamento dopo ogni unità di lavoro, chiusura sessione con "Prossimo passo suggerito").

### `STATO_TESI.md`

Template con sezioni: In corso · Ricognizione iniziale · Indice concordato e stato dei capitoli (da fare / scaletta approvata / bozza scritta / verificato / revisionato) · Fonti usate per capitolo · Decisioni prese con l'utente · Modifiche allo scheletro LaTeX · Domande aperte · Registro delle sessioni.

### Gestione delle istruzioni

Un sistema apposito per **definire e modificare le istruzioni dell'agente** senza editare a mano il markdown:

- `tesiflow instructions edit`: modifica guidata di registro, lingua, vincoli di riservatezza, livello di dettaglio, lunghezza, regole aggiuntive; rigenera `CLAUDE.md` mantenendo le parti personalizzate.
- **Istruzioni per capitolo**: file `instructions/ChapterN.md` (scopo, fonti da usare, requisiti toccati, vincoli, lunghezza) richiamato dalla procedura.
- **Profili** riutilizzabili (es. `triennale`, `magistrale`, `aziendale-riservato`), selezionabili in `tesiflow.yaml`.
- **Comandi pronti** per l'agente in `.claude/commands/` (es. `/ricognizione`, `/scaletta <cap>`, `/scrivi <cap>`, `/verifica <cap>`, `/revisione <cap>`, `/slide`), che incapsulano la procedura del metodo.
- Validazione: `tesiflow doctor` controlla che variabili, cartelle e file di stato siano coerenti e segnala istruzioni mancanti o contraddittorie.

## 4. RAG sulla code base

Funzione chiave: **interrogare la code base senza rileggerla**.

Comandi:

- `tesiflow index` — costruisce (o aggiorna in modo incrementale) l'indice di `SourceCode/` in `.claude/rag/`.
- `tesiflow search "<query>"` — ricerca semantica + lessicale, restituisce estratti con `percorso:riga-inizio–riga-fine` e punteggio.
- `tesiflow ask "<domanda>"` — risposta sintetizzata dal modello **solo** sui frammenti recuperati, con citazioni obbligatorie ai file e alle righe; se l'evidenza è insufficiente, lo dichiara.
- `tesiflow serve-mcp` — espone `search`, `ask`, `get_file`, `list_symbols` come **server MCP**, così Claude Code può usare il RAG direttamente come strumento.

Requisiti:

- **Chunking consapevole del codice**: spezzare per funzione/classe/metodo (tree-sitter o equivalente), con fallback per finestre di righe sovrapposte; includere nei metadati percorso, linguaggio, simboli, righe, hash del file.
- Indicizzare anche `DOCUMENTAZIONE/` e `README`/commenti, marcando la **sorgente** di ogni chunk (codice vs documentazione) così l'agente rispetta la gerarchia delle fonti.
- **Aggiornamento incrementale** basato sugli hash: si ri-indicizzano solo i file cambiati.
- Ricerca **ibrida** (embedding + BM25) con re-ranking opzionale.
- **Mappa del codice** generata automaticamente (`.claude/contesto/mappa-codebase.md`): alberatura, moduli, punti d'ingresso, dipendenze, simboli principali: ricavata dall'indice e non scritta a mano.
- Backend configurabili: embedding locali (default, per riservatezza del codice aziendale) o API; vector store locale embedded (es. SQLite/LanceDB/Chroma), senza servizi da installare.
- Il codice **non lascia la macchina** a meno che l'utente lo abbia scelto esplicitamente in configurazione.
- Dimensione e rumore sotto controllo: ignorare file generati, lock, binari, dati di grandi dimensioni.

## Stack consigliato (modificabile con motivazione)

- Python 3.11+, `typer` per la CLI, `pyyaml`/`pydantic` per la configurazione, `jinja2` per i template.
- RAG: `tree-sitter`, `sentence-transformers` (o API), vector store embedded, BM25.
- MCP: SDK ufficiale MCP per Python.
- Distribuzione: pacchetto installabile con `pipx install tesiflow`.
- Template di LaTeX e di istruzioni in `tesiflow/templates/`, versionati e testabili.

## Requisiti non funzionali

- Funziona su macOS e Linux; Windows se non costoso.
- Idempotente: rieseguire un comando non distrugge il lavoro dell'utente; mai sovrascrivere file modificati senza conferma o backup.
- Output chiaro e in italiano (con lingua configurabile).
- Test automatici per scaffolding, chunking, indicizzazione incrementale e generazione dei file.
- Documentazione in `README.md` aggiornata con installazione e flusso d'uso.

## Piano di consegna (a fasi, con riscontro a ogni fase)

1. **Fase 1 — Scaffolding**: `init`, template LaTeX, template `CLAUDE.md` e `STATO_TESI.md`, `build`, `doctor`. Test su una code base di esempio.
2. **Fase 2 — Istruzioni**: `instructions`, profili, istruzioni per capitolo, comandi `.claude/commands/`.
3. **Fase 3 — RAG**: `index`, `search`, `ask`, mappa del codice automatica, incrementale.
4. **Fase 4 — MCP e integrazione**: `serve-mcp`, aggancio automatico in `.claude/settings`/`.mcp.json` generato da `init`.
5. **Fase 5 (opzionale)**: interfaccia web locale per creare il workspace, modificare le istruzioni e interrogare il RAG.

## Come procedere ora

1. Leggi `README.md` e, se disponibile, la tesi di riferimento in `newdir/Tesi_Venieri_Nicolò` (`CLAUDE.md`, `STATO_TESI.md`, `main.tex`, `.claude/`) come modello di struttura e di regole.
2. Proponi l'architettura (moduli, formato di `tesiflow.yaml`, schema dell'indice RAG) e **attendi conferma** prima di scrivere codice.
3. Realizza una fase alla volta, con test, e fermati per un riscontro al termine di ciascuna.
4. Non inventare funzionalità non elencate; segnala dubbi e scelte aperte come domande.
