"""`tesiflow doctor`: coerenza di variabili, cartelle, file di stato e istruzioni."""
from __future__ import annotations

import re
from pathlib import Path

from pydantic import ValidationError

from . import config as C
from . import scaffold, toolchain
from . import render as R

ERR, WARN, OK = "errore", "avviso", "ok"
Finding = tuple[str, str]
MARKERS = ("node_modules", "__pycache__", "dist", "build")


def run(root: Path, check_tex: bool = True) -> list[Finding]:
    f: list[Finding] = []

    if check_tex:
        rep = toolchain.check()
        if rep.ok:
            f.append((OK, "Compilatore LaTeX e pacchetti richiesti presenti."))
        else:
            f.append((ERR, toolchain.format_report(rep)))

    try:
        cfg = C.load(root)
    except (ValidationError, FileNotFoundError, ValueError) as e:
        return f + [(ERR, f"tesiflow.yaml non valido: {e}")]
    f.append((OK, "tesiflow.yaml valido."))

    for k, v in cfg.tesi.model_dump().items():
        if k in ("correlatore", "azienda", "argomento"):
            continue
        if v in ("", None) or (isinstance(v, str) and "TODO" in v):
            f.append((ERR, f"Variabile `tesi.{k}` mancante o TODO."))
    if not cfg.tesi.argomento:
        f.append((WARN, "Variabile `tesi.argomento` vuota: CLAUDE.md riporta TODO."))
    if cfg.tesi.pagine_target < 20:
        f.append((WARN, f"pagine_target = {cfg.tesi.pagine_target} sembra troppo basso."))

    for d in scaffold.DIRS:
        if not (root / d).is_dir():
            f.append((ERR, f"Cartella mancante: {d}/"))
    expected = ["main.tex", "STATO_TESI.md", "CLAUDE.md", "references.bib", ".latexmkrc",
                "Abstract_It.tex", "Abstract_Eng.tex", "Acknowledgment.tex", "Dedica.tex", "Nomenclature.tex"]
    expected += [n for n, _ in scaffold.chapter_files(cfg)]
    for n in expected:
        if not (root / n).is_file():
            f.append((ERR, f"File mancante: {n} (si ricrea con `tesiflow regen`)."))

    # CLAUDE.md allineato a tesiflow.yaml
    claude = root / "CLAUDE.md"
    if claude.is_file():
        text = claude.read_text("utf-8")
        old = scaffold.render_claude_md(cfg, text)
        if re.sub(r"\s+", " ", old) != re.sub(r"\s+", " ", text):
            f.append((WARN, "CLAUDE.md non allineato a tesiflow.yaml: esegui `tesiflow regen`."))
        for sec in ("## Ruolo", "## Procedura di lavoro", "## Divieti", "## Riservatezza", "## Continuità tra sessioni"):
            if sec not in text:
                f.append((ERR, f"CLAUDE.md: manca la sezione «{sec[3:]}»."))
        if "TESIFLOW:CUSTOM:BEGIN" not in text:
            f.append((WARN, "CLAUDE.md: blocco «Regole personalizzate» assente (andrà perso a ogni rigenerazione)."))

    # main.tex allineato e coerente con i capitoli
    main = root / "main.tex"
    if main.is_file():
        mt = main.read_text("utf-8")
        block = R.get_block(mt, "META", "tex")
        if block is None:
            f.append((WARN, "main.tex: blocco TESIFLOW:META assente; il frontespizio non si aggiorna da yaml."))
        elif block != scaffold.meta_block(cfg):
            f.append((WARN, "main.tex: frontespizio non allineato a tesiflow.yaml: esegui `tesiflow regen`."))
        for n, _ in scaffold.chapter_files(cfg):
            if not re.search(r"^\s*\\input\{" + re.escape(n[:-4]) + r"\}", mt, re.M):
                f.append((WARN, f"main.tex non include {n[:-4]}."))

    # riservatezza: contraddizioni
    r = cfg.riservatezza
    if r.attiva and (not r.note.strip() or "TODO" in r.note):
        f.append((WARN, "Riservatezza attiva ma senza note concrete (`riservatezza.note`)."))
    if cfg.profilo == "aziendale-riservato" and not r.attiva:
        f.append((ERR, "Profilo `aziendale-riservato` ma `riservatezza.attiva` è false."))
    if not r.attiva and cfg.tesi.azienda:
        f.append((WARN, f"Azienda «{cfg.tesi.azienda}» indicata ma riservatezza non attiva: è voluto?"))
    if cfg.istruzioni.registro.strip() == "":
        f.append((ERR, "Registro delle istruzioni vuoto."))

    # SourceCode
    src = root / "SourceCode"
    if src.is_dir() and any(src.iterdir()):
        if (src / ".git").exists():
            f.append((ERR, "SourceCode/ contiene un .git annidato."))
        bad = [m for m in MARKERS if (src / m).exists()]
        if bad:
            f.append((WARN, "SourceCode/ contiene artefatti: " + ", ".join(bad)))
        mappa = root / ".claude" / "contesto" / "mappa-codebase.md"
        if not mappa.exists():
            f.append((WARN, "Mappa del codice assente: esegui `tesiflow map`."))
        else:
            newest = max((p.stat().st_mtime for p in src.rglob("*") if p.is_file()), default=0)
            if newest > mappa.stat().st_mtime:
                f.append((WARN, "La mappa del codice è più vecchia di SourceCode/: esegui `tesiflow map`."))
        writable = [p for p in src.rglob("*") if p.is_file() and p.stat().st_mode & 0o222]
        if writable:
            f.append((WARN, f"SourceCode/: {len(writable)} file scrivibili (dovrebbe essere sola lettura)."))
    elif cfg.sorgente.tipo != "nessuna":
        f.append((WARN, "SourceCode/ vuota: esegui `tesiflow sync`."))
    else:
        f.append((WARN, "Nessuna sorgente configurata: SourceCode/ vuota."))

    # STATO_TESI.md
    stato = root / "STATO_TESI.md"
    if stato.is_file():
        st = stato.read_text("utf-8")
        for sec in scaffold.STATO_SECTIONS:
            if f"## {sec}" not in st:
                f.append((WARN, f"STATO_TESI.md: manca la sezione «{sec}»."))

    # istruzioni per capitolo
    for n, _ in scaffold.chapter_files(cfg):
        p = root / "instructions" / f"{n[:-4]}.md"
        if not p.is_file():
            f.append((WARN, f"Istruzioni mancanti: instructions/{n[:-4]}.md"))
        elif "TODO" in p.read_text("utf-8"):
            f.append((WARN, f"instructions/{n[:-4]}.md ha ancora campi TODO."))

    for c in scaffold.COMMANDS:
        if not (root / ".claude" / "commands" / f"{c}.md").is_file():
            f.append((WARN, f"Comando mancante: .claude/commands/{c}.md"))

    if not any(s == ERR for s, _ in f) and not any(s == WARN for s, _ in f):
        f.append((OK, "Nessun problema rilevato."))
    return f
