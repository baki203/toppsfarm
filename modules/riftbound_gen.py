#!/usr/bin/env python3
"""Riftbound-Account-Generator, analog zu Nike."""
from __future__ import annotations

import asyncio

from modules.account_base import AccountGenerator, run_generator


class RiftboundGen(AccountGenerator):
    site = "riftbound"
    signup_url = "https://riftbound.com/register"
    account_dir = "accounts/Riftbound"


class RiftboundModule:
    title = "Riftbound Account Generator"

    def run(self):
        try:
            n = int(input(" Anzahl Konten [1]: ").strip() or "1")
        except ValueError:
            n = 1
        headless = input(" Headless (j/n) [j]: ").strip().lower() != "n"
        try:
            asyncio.run(run_generator(RiftboundGen(count=n, headless=headless)))
        except KeyboardInterrupt:
            print("\n abgebrochen.")


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(run_generator(RiftboundGen(count=1, headless=True))))