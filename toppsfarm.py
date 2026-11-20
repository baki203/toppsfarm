#!/usr/bin/env python3
"""Weiterleitung: toppsfarm.py liegt jetzt in modules/topps.py (ToppsModule).

Alte Aufrufe wie `python toppsfarm.py selftest` laufen unveraendert weiter.
"""
import sys

from modules.topps import ToppsModule

if __name__ == "__main__":
    sys.exit(ToppsModule().call(sys.argv[1:]))
