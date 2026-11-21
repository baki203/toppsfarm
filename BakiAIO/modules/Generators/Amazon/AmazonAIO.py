#!/usr/bin/env python3
"""Amazon AIO - alle Skyridge-Module fuer 21 Amazon-Domains.

Modul-Uebersicht (Skyridge-Muster):
  1 Account Generator   - erstellt Konten (HTTP, non-PVA, Catch-All-OTP)
  2 Account Reset       - Passwort-Reset (HTTP, forgotpassword + OTP-Mail)
  3 Invites             - Invite auf Produktseite anfragen (HTTP)
  4 Invite Checker      - prueft, ob Konten ein Invite gewonnen haben (HTTP)
  5 Farmer              - farmt Aktivitaet: Warenkorb + Merkliste (HTTP)
  6 Session Manager     - Browser-basiert: Cookies je Konto speichern + einloggen
  7 ACO (Auto Checkout) - Checkout per Produkt-ID + Dummy-Items, PLZ/Locker,
                          Kreditkarte oder iDEAL (BankQ/Revolut) (HTTP)

Nur der Session Manager ist browser-basiert (wie Skyridge); alle anderen Module
laufen ueber den HTTP-AmazonClient mit wiederhergestellten Cookies aus dem
SessionStore (restore_or_login).

Gemeinsame Basis: modules/Engine/Amazon/amazon_core.py (Domains, SkyLogger,
StatusBar, SessionStore, AmazonClient, AmazonBrowser).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.Engine.Amazon.amazon_core import (  # noqa: E402
    AmazonClient, AmazonBrowser, DOMAINS, SessionStore, SkyLogger, StatusBar,
    domain_for, paint,
)
from modules.Engine.Amazon.amazon_store import AmazonStore  # noqa: E402


class AmazonAIOModule:
    """Untermenue mit 7 Punkten + ADDRESS + Selftest. Jeder Punkt fuehrt eine
    Feature-Funktion aus, die im Skyridge-Muster ueber SkyLogger + StatusBar
    laeuft. Modul-eigener Statusbalken (Kopfzeile) je Durchlauf."""

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

    # ------------------------------------------------------------- Hilfsfunktionen
    def _log(self, cc: str) -> SkyLogger:
        return SkyLogger(site=f"Amazon{cc.upper()}")

    def _store(self) -> AmazonStore:
        return AmazonStore("amazon")

    def _client(self, cc: str, email: str = "", log: SkyLogger | None = None,
                proxy: str | None = None) -> AmazonClient:
        return AmazonClient(cc, email=email, log=log, store=SessionStore("amazon"),
                            proxy=proxy)

    async def _acquire_proxy(self, site: str = "amazon") -> str | None:
        """Liefert einen lebenden Proxy (1 Lauf = 1 Proxy, round-robin)."""
        from modules.Engine.Shopify.shopify_core import ProxyPool, Settings, State
        cfg = Settings.load()
        pool = ProxyPool(State(str(cfg.path(cfg.state_db))), site)
        return await pool.acquire()

    async def _for_accounts(self, cc: str, label: str) -> list[dict]:
        """Konten aus dem Skyridge-Input laden (tasks_/gen_/custom_);
        falls leer interaktiv ein Konto abfragen."""
        accounts = self._store().read_tasks()
        if accounts:
            return accounts
        email = input(f"  {label}: Email: ").strip()
        pwd = input(f"  {label}: Passwort: ").strip()
        if email and pwd:
            return [{"email": email, "password": pwd}]
        return []

    async def _restore_client(self, c: AmazonClient, pwd: str) -> bool:
        """Stellt die Session wieder her (Cookies aus SessionStore) oder loggt
        ein. Liefert True, wenn die Session aktiv ist."""
        if await c.restore():
            return True
        if pwd and await c.signin(pwd):
            await c.save()
            return True
        return False

    # ---------------------------------------------------------- 1 Account Generator
    async def generate(self, cc: str) -> None:
        """1 Account Generator: erstellt Konten (HTTP, non-PVA, Catch-All-OTP)."""
        log = self._log(cc)
        bar = StatusBar(log)
        bar.header(f"Amazon{cc.upper()} Account Generator")
        proxy = await self._acquire_proxy()
        from utilities.proxy import mask_proxy, proxy_origin
        log.line("Gen", "", "",
                 f"{mask_proxy(proxy) or 'kein Proxy'} (quelle={proxy_origin('amazon')})",
                 "dim")
        try:
            n = int(input("  Anzahl Konten [1]: ").strip() or "1")
        except ValueError:
            n = 1
        print("  Hinweis: fuer OTP per E-Mail nutzt der Generator die")
        print("  Skyridge-Mastermails (settings.json 'Mastermails', non-PVA).")
        print("  Telefon nur bei Aufforderung (A10).")
        for i in range(n):
            log.line("Gen", "", "", f"Konto {i+1}/{n} anlegen ...", "info")
            acc = await self._gen_one(cc, log, proxy)
            if acc:
                log.status("created")
                log.line("Gen", "", acc["email"], "Account created", "ok")
                # Skyridge: an gen_AmazonAccounts.csv anhaengen
                self._store().append("gen", {
                    "email": acc["email"], "email_password": "",
                    "password": acc["password"],
                    "firstName": acc.get("first_name", ""),
                    "lastName": acc.get("last_name", ""),
                    "phonenumber": "", "country_iso": cc, "phone_iso": "",
                    "proxy": proxy or "",
                }, dedupe_keys=["email"])
            else:
                log.status("error")
                log.line("Gen", "", "", "Account generation failed", "err")
            bar.render()
        print()

    async def _gen_one(self, cc: str, log: SkyLogger, proxy: str | None = None) -> dict | None:
        """Einzelnes Konto: Identitaet + Catch-All-Mail + HTTP-Registrierung."""
        from utilities.mailbox import create_inbox, wait_for_link
        from utilities.identity import IdentityGenerator

        ident = IdentityGenerator().generate()
        try:
            inbox = await create_inbox()
        except Exception as exc:
            log.line("Gen", "", "", f"Mailbox: {exc}", "err")
            return None
        if not inbox or not inbox.get("address"):
            return None
        async with self._client(cc, email=inbox["address"], log=log, proxy=proxy) as c:
            try:
                r = await c.s.get(c.url("/ap/register"), timeout=30)
                if r.status_code != 200:
                    reason = "anti-bot (202)" if r.status_code in (202, 403, 503) else \
                             ("not-found (404)" if r.status_code == 404 else f"http {r.status_code}")
                    log.line("Gen", "", inbox["address"],
                             f"Register-Page blockiert: {reason}", "err")
                    log.status("error")
                    return None
                data = {
                    "customerName": ident.full_name,
                    "email": inbox["address"],
                    "password": ident.password,
                    "passwordCheck": ident.password,
                    "create": "0", "action": "register",
                }
                r = await c.s.post(c.url("/ap/register"), data=data, timeout=30)
                if r.status_code != 200:
                    reason = "anti-bot (202)" if r.status_code in (202, 403, 503) else \
                             (f"http {r.status_code}")
                    log.line("Gen", "", inbox["address"],
                             f"Registrierung abgewiesen: {reason}", "err")
                    log.status("error")
                    return None
                link = None
                try:
                    link = await wait_for_link(inbox, timeout=45.0)
                except Exception:
                    link = None
                return {"site": cc, "email": inbox["address"],
                        "password": ident.password,
                        "first_name": ident.first_name, "last_name": ident.last_name,
                        "verify_link": link or ""}
            except Exception as exc:
                log.line("Gen", "", inbox["address"],
                         f"Registrierung Fehler: {type(exc).__name__}: {exc}", "err")
                log.status("error")
                return None

    # ---------------------------------------------------------- 2 Account Reset
    async def reset(self, cc: str) -> None:
        """2 Account Reset: Passwort-Reset per 'Passwort vergessen' + OTP-Mail."""
        log = self._log(cc)
        bar = StatusBar(log)
        bar.header(f"Amazon{cc.upper()} Account Reset")
        accounts = self._store().read_tasks()
        if not accounts:
            print("  keine Konten in accounts/Amazon (tasks_/gen_/custom_).")
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
            log.line("Reset", "", email, "Sending password reset ...", "info")
            ok = await self._reset_one(cc, email, new_pass, log,
                                       proxy=await self._acquire_proxy())
            log.status("ok" if ok else "error")
            log.line("Reset", "", email, "Reset sent" if ok else "Reset failed",
                     "ok" if ok else "err")
            bar.render()
        print()

    async def _reset_one(self, cc: str, email: str, new_pass: str,
                         log: SkyLogger, proxy: str | None = None) -> bool:
        """Sendet Passwort-Reset-Link (forgotpassword) an die Mailbox."""
        from utilities.mailbox import create_inbox, wait_for_link
        try:
            inbox = await create_inbox()
        except Exception as exc:
            log.line("Reset", "", email, f"Mailbox: {exc}", "err")
            return False
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
                try:
                    link = await wait_for_link(inbox, timeout=45.0)
                except Exception:
                    link = None
                return r.status_code == 200
            except Exception:
                return False

    # ---------------------------------------------------------- 3 Invites
    async def invites(self, cc: str) -> None:
        """3 Invites: Invite auf Produktseite anfragen. Skyridge-Log + Statusbar.

        Konten aus der Tasks-CSV/Artefakten (accounts/Amazon/): Pro Zeile wird
        die eigene PID (ASIN) verwendet, falls vorhanden (CSV-Spalte PID), sonst
        die interaktiv eingegebene ASIN. Login erfolgt per HTTP mit den CSV-
        Credentials (Request-Mode) - kein Session Manager noetig."""
        log = self._log(cc)
        bar = StatusBar(log)
        bar.header(f"Amazon{cc.upper()} Invites")
        store = self._store()
        accounts = self._for_accounts(cc, "Invite")
        if not accounts:
            print("  keine Konten.")
            return
        # Input-CSV waehlen: falls mehrere tasks_*-Dateien, auswaehlen
        inputs = store.list_inputs()
        sel = None
        if len(inputs) > 1:
            print("  Tasks-CSV auswaehlen (Enter = alle):")
            for i, name in enumerate(inputs, 1):
                print(f"   {i}. {name}")
            try:
                n = int(input("  Nummer [0]: ").strip() or "0")
            except ValueError:
                n = 0
            if 1 <= n <= len(inputs):
                sel = inputs[n - 1]
        if sel:
            rows = store.read_file(sel)
        else:
            rows = accounts
        if not rows:
            print("  keine Konten.")
            return
        asin_default = input("  ASIN (falls nicht in der CSV als PID) [leer=aus CSV]: ").strip().upper()
        for acc in rows:
            email = acc.get("email")
            pwd = acc.get("password")
            proxy = acc.get("proxy") or ""
            # PID/ASIN: erst aus der Zeile (Skyridge CSV-Spalte PID/ASIN), sonst Default
            asin = (acc.get("pid") or acc.get("asin") or acc.get("PID") or asin_default or "").upper()
            if not asin:
                log.line("Invite", "-", email, "Keine ASIN (CSV/Default)", "warn")
                log.status("skipped")
                bar.render()
                continue
            async with self._client(cc, email=email, log=log,
                                    proxy=proxy or await self._acquire_proxy()) as c:
                # HTTP-Login (Request-Mode). Cookies aus .sessions sind optional.
                if await c.restore():
                    log.line("Invite", asin, email, "Session restored!", "dim")
                    log.status("restored")
                elif not pwd or not await c.signin(pwd):
                    log.line("Invite", asin, email, "Login failed", "err")
                    log.status("error")
                    bar.render()
                    continue
                # Produktseite mit Retry (attempt x/3)
                ok, msg = await self._invite_flow(c, cc, asin, email, log)
                if ok:
                    log.status("requested")
                    log.line("Invite", asin, email, msg, "ok")
                    store.add_invite(asin, email, pwd, cc, proxy)
                    store.append("invited", {
                        "email": email, "asin": asin, "country_iso": cc,
                        "status": "invited", "product": "", "price": "",
                        "checked_at": _now(),
                    }, dedupe_keys=["email", "asin"])
                    store.add_asin_history(asin)
                else:
                    log.status("already")
                    log.line("Invite", asin, email, msg, "dim")
                bar.render()
        print()

    async def _invite_flow(self, c: AmazonClient, cc: str, asin: str, email: str,
                           log: SkyLogger) -> tuple[bool, str]:
        """Invite-Request: Produktseite laden (attempt x/3) -> Details -> Request."""
        import re as _re
        attempts = 3
        for attempt in range(1, attempts + 1):
            log.line("Invite", asin, email, f"Loading product page (attempt {attempt}/{attempts}) ...", "info")
            det = await c.fetch_invite_details(asin)
            if det:
                info = f" - {det.get('title','')}" if det.get("title") else ""
                price = f" | Price: {det['price']}" if det.get("price") else ""
                iid = f" | ID: {det['invite_id']}" if det.get("invite_id") else ""
                log.line("Invite", asin, email,
                         f"Fetched invite details{info}{price}{iid}", "mag")
                break
            if attempt < attempts:
                await asyncio.sleep(1.0)
        # Checking product availability
        log.line("Invite", asin, email, "Checking product availability ...", "info")
        if det is None:
            return False, "Product page failed"
        # Already requested / entered
        low = (det.get("title", "") + " ").lower()
        if det.get("invite_id"):
            log.line("Invite", asin, email, "Already requested", "dim")
            return False, "Already requested, skipping"
        if "bereits" in low or "already" in low:
            return False, "Already entered, skipping"
        # Requesting invite
        log.line("Invite", asin, email, "Requesting invite ...", "info")
        state = await c.request_invite(asin)
        if state == "requested":
            return True, "Invite requested!"
        if state == "already":
            return False, "Already requested, skipping"
        return False, "Invite request failed"

    # ---------------------------------------------------------- 4 Invite Checker
    async def invite_checker(self, cc: str) -> None:
        """4 Invite Checker: prueft, ob Konten ein Invite gewonnen haben."""
        log = self._log(cc)
        bar = StatusBar(log)
        bar.header(f"Amazon{cc.upper()} Invite Checker")
        store = self._store()
        asin = input("  ASIN: ").strip().upper()
        accounts = await self._for_accounts(cc, "Check")
        if not accounts:
            return
        for acc in accounts:
            email = acc.get("email")
            pwd = acc.get("password")
            proxy = acc.get("proxy") or ""
            async with self._client(cc, email=email, log=log,
                                    proxy=proxy or await self._acquire_proxy()) as c:
                if not await self._restore_client(c, pwd):
                    log.line("Check", asin, email, "Login failed", "err")
                    log.status("error")
                    bar.render()
                    continue
                log.line("Check", asin, email, "Checking invite status ...", "info")
                won = await c.check_invite(asin)
                st = "won" if won else "lost"
                log.status(st)
                log.line("Check", asin, email,
                         "Invite won!" if won else "No win", "ok" if won else "dim")
                store.append("checked", {
                    "email": email, "email_password": "",
                    "password": pwd, "firstName": acc.get("firstName", ""),
                    "lastName": acc.get("lastName", ""),
                    "country_iso": cc, "phone_iso": "", "phonenumber": "",
                    "status": st, "proxy": proxy,
                }, dedupe_keys=["email", "status"])
                bar.render()
        print()

    # ---------------------------------------------------------- 5 Farmer
    async def farmer(self, cc: str) -> None:
        """5 Farmer: farmt Aktivitaet (Warenkorb + Merkliste)."""
        log = self._log(cc)
        bar = StatusBar(log)
        bar.header(f"Amazon{cc.upper()} Farmer")
        store = self._store()
        asin = input("  ASIN: ").strip().upper()
        accounts = await self._for_accounts(cc, "Farmer")
        if not accounts:
            return
        for acc in accounts:
            email = acc.get("email")
            pwd = acc.get("password")
            proxy = acc.get("proxy") or ""
            async with self._client(cc, email=email, log=log,
                                    proxy=proxy or await self._acquire_proxy()) as c:
                if not await self._restore_client(c, pwd):
                    log.line("Farmer", asin, email, "Login failed", "err")
                    log.status("error")
                    bar.render()
                    continue
                log.line("Farmer", asin, email, "Adding to cart + wishlist ...", "info")
                cart = await c.add_to_cart(asin)
                wish = await c.add_wishlist(asin)
                ok = cart or wish
                log.status("added" if ok else "error")
                log.line("Farmer", asin, email,
                         f"Activity: cart={cart} wishlist={wish}" if ok else "Activity failed",
                         "ok" if ok else "err")
                if ok:
                    store.append("farmed", {
                        "email": email, "email_password": "",
                        "password": pwd, "country_iso": cc, "farmed": "farmed",
                        "proxy_host": _proxy_part(proxy, 0),
                        "proxy_port": _proxy_part(proxy, 1),
                        "proxy_pool": _proxy_part(proxy, 2),
                        "proxy_user": _proxy_part(proxy, 3),
                    }, dedupe_keys=["email"])
                    store.add_asin_history(asin)
                bar.render()
        print()

    # ---------------------------------------------------------- 6 Session Manager
    async def session(self, cc: str) -> None:
        """6 Session Manager (BROWSER-basiert, wie Skyridge):
        Cookies je Konto im persistente Browserprofil speichern und den Browser
        eingeloggt oeffnen, damit man manuell navigieren/kaufen kann."""
        log = self._log(cc)
        bar = StatusBar(log)
        bar.header(f"Amazon{cc.upper()} Session Manager")
        accounts = await self._for_accounts(cc, "Session")
        if not accounts:
            return
        keep_open = (input("  Browser offen lassen nach Login? (j/n) [j]: ").strip().lower() != "n")
        for acc in accounts:
            email = acc.get("email")
            pwd = acc.get("password")
            log.line("Session", "", email, "Restoring session ...", "info")
            async with AmazonBrowser(cc, email=email, password=pwd,
                                     proxy=await self._acquire_proxy(),
                                     headless=False, log=log) as b:
                ok = await b.restore_or_login()
                if ok:
                    # Cookies im Skyridge-Format (.sessions/<email>__<CC>.json)
                    # speichern, damit die HTTP-Module dieselbe Session nutzen.
                    cookies = await b.get_cookies()
                    if cookies:
                        self._store().save_session(email, cookies, cc)
                    await b.page.goto(f"https://{domain_for(cc)}/",
                                      wait_until="domcontentloaded", timeout=40000)
                    log.status("restored")
                    log.line("Session", "", email, "Session restored! (Cookies gespeichert)", "ok")
                    if keep_open:
                        print(paint(f"    Browser offen fuer {email} - manuell navigieren. "
                                    "Enter fuer naechstes Konto.", "dim"))
                        try:
                            input()
                        except (EOFError, KeyboardInterrupt):
                            pass
                else:
                    log.status("error")
                    log.line("Session", "", email, "Session restore failed", "err")
                bar.render()
        print()

    # ---------------------------------------------------------- 7 ACO
    async def aco(self, cc: str) -> None:
        """7 ACO: Auto-Checkout per Produkt-ID + Dummy-Items, PLZ/Locker,
        Kreditkarte oder iDEAL (BankQ/Revolut)."""
        log = self._log(cc)
        bar = StatusBar(log)
        bar.header(f"Amazon{cc.upper()} ACO")
        store = self._store()
        pid = input("  Produkt-ID (ASIN): ").strip().upper()
        if not pid:
            return
        accounts = await self._for_accounts(cc, "ACO")
        if not accounts:
            return
        ship = input("  PLZ (oder Locker-Kuerzel) [10115]: ").strip()
        dummy = []
        extra = input("  Zusaetzliche Dummy-Item-IDs (Komma getrennt, leer=keine): ").strip()
        if extra:
            dummy = [x.strip().upper() for x in extra.split(",") if x.strip()]
        pm = input("  Zahlungsmethode (card=Kreditkarte / ideal=iDEAL-BankQ-Revolut) [card]: ").strip().lower()
        if pm not in ("card", "ideal"):
            pm = "card"
        for acc in accounts:
            email = acc.get("email")
            pwd = acc.get("password")
            proxy = acc.get("proxy") or ""
            async with self._client(cc, email=email, log=log,
                                    proxy=proxy or await self._acquire_proxy()) as c:
                if not await self._restore_client(c, pwd):
                    log.line("ACO", pid, email, "Login failed", "err")
                    log.status("error")
                    bar.render()
                    continue
                log.line("ACO", pid, email, f"Checkout ({pm}) mit PLZ/Locker {ship or '-'} ...", "info")
                ok = await c.checkout(pid, plz=ship, dummy=dummy, payment=pm)
                log.status("ok" if ok else "error")
                log.line("ACO", pid, email,
                         "Checkout prepared" if ok else "Checkout failed",
                         "ok" if ok else "err")
                if ok:
                    store.append("checkout", {
                        "email": email, "email_password": "",
                        "password": pwd,
                        "firstName": acc.get("firstName", ""),
                        "lastName": acc.get("lastName", ""),
                        "phoneNumber": acc.get("phonenumber", ""),
                        "country_iso": cc, "proxy": proxy,
                        "asins": ";".join([pid] + dummy),
                        "addressLine1": acc.get("addressLine1", ""),
                        "addressLine2": acc.get("addressLine2", ""),
                        "city": acc.get("city", ""),
                        "state": acc.get("state", ""),
                        "postalCode": ship, "addressCountry": cc,
                        "bank_code": "", "cardNumber": acc.get("cardNumber", ""),
                        "cardMonth": acc.get("cardMonth", ""),
                        "cardYear": acc.get("cardYear", ""),
                        "cardCvc": acc.get("cardCvc", ""),
                        "cardHolderName": acc.get("cardHolderName", ""),
                        "giftcard": "", "webhook_url": "",
                        "delivery_preference": "",
                    }, dedupe_keys=["email", "asins"])
                    store.add_asin_history(pid)
                bar.render()
        print()

    # ---------------------------------------------------------- 8 ADDRESS
    async def address(self, cc: str) -> None:
        """8 ADDRESS-Modus: legt Default-Lieferadresse + Zahlung in einer
        EIGENEN zweiten Session an (A7). Karte erst hier, nicht beim Erstellen."""
        log = self._log(cc)
        bar = StatusBar(log)
        bar.header(f"Amazon{cc.upper()} ADDRESS")
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
            async with self._client(cc, email=email, log=log,
                                    proxy=await self._acquire_proxy()) as c:
                if not await self._restore_client(c, pwd):
                    log.line("Addr", asin, email, "Login failed", "err")
                    log.status("error")
                    bar.render()
                    continue
                log.line("Addr", asin, email, "2. Session: Adresse + Zahlung ...", "info")
                ok = await self._address_one(c, cc, asin, plz, addr, stadt, card)
                log.status("ok" if ok else "error")
                log.line("Addr", asin, email,
                         "Address+card set" if ok else "Failed", "ok" if ok else "err")
                bar.render()
        print()

    async def _address_one(self, c: AmazonClient, cc: str, asin: str,
                           plz: str, addr: str, stadt: str, card: dict) -> bool:
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

    # ---------------------------------------------------------- 9 Selftest
    async def selftest(self, cc: str = "ALL") -> None:
        """9 Selftest: prueft alle 21 Amazon-Domains ueber je einen Proxy und
        meldet Sperrquote (403/202/404 = blocked). Messwert < 5%."""
        from modules.Engine.Shopify.shopify_core import ProxyPool, Settings, State
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


def _now() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _proxy_part(proxy: str, idx: int) -> str:
    """Proxy-Format IP:PORT:USER:PASS -> Teil (host/port/pool/user)."""
    parts = proxy.split(":")
    return parts[idx] if idx < len(parts) else ""


def run(cc: str = "DE") -> int:
    AmazonAIOModule().run()
    return 0


if __name__ == "__main__":
    cc = sys.argv[1].upper() if len(sys.argv) > 1 else "DE"
    sys.exit(run(cc))