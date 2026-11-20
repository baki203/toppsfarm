"""Task-Basis fuer die Generator-Module (Konto anlegen) im Skyridge-Muster."""
from __future__ import annotations

import asyncio
from modules.base import BaseTask


class AccountGenTask(BaseTask):
    """Legt eine Anzahl Konten an. cfg erwartet: generator_factory() und count."""

    async def startRequest(self) -> dict:
        gen = self.cfg["generator_factory"]()
        n = await gen.run()
        return {"ok": True, "created": n}