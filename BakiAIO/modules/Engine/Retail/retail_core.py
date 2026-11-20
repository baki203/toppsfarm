#!/usr/bin/env python3
"""retail_core - gemeinsame Basis fuer Nicht-Shopify-Module (MediaMarkt, Saturn).
HTTP-first, Queue-it-Erkennung, hCaptcha via CapSolver, Browser-Checkout-Fallback."""
from __future__ import annotations

import asyncio
import random
from urllib.parse import urljoin

from modules.Engine.Shopify.shopify_core import (ROOT, ENV, CONSOLE, Settings, State, Notifier,
                                  Solver, session, headers, queued)
from modules.base import BaseModule
from modules.Engine.Retail.tasks import MonitorTask, CheckoutTask, build_checkout_tasks
from utilities.quality import Quality


class RetailMonitor:
    """Pollt Produkte eines MediaMarkt/Saturn-Shops ueber eine JSON-Liste bzw.
    Sitemap und meldet neue Artikel. Konkrete Quellen/Selektoren in der
    Unterklasse (self.fetch)."""

    def __init__(self, cfg: Settings, state: State, notifier: Notifier,
                 hosts: list[str], proxy: str | None = None):
        self.cfg, self.state, self.notifier = cfg, state, notifier
        self.hosts = hosts
        self.proxy = proxy
        self.stop = asyncio.Event()
        self._seen: dict[str, set] = {}
        self.q = Quality(self.name)

    @property
    def name(self):
        return "retail"

    async def run(self):
        await asyncio.gather(*(self._loop(h) for h in self.hosts))

    async def _loop(self, host):
        interval = self.cfg.poll_interval_s
        while not self.stop.is_set():
            changed = await self._poll(host)
            interval = max(1.5, interval * .75) if changed else min(20.0, interval * 1.05)
            try:
                await asyncio.wait_for(self.stop.wait(),
                                       timeout=interval + random.uniform(0, self.cfg.poll_jitter_s))
            except asyncio.TimeoutError:
                pass

    async def _poll(self, host) -> bool:
        s = session(self.cfg, self.proxy)
        changed = False
        try:
            self.q.increment("attempts")
            self._last_status = 0
            items = await self.fetch(s, host)
            # F: Cloudflare/Accountharvester-403 als banned:http zaehlen
            if getattr(self, "_last_status", 0) in (401, 403, 429):
                self.q.banned("http", str(getattr(self, "_last_status", 0)))
            for item in items:
                changed |= await self._feed(host, item)
        except Exception as exc:
            print(f"[{self.name}] {host}: {type(exc).__name__}")
            self.q.banned(str(exc))
        finally:
            await s.close()
        return changed

    async def fetch(self, s, host) -> list:
        """Unterklasse: -> Liste von (id, handle, title, price)."""
        return []

    async def _feed(self, host, item) -> bool:
        handle = item.get("handle", "")
        seen = self._seen.setdefault(host, set())
        fresh = handle and handle not in seen
        if fresh:
            seen.add(handle)
            title = item.get("title", "?")
            url = item.get("url", f"https://{host}/{handle}")
            await self.notifier.send(f"NEU {title[:100]}", "new",
                                     {"Host": host, "Link": url})
            print(f"[{self.name}] NEU {host} {title}")
        return fresh


class RetailCheckout:
    """Browser-Checkout: Oeffnet die Artikel-URL, uebersteht Queue-it und
    bereitet den Checkout vor. dry_run=True stoppt vor der Zahlung."""

    def __init__(self, cfg, notifier, name="retail"):
        self.cfg, self.notifier, self.name = cfg, notifier, name
        self.q = Quality(name)

    async def run(self, url: str, dry_run: bool = True, proxy: str | None = None) -> dict:
        from utilities.browser import Browser
        from utilities.human import Human
        browser = Browser(headless=True, seed=random.randint(0, 2**31),
                          proxy=proxy)
        await browser.start()
        res = {"ok": False, "note": "", "url": url, "order": None}
        self.q.increment("attempts")
        # A4: Geo-Pruefung gegen ship_country, sofern aktiviert
        if self.cfg.geo.get("enabled", False):
            from modules.Engine.Shopify.shopify_core import geo_check
            ok, hinweis = await geo_check(self.cfg, self._geo_profile(), proxy)
            if not ok:
                res.update(note=f"banned:geo ({hinweis})")
                self.q.banned("geo")
                return res
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            end = asyncio.get_event_loop().time() + float(self.cfg.queue.get("max_wait_s", 1800))
            while queued(page.url, await page.content()):
                if asyncio.get_event_loop().time() > end:
                    res["note"] = "queue"
                    return res
                await asyncio.sleep(float(self.cfg.queue.get("poll_s", 1.2)))
                await page.reload(wait_until="domcontentloaded", timeout=20000)
            # F: Consent-Wall automatisch wegklicken (falls vorhanden)
            await self._dismiss_consent(page)
            # JSON-LD-Preis/Lager separat auswerten
            try:
                ld = await self._jsonld(page)
                if ld:
                    res["price"] = ld.get("offers", {}).get("price") if isinstance(
                        ld.get("offers"), dict) else None
                    res["stock"] = ld.get("offers", {}).get("availability") if isinstance(
                        ld.get("offers"), dict) else None
            except Exception:
                pass
            # Warenkorb oeffnen bzw. den Checkout ansteuern (Selektor je Shop)
            target = await self._locate_checkout(page)
            if target:
                await page.goto(urljoin(page.url, target), wait_until="domcontentloaded",
                                timeout=45000)
            res.update(ok=True, url=page.url, note="checkout vorbereitet")
            self.q.success()
            return res
        except Exception as exc:
            self.q.banned(str(exc))
            res["note"] = type(exc).__name__
            return res
        finally:
            self.q.finish()
            await browser.stop()

    def _geo_profile(self):
        """Profile-Ersatz fuer die Geo-Pruefung (nur Land relevant)."""
        from modules.Engine.Shopify.shopify_core import Profile
        return Profile(id="retail", email="", first_name="", last_name="",
                       address1="", zip="", city="", country=self.cfg.ship_country)

    async def _dismiss_consent(self, page):
        """F: Cookie-Banner/Consent-Wall automatisch schliessen. Klickt den
        ersten passenden Ablehnen/Zustimmen/Schliessen-Knopf, sonst sPACE."""
        import json as _json
        # typische deutsche Consent-Banner-Muster
        for sel in ('button:has-text("Alle ablehnen")', 'button:has-text("Nur essenzielle")',
                    'button:has-text("Ablehnen")', 'button:has-text("Zustimmen")',
                    'button:has-text("Akzeptieren")', 'button:has-text("Accept all")',
                    'button:has-text("Accept")', 'button[aria-label*="consent" i]',
                    'button[aria-label*="cookie" i]', '#onetrust-reject-all-handler',
                    '#onetrust-accept-btn-handler', '.cookie-banner button',
                    '.consent button', '[class*="consent"] button',
                    '[class*="cookie"] button', '.cm-btn',
                    'button:has-text("Schliessen")', '.close', '[aria-label*="Schliessen" i]'):
            try:
                loc = page.locator(sel).first
                if await loc.count():
                    await loc.click(timeout=3000)
                    await page.wait_for_timeout(800)
                    # Banner weg?
                    try:
                        body = await page.content()
                        if ("consent" in body.lower() or "cookie" in body.lower()):
                            await page.keyboard.press("Escape")
                        return
                    except Exception:
                        return
            except Exception:
                continue
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass

    async def _jsonld(self, page) -> dict:
        """F: JSON-LD aus der Produktseite lesen -> {name, offers:{price, availability}}."""
        import json as _json
        try:
            content = await page.content()
        except Exception:
            return {}
        import re
        best = {}
        for m in re.finditer(r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
                             content, re.S):
            try:
                d = _json.loads(m.group(1))
            except Exception:
                continue
            if not isinstance(d, dict):
                continue
            g = d.get("@graph") or []
            for node in ([d] + (g if isinstance(g, list) else [])):
                if not isinstance(node, dict):
                    continue
                if node.get("@type") in ("Product", "ProductOffer", "Offer"):
                    off = node.get("offers") or node
                    price = off.get("price") or node.get("price")
                    av = off.get("availability") or node.get("availability")
                    best = {"name": node.get("name", ""),
                            "offers": {"price": price, "availability": av}}
                    break
            if best:
                break
        return best

    async def _locate_checkout(self, page) -> str | None:
        """Unterklasse kann den Checkout-Link/selektor bestimmen. None = aktuelle Seite."""
        return None


class RetailModule(BaseModule):
    """Untermenue fuer Retail-Module."""
    title = "Retail"

    def __init__(self, hosts=None):
        self.hosts = hosts or []

    def make_tasks(self, **cfg):
        if cfg.get("url"):
            return build_checkout_tasks(self.make_checkout, cfg.get("url"),
                                        cfg.get("dry_run", True))
        return [MonitorTask(make_monitor=lambda: self.make_monitor(
            Settings.load(), State(str(Settings.load().path(Settings.load().state_db))),
            Notifier(ENV.get("DISCORD_WEBHOOK", ""), ENV.get("DISCORD_WEBHOOK_ERRORS", "")),
            cfg.get("hosts", self.hosts)), max_retries=1)]

    def run(self):
        cfg = Settings.load()
        state = State(str(cfg.path(cfg.state_db)))
        notifier = Notifier(ENV.get("DISCORD_WEBHOOK", ""),
                            ENV.get("DISCORD_WEBHOOK_ERRORS", ""))
        while True:
            print(f"\n --- {self.title} ---")
            print("   1  Monitor starten")
            print("   2  Checkout (URL)")
            print("   0  Zurueck")
            try:
                wahl = input(" Auswahl: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if wahl == "0":
                return 0
            if wahl == "1":
                hosts = [h.strip() for h in
                         input(f" Hosts [{' '.join(self.hosts)}]: ").split(",")
                         if h.strip()] or self.hosts
                mon = self.make_monitor(cfg, state, notifier, hosts)
                print(f" [{self.title.lower()}] Monitor auf {len(hosts)} Host(s). "
                      "Strg+C zum Stoppen.")
                try:
                    asyncio.run(mon.run())
                except KeyboardInterrupt:
                    print()
                finally:
                    mon.q.finish()
            elif wahl == "2":
                url = input(" URL: ").strip()
                if url:
                    chk = self.make_checkout(cfg, notifier)
                    try:
                        res = asyncio.run(chk.run(url, dry_run=True))
                        print(f" [{self.title.lower()}] {res['ok']} "
                              f"{res['note']} {res['url']}")
                    except KeyboardInterrupt:
                        print()

    def make_monitor(self, cfg, state, notifier, hosts):
        return RetailMonitor(cfg, state, notifier, hosts)

    def make_checkout(self, cfg, notifier):
        return RetailCheckout(cfg, notifier, self.title.lower())