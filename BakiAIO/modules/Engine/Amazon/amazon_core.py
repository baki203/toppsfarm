#!/usr/bin/env python3
"""amazon_core - gemeinsame Basis fuer alle Amazon-Module im Skyridge-Muster.
Liefert: 21 Amazon-Domains, farbige Skyridge-CLI-Zeile, Live-Statusleiste,
SessionStore (persistente Cookie-/Browser-Profile je Konto) und einen
AmazonClient (Signin / Invite / Address / Location / Checkout-Endpunkte)."""
from __future__ import annotations

import asyncio
import datetime
import re
import time
from pathlib import Path

from curl_cffi.requests import AsyncSession

from utilities.root import ROOT

# CCF: Ländercode -> (Domain, Default-Waehrung, Default-Locale/Region)
DOMAINS = {
    "MX": ("amazon.com.mx", "MXN", "es-MX"),
    "BR": ("amazon.com.br", "BRL", "pt-BR"),
    "GB": ("amazon.co.uk", "GBP", "en-GB"),
    "DE": ("amazon.de", "EUR", "de-DE"),
    "FR": ("amazon.fr", "EUR", "fr-FR"),
    "IT": ("amazon.it", "EUR", "it-IT"),
    "ES": ("amazon.es", "EUR", "es-ES"),
    "NL": ("amazon.nl", "EUR", "nl-NL"),
    "SE": ("amazon.se", "SEK", "sv-SE"),
    "PL": ("amazon.pl", "PLN", "pl-PL"),
    "BE": ("amazon.com.be", "EUR", "nl-BE"),
    "IE": ("amazon.ie", "EUR", "en-IE"),
    "TR": ("amazon.com.tr", "TRY", "tr-TR"),
    "IN": ("amazon.in", "INR", "en-IN"),
    "SG": ("amazon.sg", "SGD", "en-SG"),
    "AU": ("amazon.com.au", "AUD", "en-AU"),
    "AE": ("amazon.ae", "AED", "en-AE"),
    "SA": ("amazon.sa", "SAR", "en-SA"),
    "EG": ("amazon.eg", "EGP", "en-EG"),
    "ZA": ("amazon.co.za", "ZAR", "en-ZA"),
    "CN": ("amazon.cn", "CNY", "zh-CN"),
}

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def domain_for(cc: str) -> str:
    return DOMAINS.get(cc.upper(), ("amazon." + cc.lower(), "EUR", "en"))[0]


def currency_for(cc: str) -> str:
    return DOMAINS.get(cc.upper(), ("amazon." + cc.lower(), "EUR", "en"))[1]


# -------------------------------------------------------------------------- CLI
# Farben (ANSI). Farbe pro Log-Level, wie Skyridge (Stufeneinfarbung der Zeile).
ANSI = {
    "info": "\033[36m", "ok": "\033[32m", "warn": "\033[33m",
    "err": "\033[31m", "dim": "\033[90m", "bold": "\033[1m",
    "mag": "\033[35m", "reset": "\033[0m",
}


def paint(text: str, *styles: str) -> str:
    return "".join(ANSI[s] for s in styles if s in ANSI) + text + ANSI["reset"]


class SkyLogger:
    """Farbige Skyridge-CLI-Zeile:
    [HH:MM:SS:mmm] [tid] [Site Feature] [ASIN] [email] Nachricht
    Ebene als Farbe der Zeile. Status-Zaehler live in der Kopfzeile."""

    def __init__(self, site: str = "AmazonDE"):
        self.site = site
        self.counters: dict[str, int] = {}
        self._last_status = ""
        self._tid = 0

    def _ts(self) -> str:
        return datetime.datetime.now().strftime("%H:%M:%S") + f":{int(time.time() * 1000) % 1000:03d}"

    def status(self, key: str, n: int = 1):
        self.counters[key] = self.counters.get(key, 0) + n

    def line(self, feature: str, asin: str, email: str, msg: str,
             level: str = "info", tid: int | None = None) -> str:
        if tid is None:
            self._tid += 1
            tid = self._tid
        line = (f"[{self._ts()}] [{tid:>4}] [{self.site} {feature}] "
                f"[{asin or '-':<11}] [{email or '-':<38}] {msg}")
        color = {"ok": "ok", "warn": "warn", "err": "err",
                 "dim": "dim", "mag": "mag"}.get(level, "info")
        print(paint(line, color))
        return line

    def render_status(self, width: int = 120) -> str:
        """Statusleiste (Kopfzeile) wie 'invited 12 ... already invited 34 ...'.
        Reihenfolge/Kuerzel je Modul zaehler-agnostisch; Farben wie Skyridge."""
        order = ("invited", "already", "requested", "entered", "won", "lost",
                 "restored", "added", "ok", "created", "error", "skipped", "proxy")
        parts = []
        for k in order:
            v = self.counters.get(k)
            if v is None:
                continue
            label = {"already": "already invited", "entered": "already entered",
                     "restored": "session restored", "added": "activity",
                     "ok": "ok", "created": "created"}.get(k, k)
            color = {"invited": "ok", "requested": "mag", "won": "ok",
                     "restored": "dim", "added": "info", "ok": "ok",
                     "created": "ok", "already": "dim", "entered": "dim",
                     "lost": "warn", "error": "err", "skipped": "dim",
                     "proxy": "err"}.get(k, "info")
            parts.append(paint(f"{label} {v}", color))
        # nicht in der Ordnung gefuhrte Zaehler hinten anhaengen
        for k, v in self.counters.items():
            if k in order:
                continue
            parts.append(paint(f"{k}:{v}", "info"))
        bar = "  " + "   ".join(parts)
        return bar[:width]


class StatusBar:
    """Live-Statusleiste (Kopfzeile): rendert den Zaehlerstand beim Start und
    vor jeder neuen Logzeile. Einfacher ANSI-Ansatz (keine Extra-Abhaengigkeit)."""

    def __init__(self, log: SkyLogger):
        self.log = log

    def render(self):
        bar = self.log.render_status()
        if bar:
            print("\r\033[2K" + bar + "\033[0K", end="\r", flush=True)

    def header(self, title: str = ""):
        """Rendert eine dauerhafte Kopfzeile (ohne Live-Cursor) vor dem Log."""
        bar = self.log.render_status()
        if bar:
            line = paint("==" * 40, "bold")
            print(line)
            print(" " + (paint(title, "bold") + "  " if title else "") + bar)
            print(line)


# ------------------------------------------------------------------- SessionStore
class SessionStore:
    """Persistentes Browserprofil + Cookies je Konto (A2).
    Verzeichnis: var/sessions/<site>/<email>/  -> cookies.json, profile/."""

    def __init__(self, site: str = "amazon"):
        self.base = ROOT / "var" / "sessions" / site

    def dir_for(self, email: str) -> Path:
        d = self.base / _slug(email)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def profile_dir(self, email: str) -> Path:
        p = self.dir_for(email) / "profile"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def cookies_path(self, email: str) -> Path:
        return self.dir_for(email) / "cookies.json"

    async def save_cookies(self, email: str, cookies: list[dict]):
        p = self.cookies_path(email)
        await asyncio.to_thread(p.write_text,
                                json_dumps(cookies), encoding="utf-8")

    async def load_cookies(self, email: str) -> list[dict] | None:
        p = self.cookies_path(email)
        if not p.exists():
            return None
        try:
            return await asyncio.to_thread(json_loads, p)
        except Exception:
            return None

    async def save_state(self, email: str, data: dict):
        p = self.dir_for(email) / "state.json"
        await asyncio.to_thread(p.write_text, json_dumps(data), encoding="utf-8")

    async def load_state(self, email: str) -> dict:
        p = self.dir_for(email) / "state.json"
        if not p.exists():
            return {}
        try:
            return await asyncio.to_thread(json_loads, p)
        except Exception:
            return {}


def _slug(email: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", email)


def json_dumps(o) -> str:
    import json
    return json.dumps(o, ensure_ascii=False)


def json_loads(p: Path):
    import json
    return json.loads(p.read_text(encoding="utf-8"))


# ----------------------------------------------------------------- AmazonClient
class AmazonClient:
    """HTTP-Session fuer Amazon. Cookies im SessionStore gesichert.
    Endpunkte/Logik laut KNOWLEDGE.md (behauptet-Markierung beibehalten)."""

    def __init__(self, cc: str, email: str = "", log: SkyLogger | None = None,
                 store: SessionStore | None = None, proxy: str | None = None):
        self.cc = cc.upper()
        self.domain = domain_for(self.cc)
        self.currency = currency_for(self.cc)
        self.email = email
        self.log = log or SkyLogger()
        self.store = store or SessionStore()
        kw = {
            "impersonate": "chrome", "timeout": 30,
            "headers": {"user-agent": UA, "accept-language": DOMAINS[self.cc][2]},
        }
        if proxy:
            kw["proxy"] = proxy
        self.s = AsyncSession(**kw)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()

    async def close(self):
        try:
            await self.s.close()
        except Exception:
            pass

    async def restore(self):
        """Laedt gespeicherte Cookies und setzt sie zurueck (Skyridge:
        'Restoring session ...' / 'Session restored!'). Bevorzugt die Skyridge-
        Session-Datei accounts/Amazon/.sessions/<email>__<CC>.json, Fallback auf
        den SessionStore (var/sessions)."""
        try:
            from modules.Engine.Amazon.amazon_store import AmazonStore
            cookies = AmazonStore("amazon").load_session(self.email, self.cc)
        except Exception:
            cookies = None
        if not cookies:
            cookies = await self.store.load_cookies(self.email)
        if not cookies:
            return False
        self.s.cookies.update({c["name"]: c["value"] for c in cookies
                               if c.get("name") and c.get("value")})
        return True

    async def save(self):
        cookies = []
        for c in self.s.cookies.jar:
            try:
                cookies.append({"name": c.name, "value": c.value,
                                "domain": c.domain, "path": c.path or "/"})
            except Exception:
                pass
        # Skyridge .sessions-Datei (primär) + SessionStore (Fallback)
        try:
            from modules.Engine.Amazon.amazon_store import AmazonStore
            AmazonStore("amazon").save_session(self.email, cookies, self.cc)
        except Exception:
            pass
        await self.store.save_cookies(self.email, cookies)

    def url(self, path: str, **params) -> str:
        from urllib.parse import urlencode
        q = ("?" + urlencode(params)) if params else ""
        return f"https://{self.domain}{path}{q}"

    async def signin(self, password: str) -> bool:
        """Login. (behauptet laut KNOWLEDGE: /ap/signin?openid.pape.max_auth_age=0
        &openid.return_to=...&openid.assoc_handle=saflex|flex)."""
        try:
            r = await self.s.get(self.url("/ap/signin", **{
                "openid.pape.max_auth_age": "0",
                "openid.return_to": f"https://{self.domain}/",
                "openid.assoc_handle": "flex",
            }))
            if r.status_code != 200:
                return False
            html = r.text
            m = re.search(r'name="[^"]*" value="([^"]+)"', html)
            # vereinfachter POST-Login
            r = await self.s.post(self.url("/ap/signin"), data={
                "email": self.email, "password": password,
                "create": "0", "action": "sign-in",
            })
            ok = r.status_code == 200 and ("auth-cookie" in self.s.cookies.get_dict()
                                           or "/ap/signin" not in str(r.url))
            if ok:
                await self.save()
            return ok
        except Exception:
            return False

    async def add_shipping_address(self, asin: str, addr: dict) -> bool:
        """Add-Address: /checkout/p/{ASIN}/add-new-shipping-address?pipelineType=Chewbacca (x1)."""
        try:
            r = await self.s.post(
                self.url(f"/checkout/p/{asin}/add-new-shipping-address",
                         pipelineType="Chewbacca"),
                json=addr)
            return r.status_code in (200, 202)
        except Exception:
            return False

    async def set_location(self, zip_code: str) -> bool:
        """Postleitzahl/Location setzen. (behauptet x3: empty/invalid body loest
        'aborting location change' aus - body muss gueltig sein)."""
        try:
            r = await self.s.post(
                self.url("/amazon/navigation/location/update", **{"_": int(time.time() * 1000)}),
                json={"locationType": "LOCATION_INPUT", "zipCode": zip_code,
                      "storeContext": "generic", "deviceType": "web",
                      "pageType": "Gateway", "actionSource": "glow"},
                headers={"content-type": "application/json"})
            return r.status_code == 200
        except Exception:
            return False

    async def add_payment_method(self, card: dict) -> bool:
        """ADDRESS-Modus: Karte als Zahlungsmittel hinterlegen (behauptet laut
        KNOWLEDGE, Endpunkt variiert je Domain; Grundgeruest per Session).
        `card` = {holder, number, exp_month, exp_year, cvv}."""
        try:
            r = await self.s.post(
                self.url("/wallet", **{"xkid": self.domain.split(".")[0]}),
                json={"cardholderName": card.get("holder", ""),
                      "addCreditCardNumber": card.get("number", ""),
                      "addCreditCardExpDate": f"{card.get('exp_month','')}/{card.get('exp_year','')}",
                      "addCreditCardVerificationNumber": card.get("cvv", ""),
                      "oneClick": "false"},
                headers={"content-type": "application/json"})
            return r.status_code in (200, 202)
        except Exception:
            return False

    # ------------------------------------------------------------ Invite (HTTP)
    async def fetch_invite_details(self, asin: str) -> dict | None:
        """Liest Invite-Details von der Produktseite (PDP). Variiert je Domain;
        Liefert {'asin', 'title', 'price', 'invite_id'} oder None."""
        try:
            r = await self.s.get(self.url(f"/dp/{asin}"), timeout=30)
            if r.status_code != 200:
                return None
            html = r.text
            title = ""
            m = re.search(r'<span[^>]*id="productTitle"[^>]*>(.*?)</span>', html, re.S)
            if m:
                title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
                import html as _html
                title = _html.unescape(title)
            price = ""
            for pat in (r'class="a-offscreen"[^>]*>([^<]+)',
                        r'id="priceblock_ourprice"[^>]*>([^<]+)'):
                mm = re.search(pat, html)
                if mm:
                    price = mm.group(1).strip()
                    break
            invite_id = ""
            for pat in (r'data-invite-registration-id="([^"]+)"',
                        r'data-registration-id="([^"]+)"',
                        r'registrationId[":=]\s*"([^"]+)"'):
                mm = re.search(pat, html)
                if mm:
                    invite_id = mm.group(1)
                    break
            return {"asin": asin, "title": title, "price": price,
                    "invite_id": invite_id}
        except Exception:
            return None

    async def request_invite(self, asin: str) -> str:
        """Requestet den Invite via HTTP. Zustand: 'requested'|'already'|'error'."""
        try:
            r = await self.s.get(self.url(f"/dp/{asin}"), timeout=30)
            if r.status_code != 200:
                return "error"
            low = r.text.lower()
            if ("already registered" in low or "bereits registriert" in low
                    or "bereits angemeldet" in low or "already requested" in low):
                return "already"
            # Registrierungs-Endpunkt (behauptet; variiert je Domain)
            r = await self.s.post(self.url(f"/gp/aws/invite-register"),
                                  json={"asin": asin, "quantity": 1,
                                        "submissionToken": "1"}, timeout=30)
            if r.status_code in (200, 202):
                return "requested"
            return "already"
        except Exception:
            return "error"

    async def check_invite(self, asin: str) -> bool:
        """Prueft, ob das Konto ein Invite gewonnen hat (Liste/Status)."""
        try:
            r = await self.s.get(self.url("/gp/most-wished-for/list/ref=gw_iph"),
                                 timeout=30)
            low = (r.text or "").lower()
            if r.status_code != 200:
                return False
            return ("gewonnen" in low or "you've been selected" in low
                    or "selected for purchase" in low or asin.lower() in low)
        except Exception:
            return False

    async def add_to_cart(self, asin: str) -> bool:
        try:
            r = await self.s.get(self.url(f"/gp/cart/ajax-endpoint/add-to-cart"),
                                 params={"asin": asin, "quantity": 1,
                                         "source": "detail"}, timeout=30)
            return r.status_code == 200
        except Exception:
            return False

    async def add_wishlist(self, asin: str) -> bool:
        try:
            r = await self.s.get(self.url("/gp/aws/add-to-wishlist"),
                                 params={"asin": asin}, timeout=30)
            return r.status_code == 200
        except Exception:
            return False

    async def get_cart_count(self) -> int:
        try:
            r = await self.s.get(self.url("/gp/cart/view.html"), timeout=30)
            m = re.search(r'id="nav-cart-count"[^>]*>(\d+)', r.text)
            return int(m.group(1)) if m else 0
        except Exception:
            return 0

    async def checkout(self, asin: str, plz: str = "", dummy: list | None = None,
                       payment: str = "card") -> bool:
        """ACO (HTTP): Produkt + Dummy-Items in Warenkorb, PLZ setzen, zur Kasse.
        Zahlung: 'card' (Kreditkarte) oder 'ideal' (iDEAL/BankQ/Revolut)."""
        try:
            if plz:
                await self.set_location(plz)
            if not await self.add_to_cart(asin):
                return False
            for d in (dummy or []):
                await self.add_to_cart(d)
            r = await self.s.get(self.url("/gp/cart/cart.html"), timeout=30)
            if r.status_code != 200:
                return False
            # Kasse oeffnen (behauptet; variiert je Domain/Zahlungsart)
            r = await self.s.get(self.url("/gp/buy/1/"), timeout=30)
            return r.status_code == 200
        except Exception:
            return False


class AmazonBrowser:
    """Browser-basierte Amazon-Session je Konto (Skyridge-Muster).

    Persistenter Chromium-Kontext pro Konto: var/browser-amazon-<cc>/<email>/
    Cookies bleiben ueber laufende Module hinweg erhalten (Login nur beim ersten
    Mal noetig). Operationen sind aufgebaut, damit echte Invite-Requests/Checkout
    mit einer eingeloggten Session funktionieren (Anti-Bot erlaubt nur so).

    Feature-Aufrufe:
      restore_or_login() -> bool        Session vorhanden / Login ok
      goto_product(asin) -> int         Produktseite mit Retry (attempt x/3)
      fetch_invite_details(asin) -> dict|None   PDP-Details (Titel/Preis/Invite-ID)
      request_invite(asin) -> str       Zustand: 'requested'|'already'|'error'
      check_invite(asin) -> bool        gewonnen?
      add_to_cart(asin)/add_wishlist    Farmer
      precheckout(asin) -> bool         ACO-Vorbereitung (Karte/Adresse/Locker)
    """

    def __init__(self, cc: str, email: str, password: str = "",
                 proxy: str | None = None, headless: bool = True,
                 log: SkyLogger | None = None, store: SessionStore | None = None):
        self.cc = cc.upper()
        self.domain = domain_for(self.cc)
        self.email = email
        self.password = password
        self.proxy = proxy
        self.headless = headless
        self.log = log or SkyLogger(site=f"Amazon{self.cc.upper()}")
        self.store = store or SessionStore("amazon")
        self.browser = None
        self.page = None
        self._dir = ROOT / "var" / f"browser-amazon-{self.cc}" / _slug(email)

    async def start(self) -> None:
        from utilities.browser import Browser
        if self.browser:
            return
        self.browser = Browser(user_data_dir=str(self._dir),
                               headless=self.headless, proxy=self.proxy)
        await self.browser.start()
        self.page = await self.browser.new_page()

    async def stop(self) -> None:
        if self.browser:
            await self.browser.stop()
        self.browser = self.page = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *exc):
        await self.stop()

    async def get_cookies(self) -> list[dict]:
        """Liest die aktuellen Browser-Cookies als Skyridge-Cookie-Liste
        [{name, value, domain, path}]. Liefert [] wenn nicht verfuegbar."""
        try:
            ctx = self.browser.browser if self.browser else None
            if not ctx:
                return []
            out = []
            for c in await ctx.cookies():
                out.append({"name": c.get("name", ""), "value": c.get("value", ""),
                            "domain": c.get("domain", ""), "path": c.get("path", "/")})
            return out
        except Exception:
            return []

    async def export_cookies(self) -> None:
        """Schreibt die aktuellen Browser-Cookies in den SessionStore, damit
        die HTTP-Module (Invites/Farmer/Checker) dieselbe Session wiederher-
        stellen koennen (Session Manager als einzige Login-Quelle)."""
        cookies = await self.get_cookies()
        if cookies:
            try:
                await self.store.save_cookies(self.email, cookies)
            except Exception:
                pass

    # ---------------------------------------------------------------- Session
    async def restore_or_login(self) -> bool:
        """True, wenn eine Session aktiv (eingeloggt) oder der Login gelingt."""
        if not self.page:
            await self.start()
        home = f"https://{self.domain}/"
        try:
            await self.page.goto(home, wait_until="domcontentloaded", timeout=40000)
        except Exception:
            return False
        if await self._logged_in():
            return True
        if not self.password:
            return False
        return await self._login()

    async def _logged_in(self) -> bool:
        try:
            if await self.page.locator("input[name='email']").count():
                return False
            # eingeloggt: Konto-Link sichtbar ODER nicht auf /ap/signin
            url = (self.page.url or "").lower()
            if "/ap/signin" in url or "/ap/register" in url:
                return False
            for sel in ('#nav-link-accountList', '[data-csa-c-slot-id="nav-link-accountList"]',
                        'a[href*="gp/yourstore"]'):
                if await self.page.locator(sel).first.count():
                    return True
            return True  # keine Login-Form => angenommen eingeloggt
        except Exception:
            return False

    async def _login(self) -> bool:
        try:
            await self.page.goto(self.url("/ap/signin", max_auth_age=0,
                                          return_to=f"https://{self.domain}/",
                                          assoc_handle="flex"),
                                 wait_until="domcontentloaded", timeout=40000)
            await self._type('input[name="email"]', self.email)
            for btn in ('button[type="submit"]', '#continue', 'input[type="submit"]'):
                if await self.page.locator(btn).first.count():
                    await self.page.locator(btn).first.click(timeout=8000)
                    break
            await self.page.wait_for_load_state("domcontentloaded")
            # Passwort-Seite (manchmal direkt im selben Formular)
            if not await self._logged_in():
                if self.password:
                    await self._type('input[name="password"]', self.password)
                    for btn in ('button[type="submit"]', '#signInSubmit',
                                'input[type="submit"]'):
                        if await self.page.locator(btn).first.count():
                            await self.page.locator(btn).first.click(timeout=8000)
                            break
                    await self.page.wait_for_load_state("domcontentloaded")
            ok = await self._logged_in()
            if ok:
                self.log.line("Session", "", self.email, "Session restored!", "dim")
            else:
                self.log.line("Session", "", self.email,
                              "Login moeglicherweise fehlgeschlagen (Captcha/OTP?)", "warn")
            return ok
        except Exception as exc:
            self.log.line("Session", "", self.email, f"Login Fehler: {type(exc).__name__}", "err")
            return False

    async def _type(self, selector: str, value: str) -> None:
        loc = self.page.locator(selector).first
        if await loc.count():
            await loc.fill(value)
            await asyncio.sleep(0.2)

    def url(self, path: str, **params) -> str:
        from urllib.parse import urlencode
        q = ("?" + urlencode(params)) if params else ""
        return f"https://{self.domain}{path}{q}"

    # ---------------------------------------------------------------- Product
    async def goto_product(self, asin: str, attempts: int = 3) -> int:
        """Produktseite laden; loggt 'Loading product page (attempt x/3)'.
        Rueckgabe: HTTP-Statuscode (oder 0 bei Fehler)."""
        last = 0
        for attempt in range(1, attempts + 1):
            self.log.line("Invite", asin, self.email,
                          f"Loading product page (attempt {attempt}/{attempts}) ...", "info")
            try:
                resp = await self.page.goto(self.url(f"/dp/{asin}"),
                                            wait_until="domcontentloaded", timeout=40000)
                last = resp.status if resp else 0
                if last == 200:
                    return last
            except Exception:
                last = 0
            await asyncio.sleep(1.0)
        return last

    async def fetch_invite_details(self, asin: str) -> dict | None:
        """Liest Titel + Preis + Invite-ID aus der PDP. Invite-ID ist oft eine
        UUID in der Angebots-URL oder im Registrierungsformular."""
        try:
            title = await self.page.locator("#productTitle").first.text_content()
            title = (title or "").strip()
        except Exception:
            title = ""
        price = ""
        for sel in ('#corePriceDisplay_desktop_feature_div .a-price .a-offscreen',
                    '.a-price .a-offscreen', '#priceblock_ourprice'):
            try:
                p = await self.page.locator(sel).first.text_content()
                if p:
                    price = (p or "").strip()
                    break
            except Exception:
                continue
        invite_id = ""
        for sel in ('[data-invite-registration-id]', '[data-registration-id]',
                    'input[name*="registrationId"]'):
            try:
                v = await self.page.locator(sel).first.get_attribute(
                    "data-invite-registration-id") or await self.page.locator(
                    sel).first.get_attribute("data-registration-id")
                if v:
                    invite_id = v
                    break
            except Exception:
                continue
        return {"asin": asin, "title": title, "price": price, "invite_id": invite_id}

    async def request_invite(self, asin: str) -> str:
        """Requestet den Invite. Zustand: 'requested'|'already'|'error'."""
        try:
            page = self.page
            # Invite-Formular/Button auf der Produktseite
            for sel in ('[data-testid="invite-register"]',
                        'button:has-text("Auf die Liste setzen")',
                        'button:has-text("Invite anfragen")',
                        'button:has-text("Registrieren")',
                        'button:has-text("Invite")',
                        '[id*="invite"] button', '#invite-button'):
                loc = page.locator(sel).first
                if await loc.count():
                    await loc.click(timeout=8000)
                    return "requested"
            # bereits angemeldet/registriert?
            body = await self._body_text()
            low = body.lower()
            if ("bereits registriert" in low or "already registered" in low
                    or "bereits angemeldet" in low):
                return "already"
            # Kein Invite-Formular sichtbar -> schon eingetragen
            return "already"
        except Exception:
            return "error"

    async def check_invite(self, asin: str) -> bool:
        try:
            body = await self._body_text()
            low = body.lower()
            return ("gewonnen" in low or "you've been selected" in low
                    or "invite gewonnen" in low or "selected for purchase" in low
                    or asin.lower() in low)
        except Exception:
            return False

    async def add_to_cart(self, asin: str) -> bool:
        try:
            for sel in ('#add-to-cart-button', 'button:has-text("In den Einkaufswagen")',
                        'button:has-text("Add to Cart")', 'input[name="submit.add-to-cart"]'):
                loc = self.page.locator(sel).first
                if await loc.count():
                    await loc.click(timeout=8000)
                    return True
            return False
        except Exception:
            return False

    async def add_wishlist(self, asin: str) -> bool:
        try:
            for sel in ('[id*="add-to-wishlist"]', '#add-to-wishlist-button',
                        'a[href*="wlOldPageType=WishList"]'):
                loc = self.page.locator(sel).first
                if await loc.count():
                    await loc.click(timeout=8000)
                    return True
            return False
        except Exception:
            return False

    async def set_location(self, zip_code: str) -> bool:
        """PLZ/Location im Browser setzen (Glow-Popup)."""
        try:
            await self.page.goto(self.url("/", **{"_": int(time.time() * 1000)}),
                                 wait_until="domcontentloaded", timeout=30000)
            for sel in ('#nav-global-location-popover-link', '#nav-global-location-data-modal-action',
                        '[data-csa-c-slot-id="nav-global-location-search"]'):
                loc = self.page.locator(sel).first
                if await loc.count():
                    await loc.click(timeout=5000)
                    break
            await asyncio.sleep(1.0)
            await self._type('input[name="locationSearchInput"]', zip_code)
            for sel in ('[name="glowDoneButton"]', 'button[data-csa-c-content-id="glow-toaster-submit"]',
                        'button[data-csa-c-slot-id="glow-toaster-submit"]',
                        'input[type="submit"][name="glowSearchSubmit"]'):
                loc = self.page.locator(sel).first
                if await loc.count():
                    await loc.click(timeout=5000)
                    break
            await asyncio.sleep(1.0)
            return True
        except Exception:
            return False

    async def precheckout(self, asin: str, plz: str = "", dummy_items: list | None = None,
                          payment: str = "card") -> bool:
        """ACO-Vorbereitung: PLZ setzen, Karte/iDEAL als Zahlung hinterlegen.
        echte Checkout-Endpunkte variieren; Grundgeruest setzt Location +
        navigiert zur Kasse. Zurueck: True wenn erreichbar."""
        try:
            if plz:
                await self.set_location(plz)
            await self.add_to_cart(asin)
            for _dummy in (dummy_items or []):
                try:
                    await self.page.goto(self.url(f"/dp/{_dummy}"),
                                         wait_until="domcontentloaded", timeout=30000)
                    await self.add_to_cart(_dummy)
                except Exception:
                    pass
            await self.page.goto(self.url("/gp/cart/cart.html"),
                                 wait_until="domcontentloaded", timeout=30000)
            return True
        except Exception:
            return False

    async def _body_text(self) -> str:
        try:
            return await self.page.evaluate("document.body ? document.body.innerText : ''")
        except Exception:
            return ""


def accounts_dir(site: str = "amazon") -> Path:
    """Kanonischer Konten-Ordner: ROOT/accounts/<site> (ROOT = repo-Root,
    wo config liegt). Generator und load_accounts schreiben/lesen denselben."""
    d = ROOT / "accounts" / site
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_accounts(site: str = "amazon") -> list[dict]:
    """Laedt Konten im Skyridge-Request-Mode-Flow aus mehreren Quellen und
    vereinigt sie (Dedupe ueber Email):

    1. accounts/<site>/accounts.csv   (Skyridge-Format, bevorzugt - Tasks)
    2. accounts/<site>/*.txt          (Generator-Artefakte <email>.txt)
    3. accounts/<site>/profiles.yaml  (Fallback, gitignored)

    Damit funktioniert: Generator -> Konten -> CSV/.txt -> Invite/Farmer/Checker
    lesen dieselben Konten, ohne vorher den Session Manager nutzen zu muessen.
    """
    base = accounts_dir(site)
    rows: list[dict] = []
    seen: set[str] = set()

    def _add(r: dict):
        # Keys normalisieren (CSV liefert u. a. EMAIL/PASSWORD/PID gross)
        norm = {str(k).strip().lower(): (v or "").strip() for k, v in r.items()}
        email = norm.get("email", "").lower()
        if not email or email in seen:
            return
        seen.add(email)
        rows.append(norm)

    # 1. Skyridge-CSV (Tasks)
    csv = base / "accounts.csv"
    if csv.exists():
        for r in _load_csv(csv):
            _add(r)
    # 2. Generator-Artefakte (<email>.txt)
    for f in sorted(base.glob("*.txt")):
        if f.name.lower() in ("readme.txt", "accounts.txt"):
            continue
        try:
            d = {}
            for ln in f.read_text(encoding="utf-8").splitlines():
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    d[k.strip().lower()] = v.strip()
            if d.get("email"):
                _add(d)
        except Exception:
            continue
    # 3. profiles.yaml (Fallback)
    p = base / "profiles.yaml"
    if p.exists():
        import yaml
        try:
            for r in (yaml.safe_load(p.read_text(encoding="utf-8")) or []):
                _add(r)
        except Exception:
            pass
    return rows


def _load_csv(p: Path) -> list[dict]:
    import csv
    rows = []
    try:
        with open(p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows.append({k.strip(): (v or "").strip() for k, v in r.items()})
    except Exception:
        pass
    return rows