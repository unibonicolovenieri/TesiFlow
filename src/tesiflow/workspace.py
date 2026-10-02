"""Importazione e sincronizzazione della code base in `SourceCode/` (sola lettura)."""
from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path

import pathspec

from .config import Sorgente

ARCHIVE_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")
SOURCE_DIR = "SourceCode"


class SourceError(Exception):
    pass


def detect_type(origine: str) -> str:
    low = origine.lower()
    if low.startswith(("http://", "https://", "git@", "ssh://", "git://")) or low.endswith(".git"):
        return "git"
    if Path(origine).expanduser().is_file() and low.endswith(ARCHIVE_SUFFIXES):
        return "archivio"
    if Path(origine).expanduser().is_dir():
        return "path"
    raise SourceError(f"Sorgente non riconosciuta o inesistente: {origine}")


def _materialize(tipo: str, origine: str, tmp: Path) -> Path:
    """Ritorna una directory locale con la code base (eventualmente in `tmp`)."""
    if tipo == "path":
        p = Path(origine).expanduser().resolve()
        if not p.is_dir():
            raise SourceError(f"Cartella inesistente: {p}")
        return p
    if tipo == "git":
        if shutil.which("git") is None:
            raise SourceError("git non è installato: impossibile clonare.")
        dest = tmp / "clone"
        r = subprocess.run(
            ["git", "clone", "--depth", "1", origine, str(dest)], capture_output=True, text=True
        )
        if r.returncode:
            raise SourceError(f"git clone fallito:\n{r.stderr.strip()}")
        return dest
    if tipo == "archivio":
        arc = Path(origine).expanduser().resolve()
        if not arc.is_file():
            raise SourceError(f"Archivio inesistente: {arc}")
        dest = tmp / "extract"
        dest.mkdir()
        if arc.name.lower().endswith(".zip"):
            with zipfile.ZipFile(arc) as z:
                for m in z.namelist():  # protezione path traversal
                    if Path(m).is_absolute() or ".." in Path(m).parts:
                        raise SourceError(f"Archivio con percorso non sicuro: {m}")
                z.extractall(dest)
        else:
            with tarfile.open(arc) as t:
                t.extractall(dest, filter="data")
        entries = [e for e in dest.iterdir() if e.name not in ("__MACOSX",)]
        if len(entries) == 1 and entries[0].is_dir():  # cartella radice unica
            return entries[0]
        return dest
    raise SourceError(f"Tipo di sorgente non valido: {tipo}")


def _spec(src: Path, esclusioni: list[str]) -> pathspec.PathSpec:
    lines = list(esclusioni)
    gi = src / ".gitignore"
    if gi.is_file():
        lines += gi.read_text(encoding="utf-8", errors="ignore").splitlines()
    try:
        return pathspec.PathSpec.from_lines("gitignore", lines)
    except Exception:  # pathspec < 0.12 non conosce "gitignore"
        return pathspec.PathSpec.from_lines("gitwildmatch", lines)


def _is_binary(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return b"\0" in f.read(8192)
    except OSError:
        return True


def collect(src: Path, esclusioni: list[str], max_file_kb: int) -> list[Path]:
    """File da copiare (percorsi relativi), rispettando .gitignore ed esclusioni."""
    spec = _spec(src, esclusioni)
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(src):
        rel_dir = Path(dirpath).relative_to(src)
        dirnames[:] = sorted(
            d for d in dirnames if not spec.match_file((rel_dir / d).as_posix() + "/")
        )
        for name in sorted(filenames):
            rel = rel_dir / name
            full = src / rel
            if full.is_symlink() or spec.match_file(rel.as_posix()):
                continue
            if full.stat().st_size > max_file_kb * 1024 or _is_binary(full):
                continue
            out.append(rel)
    return out


def _rmtree(path: Path) -> None:
    def onerror(func, p, _exc):
        os.chmod(p, stat.S_IWUSR | stat.S_IRUSR | stat.S_IXUSR)
        func(p)
    if path.exists():
        shutil.rmtree(path, onerror=onerror)


def snapshot(dest: Path) -> dict[str, str]:
    snap: dict[str, str] = {}
    if not dest.exists():
        return snap
    for p in sorted(dest.rglob("*")):
        if p.is_file():
            snap[p.relative_to(dest).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return snap


def import_source(sorgente: Sorgente, dest: Path) -> list[str]:
    """Copia la code base in `dest` sostituendo il contenuto. Ritorna i file copiati."""
    if sorgente.tipo == "nessuna" or not sorgente.origine:
        raise SourceError("Nessuna sorgente configurata in tesiflow.yaml (sezione `sorgente`).")
    with tempfile.TemporaryDirectory() as tmp:
        src = _materialize(sorgente.tipo, sorgente.origine, Path(tmp))
        files = collect(src, sorgente.esclusioni, sorgente.max_file_kb)
        _rmtree(dest)
        dest.mkdir(parents=True)
        for rel in files:
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src / rel, target)
            os.chmod(target, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)  # sola lettura
    return [f.as_posix() for f in files]


def diff_snapshots(old: dict[str, str], new: dict[str, str]) -> dict[str, list[str]]:
    return {
        "aggiunti": sorted(set(new) - set(old)),
        "rimossi": sorted(set(old) - set(new)),
        "modificati": sorted(k for k in old.keys() & new.keys() if old[k] != new[k]),
    }
