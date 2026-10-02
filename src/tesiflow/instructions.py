"""Modifica guidata delle istruzioni dell'agente e dei profili."""
from __future__ import annotations

from .config import Config
from .scaffold import load_profile


def apply_profile(cfg: Config, name: str, *, keep_pages: bool = False) -> Config:
    """Applica un profilo a cfg: istruzioni, riservatezza (se prevista), pagine."""
    prof = load_profile(name)
    cfg.profilo = name
    for k, v in prof.get("istruzioni", {}).items():
        setattr(cfg.istruzioni, k, v)
    if "riservatezza" in prof:
        cfg.riservatezza.attiva = prof["riservatezza"].get("attiva", cfg.riservatezza.attiva)
        if not cfg.riservatezza.note:
            cfg.riservatezza.note = prof["riservatezza"].get("note", "")
    if not keep_pages and "pagine_target" in prof:
        cfg.tesi.pagine_target = prof["pagine_target"]
    return cfg


def summary(cfg: Config) -> str:
    i, r = cfg.istruzioni, cfg.riservatezza
    rules = "\n".join(f"    {n}. {x}" for n, x in enumerate(i.regole_aggiuntive, 1)) or "    (nessuna)"
    return (
        f"Profilo: {cfg.profilo}\n"
        f"Registro: {i.registro}\n"
        f"Livello di dettaglio: {i.livello_dettaglio}\n"
        f"Lunghezza: {i.lunghezza or '(non indicata)'}\n"
        f"Riservatezza: {'ATTIVA — ' + (r.note or 'nessuna nota') if r.attiva else 'non attiva'}\n"
        f"Regole aggiuntive:\n{rules}"
    )
