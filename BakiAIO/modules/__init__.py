"""Alias-Pfade fuer die Skyridge-Struktur.

Alte Importe wie ``from modules.topps import ToppsModule`` oder
``from modules.Engine.Shopify.shopify_core import ...`` funktionieren weiter: Sie werden
hier auf die neuen Orte unter ``modules/Engine`` und
``modules/Generators/<Site>/modules/<Feature>`` umgeleitet.
"""
from __future__ import annotations

import sys

_ALIASES = {
    "modules.quality": "utilities.quality",
    "modules.shopify_core": "modules.Engine.Shopify.shopify_core",
    "modules.retail_core": "modules.Engine.Retail.retail_core",
    "modules.topps": "modules.Generators.Topps.modules.Drop.DropModule",
    "modules.nike_gen": "modules.Generators.Nike.modules.FCFS.FCFSModule",
    "modules.amazon_gen": "modules.Generators.Amazon.AmazonAIO",
    "modules.amazon_aio": "modules.Generators.Amazon.AmazonAIO",
    "modules.riftbound_gen": "modules.Generators.Riftbound.modules.RaffleEntry.RaffleEntryModule",
    "modules.pokemoncenter": "modules.Generators.PokemonCenter.modules.QueueCheckout.QueueCheckoutModule",
    "modules.toolbox": "modules.Generators.Toolbox.modules.ProxyTest.ProxyTestModule",
    "modules.psn": "modules.Generators.PSN.modules.QueueCheckout.QueueCheckoutModule",
    "modules.mediamarkt": "modules.Generators.MediaMarkt.modules.Monitor.MonitorModule",
    "modules.saturn": "modules.Generators.Saturn.modules.Monitor.MonitorModule",
    "modules.snkrs": "modules.Generators.Nike.modules.SNKRS.SNKRSModule",
    "modules.smyths": "modules.Generators.Smyths.modules.Monitor.MonitorModule",
    "modules.shopify": "modules.Generators.Shopify.modules.GuestCheckout.GuestCheckoutModule",
}

for _old, _new in _ALIASES.items():
    if _old not in sys.modules:
        try:
            sys.modules[_old] = __import__(_new, fromlist=["*"])
        except Exception:
            pass

