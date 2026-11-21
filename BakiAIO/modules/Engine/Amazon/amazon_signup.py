from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import os
import random
import re
import secrets
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from curl_cffi.requests import AsyncSession

from utilities.root import APP_ROOT

CSV_PATH = APP_ROOT / "var" / "amazon_gen_attempts.csv"
DOMAIN_STATS = APP_ROOT / "var" / "amazon_domains.json"
COLUMNS = ["ts", "tid", "domain", "proxy(maskiert)", "email", "dauer_fill",
           "dauer_type", "klasse", "status", "error"]

UNUSUAL = (
    "unusual activity", "ongewone activiteit", "nieuw",
    "nietypowa aktywno", "ovanlig aktivitet",
    "\u0646\u0634\u0627\u0637\u0627 \u063a\u064a\u0631 \u0639\u0627\u062f\u064a",
    "\u062e\u0637\u0623 \u0641\u064a \u0625\u0646\u0634\u0627\u0621 \u0627\u0644\u062d\u0633\u0627\u0628",
    "kontoerstellung fehlgeschlagen", "errore durante la creazione",
)
CAPTCHA = ("arkoselabs", "funcaptcha", "acic", "hcaptcha", "recaptcha",
           "data-sitekey", "/errors/validatecaptcha", "captcha challenge")
OTP = ("otp", "verify", "verification", "best\u00e4tigen", "code eingeben",
       "enter the code", "welcome", "willkommen")


def _atomic(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(path))


def _load_stats() -> dict:
    try:
        d = json.loads(DOMAIN_STATS.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


class DomainAllocator:
    def __init__(self):
        from modules.Engine.Amazon.amazon_core import GEN_PRIORITY
        self.base = list(GEN_PRIORITY)
        self.lock = asyncio.Lock()
        self.in_use: set[str] = set()
        self.rr = 0
        self.stats = _load_stats()

    def _ordered(self) -> list[str]:
        bad = []
        good = []
        for cc in self.base:
            s = self.stats.get(cc) or {}
            n = int(s.get("tries", 0))
            f = int(s.get("fail", 0))
            if n >= 20 and f / max(1, n) > 0.8:
                bad.append(cc)
            else:
                good.append(cc)
        return good + bad

    async def acquire(self) -> str | None:
        async with self.lock:
            order = self._ordered()
            for i in range(len(order)):
                cc = order[(self.rr + i) % len(order)]
                if cc not in self.in_use:
                    self.in_use.add(cc)
                    self.rr = (self.rr + i + 1) % len(order)
                    return cc
            return None

    async def release(self, cc: str, ok: bool) -> None:
        async with self.lock:
            self.in_use.discard(cc)
            s = self.stats.setdefault(cc, {"tries": 0, "fail": 0, "ok": 0})
            s["tries"] = int(s.get("tries", 0)) + 1
            s["ok"] = int(s.get("ok", 0)) + (1 if ok else 0)
            s["fail"] = int(s.get("fail", 0)) + (0 if ok else 1)
            _atomic(DOMAIN_STATS, self.stats)


class ProxyRing:
    def __init__(self):
        from utilities.proxy import parse_proxy_lines
        items: list[str] = []
        base = APP_ROOT / "proxies" / "amazon"
        f = base / "proxybaron.txt"
        files = [f] if f.exists() else sorted(base.glob("*.txt"))
        for p in files:
            if p.name.lower() == "isp.txt":
                continue
            for line in parse_proxy_lines(p.read_text(encoding="utf-8-sig")):
                if line not in items:
                    items.append(line)
        self.items = items
        self.dead: set[str] = set()
        self.rr = random.randrange(max(1, len(items))) if items else 0
        self.lock = asyncio.Lock()

    async def acquire(self) -> str | None:
        async with self.lock:
            if not self.items:
                return None
            alive = [p for p in self.items if p not in self.dead] or self.items
            p = alive[self.rr % len(alive)]
            self.rr += 1
            return p

    async def mark_dead(self, proxy: str | None) -> None:
        async with self.lock:
            if proxy:
                self.dead.add(proxy)


def synth_register_url(cc: str, domain: str) -> str:
    from modules.Engine.Amazon.amazon_core import DOMAINS, MARKETPLACE_IDS
    locale = DOMAINS.get(cc.upper(), (domain, "EUR", "en"))[2]
    q = {
        "openid.return_to": f"https://{domain}/",
        "openid.mode": "checkid_setup",
        "openid.assoc_handle": "saflex",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "marketplaceId": MARKETPLACE_IDS.get(cc.upper(), ""),
        "language": locale.split("-")[0].lower(),
        "ref_": "nav_ya_signin",
    }
    return f"https://{domain}/ap/register?{urlencode(q)}"


def make_identity(aid: str, mail_domain: str = "mail.tm"):
    from utilities.identity import UMLAUT, IdentityGenerator
    seed = int(hashlib.sha256(aid.encode("utf-8")).hexdigest()[:8], 16)
    gen = IdentityGenerator(mail_domain=mail_domain, seed=seed)
    ident = gen.generate()
    first = str(ident.first_name).translate(UMLAUT)
    last = str(ident.last_name).translate(UMLAUT)
    local = re.sub(r"[^a-z0-9]", "", f"{first}{last}".lower())[:28]
    rng = random.Random(seed ^ 0x77)
    if rng.random() < 0.4:
        local = local[:26] + str(rng.randint(12, 89))
    ident.email = f"{local}@{mail_domain}"
    return ident, local


def classify(html: str, status: int | None) -> tuple[str, str]:
    low = (html or "").lower()
    dead_gate = ("two-step verification" in low or "zwei-schritt" in low) and \
        not re.search(r'name=["\'](?:code|otp|verificationcode|securitycode)["\']',
                      html or "", re.I)
    if status in (202, 403, 404, 503) or dead_gate:
        return "d", f"register_gate_{status or 'challenge'}"
    if any(x in low for x in CAPTCHA):
        return "b", "captcha_challenge"
    if any(x in low for x in UNUSUAL):
        return "c", "unusual_activity"
    otp_form = bool(re.search(
        r'name=["\'](?:code|otp|verificationcode|securitycode)["\']|enter the code|code eingeben',
        html or "", re.I))
    if otp_form and any(x in low for x in OTP):
        return "a", "otp_oder_erfolg"
    return "d", "keine_registrierung_moeglich"


def sitekey_from(html: str) -> str:
    m = re.search(r'data-sitekey=["\']([^"\']+)', html or "", re.I)
    if m:
        return m.group(1)
    m = re.search(r"[?&](?:sitekey|site_key|k)=([^&\"']+)", html or "", re.I)
    return m.group(1) if m else ""


def captcha_key_available(cfg) -> bool:
    keys = (cfg.captcha or {}).get("keys") or {}
    if any(v for v in keys.values() if isinstance(v, str)):
        return True
    return any(os.environ.get(k) for k in
               ("CAPSOLVER_KEY", "TWOCAPTCHA_KEY", "CAPMONSTER_KEY"))


async def sleep_timing(seconds: float) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        await asyncio.sleep(min(random.uniform(0.04, 0.18), max(0.01, end - time.monotonic())))


def _clean_duplicate_headers() -> None:
    try:
        with CSV_PATH.open(encoding="utf-8", newline="") as f:
            rows = [r for r in csv.reader(f) if r]
        if len(rows) < 3:
            return
        cleaned = [rows[0]] + [r for r in rows[1:] if r[0] != "ts"]
        if len(cleaned) == len(rows):
            return
        with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(cleaned)
    except Exception:
        pass


def append_attempt(row: dict) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    _clean_duplicate_headers()
    new = not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0
    if not new:
        try:
            with CSV_PATH.open(encoding="utf-8", newline="") as f:
                first = f.readline().strip()
            if first != ",".join(COLUMNS):
                with CSV_PATH.open(encoding="utf-8", newline="") as f:
                    old = list(csv.DictReader(f))
                alias = {"attempt_id": "tid", "submit_status": "status",
                         "proxy": "proxy(maskiert)"}
                with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=COLUMNS)
                    w.writeheader()
                    for r in old:
                        mapped = {alias.get(k, k): v for k, v in r.items()}
                        w.writerow({k: str(mapped.get(k, ""))[:300] for k in COLUMNS})
                new = True
        except Exception:
            new = True
    with CSV_PATH.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            w.writeheader()
        w.writerow({k: str(row.get(k, ""))[:300] for k in COLUMNS})


async def _otp_code(inbox, timeout: float = 0.0) -> str:
    timeout = timeout or float(os.environ.get("AMAZON_OTP_WAIT", "40"))
    from utilities.mailbox import wait_for_link
    try:
        text = await wait_for_link(inbox, timeout=timeout) or ""
    except Exception:
        return ""
    m = re.search(r"\b(\d{6,8})\b", text)
    return m.group(1) if m else text.strip()[:120]


async def run_task(tid: int, cfg, alloc: DomainAllocator, proxies: ProxyRing,
                   artifact_fn, stop_event: asyncio.Event,
                   last_error: dict, browser: bool = False) -> dict:
    from modules.Engine.Amazon.amazon_core import (
        DOMAINS, SessionStore, SkyLogger, domain_for)
    from modules.Engine.Shopify.shopify_core import Solver
    from utilities.mailbox import create_inbox
    from utilities.proxy import mask_proxy, sticky_session

    cc = await alloc.acquire()
    if not cc or stop_event.is_set():
        return {"skipped": True}
    domain = domain_for(cc)
    log = SkyLogger(site=f"Amazon{cc}")
    row = {"ts": datetime.now().isoformat(timespec="seconds"), "tid": tid,
           "domain": domain, "proxy": "", "email": "", "dauer_fill": "",
           "dauer_type": "", "klasse": "", "status": "", "error": ""}
    created = False
    try:
        for proxy_try in range(3):
            if stop_event.is_set():
                break
            base = await proxies.acquire()
            if not base:
                row["error"] = "kein_Proxy"
                break
            aid = f"{int(time.time() * 1000)}_{secrets.token_hex(4)}"
            sid = secrets.token_hex(6)
            px = sticky_session(base, sid, country=cc.lower())
            row["proxy(maskiert)"] = mask_proxy(px)
            ident, local = make_identity(aid)
            inbox = await create_inbox(cfg, local)
            email = inbox.get("address", "")
            row["email"] = email
            url = synth_register_url(cc, domain)
            log.line("Gen", "", email, f"Using synthesised register URL for {cc}",
                     "dim", tid=tid)
            d_fill = round(random.uniform(5, 12), 1)
            d_type = round(random.uniform(8, 18), 1)
            row["dauer_fill"], row["dauer_type"] = d_fill, d_type
            field_order = random.sample(["customerName", "email", "password",
                                         "passwordCheck"], 4)
            log.line("Gen", "", email,
                     f"fill={d_fill}s type={d_type}s fields={','.join(field_order)}",
                     "dim", tid=tid)
            headers = {
                "user-agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/131.0.0.0 Safari/537.36"),
                "accept-language": DOMAINS.get(cc.upper(), (domain, "EUR", "en"))[2] + ",en;q=0.8",
            }
            async with AsyncSession(impersonate="chrome", proxy=px, timeout=30,
                                    headers=headers) as s:
                await sleep_timing(d_fill)
                g = await s.get(url, timeout=25)
                row["status"] = g.status_code
                if g.status_code in (202, 403, 503):
                    row["klasse"] = "d"
                    row["error"] = f"http {g.status_code}"
                    log.line("Gen", "", email,
                             f"Klasse d: {g.status_code}, Proxy verworfen", "err", tid=tid)
                    await proxies.mark_dead(base)
                    last_error["text"] = f"{cc} klasse d http {g.status_code}"
                    continue
                values = {"customerName": ident.full_name, "email": email,
                          "password": ident.password,
                          "passwordCheck": ident.password}
                data = {k: values[k] for k in field_order}
                data["action"] = "register"
                await sleep_timing(d_type)
                r = await s.post(url, data=data, timeout=30)
                html = r.text or ""
                row["status"] = r.status_code
                klasse, detail = classify(html, r.status_code)
                row["klasse"], row["error"] = klasse, detail
                captcha_rounds = 0
                unusual_retries = 0
                for _ in range(8):
                    if klasse == "c":
                        if unusual_retries >= 6:
                            row["error"] = "unusual_activity_nach_6_retries"
                            break
                        unusual_retries += 1
                        log.line("Gen", "", email,
                                 f"Klasse c retry {unusual_retries}/6", "warn", tid=tid)
                        await asyncio.sleep(random.uniform(3, 8))
                        r = await s.post(url, data=data, timeout=30)
                        html = r.text or ""
                        klasse, detail = classify(html, r.status_code)
                        row["klasse"], row["status"], row["error"] = klasse, r.status_code, detail
                        continue
                    if klasse != "b":
                        break
                    key = sitekey_from(html)
                    solver = Solver(cfg)
                    if not solver.ok:
                        if (cfg.captcha or {}).get("noCaptchaOnly"):
                            row["error"] = "noCaptchaOnly_ohne_Key"
                        break
                    if not key or captcha_rounds >= 2:
                        row["error"] = "captcha_ohne_sitekey_oder_runden"
                        break
                    try:
                        kind = "funcaptcha" if any(
                            x in html.lower() for x in ("arkose", "funcaptcha", "acic")) \
                            else ("hcaptcha" if "hcaptcha" in html.lower() else "recaptcha")
                        token = await solver.solve(kind, key, str(r.url), px)
                    except Exception:
                        token = None
                    if not token:
                        row["error"] = "captcha_token_fehlt"
                        break
                    captcha_rounds += 1
                    log.line("Gen", "", email, f"Captcha-Runde {captcha_rounds}/2",
                             "warn", tid=tid)
                    data = dict(data)
                    data.update({"captcha-token": token,
                                 "g-recaptcha-response": token,
                                 "h-captcha-response": token})
                    await asyncio.sleep(random.uniform(1, 3))
                    r = await s.post(url, data=data, timeout=30)
                    html = r.text or ""
                    klasse, detail = classify(html, r.status_code)
                    row["klasse"], row["status"], row["error"] = klasse, r.status_code, detail
                if klasse == "d" and row["status"] in (202, 403, 503):
                    await proxies.mark_dead(base)
                    last_error["text"] = f"{cc} klasse d http {row['status']}"
                    continue
                ok = klasse == "a" and "unusual" not in row["error"] \
                    and "captcha" not in row["error"]
                if ok:
                    code = await _otp_code(inbox)
                    if code:
                        d = dict(data)
                        d["code"] = code
                        await asyncio.sleep(random.uniform(1, 3))
                        r = await s.post(url, data=d, timeout=30)
                        html = r.text or ""
                        row["status"] = r.status_code
                        klasse, detail = classify(html, r.status_code)
                        row["klasse"], row["error"] = klasse, detail
                        ok = klasse == "a" and "captcha" not in detail
                    else:
                        ok = bool(re.search(r"welcome|willkommen|created|erfolgreich", html, re.I))
                    if ok:
                        try:
                            cookies = [{"name": k, "value": v, "domain": domain, "path": "/"}
                                       for k, v in dict(s.cookies).items()]
                        except Exception:
                            cookies = []
                        acc = {"email": email, "password": ident.password,
                               "first_name": ident.first_name,
                               "last_name": ident.last_name, "domain": domain,
                               "proxy(maskiert)": row["proxy(maskiert)"],
                               "proxy": row["proxy(maskiert)"], "proxy_session": sid,
                               "verify_link": "", "cookies": len(cookies)}
                        await SessionStore("amazon").save_cookies(email, cookies)
                        artifact_fn(acc)
                        created = True
                        log.line("Gen", "", email,
                                 "Account generated, no PVA needed!", "ok", tid=tid)
                        break
                last_error["text"] = f"{cc} klasse {klasse}: {row['error']}"
                log.line("Gen", "", email,
                         f"Klasse {klasse or '?'}: {row['error']}", "err", tid=tid)
                break
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"[:250]
        row["klasse"] = row["klasse"] or "d"
        last_error["text"] = row["error"]
        log.line("Gen", "", row["email"], row["error"], "err", tid=tid)
    finally:
        append_attempt(row)
        await alloc.release(cc, created)
    return {"cc": cc, "created": created, "klasse": row["klasse"], "row": row}


async def run_burst(tasks: int, threads: int = 5, artifact_fn=None,
                    browser: bool = False) -> dict:
    from modules.Engine.Shopify.shopify_core import Settings, Solver  # noqa: F401
    if artifact_fn is None:
        from modules.Generators.Amazon.AmazonAIO import AmazonAIOModule
        artifact_fn = AmazonAIOModule()._write_artifact
    cfg = Settings.load()
    alloc = DomainAllocator()
    proxies = ProxyRing()
    sem = asyncio.Semaphore(max(1, min(30, threads)))
    stop = asyncio.Event()
    last_error: dict = {}
    results: list[dict] = []

    async def one(i: int):
        async with sem:
            if browser:
                from modules.Engine.Amazon.amazon_browser_gen import run_attempt
                from modules.Engine.Amazon.amazon_core import SkyLogger
                blog = SkyLogger(site="AmazonNL")
                r, acc = await run_attempt("NL", blog, cfg, artifact_fn,
                                           warm_seconds=0, show=False)
                if acc:
                    artifact_fn(acc)
                res = {"skipped": False, "cc": "NL", "created": bool(acc),
                       "klasse": "browser", "row": r}
            else:
                res = await run_task(i % threads + 1, cfg, alloc, proxies,
                                     artifact_fn, stop, last_error)
            results.append(res)
            if not res.get("skipped"):
                if res.get("created"):
                    count["misses"] = 0
                else:
                    count["misses"] += 1
                    if count["misses"] >= 20:
                        stop.set()

    count = {"misses": 0}
    await asyncio.gather(*(one(i) for i in range(tasks)))
    real = [r for r in results if not r.get("skipped")]
    out = {"tasks": len(real), "created": sum(1 for r in real if r.get("created")),
           "classes": {}, "domains": sorted({r.get("cc", "") for r in real})}
    for r in real:
        k = r.get("klasse") or "?"
        out["classes"][k] = out["classes"].get(k, 0) + 1
    if count["misses"] >= 20:
        out["abort"] = last_error.get("text", "20 Versuche ohne Erfolg")
    return out


async def run_single(cc: str, log, cfg, artifact_fn) -> dict | None:
    alloc = DomainAllocator()
    proxies = ProxyRing()
    res = await run_task(1, cfg, alloc, proxies, artifact_fn, asyncio.Event(), {})
    if res.get("created"):
        return res.get("row")
    return None
