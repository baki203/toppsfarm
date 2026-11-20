"""Topps als Baki-AIO-Modul. Die Logik liegt unveraendert in modules/topps.py."""
from __future__ import annotations

from modules.base import Action, Module


class ToppsModule(Module):
    key = "topps"
    title = "Topps EU"
    # Dieselben Punkte und Argumente wie im alten START.bat-Menue.
    actions = [
        Action("Topps  Selftest", ["selftest"]),
        Action("Topps  Watch - Cart-Links (wenig Daten)", ["watch", "--mode", "cart"]),
        Action("Topps  Watch - mit Browser", ["watch", "--mode", "browser"]),
        Action("Topps  Drop auf Variante", ["drop", "--mode", "cart"],
               [("--host", "Host"), ("--variant", "Variant-ID"), ("--tasks", "Tasks")]),
        Action("Topps  Profile pruefen", ["profiles-check"]),
        Action("Topps  Statistik", ["stats"]),
        Action("Topps  Setup erneut ausfuehren", ["setup"]),
        Action("Topps  Browser-Engine installieren", ["install-browser"]),
    ]

    def run(self, argv: list | None = None) -> int:
        from modules import topps
        try:
            topps.main(list(argv or []))
        except KeyboardInterrupt:
            topps.CONSOLE.print("[yellow]abgebrochen[/]")
            return 130
        except SystemExit as e:  # argparse (--help, falsche Argumente)
            return e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        return 0
