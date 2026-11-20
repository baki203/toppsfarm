"""InvitesTask - Skyridge-Muster: ein einzelner Vorgang fuer dieses Feature."""
from __future__ import annotations

from modules.base import BaseTask


class InvitesTask(BaseTask):
    async def startRequest(self) -> dict:
        fab = self.cfg.get("run_feature")
        if fab is None:
            return {"ok": False, "error": "kein run_feature gesetzt"}
        return await fab(self.cfg)