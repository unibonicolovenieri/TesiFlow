"""Verifica del compilatore LaTeX locale e dei pacchetti richiesti dallo scheletro."""
from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass, field

TOOLS = ["latexmk", "pdflatex", "bibtex", "makeindex"]
# File .sty usati da main.tex (devono esistere nella distribuzione TeX locale).
PACKAGES = [
    "babel.sty", "lmodern.sty", "microtype.sty", "geometry.sty", "setspace.sty",
    "amsmath.sty", "booktabs.sty", "listings.sty", "subcaption.sty", "tikz.sty",
    "nomencl.sty", "csquotes.sty", "hyperref.sty", "xcolor.sty", "caption.sty",
]


@dataclass
class Report:
    missing_tools: list[str] = field(default_factory=list)
    missing_packages: list[str] = field(default_factory=list)
    packages_checked: bool = False

    @property
    def ok(self) -> bool:
        return not self.missing_tools and not self.missing_packages


def check() -> Report:
    rep = Report(missing_tools=[t for t in TOOLS if shutil.which(t) is None])
    if shutil.which("kpsewhich"):
        rep.packages_checked = True
        for pkg in PACKAGES:
            out = subprocess.run(
                ["kpsewhich", pkg], capture_output=True, text=True
            ).stdout.strip()
            if not out:
                rep.missing_packages.append(pkg)
    return rep


def install_hint() -> str:
    system = platform.system()
    if system == "Darwin":
        return (
            "macOS: `brew install --cask mactex-no-gui` (distribuzione completa, consigliata)\n"
            "  oppure `brew install --cask basictex` e poi\n"
            "  `sudo tlmgr update --self && sudo tlmgr install latexmk collection-latexextra "
            "collection-fontsrecommended nomencl csquotes microtype`\n"
            "  Dopo l'installazione apri un nuovo terminale (serve `/Library/TeX/texbin` nel PATH)."
        )
    if system == "Linux":
        return (
            "Debian/Ubuntu: `sudo apt install latexmk texlive-latex-extra texlive-fonts-recommended "
            "texlive-lang-italian texlive-science` (oppure `texlive-full`)\n"
            "  Fedora: `sudo dnf install latexmk texlive-scheme-full`"
        )
    return "Windows: installa MiKTeX o TeX Live (https://miktex.org, https://tug.org/texlive) e Strawberry Perl per latexmk."


def format_report(rep: Report) -> str:
    lines = []
    if rep.missing_tools:
        lines.append("Strumenti LaTeX mancanti: " + ", ".join(rep.missing_tools))
    if rep.missing_packages:
        lines.append("Pacchetti LaTeX mancanti: " + ", ".join(rep.missing_packages))
    if lines:
        lines.append("Come installare:\n  " + install_hint())
    return "\n".join(lines)
