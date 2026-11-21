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
import string
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
APP = BASE / "BakiAIO"
sys.path.insert(0, str(APP))

from utilities.proxy import normalize_proxy, proxy_playwright, mask_proxy  # noqa: E402

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


async def _click_any(page, selectors: list[str]) -> bool:
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if await loc.count():
                await loc.click(timeout=8000)
                return True
        except Exception:
            continue
    return False


async def _fill_name(page) -> bool:
    for sel in ("#ap_customer_name", "input[name='customerName']",
                "input[name='name']"):
        loc = page.locator(sel).first
        try:
            if await loc.count() and await loc.is_visible():
                await loc.fill("Max Mustermann")
                return True
        except Exception:
            continue
    return False


async def _fill_registration(page) -> None:
    pw = "Amz" + "".join(random.choice(string.ascii_letters + string.digits)
                         for _ in range(9)) + "9!"
    for sel, val in (("#ap_customer_name", "Max Mustermann"),
                     ("input[name='customerName']", "Max Mustermann"),
                     ("#ap_password", pw), ("#ap_password_check", pw),
                     ("input[name='password']", pw),
                     ("input[name='passwordCheck']", pw)):
        loc = page.locator(sel).first
        if await loc.count():
            try:
                await loc.fill(val)
            except Exception:
                pass


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


def _catchall_addresses(n: int = 3) -> list[str]:
    try:
        d = json.loads((APP / "settings.json").read_text(encoding="utf-8"))
    except Exception:
        return []
    doms: list[str] = []
    for m in (d.get("Mastermails") or []):
        c = str((m or {}).get("catchall") or "").strip()
        if "@" in c:
            dom = c.rsplit("@", 1)[1].lower()
            if dom not in doms:
                doms.append(dom)
    out = []
    if not doms:
        return out
    for i in range(n):
        dom = doms[i % len(doms)]
        local = "probe" + "".join(random.choice(string.ascii_lowercase + string.digits)
                                  for _ in range(10))
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


async def _goto(page, url: str, timeout: int = 45000):
    last = None
    for _ in range(2):
        try:
            return await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        except Exception as exc:
            last = exc
            await page.wait_for_timeout(1200)
    raise last


async def browser_case(fall: str, proxy: str | None) -> list[dict]:
    from playwright.async_api import async_playwright

    outdir = OUT / fall
    outdir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    # Frisches Profil je Lauf (alte Probe-Profile koennen gesperrt sein und
    # dann ERR_HTTP_RESPONSE_CODE_FAILURE liefern).
    profile_dir = outdir / f"_profile_{int(time.time())}"
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            str(profile_dir), channel="chrome", headless=False,
            locale="de-DE", timezone_id="Europe/Berlin",
            viewport={"width": 1366, "height": 900},
            proxy=proxy_playwright(proxy),
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = await ctx.new_page()
        nav_log: list[str] = []
        page.on("framenavigated",
                lambda f: nav_log.append(f.url) if f == page.main_frame else None)
        for name, url in URLS:
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
            await _goto(page, "https://www.amazon.de/")
            await page.wait_for_timeout(1500)
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
            await page.wait_for_timeout(2500)
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
                    await _goto(page, "https://www.amazon.de/")
                    await page.wait_for_timeout(1200)
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
                await email_loc.fill(addr)
                await _click_any(page, ["#continue", "input#continue",
                                        "button:has-text('Weiter')",
                                        "button[type=submit]",
                                        "input[type=submit]"])
                await page.wait_for_load_state("domcontentloaded")
                await page.wait_for_timeout(2500)
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
                        await page.wait_for_timeout(2500)
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
                    await page.wait_for_timeout(2500)
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
                        await page.wait_for_timeout(4000)
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


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="A,B,C")
    ap.add_argument("--proxy-file", default=str(APP / "proxies" / "amazon" / "isp.txt"))
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

    (OUT / "probe_report.json").write_text(
        json.dumps(all_rows, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\nfall | url | status | form | heading")
    for r in all_rows:
        if "steps" in r:
            print(f"{r['fall']} | FLOW signup | hit={r.get('hit')} | "
                  f"personal_links={len(r.get('personal_links') or [])} "
                  f"business_links={len(r.get('business_links') or [])}")
            for a in (r.get("attempts") or []):
                print(f"     #{a.get('attempt')} {a.get('email')} -> "
                      f"{a.get('url')} pw={a.get('registration_branch')} "
                      f"submit_status={a.get('submit_status')} "
                      f"err={a.get('submit_error_text','')[:60]}")
        else:
            print(f"{r['fall']} | {r['slug']} | {r.get('status')} | "
                  f"{'JA' if r.get('form') else 'nein'} {r.get('form')} | "
                  f"{r.get('heading','')[:60]}")
    print("\nreport:", OUT / "probe_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
