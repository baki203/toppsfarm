#!/usr/bin/env python3
"""Nike Draw-Entry (LEO/DAN). Browser zwingend (Akamai/Kasada). Liest die
Drop-Zeit von der Produktseite, waehlt die Groesse und gibt den Entry ab.
Billing == Shipping, BPE vermeiden. Persistente Session je Konto
(var/browser-nike-<email>)."""
from __future__ import annotations

import asyncio
import random
import re
from datetime import datetime, timezone

from modules.Engine.Shopify.shopify_core import Settings, State, Notifier, ProxyPool
from utilities.browser import Browser
from utilities.human import Human
from utilities.quality import Quality

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def _slug_email(email: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "_", email)


def _load_accounts() -> list[dict]:
    """Nike-Konten aus accounts/Nike/*.txt (email/password)."""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
    d = root / "accounts" / "Nike"
    out = []
    if not d.exists():
        return out
    for f in sorted(d.glob("*.txt")):
        email = password = ""
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.lower().startswith("email:"):
                email = line.split(":", 1)[1].strip()
            elif line.lower().startswith("password:"):
                password = line.split(":", 1)[1].strip()
        if email and password:
            out.append({"email": email, "password": password})
    return out


def _parse_drop_time(text: str) -> str:
    """Drop-Zeit aus der Produktseite lesen (JSON-LD/meta/__NEXT_DATA__/Text).
    Liefert '%Y-%m-%d %H:%M' oder leer. Falls keine benannten Felder,
    wird die naechste zukuenftige ISO-Zeit genommen."""
    now = datetime.now().astimezone()
    for pat in (r'"launchDate"\s*:\s*"([^"]+)"',
                r'"goLiveTime"\s*:\s*"([^"]+)"',
                r'"productLaunchDate"\s*:\s*"([^"]+)"',
                r'"productLaunchTime"\s*:\s*"([^"]+)"',
                r'content="([0-9T:\-+\.]+)"[^>]*data-launch',
                r'"launchDate"\s*:\s*"([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:\.]+)'):
        m = re.search(pat, text)
        if m:
            raw = m.group(1)
            try:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                return dt.astimezone().strftime("%Y-%m-%d %H:%M")
            except Exception:
                continue
    # Fallback: naechste zukuenftige ISO-Zeit in __NEXT_DATA__/Text
    best = None
    for m in re.finditer(r"20\d\d-\d\d-\d\d[T ][0-9:\.]+(?:[+-]\d\d:\d\d|Z)?", text):
        raw = m.group(0).replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(raw)
            if dt.astimezone() > now and (best is None or dt < best):
                best = dt
        except Exception:
            continue
    return best.astimezone().strftime("%Y-%m-%d %H:%M") if best else ""


class DrawEntry:
    """Ein Account -> ein Entry. Login, Drop-Zeit, Groesse, Entry abgeben."""

    def __init__(self, url: str, size: str = "", wait_until: str = "",
                 headless: bool = True, proxy: str | None = None):
        self.url = url
        self.size = size
        self.wait_until = wait_until  # 'YYYY-MM-DD HH:MM' optional
        self.headless = headless
        self.proxy = proxy
        self.q = Quality("nikedraw")

    async def run(self, email: str, password: str) -> dict:
        from utilities.proxy import mask_proxy
        res = {"ok": False, "note": "", "url": self.url, "drop": "", "size": self.size}
        browser = Browser(headless=self.headless,
                          seed=random.randint(0, 2**31),
                          user_data_dir=f"var/browser-nike-{_slug_email(email)}",
                          proxy=self.proxy)
        await browser.start()
        self.q.increment("attempts")
        try:
            page = await browser.new_page()
            human = Human(self.seed)
            # Login (persistente Session)
            await page.goto("https://www.nike.com/de/launch/join",
                            wait_until="domcontentloaded", timeout=45000)
            logged = await self._login(page, email, password)
            res["note"] = "login" if not logged else ""
            if not logged:
                return res
            # Produktseite, Drop-Zeit lesen
            await page.goto(self.url, wait_until="domcontentloaded", timeout=45000)
            content = await page.content()
            drop = _parse_drop_time(content)
            res["drop"] = drop
            # Optional bis Entry-Zeit warten
            if self.wait_until:
                await self._wait_until(self.wait_until, page)
                await page.reload(wait_until="domcontentloaded", timeout=45000)
            # Groesse waehlen
            await human.move_mouse(page)
            size = await self._select_size(page)
            res["size"] = size
            # Entry-Button
            entered = await self._submit_entry(page, human)
            res["ok"] = entered
            res["note"] = "entry abgegeben" if entered else "kein entry-button"
            if entered:
                self.q.success()
            else:
                self.q.banned("no entry button")
            return res
        except Exception as exc:
            self.q.banned(type(exc).__name__)
            res["note"] = type(exc).__name__
            return res
        finally:
            self.q.finish()
            await browser.stop()

    @property
    def seed(self):
        return 1337

    async def _login(self, page, email: str, password: str) -> bool:
        try:
            # falls bereits eingeloggt (persistente Session), Seitenaufruf reicht
            if "join" in page.url and await self._is_logged_in(page):
                return True
            # Login-Link
            for sel in ('a[href*="login"]', 'a[href*="signin"]',
                        'button:has-text("Anmelden")', 'button:has-text("Login")'):
                loc = page.locator(sel).first
                if await loc.count():
                    await loc.click(timeout=8000)
                    break
            await page.wait_for_timeout(2500)
            el = page.locator('input[type="email"],input[name="emailAddress"]').first
            if await el.count():
                await el.fill(email, timeout=8000)
            for sel in ('button[type="submit"]', 'button:has-text("Weiter")'):
                b = page.locator(sel).first
                if await b.count():
                    await b.click(timeout=8000)
                    break
            await page.wait_for_timeout(2500)
            pw = page.locator('input[type="password"],input[name="password"]').first
            if await pw.count():
                await pw.fill(password, timeout=8000)
            for sel in ('button[type="submit"]', 'button:has-text("Anmelden")'):
                b = page.locator(sel).first
                if await b.count():
                    await b.click(timeout=8000)
                    break
            await page.wait_for_timeout(4000)
            return await self._is_logged_in(page)
        except Exception:
            return False

    async def _is_logged_in(self, page) -> bool:
        try:
            body = (await page.content()).lower()
            return ("abmelden" in body or "logout" in body or "mein konto" in body
                    or "account" in body and "signin" not in page.url.lower())
        except Exception:
            return False

    async def _wait_until(self, when: str, page):
        target = datetime.strptime(when, "%Y-%m-%d %H:%M").astimezone()
        while datetime.now().astimezone() < target:
            await asyncio.sleep(5)
        await page.bring_to_front()

    async def _select_size(self, page) -> str:
        sel = self.size
        if not sel:
            # zufaellige verfuegbare Groesse
            btns = page.locator('button[aria-label*="Groesse" i],'
                                'label[for*="size"],button:has-text("EU")')
            try:
                n = await btns.count()
                if n:
                    return ""
            except Exception:
                pass
            return ""
        for sels in (f'button[data-value="{sel}"]', f'button:has-text("{sel}")',
                     f'label:has-text("{sel}")'):
            loc = page.locator(sels).first
            if await loc.count():
                try:
                    await loc.click(timeout=8000)
                except Exception:
                    pass
                return sel
        return ""

    async def _submit_entry(self, page, human) -> bool:
        # entry/jetzt kaufen/teilnehmen
        for sel in ('button[data-auto-id="draw-entry"]', 'button:has-text("Am Draw teilnehmen")',
                    'button:has-text("Jetzt teilnehmen")', 'button:has-text("Entry")',
                    'button[data-auto-id="buy-ticket"]',
                    'button:has-text("Jetzt kaufen")', 'button[data-auto-id="add-to-cart"]'):
            loc = page.locator(sel).first
            if await loc.count():
                try:
                    await human.move_mouse(page)
                    await loc.click(timeout=10000)
                except Exception:
                    pass
                await page.wait_for_timeout(3000)
                return True
        return False


class DrawEntryModule:
    """Nike Draw-Entry Modul. Konten aus accounts/Nike/*.txt."""

    title = "Nike Draw-Entry (LEO/DAN)"

    def run(self):
        import sys
        url = input("  Produkt-URL: ").strip()
        if not url:
            print("  keine URL.")
            return 0
        size = input("  Groesse (leer = zufaellig) [42]: ").strip() or ""
        wait = input("  Entry-Zeit (YYYY-MM-DD HH:MM, leer = sofort): ").strip()
        headless = input("  Headless (j/n) [j]: ").strip().lower() != "n"
        accounts = _load_accounts()
        if not accounts:
            print("  keine Nike-Konten unter accounts/Nike/*.txt")
            return 0
        cfg = Settings.load()
        pool = ProxyPool(State(str(cfg.path(cfg.state_db))), "nike")
        for acc in accounts:
            proxy = asyncio.run(pool.acquire())
            de = DrawEntry(url, size=size, wait_until=wait, headless=headless, proxy=proxy)
            try:
                res = asyncio.run(de.run(acc["email"], acc["password"]))
                print(f"  [{acc['email']}] ok={res['ok']} {res['note']} "
                      f"drop={res['drop']} size={res['size']}")
            except KeyboardInterrupt:
                print("\n abgebrochen.")
                break
        return 0


if __name__ == "__main__":
    import sys
    sys.exit(DrawEntryModule().run())