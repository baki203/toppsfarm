from __future__ import annotations

import asyncio
import csv
import hashlib
import random
import re
import secrets
import shutil
import time
from datetime import datetime
from pathlib import Path

from curl_cffi.requests import AsyncSession

from utilities.browser import Browser
from utilities.human import Human
from utilities.identity import UMLAUT, IdentityGenerator
from utilities.proxy import (is_proxy_failure, mask_proxy, normalize_proxy,
                             proxy_playwright, sticky_session)
from utilities.root import APP_ROOT

COLUMNS = ["attempt_id", "ts", "domain", "proxy", "session_id", "catchall_addr",
           "email", "warmup_steps", "seconds", "submit_status", "error",
           "captcha", "created"]
CSV_PATH = APP_ROOT / "var" / "amazon_gen_attempts.csv"
PROFILE_BASE = APP_ROOT / "var" / "browser-amazon-gen"

LOCALES = {
    "NL": ("nl-NL", "Europe/Amsterdam"), "BE": ("nl-BE", "Europe/Brussels"),
    "IT": ("it-IT", "Europe/Rome"), "PL": ("pl-PL", "Europe/Warsaw"),
    "IE": ("en-IE", "Europe/Dublin"), "DE": ("de-DE", "Europe/Berlin"),
    "GB": ("en-GB", "Europe/London"), "FR": ("fr-FR", "Europe/Paris"),
    "ES": ("es-ES", "Europe/Madrid"), "SE": ("sv-SE", "Europe/Stockholm"),
}
VIEWPORTS = [{"width": 1366, "height": 768}, {"width": 1440, "height": 900},
             {"width": 1536, "height": 864}]
UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
]
SEARCH_TERMS = ["pokemon karten", "pokemon tcg booster", "sammelkarten pokemon"]


class ProxySet:
    def __init__(self, module: str = "amazon"):
        from utilities.proxy import parse_proxy_lines
        items: list[str] = []
        base = APP_ROOT / "proxies" / module
        files = [base / "proxybaron.txt"] if (base / "proxybaron.txt").exists() else []
        if not files:
            files = sorted(base.glob("*.txt"))
        for f in files:
            if f.name.lower() == "isp.txt":
                continue
            for line in parse_proxy_lines(f.read_text(encoding="utf-8-sig")):
                if line not in items:
                    items.append(line)
        self.items = items
        self.dead: set[str] = set()
        self.rr = random.randrange(max(1, len(items))) if items else 0

    async def acquire(self) -> str | None:
        if not self.items:
            return None
        alive = [p for p in self.items if p not in self.dead] or self.items
        p = alive[self.rr % len(alive)]
        self.rr += 1
        return p

    def mark_dead(self, proxy: str | None) -> None:
        if proxy:
            self.dead.add(proxy)


def attempt_id() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S") + "_" + secrets.token_hex(4)


def seed_for(aid: str) -> int:
    return int(hashlib.sha256(aid.encode("utf-8")).hexdigest()[:8], 16)


def profile_for(cc: str, aid: str, show: bool = False, new_headless: bool = False) -> dict:
    rng = random.Random(seed_for(aid) ^ 0x5A17)
    locale, tz = LOCALES.get(cc.upper(), ("de-DE", "Europe/Berlin"))
    return {"locale": locale, "timezone_id": tz,
            "viewport": dict(rng.choice(VIEWPORTS)),
            "user_agent": rng.choice(UAS), "seed": seed_for(aid) ^ 0xC0FFEE,
            "channel": "chrome", "headless": bool(show),
            "args": ["--headless=new"] if new_headless else [],
            "user_data_dir": str(PROFILE_BASE / aid)}


async def exit_country(proxy: str) -> str:
    try:
        async with AsyncSession(proxy=proxy, timeout=15) as s:
            r = await s.get("https://ipapi.co/json/", timeout=15)
            if r.status_code == 200:
                return str((r.json() or {}).get("country_code") or "").upper()
    except Exception:
        pass
    try:
        async with AsyncSession(proxy=proxy, timeout=15) as s:
            r = await s.get("http://ip-api.com/json/?fields=countryCode", timeout=15)
            if r.status_code == 200:
                return str((r.json() or {}).get("countryCode") or "").upper()
    except Exception:
        pass
    return ""


async def pick_proxy(pool: ProxySet, cc: str, log, used: set[str]):
    for _ in range(max(1, len(pool.items) * 2)):
        base = await pool.acquire()
        if not base or base in used:
            continue
        used.add(base)
        sid = secrets.token_hex(6)
        px = sticky_session(base, sid, country=cc.lower())
        country = await exit_country(px)
        if country == cc.upper():
            return px, base, sid, country
        log.line("Gen", "", "", f"Proxy verworfen: exit={country or '?'} "
                                f"erwartet={cc.upper()} {mask_proxy(px)}", "warn")
    return None, None, "", ""


def make_identity(aid: str, mail_domain: str):
    gen = IdentityGenerator(mail_domain=mail_domain, seed=seed_for(aid))
    ident = gen.generate()
    first = str(ident.first_name).translate(UMLAUT)
    last = str(ident.last_name).translate(UMLAUT)
    local = re.sub(r"[^a-z0-9]", "", f"{first}{last}".lower())
    if not local:
        local = "shopper" + secrets.token_hex(3)
    rng = random.Random(seed_for(aid) ^ 0x11)
    if rng.random() < 0.4:
        local += str(rng.randint(12, 89))
    ident.email = f"{local[:28]}@{mail_domain}"
    return ident, local[:28]


async def goto(page, url: str, human: Human) -> None:
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    try:
        await page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass
    await human.pause(1.1, 3.2)


async def accept_cookies(page, human: Human) -> bool:
    selects = ["#sp-cc-accept", "input[data-cel-widget='sp-cc-accept']",
               "button:has-text('Alle akzeptieren')", "button:has-text('Akzeptieren')",
               "button:has-text('Alle Cookies akzeptieren')",
               "button:has-text('Accept all')", "input[value*='Akzeptieren']"]
    for sel in selects:
        try:
            loc = page.locator(sel).first
            if await loc.count() and await loc.is_visible():
                await human.pause(0.6, 2.1)
                if await human.click(page, loc):
                    await human.pause(0.8, 2.0)
                    return True
        except Exception:
            continue
    return False


async def _visible(page, selectors: list[str]):
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if await loc.count() and await loc.is_visible():
                return loc
        except Exception:
            continue
    return None


async def warmup(page, human: Human, cc: str, domain: str, log,
                 seconds: int) -> int:
    rng = random.Random(seed_for(domain) ^ int(time.time()))
    steps = 0
    await goto(page, f"https://{domain}/", human)
    await accept_cookies(page, human)
    steps += 1
    nav = await _visible(page, ["#nav-link-accountList", "#nav-subnav a", "a[data-nav-role='signin']"])
    if nav:
        try:
            box = await nav.bounding_box()
            if box:
                await human.move_to(page, box["x"] + box["width"] / 2,
                                    box["y"] + box["height"] / 2)
        except Exception:
            pass
    end = time.monotonic() + seconds
    cart_filled = False
    while time.monotonic() < end:
        choice = rng.choice(["category", "search", "product", "scroll", "pause", "cart"])
        log.line("Gen", "", "", f"warmup {choice} ({int(end - time.monotonic())}s)", "dim")
        if choice == "category":
            links = page.locator("#nav-subnav a, a[href*='/s?'], a[href*='/b/?']")
            n = await links.count()
            if n:
                await human.click(page, links.nth(rng.randrange(min(n, 12))))
                await human.pause(2, 6)
                steps += 1
        elif choice == "search":
            box = await _visible(page, ["#twotabsearchtextbox", "input[name='k']"])
            if box:
                await human.type_slow(page, box, rng.choice(SEARCH_TERMS))
                await page.keyboard.press("Enter")
                await human.pause(2, 7)
                steps += 1
        elif choice == "product" or choice == "cart":
            plinks = page.locator("div[data-component-type='s-search-result'] h2 a, a.s-link-style")
            n = await plinks.count()
            if n:
                await human.click(page, plinks.nth(rng.randrange(min(n, 8))))
                await human.pause(2, 6)
                steps += 1
                await human.scroll_bursts(page, 3)
                if not cart_filled:
                    btn = await _visible(page, ["#add-to-cart-button", "input[value*='Warenkorb']"])
                    if btn and await human.click(page, btn):
                        cart_filled = True
                        steps += 1
                        await human.pause(2, 5)
            await goto(page, f"https://{domain}/", human)
            await accept_cookies(page, human)
        elif choice == "scroll":
            await human.scroll_bursts(page, rng.randint(3, 6))
            steps += 1
        else:
            await human.pause(2, 9)
    await human.pause(20, 40)
    steps += 1
    await goto(page, f"https://{domain}/", human)
    await accept_cookies(page, human)
    steps += 1
    log.line("Gen", "", "", f"warmup {steps} Schritte, {seconds}s", "dim")
    return steps


async def checkout_signup(page, human: Human, log) -> bool:
    cart = await _visible(page, ["#nav-cart", "a[href*='/gp/cart/view.html']"])
    if cart and not await human.click(page, cart):
        return False
    await human.pause(2, 6)
    go = await _visible(page, ["#checkoutAllSubmit-left",
                               "input[name='proceedToRetailCheckout']",
                               "a[href*='/gp/checkout']",
                               "button:has-text('Zur Kasse')",
                               "button:has-text('Weiter zur Kasse')"])
    if not go or not await human.click(page, go):
        return False
    await human.pause(3, 8)
    create = await _visible(page, ["#createNewAccountSubmit",
                                   "input[value*='Neues Konto']",
                                   "button:has-text('Neues Konto erstellen')",
                                   "a:has-text('Neues Konto erstellen')",
                                   "input[value*='Create a new account']"])
    if not create or not await human.click(page, create):
        return False
    await human.pause(2, 5)
    log.line("Gen", "", "", "Checkout-Signup erreicht", "dim")
    return True


async def fallback_signup(page, human: Human, domain: str, email: str, log) -> bool:
    await goto(page, f"https://{domain}/", human)
    await accept_cookies(page, human)
    acct = await _visible(page, ["#nav-link-accountList", "a[data-nav-role='signin']"])
    if not acct or not await human.click(page, acct):
        return False
    await human.pause(2, 6)
    mail = await _visible(page, ["#ap_email_login", "#ap_email", "input[name='email']"])
    if not mail:
        return False
    await human.type_slow(page, mail, email)
    cont = await _visible(page, ["#continue", "input#continue", "button[type='submit']"])
    if not cont or not await human.click(page, cont):
        return False
    await human.pause(2, 7)
    create = await _visible(page, ["#intent-confirmation-form input[type='submit']",
                                   "#intention-submit-button",
                                   "button:has-text('Erstelle dein Konto')",
                                   "button:has-text('Create your account')",
                                   "input[type='submit']"])
    if not create or not await human.click(page, create):
        return False
    await human.pause(2, 6)
    if "/ax/claim/intent" in page.url:
        again = await _visible(page, ["input[type='submit']", "#continue",
                                      "button[type='submit']"])
        if again:
            await human.click(page, again)
            await human.pause(2, 5)
    log.line("Gen", "", "", "Fallback-Signup erreicht", "dim")
    return True


async def fill_form(page, human: Human, ident) -> bool:
    pairs = [
        (["#ap_customer_name", "input[name='customerName']", "#name"], ident.full_name),
        (["#ap_email", "input[name='email']"], ident.email),
        (["#ap_password", "input[name='password']"], ident.password),
        (["#ap_password_check", "input[name='passwordCheck']"], ident.password),
    ]
    filled = 0
    for selectors, value in pairs:
        loc = await _visible(page, selectors)
        if loc:
            await human.type_slow(page, loc, value)
            filled += 1
            await human.pause(0.4, 1.2)
    return filled >= 2


async def submit_form(page, human: Human) -> None:
    btn = await _visible(page, ["#continue", "input#continue",
                                "input[id*='createAccountSubmit']",
                                "button[type='submit']", "input[type='submit']"])
    if btn:
        await human.pause(1, 3)
        await human.click(page, btn)


async def detect_captcha(page) -> tuple[str, str, bool]:
    text = (await page.content()).lower()
    flagged = any(x in text for x in ("unusual activity", "ongewone activiteit",
                                      "attività insolita", "actividad inusual",
                                      "/errors/validatecaptcha"))
    kind, sitekey = "", ""
    for sel in ("iframe[src*='arkoselabs']", "iframe[src*='funcaptcha']",
                "iframe[src*='hcaptcha']", "iframe[src*='recaptcha']",
                "div[data-sitekey]", ".g-recaptcha", ".h-captcha"):
        try:
            loc = page.locator(sel).first
            if not await loc.count():
                continue
            src = (await loc.get_attribute("src")) or ""
            key = (await loc.get_attribute("data-sitekey")) or ""
            m = re.search(r"[?&](?:sitekey|site_key|k)=([^&]+)", src)
            sitekey = key or (m.group(1) if m else "")
            if "hcaptcha" in (sel + src).lower():
                kind = "hcaptcha"
            elif "recaptcha" in (sel + src).lower():
                kind = "recaptcha"
            elif "arkose" in (sel + src).lower() or "funcaptcha" in (sel + src).lower():
                kind = "arkose"
            if kind:
                break
        except Exception:
            continue
    return kind, sitekey, flagged


async def inject_token(page, token: str) -> bool:
    ok = False
    for sel in ("textarea[name='h-captcha-response']",
                "textarea[name='g-recaptcha-response']",
                "input[name*='captcha']", "#captchacharacters"):
        try:
            loc = page.locator(sel).first
            if await loc.count():
                await loc.evaluate(
                    "(e,v)=>{e.value=v;e.dispatchEvent(new Event('input',{bubbles:true}));"
                    "e.dispatchEvent(new Event('change',{bubbles:true}));}", token)
                ok = True
        except Exception:
            continue
    return ok


def append_attempt(row: dict) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    new = not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0
    with CSV_PATH.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            w.writeheader()
        w.writerow({k: str(row.get(k, ""))[:400] for k in COLUMNS})


async def run_attempt(cc: str, log, cfg, artifact_fn, warm_seconds: int = 70,
                      show: bool = False, new_headless: bool = False) -> dict:
    from modules.Engine.Amazon.amazon_core import SessionStore, domain_for
    from modules.Engine.Shopify.shopify_core import Solver
    from utilities.mailbox import MailboxError, create_inbox, wait_for_link
    from utilities.rotation import record

    aid = attempt_id()
    domain = domain_for(cc)
    row = {k: "" for k in COLUMNS}
    row.update({"attempt_id": aid, "ts": datetime.now().isoformat(timespec="seconds"),
                "domain": domain, "created": 0, "captcha": "", "warmup_steps": 0,
                "seconds": 0, "submit_status": "", "error": ""})
    started = time.monotonic()
    pool = ProxySet("amazon")
    profile = profile_for(cc, aid, show, new_headless)
    browser = None
    page = None
    base = None
    acc = None
    used_proxies: set[str] = set()
    try:
        px, base, sid, country = await pick_proxy(pool, cc, log, used_proxies)
        if not px:
            row["error"] = "kein Proxy mit passendem_exit_land"
            return row, None
        row["proxy"], row["session_id"] = mask_proxy(px), sid
        log.line("Gen", "", "", f"{aid} proxy={mask_proxy(px)} exit={country}", "dim")
        ident, local = make_identity(aid, "mail.tm")
        log.line("Gen", "", "", f"{aid} Identitaet {ident.full_name} erzeugt", "dim")
        try:
            inbox = await create_inbox(cfg, local)
        except Exception as exc:
            row["error"] = f"catchall: {type(exc).__name__}: {exc}"[:300]
            return row, None
        if not inbox or not inbox.get("address"):
            row["error"] = "catchall: keine Adresse"
            return row, None
        email = inbox["address"]
        ident.email = email
        row["catchall_addr"], row["email"] = inbox.get("catchall_base", ""), email
        record(email)
        log.line("Gen", "", email, f"Catchall {row['catchall_addr']}", "dim")
        try:
            browser = Browser(**profile, proxy=px)
            page = await browser.new_page()
        except Exception as exc:
            log.line("Gen", "", "", f"headless-Start fehlgeschlagen: "
                                    f"{type(exc).__name__}: {exc}", "warn")
            if new_headless or show:
                raise
            await browser.stop() if browser else None
            profile = profile_for(cc, aid, show, new_headless=True)
            browser = Browser(**profile, proxy=px)
            page = await browser.new_page()
            log.line("Gen", "", "", "headless=new (chrome) aktiv", "dim")
        log.line("Gen", "", "", f"Browser {profile['locale']} "
                               f"{profile['viewport']['width']}x{profile['viewport']['height']} "
                               f"headless={not show}", "dim")
        human = Human(seed_for(aid) ^ 0x1234)
        statuses: list[int] = []

        def on_response(resp):
            try:
                if resp.request.method == "POST" and any(
                        x in resp.url.lower() for x in ("/ap/register", "createaccount", "ap/signin")):
                    statuses.append(resp.status)
            except Exception:
                pass

        page.on("response", on_response)
        row["warmup_steps"] = await warmup(page, human, cc, domain, log, warm_seconds)
        ok = await checkout_signup(page, human, log)
        if not ok:
            log.line("Gen", "", "", "Checkout-Weg nicht erreichbar, Fallback Signup", "warn")
            ok = await fallback_signup(page, human, domain, email, log)
        if not ok:
            row["error"] = "kein_Signup_Flow_erreicht"
            return row, None
        if not await fill_form(page, human, ident):
            row["error"] = "Formularfelder_nicht_erreichbar"
            return row, None
        log.line("Gen", "", email, "Formular gefuellt, Submit folgt", "dim")
        rounds = 0
        captcha_log = []
        for _ in range(3):
            log.line("Gen", "", email, f"Submit {rounds + 1}/3", "dim")
            await submit_form(page, human)
            await human.pause(2, 6)
            if statuses:
                row["submit_status"] = statuses[-1]
            log.line("Gen", "", email, f"Antwort status={row['submit_status'] or '?'}", "dim")
            kind, sitekey, flagged = await detect_captcha(page)
            if not flagged:
                break
            captcha_log.append(kind or "unusual")
            log.line("Gen", "", email, f"Captcha erkannt: {kind or 'unusual'}", "warn")
            if rounds >= 2 or not kind or not sitekey:
                row["error"] = "captcha_oder_unusual_activity"
                break
            try:
                token = await Solver(cfg).solve(kind, sitekey, page.url, px)
            except Exception:
                token = None
            if not token or not await inject_token(page, token):
                row["error"] = "captcha_token_nicht_eingesetzt"
                break
            rounds += 1
        row["captcha"] = ",".join(captcha_log)
        text = (await page.content()).lower()
        created = bool(not row["error"] and any(
            x in text for x in ("willkommen", "welcome", "verify", "bestätigen", "otp")))
        if created:
            try:
                cookies = await page.context.cookies()
                await SessionStore("amazon").save_cookies(email, cookies)
                link = None
                try:
                    link = await wait_for_link(inbox, timeout=25.0)
                except Exception:
                    pass
                acc = {"email": email, "password": ident.password,
                       "first_name": ident.first_name, "last_name": ident.last_name,
                       "domain": domain, "proxy": mask_proxy(px), "proxy_session": sid,
                       "verify_link": link or "", "cookies": len(cookies)}
                artifact_fn(acc)
                row["created"] = 1
                log.line("Gen", "", email, "Account created (Browser)", "ok")
            except Exception as exc:
                row["error"] = f"artefakt: {type(exc).__name__}: {exc}"[:300]
        else:
            err = await _visible(page, ["#error_message", ".message-error", "[role='alert']"])
            detail = (await err.inner_text())[:180] if err else (row["error"] or "submit_abgelehnt")
            row["error"] = detail.replace("\n", " ").strip()
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"[:300]
        if is_proxy_failure(exc):
            pool.mark_dead(base)
    finally:
        row["seconds"] = round(time.monotonic() - started, 1)
        if page is not None and int(row.get("created", 0) or 0) != 1:
            try:
                shot = APP_ROOT / "var" / "probe" / "gen" / f"{aid}.png"
                shot.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(shot), timeout=8000)
                log.line("Gen", "", "", f"Screenshot {shot.name}", "dim")
            except Exception:
                pass
        if browser:
            try:
                await browser.stop()
            except Exception:
                pass
        profile_dir = Path(profile["user_data_dir"])
        try:
            shutil.rmtree(profile_dir, ignore_errors=True)
        except Exception:
            pass
        append_attempt(row)
    return row, acc
