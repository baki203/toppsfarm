#!/usr/bin/env python3
"""Baki AIO - Startpunkt. Banner und Menue 1-14 / 0. Platz 1: Topps."""
from __future__ import annotations

import sys
from pathlib import Path

from utilities.logger.CrashLogger import CrashLogger

SLOTS = 14

CRASHLOG = Path(__file__).resolve().parent / "crashlog.log"

CrashLogger(CRASHLOG).install()


def _auto_update() -> None:
    """EXE-Auto-Update: Ist neben der laufenden BakiAIO.exe eine BakiAIO.exe.new
    abgelegt (z. B. nach einem Neu-Build), ersetzt dieser Aufruf sie und meldet es.
    Onefile entpackt sich nach _MEIPASS, daher ist die Datei am Original-Pfad
    waehrend der Laufzeit ersetzbar. Im Source-Betrieb (kein frozen) keine Aktion."""
    try:
        if not getattr(sys, "frozen", False):
            return
        exe = Path(sys.executable)
        new = exe.with_name(exe.name + ".new")
        if not new.exists():
            return
        backup = exe.with_name(exe.name + ".old")
        import os
        try:
            os.replace(exe, backup)   # laufende EXE wegsichern
            os.replace(new, exe)      # neue Version an den Platz
        except OSError:
            return
        print(" Update: neue BakiAIO.exe installiert. Bitte erneut starten.")
    except Exception:
        pass


def _topps():
    # Import erst bei Auswahl, damit das Menue sofort erscheint.
    from modules.Generators.Topps.modules.Drop.DropModule import ToppsModule
    return ToppsModule()


def _nike():
    from modules.Generators.Nike.modules.FCFS.FCFSModule import NikeModule
    return NikeModule()


def _amazon():
    from modules.Generators.Amazon.modules.Invites.InvitesModule import AmazonModule
    return AmazonModule()


def _riftbound():
    from modules.Generators.Riftbound.modules.RaffleEntry.RaffleEntryModule import RiftboundModule
    return RiftboundModule()


def _pokemon():
    from modules.Generators.PokemonCenter.modules.QueueCheckout.QueueCheckoutModule import PokemonCenterModule
    return PokemonCenterModule()


def _toolbox():
    from modules.Generators.Toolbox.modules.ProxyTest.ProxyTestModule import ToolboxModule
    return ToolboxModule()


def _psn():
    from modules.Generators.PSN.modules.QueueCheckout.QueueCheckoutModule import PlayStationModule
    return PlayStationModule()


def _mediamarkt():
    from modules.Generators.MediaMarkt.modules.Monitor.MonitorModule import MediaMarktModule
    return MediaMarktModule()


def _saturn():
    from modules.Generators.Saturn.modules.Monitor.MonitorModule import SaturnModule
    return SaturnModule()


def _snkrs():
    from modules.Generators.Nike.modules.SNKRS.SNKRSModule import SNKRSModule
    return SNKRSModule()


def _smyths():
    from modules.Generators.Smyths.modules.Monitor.MonitorModule import SmythsModule
    return SmythsModule()


def _shopify():
    from modules.Generators.Shopify.modules.GuestCheckout.GuestCheckoutModule import ShopifyGenericModule
    return ShopifyGenericModule()


# Menueplatz -> (Text, Fabrik fuer das Modul). Freie Plaetze fehlen hier.
MODULES = {
    1: ("Topps EU", _topps),
    2: ("Pokemon Center", _pokemon),
    3: ("Nike Account Generator", _nike),
    4: ("Amazon Account Generator", _amazon),
    5: ("Riftbound Account Generator", _riftbound),
    6: ("PlayStation DE", _psn),
    7: ("MediaMarkt", _mediamarkt),
    8: ("Saturn", _saturn),
    9: ("Nike SNKRS", _snkrs),
    10: ("Smyths Toys", _smyths),
    11: ("Shopify generisch", _shopify),
    12: ("Toolbox", _toolbox),
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
    _auto_update()
    return menu()


if __name__ == "__main__":
    sys.exit(main())
