#!/usr/bin/env python3
"""Nike SNKRS - Monitor + Checkout-Vorbereitung. Akamai-geschuetzt,
Login noetig, Drop-Zeit steht auf der Produktseite, Browser zwingend."""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone

from modules.Engine.Retail.retail_core import (RetailMonitor, RetailCheckout, RetailModule,
                                 State, Notifier, Settings, ENV)


class SNKRSMonitor(RetailMonitor):
    name = "snkrs"

    async def fetch(self, s, host):
        items = []
        for url in (f"https://{host}/api/productfeed/v2/1/products?limit=100",
                    f"https://{host}/api/snkrs/v2/1/threads?limit=100"):
            try:
                r = await s.get(url)
                if r.status_code != 200:
                    continue
                data = r.json()
                blk = data.get("objects", data.get("threads", []))
                for p in (blk or []):
                    pid = p.get("id") or p.get("threadId")
                    title = p.get("title") or p.get("name") or ""
                    if not pid:
                        continue
                    # Drop-Zeit parsen, falls vorhanden
                    drop = ""
                    for key in ("launchDate", "goLiveTime", "productLaunchDate",
                                "productLaunchTime"):
                        if p.get(key):
                            try:
                                dt = datetime.fromisoformat(str(p[key]).replace("Z", "+00:00"))
                                drop = dt.astimezone().strftime("%Y-%m-%d %H:%M")
                            except Exception:
                                pass
                            break
                    items.append({"id": pid, "handle": str(pid), "title": title,
                                  "url": p.get("pdpUrl") or p.get("url") or "",
                                  "drop": drop})
                break
            except Exception:
                continue
        return items


class SNKRSCheckout(RetailCheckout):
    async def _locate_checkout(self, page):
        for sel in ('button[data-auto-id="add-to-cart"]',
                    'button[data-testid*="add-to-cart"]',
                    'a[data-auto-id="cart-link"]', 'a[data-testid*="cart"]',
                    'button:has-text("In den Warenkorb")'):
            loc = page.locator(sel).first
            if await loc.count():
                return await loc.get_attribute("href")
        return None


class SNKRSModule(RetailModule):
    title = "Nike SNKRS"
    hosts = ["www.nike.com"]

    def make_monitor(self, cfg, state, notifier, hosts):
        return SNKRSMonitor(cfg, state, notifier, hosts)

    def make_checkout(self, cfg, notifier):
        return SNKRSCheckout(cfg, notifier, "snkrs")


if __name__ == "__main__":
    import sys
    sys.exit(SNKRSModule().run())
