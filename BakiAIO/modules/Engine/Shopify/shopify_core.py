#!/usr/bin/env python3
"""shopify_core - gemeinsame Shopify-Engine fuer alle Shopify-basierten Module.
HTTP-first, Browser nur Fallback. Modulname wird ueber MODULE gesetzt."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import re
import sqlite3
import subprocess
import sys
import time
import zlib
from urllib.parse import unquote
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from curl_cffi.requests import AsyncSession
from rich.console import Console
from rich.logging import RichHandler

from modules.base import BaseModule

from utilities.proxy import parse_proxy_lines  # noqa: E402

from utilities.root import ROOT, APP_ROOT
CONSOLE = Console()
LOG = logging.getLogger("toppsfarm")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
COLORS = {"new": 0x2ECC71, "ok": 0x9B59B6, "fail": 0xE74C3C, "info": 0x95A5A6}


def load_env() -> dict:
    p = ROOT / "config" / "keys.env"
    out = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


ENV = load_env()


def _imap_host_for(mastermails: list, user: str = "") -> str:
    """Leitet den IMAP-Server aus einer Mastermail ab (gmail -> imap.gmail.com,
    sonst imap.<domain>). Leer, wenn keine E-Mail-Adresse vorliegt."""
    for m in mastermails or []:
        mm = str((m or {}).get("mastermail") or "").strip()
        if not mm and user:
            mm = user
        if "@" in mm:
            dom = mm.rsplit("@", 1)[1].lower()
            if dom in ("gmail.com", "googlemail.com"):
                return "imap.gmail.com"
            return f"imap.{dom}"
    return ""


@dataclass
class Settings:
    hosts: list = field(default_factory=list)
    ship_country: str = "DE"
    impersonate: str = "chrome"
    locale: str = "de-DE"
    concurrency_http: int = 60
    concurrency_browser: int = 8
    poll_interval_s: float = 2.5
    poll_jitter_s: float = 0.9
    # Quellen des Monitors in dieser Reihenfolge; die naechste wird nur benutzt,
    # wenn die davor nichts liefert. Moeglich: sitemap, storefront, products_json
    monitor_sources: list = field(default_factory=lambda: ["sitemap", "storefront"])
    timeout_s: int = 25
    max_retries: int = 3
    retry_backoff_s: float = 1.5
    captcha: dict = field(default_factory=dict)
    queue: dict = field(default_factory=dict)
    notify: dict = field(default_factory=dict)
    mail: dict = field(default_factory=dict)
    sms: dict = field(default_factory=dict)
    geo: dict = field(default_factory=dict)
    proxy: dict = field(default_factory=dict)
    state_db: str = "var/state.sqlite"
    log_dir: str = "var/logs"
    pokemon_hosts: list = field(
        default_factory=lambda: ["www.pokemoncenter.com",
                                 "www.pokemoncenter.com/de-de",
                                 "www.pokemoncenter.com/en-gb"])
    amazon: dict = field(default_factory=dict)   # Skyridge "Amazon" (noPhoneOnly, ...)
    license: str = ""                             # Skyridge "license-key"

    @classmethod
    def load(cls) -> "Settings":
        s = cls()
        raw = {}
        for base in (APP_ROOT, ROOT):
            j = base / "settings.json"
            if j.exists():
                try:
                    raw = json.loads(j.read_text(encoding="utf-8"))
                    break
                except Exception:
                    continue
        # Toppsfarm-Felder direkt uebernehmen (falls im selben File vorhanden)
        for k in cls.__dataclass_fields__:
            if k in raw and hasattr(s, k):
                setattr(s, k, raw[k])
        # Skyridge-Schema (settingsbeispiel.txt) in die Dataclass-Felder mappen;
        # danach, damit die Skyridge-Werte (captcha/geo/sms/mail/amazon) gewinnen
        s._map_skyridge(raw)
        # Migration: config/settings.yaml als Fallback fuer noch leere Felder
        p = ROOT / "config" / "settings.yaml"
        if p.exists():
            try:
                y = dict(yaml.safe_load(p.read_text(encoding="utf-8")) or {})
            except Exception:
                y = {}
            for k in cls.__dataclass_fields__:
                if k in y and k not in raw and hasattr(s, k):
                    setattr(s, k, y[k])
        return s

    def _map_skyridge(self, raw: dict):
        """Uebertraegt die Skyridge-Schluessel (Mastermails, CaptchaProvider,
        GeoCoder, SMSProvider, OAuthForwarder, Amazon, discord-webhook) in die
        Dataclass-Felder, damit bestehende cfg.-Zugriffe weiter funktionieren."""
        mail = self.mail
        if raw.get("Mastermails"):
            mms = [m for m in raw["Mastermails"] if isinstance(m, dict)]
            if mms:
                mail["provider"] = "catchall"
                mail["mastermails"] = mms
                mail.setdefault("imap_host", _imap_host_for(mms))
        if raw.get("OAuthForwarder"):
            of = raw["OAuthForwarder"] if isinstance(raw["OAuthForwarder"], dict) else {}
            mail["oauth_forwarder"] = of
            if of.get("target_email"):
                mail["provider"] = "catchall"
        if raw.get("CaptchaProvider") and isinstance(raw["CaptchaProvider"], dict):
            cp = raw["CaptchaProvider"]
            active = next((k for k, v in cp.items() if v), "NoneCap")
            self.captcha = {**self.captcha, "skyridge_provider": active,
                            "keys": dict(cp)}
        if raw.get("GeoCoder") and isinstance(raw["GeoCoder"], dict):
            g = raw["GeoCoder"]
            self.geo = {**self.geo, "mapbox": g.get("mapbox", ""),
                        "position_1": g.get("position_1", ""),
                        "position_2": g.get("position_2", "")}
        if raw.get("SMSProvider") and isinstance(raw["SMSProvider"], dict):
            self.sms = {**self.sms, "skyridge": raw["SMSProvider"]}
        if raw.get("Amazon") and isinstance(raw["Amazon"], dict):
            self.amazon = raw["Amazon"]
        if raw.get("discord-webhook"):
            self.notify = {**self.notify, "discord_webhook": raw["discord-webhook"]}
        if raw.get("license-key"):
            self.license = str(raw["license-key"])

    def path(self, rel: str) -> Path:
        p = ROOT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        return p


@dataclass
class Profile:
    id: str
    email: str
    first_name: str
    last_name: str
    address1: str
    zip: str
    city: str
    country: str = "DE"
    address2: str = ""
    phone: str = ""
    card: dict = field(default_factory=dict)
    proxy: str | None = None
    max_orders: int = 2
    enabled: bool = True

    def issues(self) -> list:
        out = []
        for f in ("email", "first_name", "last_name", "address1", "zip", "city"):
            if not getattr(self, f):
                out.append(f"fehlt:{f}")
        if len(self.card.get("number", "")) not in (15, 16):
            out.append("karte")
        if not re.fullmatch(r"\d{4,5}", str(self.zip)):
            out.append("plz")
        return out

    def form(self) -> dict:
        return {
            "checkout[email]": self.email,
            "checkout[shipping_address][first_name]": self.first_name,
            "checkout[shipping_address][last_name]": self.last_name,
            "checkout[shipping_address][address1]": self.address1,
            "checkout[shipping_address][address2]": self.address2,
            "checkout[shipping_address][zip]": self.zip,
            "checkout[shipping_address][city]": self.city,
            "checkout[shipping_address][country]": self.country,
            "checkout[shipping_address][phone]": self.phone,
        }

    def card_form(self) -> dict:
        c = self.card
        return {
            "checkout[credit_card][number]": str(c.get("number", "")),
            "checkout[credit_card][month]": str(c.get("exp_month", "")),
            "checkout[credit_card][year]": str(c.get("exp_year", "")),
            "checkout[credit_card][verification_value]": str(c.get("cvv", "")),
            "checkout[credit_card][name]": str(c.get("holder", "")),
        }


def _row_to_profile(row: dict) -> Profile:
    """Akzeptiert das toppsfarm-Format (address1) und das Identitaets-Format
    (street + house_no). Unbekannte oder leere Werte werden uebersprungen."""
    keep = {k: v for k, v in row.items() if k in Profile.__dataclass_fields__}
    if not keep.get("address1"):
        st = str(row.get("address1") or row.get("street") or row.get("address") or "").strip()
        hn = str(row.get("house_no") or "").strip()
        keep["address1"] = f"{st} {hn}".strip() if st else ""
    return Profile(**keep)


MODULE = "topps"


def load_profiles(module: str = MODULE, root: Path | None = None) -> list:
    if root is None:
        root = ROOT
    p = root / "accounts" / module / "profiles.yaml"
    if not p.exists():
        p = root / "config" / "profiles.yaml"  # Fallback
    if not p.exists():
        return []
    return [_row_to_profile(row)
            for row in (yaml.safe_load(p.read_text(encoding="utf-8")) or [])]


def load_targets() -> list:
    p = ROOT / "config" / "targets.yaml"
    if not p.exists():
        return []
    try:
        return (yaml.safe_load(p.read_text(encoding="utf-8")) or [])
    except yaml.YAMLError as exc:
        # YAML-Fehler -> Abbruch mit Zeilennummer, kein Lauf auf Defaults.
        mark = getattr(exc, "problem_mark", None)
        line = mark.line + 1 if mark else "?"
        CONSOLE.print(f"[red]targets.yaml Fehler (Zeile {line}): {exc}[/]")
        return []


def setup_log(cfg: Settings):
    d = cfg.path(cfg.log_dir)
    d.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[
        RichHandler(console=CONSOLE, show_path=False, rich_tracebacks=True),
        logging.FileHandler(d / f"run-{time.strftime('%Y%m%d-%H%M%S')}.log", encoding="utf-8")])


# --------------------------------------------------------------- setup wizard
def cmd_setup():
    CONSOLE.print("[bold]Setup[/] - Enter nimmt den Wert in Klammern.\n")
    (ROOT / "config").mkdir(parents=True, exist_ok=True)
    key_file = ROOT / "config" / "keys.env"
    old = load_env()
    provider = input(f"Captcha-Provider capsolver/2captcha/capmonster [{old.get('CAPTCHA_PROVIDER','capsolver')}]: ").strip() \
               or old.get("CAPTCHA_PROVIDER", "capsolver")
    keyname = {"capsolver": "CAPSOLVER_KEY", "2captcha": "TWOCAPTCHA_KEY",
               "capmonster": "CAPMONSTER_KEY"}.get(provider, "CAPSOLVER_KEY")
    key = input(f"{keyname}: ").strip() or old.get(keyname, "")
    hook = input("Discord-Webhook: ").strip() or old.get("DISCORD_WEBHOOK", "")
    errhook = input("Discord-Webhook fuer Fehler [leer = gleicher]: ").strip() or hook
    key_file.write_text(
        f"CAPTCHA_PROVIDER={provider}\n{keyname}={key}\n"
        f"DISCORD_WEBHOOK={hook}\nDISCORD_WEBHOOK_ERRORS={errhook}\n", encoding="utf-8")

    try:
        n = int(input("\nWie viele Profile anlegen? [1]: ") or "1")
    except ValueError:
        n = 1
    rows = []
    for i in range(1, n + 1):
        CONSOLE.print(f"\n[cyan]Profil {i}[/]")
        r = {
            "id": f"p{i:02d}", "enabled": True,
            "email": input("  E-Mail: ").strip(),
            "first_name": input("  Vorname: ").strip(),
            "last_name": input("  Nachname: ").strip(),
            "address1": input("  Strasse + Hausnr: ").strip(),
            "address2": "", "zip": input("  PLZ: ").strip(),
            "city": input("  Ort: ").strip(), "country": "DE",
            "phone": input("  Telefon (+49...): ").strip(),
            "card": {
                "number": input("  Kartennummer: ").strip().replace(" ", ""),
                "exp_month": int(input("  Ablauf Monat (MM): ").strip() or 0),
                "exp_year": int(input("  Ablauf Jahr (JJJJ): ").strip() or 0),
                "cvv": input("  CVV: ").strip(),
                "holder": input("  Karteninhaber: ").strip(),
            },
            "proxy": None, "max_orders": 2,
        }
        rows.append(r)
    (ROOT / "config").mkdir(parents=True, exist_ok=True)
    (ROOT / "accounts" / MODULE).mkdir(parents=True, exist_ok=True)
    (ROOT / "accounts" / MODULE / "profiles.yaml").write_text(
        yaml.safe_dump(rows, allow_unicode=True, sort_keys=False), encoding="utf-8")
    CONSOLE.print(f"\n[green]{len(rows)} Profile gespeichert.[/] Karten liegen im Klartext in "
                  f"accounts\\{MODULE}\\profiles.yaml.\n")


# --------------------------------------------------------------- notify
class Notifier:
    def __init__(self, url: str, err_url: str = ""):
        self.url, self.err, self.last = url, err_url or url, 0.0

    async def send(self, title: str, kind: str = "info", fields: dict | None = None,
                   error: bool = False):
        url = self.err if error else self.url
        if not url:
            return
        gap = 0.4 - (time.monotonic() - self.last)
        if gap > 0:
            await asyncio.sleep(gap)
        self.last = time.monotonic()
        payload = {"username": "toppsfarm", "embeds": [{
            "title": title[:240], "color": COLORS.get(kind, COLORS["info"]),
            "fields": [{"name": str(k)[:250], "value": str(v)[:1000], "inline": True}
                       for k, v in (fields or {}).items()]}]}
        try:
            async with AsyncSession(impersonate="chrome", timeout=15) as s:
                r = await s.post(url, json=payload)
                if r.status_code == 429:
                    await asyncio.sleep(float(r.json().get("retry_after", 2)))
        except Exception as exc:
            LOG.debug("webhook: %s", exc)


# --------------------------------------------------------------- proxy
def _parse_proxy_lines(text: str) -> list[str]:
    return parse_proxy_lines(text)


def proxy_files_for(module: str) -> list[Path]:
    """Liest die Proxy-Dateien je Quelle (Settings proxy.source:
    auto|shared|module). Modulordner zuerst, dann shared proxies/proxies.txt.
    Keine Modul-Hardcodes; Delegation an utilities/proxy."""
    from utilities.proxy import proxy_files_for as _pf
    return _pf(module)


class ProxyPool:
    def __init__(self, db: "State", module: str = "topps"):
        self.db = db
        self.module = module
        items: list[str] = []
        seen: set[str] = set()
        for f in proxy_files_for(module):
            if not f.exists():
                continue
            for x in parse_proxy_lines(f.read_text(encoding="utf-8-sig")):
                if x not in seen:
                    seen.add(x)
                    items.append(x)
        if not items:  # globaler Fallback (config/proxy.txt)
            p = ROOT / "config" / "proxy.txt"
            if p.exists():
                items = parse_proxy_lines(p.read_text(encoding="utf-8-sig"))
        self.items = items
        self.dead: set[str] = set()  # fuer den Lauf gesperrte Proxys
        self.rr = 0  # round-robin Zeiger

    def mark_dead(self, proxy: str):
        if proxy:
            self.dead.add(proxy)

    async def acquire(self, pinned: str | None = None) -> str | None:
        """1 Task = 1 Proxy: gibt `pinned` zurueck (kein Wechsel) oder waehlt
        round-robin aus den lebenden Proxys (Cooldown beachtet)."""
        if pinned or not self.items:
            return pinned
        cd = await self.db.cooldowns()
        now = time.time()
        alive = [p for p in self.items
                 if p not in self.dead and cd.get(p, 0) <= now]
        alive = alive or [p for p in self.items if p not in self.dead] or self.items
        p = alive[self.rr % len(alive)]
        self.rr = (self.rr + 1) % len(alive)
        return p

    async def precheck(self, cfg: Settings, host: str) -> dict:
        """Pruft jeden Proxy einmal gegen `host`. Tote Proxys werden fuer den
        Lauf gesperrt und in var/proxystats.csv dokumentiert (Punkt 4)."""
        from utilities.proxycheck import precheck_proxies
        return await precheck_proxies(self, cfg, host)


# --------------------------------------------------------------- state
SCHEMA = """
CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, host TEXT, handle TEXT,
  title TEXT, price REAL, seen REAL);
CREATE TABLE IF NOT EXISTS variants(variant_id INTEGER PRIMARY KEY, product_id INTEGER,
  host TEXT, price REAL, available INTEGER);
CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT, profile TEXT,
  host TEXT, variant INTEGER, qty INTEGER, mode TEXT, status TEXT, note TEXT,
  checkout_url TEXT, order_ref TEXT, created REAL, updated REAL);
CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT, profile TEXT,
  host TEXT, ref TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS proxystats(proxy TEXT PRIMARY KEY, ok INTEGER, fail INTEGER,
  cooldown REAL);
"""


class State:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.c = sqlite3.connect(path, check_same_thread=False)
        self.c.row_factory = sqlite3.Row
        self.c.execute("PRAGMA journal_mode=WAL")
        self.c.executescript(SCHEMA)
        self.lock = asyncio.Lock()

    async def q(self, fn, *a):
        async with self.lock:
            return await asyncio.to_thread(fn, *a)

    async def see_product(self, pid, host, handle, title, price) -> bool:
        def f():
            if self.c.execute("SELECT 1 FROM products WHERE id=?", (pid,)).fetchone():
                return False
            self.c.execute("INSERT INTO products VALUES(?,?,?,?,?,?)",
                           (pid, host, handle, title, price, time.time()))
            self.c.commit()
            return True
        return await self.q(f)

    async def see_variant(self, vid, pid, host, price, avail) -> bool:
        def f():
            known = self.c.execute("SELECT 1 FROM variants WHERE variant_id=?", (vid,)).fetchone()
            self.c.execute("INSERT INTO variants VALUES(?,?,?,?,?) ON CONFLICT(variant_id) "
                           "DO UPDATE SET price=excluded.price, available=excluded.available",
                           (vid, pid, host, price, avail))
            self.c.commit()
            return known is None
        return await self.q(f)

    async def add_task(self, prof, host, vid, qty, mode) -> int:
        def f():
            cur = self.c.execute("INSERT INTO tasks(profile,host,variant,qty,mode,status,"
                                 "created,updated) VALUES(?,?,?,?,?,'queued',?,?)",
                                 (prof, host, vid, qty, mode, time.time(), time.time()))
            self.c.commit()
            return cur.lastrowid
        return await self.q(f)

    async def set_task(self, tid, status, note=None, url=None, ref=None):
        def f():
            self.c.execute("UPDATE tasks SET status=?, note=COALESCE(?,note), "
                           "checkout_url=COALESCE(?,checkout_url), "
                           "order_ref=COALESCE(?,order_ref), updated=? WHERE id=?",
                           (status, note, url, ref, time.time(), tid))
            self.c.commit()
        await self.q(f)

    async def orders(self, prof) -> int:
        return await self.q(lambda: self.c.execute(
            "SELECT COUNT(*) c FROM orders WHERE profile=?", (prof,)).fetchone()["c"])

    async def add_order(self, prof, host, ref):
        def f():
            self.c.execute("INSERT INTO orders(profile,host,ref,ts) VALUES(?,?,?,?)",
                           (prof, host, ref, time.time()))
            self.c.commit()
        await self.q(f)

    async def stats(self):
        return await self.q(lambda: {r["status"]: r["c"] for r in self.c.execute(
            "SELECT status, COUNT(*) c FROM tasks GROUP BY status")})

    async def cooldowns(self) -> dict:
        return await self.q(lambda: {r["proxy"]: r["cooldown"] for r in
                                     self.c.execute("SELECT proxy, cooldown FROM proxystats")})

    async def report_proxy(self, proxy, ok):
        if not proxy:
            return
        def f():
            self.c.execute("INSERT INTO proxystats VALUES(?,?,?,?) ON CONFLICT(proxy) "
                           "DO UPDATE SET ok=ok+excluded.ok, fail=fail+excluded.fail, "
                           "cooldown=MAX(cooldown, excluded.cooldown)",
                           (proxy, int(ok), int(not ok), 0 if ok else time.time() + 90))
            self.c.commit()
        await self.q(f)


# --------------------------------------------------------------- cloudflare
CF_COOKIE_FILE = ROOT / "var" / "cf_cookies.json"
_CF_CACHE: dict | None = None


def cf_cookies_file() -> Path:
    CF_COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
    return CF_COOKIE_FILE


def cf_cookies() -> dict | None:
    """Gesperrte Cloudflare-Cookies (cf_clearance, __cf_bm) aus der letzten
    Browser-Sitzung. liefert {} wenn keine vorhanden sind, sonst {name: wert}."""
    global _CF_CACHE
    if _CF_CACHE is not None:
        return _CF_CACHE
    p = cf_cookies_file()
    _CF_CACHE = {}
    if p.exists():
        try:
            import json as _json
            _CF_CACHE = _json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            _CF_CACHE = {}
    return _CF_CACHE


async def cf_refresh(host: str, headless: bool = False, proxy: str | None = None) -> dict:
    """Oeffnet den Browser (einmalig, nicht headless damit Cloudflare den
    Turnstile loslaesst), wartet auf cf_clearance, speichert die Cookies fuer
    curl_cffi und liefert sie zurueck. -> {name: wert} oder {}.
    `proxy`: WICHTIG - cf_clearance ist IP-gebunden. Damit die Cookies zu den
    curl_cffi-Requests (gleicher Proxy-IP) passen, muss der Browser DURCH
    denselben Proxy laufen. Ohne proxy werden die Cookies nutzlos (403)."""
    from playwright.async_api import async_playwright
    from utilities.proxy import proxy_playwright
    dir = (ROOT / "var" / "browser-cf").resolve()
    pw = await async_playwright().start()
    lp = dict(headless=headless, user_agent=UA, locale="de-DE",
              viewport={"width": 1366, "height": 768},
              args=["--disable-blink-features=AutomationControlled", "--no-sandbox",
                    "--disable-gpu", "--disable-dev-shm-usage"])
    px = proxy_playwright(proxy)
    if px:
        lp["proxy"] = px
    ctx = await pw.chromium.launch_persistent_context(str(dir), **lp)
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    await page.add_init_script(
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        "window.chrome={runtime:{}};")
    out = {}
    try:
        await page.goto(f"https://{host}/", wait_until="domcontentloaded", timeout=60000)
        end = time.time() + 120
        while time.time() < end:
            ck = await ctx.cookies()
            if any(c["name"] == "cf_clearance" for c in ck):
                out = {c["name"]: c["value"] for c in ck
                       if c["name"] in ("cf_clearance", "__cf_bm")}
                break
            await page.wait_for_timeout(2000)
    except Exception as exc:
        LOG.warning("cf_refresh: %s", exc)
    finally:
        await ctx.close()
        await pw.stop()
    if out:
        import json as _json
        cf_cookies_file().write_text(_json.dumps(out), encoding="utf-8")
        global _CF_CACHE
        _CF_CACHE = out
    return out


def _with_cf(kw: dict) -> dict:
    """Haengt gespeicherte Cloudflare-Cookies an die Request-Optionen."""
    ck = cf_cookies()
    if ck:
        kw["cookies"] = {**kw.get("cookies", {}), **ck}
    return kw


# --------------------------------------------------------------- http
def headers(cfg: Settings, host: str, json_mode: bool = False) -> dict:
    # Minimum: nur accept und accept-language. user-agent, sec-ch-ua, sec-fetch-*
    # usw. setzt das impersonate von curl_cffi selbst (passend zum Fingerprint).
    return {
        "accept": "application/json" if json_mode else
                  "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "accept-language": f"{cfg.locale},{cfg.locale.split('-')[0]};q=0.9,en;q=0.8",
    }


def session(cfg: Settings, proxy: str | None = None) -> AsyncSession:
    kw = {"impersonate": cfg.impersonate, "timeout": cfg.timeout_s}
    if proxy:
        kw["proxy"] = proxy
    return AsyncSession(**_with_cf(kw))


async def warm(s: AsyncSession, cfg: Settings, host: str) -> bool:
    try:
        r = await s.get(f"https://{host}/", headers=headers(cfg, host))
        if r.status_code >= 400:
            return False
        await s.get(f"https://{host}/products.json?limit=1", headers=headers(cfg, host, True))
        return True
    except Exception:
        return False


# --------------------------------------------------------------- katalog
# de.topps.com & Co. sind Next.js-Frontends mit Shopify-Backend: /products.json
# ist dort per Cloudflare gesperrt (403). Produktdaten kommen stattdessen aus der
# Storefront-API (Token steht oeffentlich im HTML der Startseite), ersatzweise
# aus der Produkt-Sitemap (/products/sitemap.xml) plus Produktseite.
SF_VERSION = "2024-10"
SF_QUERY = ("query($n:Int!,$c:String){products(first:$n,after:$c,sortKey:CREATED_AT,reverse:true)"
            "{pageInfo{hasNextPage endCursor} edges{node{id handle title "
            "variants(first:20){edges{node{id availableForSale price{amount}}}}}}}}")
_SF: dict = {}        # host -> (storeDomain, storefrontAccessToken)
_SM_SEEN: dict = {}   # host -> bekannte Handles der letzten Teil-Sitemap
_SM_FAIL: dict = {}   # (host, handle) -> Fehlversuche beim Aufloesen der Produktseite
_SM_PAUSE: dict = {}  # host -> Zeitpunkt, bis zu dem die Sitemap nach 429 ruht
SM_PAUSE_S = 60       # Pause nach 429 auf der Sitemap
SM_MAX_NEW = 20      # hoechstens so viele neue Handles je Durchlauf aufloesen
SM_MAX_FAIL = 5       # danach gilt ein Handle als gesehen


def base_headers(cfg: Settings, json_mode: bool = False) -> dict:
    return {"accept": "application/json" if json_mode else
                      "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": f"{cfg.locale},{cfg.locale.split('-')[0]};q=0.9,en;q=0.8"}


def _gid(g: str) -> int:
    return int(str(g).rsplit("/", 1)[-1])


async def storefront_cfg(s: AsyncSession, cfg: Settings, host: str):
    if host in _SF:
        return _SF[host]
    r = await s.get(f"https://{host}/", headers=base_headers(cfg))
    if r.status_code != 200:
        return None
    t = r.text.replace('\\"', '"')
    d = re.search(r'"storeDomain":"([a-z0-9-]+\.myshopify\.com)"', t)
    k = re.search(r'"storefrontAccessToken":"([0-9a-f]{32})"', t)
    if not (d and k):
        return None
    _SF[host] = (d.group(1), k.group(1))
    return _SF[host]


async def storefront_products(s: AsyncSession, cfg: Settings, host: str,
                              first: int = 250, cursor: str | None = None):
    """-> (status, products im products.json-Format, naechster Cursor). status 0 = kein Token."""
    sf = await storefront_cfg(s, cfg, host)
    if not sf:
        return 0, [], None
    dom, tok = sf
    r = await s.post(f"https://{dom}/api/{SF_VERSION}/graphql.json",
                     json={"query": SF_QUERY, "variables": {"n": first, "c": cursor}},
                     headers={**base_headers(cfg, True), "content-type": "application/json",
                              "x-shopify-storefront-access-token": tok})
    if r.status_code != 200:
        if r.status_code in (401, 403):
            _SF.pop(host, None)
        return r.status_code, [], None
    data = (r.json().get("data") or {}).get("products")
    if data is None:
        return 200, [], None
    items = []
    for e in data.get("edges", []):
        n = e["node"]
        items.append({
            "id": _gid(n["id"]), "handle": n.get("handle", ""), "title": n.get("title", ""),
            "variants": [{"id": _gid(v["node"]["id"]),
                          "price": (v["node"].get("price") or {}).get("amount", 0),
                          "available": bool(v["node"].get("availableForSale"))}
                         for v in n.get("variants", {}).get("edges", [])]})
    pi = data.get("pageInfo") or {}
    return 200, items, (pi.get("endCursor") if pi.get("hasNextPage") else None)


async def sitemap_handles(s: AsyncSession, cfg: Settings, host: str):
    """-> (status, Handles der letzten Teil-Sitemap; neue Produkte stehen dort am Ende)."""
    r = await s.get(f"https://{host}/products/sitemap.xml", headers=base_headers(cfg))
    if r.status_code != 200:
        return r.status_code, []
    subs = re.findall(r"<loc>([^<]+/products/sitemap/(\d+)\.xml)</loc>", r.text)
    if not subs:
        return 200, []
    last = max(subs, key=lambda x: int(x[1]))[0]
    r = await s.get(last, headers=base_headers(cfg))
    if r.status_code != 200:
        return r.status_code, []
    return 200, re.findall(r"<loc>https?://[^<]+/products/([^<?/]+)</loc>", r.text)


async def pdp_product(s: AsyncSession, cfg: Settings, host: str, handle: str):
    """Produkt + Variant-IDs aus dem HTML der Produktseite (products.json-Format) oder None."""
    r = await s.get(f"https://{host}/products/{handle}", headers=base_headers(cfg))
    if r.status_code != 200:
        return None
    t = r.text.replace('\\"', '"')
    raw = unquote(handle)
    i = t.find(f'"handle":"{raw}","variants":[')
    if i < 0:
        return None
    blk = t[i:i + 40000]
    end = blk.find('"aggregatedVariants"')
    if end > 0:
        blk = blk[:end]
    vs = [{"id": int(m.group(2)), "price": m.group(1), "available": m.group(3) == "true"}
          for m in re.finditer(r'"price":\{"amount":"([\d.]+)".*?"id":"gid://shopify/ProductVariant/'
                               r'(\d+)".*?"availableForSale":(true|false)', blk, re.S)]
    if not vs:
        return None
    m = re.search(r"<title>(.*?)</title>", t, re.S)
    return {"id": zlib.crc32(f"{host}/{raw}".encode()), "handle": raw,
            "title": m.group(1).strip() if m else raw, "variants": vs}


async def sitemap_new(s: AsyncSession, cfg: Settings, host: str):
    """Sitemap-Weg: -> (status, neue Produkte im products.json-Format).
    Der erste Durchlauf je Host merkt sich nur die vorhandenen Handles."""
    if time.time() < _SM_PAUSE.get(host, 0):
        return 429, []
    st, handles = await sitemap_handles(s, cfg, host)
    if st == 429:   # Rate-Limit des Shops: Sitemap fuer diesen Host ruhen lassen
        _SM_PAUSE[host] = time.time() + SM_PAUSE_S
        LOG.warning("%s: Sitemap 429, Pause %ss", host, SM_PAUSE_S)
    if st != 200 or not handles:
        return st, []
    seen = _SM_SEEN.get(host)
    if seen is None:
        _SM_SEEN[host] = set(handles)
        return 200, []
    out = []
    for h in [h for h in handles if h not in seen][-SM_MAX_NEW:]:
        p = await pdp_product(s, cfg, host, h)
        if p:
            seen.add(h)
            out.append(p)
            continue
        n = _SM_FAIL[(host, h)] = _SM_FAIL.get((host, h), 0) + 1
        if n >= SM_MAX_FAIL:
            seen.add(h)
            LOG.warning("%s: Handle %s nicht aufloesbar, uebersprungen", host, h)
    return 200, out


async def products_json(s: AsyncSession, cfg: Settings, host: str, limit: int = 250):
    """Optionaler Zweitweg (klassisches Shopify-Theme): -> (status, products)."""
    r = await s.get(f"https://{host}/products.json?limit={limit}",
                    headers=headers(cfg, host, True))
    if r.status_code != 200:
        return r.status_code, []
    try:
        return 200, r.json().get("products", [])
    except Exception:
        return 200, []


# --------------------------------------------------------------- captcha
class Solver:
    def __init__(self, cfg: Settings):
        self.cfg = cfg
        self.provider = ENV.get("CAPTCHA_PROVIDER", "capsolver").lower()
        self.key = {"capsolver": ENV.get("CAPSOLVER_KEY", ""),
                    "2captcha": ENV.get("TWOCAPTCHA_KEY", ""),
                    "capmonster": ENV.get("CAPMONSTER_KEY", "")}.get(self.provider, "")

    @property
    def ok(self) -> bool:
        return bool(self.cfg.captcha.get("enabled") and self.key)

    async def solve(self, kind, sitekey, url, proxy) -> str | None:
        if not self.ok:
            return None
        for _ in range(max(1, int(self.cfg.captcha.get("retry", 2)))):
            try:
                tok = await self._poll(await self._create(kind, sitekey, url, proxy))
                if tok:
                    return tok
            except Exception as exc:
                LOG.warning("captcha: %s", exc)
                await asyncio.sleep(1.5)
        return None

    def _px(self, proxy):
        if not proxy:
            return {}
        scheme, rest = proxy.split("://", 1)
        creds, hp = (rest.split("@", 1) if "@" in rest else (None, rest))
        host, port = hp.rsplit(":", 1)
        d = {"proxyType": scheme, "proxyAddress": host, "proxyPort": int(port)}
        if creds:
            u, pw = creds.split(":", 1)
            d.update(proxyLogin=u, proxyPassword=pw)
        return d

    async def _create(self, kind, key, url, proxy) -> str:
        c, t2, cm = {"hcaptcha": ("HCaptchaTask", "hcaptcha", "HCaptchaTask"),
                     "recaptcha": ("ReCaptchaV2Task", "recaptcha_v2", "RecaptchaV2Task")}[kind]
        async with AsyncSession(timeout=30) as s:
            if self.provider in ("capsolver", "capmonster"):
                base = ("https://api.capsolver.com" if self.provider == "capsolver"
                        else "https://api.capmonster.cloud")
                ttype = c if self.provider == "capsolver" else cm
                r = await s.post(f"{base}/createTask", json={
                    "clientKey": self.key,
                    "task": {"type": ttype, "websiteURL": url, "websiteKey": key,
                             **self._px(proxy)}})
                d = r.json()
                if d.get("errorId"):
                    raise RuntimeError(d.get("errorDescription"))
                return str(d["taskId"])
            r = await s.post("https://2captcha.com/in.php", data={
                "key": self.key, "json": 1, "method": t2, "pageurl": url, "sitekey": key})
            d = r.json()
            if d.get("status") != 1:
                raise RuntimeError(str(d.get("request")))
            return str(d["request"])

    async def _poll(self, tid) -> str | None:
        end = time.monotonic() + float(self.cfg.captcha.get("max_wait_s", 120))
        async with AsyncSession(timeout=30) as s:
            while time.monotonic() < end:
                await asyncio.sleep(3)
                if self.provider == "2captcha":
                    r = await s.get("https://2captcha.com/res.php", params={
                        "key": self.key, "action": "get", "id": tid, "json": 1})
                    d = r.json()
                    if d.get("status") == 1:
                        return d["request"]
                    continue
                base = ("https://api.capsolver.com" if self.provider == "capsolver"
                        else "https://api.capmonster.cloud")
                r = await s.post(f"{base}/getTaskResult",
                                 json={"clientKey": self.key, "taskId": tid})
                d = r.json()
                if d.get("status") == "ready":
                    sol = d.get("solution", {})
                    return sol.get("gRecaptchaResponse") or sol.get("token")
                if d.get("errorId"):
                    raise RuntimeError(str(d.get("errorDescription")))
        return None


# --------------------------------------------------------------- queue
def queued(url: str, html: str) -> bool:
    low = (url + " " + html[:3000]).lower()
    return any(m in low for m in ("queue-it", "queueit", "waitingroom", "waiting-room"))


# --------------------------------------------------------------- checkout http
class HttpCheckout:
    def __init__(self, cfg, state, pool, solver, notifier):
        self.cfg, self.state, self.pool = cfg, state, pool
        self.solver, self.notifier = solver, notifier

    async def run(self, task: dict, prof: Profile) -> dict:
        host = task["host"]
        proxy = task.get("proxy") or await self.pool.acquire(prof.proxy)
        s = session(self.cfg, proxy)
        res = {"ok": False, "note": "", "url": None, "order": None}
        try:
            if not await warm(s, self.cfg, host):
                res["note"] = "warmup"
                await self.pool.report_proxy(proxy, False)
                return res
            maxp = float(task.get("max_price") or 0)
            if maxp and not await self._price_ok(s, host, task, maxp):
                res["note"] = "price over max_price"
                return res
            r = await s.post(f"https://{host}/cart/add.js",
                             json={"id": task["variant"], "quantity": task.get("qty", 1)},
                             headers=headers(self.cfg, host, True))
            if r.status_code != 200:
                # Next.js-Frontend ohne klassischen cart/add.js (z. B. de.topps.com):
                # Checkout-Link direkt ueber die Storefront-cartCreate-API.
                link = await self._storefront_cart_link(s, host, task)
                if link:
                    res.update(ok=True, url=link, note="storefront checkout-link")
                    return res
                res["note"] = f"cart {r.status_code}"
                return res
            r = await s.get(f"https://{host}/checkout", headers=headers(self.cfg, host))
            body = r.text
            if queued(str(r.url), body):
                body = await self._wait_queue(s, host)
            token = self._token(body, str(r.url))
            if not token:
                res["note"] = "kein checkout-token"
                return res
            csrf = self._csrf(body)
            url = f"https://{host}/checkouts/{token}"
            h = headers(self.cfg, host, True)
            h.update({"content-type": "application/x-www-form-urlencoded",
                      "x-csrf-token": csrf, "origin": f"https://{host}", "referer": url})
            data = prof.form()
            data.update({"_method": "patch", "authenticity_token": csrf})
            r = await s.post(url, data=data, headers=h)
            if r.status_code >= 400:
                res["note"] = f"fill {r.status_code}"
                return res
            if "hcaptcha" in r.text.lower() or "recaptcha" in r.text.lower():
                sk = self._sitekey(r.text)
                if sk:
                    tok = await self.solver.solve(sk[0], sk[1], url, proxy)
                    if tok:
                        d2 = prof.form()
                        d2.update({"_method": "patch", "authenticity_token": csrf,
                                   "checkout[hcaptcha_response]": tok})
                        await s.post(url, data=d2, headers=h)
            if task.get("mode") == "full" or task.get("card_http"):
                cf = prof.card_form()
                cf.update({"_method": "patch", "authenticity_token": csrf,
                           "checkout[payment_gateway]": "shopify"})
                r2 = await s.post(url, data=cf, headers=h)
                if any(x in r2.text for x in ("/thank_you", "/orders/")):
                    m = re.search(r"/orders/([A-Za-z0-9\-]+)", r2.text)
                    res.update(ok=True, order=m.group(1) if m else "?", url=url)
                    return res
            res.update(ok=True, url=url, note="checkout vorbereitet")
            return res
        except Exception as exc:
            res["note"] = type(exc).__name__
            await self.pool.report_proxy(proxy, False)
            return res
        finally:
            await s.close()

    async def run_prebuilt(self, s, host, cart_url, prof: Profile,
                           dry: bool = True, card: bool = False) -> dict:
        """Vollautomatischer Checkout aus einem vorgebauten Cart-Link (Speed-Pfad).
        Queue -> Formular aus Profil -> Karte -> Pay. Keine Bestaetigung, kein Klick.
        Gleiche Session + gleicher Proxy wie Prewarm/Poll. -> dict mit order/url.
        dry: stoppt vor der Zahlung und liefert den Checkout-Link."""
        res = {"ok": False, "note": "", "url": cart_url, "order": None}
        try:
            r = await s.get(cart_url, headers=headers(self.cfg, host))
            body = r.text
            if queued(str(r.url), body):
                body = await self._wait_queue(s, host)
            url = str(r.url)
            token = self._token(body, url)
            if not token:
                res["note"] = "kein checkout-token"
                return res
            csrf = self._csrf(body)
            h = headers(self.cfg, host, True)
            h.update({"content-type": "application/x-www-form-urlencoded",
                      "x-csrf-token": csrf, "origin": f"https://{host}", "referer": url})
            data = prof.form()
            data.update({"_method": "patch", "authenticity_token": csrf})
            r = await s.post(url, data=data, headers=h)
            if r.status_code >= 400:
                res["note"] = f"fill {r.status_code}"
                return res
            if "hcaptcha" in r.text.lower() or "recaptcha" in r.text.lower():
                sk = self._sitekey(r.text)
                if sk:
                    tok = await self.solver.solve(sk[0], sk[1], url, None)
                    if tok:
                        d2 = prof.form()
                        d2.update({"_method": "patch", "authenticity_token": csrf,
                                   "checkout[hcaptcha_response]": tok})
                        await s.post(url, data=d2, headers=h)
            if dry:
                res.update(ok=True, url=url, note="dry checkout-link")
                return res
            if not card:
                res.update(ok=True, url=url, note="checkout vorbereitet")
                return res
            cf = prof.card_form()
            cf.update({"_method": "patch", "authenticity_token": csrf,
                       "checkout[payment_gateway]": "shopify"})
            r2 = await s.post(url, data=cf, headers=h)
            if any(x in r2.text for x in ("/thank_you", "/orders/")):
                m = re.search(r"/orders/([A-Za-z0-9\-]+)", r2.text)
                res.update(ok=True, order=m.group(1) if m else "?", url=url)
                return res
            res["note"] = "kein order-ref"
            return res
        except Exception as exc:
            res["note"] = type(exc).__name__
            return res

    async def _price_ok(self, s, host, task, maxp) -> bool:
        """Prueft den aktuellen Preis der Variante ueber /products.json
        bzw. die Storefront-API. True, wenn er unter maxp liegt."""
        try:
            st, items, _ = await storefront_products(s, self.cfg, host, 200)
            if st == 200:
                for p in items or []:
                    for v in p.get("variants", []) or []:
                        if int(v.get("id", 0)) == int(task["variant"]):
                            price = float(v.get("price") or 0)
                            return price > 0 and price <= maxp
            st, items = await products_json(s, self.cfg, host, 250)
            if st == 200:
                for p in items or []:
                    for v in p.get("variants", []) or []:
                        if int(v.get("id", 0)) == int(task["variant"]):
                            price = float(v.get("price") or 0)
                            return price > 0 and price <= maxp
        except Exception:
            pass
        return True  # Preis unbekannt -> nicht blockieren

    async def _storefront_cart_link(self, s, host, task) -> str | None:
        """Checkout-Link ueber die Storefront-cartCreate-API fuer Next.js-Shops,
        die kein /cart/add.js anbieten. -> checkoutUrl oder None."""
        try:
            sf = await storefront_cfg(s, self.cfg, host)
            if not sf:
                return None
            dom, tok = sf
            vid = task["variant"]
            q = ("mutation cartCreate($input:CartInput!){cartCreate(input:$input){"
                 "cart{id checkoutUrl} userErrors{field message}}}")
            r = await s.post(f"https://{dom}/api/{SF_VERSION}/graphql.json",
                             json={"query": q, "variables": {
                                 "input": {"lines": [
                                     {"merchandiseId": f"gid://shopify/ProductVariant/{vid}",
                                      "quantity": int(task.get("qty", 1))}]}}},
                             headers={**base_headers(self.cfg, True),
                                      "content-type": "application/json",
                                      "x-shopify-storefront-access-token": tok})
            if r.status_code != 200:
                return None
            cart = (r.json().get("data") or {}).get("cartCreate") or {}
            if cart.get("userErrors"):
                LOG.debug("cartCreate errs: %s", cart["userErrors"])
                return None
            url = (cart.get("cart") or {}).get("checkoutUrl")
            return url or None
        except Exception as exc:
            LOG.debug("storefront cart link: %s", exc)
            return None

    async def _wait_queue(self, s, host) -> str:
        end = time.monotonic() + float(self.cfg.queue.get("max_wait_s", 1800))
        while time.monotonic() < end:
            await asyncio.sleep(float(self.cfg.queue.get("poll_s", 1.2)) * random.uniform(.85, 1.25))
            r = await s.get(f"https://{host}/checkout", headers=headers(self.cfg, host))
            if not queued(str(r.url), r.text):
                return r.text
        return ""

    @staticmethod
    def _token(body, url):
        m = re.search(r"/checkouts/([0-9a-z]{20,})", url)
        if m:
            return m.group(1)
        for pat in (r'Shopify\.Checkout\.token\s*=\s*"([0-9a-z]{20,})"',
                    r'"token"\s*:\s*"([0-9a-z]{20,})"'):
            m = re.search(pat, body)
            if m:
                return m.group(1)
        return None

    @staticmethod
    def _csrf(body):
        m = re.search(r'name="authenticity_token"\s+value="([^"]+)"', body)
        return m.group(1) if m else ""

    @staticmethod
    def _sitekey(body):
        m = re.search(r'data-sitekey="([^"]+)"', body)
        if not m:
            return None
        return ("hcaptcha" if "hcaptcha" in body.lower() else "recaptcha", m.group(1))


# --------------------------------------------------------------- checkout browser
class BrowserCheckout:
    def __init__(self, cfg, pool, solver, notifier):
        self.cfg, self.pool, self.solver, self.notifier = cfg, pool, solver, notifier
        self.pw = self.browser = None

    async def start(self):
        from playwright.async_api import async_playwright
        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch(headless=True, args=[
            "--disable-blink-features=AutomationControlled", "--no-sandbox",
            "--disable-gpu", "--disable-dev-shm-usage"])

    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.pw:
            await self.pw.stop()

    async def run(self, task: dict, prof: Profile) -> dict:
        proxy = task.get("proxy") or await self.pool.acquire(prof.proxy)
        px = None
        if proxy:
            scheme, rest = proxy.split("://", 1)
            creds, hp = (rest.split("@", 1) if "@" in rest else (None, rest))
            h, p = hp.rsplit(":", 1)
            px = {"server": f"{scheme}://{h}:{p}"}
            if creds:
                u, pw_ = creds.split(":", 1)
                px.update(username=u, password=pw_)
        ctx = await self.browser.new_context(user_agent=UA, locale="de-DE",
                                             timezone_id="Europe/Berlin", proxy=px)
        await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
                                  "window.chrome={runtime:{}};")
        page = await ctx.new_page()
        res = {"ok": False, "note": "", "url": page.url, "order": None}
        try:
            await page.goto(f"https://{task['host']}/cart/{task['variant']}:{task.get('qty',1)}"
                            f"?storefront=true", wait_until="domcontentloaded", timeout=45000)
            end = time.monotonic() + float(self.cfg.queue.get("max_wait_s", 1800))
            while queued(page.url, await page.content()):
                if time.monotonic() > end:
                    res["note"] = "queue"
                    return res
                await asyncio.sleep(float(self.cfg.queue.get("poll_s", 1.2)))
                await page.reload(wait_until="domcontentloaded", timeout=20000)
            for sel, key in (('input[name="email"]', "email"),
                             ('input[name="firstName"]', "first_name"),
                             ('input[name="lastName"]', "last_name"),
                             ('input[name="address1"]', "address1"),
                             ('input[name="postalCode"]', "zip"),
                             ('input[name="city"]', "city"),
                             ('input[name="phone"]', "phone")):
                try:
                    loc = page.locator(sel).first
                    if await loc.count():
                        await loc.fill(str(getattr(prof, key)), timeout=5000)
                except Exception:
                    pass
            try:
                await page.locator('select[name="countryCode"],select[name="country"]') \
                    .first.select_option(self.cfg.ship_country)
            except Exception:
                pass
            btn = page.locator('button[type="submit"],button:has-text("Weiter")').first
            if await btn.count():
                await btn.click(timeout=8000)
                await page.wait_for_timeout(2500)
            pay = page.locator('#checkout-pay-button,button:has-text("Jetzt kaufen")').first
            await pay.wait_for(state="visible", timeout=25000)
            for frame in page.frames:
                if "card-fields" in (frame.name or ""):
                    for name, val in (("number", prof.card.get("number")),
                                      ("expiry", f"{int(prof.card.get('exp_month',0)):02d} / "
                                                 f"{str(prof.card.get('exp_year'))[-2:]}"),
                                      ("cvv", prof.card.get("cvv")),
                                      ("name", prof.card.get("holder"))):
                        if not val:
                            continue
                        try:
                            l = frame.locator(f'input[name="{name}"]').first
                            if await l.count():
                                await l.fill(str(val), timeout=4000)
                        except Exception:
                            pass
            await pay.click(timeout=15000)
            end = time.monotonic() + 180
            while time.monotonic() < end:
                if any(x in page.url for x in ("/thank_you", "/orders/")):
                    m = re.search(r"/orders/([A-Za-z0-9\-]+)", page.url)
                    res.update(ok=True, order=m.group(1) if m else "?", url=page.url)
                    return res
                await page.wait_for_timeout(1500)
            res["note"] = "kein thank_you"
            return res
        except Exception as exc:
            res["note"] = type(exc).__name__
            await self.pool.report_proxy(proxy, False)
            return res
        finally:
            await ctx.close()


# --------------------------------------------------------------- monitor
class Monitor:
    def __init__(self, cfg, state, pool, notifier, hosts, on_new):
        self.cfg, self.state, self.pool = cfg, state, pool
        self.notifier, self.hosts, self.on_new = notifier, hosts, on_new
        self.stop = asyncio.Event()

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
        proxy = await self.pool.acquire()
        s = session(self.cfg, proxy)
        changed = False
        try:
            for src in self.cfg.monitor_sources:
                if src == "sitemap":
                    # Produkt-Sitemap diffen, Variant-IDs von der Produktseite
                    status, items = await sitemap_new(s, self.cfg, host)
                    if items:
                        changed |= await self._feed(host, items)
                elif src == "storefront":
                    # Storefront-API (zwei Seiten a 250, neueste zuerst)
                    status, cursor = 0, None
                    for _ in (1, 2):
                        status, items, cursor = await storefront_products(
                            s, self.cfg, host, 250, cursor)
                        if status != 200 or not items:
                            break
                        changed |= await self._feed(host, items)
                        if not cursor:
                            break
                elif src == "products_json":
                    status, items = await products_json(s, self.cfg, host)
                    if items:
                        changed |= await self._feed(host, items)
                else:
                    continue
                if status == 200:
                    break
        except Exception as exc:
            LOG.debug("%s: %s", host, exc)
        finally:
            await s.close()
        return changed

    async def _feed(self, host, items) -> bool:
        changed = False
        for p in items:
            is_new = await self.state.see_product(
                p["id"], host, p.get("handle", ""), p.get("title", ""),
                float(p["variants"][0]["price"]) if p.get("variants") else 0)
            for v in p.get("variants", []):
                fresh = await self.state.see_variant(
                    v["id"], p["id"], host, float(v.get("price", 0)),
                    int(bool(v.get("available"))))
                if is_new or fresh:
                    changed = True
                    await self._alert(host, p, v)
                    await self.on_new(host, p, v)
        return changed

    async def _alert(self, host, p, v):
        if not self.cfg.notify.get("on_new", True):
            return
        await self.notifier.send(f"NEU {p.get('title','?')[:100]}", "new",
                                 {"Host": host, "Preis": v.get("price"), "Variant": v.get("id"),
                                  "Link": f"https://{host}/products/{p.get('handle','')}"})
        LOG.info("NEU %s %s (%s)", host, p.get("title"), v.get("id"))


# --------------------------------------------------------------- orchestrator
async def geo_check(cfg: Settings, prof: Profile, proxy: str | None) -> tuple[bool, str]:
    """A4: IP-Geo der Proxy-Ausgangs-IP mit dem Profil-Land vergleichen.
    -> (ok, hinweis). Immer True, wenn geo nicht aktiviert oder kein Land."""
    from utilities.geo import ip_geo, region_matches
    if not cfg.geo.get("enabled", False):
        return True, "geo aus"
    geo = await ip_geo(proxy)
    if not geo:
        return (not cfg.geo.get("strict", True)), "geo unbestimmbar"
    return region_matches(geo, prof.country)


class Orchestrator:
    def __init__(self, cfg, state, pool, notifier, profiles, http_engine, browser_engine=None):
        self.cfg, self.state, self.pool = cfg, state, pool
        self.notifier, self.http, self.browser = notifier, http_engine, browser_engine
        self.profiles = [p for p in profiles if p.enabled]
        self.sem = asyncio.Semaphore(cfg.concurrency_http)
        self.bsem = asyncio.Semaphore(cfg.concurrency_browser)
        self.rr, self.tasks = 0, []
        from utilities.quality import Quality
        self.q = Quality(MODULE)

    async def pick(self):
        if not self.profiles:
            return None
        for i in range(len(self.profiles)):
            p = self.profiles[(self.rr + i) % len(self.profiles)]
            if await self.state.orders(p.id) < p.max_orders:
                self.rr = (self.rr + i + 1) % len(self.profiles)
                return p
        return None

    async def spawn(self, host, vid, qty, mode, count, card_http=False, max_price=0,
                    title="", price=0.0):
        for _ in range(count):
            p = await self.pick()
            if not p:
                LOG.warning("keine freien Profile")
                return
            tid = await self.state.add_task(p.id, host, vid, qty, mode)
            proxy = await self.pool.acquire(p.proxy)
            self.tasks.append(asyncio.create_task(self._run(tid, {
                "host": host, "variant": vid, "qty": qty, "mode": mode,
                "card_http": card_http, "max_price": max_price,
                "title": title, "price": price,
                "profile": p, "proxy": proxy})))
            await asyncio.sleep(random.uniform(.03, .15))

    async def _run(self, tid, task):
        prof = task["profile"]
        self.q.increment("attempts")
        # A4: Geo-Pruefung vor Taskstart
        if self.cfg.geo.get("enabled", False):
            ok, hinweis = await geo_check(self.cfg, prof, task.get("proxy"))
            if not ok:
                await self.state.set_task(tid, "fail", f"banned:geo ({hinweis})")
                self.q.banned("geo")
                return
        for attempt in range(self.cfg.max_retries):
            if task["mode"] == "browser" and self.browser:
                async with self.bsem:
                    res = await self.browser.run(task, prof)
            else:
                async with self.sem:
                    res = await self.http.run(task, prof)
            if res["ok"] and res.get("order"):
                self.q.success()
                await self.state.set_task(tid, "ok", res.get("note"), res.get("url"),
                                          res.get("order"))
                await self.state.add_order(prof.id, task["host"], res["order"])
                await self.notifier.send("ERFOLG", "ok",
                                         {"Profil": prof.id, "Host": task["host"],
                                          "Produkt": task.get("title") or "-",
                                          "Preis": task.get("price") or "-",
                                          "Order": res["order"], "Konto": prof.email,
                                          "Zeit": time.strftime("%Y-%m-%d %H:%M:%S")})
                return
            if res["ok"]:  # kein Order-Beleg -> nur vorbereitet, kein Erfolg
                await self.state.set_task(tid, "prepared", res.get("note"), res.get("url"))
                CONSOLE.print(f"[cyan]prepared[/] {prof.id}: {res.get('note')}")
                return
            self.q.banned(res.get("note") or "")
            await self.state.set_task(tid, "retry" if attempt + 1 < self.cfg.max_retries
                                      else "fail", res.get("note"))
            if attempt + 1 < self.cfg.max_retries:
                await asyncio.sleep(self.cfg.retry_backoff_s * (attempt + 1))
            else:
                await self.notifier.send("Task fail", "fail",
                                         {"Profil": prof.id, "Grund": res.get("note", "-"),
                                          "Cart-Link": res.get("url") or "-"}, error=True)

    async def drain(self):
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
            self.tasks.clear()
        self.q.finish()


# --------------------------------------------------------------- cli
async def cmd_selftest(cfg, state, pool, notifier):
    for p in load_profiles(MODULE):
        iss = p.issues()
        CONSOLE.print(f"[{'green' if not iss else 'red'}]{p.id}: "
                      f"{'ok' if not iss else ','.join(iss)}[/]")
    for host in cfg.hosts:
        s = session(cfg, await pool.acquire())
        try:
            # dieselben Quellen und dieselbe Reihenfolge wie der Monitor
            status, src, ok, failed = 0, "", False, []
            for name in cfg.monitor_sources:
                if name == "sitemap":
                    st, handles = await sitemap_handles(s, cfg, host)
                    ok, src = st == 200 and bool(handles), f"sitemap, {len(handles)} handles"
                elif name == "storefront":
                    st, items, _ = await storefront_products(s, cfg, host, 1)
                    ok, src = st == 200 and bool(items), "storefront products-JSON"
                elif name == "products_json":
                    st, items = await products_json(s, cfg, host, 1)
                    ok, src = st == 200 and bool(items), "products.json"
                else:
                    continue
                status = st or status
                if ok:
                    break
                failed.append(f"{name} {st}")
            CONSOLE.print(f"[{'green' if ok else 'red'}]{'OK ' if ok else '---'} {host} "
                          f"({status}){' ' + src if ok else ''}"
                          f"{' | vorher: ' + ', '.join(failed) if ok and failed else ''}[/]")
        except Exception as exc:
            CONSOLE.print(f"[red]--- {host} ({type(exc).__name__})[/]")
        finally:
            await s.close()


async def cmd_watch(cfg, state, pool, notifier, solver, mode, hosts):
    if cfg.proxy.get("precheck", False) and pool.items:
        target = hosts[0] if hosts else (cfg.hosts[0] if cfg.hosts else "")
        if target:
            r = await pool.precheck(cfg, target)
            CONSOLE.print(f"[bold]Proxy-Vorpruefung[/]: {r['checked']} geprueft, "
                          f"{r['alive']} ok, {r['dead']} tot -> var/proxystats.csv")
    http_engine = HttpCheckout(cfg, state, pool, solver, notifier)
    browser = None
    if mode == "browser":
        browser = BrowserCheckout(cfg, pool, solver, notifier)
        await browser.start()
    orch = Orchestrator(cfg, state, pool, notifier, load_profiles(MODULE), http_engine, browser)
    targets = load_targets()

    async def on_new(host, product, variant):
        blob = (product.get("handle", "") + product.get("title", "")).lower()
        t = next((t for t in targets if t.get("match", "").lower() in blob), None)
        if not t or (t.get("hosts") and host not in t["hosts"]):
            return
        await orch.spawn(host, variant["id"], t.get("quantity", 1), t.get("mode", mode),
                         t.get("tasks", 5))

    mon = Monitor(cfg, state, pool, notifier, hosts, on_new)
    CONSOLE.print(f"[bold]watch[/] {len(hosts)} Hosts, Modus {mode}")
    try:
        await mon.run()
    finally:
        await orch.drain()
        if browser:
            await browser.stop()


def _at_deadline(at: str) -> float | None:
    """HH:MM oder HH:MM:SS -> Sekunden bis dahin als monotone Deadline.
    Sekundengenau; aehnliche Uhrzeit heute, sonst morgen. None wenn unparsbar."""
    import datetime as _dt
    parts = at.split(":")
    if len(parts) not in (2, 3):
        return None
    try:
        hh, mm = int(parts[0]), int(parts[1])
        ss = int(parts[2]) if len(parts) == 3 else 0
    except ValueError:
        return None
    if not (0 <= hh < 24 and 0 <= mm < 60 and 0 <= ss < 60):
        return None
    now = _dt.datetime.now()
    target = now.replace(hour=hh, minute=mm, second=ss, microsecond=0)
    if target <= now:
        target += _dt.timedelta(days=1)
    return time.monotonic() + (target - now).total_seconds()


async def _wait_until(deadline: float | None):
    """Wartet bis zur monotone Deadline (Sekundengenauigkeit)."""
    if deadline is None:
        return
    while True:
        d = deadline - time.monotonic()
        if d <= 0:
            return
        await asyncio.sleep(min(1.0, d))


def _pick_variant(prod: dict) -> dict | None:
    """Bevorzugt eine verfuegbare Variante, sonst die erste."""
    if not prod or not prod.get("variants"):
        return None
    for v in prod["variants"]:
        if v.get("available"):
            return v
    return prod["variants"][0]


# --------------------------------------------------------------- landing resolve
def _slug_from_url(url: str) -> str:
    """Letztes Pfad-Segment der Landing-URL als Slug (fuer Search/Slug-Kandidaten)."""
    from urllib.parse import urlparse, unquote
    seg = [x for x in unquote(urlparse(url).path).split("/") if x]
    return (seg[-1].split("?")[0].lower() if seg else "")


def _extract_handles_from_html(html: str) -> set:
    """Produkt-Handles aus dem HTML: /products/<handle>-Links (deckt Links,
    eingebettete Objekte und JSON-LD-Urls ab) plus explizite "handle"-Felder.
    Collection-IDs werden separat ueber _extract_collections geliefert."""
    out = set()
    for m in re.finditer(r"/products/([a-z0-9][a-z0-9\-]+)", html):
        h = m.group(1)
        if len(h) > 3:
            out.add(h)
    for m in re.finditer(r'"handle"\s*:\s*"([a-z0-9][a-z0-9\-]+)"', html):
        h = m.group(1)
        if len(h) > 3:
            out.add(h)
    for m in re.finditer(r'data-product-id="(\d+)"', html):
        pass  # numerische ID -> kein Handle; bleibt fuer collection/gid-Nutzung
    return out


def _extract_collections(html: str) -> set:
    """Collection-IDs aus dem HTML (data-collection-id / "id" in Collections,
    /collections/<handle>-Links und gid://shopify/Collection/<id>)."""
    out = set()
    for m in re.finditer(r'gid://shopify/Collection/(\d+)', html):
        out.add(m.group(1))
    for m in re.finditer(r'data-collection-id="(\d+)"', html):
        out.add(m.group(1))
    for m in re.finditer(r'/collections/([a-z0-9][a-z0-9\-]+)', html):
        if len(m.group(1)) > 2:
            out.add("handle:" + m.group(1))
    return out


def _slug_candidates(slug: str) -> set:
    """Kandidaten aus dem Slug: selbst, Praefixe/Suffixe an "-" und gaengige
    Shopify-Suffixe (Box/Pack/Set/Drop/Launch...)."""
    cands = {slug}
    parts = slug.split("-")
    for i in range(1, len(parts)):
        cands.add("-".join(parts[:i]))
        cands.add("-".join(parts[-i:]))
    for suf in ("", "-drop", "-release", "-launch", "-box", "-pack", "-set",
                "-bundle", "-display", "-booster"):
        cands.add(slug + suf)
    return {c for c in cands if len(c) > 2}


async def _load_landing(s: AsyncSession, cfg: Settings, host: str,
                        url: str) -> str:
    try:
        r = await s.get(url, headers=headers(cfg, host))
        return r.text if r.status_code == 200 else ""
    except Exception:
        return ""


async def _storefront_product(s: AsyncSession, cfg: Settings, host: str,
                              handle: str) -> dict | None:
    """product(handle:) via Storefront -> {handle, title, productType, tags,
    collections, variants[]} oder None, wenn das Handle nicht aufloesbar (null)."""
    sf = await storefront_cfg(s, cfg, host)
    if not sf:
        return None
    dom, tok = sf
    q = ("query($h:String!){product(handle:$h){id handle title productType tags "
         "collections(first:20){edges{node{handle}}} "
         "variants(first:50){edges{node{id title availableForSale "
         "price{amount}}}}}}")
    try:
        r = await s.post(f"https://{dom}/api/{SF_VERSION}/graphql.json",
                         json={"query": q, "variables": {"h": handle}},
                         headers={**base_headers(cfg, True), "content-type": "application/json",
                                  "x-shopify-storefront-access-token": tok})
    except Exception:
        return None
    if r.status_code != 200:
        return None
    data = (r.json().get("data") or {}).get("product")
    if not data:
        return None
    variants = [{"id": _gid(v["node"]["id"]), "title": v["node"].get("title", ""),
                 "available": bool(v["node"].get("availableForSale")),
                 "price": float((v["node"].get("price") or {}).get("amount") or 0)}
                for v in data.get("variants", {}).get("edges", [])]
    return {"handle": data.get("handle", handle), "title": data.get("title", ""),
            "productType": data.get("productType", ""),
            "tags": list(data.get("tags", []) or []),
            "collections": [c["node"]["handle"] for c in
                            (data.get("collections", {}) or {}).get("edges", [])
                            if (c.get("node") or {}).get("handle")],
            "variants": variants}


async def _collection_products(s: AsyncSession, cfg: Settings, host: str,
                               col) -> set:
    """Produkt-Handles einer Collection (handle oder numerische gid)."""
    sf = await storefront_cfg(s, cfg, host)
    if not sf:
        return set()
    dom, tok = sf
    if col.startswith("handle:"):
        query = ("query($h:String!){collection(handle:$h){products(first:20){"
                 "edges{node{handle}}}}}")
        var, key = {"h": col[7:]}, "handle"
    else:
        gid = f"gid://shopify/Collection/{col}"
        query = ("query($h:ID!){collection(id:$h){products(first:20){"
                 "edges{node{handle}}}}}")
        var, key = {"h": gid}, "id"
    try:
        r = await s.post(f"https://{dom}/api/{SF_VERSION}/graphql.json",
                         json={"query": query, "variables": var},
                         headers={**base_headers(cfg, True), "content-type": "application/json",
                                  "x-shopify-storefront-access-token": tok})
        if r.status_code != 200:
            return set()
        data = (r.json().get("data") or {}).get("collection")
        if not data:
            return set()
        return {e["node"]["handle"] for e in
                data.get("products", {}).get("edges", []) if e["node"].get("handle")}
    except Exception:
        return set()


async def _search_suggest(s: AsyncSession, cfg: Settings, host: str,
                          slug: str) -> set:
    """Storefront-Search: /search/suggest.json?q=<Schluesselwoerter>&resources
    [type]=product -> Handles."""
    q = re.sub(r"[^a-z0-9]+", " ", slug).strip() or slug
    try:
        r = await s.get(f"https://{host}/search/suggest.json", params={
            "q": q, "resources[type]": "product", "resources[limit]": 10},
            headers=headers(cfg, host, True))
        if r.status_code != 200:
            return set()
        data = r.json()
        results = (data.get("resources") or {}).get("results") or []
        out = set()
        for p in results:
            h = (p or {}).get("handle") or ""
            if h:
                out.add(h)
                continue
            u = (p or {}).get("url", "") or ""
            if u:
                out.add(u.rsplit("/", 1)[-1])
        return out
    except Exception:
        return set()


async def _new_products(s: AsyncSession, cfg: Settings, host: str) -> set:
    """Neue Produkte: products(first:20, sortKey:CREATED_AT, reverse:true)."""
    try:
        st, items, _ = await storefront_products(s, cfg, host, 20)
        return {p.get("handle") for p in (items or []) if p.get("handle")}
    except Exception:
        return set()


async def _sitemap_jump(s: AsyncSession, cfg: Settings, host: str) -> set:
    """Sitemap-Sprung: sitemap_products_1.xml; fallt auf die letzte Teil-Sitemap
    (/products/sitemap/N.xml) zurueck, wenn das erste Pfad-Format kein
    Sitemap-XML liefert (z. B. SPA-Redirect)."""
    try:
        r = await s.get(f"https://{host}/products/sitemap_products_1.xml",
                        headers=headers(cfg, host))
        if r.status_code == 200 and re.search(r"<loc>", r.text):
            handles = {m.group(1) for m in
                       re.finditer(r"<loc>https?://[^<]+/products/([^<?/]+)</loc>", r.text)}
            if handles:
                return handles
    except Exception:
        pass
    try:
        _, handles = await sitemap_handles(s, cfg, host)
        return set(handles)
    except Exception:
        return set()


async def _resolve_from(s: AsyncSession, cfg: Settings, host: str,
                        candidates) -> dict | None:
    for c in candidates:
        p = await _storefront_product(s, cfg, host, c)
        if p:
            return p
    return None


async def resolve_product(s: AsyncSession, cfg: Settings, host: str,
                          url: str) -> dict:
    """6-stufige Landing-Aufloesung. Jede Stufe nur, wenn die vorige nichts
    lieferte. -> {handle, title, variants[]} oder {} wenn keine Aufloesung."""
    html = await _load_landing(s, cfg, host, url)
    slug = _slug_from_url(url)
    p = None
    # URL ist selbst eine Produkt-URL -> exaktes Handle zuerst
    own = (re.search(r"/products/([a-z0-9][a-z0-9\-]+)", url) or [None, None])
    if own and own[1]:
        p = await _storefront_product(s, cfg, host, own[1])
    if p:
        return p
    if html:
        p = await _resolve_from(s, cfg, host, _extract_handles_from_html(html))
    if p:
        return p
    if html:  # Collection-IDs aus der Landing-Page
        col_handles = set()
        for col in _extract_collections(html):
            col_handles |= await _collection_products(s, cfg, host, col)
        p = await _resolve_from(s, cfg, host, col_handles)
    if p:
        return p
    if slug:
        p = await _resolve_from(s, cfg, host, await _search_suggest(s, cfg, host, slug))
    if p:
        return p
    p = await _resolve_from(s, cfg, host, await _new_products(s, cfg, host))
    if p:
        return p
    p = await _resolve_from(s, cfg, host, await _sitemap_jump(s, cfg, host))
    if p:
        return p
    if slug:
        p = await _resolve_from(s, cfg, host, _slug_candidates(slug))
    if p:
        return p
    return {}


# --------------------------------------------------------------- buy decision
# Code-Defaults fuer "nie kaufen". Nutzerlisten (negativ/positiv/allow) in
# targets.yaml sind additiv; leere Liste = Defaults bleiben aktiv.
CODE_NEGATIV = ("value", "mega", "eco", "tin", "tins", "starter", "blaster",
                "retail", "loose", "single pack", "booster")
CODE_ACCESSORIES = ("sleeve", "binder", "top loader", "toploader", "playmat")


def _low(text) -> str:
    return (text or "").lower()


def _word_match(pattern, text) -> bool:
    """Teilstring-Match, case-insensitive, Wortgrenzen; erlaubt Plural-s
    ('sleeve' matcht 'sleeves')."""
    return bool(re.search(r"\b" + re.escape(_low(pattern)) + r"s?\b", _low(text)))


def _list_hit(patterns, text) -> str | None:
    for p in patterns or []:
        if _word_match(p, text):
            return str(p)
    return None


def _setname_tokens(setname) -> set:
    return {t for t in re.findall(r"[a-z0-9]+", _low(setname)) if len(t) > 2}


def _matches_set(setname, title, handle) -> bool:
    """Setname-Tokens muessen im Titel oder Handle matchen (mind. 2, case-
    insensitive). Weniger als 2 aussagekraeftige Tokens -> kein Match."""
    toks = _setname_tokens(setname)
    if len(toks) < 2:
        return False
    blob = _low(f"{title} {handle}")
    return sum(1 for t in toks if t in blob) >= 2


def _box_kind(prod) -> str | None:
    """Box-Art des Produkts (jumbo vor hobby, sonst None)."""
    text = _low(f"{prod.get('title', '')} {prod.get('productType', '')} "
                f"{' '.join(prod.get('tags', []) or [])} "
                f"{' '.join(prod.get('collections', []) or [])}")
    if "jumbo" in text:
        return "jumbo"
    if "hobby" in text:
        return "hobby"
    return None


def _variant_price(prod) -> float:
    """Preis der bevorzugten (verfuegbaren) Variante, sonst der ersten."""
    vs = prod.get("variants", []) or []
    if not vs:
        return 0.0
    for v in vs:
        if v.get("available") and v.get("price"):
            return float(v["price"])
    return float((vs[0] or {}).get("price") or 0)


def _decide(t, prod) -> tuple[bool, str, list]:
    """Kaufentscheidung. Praezedenz: allow > negativ > positiv > Preisband.
    -> (kaufen, grund, signale)."""
    text = _low(f"{prod.get('title', '')} {prod.get('handle', '')} "
                f"{' '.join(prod.get('tags', []) or [])} {prod.get('productType', '')} "
                f"{' '.join(prod.get('collections', []) or [])}")
    price = _variant_price(prod)
    minp = float(t.get("min_price") or 0)
    maxp = float(t.get("max_price") or 0)
    allow = list(t.get("allow") or [])
    neg = list(CODE_NEGATIV) + list(t.get("negativ") or [])
    pos = list(t.get("positiv") or [])

    if allow:
        m = _list_hit(allow, text)
        if m:
            return True, f"allow: {m}", ["allow"]
    m = _list_hit(neg, text)
    if m:
        return False, f"negativ: {m}", ["negativ"]
    m = _list_hit(CODE_ACCESSORIES, text)
    if m:
        return False, f"zubehoer: {m}", ["zubehoer"]
    if minp and price and price < minp:
        return False, f"unter min_price: {prod.get('title', '')} {price}", ["preis"]
    if maxp and price and price > maxp:
        return False, f"ueber max_price: {prod.get('title', '')} {price}", ["preis"]

    a = bool(re.search(r"\b(?:hobby|jumbo)\b", _low(prod.get("title", ""))))
    b = _list_hit(("hobby", "display", "box"),
                  f"{' '.join(prod.get('tags', []) or [])} {prod.get('productType', '')} "
                  f"{' '.join(prod.get('collections', []) or [])}") is not None
    c = bool(price > 0) and (not (minp or maxp) or (minp <= price <= maxp))
    sig = []
    if a:
        sig.append("a:hobby/jumbo")
    if b:
        sig.append("b:tags/typ/collection")
    if c:
        sig.append("c:preisband")
    pm = _list_hit(pos, text)
    if pm:
        sig.append("positiv:" + pm)
    if len(sig) >= 2:
        return True, "signale " + ",".join(sig), sig
    # Einzelprodukt-Regel: einzige Variante des Sets + Preis im Band
    if len(prod.get("variants", []) or []) == 1 and c:
        return True, "einzelvariante+preisband", ["single"]
    return False, f"signale {len(sig)}/3", sig


def _select_plan(cands, t) -> tuple[list, str]:
    """Whitelist-Reihenfolge. -> (plan, grund).
    hobby vor jumbo; beide gleichzeitig -> hobby zuerst, jumbo nach 20 s;
    nur eine Art -> sofort (keine Wartezeit)."""
    hobby = [c for c in cands if _box_kind(c) == "hobby"]
    jumbo = [c for c in cands if _box_kind(c) == "jumbo"]
    other = [c for c in cands if _box_kind(c) not in ("hobby", "jumbo")]
    plan: list[tuple[int, str, float]] = []  # (vid, handle, budget_s)
    if hobby:
        plan = [(_variant_id(c), c.get("handle", ""), 20.0) for c in hobby]
        if jumbo:
            plan += [(_variant_id(c), c.get("handle", ""), 0.0) for c in jumbo]
            return plan, "hobby gewinnt, jumbo Fallback nach 20 s"
        return plan, "hobby"
    if jumbo:
        plan = [(_variant_id(c), c.get("handle", ""), 0.0) for c in jumbo]
        return plan, "jumbo (sofort)"
    if other:
        plan = [(_variant_id(c), c.get("handle", ""), 0.0) for c in other]
        return plan, "einzelprodukt"
    return [], "kein whitelist-treffer"


def _variant_id(prod) -> int:
    v = _pick_variant(prod)
    return int(v["id"]) if v else 0


def _norm_target(t) -> dict:
    t = dict(t or {})
    t.setdefault("set", t.get("name", ""))
    t["variant_id"] = t.get("variant_id") or t.get("variant")
    t["qty"] = t.get("qty") or t.get("quantity", 1)
    return t


def _load_targets_norm() -> list:
    return [_norm_target(t) for t in load_targets()]


# --------------------------------------------------------------- id validierung
async def _validate_id(s, cfg, host, vid, handle) -> str:
    """Vorlauf-Validierung der Varianten-ID. -> 'ok' | 'stale' | 'dead'.
    product(handle:) null oder leere variants => stale (Ziel veraltet)."""
    if not handle:
        return "unbekannt"
    prod = await _storefront_product(s, cfg, host, handle)
    if not prod:
        return "stale"
    vs = prod.get("variants", []) or []
    if not vs:
        return "stale"
    if not any(int(v.get("id", 0)) == int(vid) for v in vs):
        return "dead"
    return "ok"


# --------------------------------------------------------------- set aufloesung
def _slug(setname: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _low(setname)).strip("-") or setname


async def _candidate_handles(s, cfg, host, setname, url) -> list:
    """Sammelt Handle-Kandidaten ueber die Kaskade. Jede Stufe nur, wenn die
    vorige nichts lieferte. -> deduplizierte Liste von Handles."""
    out: list[str] = []

    def add(handles):
        for h in handles or []:
            if h and h not in out:
                out.append(h)

    html = await _load_landing(s, cfg, host, url) if url else ""
    slug = _slug_from_url(url) if url else _slug(setname)
    own = None
    if url:
        own = (re.search(r"/products/([a-z0-9][a-z0-9\-]+)", url) or [None, None])[1]
    if own:
        add([own])
    if not out and html:  # Stufe 2: HTML-Handles
        add(_extract_handles_from_html(html))
    if not out and html:  # Collection-IDs aus der Landing-Page
        for col in _extract_collections(html):
            add(await _collection_products(s, cfg, host, col))
    if not out:  # Stufe 3: suggest.json
        add(await _search_suggest(s, cfg, host, slug))
    if not out:  # Stufe 4: neue Produkte
        add(await _new_products(s, cfg, host))
    if not out:  # Stufe 5: Sitemap-Sprung
        add(await _sitemap_jump(s, cfg, host))
    if not out:  # Stufe 6: Slug-Kandidaten
        add(_slug_candidates(slug))
    return out


async def _resolve_set(s, cfg, host, setname, url) -> list:
    """Set/Resolve -> Liste aufgeloester Produkt-Dicts, nach Setname gefiltert."""
    handles = await _candidate_handles(s, cfg, host, setname, url)
    cands = []
    for h in handles:
        p = await _storefront_product(s, cfg, host, h)
        if not p:
            continue
        if setname and not _matches_set(setname, p.get("title", ""), h):
            continue
        cands.append(p)
    return cands


# --------------------------------------------------------------- targets write-back
def _write_targets(text_patch: str, setname: str):
    """Schreibt eine Variante/Handle-Aktualisierung in targets.yaml zurueck.
    Textbasiert, damit Kommentare erhalten bleiben. -> bool."""
    p = ROOT / "config" / "targets.yaml"
    if not p.exists():
        return False
    lines = p.read_text(encoding="utf-8").splitlines()
    # Block eines Sets finden (eingeruecktes `- name:`/`- set:` Feld bis zur
    # naechsten Liste auf gleicher Ebene).
    start = None
    for i, ln in enumerate(lines):
        m = re.match(r"^-\s+(?:set|name):\s*['\"]?(.*?)['\"]?\s*$", ln)
        if m and (m.group(1) == setname or m.group(1).lower() == setname.lower()):
            start = i
            break
    if start is None:
        return False
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if re.match(r"^-\s+", lines[i]):
            end = i
            break
    block = lines[start:end]
    if not _patch_block(block, text_patch):
        return False
    lines[start:end] = block
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def _patch_block(block: list, patch: dict) -> bool:
    changed = False
    for key in ("variant_id", "variant", "handle"):
        if key not in patch:
            continue
        for i, ln in enumerate(block):
            if re.match(rf"^\s*{key}:", ln):
                block[i] = f"  {key}: {patch[key]}"
                changed = True
                break
        else:
            block.insert(1, f"  {key}: {patch[key]}")
            changed = True
    if "min_price" not in patch and patch.get("suggestion"):
        for i, ln in enumerate(block):
            if re.match(r"^\s*min_price:", ln):
                block[i] = f"  min_price: {patch['suggestion']}"
                changed = True
                break
    # Kommentar-Zeilen (Timestamp, Quelle, alte ID, min_price-Vorschlag)
    cmts = []
    if patch.get("ts"):
        cmts.append(f"  # updated: {patch['ts']} via {patch.get('source', '?')}"
                    f" (alte ID {patch.get('old', '-')})")
    if patch.get("suggestion"):
        cmts.append(f"  # min_price-Vorschlag: Median der letzten 5 Hobby-Box-Preise "
                    f"minus 30% = {patch['suggestion']}")
    for c in reversed(cmts):
        block.insert(1, c)
    return changed


# --------------------------------------------------------------- preis-historie
PRICE_FILE = ROOT / "var" / "set_prices.json"


def _price_history(setname) -> list:
    if not setname or not PRICE_FILE.exists():
        return []
    try:
        d = json.loads(PRICE_FILE.read_text(encoding="utf-8"))
        return list(d.get(setname, []) or [])
    except Exception:
        return []


def _remember_price(setname, price):
    if not setname:
        return
    d = {}
    if PRICE_FILE.exists():
        try:
            d = json.loads(PRICE_FILE.read_text(encoding="utf-8"))
        except Exception:
            d = {}
    lst = list(d.get(setname, []) or [])
    if float(price) > 0:
        lst.append(float(price))
        d[setname] = lst[-20:]
    PRICE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PRICE_FILE.write_text(json.dumps(d), encoding="utf-8")


def _price_suggestion(setname, price) -> float:
    """Median der letzten 5 Hobby-Box-Preise des Sets minus 30 % als Vorschlag."""
    lst = _price_history(setname)[-5:]
    if not lst:
        return round(float(price) * 0.7, 2) if price else 0.0
    s = sorted(lst)
    med = s[len(s) // 2] if len(s) % 2 else (s[len(s) // 2 - 1] + s[len(s) // 2]) / 2
    return round(med * 0.7, 2)


async def _available(s: AsyncSession, cfg: Settings, host: str,
                     variant_id: int, handle: str = "") -> bool:
    """Verfuegbarkeit der Variante. Ein Endpunkt: product(handle:) wenn ein
    Handle bekannt ist, sonst storefront_products (neueste zuerst)."""
    if handle:
        prod = await _storefront_product(s, cfg, host, handle)
        if prod:
            return any(int(v["id"]) == int(variant_id) and v.get("available")
                       for v in prod["variants"])
        return False
    st, items, _ = await storefront_products(s, cfg, host, 250)
    if st == 200:
        for p in items or []:
            for v in p.get("variants", []) or []:
                if int(v.get("id", 0)) == int(variant_id):
                    return bool(v.get("available"))
    return False


async def _build_cart(s: AsyncSession, cfg: Settings, host: str,
                      variant_id: int, qty: int) -> str | None:
    """Cart vorbauen (cartCreate) -> checkoutUrl."""
    sf = await storefront_cfg(s, cfg, host)
    if not sf:
        return None
    dom, tok = sf
    q = ("mutation cartCreate($input:CartInput!){cartCreate(input:$input){"
         "cart{id checkoutUrl} userErrors{field message}}}")
    try:
        r = await s.post(f"https://{dom}/api/{SF_VERSION}/graphql.json",
                         json={"query": q, "variables": {"input": {"lines": [
                             {"merchandiseId": f"gid://shopify/ProductVariant/{variant_id}",
                              "quantity": int(qty)}]}}},
                         headers={**base_headers(cfg, True), "content-type": "application/json",
                                  "x-shopify-storefront-access-token": tok})
    except Exception:
        return None
    if r.status_code != 200:
        return None
    cart = (r.json().get("data") or {}).get("cartCreate") or {}
    if cart.get("userErrors"):
        return None
    return (cart.get("cart") or {}).get("checkoutUrl")


async def _wait_available(s: AsyncSession, cfg: Settings, host: str,
                          variant_id: int, handle: str = "") -> bool:
    """Poll auf availableForSale, 1,0 s, gleiche Session + gleicher Proxy.
    -> True sobald die Variante verfuegbar ist (max_wait_s = Ende)."""
    end = time.monotonic() + float(cfg.queue.get("max_wait_s", 1800))
    poll = max(0.2, float(cfg.queue.get("poll_s", 1.0)))
    while time.monotonic() < end:
        if await _available(s, cfg, host, variant_id, handle):
            return True
        await asyncio.sleep(poll)
    return False


async def _cached_price(s: AsyncSession, cfg: Settings, host: str,
                        vid) -> tuple[str, float]:
    """Preis/Title der Variante aus dem Prewarm-Cache (Storefront, neueste
    zuerst) - keine Live-Nachfrage im Drop."""
    try:
        st, items, _ = await storefront_products(s, cfg, host, 200)
        if st == 200:
            for p in items or []:
                for v in p.get("variants", []) or []:
                    if int(v.get("id", 0)) == int(vid):
                        return p.get("title", ""), float(v.get("price") or 0)
    except Exception:
        pass
    return "", 0.0


async def _prepare_set(s, cfg, notifier, host, job, t, deadline) -> bool:
    """Set/Resolve: Kandidaten sammeln, Kaufentscheidung, Whitelist-Plan.
    Setzt job['vid'/'handle'/'title'/'price'/'plan'/'resolved_new']. -> bool."""
    setname = job.get("setname", "")
    url = job.get("url", "")
    cands = await _resolve_set(s, cfg, host, setname, url)
    # Set-Config ermitteln: --resolve kennt kein Set -> passendes Set aus dem
    # aufgeloesten Titel (Setname-Tokens) bestimmen, sonst Defaults.
    if not (t.get("set") or t.get("name")):
        for c in cands:
            mt = next((x for x in _load_targets_norm()
                       if x.get("set") and _matches_set(x["set"], c.get("title", ""),
                                                        c.get("handle", ""))), None)
            if mt:
                t.update(mt)
                break
        job["t"] = t
    if not cands:
        CONSOLE.print(f"[red]{'resolve' if url else 'set'} '{setname or url}': kein Treffer.[/]")
        await notifier.send("Aufloesung fehlgeschlagen", "fail",
                            {"Host": host, "Set": setname or url,
                             "Grund": "keine Kandidaten"}, error=True)
        return False
    buys = []
    for p in cands:
        buy, reason, _sig = _decide(t, p)
        LOG.info("Kaufentscheidung %s -> %s (%s)",
                 p.get("title", ""), "kaufen" if buy else "verworfen", reason)
        if buy:
            buys.append(p)
    if not buys:
        CONSOLE.print("[yellow]Kein Kauf: alle Kandidaten verworfen.[/]")
        await notifier.send("Kein Kauf", "fail",
                            {"Host": host, "Set": setname or url,
                             "Grund": "kein whitelist-treffer"}, error=True)
        return False
    plan, pg = _select_plan(buys, t)
    if not plan:
        CONSOLE.print(f"[yellow]Kein Kauf: {pg}[/]")
        await notifier.send("Kein Kauf", "fail",
                            {"Host": host, "Set": setname or url, "Grund": pg}, error=True)
        return False
    CONSOLE.print(f"[green]Kaufentscheidung[/]: {pg} -> "
                  f"{[p.get('title', '') for p in buys]}")
    vid = int(plan[0][0])
    handle = plan[0][1]
    first = next((p for p in buys if int(_variant_id(p)) == vid), buys[0])
    job.update(vid=vid, handle=handle, title=first.get("title", ""),
               price=_variant_price(first), plan=plan, resolved_new=True)
    return True


async def _poll_plan(s, cfg, host, plan) -> int | None:
    """Plan abarbeiten (gleiche Session+Proxy): hobby zuerst (20 s Budget),
    jumbo als Fallback (letzter Eintrag ohne Budget bis max_wait_s).
    -> gewaehlte Varianten-ID oder None."""
    end = time.monotonic() + float(cfg.queue.get("max_wait_s", 1800))
    poll = max(0.2, float(cfg.queue.get("poll_s", 1.0)))
    for vid, handle, budget in plan:
        step_end = min(end, time.monotonic() + budget) if budget else end
        while time.monotonic() < step_end:
            if await _available(s, cfg, host, vid, handle):
                return vid
            await asyncio.sleep(poll)
    return None


async def _run_drop(cfg, state, pool, notifier, solver, job, deadline):
    """Gemeinsamer Drop-Pfad (--target / --set / --resolve).
    Speed-Pfad: 90 s vor --at cf_clearance + Session + cartCreate (Cart-Link im
    Speicher). Vorlauf-Validierung nur T-90 bis T-10. Poll 1,0 s auf
    availableForSale (ein Endpunkt, gleiche Session + gleicher Proxy).
    Vollautomatischer Checkout; pro Konto genau EINE Order. max_price/min_price
    aus dem Prewarm-Cache, keine Live-Nachfrage. dry stoppt vor der Zahlung."""
    from utilities.quality import Quality
    t = job.get("t") or {}
    host = job["host"]
    mode = job.get("mode", "cart")
    card = job.get("card", False)
    dry = job.get("dry", True)
    qty = int(job.get("qty") or 1)
    minp = float(t.get("min_price") or 0)
    maxp = float(t.get("max_price") or 0)
    q = Quality(MODULE)
    prof = job.get("prof")

    prewarm = 90.0
    if deadline is not None:
        until_at = deadline - time.monotonic()
        wait_first = max(0.0, until_at - prewarm)
        if wait_first:
            CONSOLE.print(f"[bold]Speed-Pfad[/]: Vorwaermen in {int(wait_first)}s "
                          f"(90 s vor --at).")
            await _wait_until(time.monotonic() + wait_first)

    proxy = await pool.acquire()
    s = session(cfg, proxy)
    try:
        # Prewarm: frische cf_clearance ueber den Task-Proxy (IP-gebunden).
        if proxy:
            try:
                await asyncio.wait_for(cf_refresh(host, proxy=proxy), timeout=60)
            except Exception as exc:
                LOG.debug("prewarm cf: %s", exc)

        # ---- Prewarm: Ziel aufloesen / ID bestimmen ----
        vid, handle, title, price = 0, "", "", 0.0
        if job.get("fixed_vid"):
            # --target Varianten-ID: kein Aufloesen, direkt in den Poll
            vid = int(job["fixed_vid"])
            handle = job.get("fixed_handle", "")
            title, price = await _cached_price(s, cfg, host, vid)
            CONSOLE.print(f"[green]target[/] Variante {vid} {title or ''} Preis {price}")
        elif job.get("fixed_handle"):
            prod = await _storefront_product(s, cfg, host, job["fixed_handle"])
            if not prod:
                CONSOLE.print("[red]target: Handle nicht aufloesbar.[/]")
                return
            v = _pick_variant(prod)
            if not v:
                CONSOLE.print("[red]target: Produkt ohne Varianten.[/]")
                return
            vid = int(v["id"])
            handle = prod.get("handle", "")
            title = prod.get("title", "")
            price = float(v.get("price") or 0)
            CONSOLE.print(f"[green]target[/] {title} ({handle}) Variante {vid} Preis {price}")
        elif job.get("needs_resolve") or job.get("stale"):
            old_vid = vid or job.get("vid")
            if not await _prepare_set(s, cfg, notifier, host, job, t, deadline):
                return
            vid, handle, title, price = (job["vid"], job["handle"],
                                         job["title"], job["price"])
            if job.get("resolved_new") and (t.get("set") or t.get("name")):
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                sugg = _price_suggestion(t.get("set") or t.get("name"), price)
                patched = _write_targets(
                    {"variant_id": vid, "handle": handle, "ts": ts,
                     "source": "resolve", "old": str(old_vid or "-"),
                     "suggestion": sugg},
                    t.get("set") or t.get("name"))
                if patched:
                    CONSOLE.print(f"[green]targets.yaml aktualisiert: "
                                  f"{handle} / Variante {vid}[/]")
                _remember_price(t.get("set") or t.get("name"), price)
                await notifier.send("ID veraltet, neu aufgeloest", "info",
                                    {"Titel": title, "Host": host,
                                     "Set": t.get("set", ""), "Variante": vid})
        else:
            # bekannte ID + Handle aus targets.yaml (Schnellweg)
            vid = int(job.get("vid") or 0)
            handle = job.get("handle", "")
            title, price = await _cached_price(s, cfg, host, vid)

        if not vid:
            CONSOLE.print("[red]Drop: keine Varianten-ID.[/]")
            return

        # ---- Vorlauf-Validierung: nur T-90 bis T-10 (nie in den letzten 10 s) ----
        if deadline is not None and not dry:
            t_until = deadline - time.monotonic()
            if 10.0 <= t_until <= 90.0 and handle:
                v = await _validate_id(s, cfg, host, vid, handle)
                if v != "ok":
                    CONSOLE.print(f"[yellow]ID {vid} {v} - Neuaufloesung.[/]")
                    old_vid = vid
                    if not await _prepare_set(s, cfg, notifier, host, job, t, deadline):
                        return
                    vid, handle, title, price = (job["vid"], job["handle"],
                                                 job["title"], job["price"])
                    if job.get("resolved_new") and (t.get("set") or t.get("name")):
                        ts = time.strftime("%Y-%m-%d %H:%M:%S")
                        _write_targets(
                            {"variant_id": vid, "handle": handle, "ts": ts,
                             "source": "validierung", "old": str(old_vid or "-")},
                            t.get("set") or t.get("name"))
                        await notifier.send("ID veraltet, neu aufgeloest", "info",
                                            {"Titel": title, "Host": host,
                                             "Set": t.get("set", ""), "Variante": vid})
            else:
                LOG.info("validierung nur bis T-10 (jetzt %.0fs vor --at), uebersprungen",
                         t_until)

        # Preisband aus Prewarm-Cache
        if minp and price and price < minp:
            CONSOLE.print(f"[red]unter min_price: {title} {price}[/]")
            await notifier.send("Preis verworfen", "fail",
                                {"Grund": f"unter min_price: {title} {price}",
                                 "Host": host}, error=True)
            return
        if maxp and price and price > maxp:
            CONSOLE.print(f"[red]ueber max_price: {title} {price}[/]")
            await notifier.send("Preis verworfen", "fail",
                                {"Grund": f"ueber max_price: {title} {price}",
                                 "Host": host}, error=True)
            return

        plan = job.get("plan") or [(vid, handle, 0.0)]
        # cartCreate fuer alle Plan-Varianten vorab (Speed-Pfad)
        carts: dict[int, str] = {}
        for pv, _ph, _b in plan:
            cl = await _build_cart(s, cfg, host, pv, qty)
            if cl:
                carts[pv] = cl
        if not carts:
            CONSOLE.print("[red]Drop: kein Cart-Link (cartCreate leer).[/]")
            await notifier.send("Kein Cart", "fail",
                                {"Host": host, "Grund": "cartCreate leer"}, error=True)
            return
        CONSOLE.print(f"[bold]Cart bereit[/] ({len(carts)} im Speicher)")

        # auf --at warten (monotone Uhr, Sekundengenau)
        if deadline is not None:
            CONSOLE.print("[bold]Scheduler[/]: warte bis --at.")
            await _wait_until(deadline)

        if dry:
            link = carts.get(vid) or next(iter(carts.values()))
            if not link:
                CONSOLE.print("[red]dry: kein Checkout-Link.[/]")
            else:
                CONSOLE.print(f"[bold green]CHECKOUT[/] {link}")
            return

        # Live: Plan abarbeiten (hobby zuerst, jumbo Fallback nach 20 s)
        chosen = await _poll_plan(s, cfg, host, plan)
        if chosen is None:
            CONSOLE.print("[red]Drop: keine Variante verfuegbar (Zeitueberschreitung).[/]")
            await notifier.send("Drop fehlgeschlagen", "fail",
                                {"Host": host, "Set": t.get("set", ""),
                                 "Grund": "nicht verfuegbar"}, error=True)
            return
        link = carts.get(chosen) or await _build_cart(s, cfg, host, chosen, qty)
        if not link:
            CONSOLE.print("[red]Drop: kein Cart-Link.[/]")
            return
        if not prof:
            CONSOLE.print("[red]Drop: kein Profil vorhanden.[/]")
            return
        # Pro Konto genau EINE Order -> danach Task-Ende fuer das Konto
        if await state.orders(prof.id) > 0 and job.get("one_per_account"):
            CONSOLE.print(f"[yellow]{prof.id} hat bereits eine Order - Task-Ende.[/]")
            return
        http = HttpCheckout(cfg, state, pool, solver, notifier)
        res = await http.run_prebuilt(s, host, link, prof, dry=False, card=card)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        q.increment("attempts")
        if res.get("order"):
            q.success()
            await state.add_order(prof.id, host, res["order"])
            await notifier.send("ERFOLG", "ok",
                                {"Produkt": title or "-", "Variante": chosen,
                                 "Preis": price, "Order": res["order"],
                                 "Konto": prof.email, "Zeit": ts,
                                 "Link": res.get("url", link)})
            CONSOLE.print(f"[bold green]ERFOLG[/] Order {res['order']}")
        else:
            q.banned(res.get("note", ""))
            await notifier.send("Checkout-Fehler", "fail",
                                {"Host": host, "Variante": chosen,
                                 "Ursache": res.get("note", "?"),
                                 "Cart-Link": link}, error=True)
            CONSOLE.print(f"[red]Checkout-Fehler[/] {res.get('note')}")
    finally:
        await s.close()
        q.finish()


async def cmd_drop(cfg, state, pool, notifier, solver, host, vid, tasks, qty, mode,
                   card=False, at="", targets=None, setname="", resolve="", dry=True):
    """Zielwege (Aufgabe 1): --target (Handle/Variant-ID/Name, mehrfach), sonst
    --set <setname> oder --resolve <set-landing-url> als Aufloesung. Ohne beides
    keine Ausfuehrung (kein Blindlauf)."""
    targets = list(targets or [])
    jobs: list[dict] = []
    tn = _load_targets_norm()
    for tg in targets:
        tg = str(tg).strip()
        if not tg:
            continue
        t = next((x for x in tn if str(x.get("name", "")).lower() == tg.lower()), None)
        if t:
            jobs.append({
                "t": t, "host": host or (t.get("hosts") or [cfg.hosts[0]])[0],
                "vid": int(t["variant_id"]) if t.get("variant_id") else 0,
                "handle": t.get("handle", ""), "setname": t.get("set", ""),
                "mode": mode or t.get("mode", "cart"),
                "qty": qty or int(t.get("qty") or 1),
                "card": card, "dry": dry, "needs_resolve": False, "fixed_vid": 0})
        elif tg.isdigit():
            jobs.append({
                "t": {}, "host": host or (cfg.hosts[0] if cfg.hosts else ""),
                "fixed_vid": int(tg), "fixed_handle": "", "mode": mode,
                "qty": qty or 1, "card": card, "dry": dry, "needs_resolve": False})
        else:
            jobs.append({
                "t": {}, "host": host or (cfg.hosts[0] if cfg.hosts else ""),
                "fixed_vid": 0, "fixed_handle": tg, "mode": mode,
                "qty": qty or 1, "card": card, "dry": dry, "needs_resolve": False})
    if setname:
        t = next((x for x in tn
                  if str(x.get("set") or x.get("name", "")).lower() == setname.lower()), None)
        if not t:
            CONSOLE.print(f"[red]set '{setname}' nicht in targets.yaml.[/]")
            return
        host = host or (t.get("hosts") or [cfg.hosts[0]])[0]
        jobs.append({
            "t": t, "host": host, "setname": t.get("set", setname), "url": "",
            "mode": mode or t.get("mode", "cart"),
            "qty": qty or int(t.get("qty") or 1),
            "card": card, "dry": dry, "needs_resolve": True})
    if resolve:
        if MODULE != "topps":
            CONSOLE.print("[red]--resolve ist nur im Modul topps verfuegbar.[/]")
            return
        from urllib.parse import urlparse
        r_host = (urlparse(resolve).netloc or "").lower()
        if r_host.startswith("www."):
            r_host = r_host[4:]
        host = r_host or host or (cfg.hosts[0] if cfg.hosts else "")
        t = {}
        jobs.append({
            "t": t, "host": host, "setname": "", "url": resolve,
            "mode": mode, "qty": qty or 1, "card": card, "dry": dry,
            "needs_resolve": True})
    if not jobs:
        CONSOLE.print("[red]--target oder --resolve/--set erforderlich - kein Blindlauf.[/]")
        return
    deadline = _at_deadline(at) if at else None
    if at and deadline is None:
        CONSOLE.print(f"[red]--at '{at}' ungueltig (HH:MM oder HH:MM:SS).[/]")
        return
    # Pro Konto genau EINE Order: jedem Job ein anderes Profil zuordnen
    profs = [p for p in load_profiles(MODULE) if p.enabled]
    for i, job in enumerate(jobs):
        job["one_per_account"] = True
        job["prof"] = profs[i % len(profs)] if profs else None
        CONSOLE.print(f"[bold]drop[/] {job['host']} "
                      f"{'resolve' if job.get('needs_resolve') else 'Variante ' + str(job.get('fixed_vid') or job.get('vid'))} "
                      f"x{job['qty']} ({tasks} Tasks, Modus {job['mode']}{', dry' if dry else ''})")
        await _run_drop(cfg, state, pool, notifier, solver, job, deadline)


# --------------------------------------------------------------- cli generisch
def argv_parser(prog: str = "baki", module: str | None = None):
    """Baut den Argument-Parser. Rufer koennen ein eigenes prog angeben."""
    ap = argparse.ArgumentParser(prog=prog)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("setup", "selftest", "profiles-check", "stats", "install-browser",
              "cf-refresh", "quality"):
        sub.add_parser(c)
    g = sub.add_parser("profiles-gen")
    g.add_argument("--count", type=int, default=1)
    g.add_argument("--seed", type=int, default=None)
    g.add_argument("--module", default=module or MODULE)
    g.add_argument("--out", default=None)
    w = sub.add_parser("watch")
    w.add_argument("--mode", default="cart", choices=["cart", "browser"])
    w.add_argument("--hosts", default="")
    d = sub.add_parser("drop")
    d.add_argument("--host", default="")
    d.add_argument("--variant", type=int, default=None)
    d.add_argument("--tasks", type=int, default=10)
    d.add_argument("--qty", type=int, default=1)
    d.add_argument("--mode", default="cart", choices=["cart", "browser"])
    d.add_argument("--card-http", action="store_true")
    d.add_argument("--dry", action="store_true", help="Stopp vor Zahlung")
    d.add_argument("--at", default="", help="HH:MM oder HH:MM:SS Wartezeit (Scheduler)")
    d.add_argument("--target", action="append", default=[],
                   help="Handle/Variant-ID/Name aus targets.yaml (mehrfach)")
    d.add_argument("--set", default="", help="Setname -> Aufloesung + Kaufentscheidung")
    d.add_argument("--resolve", default="",
                   help="Set-Landing-URL zur Aufloesung (nur Modul topps, nur mit --at sinnvoll)")
    return ap


def main(argv=None):
    """Generischer CLI-Einstieg. Modulname, Hosts und Quellen bestimmt der
    konkrete Aufrufer ueber MODULE, cfg.hosts und cfg.monitor_sources."""
    ap = argv_parser("baki", MODULE)
    a = ap.parse_args(argv)

    if a.cmd == "setup":
        cmd_setup()
        return
    if a.cmd == "install-browser":
        if getattr(sys, "frozen", False):
            from playwright.__main__ import main as pw
            sys.argv = ["playwright", "install", "chromium"]
            pw()
        else:
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])
        return

    cfg = Settings.load()
    setup_log(cfg)
    state = State(str(cfg.path(cfg.state_db)))
    pool = ProxyPool(state, MODULE)
    notifier = Notifier(ENV.get("DISCORD_WEBHOOK", ""), ENV.get("DISCORD_WEBHOOK_ERRORS", ""))
    CONSOLE.print("[dim]Webhook: " + ("ok" if notifier.url else "nicht gesetzt") +
                  (" (Errors ok)" if notifier.err else " (Errors fehlt)") + "[/]")
    solver = Solver(cfg)

    if a.cmd == "profiles-check":
        for p in load_profiles(MODULE):
            iss = p.issues()
            CONSOLE.print(f"{p.id}: {'ok' if not iss else ','.join(iss)}")
    elif a.cmd == "stats":
        CONSOLE.print(asyncio.run(state.stats()))
    elif a.cmd == "profiles-gen":
        from utilities.profiles import generate_profiles, write_profiles
        rows = generate_profiles(max(1, a.count), a.seed)
        dest = write_profiles(rows, a.module, Path(a.out) if a.out else None)
        CONSOLE.print(f"[green]{len(rows)} Profile nach {dest}[/]")
    elif a.cmd == "cf-refresh":
        host = cfg.hosts[0] if cfg.hosts else "de.topps.com"
        out = asyncio.run(cf_refresh(host))
        if out:
            CONSOLE.print(f"[green]Cloudflare-Cookies geholt: "
                          f"{', '.join(sorted(out))}[/]")
        else:
            CONSOLE.print("[red]Keine cf_clearance erhalten.[/]")
    elif a.cmd == "quality":
        from utilities.quality import Quality
        CONSOLE.print(Quality(MODULE).report())
    elif a.cmd == "selftest":
        asyncio.run(cmd_selftest(cfg, state, pool, notifier))
    elif a.cmd == "watch":
        hosts = [h.strip() for h in a.hosts.split(",") if h.strip()] or cfg.hosts
        asyncio.run(cmd_watch(cfg, state, pool, notifier, solver, a.mode, hosts))
    elif a.cmd == "drop":
        dry = not a.card_http and not getattr(a, "dry", False) is False
        asyncio.run(cmd_drop(cfg, state, pool, notifier, solver, a.host, a.variant,
                             a.tasks, a.qty, a.mode, a.card_http, a.at, a.target,
                             a.set, a.resolve, dry))


class ShopifyModule(BaseModule):
    """Basis fuer alle Shopify-Module. Unterklassen setzen title + actions."""
    title = "Shopify"
    actions = [
        ("Selftest", ["selftest"], []),
        ("Watch - Cart-Links (wenig Daten)", ["watch", "--mode", "cart"], []),
        ("Watch - mit Browser", ["watch", "--mode", "browser"], []),
        ("Drop auf Variante", ["drop", "--mode", "cart"],
         [("--host", "Host"), ("--variant", "Variant-ID"), ("--tasks", "Tasks")]),
        ("Profile pruefen", ["profiles-check"], []),
        ("Statistik", ["stats"], []),
        ("Setup erneut ausfuehren", ["setup"], []),
        ("Browser-Engine installieren", ["install-browser"], []),
        ("Cloudflare-Cookies erneuern", ["cf-refresh"], []),
    ]

    def make_tasks(self, **cfg):
        from modules.Generators.Topps.modules.Drop.DropTask import DropTask
        if cfg.get("variant") or cfg.get("host"):
            return [DropTask(run_drop=self._drop, host=cfg.get("host"),
                             variant=cfg.get("variant"),
                             tasks=cfg.get("tasks", 1), qty=cfg.get("qty", 1),
                             mode=cfg.get("mode", "cart"))]
        return []

    def _drop(self, host=None, variant=None, tasks=1, qty=1, mode="cart"):
        cfg = Settings.load()
        state = State(str(cfg.path(cfg.state_db)))
        pool = ProxyPool(state, MODULE)
        notifier = Notifier(ENV.get("DISCORD_WEBHOOK", ""),
                            ENV.get("DISCORD_WEBHOOK_ERRORS", ""))
        solver = Solver(cfg)
        targets = [variant] if variant else []
        return cmd_drop(cfg, state, pool, notifier, solver, host, variant,
                        tasks, qty, mode, card=False, at="", targets=targets,
                        setname="", resolve="", dry=True)

    def call(self, argv) -> int:
        try:
            main(list(argv))
        except KeyboardInterrupt:
            CONSOLE.print("[yellow]abgebrochen[/]")
            return 130
        except SystemExit as e:
            return e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        return 0

    def run(self):
        while True:
            print()
            print(f" --- {self.title} ---")
            for i, (text, _, _) in enumerate(self.actions, 1):
                print(f"  {i:>2}  {text}")
            print("   0  Zurueck")
            try:
                wahl = input(f" {self.title}-Auswahl: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if wahl == "0":
                return 0
            if not (wahl.isdigit() and 1 <= int(wahl) <= len(self.actions)):
                print(" Ungueltige Auswahl.")
                continue
            _, argv, fragen = self.actions[int(wahl) - 1]
            argv = list(argv)
            try:
                for flag, frage in fragen:
                    wert = input(f" {frage}: ").strip()
                    if wert:
                        argv += [flag, wert]
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            try:
                code = self.call(argv)
            except Exception as e:
                print(f" Fehler: {type(e).__name__}: {e}")
                continue
            if code:
                print(f" Exitcode {code}")

