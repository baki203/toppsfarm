"""Zentrale Wurzel-Aufloesung.

Frozen (EXE): APP_ROOT = ROOT = Verzeichnis der EXE, NIE ein Elternpfad und
KEIN Walk ueber config/. Alle Daten (accounts, proxies, Address Toolbox,
settings.json, crashlog.log, var, FirstNames.txt, LastNames.txt) liegen relativ
zur EXE. Ungefroren (Quelle): APP_ROOT = Programmwurzel (BakiAIO\\), ROOT =
Repo-Wurzel (Walk bis config/ vorhanden).
"""
from __future__ import annotations

import sys
from pathlib import Path

_FROZEN = bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    """Programm-Wurzel. Frozen: immer das EXE-Verzeichnis."""
    if _FROZEN:
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent  # utilities/ -> BakiAIO\


def repo_root() -> Path:
    """Repo-/Daten-Wurzel. Frozen: identisch zur Programm-Wurzel (kein Walk).
    Ungefroren: Walk bis config/ gefunden."""
    if _FROZEN:
        return app_root()
    r = Path(__file__).resolve().parent.parent
    while not (r / "config").exists() and r.parent != r:
        r = r.parent
    return r


APP_ROOT = app_root()
ROOT = repo_root()


def ensure_runtime() -> Path:
    """Legt zur Laufzeit fehlende Ordner/Dateien relativ zu APP_ROOT an, statt
    zu crashen. -> Pfad zur crashlog.log."""
    for sub in ("accounts", "proxies", "Address Toolbox", "var"):
        (APP_ROOT / sub).mkdir(parents=True, exist_ok=True)
    crash = APP_ROOT / "crashlog.log"
    if not crash.exists():
        crash.write_text("", encoding="utf-8")
    return crash


def ensure_settings() -> bool:
    """Stellt settings.json sicher: fehlt sie, wird sie aus der mitgelieferten
    settings.example.json erzeugt (frisch) und der Nutzer mit Hinweis informiert.
    -> True wenn vorhanden/erzeugt, sonst False (beide Dateien fehlen)."""
    target = APP_ROOT / "settings.json"
    if target.exists():
        return True
    example = APP_ROOT / "settings.example.json"
    if example.exists():
        target.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        print(" settings.json fehlte - aus settings.example.json frisch erzeugt.")
        print(" Bitte Daten (Proxies, Mastermails, Keys) eintragen und neu starten.")
        return True
    print(" Warnung: weder settings.json noch settings.example.json gefunden.")
    return False