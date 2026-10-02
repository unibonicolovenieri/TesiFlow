"""Mappa statica del codice (senza indice RAG): alberatura, linguaggi, punti d'ingresso,
dipendenze, simboli principali. Scritta in `.claude/contesto/mappa-codebase.md`."""
from __future__ import annotations

import ast
import json
import re
import tomllib
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

LANGS = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript",
    ".tsx": "TypeScript", ".java": "Java", ".kt": "Kotlin", ".go": "Go", ".rs": "Rust",
    ".c": "C", ".h": "C/C++", ".cpp": "C++", ".hpp": "C++", ".cc": "C++", ".cs": "C#",
    ".rb": "Ruby", ".php": "PHP", ".swift": "Swift", ".scala": "Scala", ".sh": "Shell",
    ".sql": "SQL", ".html": "HTML", ".css": "CSS", ".yml": "YAML", ".yaml": "YAML",
    ".json": "JSON", ".toml": "TOML", ".md": "Markdown", ".m": "MATLAB/ObjC", ".r": "R",
    ".ipynb": "Notebook",
}
CODE_LANGS = {l for l in LANGS.values()} - {"YAML", "JSON", "TOML", "Markdown", "HTML", "CSS", "Notebook"}
ENTRY_NAMES = {
    "main.py", "__main__.py", "app.py", "manage.py", "wsgi.py", "asgi.py", "cli.py", "index.js",
    "index.ts", "main.js", "main.ts", "server.js", "server.ts", "app.js", "app.ts", "main.go",
    "main.rs", "lib.rs", "main.c", "main.cpp", "Main.java", "Application.java", "Program.cs",
    "Dockerfile", "docker-compose.yml", "Makefile",
}
MANIFESTS = {
    "requirements.txt", "pyproject.toml", "setup.py", "Pipfile", "package.json", "pom.xml",
    "build.gradle", "build.gradle.kts", "go.mod", "Cargo.toml", "Gemfile", "composer.json",
    "CMakeLists.txt", "environment.yml",
}
SYMBOL_RES = {
    ".js": r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(function\*?|class)\s+([A-Za-z_$][\w$]*)",
    ".ts": r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?(?:async\s+)?(function\*?|class|interface|enum)\s+([A-Za-z_$][\w$]*)",
    ".java": r"^\s*(?:public|protected|private)?\s*(?:abstract\s+|final\s+|static\s+)*(class|interface|enum|record)\s+(\w+)",
    ".kt": r"^\s*(?:\w+\s+)*(class|object|interface|fun)\s+(\w+)",
    ".go": r"^(func|type)\s+(?:\([^)]*\)\s*)?(\w+)",
    ".rs": r"^\s*(?:pub(?:\([^)]*\))?\s+)?(fn|struct|enum|trait|impl)\s+(\w+)",
    ".cs": r"^\s*(?:public|internal|private|protected)?\s*(?:static\s+|abstract\s+|sealed\s+)*(class|interface|enum|struct)\s+(\w+)",
    ".rb": r"^\s*(def|class|module)\s+([\w.?!]+)",
    ".php": r"^\s*(?:abstract\s+)?(function|class|interface|trait)\s+(\w+)",
    ".c": r"^[A-Za-z_][\w\s\*]*?\b()([A-Za-z_]\w*)\s*\([^;]*\)\s*\{?\s*$",
    ".cpp": r"^[A-Za-z_][\w:<>\s\*&]*?\b()([A-Za-z_][\w:]*)\s*\([^;]*\)\s*(?:const\s*)?\{?\s*$",
}
SYMBOL_RES[".jsx"] = SYMBOL_RES[".js"]
SYMBOL_RES[".tsx"] = SYMBOL_RES[".ts"]
SYMBOL_RES[".h"] = SYMBOL_RES[".c"]
SYMBOL_RES[".hpp"] = SYMBOL_RES[".cpp"]
SYMBOL_RES[".cc"] = SYMBOL_RES[".cpp"]
C_KEYWORDS = {"if", "for", "while", "switch", "return", "else", "sizeof", "catch"}

MAX_TREE_ENTRIES = 80
MAX_FILES_WITH_SYMBOLS = 120
MAX_SYMBOLS_PER_FILE = 25


def _files(src: Path) -> list[Path]:
    return sorted(p.relative_to(src) for p in src.rglob("*") if p.is_file())


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")


def _py_symbols(text: str) -> list[tuple[str, str, int, int]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(("funzione", node.name, node.lineno, node.end_lineno or node.lineno))
        elif isinstance(node, ast.ClassDef):
            out.append(("classe", node.name, node.lineno, node.end_lineno or node.lineno))
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append(("metodo", f"{node.name}.{sub.name}", sub.lineno, sub.end_lineno or sub.lineno))
    return out


def _regex_symbols(ext: str, text: str) -> list[tuple[str, str, int, int]]:
    pat = SYMBOL_RES.get(ext)
    if not pat:
        return []
    rx = re.compile(pat)
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        m = rx.match(line)
        if m:
            kind, name = m.group(1) or "funzione", m.group(2)
            if name in C_KEYWORDS:
                continue
            out.append((kind, name, n, n))
    return out


def symbols(path: Path, text: str) -> list[tuple[str, str, int, int]]:
    ext = path.suffix.lower()
    syms = _py_symbols(text) if ext == ".py" else _regex_symbols(ext, text)
    return syms[:MAX_SYMBOLS_PER_FILE]


def _tree(files: list[Path]) -> list[str]:
    counts: Counter[str] = Counter()
    for f in files:
        parts = f.parts
        for d in range(1, min(len(parts), 3)):
            counts["/".join(parts[:d])] += 1
    lines = []
    for d, n in sorted(counts.items())[:MAX_TREE_ENTRIES]:
        depth = d.count("/")
        lines.append(f"{'  ' * depth}{d.split('/')[-1]}/  ({n} file)")
    root_files = [f.name for f in files if len(f.parts) == 1]
    return [f"(radice): {', '.join(root_files[:25])}"] + lines


def _deps(src: Path, manifest: Path) -> list[str]:
    full, name = src / manifest, manifest.name
    text = _read(full)
    try:
        if name == "requirements.txt":
            return [l.strip() for l in text.splitlines() if l.strip() and not l.startswith(("#", "-"))][:40]
        if name == "package.json":
            d = json.loads(text)
            out = [f"{k} {v}" for k, v in list(d.get("dependencies", {}).items())[:40]]
            out += [f"(dev) {k}" for k in list(d.get("devDependencies", {}))[:15]]
            out += [f"script `{k}`: {v}" for k, v in list(d.get("scripts", {}).items())[:10]]
            return out
        if name == "pyproject.toml":
            d = tomllib.loads(text)
            return list(d.get("project", {}).get("dependencies", []))[:40]
        if name == "Cargo.toml":
            return list(tomllib.loads(text).get("dependencies", {}))[:40]
        if name == "go.mod":
            return [l.strip() for l in text.splitlines() if l.startswith("\t")][:40]
        if name == "pom.xml":
            return sorted(set(re.findall(r"<artifactId>([^<]+)</artifactId>", text)))[:40]
    except Exception:  # manifest malformato: ci si limita a elencarlo
        return []
    return []


def build(src: Path) -> str:
    if not src.is_dir() or not any(src.iterdir()):
        return "# Mappa della code base\n\n_`SourceCode/` è vuota: eseguire `tesiflow sync`._\n"
    files = _files(src)
    loc: Counter[str] = Counter()
    nfiles: Counter[str] = Counter()
    per_file_loc: dict[Path, int] = {}
    for f in files:
        lang = LANGS.get(f.suffix.lower())
        if not lang:
            continue
        n = _read(src / f).count("\n") + 1
        loc[lang] += n
        nfiles[lang] += 1
        per_file_loc[f] = n

    out = [
        "# Mappa della code base",
        "",
        f"> Generata automaticamente da `tesiflow map` ({date.today().isoformat()}) a partire da `SourceCode/`. "
        "Non modificare a mano: viene riscritta a ogni `tesiflow sync`/`map`. "
        "I numeri di riga si riferiscono ai file in `SourceCode/`.",
        "",
        f"File totali: {len(files)}",
        "",
        "## Linguaggi",
        "",
        "| Linguaggio | File | Righe |",
        "|---|---:|---:|",
    ]
    out += [f"| {l} | {nfiles[l]} | {n} |" for l, n in loc.most_common()]

    out += ["", "## Alberatura (fino a 3 livelli)", "", "```", *_tree(files), "```"]

    entries = [f for f in files if f.name in ENTRY_NAMES]
    out += ["", "## Punti d'ingresso (euristica sui nomi)", ""]
    out += [f"- `SourceCode/{e.as_posix()}`" for e in entries[:30]] or ["_nessuno riconosciuto_"]

    out += ["", "## Dipendenze dichiarate", ""]
    found = False
    for m in files:
        if m.name in MANIFESTS:
            found = True
            out.append(f"### `SourceCode/{m.as_posix()}`")
            deps = _deps(src, m)
            out += [f"- {d}" for d in deps] if deps else ["_(file di build: consultare direttamente)_"]
            out.append("")
    if not found:
        out.append("_nessun file di dipendenze riconosciuto_")

    out += ["", "## Moduli e simboli principali", "",
            "Formato: `riga-inizio–riga-fine` tipo nome (righe del file in `SourceCode/`). "
            "Per i linguaggi diversi da Python l'estrazione è euristica (solo riga di dichiarazione).", ""]
    code_files = sorted(
        (f for f in per_file_loc if LANGS.get(f.suffix.lower()) in CODE_LANGS),
        key=lambda f: -per_file_loc[f],
    )[:MAX_FILES_WITH_SYMBOLS]
    by_dir: dict[str, list[Path]] = defaultdict(list)
    for f in code_files:
        by_dir[f.parts[0] if len(f.parts) > 1 else "(radice)"].append(f)
    for d in sorted(by_dir):
        out.append(f"### {d}")
        for f in sorted(by_dir[d]):
            syms = symbols(f, _read(src / f))
            out.append(f"- `SourceCode/{f.as_posix()}` ({per_file_loc[f]} righe)")
            for kind, name, a, b in syms:
                rng = f"{a}–{b}" if b != a else f"{a}"
                out.append(f"  - {rng} {kind} `{name}`")
        out.append("")
    if len(per_file_loc) > MAX_FILES_WITH_SYMBOLS:
        out.append(f"_Mostrati i {MAX_FILES_WITH_SYMBOLS} file di codice più grandi._")
    return "\n".join(out).rstrip() + "\n"
