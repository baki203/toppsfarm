#!/usr/bin/env python3
"""Baki AIO - Startpunkt. Banner, Menue 1-14 und Weitergabe an die Module.

  baki.py                  Menue
  baki.py <modul> <args>   Modul direkt, z. B.  baki.py topps selftest
"""
from __future__ import annotations

import sys

import modules
from modules.base import Action, ask, pause

SLOTS = 14

# Hardcode-Fallback (pyfiglet "standard"), reines ASCII, laeuft in jeder Codepage.
BANNER_ASCII = r"""
 ____    _    _  _____      _    ___ ___
| __ )  / \  | |/ /_ _|    / \  |_ _/ _ \
|  _ \ / _ \ | ' / | |    / _ \  | | | | |
| |_) / ___ \| . \ | |   / ___ \ | | |_| |
|____/_/   \_\_|\_\___| /_/   \_\___\___/
"""


def banner() -> str:
    """ansi_shadow ueber pyfiglet; ohne pyfiglet/Font oder wenn die Konsole
    die Blockzeichen nicht darstellen kann, der Hardcode-Banner."""
    try:
        import pyfiglet
        text = pyfiglet.figlet_format("BAKI AIO", font="ansi_shadow")
        text.encode(sys.stdout.encoding or "ascii")
        return "\n" + text.rstrip() + "\n"
    except Exception:
        return BANNER_ASCII


def menu_entries() -> list:
    """(Modul-Kurzname, Action) je Menueplatz, aufgefuellt auf SLOTS Plaetze."""
    entries = []
    for key in modules.KEYS:
        mod = modules.load(key)
        entries += [(key, a) for a in mod.actions]
    entries = entries[:SLOTS]
    return entries + [None] * (SLOTS - len(entries))


def run_module(key: str, argv: list) -> int:
    mod = modules.load(key)
    if mod is None:
        print(f"Unbekanntes Modul: {key}. Vorhanden: {', '.join(modules.KEYS)}")
        return 2
    return mod.run(argv)


def run_action(key: str, action: Action) -> int:
    argv = list(action.argv)
    for opt, frage in action.prompts:
        wert = ask(f" {frage}: ")
        if not wert:
            print(" abgebrochen")
            return 1
        argv += [opt, wert]
    return run_module(key, argv)


def menu() -> int:
    entries = menu_entries()
    text = banner()
    while True:
        print(text)
        print(" " + "=" * 50)
        for i, e in enumerate(entries, 1):
            print(f"  {i:>2}  {e[1].title if e else '-'}")
        print("   0  Ende")
        print(" " + "=" * 50)
        try:
            wahl = input(" Auswahl: ").strip()
        except (EOFError, KeyboardInterrupt):
            return 0
        if wahl == "0":
            return 0
        if not wahl.isdigit() or not 1 <= int(wahl) <= SLOTS:
            continue
        e = entries[int(wahl) - 1]
        if e is None:
            print(" Platz nicht belegt.")
        else:
            run_action(*e)
        pause()


def main() -> int:
    if len(sys.argv) > 1:
        return run_module(sys.argv[1], sys.argv[2:])
    return menu()


if __name__ == "__main__":
    sys.exit(main())
