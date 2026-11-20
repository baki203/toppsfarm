"""DropTask - ein Topps-Drop auf einer Variante (Skyridge-Muster).

Kapselt die Shopify-Drop-Logik. cfg erwartet: run_drop() (Coroutine-Fabrik)
oder die Standard-Parameter host/variant/tasks/qty/mode.
"""
from __future__ import annotations

from modules.base import BaseTask


class DropTask(BaseTask):
    async def startRequest(self) -> dict:
        run_drop = self.cfg.get("run_drop")
        if run_drop is None:
            return {"ok": False, "error": "kein run_drop gesetzt"}
        return await run_drop(
            host=self.cfg.get("host"),
            variant=self.cfg.get("variant"),
            tasks=self.cfg.get("tasks", 1),
            qty=self.cfg.get("qty", 1),
            mode=self.cfg.get("mode", "cart"),
        )