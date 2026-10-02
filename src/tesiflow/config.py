"""Modello di `tesiflow.yaml` e ricerca della radice del workspace."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

CONFIG_NAME = "tesiflow.yaml"

CAPITOLI_DEFAULT = {
    "it": [
        "Introduzione",
        "Contesto e stato dell'arte",
        "Requisiti e analisi",
        "Progettazione e architettura",
        "Implementazione",
        "Validazione e risultati",
    ],
    "en": [
        "Introduction",
        "Background and state of the art",
        "Requirements and analysis",
        "Design and architecture",
        "Implementation",
        "Validation and results",
    ],
}
TITOLO_CONCLUSIONI = {"it": "Conclusioni", "en": "Conclusions"}

ESCLUSIONI_DEFAULT = [
    ".git/", "node_modules/", "build/", "dist/", "target/", "out/", "bin/", "obj/",
    "__pycache__/", "*.pyc", ".venv/", "venv/", ".idea/", ".vscode/", ".gradle/",
    ".pytest_cache/", ".mypy_cache/", ".next/", ".DS_Store", "*.log",
    "*.lock", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "*.exe", "*.dll", "*.so", "*.dylib", "*.o", "*.a", "*.class", "*.jar", "*.war",
    "*.zip", "*.tar", "*.tar.*", "*.gz", "*.7z", "*.rar",
    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.ico", "*.pdf", "*.mp4", "*.mov",
    "*.sqlite", "*.db", "*.parquet", "*.h5", "*.pkl", "*.bin", "*.pt", "*.onnx",
]


class Tesi(BaseModel):
    candidato: str
    titolo: str
    argomento: str = ""
    azienda: str = ""
    ateneo: str
    relatore: str
    correlatore: str = ""
    anno_accademico: str
    lingua: Literal["it", "en"] = "it"
    pagine_target: int = 100


class Riservatezza(BaseModel):
    attiva: bool = False
    note: str = ""


class Sorgente(BaseModel):
    tipo: Literal["path", "git", "archivio", "nessuna"] = "nessuna"
    origine: str = ""
    esclusioni: list[str] = Field(default_factory=lambda: list(ESCLUSIONI_DEFAULT))
    max_file_kb: int = 1024


class Istruzioni(BaseModel):
    registro: str = "formale e impersonale"
    livello_dettaglio: str = "medio"
    lunghezza: str = ""
    regole_aggiuntive: list[str] = Field(default_factory=list)


class Config(BaseModel):
    versione: int = 1
    tesi: Tesi
    riservatezza: Riservatezza = Field(default_factory=Riservatezza)
    profilo: str = "magistrale"
    capitoli: list[str] = Field(default_factory=list)
    sorgente: Sorgente = Field(default_factory=Sorgente)
    istruzioni: Istruzioni = Field(default_factory=Istruzioni)

    @property
    def titolo_conclusioni(self) -> str:
        return TITOLO_CONCLUSIONI[self.tesi.lingua]


def load(root: Path) -> Config:
    data = yaml.safe_load((root / CONFIG_NAME).read_text(encoding="utf-8")) or {}
    return Config.model_validate(data)


def save(root: Path, cfg: Config) -> None:
    text = yaml.safe_dump(
        cfg.model_dump(), allow_unicode=True, sort_keys=False, width=100
    )
    (root / CONFIG_NAME).write_text(text, encoding="utf-8")


def find_root(start: Path | None = None) -> Path:
    cur = (start or Path.cwd()).resolve()
    for p in [cur, *cur.parents]:
        if (p / CONFIG_NAME).exists():
            return p
    raise FileNotFoundError(
        f"{CONFIG_NAME} non trovato: esegui il comando dentro un workspace TesiFlow."
    )
