# STATE (nach Schritt 15c, 2026-11-20)

Stand:
- core/ und modules/ mit leerer __init__.py (15a); modules/base.py nur `BaseModule.run()` (15b).
- baki.py: Banner (pyfiglet ansi_shadow, Hardcode-Fallback ansi_shadow, sonst ASCII), Menue 1-14 (alle `-`) und 0, input; keine Modul-Logik, keine Argumente (15c).

Offene Punkte:
- modules/topps_module.py importiert Action/Module aus modules.base (gibt es nicht) -> laeuft nicht.
- toppsfarm.py fehlt im Repo (Logik liegt in modules/topps.py), Weiterleitung fehlt; README beschreibt noch Registry/Direktaufruf.
- START.bat ruft `baki.py topps setup` auf, baki.py ignoriert Argumente; Exe/START.bat noch nicht final (15e); Banner im echten Konsolenfenster ungeprueft.

Naechster Schritt: 15d - ToppsModule(BaseModule) mit run() in modules/topps.py, Menuepunkt 1 in baki.py ruft sie auf, toppsfarm.py als duenne Weiterleitung.
