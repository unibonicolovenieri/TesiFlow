import tarfile
import zipfile

from tesiflow import codemap, workspace as W
from tesiflow.config import Sorgente


def test_detect_type(sample, tmp_path):
    assert W.detect_type(str(sample)) == "path"
    assert W.detect_type("https://github.com/a/b") == "git"
    assert W.detect_type("git@github.com:a/b.git") == "git"
    z = tmp_path / "a.zip"
    z.write_bytes(b"")
    assert W.detect_type(str(z)) == "archivio"


def test_archivio_zip_e_tar(sample, tmp_path):
    z = tmp_path / "c.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.write(sample / "app" / "main.py", "proj/app/main.py")
        zf.writestr("proj/node_modules/a.js", "x")
    dest = tmp_path / "out"
    files = W.import_source(Sorgente(tipo="archivio", origine=str(z)), dest)
    assert files == ["app/main.py"]  # cartella radice unica scartata, node_modules escluso
    t = tmp_path / "c.tar.gz"
    with tarfile.open(t, "w:gz") as tf:
        tf.add(sample / "app" / "ui.js", "ui.js")
    assert W.import_source(Sorgente(tipo="archivio", origine=str(t)), tmp_path / "out2") == ["ui.js"]


def test_file_grandi_esclusi(sample, tmp_path):
    (sample / "big.txt").write_text("a" * 3000)
    files = W.import_source(Sorgente(tipo="path", origine=str(sample), max_file_kb=1), tmp_path / "o")
    assert "big.txt" not in files and "app/main.py" in files


def test_sync_segnala_differenze(ws, sample, run):
    (sample / "app" / "main.py").write_text("def nuovo():\n    pass\n")
    (sample / "app" / "extra.py").write_text("x = 1\n")
    (sample / "requirements.txt").unlink()
    r = run("sync")
    assert r.exit_code == 0, r.output
    assert "1 aggiunti, 1 rimossi, 1 modificati" in r.output
    stato = (ws / "STATO_TESI.md").read_text()
    assert "app/extra.py" in stato and "requirements.txt" in stato
    assert "def nuovo" in (ws / "SourceCode" / "app" / "main.py").read_text()
    assert "nuovo" in (ws / ".claude/contesto/mappa-codebase.md").read_text()


def test_mappa_codice(ws):
    text = (ws / ".claude/contesto/mappa-codebase.md").read_text()
    assert "Python" in text and "JavaScript" in text
    assert "classe `Foo`" in text and "metodo `Foo.bar`" in text and "funzione `main`" in text
    assert "requests==2.0" in text and "SourceCode/app/main.py" in text
    assert "node_modules" not in text


def test_mappa_sorgente_vuota(tmp_path):
    assert "vuota" in codemap.build(tmp_path)
