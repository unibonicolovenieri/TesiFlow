"""Interfaccia a riga di comando di TesiFlow."""
from __future__ import annotations

import shutil
import subprocess
from datetime import date
from pathlib import Path
from typing import Optional

import typer
import yaml

from . import __version__
from . import build as B
from . import codemap, doctor as D, instructions as I, scaffold, toolchain, workspace as W
from . import config as C
from . import render as R

app = typer.Typer(help="TesiFlow: workspace, scheletro LaTeX e istruzioni per scrivere una tesi dal codice.",
                  no_args_is_help=True, add_completion=False)
instr_app = typer.Typer(help="Gestione delle istruzioni per l'agente.", no_args_is_help=True)
app.add_typer(instr_app, name="instructions")

OK, WARN, ERR = typer.style("✔", fg="green"), typer.style("!", fg="yellow"), typer.style("✘", fg="red")


def _root() -> Path:
    try:
        return C.find_root()
    except FileNotFoundError as e:
        typer.secho(str(e), fg="red")
        raise typer.Exit(2)


def _print_results(res: list[tuple[str, str]]) -> None:
    for rel, status in res:
        if status not in ("invariato",):
            typer.echo(f"  {rel}: {status}")


def _tex_warning() -> bool:
    rep = toolchain.check()
    if not rep.ok:
        typer.secho("\nATTENZIONE: la compilazione LaTeX locale non è possibile.", fg="yellow", bold=True)
        typer.echo(toolchain.format_report(rep))
    return rep.ok


@app.command()
def version() -> None:
    """Mostra la versione."""
    typer.echo(__version__)


@app.command()
def init(
    nome: str = typer.Argument(..., help="Nome della cartella di lavoro della tesi."),
    config: Optional[Path] = typer.Option(None, "--config", help="File YAML con i valori di default."),
    source: Optional[str] = typer.Option(None, "--source", help="Percorso locale, URL git o archivio con il codice."),
    candidato: Optional[str] = typer.Option(None), titolo: Optional[str] = typer.Option(None),
    argomento: Optional[str] = typer.Option(None), azienda: Optional[str] = typer.Option(None),
    ateneo: Optional[str] = typer.Option(None), relatore: Optional[str] = typer.Option(None),
    correlatore: Optional[str] = typer.Option(None),
    anno_accademico: Optional[str] = typer.Option(None, "--anno-accademico"),
    lingua: Optional[str] = typer.Option(None, help="it | en"),
    pagine: Optional[int] = typer.Option(None, "--pagine", help="Pagine target."),
    profilo: Optional[str] = typer.Option(None, help="triennale | magistrale | aziendale-riservato"),
    riservatezza: Optional[str] = typer.Option(None, help="Vincoli di riservatezza (attiva la riservatezza)."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Non interattivo: errore se manca un valore obbligatorio."),
    no_git: bool = typer.Option(False, "--no-git", help="Non inizializzare il repository git."),
) -> None:
    """Crea il workspace di tesi (idempotente: non sovrascrive file esistenti)."""
    root = Path(nome).resolve()
    tex_ok = _tex_warning()
    cfg_path = root / C.CONFIG_NAME

    if cfg_path.exists():
        typer.echo(f"Workspace esistente in {root}: creo solo i file mancanti.")
        cfg = C.load(root)
    else:
        if root.exists() and any(root.iterdir()):
            typer.secho(f"{root} esiste e non è vuota.", fg="red")
            raise typer.Exit(1)
        base = yaml.safe_load(config.read_text("utf-8")) if config else {}
        base_t = base.get("tesi", {})

        def ask(key: str, val, label: str, required: bool = True, default=None):
            if val is not None:
                return val
            if base_t.get(key) not in (None, ""):
                return base_t[key]
            if yes:
                if required:
                    typer.secho(f"Valore obbligatorio mancante: --{key.replace('_', '-')}", fg="red")
                    raise typer.Exit(2)
                return default if default is not None else ""
            return typer.prompt(label, default=default if default is not None else "", show_default=bool(default)) \
                if not required else typer.prompt(label)

        prof = profilo or base.get("profilo")
        if prof is None:
            prof = "magistrale" if yes else typer.prompt(
                f"Profilo ({', '.join(scaffold.list_profiles())})", default="magistrale")
        if prof not in scaffold.list_profiles():
            typer.secho(f"Profilo sconosciuto: {prof}", fg="red")
            raise typer.Exit(2)

        t = dict(
            candidato=ask("candidato", candidato, "Candidato"),
            titolo=ask("titolo", titolo, "Titolo della tesi"),
            argomento=ask("argomento", argomento, "Argomento (breve descrizione)", False),
            azienda=ask("azienda", azienda, "Azienda/ente (vuoto se nessuno)", False),
            ateneo=ask("ateneo", ateneo, "Ateneo"),
            relatore=ask("relatore", relatore, "Relatore"),
            correlatore=ask("correlatore", correlatore, "Correlatore (vuoto se nessuno)", False),
            anno_accademico=ask("anno_accademico", anno_accademico, "Anno accademico (es. 2025/2026)"),
            lingua=ask("lingua", lingua, "Lingua della tesi (it/en)", False, "it") or "it",
        )
        pag = pagine or base_t.get("pagine_target")
        cfg = C.Config(tesi=C.Tesi(**t, pagine_target=pag or 100), profilo=prof)
        I.apply_profile(cfg, prof, keep_pages=pag is not None)
        for k in ("riservatezza", "istruzioni", "capitoli"):  # valori espliciti dal file di config
            if k in base:
                if k == "capitoli":
                    cfg.capitoli = base[k]
                else:
                    cur = getattr(cfg, k).model_dump()
                    cur.update(base[k])
                    setattr(cfg, k, type(getattr(cfg, k))(**cur))
        if riservatezza is not None:
            cfg.riservatezza = C.Riservatezza(attiva=True, note=riservatezza)
        elif not yes and not cfg.riservatezza.attiva and typer.confirm(
                "Ci sono vincoli di riservatezza (codice/nomi aziendali)?", default=bool(cfg.tesi.azienda)):
            cfg.riservatezza = C.Riservatezza(attiva=True, note=typer.prompt("Descrivili"))
        if not cfg.capitoli:
            cfg.capitoli = scaffold.default_chapters(cfg.tesi.lingua)

        origine = source or (base.get("sorgente") or {}).get("origine")
        if origine is None and not yes:
            origine = typer.prompt("Code base: percorso, URL git o archivio (vuoto per saltare)", default="",
                                   show_default=False)
        if origine:
            try:
                tipo = W.detect_type(origine)
            except W.SourceError as e:
                typer.secho(str(e), fg="red")
                raise typer.Exit(1)
            cfg.sorgente.tipo, cfg.sorgente.origine = tipo, origine
            extra = (base.get("sorgente") or {}).get("esclusioni")
            if extra:
                cfg.sorgente.esclusioni += extra
        root.mkdir(parents=True, exist_ok=True)
        C.save(root, cfg)

    typer.echo(f"\nCreo il workspace in {root}")
    _print_results(scaffold.scaffold(root, cfg))

    src_dir = root / W.SOURCE_DIR
    if cfg.sorgente.tipo != "nessuna" and not any(src_dir.iterdir()):
        typer.echo(f"\nImporto la code base ({cfg.sorgente.tipo}: {cfg.sorgente.origine})…")
        try:
            files = W.import_source(cfg.sorgente, src_dir)
            typer.echo(f"  {len(files)} file copiati in SourceCode/ (sola lettura, senza .git né artefatti).")
        except W.SourceError as e:
            typer.secho(f"  {e}", fg="red")
    if any(src_dir.iterdir()):
        _write_map(root)

    if not no_git and shutil.which("git") and not (root / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=root)
        subprocess.run(["git", "add", "-A"], cwd=root)
        subprocess.run(["git", "commit", "-q", "-m", "Scaffolding iniziale TesiFlow"], cwd=root,
                       capture_output=True)
        typer.echo("  Repository git inizializzato.")

    typer.secho(f"\n{'Fatto' if tex_ok else 'Fatto (ma installa LaTeX prima di compilare)'}.", fg="green")
    typer.echo(f"Prossimi passi: cd {nome}; copia documenti in DOCUMENTAZIONE/, Requirements/, HINTS/; "
               "poi `tesiflow doctor`, `tesiflow build` e avvia Claude Code (`/ricognizione`).")


def _write_map(root: Path) -> None:
    text = codemap.build(root / W.SOURCE_DIR)
    R.write_file(root, ".claude/contesto/mappa-codebase.md", text, "managed")
    typer.echo("  Mappa del codice aggiornata: .claude/contesto/mappa-codebase.md")


@app.command()
def map() -> None:
    """Rigenera la mappa del codice da SourceCode/."""
    _write_map(_root())


@app.command()
def sync() -> None:
    """Riallinea SourceCode/ alla sorgente originale e segnala le differenze in STATO_TESI.md."""
    root = _root()
    cfg = C.load(root)
    dest = root / W.SOURCE_DIR
    old = W.snapshot(dest)
    try:
        W.import_source(cfg.sorgente, dest)
    except W.SourceError as e:
        typer.secho(str(e), fg="red")
        raise typer.Exit(1)
    diff = W.diff_snapshots(old, W.snapshot(dest))
    tot = sum(len(v) for v in diff.values())
    typer.echo(f"Sincronizzato: {len(diff['aggiunti'])} aggiunti, {len(diff['rimossi'])} rimossi, "
               f"{len(diff['modificati'])} modificati.")
    _write_map(root)
    if tot:
        stato = root / "STATO_TESI.md"
        lines = [f"\n### Sync del {date.today().isoformat()}\n"]
        for k, v in diff.items():
            if v:
                shown = v[:30]
                lines.append(f"- {k} ({len(v)}): " + ", ".join(f"`{x}`" for x in shown)
                             + (" …" if len(v) > 30 else ""))
        lines.append("- Verificare i capitoli che dipendono dai file toccati.\n")
        text = stato.read_text("utf-8") if stato.exists() else ""
        marker = "## Sincronizzazioni di SourceCode"
        block = "\n".join(lines)
        if marker in text:
            head, tail = text.split(marker, 1)
            nxt = tail.find("\n## ")
            body, rest = (tail, "") if nxt < 0 else (tail[:nxt], tail[nxt:])
            text = head + marker + body.rstrip() + "\n" + block + rest
        else:
            text += f"\n{marker}\n{block}"
        stato.write_text(text, encoding="utf-8")
        typer.echo("  Differenze registrate in STATO_TESI.md.")


@app.command()
def build(
    clean: bool = typer.Option(False, "--clean", help="Pulisce i file intermedi prima di compilare."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Mostra anche tutti i warning."),
) -> None:
    """Compila la tesi (latexmk -pdf) e riassume errori, warning, riferimenti e TODO."""
    root = _root()
    rep = toolchain.check()
    if rep.missing_tools or rep.missing_packages:
        typer.secho("Impossibile compilare: LaTeX non è installato correttamente.", fg="red", bold=True)
        typer.echo(toolchain.format_report(rep))
        raise typer.Exit(2)
    typer.echo("Compilazione in corso…")
    res = B.run(root, clean)
    if res.errors:
        typer.secho(f"\n{ERR} Errori ({len(res.errors)}):", bold=True)
        for e in res.errors[:20]:
            typer.echo(f"  - {e}")
    if not res.ok and not res.errors:
        typer.echo(res.raw_tail)
    if res.undefined_refs:
        typer.echo(f"\n{WARN} Riferimenti non risolti ({len(res.undefined_refs)}): " + ", ".join(res.undefined_refs))
    if res.undefined_cites:
        typer.echo(f"\n{WARN} Citazioni non risolte ({len(res.undefined_cites)}): " + ", ".join(res.undefined_cites))
    if res.bibtex:
        typer.echo(f"\n{WARN} BibTeX:")
        for b in res.bibtex[:10]:
            typer.echo(f"  - {b}")
    typer.echo(f"\n{WARN if res.warnings else OK} Altri warning: {len(res.warnings)}; overfull hbox: {res.overfull}")
    if verbose:
        for w in res.warnings:
            typer.echo(f"  - {w}")
    n = sum(res.todos.values())
    typer.echo(f"{WARN if n else OK} TODO rimasti: {n}" + (f" in {len(res.todos)} file" if n else "")
               + (f"; \\cite{{TODO-…}}: {res.cite_todos}" if res.cite_todos else ""))
    for f, c in res.todos.items():
        typer.echo(f"  - {f}: {c}")
    if res.ok:
        typer.secho(f"\n{OK} PDF generato: {res.pdf}", fg="green")
    else:
        typer.secho(f"\n{ERR} Compilazione fallita.", fg="red")
        raise typer.Exit(1)


@app.command()
def doctor(no_tex: bool = typer.Option(False, "--no-tex", help="Salta il controllo di LaTeX.")) -> None:
    """Controlla coerenza di variabili, cartelle, file di stato, istruzioni e LaTeX."""
    root = _root()
    findings = D.run(root, check_tex=not no_tex)
    sym = {D.OK: OK, D.WARN: WARN, D.ERR: ERR}
    for level, msg in findings:
        typer.echo(f"{sym[level]} {msg}")
    errs = sum(1 for lv, _ in findings if lv == D.ERR)
    warns = sum(1 for lv, _ in findings if lv == D.WARN)
    typer.echo(f"\n{errs} errori, {warns} avvisi.")
    if errs:
        raise typer.Exit(1)


@app.command()
def regen() -> None:
    """Riallinea CLAUDE.md, frontespizio e file mancanti a tesiflow.yaml (conserva le parti personalizzate)."""
    root = _root()
    res = scaffold.regen(root, C.load(root))
    _print_results(res) if res else typer.echo("Già allineato.")


# --- instructions -------------------------------------------------------------------

@instr_app.command("show")
def instr_show() -> None:
    """Mostra le istruzioni correnti."""
    typer.echo(I.summary(C.load(_root())))


@instr_app.command("profiles")
def instr_profiles() -> None:
    """Elenca i profili disponibili."""
    for p in scaffold.list_profiles():
        typer.echo(f"- {p}: {scaffold.load_profile(p)['istruzioni']['lunghezza']}")


@instr_app.command("profile")
def instr_profile(nome: str = typer.Argument(...)) -> None:
    """Applica un profilo (sovrascrive registro, dettaglio, lunghezza, regole) e rigenera CLAUDE.md."""
    root = _root()
    cfg = C.load(root)
    try:
        I.apply_profile(cfg, nome, keep_pages=True)
    except ValueError as e:
        typer.secho(str(e), fg="red")
        raise typer.Exit(2)
    C.save(root, cfg)
    _print_results(scaffold.regen(root, cfg))


@instr_app.command("edit")
def instr_edit(
    registro: Optional[str] = typer.Option(None), dettaglio: Optional[str] = typer.Option(None),
    lunghezza: Optional[str] = typer.Option(None),
    riservatezza: Optional[str] = typer.Option(None, help="Testo dei vincoli; stringa vuota per disattivare."),
    aggiungi_regola: list[str] = typer.Option([], "--aggiungi-regola"),
    rimuovi_regola: list[int] = typer.Option([], "--rimuovi-regola", help="Numero della regola (vedi `show`)."),
) -> None:
    """Modifica guidata (senza opzioni: interattiva) e rigenera CLAUDE.md."""
    root = _root()
    cfg = C.load(root)
    i = cfg.istruzioni
    interactive = all(v is None or v == [] for v in
                      (registro, dettaglio, lunghezza, riservatezza, aggiungi_regola, rimuovi_regola))
    if interactive:
        typer.echo(I.summary(cfg) + "\n")
        i.registro = typer.prompt("Registro", default=i.registro)
        i.livello_dettaglio = typer.prompt("Livello di dettaglio", default=i.livello_dettaglio)
        i.lunghezza = typer.prompt("Lunghezza", default=i.lunghezza, show_default=bool(i.lunghezza))
        if typer.confirm("Vincoli di riservatezza attivi?", default=cfg.riservatezza.attiva):
            cfg.riservatezza = C.Riservatezza(
                attiva=True, note=typer.prompt("Vincoli", default=cfg.riservatezza.note or ""))
        else:
            cfg.riservatezza.attiva = False
        while i.regole_aggiuntive and typer.confirm("Rimuovere una regola aggiuntiva?", default=False):
            n = typer.prompt("Numero regola", type=int)
            if 1 <= n <= len(i.regole_aggiuntive):
                i.regole_aggiuntive.pop(n - 1)
        while (r := typer.prompt("Nuova regola aggiuntiva (vuoto per finire)", default="", show_default=False)):
            i.regole_aggiuntive.append(r)
    else:
        if registro is not None:
            i.registro = registro
        if dettaglio is not None:
            i.livello_dettaglio = dettaglio
        if lunghezza is not None:
            i.lunghezza = lunghezza
        if riservatezza is not None:
            cfg.riservatezza = C.Riservatezza(attiva=bool(riservatezza), note=riservatezza)
        for n in sorted(rimuovi_regola, reverse=True):
            if 1 <= n <= len(i.regole_aggiuntive):
                i.regole_aggiuntive.pop(n - 1)
        i.regole_aggiuntive += aggiungi_regola
    C.save(root, cfg)
    _print_results(scaffold.regen(root, cfg))
    typer.echo("Istruzioni aggiornate.")
