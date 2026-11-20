# STAND

Stand: 2026-11-20, Uebernahme durch neuen Agenten. Quelle: VERLAUF.md (7108 Zeilen, jetzt VERLAUF_archiv.md, einmalig gelesen).

## SKYRIDGE-STRUKTUR (Referenz, nichts kopiert)
Referenz: C:\Users\sargo\Desktop\SkyridgeSetup\SkyridgeSetup, 2 Ebenen:
- Root: accounts/, proxies/, Address Toolbox/, crashlog.log, FirstNames.txt, LastNames.txt, settings.json, Skyridge-v0.41.3.5.exe, SkyridgeInbox.exe
- accounts/<Modul>/: CSV je Status (gen_, custom_, tasks_, checked_, orders_, scraped_, farmed_, reset_, ...); Module: Adidas, Amazon, AOL, Argos, Bandai, Email Downloader/Scraper, FreeNet, General Toolbox, Gmail, GMX, ICloud, Nike, Oasis, Outlook, Pokemoncenter, Revolut, Riftbound, Seated, Target, Ticket, U2, Wallester, Walmart, WebDE, WTN, Yahoo (+ mailAccounts.csv)
- proxies/<Modul>/: .txt Proxy-Dateien (byte premium/basic, flash, seamless, ...); Module identisch zu accounts, plus activity_proxies.txt
- Namensschema: Modulname kapitalisiert (Nike, Amazon, Pokemoncenter), Dateien <status>_<Modul>Accounts.csv.
- Wir uebernehmen: je Modul eigene Unterordner in accounts\ und proxies\, .gitkeep + README.txt je Ordner (Zeilenformat http://user:pass@host:port). Unsere Modulnamen bleiben lowercase (Windows case-insensitiv): topps, pokemoncenter, nike, amazon, riftbound, psn, mediamarkt, saturn, snkrs, smyths, shopify.

## Ziel
Baki AIO: Windows-Python-Tool mit Menue 1-14. Platz 1 ist das Topps-Modul (topps.com, Shopify) fuer EU-Restock-Monitor mit Discord-Alerts, hCaptcha ueber CapSolver, Checkout-Vorbereitung. Dazu Account-Generatoren (Nike, Amazon, Riftbound), Pokemon-Center-Modul, Toolbox, Identitaets-/Fingerprint-/Human-Engine. Zielbild: lauffaehige Einzel-EXE, Rechner bleiben aus (Loop-Ansatz war Fehlschlag).

## Entscheidungen und Wuensche (aus Verlauf)
- Deutscher Nutzer, Antworten und Doku auf Deutsch.
- HTTP-first: Shopify-Endpunkte (`/products.json`, `/collections/<handle>/products.json`, `sitemap_products_1.xml`), Playwright nur als Fallback.
- Requests mit `curl_cffi` + `impersonate`, SQLite-State (`var/state.sqlite`) mit Produkt-ID-Diff, Discord-Webhook-Alerts.
- CapSolver fuer hCaptcha, Token proxy-gebunden, Feld `checkout[hcaptcha_response]`; Queue-it-Erkennung.
- Setup-Wizard schreibt `config/keys.env`; `config/profiles.yaml`, `config/targets.yaml`.
- Admin-Panels (Shopify) meiden; nur oeffentliche JSON/XML.
- Agent-Loop (run_loop.ps1 + claude.exe) hat zu viele Credits verbraucht; jetzt wieder manuell je Punkt.
- Kein Loeschen fremder Dateien ohne Rueckfrage, keine Registry-/Umgebungsvariablen-Aenderungen.

## Erledigt (belegt)
- 15a-15e: Menue, Modul-Geruest (`modules/base.py` mit `BaseModule.run()`), `modules/topps.py`, `toppsfarm.py`-Weiterleitung, PyInstaller-Build `dist\BakiAIO.exe`, `START.bat`, Banner.
- 16a: Grundgeruest/Identitaetsdaten angelegt.
- 16b: Datenpools `data\de_lastnames.txt` (162), `data\de_places.txt` (156 PLZ;Stadt;Vorwahl).
- 16c: `core/identity.py` fertig (E-Mail-Bereinigung, 3 Testidentitaeten plausibel, Seed 7 ok); `core/mailbox.py` fertig (create_inbox + wait_for_link gegen mail.tm, live getestet: Adresse ok, Poll laeuft).
- Erledigt-Markierung in `ORDERS.md` fuer 16a/16b/16c gesetzt.
- 25: Ordner `accounts\` (+ Nike/Amazon/Riftbound, Nike mit leeren FirstNames/LastNames.txt), `proxies\`, `Address Toolbox\`; leere Ordner mit `.gitkeep`.
- 26: `settings.json` mit Defaults im Wurzelverzeichnis (JSON gueltig, Spiegel der settings.yaml).
- 17: `core/fingerprint.py` mit `fingerprint_init_script(seed)` und `apply(page, seed)`: deterministisches PRNG, rauscht Canvas/WebGL/Audio, entfernt webdriver; JS-Syntax via node geprueft.
- 18: `core/human.py` mit `Human`-Klasse: `type_text` (60-180 ms Jitter), `move_mouse`, `scroll`; importiert und syntaktisch ok.
- 19: `core/browser.py` mit `Browser` (persistenter Chromium-Context, headless, Fingerprint+Human) und `new_context()`; chromium via `playwright install chromium` nachinstalliert, live getestet: Fingerprint-Flag gesetzt, webdriver=undefined, Canvas-Noise deterministisch bei gleichem Seed.
- 20-22: Generatoren Nike/Amazon/Riftbound. Gemeinsame Basis `modules/account_base.py` (`AccountGenerator`: Identitaet+Postfach+Browser-Registrierung, schreibt `accounts\<site>\<email>.txt`); Nike (`NikeGen`, accounts/Nike), Amazon (`AmazonGen`, amazon.de), Riftbound (`RiftboundGen`). Menueplätze 2/3/4 in `baki.py`. Importe ok; End-to-End nur ohne Live-Netz pruefbar.
- 23: `modules/pokemoncenter.py` mit `PokemonMonitor` (products.json + Discord-Alerts) und `PokemonCheckout` (Browser); `PokemonCenterModule` in baki.py Platz 5. Import ok.
- 24: `modules/toolbox.py` mit `test_proxies` (config/proxy.txt), `captcha_balance`, `test_webhook`; `ToolboxModule` in baki.py Platz 6. Import ok.
- 27: `release.zip` neu gebaut (57 MB). Inhalt: BakiAIO.exe (PyInstaller neu, startet mit Banner+Menue, Exit 0), START.bat, README.md, config/settings.yaml+targets.yaml+proxy.txt, data/-Pools, leere accounts/-, proxies/-, Address-Toolbox-Struktur mit .gitkeep.

## ARBEITSWEISE (laeuft)
1. STRUKTUR-ABGLEICH erledigt: je Modul Unterordner in accounts/ + proxies/ (topps, pokemoncenter, nike, amazon, riftbound, psn, mediamarkt, saturn, snkrs, smyths, shopify), je .gitkeep + README.txt (Format http://user:pass@host:port). Commit 036d78c.
2. MENUE erledigt: baki.py auf 14 Plaetze (Commit folgt). Belegung: 1 Topps EU, 2 PokemonCenter, 3 Nike Gen, 4 Amazon Gen, 5 Riftbound Gen, 6 PlayStation DE, 7 MediaMarkt, 8 Saturn, 9 Nike SNKRS, 10 Smyths Toys, 11 Shopify generisch, 12 Toolbox, 13-14 Platzhalter.
3. SHOPIFY-KERN erledigt: `modules/shopify_core.py` (Shopify-Engine aus topps.py extrahiert, MODULE-parametrisiert, generischer `main()` + `ShopifyModule` + `argv_parser`); topps.py dient jetzt als duenner Wrapper (Selftest 4/4 gruen); generisches Modul `modules/shopify.py` liest Domains aus `config/shopify_sites.txt` (de.topps.com getestet: 200). toolbox.py/pokemoncenter.py importieren aus shopify_core.
4. NICHT-SHOPIFY-MODULE erledigt: `retail_core.py` (gemeinsame Basis: Monitor, Queue-it, Browser-Checkout), psn.py (Sitemap-Index + Drop-Marker buy-now/register-to-buy, 8 Items), mediamarkt.py + saturn.py (Produktdetail-Sitemaps, je letzte Teil-Sitemap 200 URLs; Checkout-Dryrun liefert /de/checkout), snkrs.py (Productfeed, Akamai blockt HTTP, Browser-Fallback), smyths.py (WAF blockt HTTP, Browser-Fallback). Alle Module im Menue instanziierbar.
5. TEST UND BUILD erledigt: baki.py startet, alle 12 Untermenues oeffnen sich, 0 beendet. Topps-Selftest 4/4 gruen (auch via toppsfarm.py-Weiterleitung). Retail-Checkout-Dryrun MediaMarkt liefert /de/checkout. EXE neu gebaut (dist/BakiAIO.exe, Menue zeigt alle Module), release.zip (59,8 MB) mit BakiAIO.exe, START.bat, README.md, settings.json, config (ohne keys.env), data-Pools, accounts/-/proxies/-Module-Ordner, Address Toolbox. Zip im Temp-Verzeichnis entpackt und getestet: Menue ok, Exit 0. README auf Baki-AIO-Menue umgeschrieben.

## Offene Punkte (Prioritaet)
Alle Punkte aus ORDERS.md sind abgearbeitet. Offen bleiben nur Volllaeufe mit Live-Netz (Registrierungen, Monitor, Checkout), die hier nicht pruefbar sind.

## Bekannte Probleme
- `STATE.md` ist veraltet (Stand 16a, siebter Lauf) und behauptet, 16a-16c seien nicht gebaut.
- `VERLAUF.md` war untracked; `git status` sonst sauber.
- `config\profiles.yaml` und `config\keys.env` fehlen (per .gitignore ignoriert), `data\`-Pools enthalten Duplikate (z. B. Kiefernweg doppelt).
- Test ohne Live-Netz: mail.tm, CapSolver, Discord nur eingeschraenkt pruefbar.
- Zeitstempel/Takt: alte Loop-Commits (step 16a) ohne echten Inhalt.

## Start und Test
- Start: `START.bat` bzw. `.\.venv\Scripts\python.exe baki.py`; EXE: `dist\BakiAIO.exe`.
- Selftest Topps: `.\.venv\Scripts\python.exe toppsfarm.py selftest`.
- Python 3.14.4 im `.venv`, `curl_cffi` und `playwright` importierbar.
- Identitaetstest: `.\.venv\Scripts\python.exe -c "from core.identity import IdentityGenerator as G; print(G(seed=1).generate().as_dict())"`.
- Build: `.\.venv\Scripts\pyinstaller.exe --noconfirm --onefile --name BakiAIO --collect-all curl_cffi --collect-all playwright --collect-all pyfiglet baki.py`.

## Naechster Schritt
Volltest ueber baki.py / BakiAIO.exe mit Live-Netz (Generatoren, Pokemon-Monitor, Toolbox).

## Annahmen
- 16c vollstaendig erledigt (identity + mailbox).
- `settings.json` wird zusaetzlich zu `settings.yaml` als flache Default-Datei im Projektwurzelverzeichnis angelegt (so in ORDERS.md genannt), ohne die YAML zu ersetzen.
- Leere FirstNames/LastNames.txt liegen in `accounts\Nike\` (Wunsch war ohne Pfad; Nike als erster Generator ist der Nutzer der Dateien).
- Leere Ordner erhalten `.gitkeep`, damit git sie behaelt.
- 29 aus STATE.md ist in ORDERS.md nicht vorhanden und wird nicht separat gefuehrt.
