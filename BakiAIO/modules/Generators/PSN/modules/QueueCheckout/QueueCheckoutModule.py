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
    def __init__(self, cfg, notifier, name="psn", user_data_dir=None):
        super().__init__(cfg, notifier, name)
        self.user_data_dir = user_data_dir or f"var/browser-{name}"

    async def login(self, email: str, password: str, proxy: str | None = None) -> dict:
        """Loggt im persistenten Browser-Context ein. Gibt zurueck, ob eine
        Login-Interaktion noetig war und ob die Session (cookie) aktiv ist."""
        from utilities.browser import Browser
        import random
        browser = Browser(headless=not self.cfg.geo.get("headful", False),
                          seed=random.randint(0, 2**31),
                          user_data_dir=self.user_data_dir)
        await browser.start()
        res = {"logged_in": False, "login_performed": False, "note": "", "url": ""}
        try:
            page = await browser.new_page()
            await page.goto("https://www.playstation.com/de-de/",
                            wait_until="domcontentloaded", timeout=45000)
            # Login-Seite der Sony-Konto-Verwaltung
            await page.goto("https://ca.account.sony.com/login/v2/ssocookie?service=sce",
                            wait_until="domcontentloaded", timeout=45000)
            # Eingeloggt? (ssocookie-Redirect weg vom Login-Formular)
            await page.wait_for_timeout(2500)
            if "/login" not in page.url.lower():
                res.update(logged_in=True, url=page.url,
                           note="session vorhanden (kein Login noetig)")
                return res
            # Email
            sel_email = 'input[type="email"],input[name*="email" i]'
            loc = page.locator(sel_email).first
            if await loc.count():
                await loc.fill(email, timeout=8000)
            # Weiter / Passwort
            for sel_next in ('button:has-text("Weiter")', 'button[type="submit"]'):
                nxt = page.locator(sel_next).first
                if await nxt.count():
                    await nxt.click(timeout=8000)
                    break
            await page.wait_for_timeout(2500)
            sel_pw = 'input[type="password"],input[name*="password" i]'
            loc = page.locator(sel_pw).first
            if await loc.count():
                await loc.fill(password, timeout=8000)
            for sel_sub in ('button:has-text("Anmelden")', 'button[type="submit"]'):
                sub = page.locator(sel_sub).first
                if await sub.count():
                    await sub.click(timeout=8000)
                    break
            await page.wait_for_timeout(4000)
            res.update(login_performed=True, url=page.url,
                       note="session gespeichert" if "/login" not in page.url.lower()
                       else "login moeglicherweise fehlgeschlagen")
            res["logged_in"] = "/login" not in page.url.lower()
            return res
        except Exception as exc:
            res.update(note=type(exc).__name__)
            return res
        finally:
            await browser.stop()

    async def run(self, url: str, dry_run: bool = True, email: str | None = None,
                  password: str | None = None) -> dict:
        if email and password:
            li = await self.login(email, password)
            if not li["logged_in"] and not dry_run:
                return {"ok": False, "note": "login fehlgeschlagen",
                        "url": li.get("url", "")}
        return await super().run(url, dry_run=dry_run)

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

    def run(self):
        import sys
        import asyncio
        cfg = Settings.load()
        state = State(str(cfg.path(cfg.state_db)))
        notifier = Notifier(ENV.get("DISCORD_WEBHOOK", ""),
                            ENV.get("DISCORD_WEBHOOK_ERRORS", ""))
        while True:
            print(f"\n --- {self.title} ---")
            print("   1  Monitor starten")
            print("   2  Checkout (URL)")
            print("   3  Login (PSN-Konto)")
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
                print(f" [psn] Monitor auf {len(hosts)} Host(s). Strg+C zum Stoppen.")
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
                        print(f" [psn] {res['ok']} {res['note']} {res['url']}")
                    except KeyboardInterrupt:
                        print()
            elif wahl == "3":
                email = input(" PSN-Email: ").strip()
                password = input(" PSN-Passwort: ").strip()
                if email and password:
                    chk = self.make_checkout(cfg, notifier)
                    try:
                        res = asyncio.run(chk.login(email, password))
                        print(f" [psn] logged_in={res['logged_in']} "
                              f"{res['note']} {res['url']}")
                    except KeyboardInterrupt:
                        print()


if __name__ == "__main__":
    import sys
    sys.exit(PlayStationModule().run())
