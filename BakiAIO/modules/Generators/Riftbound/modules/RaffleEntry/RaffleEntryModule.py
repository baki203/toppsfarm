#!/usr/bin/env python3
"""Riftbound-Account-Generator (riftbound.com), analog zu Amazon/Nike."""
from __future__ import annotations

import asyncio
from modules.base import BaseModule
from modules.Generators.Riftbound.modules.RaffleEntry.RaffleEntryTask import RaffleEntryTask
from modules.account_base import AccountGenerator, run_generator


class RiftboundGen(AccountGenerator):
    site = "riftbound"
    signup_url = "https://riftbound.com/register"
    account_dir = "accounts/Riftbound"


class RiftboundModule(BaseModule):
    title = "Riftbound Account Generator"

    def make_tasks(self, **cfg):
        return [RaffleEntryTask(run_feature=self._run, count=cfg.get("count", 1),
                                headless=cfg.get("headless", True))]

    async def _run(self, cfg):
        gen = RiftboundGen(count=cfg.get("count", 1), headless=cfg.get("headless", True))
        n = await gen.run()
        return {"ok": True, "created": n}

    def run(self):
        try:
            n = int(input(" Anzahl Konten [1]: ").strip() or "1")
        except ValueError:
            n = 1
        headless = input(" Headless (j/n) [j]: ").strip().lower() != "n"
        try:
            res = asyncio.run(self.runTask(count=n, headless=headless))
            print(f" {res[0].get('created', 0)} Konto(en) erstellt" if res else " kein Ergebnis")
        except KeyboardInterrupt:
            print("\n abgebrochen.")


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(run_generator(RiftboundGen(count=1, headless=True))))