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
