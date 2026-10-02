"""Rendering dei template e scrittura sicura (mai sovrascrivere lavoro dell'utente)."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, PackageLoader, StrictUndefined

TEX_SPECIAL = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}
MANIFEST = Path(".tesiflow") / "manifest.json"


def tex_escape(value: object) -> str:
    return "".join(TEX_SPECIAL.get(c, c) for c in str(value))


def slugify(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", norm.lower()).strip("-") or "capitolo"


def _env(tex: bool) -> Environment:
    kw = dict(
        loader=PackageLoader("tesiflow", "templates"),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    if tex:  # delimitatori che non collidono con la sintassi LaTeX
        kw.update(
            variable_start_string="<<", variable_end_string=">>",
            block_start_string="<%", block_end_string="%>",
            comment_start_string="<#", comment_end_string="#>",
        )
    env = Environment(**kw)
    env.filters["tex"] = tex_escape
    env.filters["slug"] = slugify
    return env


_ENV_TEX, _ENV_MD = _env(True), _env(False)


def render(template: str, **ctx) -> str:
    env = _ENV_TEX if template.startswith("latex/") else _ENV_MD
    return env.get_template(template).render(**ctx)


# --- blocchi gestiti / personalizzati --------------------------------------------

def _markers(name: str, comment: str) -> tuple[str, str]:
    if comment == "html":
        return f"<!-- TESIFLOW:{name}:BEGIN -->", f"<!-- TESIFLOW:{name}:END -->"
    return f"% TESIFLOW:{name}:BEGIN", f"% TESIFLOW:{name}:END"


def get_block(text: str, name: str, comment: str = "html") -> str | None:
    b, e = _markers(name, comment)
    m = re.search(re.escape(b) + r"\n(.*?)" + re.escape(e), text, re.S)
    return m.group(1) if m else None


def set_block(text: str, name: str, content: str, comment: str = "html") -> str:
    b, e = _markers(name, comment)
    pat = re.compile(re.escape(b) + r"\n.*?" + re.escape(e), re.S)
    repl = b + "\n" + content + e
    return pat.sub(lambda _m: repl, text, count=1)


# --- scrittura sicura ----------------------------------------------------------

def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _manifest(root: Path) -> dict:
    p = root / MANIFEST
    return json.loads(p.read_text()) if p.exists() else {}


def _save_manifest(root: Path, data: dict) -> None:
    p = root / MANIFEST
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=True))


def backup(root: Path, rel: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = root / ".tesiflow" / "backup" / stamp / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / rel, dest)
    return dest


def write_file(root: Path, rel: str, content: str, mode: str = "create") -> str:
    """Scrive `content` in `rel`.

    mode:
      create  - crea solo se manca (file di lavoro dell'utente: capitoli, stato, ...)
      managed - rigenera; se l'utente ha modificato il file ne fa prima un backup
    Ritorna: creato | invariato | aggiornato | saltato | aggiornato (backup in ...)
    """
    path = root / rel
    man = _manifest(root)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        man[rel] = sha(content)
        _save_manifest(root, man)
        return "creato"
    current = path.read_text(encoding="utf-8")
    if current == content:
        man[rel] = sha(content)
        _save_manifest(root, man)
        return "invariato"
    if mode == "create":
        return "saltato"
    note = "aggiornato"
    if man.get(rel) != sha(current):  # modificato a mano dopo l'ultima generazione
        note = f"aggiornato (backup in {backup(root, rel).relative_to(root)})"
    path.write_text(content, encoding="utf-8")
    man[rel] = sha(content)
    _save_manifest(root, man)
    return note
