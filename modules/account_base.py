"""Gemeinsame Basis fuer die Account-Generatoren (Nike/Amazon/Riftbound)."""
from __future__ import annotations

import asyncio
import random
from pathlib import Path

from core.browser import Browser
from core.human import Human
from core.identity import IdentityGenerator
from core.mailbox import create_inbox, wait_for_link

ROOT = Path(__file__).resolve().parent.parent


class AccountGenerator:
    """Erzeugt `count` Konten: Identitaet + Postfach + Browser-Registrierung.
    Unterklassen setzen `site`, `signup_url` und `account_dir`."""

    site: str
    signup_url: str
    account_dir: str

    def __init__(self, count: int = 1, headless: bool = True, seed: int | None = None):
        self.count = count
        self.headless = headless
        self.seed = seed if seed is not None else random.SystemRandom().randint(0, 2**31)
        self.idgen = IdentityGenerator(seed=self.seed)

    async def run(self) -> list[str]:
        d = ROOT / self.account_dir
        d.mkdir(parents=True, exist_ok=True)
        made = []
        browser = Browser(user_data_dir=str(ROOT / "var" / f"browser-{self.site}"),
                          headless=self.headless, seed=self.seed)
        await browser.start()
        try:
            for _ in range(self.count):
                ident = self.idgen.generate()
                inbox = await create_inbox()
                account = await self._register(browser, ident, inbox)
                f = d / f"{ident.email}.txt"
                f.write_text(_dump(account), encoding="utf-8")
                made.append(str(f))
                print(f"[{self.site}] angelegt: {ident.email} -> {f.name}")
        finally:
            await browser.stop()
        return made

    async def _register(self, browser: Browser, ident, inbox: dict) -> dict:
        human = Human(self.seed)
        page = await browser.new_page()
        try:
            await page.goto(self.signup_url, wait_until="domcontentloaded", timeout=45000)
            await human.move_mouse(page)
            await asyncio.sleep(random.uniform(.5, 1.2))

            fields = self._fields(inbox, ident)
            for sel, val in fields:
                try:
                    loc = page.locator(sel).first
                    if await loc.count():
                        await human.type_text(page, sel, str(val))
                except Exception:
                    pass
            await human.scroll(page)

            for btn in ('button[type="submit"]',
                        'button:has-text("Konto erstellen")',
                        'button:has-text("Registrieren")',
                        'button:has-text("Anmelden")',
                        'button:has-text("Weiter")'):
                try:
                    loc = page.locator(btn).first
                    if await loc.count():
                        await human.move_mouse(page)
                        await loc.click(timeout=5000)
                        break
                except Exception:
                    pass

            try:
                link = await wait_for_link(inbox, timeout=45.0)
            except Exception:
                link = None
            return {"site": self.site, "email": inbox["address"],
                    "password": ident.password, "first_name": ident.first_name,
                    "last_name": ident.last_name,
                    "birth": ident.birthdate.strftime("%d.%m.%Y"),
                    "verify_link": link or ""}
        finally:
            await page.close()

    def _fields(self, inbox: dict, ident) -> list:
        return [('input[name="email"]', inbox["address"]),
                ('input[name="password"]', ident.password),
                ('input[name="first_name"]', ident.first_name),
                ('input[name="last_name"]', ident.last_name),
                ('input[name="birth_day"]', ident.birth_day),
                ('input[name="birth_month"]', ident.birth_month),
                ('input[name="birth_year"]', ident.birth_year)]


def _dump(a: dict) -> str:
    lines = [f"site: {a['site']}", f"email: {a['email']}", f"password: {a['password']}",
             f"first_name: {a['first_name']}", f"last_name: {a['last_name']}",
             f"birth: {a['birth']}"]
    if a.get("verify_link"):
        lines.append(f"verify_link: {a['verify_link']}")
    return "\n".join(lines) + "\n"


async def run_generator(gen: AccountGenerator) -> int:
    await gen.run()
    return 0