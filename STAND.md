# STAND
Stand 2026-11-20, ARBEITSWEISE (8 Punkte). Deutsch. Je Punkt: Test + STAND.md + commit + push.

## BLOCKER
- Skyridge-GitBook auth-geschuetzt (SPA nur JS-Shell, Content-API 403, kein Wayback-Mirror). Erkenntnisse stattdessen aus lokaler settings.json + crashlog.log (PyInstaller-Tracebacks) + PepperScripts-Doku.

## Stand Punkte
1 STRUKTUR: erledigt. accounts\ + proxies\ je Modul (topps, pokemoncenter, nike, amazon, riftbound, psn, mediamarkt, saturn, snkrs, smyths, shopify), je .gitkeep + README.txt (Format http://user:pass@host:port). Verifiziert.
2 SKYRIDGE LERNEN: erledigt. KNOWLEDGE.md: settings-Schema (Captcha/SMS-Provider, Geocoder, Mastermails+Catchall), Amazon (ADDRESS/SECRET/MONITOR-AWAIT, Adresse in 2. Session, Karte erst beim Kauf, Retry=SECRET, keine gleiche CC/Adresse ueber Konten), Nike SNKRS (FAST/SHOCK, ENTRY TIME, Browser zwingend, Billing==Shipping), Nike FCFS, Shopify (Preload, Shop <CC>-Regionen), PokemonCenter. Committet.
3 QUALITY.md: erledigt. QUALITY.md mit A1..A10-Pruefliste (Catch-All statt Wegwerf, persistentes Profil je Konto, sticky Wohn-IP je Konto, IP-Land/Region zur Adresse, Adressvariation, Browsen vor Registrierung, Adresse in 2. Session, Karte erst beim Kauf, Erstkauf klein/zeitversetzt, Telefon nur auf Aufforderung) + Messpunkten (attempts/success/banned/retries, Sperrquote %, Modulende-Ausgabe, var/quality.sqlite, Schwelle >25%). Umsetzung: modules/quality.py (Quality-Klasse, --quality-CLI), eingebunden in retail_core + account_base. Committet.
4 MENUE: erledigt (14 Plaetze, Belegung aus altem STAND).
5 SHOPIFY-KERN: erledigt (shopify_core.py, topps.py Wrapper, shopify.py generisch).
6 NICHT-SHOPIFY: erledigt (retail_core.py + psn/mediamarkt/saturn/snkrs/smyths).
7 TEST+BUILD: (offen, wird am Ende erneut)
8 REIHENFOLGE: 2,3 -> 5 -> 4,6 -> 7. 5 vor 6 bei Zeitdruck.

## Erledigt (belegt, kompakt)
- Topps-Selftest 4/4 gruen; Menu 1-14 startet; MediaMarkt-Dryrun -> /de/checkout; release.zip (59,8 MB) getestet.
- Analyse-Werkzeuge: pyinstxtractor-ng (venv), UPX (winget). Main-EXE = .NET-Launcher (.fptable, 1x MZ); UPX/NSIS-Marker false positive; Inbox-EXE = Tauri (inbox.skyridge.eu).

## Naechster Schritt
Punkt 3: QUALITY.md schreiben (Ja/Nein-Pruefliste + Messpunkte Sperren/Sperrquote je Modul), commit+push. Danach Punkt 7 (Test+Build wiederholen, README ergaenzen).