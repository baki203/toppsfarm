# Baki AIO
Modulsystem. Start: `START.bat` oder `python baki.py` (Banner + Menue 1-14).

- `baki.py` - Startpunkt, Menue, Platz 1 = Topps
- `core/` - gemeinsame Bausteine
- `modules/base.py` - Modul-Interface (`BaseModule.run()`)
- `modules/topps.py` - Topps-EU-Monitor (frueher toppsfarm.py) mit `ToppsModule(BaseModule)`, Untermenue ueber Menuepunkt 1
- `toppsfarm.py` - nur noch Weiterleitung auf `modules/topps.py`

Direktaufruf ohne Menue: `python toppsfarm.py selftest` (alle bisherigen toppsfarm-Befehle).

## Topps
HTTP-first Topps-EU-Monitor. `setup` beim ersten Start ausfuellen.

Modi: cart (wenig Daten) / browser (Fallback).
Karte per API = `--card-http`, experimentell.

## Build
`.venv\Scripts\pyinstaller.exe --noconfirm --onefile --name BakiAIO --collect-all curl_cffi --collect-all playwright --collect-all pyfiglet baki.py`
