#!/usr/bin/env python3
"""toppsfarm - Topps EU Monitor + Checkout. HTTP-first, Browser nur Fallback."""
from __future__ import annotations

import argparse
import asyncio
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

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
if not (ROOT / "config").exists() and (ROOT.parent / "config").exists():
    ROOT = ROOT.parent
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
    state_db: str = "var/state.sqlite"
    log_dir: str = "var/logs"

    @classmethod
    def load(cls) -> "Settings":
        p = ROOT / "config" / "settings.yaml"
        data = yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}
        s = cls()
        for k, v in (data or {}).items():
            if hasattr(s, k):
                setattr(s, k, v)
        return s

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


def load_profiles() -> list:
    p = ROOT / "config" / "profiles.yaml"
    if not p.exists():
        return []
    return [Profile(**{k: v for k, v in row.items() if k in Profile.__dataclass_fields__})
            for row in (yaml.safe_load(p.read_text(encoding="utf-8")) or [])]


def load_targets() -> list:
    p = ROOT / "config" / "targets.yaml"
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or []) if p.exists() else []


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
    (ROOT / "config" / "profiles.yaml").write_text(
        yaml.safe_dump(rows, allow_unicode=True, sort_keys=False), encoding="utf-8")
    CONSOLE.print(f"\n[green]{len(rows)} Profile gespeichert.[/] Karten liegen im Klartext in "
                  f"config\\profiles.yaml.\n")


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
class ProxyPool:
    def __init__(self, db: "State"):
        self.db = db
        p = ROOT / "config" / "proxy.txt"
        self.items = [l.strip() for l in p.read_text(encoding="utf-8-sig").splitlines()
                      if l.strip() and not l.strip().startswith("#")] if p.exists() else []

    async def acquire(self, pinned: str | None = None) -> str | None:
        if pinned or not self.items:
            return pinned
        cd = await self.db.cooldowns()
        now = time.time()
        alive = [p for p in self.items if cd.get(p, 0) <= now] or self.items
        return random.choice(alive)


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
    return AsyncSession(**kw)


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
        proxy = await self.pool.acquire(prof.proxy)
        s = session(self.cfg, proxy)
        res = {"ok": False, "note": "", "url": None, "order": None}
        try:
            if not await warm(s, self.cfg, host):
                res["note"] = "warmup"
                await self.pool.report_proxy(proxy, False)
                return res
            r = await s.post(f"https://{host}/cart/add.js",
                             json={"id": task["variant"], "quantity": task.get("qty", 1)},
                             headers=headers(self.cfg, host, True))
            if r.status_code != 200:
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
        proxy = await self.pool.acquire(prof.proxy)
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
class Orchestrator:
    def __init__(self, cfg, state, pool, notifier, profiles, http_engine, browser_engine=None):
        self.cfg, self.state, self.pool = cfg, state, pool
        self.notifier, self.http, self.browser = notifier, http_engine, browser_engine
        self.profiles = [p for p in profiles if p.enabled]
        self.sem = asyncio.Semaphore(cfg.concurrency_http)
        self.bsem = asyncio.Semaphore(cfg.concurrency_browser)
        self.rr, self.tasks = 0, []

    async def pick(self):
        if not self.profiles:
            return None
        for i in range(len(self.profiles)):
            p = self.profiles[(self.rr + i) % len(self.profiles)]
            if await self.state.orders(p.id) < p.max_orders:
                self.rr = (self.rr + i + 1) % len(self.profiles)
                return p
        return None

    async def spawn(self, host, vid, qty, mode, count, card_http=False):
        for _ in range(count):
            p = await self.pick()
            if not p:
                LOG.warning("keine freien Profile")
                return
            tid = await self.state.add_task(p.id, host, vid, qty, mode)
            self.tasks.append(asyncio.create_task(self._run(tid, {
                "host": host, "variant": vid, "qty": qty, "mode": mode,
                "card_http": card_http, "profile": p})))
            await asyncio.sleep(random.uniform(.03, .15))

    async def _run(self, tid, task):
        prof = task["profile"]
        for attempt in range(self.cfg.max_retries):
            if task["mode"] == "browser" and self.browser:
                async with self.bsem:
                    res = await self.browser.run(task, prof)
            else:
                async with self.sem:
                    res = await self.http.run(task, prof)
            if res["ok"]:
                await self.state.set_task(tid, "ok", res.get("note"), res.get("url"),
                                          res.get("order"))
                if res.get("order"):
                    await self.state.add_order(prof.id, task["host"], res["order"])
                await self.notifier.send("CHECKOUT", "ok",
                                         {"Profil": prof.id, "Host": task["host"],
                                          "Order": res.get("order") or "-",
                                          "URL": res.get("url") or "-"})
                return
            await self.state.set_task(tid, "retry" if attempt + 1 < self.cfg.max_retries
                                      else "fail", res.get("note"))
            if attempt + 1 < self.cfg.max_retries:
                await asyncio.sleep(self.cfg.retry_backoff_s * (attempt + 1))
            else:
                await self.notifier.send("Task fail", "fail",
                                         {"Profil": prof.id, "Grund": res.get("note", "-")})

    async def drain(self):
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
            self.tasks.clear()


# --------------------------------------------------------------- cli
async def cmd_selftest(cfg, state, pool, notifier):
    for p in load_profiles():
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
    http_engine = HttpCheckout(cfg, state, pool, solver, notifier)
    browser = None
    if mode == "browser":
        browser = BrowserCheckout(cfg, pool, solver, notifier)
        await browser.start()
    orch = Orchestrator(cfg, state, pool, notifier, load_profiles(), http_engine, browser)
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


async def cmd_drop(cfg, state, pool, notifier, solver, host, vid, tasks, qty, mode, card):
    http_engine = HttpCheckout(cfg, state, pool, solver, notifier)
    browser = None
    if mode == "browser":
        browser = BrowserCheckout(cfg, pool, solver, notifier)
        await browser.start()
    orch = Orchestrator(cfg, state, pool, notifier, load_profiles(), http_engine, browser)
    await orch.spawn(host, vid, qty, mode, tasks, card)
    await orch.drain()
    if browser:
        await browser.stop()
    CONSOLE.print(await state.stats())


def main(argv=None):
    ap = argparse.ArgumentParser(prog="toppsfarm")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("setup", "selftest", "profiles-check", "stats", "install-browser"):
        sub.add_parser(c)
    w = sub.add_parser("watch")
    w.add_argument("--mode", default="cart", choices=["cart", "browser"])
    w.add_argument("--hosts", default="")
    d = sub.add_parser("drop")
    d.add_argument("--host", required=True)
    d.add_argument("--variant", type=int, required=True)
    d.add_argument("--tasks", type=int, default=10)
    d.add_argument("--qty", type=int, default=1)
    d.add_argument("--mode", default="cart", choices=["cart", "browser"])
    d.add_argument("--card-http", action="store_true")
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
    pool = ProxyPool(state)
    notifier = Notifier(ENV.get("DISCORD_WEBHOOK", ""), ENV.get("DISCORD_WEBHOOK_ERRORS", ""))
    solver = Solver(cfg)

    if a.cmd == "profiles-check":
        for p in load_profiles():
            iss = p.issues()
            CONSOLE.print(f"{p.id}: {'ok' if not iss else ','.join(iss)}")
    elif a.cmd == "stats":
        CONSOLE.print(asyncio.run(state.stats()))
    elif a.cmd == "selftest":
        asyncio.run(cmd_selftest(cfg, state, pool, notifier))
    elif a.cmd == "watch":
        hosts = [h.strip() for h in a.hosts.split(",") if h.strip()] or cfg.hosts
        asyncio.run(cmd_watch(cfg, state, pool, notifier, solver, a.mode, hosts))
    elif a.cmd == "drop":
        asyncio.run(cmd_drop(cfg, state, pool, notifier, solver, a.host, a.variant,
                             a.tasks, a.qty, a.mode, a.card_http))


class ToppsModule(BaseModule):
    """Topps EU als Baki-AIO-Modul. run() zeigt das Topps-Untermenue."""
    title = "Topps EU"
    # (Text, feste Argumente, abgefragte Argumente als (Flag, Frage))
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
    ]

    def call(self, argv) -> int:
        """Fuehrt einen toppsfarm-Befehl aus, liefert den Exitcode."""
        try:
            main(list(argv))
        except KeyboardInterrupt:
            CONSOLE.print("[yellow]abgebrochen[/]")
            return 130
        except SystemExit as e:  # argparse (--help, falsche Argumente)
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
                wahl = input(" Topps-Auswahl: ").strip()
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
            except Exception as e:  # ein Fehler im Modul soll das Menue nicht beenden
                print(f" Fehler: {type(e).__name__}: {e}")
                continue
            if code:
                print(f" Exitcode {code}")


if __name__ == "__main__":
    sys.exit(ToppsModule().call(sys.argv[1:]))
