"""CrashLogger - zeichnet unbehandelte Ausnahmen im crashlog.log auf."""
from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path


class CrashLogger:
    """Registriert sys.excepthook und schreibt Tracebacks nach crashlog.log."""

    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            path = Path(__file__).resolve().parent.parent.parent / "crashlog.log"
        self.path = Path(path)

    def _hook(self, typ, val, tb):
        try:
            with self.path.open("a", encoding="utf-8") as f:
                f.write("\n--- " + time.strftime("%Y-%m-%d %H:%M:%S") + " ---\n")
                traceback.print_exception(typ, val, tb, file=f)
        except Exception:
            pass
        traceback.print_exception(typ, val, tb)

    def install(self) -> None:
        sys.excepthook = self._hook