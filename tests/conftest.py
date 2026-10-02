import shutil
import pytest
from typer.testing import CliRunner

from tesiflow.cli import app

HAS_LATEX = shutil.which("latexmk") is not None and shutil.which("pdflatex") is not None
needs_latex = pytest.mark.skipif(not HAS_LATEX, reason="LaTeX non installato")


@pytest.fixture
def sample(tmp_path):
    s = tmp_path / "sample"
    (s / "app").mkdir(parents=True)
    (s / "node_modules" / "x").mkdir(parents=True)
    (s / "build").mkdir()
    (s / "app" / "main.py").write_text("class Foo:\n    def bar(self):\n        return 1\n\n\ndef main():\n    pass\n")
    (s / "app" / "ui.js").write_text("export function hi(){}\n")
    (s / "app" / "blob.dat").write_bytes(b"\x00\x01\x02")
    (s / "requirements.txt").write_text("requests==2.0\n")
    (s / "node_modules" / "x" / "i.js").write_text("junk")
    (s / "build" / "o.txt").write_text("junk")
    (s / ".gitignore").write_text("secret.txt\n")
    (s / "secret.txt").write_text("s")
    (s / ".git").mkdir()
    (s / ".git" / "HEAD").write_text("ref")
    return s


@pytest.fixture
def run():
    runner = CliRunner()
    return lambda *args, **kw: runner.invoke(app, [str(a) for a in args], **kw)


@pytest.fixture
def ws(tmp_path, sample, run, monkeypatch):
    """Workspace creato con `init` non interattivo."""
    path = tmp_path / "tesi"
    r = run("init", path, "-y", "--no-git", "--candidato", "Mario Rossi", "--titolo", "Analisi & Progetto_X 50%",
            "--ateneo", "Università di Pisa", "--relatore", "Prof. Bianchi", "--anno-accademico", "2025/2026",
            "--azienda", "ACME", "--profilo", "magistrale", "--source", sample)
    assert r.exit_code == 0, r.output
    monkeypatch.chdir(path)
    return path
