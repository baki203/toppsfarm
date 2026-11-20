# STATE (nach Schritt 15b, 2026-11-20)

Stand:
- core/ und modules/ mit leerer __init__.py (15a).
- modules/base.py: nur `class BaseModule` mit `run(self)` (raise NotImplementedError) (15b).

Offene Punkte:
- baki.py und modules/topps_module.py importieren Action/Module/ask/pause aus modules.base, die es nicht mehr gibt -> beide laufen nicht (15c/15d).
- baki.py nutzt modules.KEYS / modules.load, modules/__init__.py ist leer.
- toppsfarm.py fehlt im Repo (liegt als modules/topps.py), Weiterleitung fehlt; START.bat/Exe noch nicht final (15e).

Naechster Schritt: 15c - baki.py neu: Banner (pyfiglet ansi_shadow + Hardcode-Fallback), Menue 1-14 und 0, input, ohne Modul-Logik.
