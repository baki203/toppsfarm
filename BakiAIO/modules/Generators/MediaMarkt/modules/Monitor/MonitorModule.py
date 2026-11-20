#!/usr/bin/env python3
"""MediaMarkt DE - Monitor + Checkout-Vorbereitung (retail_core-Basis)."""
from __future__ import annotations

from modules.Engine.Retail.retail_core import (RetailMonitor, RetailCheckout, RetailModule,
                                 State, Notifier, Settings, ENV, queued)


class MediaMarktMonitor(RetailMonitor):
    name = "mediamarkt"

    async def fetch(self, s, host):
        import re
        from modules.Engine.Shopify.shopify_core import base_headers
        items = []
        try:
            idx = await s.get(f"https://{host}/sitemaps/sitemap-index.xml",
                              headers=base_headers(self.cfg))
            if idx.status_code != 200:
                return items
            subs = [l for l in re.findall(r"<loc>([^<]+)</loc>", idx.text)
                    if "productdetailspages" in l][-1:]
            for sub in subs:
                r = await s.get(sub, headers=base_headers(self.cfg))
                if r.status_code != 200:
                    continue
                for m in re.findall(r"<loc>([^<]+/de/product/[^<]+)</loc>", r.text)[-200:]:
                    u = m.strip()
                    slug = u.split("/de/product/")[-1].replace(".html", "")
                    items.append({"id": slug, "handle": slug,
                                  "title": slug.rsplit("-", 1)[0].replace("-", " ").title(),
                                  "url": u})
        except Exception:
            pass
        return items


class MediaMarktCheckout(RetailCheckout):
    async def _locate_checkout(self, page):
        for sel in ('a[href*="/checkout"]', 'a[href*="/warenkorb"]',
                    'button[data-testid*="checkout"]', 'button[data-testid*="cart"]'):
            loc = page.locator(sel).first
            if await loc.count():
                return await loc.get_attribute("href")
        return None


class MediaMarktModule(RetailModule):
    title = "MediaMarkt"
    hosts = ["www.mediamarkt.de"]

    def make_monitor(self, cfg, state, notifier, hosts):
        return MediaMarktMonitor(cfg, state, notifier, hosts)

    def make_checkout(self, cfg, notifier):
        return MediaMarktCheckout(cfg, notifier, "mediamarkt")


if __name__ == "__main__":
    import sys
    sys.exit(MediaMarktModule().run())
