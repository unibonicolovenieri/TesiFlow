import os
import stat

from tesiflow import config as C, render as R


def test_struttura_creata(ws):
    for n in ["tesiflow.yaml", "CLAUDE.md", "STATO_TESI.md", "main.tex", "Abstract_It.tex", "Abstract_Eng.tex",
              "Acknowledgment.tex", "Dedica.tex", "Nomenclature.tex", "Conclusion.tex", "references.bib",
              ".latexmkrc", ".claude/CLAUDE.md", ".claude/contesto/lavoro-svolto.md",
              ".claude/contesto/mappa-codebase.md", "instructions/Chapter1.md", "instructions/Conclusion.md"]:
        assert (ws / n).is_file(), n
    for d in ["figs", "DOCUMENTAZIONE", "SourceCode", "Requirements", "HINTS", "SLIDES"]:
        assert (ws / d).is_dir()
    for c in ["ricognizione", "scaletta", "scrivi", "verifica", "revisione", "slide"]:
        assert (ws / ".claude" / "commands" / f"{c}.md").is_file()
    assert len(list(ws.glob("Chapter*.tex"))) == 6


def test_variabili_e_escape_latex(ws):
    main = (ws / "main.tex").read_text()
    assert r"Analisi \& Progetto\_X 50\%" in main
    assert "ACME" in main
    claude = (ws / "CLAUDE.md").read_text()
    assert "Analisi & Progetto_X 50%" in claude
    assert "{{" not in claude and "<<" not in main


def test_sorgente_filtrata_e_sola_lettura(ws):
    src = ws / "SourceCode"
    files = {p.relative_to(src).as_posix() for p in src.rglob("*") if p.is_file()}
    assert files == {".gitignore", "requirements.txt", "app/main.py", "app/ui.js"}
    assert not (src / ".git").exists()
    for p in src.rglob("*"):
        if p.is_file():
            assert not p.stat().st_mode & stat.S_IWUSR


def test_init_idempotente_non_sovrascrive(ws, run):
    (ws / "Chapter1.tex").write_text("LAVORO DELL'UTENTE")
    r = run("init", ws, "-y", "--no-git")
    assert r.exit_code == 0
    assert (ws / "Chapter1.tex").read_text() == "LAVORO DELL'UTENTE"


def test_init_rifiuta_cartella_non_vuota(tmp_path, run):
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "f").write_text("a")
    r = run("init", tmp_path / "x", "-y", "--candidato", "a", "--titolo", "b", "--ateneo", "c",
            "--relatore", "d", "--anno-accademico", "e")
    assert r.exit_code == 1


def test_init_yes_senza_valori_obbligatori(tmp_path, run):
    r = run("init", tmp_path / "t", "-y")
    assert r.exit_code == 2


def test_regen_conserva_blocco_personalizzato_e_backup(ws, run):
    p = ws / "CLAUDE.md"
    p.write_text(R.set_block(p.read_text(), "CUSTOM", "REGOLA MIA\n"))
    r = run("instructions", "edit", "--registro", "colloquiale", "--aggiungi-regola", "Usa il passato")
    assert r.exit_code == 0, r.output
    text = p.read_text()
    assert "REGOLA MIA" in text and "colloquiale" in text and "Usa il passato" in text
    assert list((ws / ".tesiflow" / "backup").rglob("CLAUDE.md"))  # modificato a mano -> backup


def test_regen_aggiorna_frontespizio_e_non_tocca_capitoli(ws, run):
    cfg = C.load(ws)
    cfg.tesi.titolo = "Nuovo Titolo"
    C.save(ws, cfg)
    (ws / "Chapter2.tex").write_text("MIO")
    assert run("regen").exit_code == 0
    assert "Nuovo Titolo" in (ws / "main.tex").read_text()
    assert (ws / "Chapter2.tex").read_text() == "MIO"
    assert "Nuovo Titolo" in (ws / "CLAUDE.md").read_text()


def test_profilo_aziendale_attiva_riservatezza(ws, run):
    assert run("instructions", "profile", "aziendale-riservato").exit_code == 0
    assert C.load(ws).riservatezza.attiva
    assert "Vincoli attivi" in (ws / "CLAUDE.md").read_text()
    assert run("instructions", "profile", "inesistente").exit_code == 2


def test_lingua_inglese(tmp_path, sample, run):
    path = tmp_path / "en"
    r = run("init", path, "-y", "--no-git", "--candidato", "J", "--titolo", "T", "--ateneo", "U", "--relatore", "R",
            "--anno-accademico", "2025/2026", "--lingua", "en")
    assert r.exit_code == 0, r.output
    assert "[italian,english]{babel}" in (path / "main.tex").read_text()
    assert "Introduction" in (path / "Chapter1.tex").read_text()


def test_config_yaml_e_capitoli_personalizzati(tmp_path, run):
    cfgf = tmp_path / "base.yaml"
    cfgf.write_text("tesi: {candidato: A, titolo: T, ateneo: U, relatore: R, anno_accademico: 2025/2026}\n"
                    "capitoli: [Uno, Due]\n")
    r = run("init", tmp_path / "w", "-y", "--no-git", "--config", cfgf)
    assert r.exit_code == 0, r.output
    assert len(list((tmp_path / "w").glob("Chapter*.tex"))) == 2
    assert "\\input{Chapter2}" in (tmp_path / "w" / "main.tex").read_text()
