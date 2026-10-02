"""Generazione dei file del workspace a partire da `tesiflow.yaml`."""
from __future__ import annotations

from pathlib import Path

import yaml
from importlib import resources

from . import render as R
from .config import CAPITOLI_DEFAULT, Config

DIRS = [
    "figs", "DOCUMENTAZIONE", "Requirements", "HINTS", "SLIDES", "SourceCode",
    "instructions", ".claude/contesto", ".claude/commands",
]
COMMANDS = ["ricognizione", "scaletta", "scrivi", "verifica", "revisione", "slide"]
STATO_SECTIONS = [
    "In corso", "Ricognizione iniziale", "Indice concordato e stato dei capitoli",
    "Fonti usate per capitolo", "Decisioni prese con l'utente", "Modifiche allo scheletro LaTeX",
    "Domande aperte", "Registro delle sessioni",
]
GITIGNORE = """# LaTeX
*.aux
*.bbl
*.blg
*.fdb_latexmk
*.fls
*.lof
*.lot
*.out
*.toc
*.nlo
*.nls
*.nlg
*.synctex.gz
*.log
/main.pdf
# TesiFlow
.tesiflow/backup/
.claude/rag/
.DS_Store
"""
LINGUE = {"it": "italiano", "en": "inglese"}
LABELS = {
    "it": dict(babel="english,italian", nomname="Nomenclatura", ack="Ringraziamenti",
               candidato="Candidato", relatore="Relatore", correlatore="Correlatore",
               azienda="Azienda", aa="Anno Accademico"),
    "en": dict(babel="italian,english", nomname="Nomenclature", ack="Acknowledgments",
               candidato="Candidate", relatore="Supervisor", correlatore="Co-supervisor",
               azienda="Company", aa="Academic Year"),
}
SCOPI = {
    "it": "TODO: descrivere in una riga a quale domanda risponde il capitolo.",
    "en": "TODO: describe in one line which question this chapter answers.",
}


def load_profile(name: str) -> dict:
    path = resources.files("tesiflow").joinpath("templates", "profiles", f"{name}.yaml")
    if not path.is_file():
        raise ValueError(f"Profilo sconosciuto: {name}. Disponibili: {', '.join(list_profiles())}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def list_profiles() -> list[str]:
    d = resources.files("tesiflow").joinpath("templates", "profiles")
    return sorted(p.name[:-5] for p in d.iterdir() if p.name.endswith(".yaml"))


def default_chapters(lingua: str) -> list[str]:
    return list(CAPITOLI_DEFAULT[lingua])


def chapter_files(cfg: Config) -> list[tuple[str, str]]:
    files = [(f"Chapter{i}.tex", t) for i, t in enumerate(cfg.capitoli, 1)]
    return files + [("Conclusion.tex", cfg.titolo_conclusioni)]


def meta_block(cfg: Config) -> str:
    tipo = load_profile(cfg.profilo)["tipo_tesi"]
    return R.render("latex/meta.tex.j2", t=cfg.tesi, tipo_tesi=tipo)


def _main(cfg: Config) -> str:
    lab = LABELS[cfg.tesi.lingua]
    return R.render(
        "latex/main.tex.j2", t=cfg.tesi, meta=meta_block(cfg),
        chapters=range(1, len(cfg.capitoli) + 1), babel=lab["babel"], nomname=lab["nomname"],
        lbl_candidato=lab["candidato"], lbl_relatore=lab["relatore"],
        lbl_correlatore=lab["correlatore"], lbl_azienda=lab["azienda"], lbl_aa=lab["aa"],
    )


def render_claude_md(cfg: Config, existing: str | None = None) -> str:
    text = R.render(
        "claude/CLAUDE.md.j2", t=cfg.tesi, r=cfg.riservatezza, i=cfg.istruzioni,
        lingua_estesa=LINGUE[cfg.tesi.lingua],
    )
    custom = R.get_block(existing, "CUSTOM") if existing else None
    if custom is not None:
        text = R.set_block(text, "CUSTOM", custom)
    return text


def _pagine(cfg: Config) -> str:
    n = max(len(cfg.capitoli), 1)
    return f"~{round(cfg.tesi.pagine_target / (n + 1))}"


def scaffold(root: Path, cfg: Config) -> list[tuple[str, str]]:
    """Crea i file mancanti; non tocca mai quelli esistenti (tranne i file gestiti)."""
    res: list[tuple[str, str]] = []
    for d in DIRS:
        (root / d).mkdir(parents=True, exist_ok=True)
        if d != "SourceCode" and not any((root / d).iterdir()):
            (root / d / ".gitkeep").touch()
    lab = LABELS[cfg.tesi.lingua]

    def w(rel: str, content: str, mode: str = "create") -> None:
        res.append((rel, R.write_file(root, rel, content, mode)))

    w("main.tex", _main(cfg))
    for name in ("Abstract_It", "Abstract_Eng", "Dedica", "Nomenclature"):
        w(f"{name}.tex", R.render(f"latex/{name}.tex.j2"))
    w("Acknowledgment.tex", R.render("latex/Acknowledgment.tex.j2", title=lab["ack"]))
    w("references.bib", R.render("latex/references.bib.j2"))
    w(".latexmkrc", R.render("latex/latexmkrc.j2"))
    w(".gitignore", GITIGNORE)

    for i, (fname, titolo) in enumerate(chapter_files(cfg), 1):
        is_concl = fname == "Conclusion.tex"
        n = "" if is_concl else str(i)
        if is_concl:
            w(fname, R.render("latex/Conclusion.tex.j2", titolo=titolo))
        else:
            w(fname, R.render("latex/Chapter.tex.j2", titolo=titolo, n=n, scopo=SCOPI[cfg.tesi.lingua]))
        w(
            f"instructions/{fname[:-4]}.md",
            R.render("claude/chapter_instructions.md.j2", titolo=titolo, file=fname,
                     scopo=SCOPI[cfg.tesi.lingua], pagine=_pagine(cfg)),
        )

    w("STATO_TESI.md", R.render("claude/STATO_TESI.md.j2", t=cfg.tesi, capitoli=chapter_files(cfg)))
    existing = (root / "CLAUDE.md")
    w("CLAUDE.md", render_claude_md(cfg, existing.read_text("utf-8") if existing.exists() else None))
    w(".claude/CLAUDE.md", R.render("claude/folder_CLAUDE.md.j2", t=cfg.tesi))
    w(".claude/contesto/lavoro-svolto.md", R.render("claude/lavoro-svolto.md.j2", t=cfg.tesi))
    w("SLIDES/README.md", R.render("claude/slides_README.md.j2", t=cfg.tesi))
    for c in COMMANDS:
        src = resources.files("tesiflow").joinpath("templates", "commands", f"{c}.md")
        w(f".claude/commands/{c}.md", src.read_text(encoding="utf-8"))
    return res


def regen(root: Path, cfg: Config) -> list[tuple[str, str]]:
    """Riallinea i file derivati da `tesiflow.yaml`: CLAUDE.md, blocco META di main.tex,
    file mancanti dei capitoli. I capitoli già esistenti non vengono toccati."""
    res: list[tuple[str, str]] = []
    claude = root / "CLAUDE.md"
    old = claude.read_text("utf-8") if claude.exists() else None
    res.append(("CLAUDE.md", R.write_file(root, "CLAUDE.md", render_claude_md(cfg, old), "managed")))

    main = root / "main.tex"
    if main.exists():
        text = main.read_text("utf-8")
        if R.get_block(text, "META", "tex") is None:
            res.append(("main.tex", "saltato (blocco TESIFLOW:META assente)"))
        else:
            new = R.set_block(text, "META", meta_block(cfg), "tex")
            if new != text:
                R.backup(root, "main.tex")
                main.write_text(new, encoding="utf-8")
                res.append(("main.tex", "aggiornato (blocco META; backup in .tesiflow/backup)"))
            else:
                res.append(("main.tex", "invariato"))
    res += [r for r in scaffold(root, cfg) if r[1] != "invariato" and r[1] != "saltato"]
    return res
