# STATUS

## Schritt 1 - ROOT-Pfad (2026-11-20)
Ergebnis: erledigt.
- `ROOT` in toppsfarm.py ersetzt (frozen -> Ordner der Exe, sonst Ordner des Skripts), darunter Fallback auf `ROOT.parent`, wenn `config` nur eine Ebene hoeher liegt (Fall `dist\toppsfarm.exe`).
- Schreibpfade geprueft, alle laufen ueber ROOT:
  - `config/keys.env` (cmd_setup) -> `ROOT / "config" / "keys.env"`
  - `config/profiles.yaml` (cmd_setup) -> `ROOT / "config" / "profiles.yaml"`
  - `var/state.sqlite` -> `cfg.path(cfg.state_db)` = `ROOT / rel`
  - `var/logs/run-*.log` -> `cfg.path(cfg.log_dir)` = `ROOT / rel`
- Keine Schreibzugriffe relativ zum Arbeitsverzeichnis gefunden.
Fehler: keine.

## Schritt 2 - config-Ordner in cmd_setup (2026-11-20)
Ergebnis: erledigt.
- `(ROOT / "config").mkdir(parents=True, exist_ok=True)` steht jetzt am Anfang von cmd_setup (vor keys.env) und noch einmal direkt vor dem Schreiben von profiles.yaml.
- `py_compile toppsfarm.py` laeuft ohne Fehler.
Fehler: keine.

## Schritt 3 - Exe bauen (2026-11-20)
Ergebnis: erledigt.
- Befehl: `.venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --name toppsfarm --collect-all curl_cffi --collect-all playwright toppsfarm.py`
- Exit-Code 0, kein Traceback, keine ERROR-Zeile im Build-Log.
- Letzte Zeile: `Build complete! The results are available in: C:\Users\sargo\Downloads\toppsfarm\dist`
- `dist\toppsfarm.exe`, 60285373 Bytes.
Fehler: keine.

## Schritt 4 - Selftest der Exe (2026-11-20)
Ergebnis: NICHT bestanden. Exe startet und laeuft ohne Traceback durch, aber de.topps.com liefert 403 statt 200.

Verlauf, drei Laeufe von `dist\toppsfarm.exe selftest`:

Lauf 1 - Traceback (behoben):
```
Traceback (most recent call last):
  File "toppsfarm.py", line 922, in <module>
    main()
  File "toppsfarm.py", line 898, in main
    setup_log(cfg)
  File "toppsfarm.py", line 151, in setup_log
    logging.FileHandler(d / f"run-{time.strftime('%Y%m%d-%H%M%S')}.log", encoding="utf-8")])
  File "logging\__init__.py", line 1219, in __init__
  File "logging\__init__.py", line 1248, in _open
FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\sargo\\Downloads\\toppsfarm\\var\\logs\\run-20261120-024225.log'
[PYI-30388:ERROR] Failed to execute script 'toppsfarm' due to unhandled exception!
```
Ursache: `Settings.path()` legt nur den Elternordner (`var`) an, nicht `var\logs` selbst. Fix: `d.mkdir(parents=True, exist_ok=True)` in setup_log.

Lauf 2 - ProxyError auf allen Hosts (behoben):
```
--- de.topps.com (ProxyError)
--- shop-de.topps.com (ProxyError)
--- es.topps.com (ProxyError)
--- fr.topps.com (ProxyError)
--- it.topps.com (ProxyError)
--- nl.topps.com (ProxyError)
--- at.topps.com (ProxyError)
--- be.topps.com (ProxyError)
--- pl.topps.com (ProxyError)
--- shop-uk.topps.com (ProxyError)
```
Ursache: `config\proxy.txt` beginnt mit UTF-8-BOM (EF BB BF). Die Kommentarzeile fing dadurch nicht mit `#` an und wurde als Proxy benutzt. Fix: proxy.txt und keys.env werden mit `utf-8-sig` gelesen, Kommentarpruefung auf der getrimmten Zeile.

Lauf 3 - aktueller Stand, direkt ohne Proxy:
```
--- de.topps.com (403)
--- shop-de.topps.com (403)
--- es.topps.com (403)
--- fr.topps.com (403)
--- it.topps.com (403)
--- nl.topps.com (DNSError)
--- at.topps.com (DNSError)
--- be.topps.com (DNSError)
--- pl.topps.com (DNSError)
--- shop-uk.topps.com (403)
```
- 403 auf `/products.json?limit=1` bei allen erreichbaren Hosts: der Shop lehnt die automatisierte Anfrage ab. Antwortinhalt nicht weiter untersucht.
- nl/at/be/pl.topps.com loesen per DNS nicht auf (Hostnamen existieren so nicht).
- Hier nicht weiter gegangen: den 403 zu umgehen hiesse, den Bot-Schutz des Shops auszuhebeln. Das wurde nicht versucht.

## Schritt 5 - cart-Flow (2026-11-20)
Ergebnis: nicht ausgefuehrt. Haengt an Schritt 4 (products.json liefert 403, keine Variant-ID abrufbar). Automatisierten Checkout gegen den Live-Shop wurde nicht debuggt.

## Schritt 6 - hCaptcha-Injektion (2026-11-20)
Ergebnis: nicht ausgefuehrt, nur Code gelesen, nichts geaendert. Stand im Code (HttpCheckout.run): zweiter POST auf `/checkouts/<token>` mit `_method=patch`, `authenticity_token` und `checkout[hcaptcha_response]=<token>`. Kein Live-Test.

## Schritt 7 - release.zip (2026-11-20)
Ergebnis: nicht gebaut. Vorhandene release.zip unveraendert gelassen, da Schritt 4 nicht bestanden ist.
