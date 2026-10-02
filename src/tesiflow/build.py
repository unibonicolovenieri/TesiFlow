"""Wrapper di `latexmk -pdf` con riepilogo di errori, warning, riferimenti e TODO."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

ERR_RE = re.compile(r"^(?:\./)?([^\s:]+\.(?:tex|sty|cls|bib)):(\d+): (.*)$")


@dataclass
class BuildResult:
    returncode: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    undefined_refs: list[str] = field(default_factory=list)
    undefined_cites: list[str] = field(default_factory=list)
    bibtex: list[str] = field(default_factory=list)
    overfull: int = 0
    todos: dict[str, int] = field(default_factory=dict)
    cite_todos: int = 0
    pdf: Path | None = None
    raw_tail: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.errors


def scan_todos(root: Path) -> tuple[dict[str, int], int]:
    todos, cites = {}, 0
    for f in sorted(root.glob("*.tex")):
        text = f.read_text(encoding="utf-8", errors="ignore")
        n = len(re.findall(r"\bTODO\b", text))
        if n:
            todos[f.name] = n
        cites += len(re.findall(r"\\cite\w*\{[^}]*TODO-", text))
    return todos, cites


def parse_log(log: str, res: BuildResult) -> None:
    lines = log.splitlines()
    for i, line in enumerate(lines):
        m = ERR_RE.match(line)
        if m:
            res.errors.append(f"{m.group(1)}:{m.group(2)}: {m.group(3)}")
        elif line.startswith("! "):
            res.errors.append(line[2:])
        if "LaTeX Warning:" in line or "Package " in line and "Warning:" in line:
            msg = line.split("Warning:", 1)[1].strip()
            m2 = re.match(r"Reference `([^']+)'", msg)
            m3 = re.match(r"Citation `([^']+)'", msg)
            if m2:
                res.undefined_refs.append(m2.group(1))
            elif m3:
                res.undefined_cites.append(m3.group(1))
            elif not msg.startswith(
                ("There were undefined", "Label(s) may have changed", "Empty `thebibliography'")
            ):
                res.warnings.append(msg)
        if line.startswith("Overfull \\hbox"):
            res.overfull += 1


def run(root: Path, clean: bool = False) -> BuildResult:
    res = BuildResult()
    if clean:
        subprocess.run(["latexmk", "-C"], cwd=root, capture_output=True)
    proc = subprocess.run(
        ["latexmk", "-pdf", "-interaction=nonstopmode", "-file-line-error", "main.tex"],
        cwd=root, capture_output=True, text=True,
    )
    res.returncode = proc.returncode
    res.raw_tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-40:])
    log = root / "main.log"
    if log.exists():
        parse_log(log.read_text(encoding="utf-8", errors="ignore"), res)
    blg = root / "main.blg"
    if blg.exists():
        for line in blg.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith(("Warning--", "I couldn't open")):
                res.bibtex.append(line)
    # deduplica mantenendo l'ordine
    for attr in ("errors", "warnings", "undefined_refs", "undefined_cites", "bibtex"):
        setattr(res, attr, list(dict.fromkeys(getattr(res, attr))))
    res.todos, res.cite_todos = scan_todos(root)
    pdf = root / "main.pdf"
    res.pdf = pdf if pdf.exists() and res.returncode == 0 else None
    return res
