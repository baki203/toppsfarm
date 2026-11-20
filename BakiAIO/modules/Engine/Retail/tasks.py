"""Gemeinsame Task-Basis fuer Retail-Module (Monitor/Checkout) im Skyridge-Muster."""
from __future__ import annotations

import asyncio
from modules.base import BaseTask


class MonitorTask(BaseTask):
    """Fuehrt den Monitor eines Retail-Shops aus. cfg erwartet:
    make_monitor() (Fabrik), hosts."""

    async def startRequest(self) -> dict:
        mon = self.cfg["make_monitor"]()
        try:
            await asyncio.wait_for(mon.run(), timeout=self.cfg.get("timeout_s", 0) or None)
        except asyncio.TimeoutError:
            pass
        return {"ok": True, "note": "monitor beendet"}


class CheckoutTask(BaseTask):
    """Checkout einer Retail-URL vorbereiten. cfg: make_checkout(), url, dry_run."""

    async def startRequest(self) -> dict:
        chk = self.cfg["make_checkout"]()
        res = await chk.run(self.cfg["url"], dry_run=self.cfg.get("dry_run", True))
        return res


def build_checkout_tasks(fabrik, url: str, dry_run: bool = True,
                         max_retries: int = 3) -> list[CheckoutTask]:
    return [CheckoutTask(make_checkout=fabrik, url=url, dry_run=dry_run,
                         max_retries=max_retries)]