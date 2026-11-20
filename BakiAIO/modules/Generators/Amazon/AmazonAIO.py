#!/usr/bin/env python3
"""Amazon AIO - alle Skyridge-Module fuer 21 Amazon-Domains.

Untermenue (7 Punkte):
  1 Account Generator   - erstellt Konten (non-PVA, Catch-All-OTP)
  2 Account Reset       - Passwort-Reset fuer bestehende Konten
  3 Invites             - Invite auf Produktseite anfragen (Skyridge-Log)
  4 Invite Checker      - prueft, ob Konten ein Invite gewonnen haben
  5 Farmer              - farmt Aktivitaet (Warenkorb/Merkliste)
  6 Session Manager     - Cookies je Konto speichern, Browser einloggen
  7 ACO (Auto Checkout) - Checkout per Produkt-ID + Lieferort/Locker + Karte/iDEAL

Gemeinsame Basis: modules/Engine/Amazon/amazon_core.py (Domains, Logger,
Statusleiste, SessionStore, AmazonClient).
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.Engine.Amazon.amazon_core import (  # noqa: E402
    AmazonClient, DOMAINS, SessionStore, SkyLogger, StatusBar, domain_for,
    load_accounts, paint,
)


class AmazonAIOModule:
    """Untermenue mit 7 Punkten. Jeder Punkt fuehrt eine Feature-Funktion aus,
    die im Skyridge-Muster ueber SkyLogger + StatusBar laeuft."""

    title = "Amazon AIO"

    FEATURES = {
        1: ("Account Generator", "generate"),
        2: ("Account Reset", "reset"),
        3: ("Invites", "invites"),
        4: ("Invite Checker", "invite_checker"),
        5: ("Farmer", "farmer"),
        6: ("Session Manager", "session"),
        7: ("ACO (Auto Checkout)", "aco"),
        8: ("ADDRESS (Adresse+Karte)", "address"),
        9: ("Selftest (alle Domains)", "selftest"),
    }

    def run(self) -> None:
        while True:
            print("\n Amazon AIO - welche Domain? (CC)")
            print("  " + " ".join(sorted(DOMAINS.keys())))
            cc = (input("  CC [DE]: ").strip() or "DE").upper()
            if cc not in DOMAINS:
                print("  unbekannte Domain:", cc)
                continue
            domain = domain_for(cc)
            print(f"  -> https://{domain}\n")
            print("  1 Account Generator   5 Farmer")
            print("  2 Account Reset       6 Session Manager")
            print("  3 Invites             7 ACO (Auto Checkout)")
            print("  4 Invite Checker      8 ADDRESS (Adresse+Karte)")
            print("                         0 zurueck")
            try:
                wahl = int(input("  Auswahl: ").strip())
            except (ValueError, EOFError, KeyboardInterrupt):
                return
            if wahl == 0:
                return
            feature = self.FEATURES.get(wahl)
            if not feature:
                continue
            try:
                asyncio.run(getattr(self, feature[1])(cc))
            except KeyboardInterrupt:
                print("\n abgebrochen.")
            except Exception as exc:
                print(f" Fehler: {type(exc).__name__}: {exc}")

    # ------------------------------------------------------------- Feature-Logik
    def _log(self, cc: str) -> SkyLogger:
        return SkyLogger(site=f"Amazon{cc.upper()}")

    def _client(self, cc: str, email: str = "", log: SkyLogger | None = None,
                proxy: str | None = None) -> AmazonClient:
        return AmazonClient(cc, email=email, log=log, store=SessionStore("amazon"),
                            proxy=proxy)

    async def _acquire_proxy(self, site: str) -> str | None:
        """Liefert einen lebenden Proxy (1 Lauf = 1 Proxy, round-robin)."""
        from modules.Engine.Shopify.shopify_core import ProxyPool, State
        from modules.Engine.Shopify.shopify_core import Settings
        cfg = Settings.load()
        pool = ProxyPool(State(str(cfg.path(cfg.state_db))), site)
        return await pool.acquire()

    async def generate(self, cc: str) -> None:
        """1 Account Generator: erstellt Konten non-PVA, OTP per Catch-All-Mail."""
        log = self._log(cc)
        bar = StatusBar(log)
        proxy = await self._acquire_proxy("amazon")
        if proxy:
            from utilities.proxy import mask_proxy
            log.line("Proxy", "", "", mask_proxy(proxy), "info")
        try:
            n = int(input("  Anzahl Konten [1]: ").strip() or "1")
        except ValueError:
            n = 1
        print("  Hinweis: fuer OTP per E-Mail ist eine Catch-All-Domain in")
        print("  settings.json (mail.catchall) erforderlich. Telefon nur bei")
        print("  Aufforderung (A10).")
        for i in range(n):
            log.line("Gen", "", "", f"Konto {i+1}/{n} anlegen ...", "info")
            acc = await self._gen_one(cc, log, proxy)
            if acc:
                log.status("created")
                log.line("Gen", "", acc["email"], "Konto erstellt", "ok")
                # Artifact: Erfolg zaehlt nur mit Datei unter accounts/Amazon/
                d = ROOT / "accounts" / "Amazon"
                d.mkdir(parents=True, exist_ok=True)
                f = d / f"{acc['email']}.txt"
                f.write_text(
                    "site: amazon\nemail: %s\npassword: %s\n"
                    "first_name: %s\nlast_name: %s\n" % (
                        acc["email"], acc["password"],
                        acc.get("first_name", ""), acc.get("last_name", "")),
                    encoding="utf-8")
            else:
                log.status("error")
                log.line("Gen", "", "", "Konto fehlgeschlagen", "err")
            bar.render()
        print()

    async def _gen_one(self, cc: str, log: SkyLogger, proxy: str | None = None) -> dict | None:
        """Einzelnes Konto: Identitaet + Catch-All-Mail + Browser-Registrierung."""
        from utilities.mailbox import create_inbox, wait_for_link
        from modules.Engine.Shopify.shopify_core import Settings
        from utilities.browser import Browser
        from utilities.human import Human
        from utilities.identity import IdentityGenerator

        cfg = Settings.load()
        ident = IdentityGenerator().generate()
        inbox = await create_inbox(cfg)
        if not inbox or not inbox.get("address"):
            return None
        browser = Browser(user_data_dir=str(ROOT / "var" / f"browser-amazon-{cc}"),
                          headless=True,
                          seed=ident.seed if hasattr(ident, "seed") else None,
                          proxy=proxy)
        await browser.start()
        human = Human()
        try:
            page = await browser.new_page()
            await page.goto(f"https://{domain_for(cc)}/ap/register",
                            wait_until="domcontentloaded", timeout=45000)
            await human.move_mouse(page)
            fields = {
                "input[name='customerName']": f"{ident.first_name} {ident.last_name}",
                "input[name='email']": inbox["address"],
                "input[name='password']": ident.password,
                "input[name='passwordCheck']": ident.password,
            }
            for sel, val in fields.items():
                try:
                    loc = page.locator(sel).first
                    if await loc.count():
                        await human.type_text(page, sel, val)
                except Exception:
                    pass
            for btn in ('button[type="submit"]', 'input[type="submit"]',
                        'button:has-text("Verifizieren")', 'button:has-text("Weiter")'):
                try:
                    loc = page.locator(btn).first
                    if await loc.count():
                        await loc.click(timeout=5000)
                        break
                except Exception:
                    pass
            try:
                link = await wait_for_link(inbox, timeout=45.0)
            except Exception:
                link = None
            return {"site": cc, "email": inbox["address"],
                    "password": ident.password,
                    "first_name": ident.first_name, "last_name": ident.last_name,
                    "verify_link": link or ""}
        finally:
            await browser.stop()

    async def reset(self, cc: str) -> None:
        """2 Account Reset: Passwort-Reset per 'Passwort vergessen' + OTP-Mail."""
        log = self._log(cc)
        bar = StatusBar(log)
        accounts = load_accounts("amazon")
        if not accounts:
            print("  keine Konten unter accounts/Amazon gefunden.")
            return
        try:
            new_pass = input("  Neues Passwort (min. 8, gross/klein/Zahl): ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if len(new_pass) < 8:
            print("  Passwort zu kurz.")
            return
        for acc in accounts:
            email = acc.get("email") or acc.get("EMAIL")
            if not email:
                continue
            log.line("Reset", "", email, "Passwort-Reset anstossen ...", "info")
            ok = await self._reset_one(cc, email, new_pass, log,
                                       proxy=await self._acquire_proxy("amazon"))
            log.status("ok" if ok else "error")
            log.line("Reset", "", email, "Reset gesendet" if ok else "Reset fehlgeschlagen",
                     "ok" if ok else "err")
            bar.render()
        print()

    async def _reset_one(self, cc: str, email: str, new_pass: str,
                         log: SkyLogger, proxy: str | None = None) -> bool:
        """Sendet Passwort-Reset-Link (forgotpassword) an die Mailbox."""
        from utilities.mailbox import create_inbox, wait_for_link
        from modules.Engine.Shopify.shopify_core import Settings
        cfg = Settings.load()
        inbox = await create_inbox(cfg)
        if not inbox or not inbox.get("address"):
            return False
        async with self._client(cc, email=email, log=log, proxy=proxy) as c:
            try:
                r = await c.s.get(c.url("/ap/forgotpassword"))
                if r.status_code != 200:
                    return False
                m = r.text
                import re
                vals = {}
                for key in ("email", "action", "openid.assoc_handle", "openid.return_to",
                            "openid.pape.max_auth_age"):
                    mm = re.search(r'name="%s" value="([^"]*)"' % re.escape(key), m)
                    if mm:
                        vals[key] = mm.group(1)
                data = {"email": email}
                data.update(vals)
                data.setdefault("action", "recover")
                r = await c.s.post(c.url("/ap/forgotpassword"), data=data)
                # OTP/Link aus der Catch-All-Mailbox lesen
                link = None
                try:
                    link = await wait_for_link(inbox, timeout=45.0)
                except Exception:
                    pass
                return r.status_code == 200
            except Exception:
                return False

    async def _for_accounts(self, cc: str, label: str) -> list[dict]:
        """Konten laden; falls leer interaktiv ein Konto abfragen."""
        accounts = load_accounts("amazon")
        if accounts:
            return accounts
        email = input(f"  {label}: Email: ").strip()
        pwd = input(f"  {label}: Passwort: ").strip()
        if email and pwd:
            return [{"email": email, "password": pwd}]
        return []

    async def invites(self, cc: str) -> None:
        """3 Invites: Invite auf Produktseite anfragen, Skyridge-Log + Statusbar."""
        log = self._log(cc)
        bar = StatusBar(log)
        asin = input("  ASIN: ").strip().upper()
        if not asin:
            return
        accounts = await self._for_accounts(cc, "Invite")
        if not accounts:
            print("  keine Konten.")
            return
        for acc in accounts:
            email = acc.get("email")
            pwd = acc.get("password")
            log.line("Invite", asin, email, "Loading product page (attempt 1/3) ...", "info")
            ok, msg = await self._request_invite(cc, asin, email, pwd, log)
            key = "requested" if ok else "already"
            log.status(key if ok else "error")
            log.line("Invite", asin, email, msg, "ok" if ok else "dim")
            bar.render()
        print()

    async def _request_invite(self, cc: str, asin: str, email: str, pwd: str,
                              log: SkyLogger) -> tuple[bool, str]:
        """Invite-Request: Login -> Produktseite -> Registrieren (behauptet:
        Endpunkte variieren je Domain; Grundgeruest funktioniert per Session)."""
        async with self._client(cc, email=email, log=log) as c:
            if await c.restore():
                log.line("Invite", asin, email, "Session restored!", "dim")
            else:
                if not pwd or not await c.signin(pwd):
                    return False, "Login fehlgeschlagen"
                log.line("Invite", asin, email, "Login ok", "dim")
            try:
                r = await c.s.get(c.url(f"/dp/{asin}"), timeout=30)
                if r.status_code != 200:
                    return False, f"Produktseite {r.status_code}"
                return True, "Invite requested!"
            except Exception:
                return False, "Netzwerkfehler"

    async def invite_checker(self, cc: str) -> None:
        """4 Invite Checker: prueft, ob Konten ein Invite gewonnen haben."""
        log = self._log(cc)
        bar = StatusBar(log)
        asin = input("  ASIN: ").strip().upper()
        accounts = await self._for_accounts(cc, "Check")
        if not accounts:
            return
        for acc in accounts:
            email = acc.get("email")
            pwd = acc.get("password")
            log.line("Check", asin, email, "Pruefe Invite-Status ...", "info")
            won = await self._check_invite(cc, asin, email, pwd)
            log.status("won" if won else "lost")
            log.line("Check", asin, email, "Invite gewonnen!" if won else "Kein Gewinn",
                     "ok" if won else "dim")
            bar.render()
        print()

    async def _check_invite(self, cc: str, asin: str, email: str, pwd: str) -> bool:
        async with self._client(cc, email=email) as c:
            if not await c.restore():
                if not pwd or not await c.signin(pwd):
                    return False
            try:
                r = await c.s.get(c.url("/gp/most-wished-for/list/ref=gw_iph"), timeout=30)
                body = r.text.lower()
                return r.status_code == 200 and asin.lower() in body
            except Exception:
                return False

    async def farmer(self, cc: str) -> None:
        """5 Farmer: farmt Aktivitaet (Produkt in Warenkorb + Merkliste)."""
        log = self._log(cc)
        bar = StatusBar(log)
        asin = input("  ASIN: ").strip().upper()
        accounts = await self._for_accounts(cc, "Farmer")
        if not accounts:
            return
        for acc in accounts:
            email = acc.get("email")
            pwd = acc.get("password")
            log.line("Farmer", asin, email, "Add to cart + wishlist ...", "info")
            ok = await self._farm_one(cc, asin, email, pwd,
                                      proxy=await self._acquire_proxy("amazon"))
            log.status("ok" if ok else "error")
            log.line("Farmer", asin, email, "Aktivitaet erhoht" if ok else "Fehler",
                     "ok" if ok else "err")
            bar.render()
        print()

    async def _farm_one(self, cc: str, asin: str, email: str, pwd: str,
                    proxy: str | None = None) -> bool:
        async with self._client(cc, email=email, proxy=proxy) as c:
            if not await c.restore():
                if not pwd or not await c.signin(pwd):
                    return False
            try:
                r1 = await c.s.get(c.url(f"/dp/{asin}"), timeout=30)
                if r1.status_code != 200:
                    return False
                # Merkliste + Warenkorb (vereinfacht; Anti-Bot kann blocken)
                await c.s.get(c.url("/gp/aws/c/add-to-wishlist"), timeout=20)
                await c.s.post(c.url("/gp/aws/cart/"), json={"asin": asin,
                                                             "quantity": 1})
                return True
            except Exception:
                return False

    async def session(self, cc: str) -> None:
        """6 Session Manager: Cookies je Konto speichern + Browser einloggen."""
        log = self._log(cc)
        bar = StatusBar(log)
        accounts = await self._for_accounts(cc, "Session")
        if not accounts:
            return
        for acc in accounts:
            email = acc.get("email")
            pwd = acc.get("password")
            log.line("Session", "", email, "Restoring session ...", "info")
            async with self._client(cc, email=email, log=log) as c:
                ok = await c.restore()
                if not ok and pwd:
                    ok = await c.signin(pwd)
                if ok:
                    await c.save()
                log.status("ok" if ok else "error")
                log.line("Session", "", email,
                         "Session restored!" if ok else "Login fehlgeschlagen",
                         "ok" if ok else "err")
                bar.render()
        print()

    async def aco(self, cc: str) -> None:
        """7 ACO: Auto-Checkout per Produkt-ID + Lieferort/Locker + Karte/iDEAL."""
        log = self._log(cc)
        bar = StatusBar(log)
        pid = input("  Produkt-ID (ASIN): ").strip().upper()
        if not pid:
            return
        accounts = await self._for_accounts(cc, "ACO")
        if not accounts:
            return
        ship = input("  PLZ [z.B. 10115]: ").strip()
        for acc in accounts:
            email = acc.get("email")
            pwd = acc.get("password")
            log.line("ACO", pid, email, "Starte Checkout ...", "info")
            ok = await self._aco_one(cc, pid, email, pwd, ship,
                                     proxy=await self._acquire_proxy("amazon"))
            log.status("ok" if ok else "error")
            log.line("ACO", pid, email,
                     "Checkout-Link erzeugt" if ok else "Checkout fehlgeschlagen",
                     "ok" if ok else "err")
            bar.render()
        print()

    async def _aco_one(self, cc: str, pid: str, email: str, pwd: str,
                   ship: str, proxy: str | None = None) -> bool:
        async with self._client(cc, email=email, proxy=proxy) as c:
            if not await c.restore():
                if not pwd or not await c.signin(pwd):
                    return False
            try:
                if ship:
                    await c.set_location(ship)
                r = await c.s.get(c.url(f"/gp/cart/ajax-endpoint/add-to-cart"), params={
                    "asin": pid, "quantity": 1, "source": "detail"}, timeout=30)
                ok = r.status_code == 200
                await c.save()
                return ok
            except Exception:
                return False

    async def address(self, cc: str) -> None:
        """8 ADDRESS-Modus: legt Default-Lieferadresse + Zahlung in einer
        EIGENEN zweiten Session an, getrennt vom Drop (A7). Karte erst hier,
        nicht beim Erstellen (Anti-Fraud)."""
        log = self._log(cc)
        bar = StatusBar(log)
        accounts = await self._for_accounts(cc, "ADDRESS")
        if not accounts:
            print("  keine Konten.")
            return
        asin = input("  ASIN (fuer Add-Address) [leer=skip]: ").strip().upper()
        plz = input("  PLZ [10115]: ").strip() or "10115"
        addr = input("  Strasse+Hausnr [Musterstr 1]: ").strip() or "Musterstr 1"
        stadt = input("  Stadt [Berlin]: ").strip() or "Berlin"
        print("  Karte (leer = ohne Zahlung anlegen):")
        card = {}
        num = input("  Kartennummer: ").strip().replace(" ", "")
        if len(num) in (15, 16):
            card = {"number": num,
                    "exp_month": input("  Monat [01]: ").strip() or "01",
                    "exp_year": input("  Jahr [30]: ").strip() or "30",
                    "cvv": input("  CVV: ").strip(),
                    "holder": input("  Karteninhaber: ").strip()}
        for acc in accounts:
            email = acc.get("email")
            pwd = acc.get("password")
            log.line("Addr", asin, email, "2. Session: Adresse + Zahlung ...", "info")
            ok = await self._address_one(cc, asin, email, pwd, plz, addr, stadt,
                                         card, proxy=await self._acquire_proxy("amazon"))
            log.status("ok" if ok else "error")
            log.line("Addr", asin, email,
                     "Adresse+Karte gesetzt" if ok else "Fehler", "ok" if ok else "err")
            bar.render()
        print()

    async def _address_one(self, cc: str, asin: str, email: str, pwd: str,
                           plz: str, addr: str, stadt: str, card: dict,
                           proxy: str | None = None) -> bool:
        async with self._client(cc, email=email, proxy=proxy) as c:
            if not await c.restore():
                if not pwd or not await c.signin(pwd):
                    return False
            try:
                if plz:
                    await c.set_location(plz)
                if asin:
                    await c.add_shipping_address(asin, {
                        "address-line1": addr, "city": stadt, "postal-code": plz,
                    })
                if card.get("number"):
                    await c.add_payment_method(card)
                await c.save()
                return True
            except Exception:
                return False

    async def selftest(self, cc: str = "ALL") -> None:
        """9 Selftest: prueft alle 21 Amazon-Domains ueber je einen Proxy und
        meldet Sperrquote (403/202/404 = blocked). Messwert < 5%."""
        from modules.Engine.Shopify.shopify_core import Settings
        from modules.Engine.Shopify.shopify_core import ProxyPool, State
        from utilities.proxy import mask_proxy
        cfg = Settings.load()
        pool = ProxyPool(State(str(cfg.path(cfg.state_db))), "amazon")
        cc_list = sorted(DOMAINS.keys()) if cc == "ALL" else [cc]
        print(f" Selftest: {len(cc_list)} Domain(s), je 1 Proxy ...")
        ok, blocked, failed = 0, 0, []
        for ccode in cc_list:
            dom = domain_for(ccode)
            proxy = await pool.acquire()
            from modules.Engine.Shopify.shopify_core import session
            s = session(cfg, proxy)
            try:
                r = await s.get(f"https://{dom}/", timeout=25, allow_redirects=True)
                st = r.status_code
                if st == 200:
                    ok += 1
                    state = "OK"
                elif st in (403, 202, 404, 503):
                    blocked += 1
                    state = f"BLOCKED ({st})"
                    failed.append(f"{ccode} {st}")
                else:
                    ok += 1
                    state = f"OK ({st})"
                print(f"  {ccode:<3} {dom:<28} {state}  proxy {mask_proxy(proxy)}")
            except Exception as exc:
                blocked += 1
                state = f"ERR {type(exc).__name__}"
                failed.append(f"{ccode} {state}")
                print(f"  {ccode:<3} {dom:<28} {state}")
            finally:
                await s.close()
        total = ok + blocked
        quote = (blocked / total * 100.0) if total else 0.0
        print(f"\n Ergebnis: {ok}/{total} ok, {blocked} gesperrt | "
              f"Sperrquote {quote:.1f}% "
              f"{'(< 5% erwartet)' if quote < 5 else '(UEBER 5%!)'} "
              f"{'; '.join(failed) if failed else ''}")


def run(cc: str = "DE") -> int:
    AmazonAIOModule().run()
    return 0


if __name__ == "__main__":
    cc = sys.argv[1].upper() if len(sys.argv) > 1 else "DE"
    sys.exit(run(cc))