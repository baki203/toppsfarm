#!/usr/bin/env python3
"""shopify - generisches Shopify-Modul. Ueberwacht alle in
config/shopify_sites.txt gelisteten Shops (eine Domain je Zeile) mit der
gemeinsamen Shopify-Engine aus shopify_core."""
from __future__ import annotations

import sys
from pathlib import Path

from modules import shopify_core as core
from modules.base import BaseModule

core.MODULE = "shopify"

from modules.shopify_core import (ENV, ROOT, CONSOLE, Settings, State, Notifier,
                                  ProxyPool, Solver, load_profiles, setup_log,
                                  cmd_selftest, main as core_main, ShopifyModule)
MODULE = "shopify"


def shopify_sites() -> list[str]:
    p = ROOT / "config" / "shopify_sites.txt"
    out: list[str] = []
    if p.exists():
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                out.append(line)
    return out


def main(argv=None):
    sites = shopify_sites()
    if not sites:
        CONSOLE.print("[red]config/shopify_sites.txt ist leer. Eine Domain je "
                      "Zeile eintragen.[/]")
        return 1
    cfg = Settings.load()
    cfg.hosts = sites
    cfg.monitor_sources = ["sitemap", "storefront"]
    cfg.state_db = "var/shopify.sqlite"
    ap = core.argv_parser(MODULE)
    a = ap.parse_args(argv)
    if a.cmd == "setup":
        core.cmd_setup()
        return 0
    if a.cmd == "install-browser":
        import subprocess
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])
        return 0
    setup_log(cfg)
    state = State(str(cfg.path(cfg.state_db)))
    pool = ProxyPool(state, MODULE)
    notifier = Notifier(ENV.get("DISCORD_WEBHOOK", ""), ENV.get("DISCORD_WEBHOOK_ERRORS", ""))
    solver = Solver(cfg)
    if a.cmd == "profiles-check":
        for p in load_profiles(MODULE):
            iss = p.issues()
            CONSOLE.print(f"{p.id}: {'ok' if not iss else ','.join(iss)}")
    elif a.cmd == "stats":
        CONSOLE.print(__import__("asyncio").run(state.stats()))
    elif a.cmd == "selftest":
        __import__("asyncio").run(cmd_selftest(cfg, state, pool, notifier))
    elif a.cmd == "watch":
        hosts = [h.strip() for h in a.hosts.split(",") if h.strip()] or cfg.hosts
        __import__("asyncio").run(core.cmd_watch(cfg, state, pool, notifier,
                                                 solver, a.mode, hosts))
    elif a.cmd == "drop":
        __import__("asyncio").run(core.cmd_drop(cfg, state, pool, notifier, solver,
                                                a.host, a.variant, a.tasks, a.qty,
                                                a.mode, a.card_http))
    return 0


class ShopifyGenericModule(ShopifyModule):
    title = "Shopify generisch"

    def call(self, argv) -> int:
        try:
            return main(list(argv)) or 0
        except KeyboardInterrupt:
            CONSOLE.print("[yellow]abgebrochen[/]")
            return 130
        except SystemExit as e:
            return e.code if isinstance(e.code, int) else (0 if e.code is None else 1)


if __name__ == "__main__":
    sys.exit(ShopifyGenericModule().call(sys.argv[1:]))