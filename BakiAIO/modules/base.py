"""Basisklassen im Skyridge-Muster.

Module orchestrieren (``runTask`` erzeugt Tasks und steuert Retry/Sammeln),
Tasks fuehren einen einzelnen Vorgang aus (``__init__`` -> ``startRequest`` ->
``_preCheck``). ``startRequest`` implementiert die Unterklasse, ``_preCheck``
prueft Vorbedingungen und wird vor dem Start aufgerufen.
"""
from __future__ import annotations

import time
from typing import Any


class BaseTask:
    """Ein einzelner Vorgang (Konto/Profil/Drop). Retry-Schleife in runTask."""

    def __init__(self, **cfg: Any) -> None:
        self.cfg = cfg
        self.max_retries = int(cfg.get("max_retries", 3))
        self.retry_backoff_s = float(cfg.get("retry_backoff_s", 1.5))
        self.result: dict = {}

    def _preCheck(self) -> str | None:
        """Vorbedingungen pruefen. Rueckgabe: Fehlermeldung oder None=ok."""
        return None

    async def startRequest(self) -> dict:
        raise NotImplementedError

    async def runTask(self) -> dict:
        """Vorpruefung, dann startRequest mit Retry."""
        err = self._preCheck()
        if err:
            self.result = {"ok": False, "error": err}
            return self.result
        last = None
        for attempt in range(1, self.max_retries + 1):
            try:
                self.result = await self.startRequest()
                if self.result.get("ok"):
                    return self.result
                last = self.result.get("error") or "unbekannter Fehler"
            except Exception as exc:
                last = f"{type(exc).__name__}: {exc}"
            if attempt < self.max_retries:
                time.sleep(self.retry_backoff_s * attempt)
        self.result = {"ok": False, "error": str(last)}
        return self.result


class BaseModule:
    """Orchestrator: erzeugt Tasks und steuert die Ausfuehrung."""

    title: str = "Modul"

    def run(self) -> None:
        raise NotImplementedError

    def make_tasks(self, **cfg: Any) -> list[BaseTask]:
        raise NotImplementedError

    async def runTask(self, task: BaseTask | None = None, **cfg: Any) -> list[dict]:
        """Fuehrt alle Tasks (oder einen einzelnen) aus und sammelt Ergebnisse."""
        tasks = [task] if task is not None else self.make_tasks(**cfg)
        out: list[dict] = []
        for t in tasks:
            out.append(await t.runTask())
        return out
