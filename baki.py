#!/usr/bin/env python3
"""Baki AIO - Startpunkt. Banner und Menue 1-14 / 0. Platz 1: Topps."""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

SLOTS = 14

CRASHLOG = Path(__file__).resolve().parent / "crashlog.log"


def _excepthook(typ, val, tb):
    try:
        with CRASHLOG.open("a", encoding="utf-8") as f:
            f.write("\n--- " + __import__("time").strftime("%Y-%m-%d %H:%M:%S") + " ---\n")
            traceback.print_exception(typ, val, tb, file=f)
    except Exception:
        pass
    traceback.print_exception(typ, val, tb)


sys.excepthook = _excepthook


def _topps():
    # Import erst bei Auswahl, damit das Menue sofort erscheint.
    from modules.topps import ToppsModule
    return ToppsModule()


def _nike():
    from modules.nike_gen import NikeModule
    return NikeModule()


def _amazon():
    from modules.amazon_gen import AmazonModule
    return AmazonModule()


def _riftbound():
    from modules.riftbound_gen import RiftboundModule
    return RiftboundModule()


def _pokemon():
    from modules.pokemoncenter import PokemonCenterModule
    return PokemonCenterModule()


def _toolbox():
    from modules.toolbox import ToolboxModule
    return ToolboxModule()


# Menueplatz -> (Text, Fabrik fuer das Modul). Freie Plaetze fehlen hier.
MODULES = {
    1: ("Topps EU", _topps),
    2: ("Nike Account Generator", _nike),
    3: ("Amazon Account Generator", _amazon),
    4: ("Riftbound Account Generator", _riftbound),
    5: ("Pokemon Center", _pokemon),
    6: ("Toolbox", _toolbox),
}

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
    return "\n" + text.strip("\n").rstrip() + "\n"


def show_menu() -> None:
    print(banner())
    print(" " + "=" * 50)
    for i in range(1, SLOTS + 1):
        print(f"  {i:>2}  {MODULES[i][0] if i in MODULES else '-'}")
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
        if wahl.isdigit() and int(wahl) in MODULES:
            try:
                MODULES[int(wahl)][1]().run()
            except Exception as e:  # ein Fehler im Modul soll das Menue nicht beenden
                print(f" Fehler: {type(e).__name__}: {e}")
        elif wahl.isdigit() and 1 <= int(wahl) <= SLOTS:
            print(f" {int(wahl)}: noch nicht belegt.")
        else:
            print(" Ungueltige Auswahl.")


def main() -> int:
    return menu()


if __name__ == "__main__":
    sys.exit(main())
