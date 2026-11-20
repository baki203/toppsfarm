# STATE (nach Schritt 15d, 2026-11-20)
Stand:
- 15a-15d abgehakt. modules/topps.py enthaelt `ToppsModule(BaseModule)` mit Untermenue (run) und Befehlsaufruf (call); baki.py Menuepunkt 1 = Topps EU, 2-14 leer.
- toppsfarm.py ist nur noch Weiterleitung (`python toppsfarm.py <befehl>` laeuft wie frueher). modules/topps_module.py geloescht.
- Getestet per Pipe: Menue 1 -> Untermenue, Statistik, Profile pruefen, Weiterleitung. Exitcode 0, keine Fehler.

Offene Punkte:
- Selftest/Watch/Drop/Setup ueber das Untermenue nicht getestet; nichts im echten Konsolenfenster geprueft.
- START.bat ruft noch `baki.py topps setup` auf (baki.py kennt keine Argumente); dist\BakiAIO.exe hat den Stand 15d nicht (15e).
- Schritte 16-24 (erfundene Identitaeten, Fingerprint-/Bot-Erkennungs-Umgehung, Massen-Account-Generatoren): siehe Hinweis in STATUS.md, vor dem Loop klaeren.

Naechster Schritt: 15e - Exe als BakiAIO bauen, START.bat auf baki.py umstellen, Menue testen.
