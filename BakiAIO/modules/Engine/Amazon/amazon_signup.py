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
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlencode

from curl_cffi.requests import AsyncSession

from modules.Engine.Amazon.amazon_core import GEN_PRIORITY, GEN_TIERS
from utilities.root import APP_ROOT

CSV_PATH = APP_ROOT / "var" / "amazon_gen_attempts.csv"
DOMAIN_STATS = APP_ROOT / "var" / "amazon_domains.json"
DAILY_STATS = APP_ROOT / "var" / "amazon_daily.json"
PROXY_FILE = APP_ROOT / "proxies" / "amazon" / "proxybaron.txt"
USED_PROXIES = APP_ROOT / "var" / "amazon_used_proxies.txt"
COLUMNS = ["ts", "tid", "domain", "proxy(maskiert)", "email", "dauer_fill",
           "dauer_type", "klasse", "status"]

CAPTCHA = ("arkoselabs", "funcaptcha", "acic", "hcaptcha", "recaptcha",
           "data-sitekey", "/errors/validatecaptcha", "captcha")
UNUSUAL = (
    "unusual activity", "ongewone activiteit", "nietypowa aktywność",
    "nietypowa aktywno", "ovanlig aktivitet",
    "\u0646\u0634\u0627\u0637\u0627 \u063a\u064a\u0631 \u0639\u0627\u062f\u064a",
    "\u062e\u0637\u0623 \u0641\u064a \u0625\u0646\u0634\u0627\u0621 \u0627\u0644\u062d\u0633\u0627\u0628",
    "kontoerstellung fehlgeschlagen", "errore durante la creazione",
)
OTP = ("otp", "verify", "verification", "best\u00e4tigen", "code eingeben",
       "enter the code", "welcome", "willkommen")
TIERS = GEN_TIERS
STAT_FIELDS = ("attempts", "clean", "otp", "success", "captcha")


def _delay(seconds: float) -> float:
    return max(0.0, seconds * float(os.environ.get("AMAZON_DELAY_SCALE", "1")))


async def _nap(seconds: float) -> None:
    scaled = _delay(seconds)
    if scaled <= 0:
        await asyncio.sleep(0)
        return
    await asyncio.sleep(scaled)


def _atomic(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(path))


def _load_json(path: Path) -> dict:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _norm_stats(raw: dict | None) -> dict:
    raw = raw or {}
    out = {}
    for cc in GEN_PRIORITY:
        s = raw.get(cc) or {}
        attempts = int(s.get("attempts") or s.get("tries") or 0)
        out[cc] = {
            "attempts": attempts,
            "clean": int(s.get("clean") or s.get("ok") or 0),
            "otp": int(s.get("otp") or 0),
            "success": int(s.get("success") or s.get("ok") or 0),
            "captcha": int(s.get("captcha") or 0),
        }
    return out


class DomainAllocator:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.in_use: set[str] = set()
        self.rr = 0
        self.stats = _norm_stats(_load_json(DOMAIN_STATS))
        self.last_end: dict[str, float] = {}
        self.gap = {cc: _delay(random.uniform(2, 4)) for cc in GEN_PRIORITY}
        self.tier = {cc: i for i, tier in enumerate(TIERS) for cc in tier}
        self.base_index = {cc: i for i, cc in enumerate(GEN_PRIORITY)}

    def _ordered(self) -> list[str]:
        def rank(cc: str):
            s = self.stats.get(cc) or {}
            attempts = int(s.get("attempts", 0))
            rate = float(s.get("clean", 0)) / attempts if attempts else 1.0
            return (self.tier.get(cc, 2), -rate, self.base_index.get(cc, 99))

        return sorted(GEN_PRIORITY, key=rank)

    async def acquire(self) -> str | None:
        while True:
            wait = 0.0
            async with self.lock:
                now = time.monotonic()
                order = self._ordered()
                for i in range(len(order)):
                    cc = order[(self.rr + i) % len(order)]
                    if cc in self.in_use:
                        continue
                    last = self.last_end.get(cc)
                    need = self.gap.get(cc, 2.0)
                    if last is not None and now - last < need:
                        wait = max(wait, need - (now - last))
                        continue
                    self.in_use.add(cc)
                    self.rr = (self.rr + i + 1) % len(order)
                    return cc
                wait = wait or 0.1
            await asyncio.sleep(wait)

    async def release(self, cc: str, outcome: dict | None = None) -> None:
        async with self.lock:
            self.in_use.discard(cc)
            self.last_end[cc] = time.monotonic()
            if outcome:
                s = self.stats.setdefault(cc, {k: 0 for k in STAT_FIELDS})
                for key in STAT_FIELDS:
                    s[key] = int(s.get(key, 0)) + int(bool(outcome.get(key)))
                _atomic(DOMAIN_STATS, self.stats)


class OneShotProxyPool:
    def __init__(self, path: Path | None = None, used_path: Path | None = None):
        from utilities.proxy import parse_proxy_lines
        self.path = Path(path) if path else Path(PROXY_FILE)
        self.used_path = Path(used_path) if used_path else Path(USED_PROXIES)
        items: list[str] = []
        source = self.path if self.path.exists() else Path(PROXY_FILE)
        if source.exists():
            for line in parse_proxy_lines(source.read_text(encoding="utf-8-sig")):
                if line not in items:
                    items.append(line)
        self.items = items
        self.index = {p: i for i, p in enumerate(items)}
        self.used = self._read_used()
        self.free = [p for p in items if p not in self.used]
        self.lock = asyncio.Lock()
        self.exhausted = False

    def _read_used(self) -> set[str]:
        try:
            return {ln.strip() for ln in self.used_path.read_text(
                encoding="utf-8-sig").splitlines() if ln.strip()}
        except Exception:
            return set()

    async def reserve(self, tid: int, log):
        async with self.lock:
            used = self._read_used()
            while self.free and self.free[0] in used:
                self.free.pop(0)
            if not self.free:
                self.exhausted = True
                log.line("Gen", "", "", "Pool erschoepft", "err", tid=tid)
                return None
            proxy = self.free.pop(0)
            if proxy in used:
                self.exhausted = True
                log.line("Gen", "", "", "Pool erschoepft", "err", tid=tid)
                return None
            self.used_path.parent.mkdir(parents=True, exist_ok=True)
            with self.used_path.open("a", encoding="utf-8", newline="\n") as f:
                f.write(proxy + "\n")
                f.flush()
                os.fsync(f.fileno())
            self.used.add(proxy)
            idx = self.index.get(proxy, -1)
            remaining = len(self.free)
            log.line("Gen", "", "", f"proxy #{idx} reserviert, {remaining} frei",
                     "dim", tid=tid)
            return proxy, idx, remaining


class DailyCounter:
    def __init__(self):
        self.lock = asyncio.Lock()
        today = date.today().isoformat()
        raw = _load_json(DAILY_STATS)
        self.data = {"day": today, **{k: 0 for k in STAT_FIELDS}}
        if raw.get("day") == today:
            for key in STAT_FIELDS:
                self.data[key] = int(raw.get(key, 0))

    async def add(self, outcome: dict) -> None:
        async with self.lock:
            for key in STAT_FIELDS:
                self.data[key] += int(bool(outcome.get(key)))
            _atomic(DAILY_STATS, self.data)

    def snapshot(self) -> dict:
        d = dict(self.data)
        attempts = max(1, int(d.get("attempts", 0)))
        d["quote"] = f"{100.0 * d.get('success', 0) / attempts:.1f}%"
        return d


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
    if any(x in low for x in CAPTCHA):
        return "b", "captcha_challenge"
    if any(x in low for x in UNUSUAL):
        return "c", "unusual_activity"
    if status in (202, 403, 503):
        return "d", f"proxy_http_{status}"
    dead_gate = ("two-step verification" in low or "zwei-schritt" in low) and \
        not re.search(r'name=["\'](?:code|otp|verificationcode|securitycode)["\']',
                      html or "", re.I)
    if status == 404 or dead_gate:
        return "d", "register_gate"
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


def no_captcha_only(cfg) -> bool:
    amazon_conf = getattr(cfg, "amazon", None) or {}
    if "noCaptchaOnly" in amazon_conf:
        return bool(amazon_conf.get("noCaptchaOnly"))
    captcha_conf = getattr(cfg, "captcha", None) or {}
    if "noCaptchaOnly" in captcha_conf:
        return bool(captcha_conf.get("noCaptchaOnly"))
    return True


async def sleep_timing(seconds: float) -> None:
    end = time.monotonic() + _delay(seconds)
    while time.monotonic() < end:
        await _nap(min(random.uniform(0.04, 0.18), max(0.0, end - time.monotonic())))


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
                        if not mapped.get("status"):
                            mapped["status"] = mapped.get("error", "")
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


async def run_task(tid: int, cfg, alloc: DomainAllocator, proxies: OneShotProxyPool,
                   artifact_fn, stop_event: asyncio.Event, daily: DailyCounter,
                   last_error: dict) -> dict:
    from modules.Engine.Amazon.amazon_core import (
        DOMAINS, SessionStore, SkyLogger, domain_for)
    from utilities.mailbox import create_inbox
    from utilities.proxy import mask_proxy, sticky_session

    cc = await alloc.acquire()
    if not cc or stop_event.is_set():
        return {"skipped": True}

    domain = domain_for(cc)
    log = SkyLogger(site=f"Amazon{cc}")
    row = {"ts": datetime.now().isoformat(timespec="seconds"), "tid": tid,
           "domain": domain, "proxy(maskiert)": "", "email": "",
           "dauer_fill": "", "dauer_type": "", "klasse": "", "status": ""}
    outcome = {"attempts": 1, "clean": 0, "otp": 0, "success": 0, "captcha": 0}
    counted = False
    abort_task = False
    try:
        for proxy_try in range(3):
            if stop_event.is_set():
                break
            reserved = await proxies.reserve(tid, log)
            if not reserved:
                stop_event.set()
                last_error["text"] = "Pool erschoepft"
                break
            base, idx, remaining = reserved
            counted = True
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
            field_order = random.sample(["customerName", "email", "password",
                                         "passwordCheck"], 4)
            values = {"customerName": ident.full_name, "email": email,
                      "password": ident.password,
                      "passwordCheck": ident.password}
            data = {k: values[k] for k in field_order}
            data["action"] = "register"
            char_count = sum(len(str(v)) for v in values.values())
            d_type = round(min(18.0, max(8.0, char_count * random.uniform(0.04, 0.18))), 1)
            row["dauer_fill"], row["dauer_type"] = d_fill, d_type
            pre = round(random.uniform(1, 3), 1)
            log.line("Gen", "", email,
                     f"fill={d_fill}s type={d_type}s pre={pre}s "
                     f"fields={','.join(field_order)}", "dim", tid=tid)

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
                if g.status_code in (202, 403, 503):
                    row["klasse"], row["status"] = "d", f"proxy_http_{g.status_code}"
                    log.line("Gen", "", email,
                             f"Klasse d: {g.status_code}, Proxy #{idx} verworfen",
                             "warn", tid=tid)
                    last_error["text"] = f"{cc} klasse d http {g.status_code}"
                    continue

                await sleep_timing(d_type)
                await _nap(pre)
                r = await s.post(url, data=data, timeout=30)
                html = r.text or ""
                row["status"] = str(r.status_code)
                klasse, detail = classify(html, r.status_code)
                row["klasse"] = klasse

                if klasse == "b":
                    outcome["captcha"] = 1
                    row["status"] = "captcha_challenge"
                    log.line("Gen", "", email,
                             "Captcha challenge required — aborting (noCaptchaOnly)",
                             "err", tid=tid)
                    if no_captcha_only(cfg):
                        row["status"] = "captcha_abort"
                        log.line("Gen", "", email,
                                 "captcha_abort: Task verworfen, naechster Task startet",
                                 "warn", tid=tid)
                        try:
                            s.cookies.clear()
                        except Exception:
                            pass
                        abort_task = True
                    else:
                        from modules.Engine.Shopify.shopify_core import Solver
                        solver = Solver(cfg)
                        key = sitekey_from(html)
                        token = ""
                        if solver.ok and key:
                            kind = "funcaptcha" if any(
                                x in html.lower() for x in ("arkose", "funcaptcha", "acic")) \
                                else ("hcaptcha" if "hcaptcha" in html.lower() else "recaptcha")
                            try:
                                token = await solver.solve(kind, key, str(r.url), px)
                            except Exception:
                                token = ""
                        if not token:
                            row["status"] = "captcha_abort"
                            abort_task = True
                            try:
                                s.cookies.clear()
                            except Exception:
                                pass
                        else:
                            data = dict(data)
                            data.update({"captcha-token": token,
                                         "g-recaptcha-response": token,
                                         "h-captcha-response": token})
                            await _nap(random.uniform(1, 3))
                            r = await s.post(url, data=data, timeout=30)
                            html = r.text or ""
                            row["status"] = str(r.status_code)
                            klasse, detail = classify(html, r.status_code)
                            row["klasse"] = klasse
                    if abort_task:
                        last_error["text"] = f"{cc} captcha_abort"
                        break

                unusual_retries = 0
                while klasse == "c" and unusual_retries < 6:
                    unusual_retries += 1
                    log.line("Gen", "", email,
                             f"Klasse c retry {unusual_retries}/6", "warn", tid=tid)
                    await _nap(random.uniform(3, 8))
                    r = await s.post(url, data=data, timeout=30)
                    html = r.text or ""
                    row["status"] = str(r.status_code)
                    klasse, detail = classify(html, r.status_code)
                    row["klasse"] = klasse
                if klasse == "c":
                    row["status"] = "failed"
                    last_error["text"] = f"{cc} unusual_activity nach 6 Retries"
                    break

                if klasse == "d" and row["status"] in ("202", "403", "503"):
                    log.line("Gen", "", email,
                             f"Klasse d: {row['status']}, Proxy #{idx} verworfen",
                             "warn", tid=tid)
                    last_error["text"] = f"{cc} klasse d http {row['status']}"
                    continue

                if klasse == "a":
                    outcome["otp"] = 1
                    code = await _otp_code(inbox)
                    if code:
                        d = dict(data)
                        d["code"] = code
                        await _nap(random.uniform(1, 3))
                        r = await s.post(url, data=d, timeout=30)
                        html = r.text or ""
                        row["status"] = str(r.status_code)
                        klasse, detail = classify(html, r.status_code)
                        row["klasse"] = klasse
                        ok = klasse == "a"
                    else:
                        ok = bool(re.search(
                            r"welcome|willkommen|created|erfolgreich", html, re.I))
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
                        outcome["clean"] = 1
                        outcome["success"] = 1
                        row["status"] = "success"
                        log.line("Gen", "", email,
                                 "Account generated, no PVA needed!", "ok", tid=tid)
                        break
                row["status"] = row["status"] or "failed"
                if row["status"] not in ("captcha_abort",):
                    row["status"] = "failed"
                last_error["text"] = f"{cc} klasse {klasse or '?'}: {detail}"
                log.line("Gen", "", email,
                         f"Klasse {klasse or '?'}: {detail}", "err", tid=tid)
                break
    except Exception as exc:
        row["klasse"] = row["klasse"] or "d"
        row["status"] = "failed"
        last_error["text"] = f"{type(exc).__name__}: {exc}"[:250]
        log.line("Gen", "", row["email"], last_error["text"], "err", tid=tid)
    finally:
        if counted:
            append_attempt(row)
            if not outcome["captcha"]:
                outcome["clean"] = 1
            await daily.add(outcome)
        await alloc.release(cc, outcome if counted else None)
    return {"skipped": not counted, "cc": cc, "created": bool(outcome["success"]),
            "klasse": row["klasse"], "status": row["status"],
            "clean": bool(outcome["clean"]), "row": row}


async def run_burst(tasks: int, threads: int = 5, artifact_fn=None) -> dict:
    from modules.Engine.Shopify.shopify_core import Settings
    if artifact_fn is None:
        from modules.Generators.Amazon.AmazonAIO import AmazonAIOModule
        artifact_fn = AmazonAIOModule()._write_artifact
    cfg = Settings.load()
    alloc = DomainAllocator()
    proxies = OneShotProxyPool()
    daily = DailyCounter()
    stop = asyncio.Event()
    last_error: dict = {}
    results: list[dict] = []
    next_task = 0
    miss = 0
    take_lock = asyncio.Lock()

    async def worker(tid: int):
        nonlocal next_task, miss
        while not stop.is_set():
            async with take_lock:
                if next_task >= tasks or stop.is_set():
                    return
                next_task += 1
            res = await run_task(tid, cfg, alloc, proxies, artifact_fn,
                                 stop, daily, last_error)
            results.append(res)
            if res.get("skipped"):
                continue
            if res.get("created"):
                miss = 0
            else:
                miss += 1
                if miss >= 60:
                    stop.set()
                    last_error.setdefault("text", "60 Versuche ohne Erfolg")
            if proxies.exhausted:
                stop.set()

    await asyncio.gather(*(worker(i + 1) for i in range(max(1, min(30, threads)))))
    real = [r for r in results if not r.get("skipped")]
    out = {"tasks": len(real),
           "created": sum(1 for r in real if r.get("created")),
           "captcha": sum(1 for r in real if r.get("klasse") == "b"),
           "clean": sum(1 for r in real if r.get("clean")),
           "classes": {}, "domains": sorted({r.get("cc", "") for r in real}),
           "daily": daily.snapshot()}
    for r in real:
        k = r.get("status") or r.get("klasse") or "?"
        out["classes"][k] = out["classes"].get(k, 0) + 1
    if stop.is_set():
        out["abort"] = last_error.get("text", "Pool erschoepft")
    return out


async def run_single(cc: str, log, cfg, artifact_fn) -> dict | None:
    alloc = DomainAllocator()
    proxies = OneShotProxyPool()
    daily = DailyCounter()
    res = await run_task(1, cfg, alloc, proxies, artifact_fn,
                         asyncio.Event(), daily, {})
    if res.get("created"):
        return res.get("row")
    return None
