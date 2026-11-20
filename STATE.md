# STATE (nach Schritt 15e, 2026-11-20)
Stand:
- 15a-15e abgehakt. `dist\BakiAIO.exe` (60296751 Bytes, 03:42) neu gebaut aus `BakiAIO.spec`, enthaelt Menue + ToppsModule (Platz 1), 2-14 leer.
- START.bat startet baki.py (.venv) bzw. BakiAIO.exe ohne Argumente; bei fehlender profiles.yaml nur noch Hinweiszeile.
- Getestet per Eingabedatei: Exe und START.bat, Menue 1 -> Topps-Untermenue, Statistik, Profile pruefen, zurueck, Ende. Exitcode 0.
- Alte dist\toppsfarm.exe und toppsfarm.spec geloescht (unversioniert).

Offene Punkte:
- Nichts im echten Konsolenfenster geprueft (Banner ansi_shadow in der Exe, Doppelklick START.bat); Selftest/Watch/Drop/Setup aus der Exe nicht getestet.
- release.zip ist alt (noch toppsfarm.exe), neu erst mit Schritt 29.
- Schritte 16-24 (erfundene Identitaeten, Fingerprint-/Bot-Erkennungs-Umgehung, Massen-Account-Generatoren): siehe Hinweis in STATUS.md, vor dem Loop klaeren.

Naechster Schritt: 16 - core/identity.py (siehe offener Punkt, wird voraussichtlich abgelehnt).
