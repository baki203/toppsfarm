#!/usr/bin/env python3
"""Pokemon-Center-Modul: Monitor plus Checkout."""
from __future__ import annotations

import asyncio
import random
from pathlib import Path

from modules.topps import (State, Notifier, Solver, Settings, load_env,
                           session, base_headers, headers, queued)

ROOT = Path(__file__).resolve().parent.parent


class PokemonMonitor:
    """Pollt /products.json und die Produkt-Sitemap, meldet neue Produkte/Varianten."""

    def __init__(self, cfg: Settings, state: State, notifier: Notifier, hosts: list[str]):
        self.cfg, self.state, self.notifier = cfg, state, notifier
        self.hosts = hosts or ["www.pokemoncenter.com"]
        self.stop = asyncio.Event()
        self._seen: dict[str, set] = {}

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
        s = session(self.cfg)
        changed = False
        try:
            r = await s.get(f"https://{host}/products.json?limit=250",
                            headers=headers(self.cfg, host, True))
            if r.status_code == 200:
                for p in r.json().get("products", []):
                    changed |= await self._feed(host, p)
        except Exception as exc:
            print(f"[pokemon] {host}: {type(exc).__name__}")
        finally:
            await s.close()
        return changed

    async def _feed(self, host, p) -> bool:
        handle = p.get("handle", "")
        seen = self._seen.setdefault(host, set())
        fresh = handle and handle not in seen
        if fresh:
            seen.add(handle)
            title = p.get("title", "?")
            await self.notifier.send(f"NEU {title[:100]}", "new",
                                     {"Host": host, "Link": f"https://{host}/products/{handle}"})
            print(f"[pokemon] NEU {host} {title}")
        return fresh


class PokemonCheckout:
    """Browser-Checkout fuer eine Produkt-/Varianten-URL."""

    def __init__(self, cfg, notifier):
        self.cfg, self.notifier = cfg, notifier

    async def run(self, url: str, prof) -> dict:
        from core.browser import Browser
        from core.human import Human
        from core.identity import IdentityGenerator

        browser = Browser(headless=True, seed=random.randint(0, 2**31))
        await browser.start()
        res = {"ok": False, "note": "", "url": url, "order": None}
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            if queued(page.url, await page.content()):
                res["note"] = "queue"
                return res
            human = Human(7)
            ident = prof or IdentityGenerator(seed=7).generate()
            for sel, val in (('input[name="email"]', ident.email),
                             ('input[name="firstname"]', ident.first_name),
                             ('input[name="lastname"]', ident.last_name),
                             ('input[name="postalCode"]', ident.zip),
                             ('input[name="city"]', ident.city),
                             ('input[name="phone"]', ident.phone)):
                try:
                    loc = page.locator(sel).first
                    if await loc.count():
                        await human.type_text(page, sel, str(val))
                except Exception:
                    pass
            res.update(ok=True, note="checkout vorbereitet")
            return res
        finally:
            await browser.stop()


async def cmd_monitor(cfg, state, notifier, hosts):
    mon = PokemonMonitor(cfg, state, notifier, hosts)
    print(f"[pokemon] Monitor auf {len(hosts)} Host(s). Strg+C zum Stoppen.")
    try:
        await mon.run()
    except asyncio.CancelledError:
        pass


async def cmd_checkout(cfg, notifier, url, prof):
    res = await PokemonCheckout(cfg, notifier).run(url, prof)
    print(f"[pokemon] {res['ok']} {res['note']} {res['order'] or ''}")


class PokemonCenterModule:
    title = "Pokemon Center"

    def run(self):
        cfg = Settings.load()
        ENV = load_env()
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
                hosts = [h.strip() for h in input(" Hosts (kommagetrennt) [www.pokemoncenter.com]: ")
                         .split(",") if h.strip()] or ["www.pokemoncenter.com"]
                try:
                    asyncio.run(cmd_monitor(cfg, state, notifier, hosts))
                except KeyboardInterrupt:
                    print()
            elif wahl == "2":
                url = input(" URL: ").strip()
                if url:
                    try:
                        asyncio.run(cmd_checkout(cfg, notifier, url, None))
                    except KeyboardInterrupt:
                        print()


if __name__ == "__main__":
    import sys
    sys.exit(PokemonCenterModule().run())