#!/usr/bin/env python3
"""Baki AIO - Startpunkt. Banner und Menue 1-14 / 0. Noch ohne Modul-Logik."""
from __future__ import annotations

import sys

SLOTS = 14

# Hardcode-Fallback 1: ansi_shadow, fest eingetragen (falls pyfiglet oder der Font fehlt).
BANNER_SHADOW = """\
██████╗  █████╗ ██╗  ██╗██╗     █████╗ ██╗ ██████╗
██╔══██╗██╔══██╗██║ ██╔╝██║    ██╔══██╗██║██╔═══██╗
██████╔╝███████║█████╔╝ ██║    ███████║██║██║   ██║
██╔══██╗██╔══██║██╔═██╗ ██║    ██╔══██║██║██║   ██║
██████╔╝██║  ██║██║  ██╗██║    ██║  ██║██║╚██████╔╝
╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝    ╚═╝  ╚═╝╚═╝ ╚═════╝
"""

# Hardcode-Fallback 2: reines ASCII, falls die Konsole keine Blockzeichen ausgeben kann.
BANNER_ASCII = r"""
 ____    _    _  _____      _    ___ ___
| __ )  / \  | |/ /_ _|    / \  |_ _/ _ \
|  _ \ / _ \ | ' / | |    / _ \  | | | | |
| |_) / ___ \| . \ | |   / ___ \ | | |_| |
|____/_/   \_\_|\_\___| /_/   \_\___\___/
"""


def banner() -> str:
    """pyfiglet ansi_shadow, sonst der fest eingetragene Banner."""
    try:
        import pyfiglet
        text = pyfiglet.figlet_format("BAKI AIO", font="ansi_shadow", width=200)
    except Exception:
        text = BANNER_SHADOW
    try:
        text.encode(sys.stdout.encoding or "ascii")
    except (UnicodeError, LookupError):
        text = BANNER_ASCII
    return "\n" + text.strip("\n") + "\n"


def show_menu() -> None:
    print(banner())
    print(" " + "=" * 50)
    for i in range(1, SLOTS + 1):
        print(f"  {i:>2}  -")
    print("   0  Ende")
    print(" " + "=" * 50)


def menu() -> int:
    while True:
        show_menu()
        try:
            wahl = input(" Auswahl: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if wahl == "0":
            return 0
        if wahl.isdigit() and 1 <= int(wahl) <= SLOTS:
            print(f" {int(wahl)}: noch nicht belegt.")
        else:
            print(" Ungueltige Auswahl.")


def main() -> int:
    return menu()


if __name__ == "__main__":
    sys.exit(main())
