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

ROOT = Path(__file__).resolve().parent.parent.parent

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

    def render_status(self, width: int = 100) -> str:
        """Statusleiste (Kopfzeile) wie 'invited 12 ... already invited 34 ...'"""
        if not self.counters:
            return ""
        parts = []
        for k, v in self.counters.items():
            color = {"invited": "ok", "already": "dim", "error": "err",
                     "requested": "mag", "skipped": "dim"}.get(k, "info")
            parts.append(paint(f"{k}:{v}", color))
        bar = "  " + "   ".join(parts)
        bar = bar[:width]
        return bar


class StatusBar:
    """Live-Statusleiste (Kopfzeile): rendert den Zaehlerstand beim Start und
    vor jeder neuen Logzeile. Einfacher ANSI-Ansatz (keine Extra-Abhaengigkeit)."""

    def __init__(self, log: SkyLogger):
        self.log = log

    def render(self):
        bar = self.log.render_status()
        if bar:
            print("\r\033[2K" + bar + "\033[0K", end="\r", flush=True)


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
        'Restoring session ...' / 'Session restored!')."""
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


def load_accounts(site: str = "amazon") -> list[dict]:
    """Laedt Konten aus accounts/<site>/profiles.yaml (gitignored) oder
    accounts/<site>/accounts.csv (Skyridge-Format)."""
    p = ROOT / "accounts" / site / "profiles.yaml"
    if p.exists():
        import yaml
        try:
            return yaml.safe_load(p.read_text(encoding="utf-8")) or []
        except Exception:
            return []
    csv = ROOT / "accounts" / site / "accounts.csv"
    if csv.exists():
        return _load_csv(csv)
    return []


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