# Baki AIO
Modulsystem. Start: `START.bat` oder `python baki.py` (Banner + Menue 1-14).

- `baki.py` - Startpunkt, Menue, Modul-Registry
- `core/` - gemeinsame Bausteine
- `modules/base.py` - Modul-Interface (`Module.run()`)
- `modules/topps.py` - Topps-EU-Monitor (frueher toppsfarm.py), `modules/topps_module.py` bindet ihn ins Menue ein

Direktaufruf ohne Menue: `python baki.py topps selftest` (alle bisherigen toppsfarm-Befehle).

## Topps
HTTP-first Topps-EU-Monitor. `setup` beim ersten Start ausfuellen.

Modi: cart (wenig Daten) / browser (Fallback).
Karte per API = `--card-http`, experimentell.

## Build
`.venv\Scripts\pyinstaller.exe --noconfirm --onefile --name BakiAIO --collect-all curl_cffi --collect-all playwright --collect-all pyfiglet baki.py`
