#!/usr/bin/env python3
"""Toolbox: Proxy-Test, Captcha-Balance, Webhook-Test."""
from __future__ import annotations

import asyncio
from pathlib import Path

from curl_cffi.requests import AsyncSession

from modules.shopify_core import Settings, load_env, session, headers

ROOT = Path(__file__).resolve().parent.parent
ENV = load_env()


async def test_proxy(proxy: str, timeout: int = 15) -> dict:
    """Pruft einen Proxy gegen eine neutrale Adresse."""
    try:
        s = AsyncSession(timeout=timeout, impersonate="chrome", proxy=proxy)
        r = await s.get("https://example.com/")
        await s.close()
        return {"proxy": proxy, "ok": r.status_code == 200,
                "status": r.status_code, "note": ""}
    except Exception as exc:
        return {"proxy": proxy, "ok": False, "status": 0,
                "note": type(exc).__name__}


async def test_proxies(module: str = "topps") -> list[dict]:
    """Testet alle Eintraege aus proxies/<module>/ und proxies/*.txt."""
    from modules.shopify_core import proxy_files_for, _parse_proxy_lines
    files = proxy_files_for(module)
    items: list[str] = []
    seen: set[str] = set()
    for f in files:
        if not f.exists():
            continue
        for x in _parse_proxy_lines(f.read_text(encoding="utf-8-sig")):
            if x not in seen:
                seen.add(x)
                items.append(x)
    if not items:
        p = ROOT / "config" / "proxy.txt"
        if p.exists():
            items = _parse_proxy_lines(p.read_text(encoding="utf-8-sig"))
    if not items:
        print(f"[toolbox] keine Proxies fuer Modul '{module}' gefunden.")
        return []
    return list(await asyncio.gather(*(test_proxy(x) for x in items)))


async def captcha_balance() -> dict:
    """Fragt das Guthaben beim konfigurierten Captcha-Provider ab."""
    provider = ENV.get("CAPTCHA_PROVIDER", "capsolver").lower()
    key = {"capsolver": ENV.get("CAPSOLVER_KEY", ""),
           "2captcha": ENV.get("TWOCAPTCHA_KEY", ""),
           "capmonster": ENV.get("CAPMONSTER_KEY", "")}.get(provider, "")
    if not key:
        return {"provider": provider, "ok": False, "note": "kein API-Key"}
    try:
        async with AsyncSession(timeout=20) as s:
            if provider in ("capsolver", "capmonster"):
                base = ("https://api.capsolver.com" if provider == "capsolver"
                        else "https://api.capmonster.cloud")
                r = await s.post(f"{base}/getBalance", json={"clientKey": key})
                d = r.json()
                return {"provider": provider, "ok": d.get("balance") is not None,
                        "balance": d.get("balance")}
            r = await s.get("https://2captcha.com/res.php", params={
                "key": key, "action": "getbalance", "json": 1})
            d = r.json()
            return {"provider": provider, "ok": d.get("status") == 1,
                    "balance": d.get("request")}
    except Exception as exc:
        return {"provider": provider, "ok": False, "note": type(exc).__name__}


async def test_webhook(url: str) -> dict:
    """Sendet eine Testnachricht an einen Discord-Webhook."""
    from modules.shopify_core import Notifier
    n = Notifier(url)
    await n.send("Toolbox-Test", "info", {"status": "ok"})
    return {"ok": True, "note": "gesendet"}


class ToolboxModule:
    title = "Toolbox"

    def run(self):
        while True:
            print(f"\n --- {self.title} ---")
            print("   1  Proxy testen (Modulordner)")
            print("   2  Captcha-Balance")
            print("   3  Discord-Webhook testen")
            print("   0  Zurueck")
            try:
                wahl = input(" Auswahl: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if wahl == "0":
                return 0
            if wahl == "1":
                mod = input(" Modul [topps]: ").strip() or "topps"
                try:
                    for r in asyncio.run(test_proxies(mod)):
                        print(f"[{'OK' if r['ok'] else 'FAIL'}] {r['proxy']} "
                              f"({r['status']}) {r['note']}")
                except KeyboardInterrupt:
                    print()
            elif wahl == "2":
                try:
                    b = asyncio.run(captcha_balance())
                    print(f"[toolbox] {b}")
                except KeyboardInterrupt:
                    print()
            elif wahl == "3":
                url = input(" Webhook-URL: ").strip()
                if url:
                    try:
                        print(asyncio.run(test_webhook(url)))
                    except KeyboardInterrupt:
                        print()


if __name__ == "__main__":
    import sys
    sys.exit(ToolboxModule().run())