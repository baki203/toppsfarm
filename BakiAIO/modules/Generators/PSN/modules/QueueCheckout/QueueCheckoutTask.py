"""QueueCheckoutTask - PSN: Login + Queue + Checkout vorbereiten."""
from __future__ import annotations

from modules.base import BaseTask


class QueueCheckoutTask(BaseTask):
    async def startRequest(self) -> dict:
        fab = self.cfg.get("run_checkout")
        if fab is None:
            return {"ok": False, "error": "kein run_checkout gesetzt"}
        return await fab(self.cfg.get("url"), dry_run=self.cfg.get("dry_run", True))