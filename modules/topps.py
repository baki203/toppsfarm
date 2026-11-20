#!/usr/bin/env python3
"""topps - Topps EU Modul. Setzt den Modulnamen und nutzt die gemeinsame
Shopify-Engine aus shopify_core. HTTP-first, Browser nur Fallback."""
from __future__ import annotations

import sys

from modules import shopify_core as core
from modules.base import BaseModule

core.MODULE = "topps"

from modules.shopify_core import (ENV, ROOT, CONSOLE, LOG, UA, COLORS,
                                  Settings, Profile, load_env, load_profiles,
                                  load_targets, setup_log, Notifier, ProxyPool,
                                  State, Solver, session, headers, base_headers,
                                  warm, queued, cf_cookies, cf_refresh,
                                  products_json, storefront_products,
                                  sitemap_new, HttpCheckout, BrowserCheckout,
                                  Monitor, Orchestrator, cmd_setup, cmd_selftest,
                                  cmd_watch, cmd_drop, main as core_main,
                                  ShopifyModule)
MODULE = "topps"


def main(argv=None):
    return core_main(argv)


class ToppsModule(ShopifyModule):
    title = "Topps EU"
    actions = ShopifyModule.actions


if __name__ == "__main__":
    sys.exit(ToppsModule().call(sys.argv[1:]))