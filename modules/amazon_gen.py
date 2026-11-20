#!/usr/bin/env python3
"""Amazon-Account-Generator (amazon.de), analog zu Nike."""
from __future__ import annotations

import asyncio

from modules.account_base import AccountGenerator, run_generator


class AmazonGen(AccountGenerator):
    site = "amazon"
    signup_url = "https://www.amazon.de/ap/register"
    account_dir = "accounts/Amazon"


class AmazonModule:
    title = "Amazon Account Generator"

    def run(self):
        try:
            n = int(input(" Anzahl Konten [1]: ").strip() or "1")
        except ValueError:
            n = 1
        headless = input(" Headless (j/n) [j]: ").strip().lower() != "n"
        try:
            asyncio.run(run_generator(AmazonGen(count=n, headless=headless)))
        except KeyboardInterrupt:
            print("\n abgebrochen.")


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(run_generator(AmazonGen(count=1, headless=True))))