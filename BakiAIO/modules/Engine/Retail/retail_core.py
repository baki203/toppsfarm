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
            items = await self.fetch(s, host)
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