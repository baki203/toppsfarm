#!/usr/bin/env python3
"""Smyths Toys - Monitor + Checkout-Vorbereitung. Eigene Selektoren,
Filial- und Liefer-Verfuegbarkeit getrennt."""
from __future__ import annotations

import asyncio

from modules.Engine.Retail.retail_core import (RetailMonitor, RetailCheckout, RetailModule,
                                 State, Notifier, Settings, ENV)


class SmythsMonitor(RetailMonitor):
    name = "smyths"

    async def fetch(self, s, host):
        from modules.Engine.Shopify.shopify_core import base_headers
        import re
        items = []
        try:
            r = await s.get(f"https://{host}/sitemap.xml", headers=base_headers(self.cfg))
            if r.status_code != 200:
                return items
            for m in re.findall(r"<loc>([^<]+/product/[^<]+)</loc>", r.text):
                u = m.strip()
                if not u.startswith(f"https://{host}/"):
                    continue
                slug = u.split("/product/")[-1]
                items.append({"id": slug, "handle": slug,
                              "title": slug.replace("-", " ").title(),
                              "url": u})
        except Exception:
            pass
        return items


class SmythsCheckout(RetailCheckout):
    async def _locate_checkout(self, page):
        for sel in ('a[href*="/checkout"]', 'a[href*="/basket"]',
                    'button[data-testid*="checkout"]', 'button[data-testid*="basket"]'):
            loc = page.locator(sel).first
            if await loc.count():
                return await loc.get_attribute("href")
        return None


class SmythsModule(RetailModule):
    title = "Smyths Toys"
    hosts = ["www.smythstoys.com"]

    def make_monitor(self, cfg, state, notifier, hosts):
        return SmythsMonitor(cfg, state, notifier, hosts)

    def make_checkout(self, cfg, notifier):
        return SmythsCheckout(cfg, notifier, "smyths")


if __name__ == "__main__":
    import sys
    sys.exit(SmythsModule().run())
