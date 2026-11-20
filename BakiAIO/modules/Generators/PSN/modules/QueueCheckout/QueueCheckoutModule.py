#!/usr/bin/env python3
"""PlayStation DE - Monitor (sitemap-Produkte) + Checkout-Vorbereitung.
Queue-it-Shop, Region de-de."""
from __future__ import annotations

import asyncio

from modules.Engine.Retail.retail_core import (RetailMonitor, RetailCheckout, RetailModule,
                                 State, Notifier, Settings, ENV, queued)


class PSNMonitor(RetailMonitor):
    name = "psn"
    DROP_MARKER = ("/buy-now/", "/register-to-buy/")

    async def fetch(self, s, host):
        import re
        from modules.Engine.Shopify.shopify_core import base_headers
        items = []
        try:
            idx = await s.get("https://www.playstation.com/sitemap_index.xml",
                              headers=base_headers(self.cfg))
            if idx.status_code != 200:
                return items
            sub = [l for l in re.findall(r"<loc>([^<]+)</loc>", idx.text)
                   if "/de-de/sitemap.xml" in l]
            if not sub:
                return items
            r = await s.get(sub[0], headers=base_headers(self.cfg))
            if r.status_code != 200:
                return items
            for m in re.findall(r"<loc>([^<]+)</loc>", r.text):
                u = m.strip()
                if not u.startswith("https://www.playstation.com/de-de/"):
                    continue
                if any(k in u for k in self.DROP_MARKER):
                    slug = u.rstrip("/").split("/de-de/")[-1]
                    items.append({"id": slug, "handle": slug,
                                  "title": slug.replace("-", " ").title(),
                                  "url": u})
        except Exception:
            pass
        return items


class PSNCheckout(RetailCheckout):
    async def _locate_checkout(self, page):
        for sel in ('a[href*="/checkout"]', 'a[href*="/cart"]',
                    'button[data-testid*="add-to-cart"]', 'button[data-testid*="buy"]'):
            loc = page.locator(sel).first
            if await loc.count():
                return await loc.get_attribute("href")
        return None


class PlayStationModule(RetailModule):
    title = "PlayStation DE"
    hosts = ["www.playstation.com"]

    def make_monitor(self, cfg, state, notifier, hosts):
        return PSNMonitor(cfg, state, notifier, hosts)

    def make_checkout(self, cfg, notifier):
        return PSNCheckout(cfg, notifier, "psn")


if __name__ == "__main__":
    import sys
    sys.exit(PlayStationModule().run())
