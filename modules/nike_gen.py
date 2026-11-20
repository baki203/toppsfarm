#!/usr/bin/env python3
"""Nike-Account-Generator: Identitaet + Postfach + Registrierung."""
from __future__ import annotations

import asyncio

from modules.account_base import AccountGenerator, run_generator


class NikeGen(AccountGenerator):
    site = "nike"
    signup_url = "https://www.nike.com/de/launch/join"
    account_dir = "accounts/Nike"


class NikeModule:
    title = "Nike Account Generator"

    def run(self):
        try:
            n = int(input(" Anzahl Konten [1]: ").strip() or "1")
        except ValueError:
            n = 1
        headless = input(" Headless (j/n) [j]: ").strip().lower() != "n"
        try:
            asyncio.run(run_generator(NikeGen(count=n, headless=headless)))
        except KeyboardInterrupt:
            print("\n abgebrochen.")


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(run_generator(NikeGen(count=1, headless=True))))