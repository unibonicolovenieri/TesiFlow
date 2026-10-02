from conftest import needs_latex

from tesiflow import config as C, doctor as D, toolchain


def levels(ws, **kw):
    return D.run(ws, check_tex=False, **kw)


def test_doctor_ok_con_avvisi(ws):
    f = levels(ws)
    assert not [m for lv, m in f if lv == D.ERR]


def test_doctor_rileva_problemi(ws):
    (ws / "Chapter3.tex").unlink()
    (ws / "SourceCode" / ".git").mkdir()
    cfg = C.load(ws)
    cfg.profilo = "aziendale-riservato"
    C.save(ws, cfg)
    msgs = [m for lv, m in levels(ws) if lv == D.ERR]
    assert any("Chapter3.tex" in m for m in msgs)
    assert any(".git annidato" in m for m in msgs)
    assert any("aziendale-riservato" in m for m in msgs)


def test_doctor_rileva_disallineamenti(ws):
    cfg = C.load(ws)
    cfg.tesi.titolo = "Altro"
    C.save(ws, cfg)
    msgs = [m for _, m in levels(ws)]
    assert any("CLAUDE.md non allineato" in m for m in msgs)
    assert any("frontespizio non allineato" in m for m in msgs)


def test_doctor_senza_workspace(tmp_path, run, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run("doctor").exit_code == 2


def test_toolchain_report_formattato(monkeypatch):
    monkeypatch.setattr(toolchain.shutil, "which", lambda n: None)
    rep = toolchain.check()
    assert rep.missing_tools and not rep.ok
    assert "Come installare" in toolchain.format_report(rep)


def test_build_senza_latex_da_errore_chiaro(ws, run, monkeypatch):
    monkeypatch.chdir(ws)
    monkeypatch.setattr(toolchain.shutil, "which", lambda n: None)
    r = run("build")
    assert r.exit_code == 2 and "LaTeX non è installato" in r.output


@needs_latex
def test_build_compila_e_riassume(ws, run, monkeypatch):
    monkeypatch.chdir(ws)
    r = run("build")
    assert r.exit_code == 0, r.output
    assert (ws / "main.pdf").exists() and "TODO rimasti" in r.output


@needs_latex
def test_build_segnala_errori_e_riferimenti(ws, run, monkeypatch):
    monkeypatch.chdir(ws)
    (ws / "Chapter1.tex").write_text("\\chapter{A}\nVedi \\ref{nope}, \\cite{TODO-x}. \\comandoinesistente\n")
    r = run("build")
    assert r.exit_code == 1
    assert "Chapter1.tex:2" in r.output
    r2 = run("build", "--clean")  # l'errore rimane finché non corretto
    assert r2.exit_code == 1
    (ws / "Chapter1.tex").write_text("\\chapter{A}\nVedi \\ref{nope}, \\cite{TODO-x}.\n")
    r3 = run("build")
    assert r3.exit_code == 0, r3.output
    assert "nope" in r3.output and "TODO-x" in r3.output and "cite{TODO" in r3.output
