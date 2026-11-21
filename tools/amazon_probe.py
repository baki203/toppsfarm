#!/usr/bin/env python3
"""amazon_probe - Gegenprobe Amazon-Auth-Gate (Netz vs. Code), NUR persoenliches
Kundenkonto (Business hart ausgeschlossen).

Faelle:
  A  echter Chrome (channel=chrome, headed), ohne Proxy
  B  echter Chrome, durch ISP-Proxy (Playwright server+auth)
  C  ISP-Proxy + curl_cffi im Request-Mode

Je Fall/Ziel-URL: Status, finale URL, Titel, Screenshot, HTML, Formular-Erkennung,
Ueberschrift. Browser-Faelle protokollieren den persoenlichen Pfad
Startseite -> #nav-link-accountList -> Signin -> Link "Konto erstellen"/"Neu bei
Amazon"/href /ap/register (ohne business). Gibt es nur den Business-Link, wird
/ap/register?openid... direkt aufgerufen. Business-Spuren werden als solche
festgehalten (welcher Link gegriffen hat).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import secrets
import string
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
APP = BASE / "BakiAIO"
sys.path.insert(0, str(APP))

from utilities.proxy import (mask_proxy, normalize_proxy, proxy_playwright,  # noqa: E402
                             sticky_session)
from modules.Engine.Amazon.amazon_core import domain_for  # noqa: E402

OUT = APP / "var" / "probe"
URLS = [
    ("home", "https://www.amazon.de/"),
    ("register", "https://www.amazon.de/ap/register"),
    ("signin", "https://www.amazon.de/ap/signin"),
    ("gp_register", "https://www.amazon.de/gp/register"),
]
REGISTER_DIRECT = ("https://www.amazon.de/ap/register?"
                   "openid.return_to=https%3A%2F%2Fwww.amazon.de%2F"
                   "&openid.mode=checkid_setup")

EXTRA_URLS = [
    ("amazon_com_register",
     "https://www.amazon.com/ap/register?openid.return_to=https%3A%2F%2Fwww.amazon.com%2F"
     "&openid.mode=checkid_setup"),
    ("de_register_lang",
     "https://www.amazon.de/ap/register?openid.return_to=https%3A%2F%2Fwww.amazon.de%2F"
     "&openid.mode=checkid_setup&language=de_DE"),
    ("de_gp_register_openid",
     "https://www.amazon.de/gp/register?openid.return_to=https%3A%2F%2Fwww.amazon.de%2F"
     "&openid.mode=checkid_setup"),
]

FORM_MARKERS = {
    "#ap_customer_name": r'id="ap_customer_name"',
    "#ap_email": r'id="ap_email"',
    "#ap_password": r'id="ap_password"',
    'input[name="customerName"]': r'name="customerName"',
    'input[name="email"]': r'name="email"',
    'button/Konto erstellen': r"Konto erstellen",
    "button/Create account": r"[Cc]reate (?:your )?account",
}
BUSINESS_RE = re.compile(r"business|gesch(?:ae|ä)ft|unternehmen|businesscustomer",
                         re.I)
PERSONAL_TEXT_RE = re.compile(r"konto erstellen|neu bei amazon|registrieren", re.I)


def detect_form(html: str) -> list[str]:
    return [k for k, rx in FORM_MARKERS.items() if re.search(rx, html or "")]


def heading(html: str) -> str:
    for tag in ("h1", "h4", "h2"):
        m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", html or "", re.S | re.I)
        if m:
            txt = re.sub(r"<[^>]+>", " ", m.group(1))
            txt = re.sub(r"\s+", " ", txt).strip()
            if txt:
                return txt[:200]
    return ""


async def _fields(page) -> list[dict]:
    try:
        return await page.evaluate(
            """() => Array.from(document.querySelectorAll('input,button,a')).map(e => {
                 const r = e.getBoundingClientRect();
                 const vis = !!(e.offsetParent || (r.width && r.height));
                 return {tag: e.tagName.toLowerCase(), id: e.id || '',
                         name: e.name || '', type: e.type || '',
                         autocomplete: e.autocomplete || '', visible: vis,
                         text: (e.innerText || e.value || '').trim().slice(0, 60)};
               })""")
    except Exception:
        return []


EMAIL_SELECTORS = ("#ap_email_login", "#ap_email", "input[name='email']")


async def _email_locator(page):
    for sel in EMAIL_SELECTORS:
        loc = page.locator(sel).first
        try:
            if await loc.count() and await loc.is_visible():
                return loc
        except Exception:
            continue
    return None


def _has_password_field(fields: list[dict]) -> bool:
    for f in fields:
        if f.get("tag") != "input" or f.get("type") != "password":
            continue
        if not f.get("visible"):
            continue
        if f.get("id") == "auth-credential-autofill-hint":
            continue
        if f.get("id") in ("ap_password", "ap_password_check"):
            return True
        if f.get("name") in ("password", "passwordCheck"):
            return True
    return False


async def _save(page, outdir: Path, name: str) -> None:
    html = await page.content()
    (outdir / f"{name}.html").write_text(html, encoding="utf-8")
    await page.screenshot(path=str(outdir / f"{name}.png"), full_page=True)


COOKIE_SELECTORS = (
    "#sp-cc-accept", "input#sp-cc-accept", "#sp-cc-cookie-banner button",
    "button:has-text('Alle akzeptieren')", "button:has-text('Akzeptieren')",
    "input[value*='Akzeptieren']", "[data-testid='cookie-accept']",
)

COOKIE_TEXTS = (
    "Alle akzeptieren", "Akzeptieren", "Cookies akzeptieren", "Akzeptiere alle",
    "Accept all", "Accept", "I agree", "Got it", "OK",
)


async def _cursor_wander(page) -> None:
    """Echter Mauszeiger: unregelmaessige Bewegungen ueber die Seite."""
    try:
        vp = page.viewport_size or {"width": 1366, "height": 900}
        w, h = vp.get("width", 1366), vp.get("height", 900)
        for _ in range(random.randint(2, 4)):
            x = random.randint(int(w * 0.12), int(w * 0.88))
            y = random.randint(int(h * 0.15), int(h * 0.85))
            await page.mouse.move(x, y, steps=random.randint(9, 22))
            await page.wait_for_timeout(random.randint(90, 340))
    except Exception:
        pass


async def _human_click(page, loc) -> bool:
    """Maus sichtbar zum Ziel bewegen, kurz zielen, dann klicken."""
    try:
        await _cursor_wander(page)
        box = await loc.bounding_box(timeout=3000)
        if box and box.get("width") and box.get("height"):
            x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
            y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
            await page.mouse.move(x, y, steps=random.randint(10, 22))
            await page.wait_for_timeout(random.randint(220, 650))
            await page.mouse.move(x + random.uniform(-7, 7),
                                  y + random.uniform(-7, 7),
                                  steps=random.randint(2, 5))
            await page.wait_for_timeout(random.randint(120, 320))
        await loc.hover(timeout=3000)
        await page.wait_for_timeout(random.randint(120, 350))
        await loc.click(timeout=10000)
        return True
    except Exception:
        return False


async def _accept_cookies(page) -> bool:
    """Cookie-Banner wie ein Mensch annehmen (Selector + sichtbarer Text)."""
    for sel in COOKIE_SELECTORS:
        try:
            loc = page.locator(sel).first
            if await loc.count() and await loc.is_visible():
                if await _human_click(page, loc):
                    await page.wait_for_timeout(random.randint(600, 1400))
                    return True
        except Exception:
            continue
    for text in COOKIE_TEXTS:
        try:
            loc = page.get_by_role("button", name=text, exact=False).first
            if await loc.count() and await loc.is_visible():
                if await _human_click(page, loc):
                    await page.wait_for_timeout(random.randint(600, 1400))
                    return True
        except Exception:
            continue
    return False


async def _settle(page, ms: int = 1800) -> bool:
    """Menschliche Pause: scrollen, Maus bewegen, Cookie-Banner pruefen."""
    await page.wait_for_timeout(random.randint(max(400, ms // 2), ms + 800))
    await _cursor_wander(page)
    try:
        await page.mouse.wheel(0, random.randint(120, 380))
        await page.wait_for_timeout(random.randint(250, 700))
        await page.mouse.wheel(0, -random.randint(120, 380))
    except Exception:
        pass
    return await _accept_cookies(page)


async def _click_any(page, selectors: list[str]) -> bool:
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if await loc.count() and await loc.is_visible():
                await page.wait_for_timeout(random.randint(500, 1400))
                if await _human_click(page, loc):
                    return True
        except Exception:
            continue
    return False


async def _human_type(page, loc, text: str) -> None:
    try:
        await _human_click(page, loc)
        await page.keyboard.press("ControlOrMeta+A")
        await page.keyboard.press("Backspace")
        await page.wait_for_timeout(random.randint(150, 450))
        await page.keyboard.type(text, delay=random.randint(70, 160))
        await page.wait_for_timeout(random.randint(250, 700))
    except Exception:
        try:
            await loc.fill(text)
        except Exception:
            pass


async def _fill_name(page, ident=None) -> bool:
    name = ident.full_name if ident else "Max Mustermann"
    for sel in ("#ap_customer_name", "input[name='customerName']",
                "input[name='name']"):
        loc = page.locator(sel).first
        try:
            if await loc.count() and await loc.is_visible():
                await _human_type(page, loc, name)
                return True
        except Exception:
            continue
    return False


async def _fill_registration(page, ident=None) -> None:
    pw = ident.password if ident else ("Amz" + "".join(
        random.choice(string.ascii_letters + string.digits) for _ in range(9)) + "9!")
    name = ident.full_name if ident else "Max Mustermann"
    for sel, val in (("#ap_customer_name", name),
                     ("input[name='customerName']", name),
                     ("#ap_password", pw), ("#ap_password_check", pw),
                     ("input[name='password']", pw),
                     ("input[name='passwordCheck']", pw)):
        loc = page.locator(sel).first
        if await loc.count():
            await _human_type(page, loc, val)


async def _error_text(page) -> str:
    for sel in ("#auth-error-message-box", ".a-alert-error",
                "#auth-warning-message-box", "[role=alert]"):
        loc = page.locator(sel).first
        if await loc.count():
            try:
                return (await loc.inner_text())[:300]
            except Exception:
                pass
    return ""


def _last_doc_status(responses: list[dict]) -> int | None:
    return responses[-1]["status"] if responses else None


def _catchalls() -> list[str]:
    """Nur die catchall-Adressen aus settings.json ( keine Passwoerter )."""
    try:
        text = (APP / "settings.json").read_text(encoding="utf-8")
    except Exception:
        return []
    out: list[str] = []
    for c in re.findall(r'"catchall"\s*:\s*"([^"]+)"', text, re.I):
        c = c.strip()
        if "@" in c and c not in out:
            out.append(c)
    return out


def _catchall_addresses(n: int = 3) -> list[str]:
    """Skyridge-Stil: vorname+nachname (@ Catch-All), je Versuch anders."""
    cs = _catchalls()
    if not cs:
        return []
    from utilities.identity import IdentityGenerator
    gen = IdentityGenerator()
    out = []
    for i in range(n):
        catchall = cs[i % len(cs)]
        dom = catchall.rsplit("@", 1)[1].lower()
        ident = gen.generate()
        local = ident.email.split("@", 1)[0].replace(".", "")
        if random.random() < 0.6:
            local = re.sub(r"\d+$", "", local)
        out.append(f"{local}@{dom}")
    return out


async def _collect_links(page) -> list[dict]:
    try:
        return await page.evaluate(
            """() => Array.from(document.querySelectorAll('a')).map(
                 a => ({href: a.href || '', text: (a.innerText || a.textContent || '').trim()}))""")
    except Exception:
        return []


def _classify_links(links: list[dict]) -> tuple[list[dict], list[dict]]:
    personal, business = [], []
    for ln in links:
        href = (ln.get("href") or "").lower()
        text = ln.get("text") or ""
        match = ("/ap/register" in href) or bool(PERSONAL_TEXT_RE.search(text))
        if not match:
            continue
        is_biz = bool(BUSINESS_RE.search(href)) or bool(BUSINESS_RE.search(text))
        (business if is_biz else personal).append(ln)
    return personal, business


async def _goto(page, url: str, timeout: int = 60000):
    """Erst alles laden lassen (load + networkidle), dann Cookies annehmen."""
    last = None
    for _ in range(2):
        try:
            resp = await page.goto(url, wait_until="load", timeout=timeout)
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            await _accept_cookies(page)
            await page.wait_for_timeout(random.randint(800, 1800))
            return resp
        except Exception as exc:
            last = exc
            await page.wait_for_timeout(1500)
    raise last


async def browser_case(fall: str, proxy: str | None, cc: str = "DE",
                       flow_only: bool = False) -> list[dict]:
    from playwright.async_api import async_playwright

    domain = domain_for(cc)
    outdir = OUT / fall / cc
    outdir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    # Frisches Profil je Lauf (alte Probe-Profile koennen gesperrt sein und
    # dann ERR_HTTP_RESPONSE_CODE_FAILURE liefern).
    profile_dir = outdir / f"_profile_{int(time.time())}"
    locale = {"NL": "nl-NL", "IT": "it-IT", "BE": "nl-BE", "PL": "pl-PL",
              "SE": "sv-SE", "IE": "en-IE", "DE": "de-DE"}.get(cc, "de-DE")
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            str(profile_dir), channel="chrome", headless=False,
            locale=locale, timezone_id="Europe/Berlin",
            viewport={"width": 1366, "height": 900},
            proxy=proxy_playwright(proxy),
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = await ctx.new_page()
        nav_log: list[str] = []
        page.on("framenavigated",
                lambda f: nav_log.append(f.url) if f == page.main_frame else None)
        urls = [] if flow_only else [
            (name, u.replace("www.amazon.de", "www." + domain)) for name, u in URLS]
        for name, url in urls:
            rec = {"fall": fall, "slug": name, "url": url}
            try:
                resp = await _goto(page, url)
                await page.wait_for_timeout(1500)
                html = await page.content()
                rec["status"] = resp.status if resp else None
                rec["final_url"] = page.url
                rec["title"] = await page.title()
                rec["form"] = detect_form(html)
                rec["heading"] = heading(html)
                rec["html_path"] = str(outdir / f"{name}.html")
                rec["png_path"] = str(outdir / f"{name}.png")
                (outdir / f"{name}.html").write_text(html, encoding="utf-8")
                await page.screenshot(path=str(outdir / f"{name}.png"), full_page=True)
            except Exception as exc:
                rec["status"] = None
                rec["error"] = f"{type(exc).__name__}: {exc}"[:300]
            rows.append(rec)

        # Persoenlicher Pfad (verbindlich): Home -> #nav-link-accountList ->
        # #ap_email fuellen -> #continue -> 2. Schritt pruefen (Passwortfelder
        # = Registrierungszweig). /ax/claim/intent ohne Passwort -> andere
        # E-Mail versuchen (max 3, verschiedene Catch-All-Domains).
        flow = {"fall": fall, "slug": "flow_signup", "steps": []}
        nav_log.clear()
        responses: list[dict] = []
        page.on("response", lambda r: responses.append(
            {"url": r.url, "status": r.status})
            if r.request.resource_type == "document" else None)
        try:
            addrs = _catchall_addresses(3)
            flow["addresses"] = addrs
            await _goto(page, f"https://www.{domain}/")
            await _settle(page, 2600)
            flow["steps"].append({"step": "home", "url": page.url,
                                  "title": await page.title()})
            clicked = False
            for sel in ('#nav-link-accountList', 'a[data-nav-role="signin"]',
                        'a[href*="/ap/signin"]'):
                loc = page.locator(sel).first
                if await loc.count():
                    try:
                        await loc.click(timeout=8000)
                        clicked = True
                        break
                    except Exception:
                        pass
            flow["clicked_account_list"] = clicked
            await page.wait_for_load_state("domcontentloaded")
            flow["cookies_signin"] = await _settle(page, 2500)
            flow["steps"].append({"step": "signin", "url": page.url,
                                  "title": await page.title()})
            await _save(page, outdir, "flow_signin")
            flow["signin_fields"] = await _fields(page)
            flow["signin_heading"] = heading(await page.content())
            links = await _collect_links(page)
            personal, business = _classify_links(links)
            flow["personal_links"] = personal[:10]
            flow["business_links"] = business[:10]

            attempts: list[dict] = []
            for i, addr in enumerate(addrs):
                step: dict = {"attempt": i + 1, "email": addr}
                email_loc = await _email_locator(page)
                if email_loc is None:
                    await _click_any(page, [
                        'a:has-text("andere E-Mail")',
                        'a:has-text("Andere E-Mail")',
                        'a:has-text("Try another")',
                        'a:has-text("E-Mail-Adresse")'])
                    await page.wait_for_timeout(1500)
                    email_loc = await _email_locator(page)
                if email_loc is None:
                    await _goto(page, f"https://www.{domain}/")
                    await _settle(page, 2000)
                    for sel in ('#nav-link-accountList', 'a[href*="/ap/signin"]'):
                        loc = page.locator(sel).first
                        if await loc.count():
                            try:
                                await loc.click(timeout=8000)
                                break
                            except Exception:
                                pass
                    await page.wait_for_load_state("domcontentloaded")
                    await page.wait_for_timeout(2000)
                    email_loc = await _email_locator(page)
                if email_loc is None:
                    step["error"] = "kein E-Mail-Feld erreichbar"
                    attempts.append(step)
                    break
                await _human_type(page, email_loc, addr)
                await _click_any(page, ["#continue", "input#continue",
                                        "button:has-text('Weiter')",
                                        "button[type=submit]",
                                        "input[type=submit]"])
                await page.wait_for_load_state("domcontentloaded")
                step["cookies"] = await _settle(page, 2500)
                step["url"] = page.url
                step["title"] = await page.title()
                await _save(page, outdir, f"flow_step2_{i + 1}")
                fields = await _fields(page)
                step["fields"] = fields
                step["heading"] = heading(await page.content())
                has_pw = _has_password_field(fields)
                step["registration_branch"] = has_pw
                if not has_pw:
                    # /ax/claim/intent "Diese E-Mail ist neu fuer uns":
                    # Button "Erstelle dein Konto" postet nach /ap/register.
                    clicked_create = await _click_any(page, [
                        "#intent-confirmation-form input[type=submit]",
                        "#intention-submit-button",
                        "button:has-text('Erstelle dein Konto')",
                        "input[value*='Erstelle dein Konto']",
                        "button:has-text('Create your account')"])
                    if clicked_create:
                        await page.wait_for_load_state("domcontentloaded")
                        await _settle(page, 2500)
                        step["create_clicked"] = True
                        step["url"] = page.url
                        step["title"] = await page.title()
                        await _save(page, outdir, f"flow_register_{i + 1}")
                        fields = await _fields(page)
                        step["fields"] = fields
                        step["heading"] = heading(await page.content())
                        has_pw = _has_password_field(fields)
                        step["registration_branch"] = has_pw
                if not has_pw and await _fill_name(page):
                    # /ap/register Schritt 1: "Dein Name" -> Weiter -> Passwort
                    await _click_any(page, [
                        "#continue", "input#continue",
                        "button:has-text('Weiter')", "input[type=submit]",
                        "button[type=submit]"])
                    await page.wait_for_load_state("domcontentloaded")
                    await _settle(page, 2500)
                    step["name_step"] = True
                    step["url"] = page.url
                    step["title"] = await page.title()
                    await _save(page, outdir, f"flow_password_{i + 1}")
                    fields = await _fields(page)
                    step["fields2"] = fields
                    step["heading2"] = heading(await page.content())
                    has_pw = _has_password_field(fields)
                    step["registration_branch"] = has_pw
                if has_pw:
                    try:
                        await _fill_registration(page)
                        await _click_any(page, [
                            "#continue", "input#continue",
                            "input[id*='createAccountSubmit']",
                            "button[type=submit]", "input[type=submit]"])
                        await page.wait_for_load_state("domcontentloaded")
                        await _settle(page, 4000)
                    except Exception as exc:
                        step["submit_error"] = f"{type(exc).__name__}: {exc}"[:200]
                    step["submit_url"] = page.url
                    step["submit_title"] = await page.title()
                    step["submit_heading"] = heading(await page.content())
                    step["submit_error_text"] = await _error_text(page)
                    step["submit_status"] = _last_doc_status(responses)
                    await _save(page, outdir, f"flow_submit_{i + 1}")
                    attempts.append(step)
                    break
                attempts.append(step)
                await _click_any(page, [
                    'a:has-text("andere E-Mail")',
                    'a:has-text("Andere E-Mail")',
                    'a:has-text("Try another")',
                    'a:has-text("E-Mail-Adresse")'])
                await page.wait_for_timeout(1500)
            flow["attempts"] = attempts
            flow["nav_log"] = list(nav_log)
            flow["hit"] = any(a.get("registration_branch") for a in attempts)
        except Exception as exc:
            flow["error"] = f"{type(exc).__name__}: {exc}"[:300]
        rows.append(flow)
        await ctx.close()
    return rows


async def signup_one(page, cc: str, addr: str, outdir: Path, label: int,
                     ident=None) -> dict:
    """Ein frischer Browser, eine E-Mail, ein Proxy - ein Registrierungsversuch."""
    domain = domain_for(cc)
    step: dict = {"attempt": label, "email": addr}
    responses: list[dict] = []
    page.on("response", lambda r: responses.append(
        {"url": r.url, "status": r.status})
        if r.request.resource_type == "document" else None)
    try:
        await _goto(page, f"https://www.{domain}/")
        await _settle(page, 2600)
        step["home"] = page.url
        clicked = False
        for sel in ('#nav-link-accountList', 'a[data-nav-role="signin"]',
                    'a[href*="/ap/signin"]'):
            loc = page.locator(sel).first
            if await loc.count() and await loc.is_visible():
                if await _human_click(page, loc):
                    clicked = True
                    break
        step["clicked_account_list"] = clicked
        await page.wait_for_load_state("domcontentloaded")
        step["cookies"] = await _settle(page, 2500)
        step["signin"] = page.url
        await _save(page, outdir, f"signin_{label}")
        email_loc = await _email_locator(page)
        if email_loc is None:
            step["error"] = "kein E-Mail-Feld erreichbar"
            return step
        await _human_type(page, email_loc, addr)
        await _click_any(page, ["#continue", "input#continue",
                                "button:has-text('Weiter')", "button[type=submit]",
                                "input[type=submit]"])
        await page.wait_for_load_state("domcontentloaded")
        await _settle(page, 2500)
        step["step2"] = page.url
        await _save(page, outdir, f"step2_{label}")
        fields = await _fields(page)
        step["fields"] = fields
        step["heading"] = heading(await page.content())
        has_pw = _has_password_field(fields)
        if not has_pw:
            clicked_create = await _click_any(page, [
                "#intent-confirmation-form input[type=submit]",
                "#intention-submit-button",
                "button:has-text('Erstelle dein Konto')",
                "input[value*='Erstelle dein Konto']",
                "button:has-text('Create your account')"])
            if clicked_create:
                await page.wait_for_load_state("domcontentloaded")
                await _settle(page, 2500)
                if "/ax/claim/intent" in page.url:
                    await _click_any(page, ["input[type=submit]", "#continue",
                                            "button[type=submit]"])
                    await page.wait_for_load_state("domcontentloaded")
                    await _settle(page, 2000)
                step["create_clicked"] = True
                step["register"] = page.url
                await _save(page, outdir, f"register_{label}")
                fields = await _fields(page)
                has_pw = _has_password_field(fields)
        if not has_pw and await _fill_name(page, ident):
            await _click_any(page, ["#continue", "input#continue",
                                    "button:has-text('Weiter')", "input[type=submit]",
                                    "button[type=submit]"])
            await page.wait_for_load_state("domcontentloaded")
            await _settle(page, 2500)
            step["name_step"] = True
            await _save(page, outdir, f"password_{label}")
            fields = await _fields(page)
            has_pw = _has_password_field(fields)
        step["registration_branch"] = has_pw
        if has_pw:
            try:
                await _fill_registration(page, ident)
                await _click_any(page, ["#continue", "input#continue",
                                        "input[id*='createAccountSubmit']",
                                        "button[type=submit]", "input[type=submit]"])
                await page.wait_for_load_state("domcontentloaded")
                await _settle(page, 4000)
            except Exception as exc:
                step["submit_error"] = f"{type(exc).__name__}: {exc}"[:200]
            step["submit_url"] = page.url
            step["submit_heading"] = heading(await page.content())
            step["submit_error_text"] = await _error_text(page)
            step["submit_status"] = _last_doc_status(responses)
            await _save(page, outdir, f"submit_{label}")
            step["created"] = bool(
                re.search(r"willkommen|welcome|verify|best.tigen|otp|code",
                          (step["submit_heading"] or "") + (step["submit_url"] or ""),
                          re.I)) and not step["submit_error_text"]
    except Exception as exc:
        step["error"] = f"{type(exc).__name__}: {exc}"[:300]
    return step


async def human_country_flow(cc: str, pf: Path, count: int = 3) -> list[dict]:
    """Je Versuch: neue E-Mail + neuer Proxy + neuer Browser (frische Session)."""
    from playwright.async_api import async_playwright

    from utilities.identity import IdentityGenerator

    domain = domain_for(cc)
    outdir = OUT / "FLOW" / cc
    outdir.mkdir(parents=True, exist_ok=True)
    catchalls = _catchalls()
    gen = IdentityGenerator()
    rows: list[dict] = []
    start = random.randrange(len(catchalls)) if catchalls else 0
    async with async_playwright() as pw:
        for i in range(count):
            if not catchalls:
                break
            catchall = catchalls[(start + i) % len(catchalls)]
            dom = catchall.rsplit("@", 1)[1].lower()
            ident = gen.generate()
            local = ident.email.split("@", 1)[0].replace(".", "")
            if random.random() < 0.6:
                local = re.sub(r"\d+$", "", local)
            addr = f"{local}@{dom}"
            px = country_proxy(cc, pf)
            if not px:
                break
            profile = outdir / f"_profile_{int(time.time())}_{i}"
            locale = {"NL": "nl-NL", "IT": "it-IT", "BE": "nl-BE",
                      "PL": "pl-PL", "SE": "sv-SE", "DE": "de-DE"}.get(cc, "de-DE")
            ctx = await pw.chromium.launch_persistent_context(
                str(profile), channel="chrome", headless=False,
                locale=locale, timezone_id="Europe/Berlin",
                viewport={"width": 1366, "height": 900},
                proxy=proxy_playwright(px),
                args=["--disable-blink-features=AutomationControlled"])
            try:
                page = await ctx.new_page()
                step = await signup_one(page, cc, addr, outdir, i + 1, ident)
                step["proxy"] = mask_proxy(px)
                step["catchall"] = catchall
                rows.append({"fall": "FLOW", "slug": "signup", "cc": cc,
                             "domain": domain, "attempts": [step],
                             "hit": step.get("registration_branch", False),
                             "created": step.get("created", False)})
                if step.get("created"):
                    break
            finally:
                await ctx.close()
    return rows


def request_case(fall: str, proxy: str | None) -> list[dict]:
    from curl_cffi import requests

    outdir = OUT / fall
    outdir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    kw = {"impersonate": "chrome", "timeout": 30}
    if proxy:
        kw["proxy"] = proxy
    targets = list(URLS) + [("register_openid", REGISTER_DIRECT)]
    for name, url in targets:
        rec = {"fall": fall, "slug": name, "url": url}
        try:
            r = requests.get(url, **kw)
            html = r.text or ""
            rec["status"] = r.status_code
            rec["final_url"] = str(r.url)
            rec["title"] = heading(html)
            rec["form"] = detect_form(html)
            rec["heading"] = heading(html)
            rec["html_path"] = str(outdir / f"{name}.html")
            rec["png_path"] = None
            (outdir / f"{name}.html").write_text(html, encoding="utf-8")
        except Exception as exc:
            rec["status"] = None
            rec["error"] = f"{type(exc).__name__}: {exc}"[:300]
        rows.append(rec)
    return rows


def country_proxy(cc: str, pf: Path) -> str | None:
    """ProxyBaron mit passendem Land + frischer Session (sticky)."""
    if not pf.exists():
        return None
    base = normalize_proxy(pf.read_text(encoding="utf-8-sig").splitlines()[0])
    return sticky_session(base, secrets.token_hex(6), country=cc.lower())


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="A,B,C")
    ap.add_argument("--proxy-file", default=str(APP / "proxies" / "amazon" / "isp.txt"))
    ap.add_argument("--flow-cc", default="", help="z. B. NL,IT,BE - persoenlicher Flow je Land")
    ap.add_argument("--flow-proxy-file",
                    default=str(APP / "proxies" / "amazon" / "proxybaron.txt"))
    ap.add_argument("--flow-count", type=int, default=3)
    a = ap.parse_args()
    cases = {c.strip().upper() for c in a.cases.split(",") if c.strip()}

    proxy = None
    pf = Path(a.proxy_file)
    if pf.exists():
        proxy = normalize_proxy(pf.read_text(encoding="utf-8-sig").splitlines()[0])
    if cases & {"B", "C"} and not proxy:
        print("[probe] ISP-Proxy fehlt:", pf)
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict] = []
    if "A" in cases:
        print("[probe] Fall A: Chrome ohne Proxy ...")
        all_rows += await browser_case("A", None)
    if "B" in cases:
        print(f"[probe] Fall B: Chrome via ISP {mask_proxy(proxy)} ...")
        all_rows += await browser_case("B", proxy)
    if "C" in cases:
        print(f"[probe] Fall C: curl_cffi via ISP {mask_proxy(proxy)} ...")
        all_rows += request_case("C", proxy)
    flow_ccs = [c.strip().upper() for c in a.flow_cc.split(",") if c.strip()]
    for cc in flow_ccs:
        px = country_proxy(cc, Path(a.flow_proxy_file))
        if not px:
            print(f"[probe] kein Land-Proxy fuer {cc}")
            continue
        print(f"[probe] FLOW {cc} -> {domain_for(cc)} (neue Session je Versuch) ...")
        all_rows += await human_country_flow(cc, Path(a.flow_proxy_file), a.flow_count)

    (OUT / "probe_report.json").write_text(
        json.dumps(all_rows, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\nfall | url | status | form | heading")
    for r in all_rows:
        if "steps" in r or "attempts" in r:
            print(f"{r['fall']} | FLOW {r.get('cc', '')} | hit={r.get('hit')} "
                  f"created={r.get('created')}")
            for a in (r.get("attempts") or r.get("steps") or []):
                print(f"     #{a.get('attempt')} {a.get('email')} -> "
                      f"{a.get('submit_url') or a.get('step2') or a.get('url')} "
                      f"pw={a.get('registration_branch')} "
                      f"submit_status={a.get('submit_status')} "
                      f"err={a.get('submit_error_text', a.get('error', ''))[:70]}")
        else:
            print(f"{r['fall']} | {r['slug']} | {r.get('status')} | "
                  f"{'JA' if r.get('form') else 'nein'} {r.get('form')} | "
                  f"{r.get('heading','')[:60]}")
    print("\nreport:", OUT / "probe_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
