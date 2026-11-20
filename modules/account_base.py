"""Gemeinsame Basis fuer die Account-Generatoren (Nike/Amazon/Riftbound)."""
from __future__ import annotations

import asyncio
import random
from pathlib import Path

from core.browser import Browser
from core.human import Human
from core.identity import IdentityGenerator
from core.mailbox import create_inbox, wait_for_link
from modules.quality import Quality

ROOT = Path(__file__).resolve().parent.parent


def _load_settings():
    from modules.shopify_core import Settings
    return Settings.load()


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
        self.q = Quality(self.site)

    async def run(self) -> list[str]:
        from modules.shopify_core import geo_check
        cfg = _load_settings()
        self._cfg = cfg
        d = ROOT / self.account_dir
        d.mkdir(parents=True, exist_ok=True)
        made = []
        browser = Browser(user_data_dir=str(ROOT / "var" / f"browser-{self.site}"),
                          headless=self.headless, seed=self.seed)
        await browser.start()
        try:
            for _ in range(self.count):
                self.q.increment("attempts")
                ident = self.idgen.generate()
                # A4: Geo-Pruefung gegen Identitaets-Land (DE), sofern aktiviert
                if cfg.geo.get("enabled", False):
                    from modules.shopify_core import Profile
                    prof = Profile(id=self.site, email=ident.email, first_name=ident.first_name,
                                   last_name=ident.last_name,
                                   address1=f"{ident.street} {ident.house_no}".strip(),
                                   zip=ident.zip, city=ident.city, country="DE")
                    ok, hinweis = await geo_check(cfg, prof, None)
                    if not ok:
                        self.q.banned(f"geo ({hinweis})")
                        continue
                inbox = await create_inbox(cfg)
                try:
                    account = await self._register(browser, ident, inbox)
                    self.q.success()
                except Exception:
                    self.q.banned(f"generator-{self.site}")
                    continue
                f = d / f"{account['email']}.txt"
                f.write_text(_dump(account), encoding="utf-8")
                made.append(str(f))
                print(f"[{self.site}] angelegt: {account['email']} -> {f.name}")
        finally:
            self.q.finish()
            await browser.stop()
        return made

    async def _register(self, browser: Browser, ident, inbox: dict) -> dict:
        human = Human(self.seed)
        page = await browser.new_page()
        sms_order = None
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
            # A10: SMS-Nummer nur auf Aufforderung (Settings.sms.only_on_request=false
            # und nur fuer Nike/Amazon). Messung ueber den Provider-Zaehler.
            sms_num, sms_order = await self._maybe_sms_phone()
            if sms_num:
                for sel in ('input[name="phone"]', 'input[name="phone_number"]',
                            'input[autocomplete="tel"]'):
                    try:
                        loc = page.locator(sel).first
                        if await loc.count():
                            await human.type_text(page, sel, sms_num)
                            break
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
            # SMS-Code pollen und verifizieren (sofern Nummer gekauft)
            sms_code = ""
            if sms_order:
                try:
                    from core.sms import get_provider
                    prov = get_provider(getattr(self, "_cfg", None) or _load_settings())
                    if prov:
                        sms_code = await prov.poll_code(sms_order, self.site, timeout=90.0) or ""
                except Exception:
                    pass
            return {"site": self.site, "email": inbox["address"],
                    "password": ident.password, "first_name": ident.first_name,
                    "last_name": ident.last_name,
                    "birth": ident.birthdate.strftime("%d.%m.%Y"),
                    "verify_link": link or "", "sms_order": sms_order or ""}
        finally:
            if sms_order:
                try:
                    from core.sms import get_provider
                    prov = get_provider(getattr(self, "_cfg", None) or _load_settings())
                    if prov:
                        await prov.release(sms_order)
                except Exception:
                    pass
            await page.close()

    async def _maybe_sms_phone(self) -> tuple[str | None, str | None]:
        """A10: kauft eine SMS-Nummer, wenn der Provider aktiv und die Seite
        zulassig ist (default nur nike/amazon und only_on_request=false).
        -> (nummer, order_id) oder (None, None)."""
        try:
            from core.sms import get_provider, need_sms
        except Exception:
            return None, None
        cfg = getattr(self, "_cfg", None) or _load_settings()
        zulassig = cfg.sms.get("sites", ["nike"])
        if not (need_sms(cfg) and self.site in zulassig):
            return None, None
        prov = get_provider(cfg)
        if not prov:
            return None, None
        try:
            service = cfg.sms.get("service") or {"nike": "nike"}.get(self.site, "other")
            r = await prov.buy(service)
            self._sms_order = r.get("order_id")
            return r.get("number"), self._sms_order
        except Exception:
            return None, None

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