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

## Schritt 3 - Exe bauen, zweiter Durchlauf (2026-11-20)
Ergebnis: erledigt.
- Befehl: `.\.venv\Scripts\pyinstaller.exe --noconfirm --onefile --name toppsfarm --collect-all curl_cffi --collect-all playwright toppsfarm.py`
- Exit-Code 0, 0 Zeilen mit `Traceback` oder `ERROR` im Build-Log.
- Ende der Ausgabe:
```
33466 INFO: Copying 0 resources to EXE
33466 INFO: Embedding manifest in EXE
33500 INFO: Appending PKG archive to EXE
33571 INFO: Fixing EXE headers
33967 INFO: Building EXE from EXE-00.toc completed successfully.
33977 INFO: Build complete! The results are available in: C:\Users\sargo\Downloads\toppsfarm\dist
```
- `dist\toppsfarm.exe`, 60285173 Bytes, 20.11.2026 02:45:37.
- Enthaelt die Fixes aus Schritt 4 (var\logs anlegen, BOM-tolerantes Lesen von proxy.txt/keys.env).
Fehler: keine.

## Schritt 4 - Selftest, zweiter Durchlauf (2026-11-20)
Ergebnis: NICHT bestanden. Exe laeuft ohne Traceback (Exit-Code 0), de.topps.com liefert 403 statt 200.

Ausgabe von `.\dist\toppsfarm.exe selftest`, woertlich:
```
--- de.topps.com (403)
--- shop-de.topps.com (403)
--- es.topps.com (403)
--- fr.topps.com (403)
--- it.topps.com (403)
--- nl.topps.com (DNSError)
--- at.topps.com (Timeout)
--- be.topps.com (DNSError)
--- pl.topps.com (DNSError)
--- shop-uk.topps.com (Timeout)
```
Keine Profilzeilen, weil `config\profiles.yaml` nicht existiert.

Ursache 403: Cloudflare-Sperrseite, kein Fehler im Programm. Einmalige Kontrollabfrage auf `https://de.topps.com/products.json?limit=1` (curl_cffi, impersonate=chrome, ohne Proxy):
```
status: 403
server: cloudflare
content-type: text/html; charset=UTF-8
cf-ray: a5d3c830aa38db0c-FRA
title: Attention Required! | Cloudflare
```
Statt products-JSON kommt die HTML-Blockseite "Attention Required!" der Cloudflare-Firewall. Der Shop sperrt die Anfrage also gezielt (Firewall-Regel auf Client/IP/Endpunkt), es ist keine Challenge und kein Shopify-Fehler.

Ursache DNSError/Timeout:
- nl/be/pl.topps.com: Hostname loest nicht auf.
- at.topps.com: im ersten Durchlauf DNSError, jetzt Timeout.
- shop-uk.topps.com: im ersten Durchlauf 403, jetzt Timeout.

Nicht versucht: die Cloudflare-Sperre zu umgehen (anderer Fingerprint, Proxys, Header-Varianten).

## Schritt 3 - Exe bauen, dritter Durchlauf (2026-11-20)
Ergebnis: erledigt. Build laeuft ohne Traceback durch (Exit-Code 0).
- Befehl: `.\.venv\Scripts\pyinstaller.exe --noconfirm --onefile --name toppsfarm --collect-all curl_cffi --collect-all playwright toppsfarm.py`
- PyInstaller 6.22.3, Python 3.14.4. Kein `Traceback`, keine `ERROR`-Zeile von PyInstaller im Build-Log.
- Ende der Ausgabe:
```
3512 INFO: checking PYZ
3626 INFO: checking PKG
3667 INFO: checking EXE
3681 INFO: Build complete! The results are available in: C:\Users\sargo\Downloads\toppsfarm\dist
```
- Die Exe wurde dabei NICHT neu geschrieben: PyInstaller hat PYZ/PKG/EXE nur geprueft und als aktuell befunden (Build-Cache, toppsfarm.py seit dem letzten Build unveraendert). `dist\toppsfarm.exe` ist weiterhin die Datei vom zweiten Durchlauf: 60285173 Bytes, 20.11.2026 02:45:37.
- Auffaellig: PyInstaller meldet als Python-Umgebung `C:\Users\sargo\Desktop\topps bot\toppsfarm\.venv`, nicht den `.venv`-Ordner unter `Downloads\toppsfarm`. Der Build funktioniert, die venv zeigt aber auf den alten Pfad.
Fehler: keine.


## Schritt 4 - Selftest der Exe, neuer Durchlauf + Diagnose-Matrix (2026-11-20)
Selftest `.\dist\toppsfarm.exe selftest` (Exit-Code 0, kein Traceback), Host-Zeilen woertlich:
```
--- de.topps.com (403)
--- shop-de.topps.com (403)
--- es.topps.com (403)
--- fr.topps.com (403)
--- it.topps.com (403)
--- nl.topps.com (DNSError)
--- at.topps.com (DNSError)
--- be.topps.com (DNSError)
--- pl.topps.com (Timeout)
--- shop-uk.topps.com (403)
```
de.topps.com liefert weiter 403, kein products-JSON.

Diagnose-Matrix aus ORDERS.md, Skript `diag_cf.py` (curl_cffi 0.17.0, kein Proxy, kein Browser, je Variante genau eine Anfrage).
Spalten: Variante | Status | http (curl-Enum: 2 = HTTP/1.1, 3 = HTTP/2) | content-type | Groesse | Inhalt.

### Matrix 1 - minimale Header
Nur `accept` und `accept-language` selbst gesetzt, Rest vom impersonate.
```
minimal-header chrome /products.json | 403 | http=3 | text/html; charset=UTF-8 | 5683 B | title=Attention Required! | Cloudflare
```
Ergebnis: 403. Die selbst gesetzten Header (user-agent Chrome 131, sec-ch-ua, x-requested-with) sind nicht die Ursache.

### Matrix 2 - impersonate-Varianten
Alle fuenf sind in curl_cffi 0.17.0 vorhanden, keine uebersprungen.
```
impersonate=chrome /products.json | 403 | http=3 | text/html; charset=UTF-8 | 5683 B | title=Attention Required! | Cloudflare
impersonate=chrome131 /products.json | 403 | http=3 | text/html; charset=UTF-8 | 5683 B | title=Attention Required! | Cloudflare
impersonate=chrome124 /products.json | 403 | http=3 | text/html; charset=UTF-8 | 5683 B | title=Attention Required! | Cloudflare
impersonate=safari17_0 /products.json | 403 | http=3 | text/html; charset=UTF-8 | 5683 B | title=Attention Required! | Cloudflare
impersonate=firefox133 /products.json | 403 | http=3 | text/html; charset=UTF-8 | 5683 B | title=Attention Required! | Cloudflare
```
Ergebnis: 403 bei allen. Der TLS-/Browser-Fingerprint ist nicht die Ursache.

### Matrix 3 - HTTP/1.1 erzwingen
```
http1.1 chrome /products.json | 403 | http=2 | text/html; charset=UTF-8 | 5683 B | title=Attention Required! | Cloudflare
h2 chrome /products.json (Vergleich) | 403 | http=3 | text/html; charset=UTF-8 | 5683 B | title=Attention Required! | Cloudflare
```
Ergebnis: 403 mit HTTP/1.1 (http=2) genauso wie mit h2 (http=3).

### Matrix 4 - mit und ohne ?limit=250
```
ohne Query /products.json | 403 | http=3 | text/html; charset=UTF-8 | 5683 B | title=Attention Required! | Cloudflare
mit Query /products.json?limit=250 | 403 | http=3 | text/html; charset=UTF-8 | 5683 B | title=Attention Required! | Cloudflare
```
Ergebnis: kein Unterschied, beide 403.

### Matrix 5 - Sitemap und /products/<handle>.js
```
/ (Startseite) | 200 | http=3 | text/html; charset=utf-8 | 1154468 B | title=Topps Deutschland Official | Sammelkarten, exklusi
/robots.txt | 200 | http=3 | text/plain | 173 B | body=User-Agent: * Allow: / Disallow: /*?* Di
/sitemap.xml | 200 | http=3 | application/xml | 61392 B | body=<?xml version="1.0" encoding="UTF-8"?> <
/sitemap_products_1.xml | 404 | http=3 | text/html; charset=utf-8 | 237562 B | body=<!DOCTYPE html><html lang="de"><head><me
/products/sitemap.xml | 200 | application/xml | 24446 B | <?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="h
/products/sitemap/0.xml | 200 | application/xml | 36622 B | <?xml version="1.0" encoding="UTF-8"?> <urlset xmlns="http://www.sitem
/products/sitemap/324.xml | 200 | application/xml | 2989 B | <?xml version="1.0" encoding="UTF-8"?> <urlset xmlns="http://www.sitem
/products/<handle>.js | 200 | text/html; charset=utf-8 | 238782 B | (HTML-Seite, kein JSON)
/products/<handle>.json | 200 | text/html; charset=utf-8 | 240595 B | (HTML-Seite, kein JSON)
/products/<handle> | 200 | text/html; charset=utf-8 | 507212 B | Produktseite, Variant-IDs im HTML
shop-de.topps.com/products/<handle>.js | 404 | application/json; charset=utf-8 | 0 B
topps-deu.myshopify.com/products/<handle>.js | 404 | application/json; charset=utf-8 | 0 B
```
(`<handle>` = erster Eintrag aus `/products/sitemap/0.xml`.)

Befund - eigentliche Ursache des 403:
- de.topps.com ist kein klassisches Shopify-Theme mehr, sondern ein Next.js-Frontend auf Vercel (`x-powered-by: Next.js`, `x-vercel-id`) mit Shopify nur noch als Backend (`storeDomain: topps-deu.myshopify.com`, Checkout-Domain `shop-de.topps.com`).
- Die Shopify-Theme-Endpunkte gibt es dort nicht mehr: `/products.json` wird von Cloudflare pauschal mit 403 geblockt (unabhaengig von Headern, Fingerprint, HTTP-Version, Query), `/sitemap_products_1.xml` ist 404, `/products/<handle>.js` liefert die HTML-Produktseite statt JSON.
- Die Produkt-Sitemap liegt laut robots.txt unter `/products/sitemap.xml` (Index mit 325 Teil-Sitemaps `/products/sitemap/0.xml` .. `324.xml`, ca. 194 Handles je Datei, neueste Produkte am Ende der letzten Datei).
- Variant-IDs stehen im HTML der Produktseite (`gid://shopify/ProductVariant/<id>` inkl. `availableForSale` und Preis).

### Matrix 6 - Monitor auf Sitemap umgebaut
Sitemap ist erreichbar (200), aber nicht unter `sitemap_products_1.xml`, sondern `/products/sitemap.xml` -> `/products/sitemap/<n>.xml`. Umbau in toppsfarm.py:
- `sitemap_handles()`: liest den Index, nimmt die Teil-Sitemap mit der hoechsten Nummer (neue Produkte stehen dort am Ende), liefert deren Handles.
- `pdp_product()`: Variant-IDs, Preis und Verfuegbarkeit aus dem HTML von `/products/<handle>` (nicht aus `/products/<handle>.js`, das liefert nur HTML ohne JSON).
- `Monitor._poll()`: fragt nicht mehr `/products.json` ab. Erster Weg ist die Storefront-API (Matrix 7), bei Status != 200 der Sitemap-Weg: erster Durchlauf merkt sich die Handles, danach werden neue Handles gedifft und ueber die Produktseite aufgeloest.
- `cmd_selftest()`: prueft dieselben Quellen statt `/products.json`.
Test aus dem Quelltext gegen de.topps.com:
```
sitemap | 200 | 15 handles | letztes: darius-acuff-jr-2026-27-nba-topps-now-r-card-96
pdp | {'id': 3856205069, 'handle': 'darius-acuff-jr-2026-27-nba-topps-now-r-card-96', 'variants': [{'id': 51171485516016, 'price': '9.99', 'available': True}, {'id': 51171485548784, 'price': '46.99', 'available': True}, {'id': 51171485581552, 'price': '81.99', 'available': True}, {'id': 51171485614320, 'price': '150.99', 'available': True}]}
```
Einschraenkungen des Sitemap-Wegs: Produkt-ID ist dort ein CRC aus Host+Handle (die echte Shopify-Produkt-ID steht nicht eindeutig im HTML); Restocks alter Produkte erkennt er nicht, nur neue Handles. Im laufenden Betrieb (watch) ist der Sitemap-Weg nicht getestet, nur die beiden Funktionen einzeln.

### Matrix 7 - Storefront-API
Der Token steht nicht in einem JS-Bundle, sondern direkt im HTML der Startseite (Next.js-Datenblock): `storeDomain: topps-deu.myshopify.com`, `storefrontAccessToken` (32 Hex-Zeichen, oeffentlicher Storefront-Token). `storefront_cfg()` liest beides pro Host zur Laufzeit aus, nichts ist fest einkodiert.
GraphQL-products-Query (`products(first:3, sortKey:CREATED_AT, reverse:true)`):
```
POST topps-deu.myshopify.com/api/2024-10/graphql.json | 200 | application/json; charset=utf-8 | 1442 B | {"data":{"products":{"edges":[{"node":{"handle":"darius-acuff-jr-2026-
POST shop-de.topps.com/api/2024-10/graphql.json | 200 | application/json; charset=utf-8 | 1442 B | {"data":{"products":{"edges":[{"node":{"handle":"darius-acuff-jr-2026-
```
Ueber `storefront_products()` aus dem Quelltext:
```
storefront p1 | 200 | 250 produkte | cursor True | 1.8s
storefront p2 | 200 | 250
```
Ergebnis: 200 mit Produkten, Variant-IDs, Preis und `availableForSale`. Das ist jetzt die Hauptquelle des Monitors (2 Seiten a 250, neueste zuerst).

### Schritt 4 - Endergebnis nach Umbau
Exe neu gebaut (gleicher PyInstaller-Befehl wie Schritt 3, Exit-Code 0, kein Traceback, `Build complete!`; `dist\toppsfarm.exe` 60291382 Bytes, 20.11.2026 03:01:39).
`.\dist\toppsfarm.exe selftest` (Exit-Code 0), Host-Zeilen woertlich:
```
OK  de.topps.com (200) storefront products-JSON
--- shop-de.topps.com (404)
OK  es.topps.com (200) storefront products-JSON
OK  fr.topps.com (200) storefront products-JSON
OK  it.topps.com (200) storefront products-JSON
--- nl.topps.com (DNSError)
--- at.topps.com (DNSError)
--- be.topps.com (DNSError)
--- pl.topps.com (DNSError)
--- shop-uk.topps.com (404)
```
Ergebnis: de.topps.com liefert 200 mit Produkt-JSON - aber ueber die Storefront-API, NICHT ueber `/products.json`. `/products.json` selbst bleibt in jeder getesteten Variante 403 (Matrix 1-4) und wird nicht mehr benutzt. Schritt 4 deshalb in ORDERS.md auf [x].

Fehler / offen:
- `--- shop-de.topps.com (404)` und `--- shop-uk.topps.com (404)`: das sind reine Checkout-Domains ohne Startseite/Sitemap (vorher 403 auf /products.json). Als Monitor-Hosts ungeeignet.
- `--- nl/at/be/pl.topps.com (DNSError)`: Hostnamen loesen nicht auf.
- Keine Profilzeilen, weil `config\profiles.yaml` nicht existiert.
- `warm()` und `HttpCheckout` rufen weiterhin `/products.json?limit=1`, `/cart/add.js` und `/checkout` auf dem Frontend-Host auf. Nicht angefasst (gehoert zu Schritt 5), wird dort auf de.topps.com voraussichtlich nicht funktionieren, weil das Frontend kein Shopify-Theme ist. Schritt 5 nennt ausserdem `/products.json?limit=20` als Quelle der Variant-ID - die gibt es nicht mehr, Variant-IDs kommen jetzt aus der Storefront-API.
- Die Startseite bindet `consumer.fanfare.io` ein (Warteraum-/Drop-Dienst). Nicht untersucht.

## Schritt 8 - headers() auf Minimum (2026-11-20)
Ergebnis: Code-Aenderung erledigt, Test liefert weiter 403.
- `headers()` in toppsfarm.py setzt nur noch `accept` und `accept-language`. Entfernt: `user-agent`, `sec-ch-ua`, `sec-ch-ua-mobile`, `sec-ch-ua-platform`, `sec-fetch-dest`, `sec-fetch-mode`, `sec-fetch-site`, `referer`, `x-requested-with`. Diese Header kommen jetzt vom impersonate (`cfg.impersonate`, Standard `chrome`).
- Aufrufer, die eigene Header ergaenzen (HttpCheckout: `content-type`, `x-csrf-token`, `origin`, `referer`), sind unveraendert.
- `py_compile toppsfarm.py` ohne Fehler.
- Die Exe wurde NICHT neu gebaut; `dist\toppsfarm.exe` enthaelt noch die alten Header.

Test: eine Anfrage aus dem Quelltext (`session(cfg)` + `headers(cfg, host, True)`), ohne Proxy, auf `https://de.topps.com/products.json` ohne Query:
```
headers: {'accept': 'application/json', 'accept-language': 'de-DE,de;q=0.9,en;q=0.8'}
status: 403
content-type: text/html; charset=UTF-8
server: cloudflare
body[:300]: '<!DOCTYPE html>\n<!--[if lt IE 7]> <html class="no-js ie6 oldie" lang="en-US"> <![endif]-->\n<!--[if IE 7]>    <html class="no-js ie7 oldie" lang="en-US"> <![endif]-->\n<!--[if IE 8]>    <html class="no-js ie8 oldie" lang="en-US"> <![endif]-->\n<!--[if gt IE 8]><!--> <html class="no-js" lang="en-US"> <!'
```
Fehler: Statuscode 403, Body ist die Cloudflare-Blockseite (HTML), kein products-JSON. Gleiches Ergebnis wie Matrix 1 aus Schritt 4: die Header sind nicht die Ursache des 403.

## Schritt 9 - impersonate-Varianten (2026-11-20)
Ergebnis: alle fuenf Varianten liefern 403. Keine uebersprungen, alle sind in curl_cffi 0.17.0 vorhanden.
- Je Variante genau eine Anfrage auf `https://de.topps.com/products.json` (ohne Query, ohne Proxy), Header nur `accept` und `accept-language` wie nach Schritt 8, Rest vom impersonate.
- `chrome` ist in curl_cffi ein Alias auf die neueste Chrome-Version und steht nicht in der `BrowserType`-Liste; die Variante wurde deshalb einzeln nachgetestet.
- Kein Code geaendert, `cfg.impersonate` bleibt `chrome`.

Spalten: Variante | Status | content-type | Groesse | server | Inhalt.
```
impersonate=chrome | 403 | text/html; charset=UTF-8 | 5683 B | server=cloudflare | title=Attention Required! | Cloudflare
impersonate=chrome131 | 403 | text/html; charset=UTF-8 | 5683 B | server=cloudflare | title=Attention Required! | Cloudflare
impersonate=chrome124 | 403 | text/html; charset=UTF-8 | 5683 B | server=cloudflare | title=Attention Required! | Cloudflare
impersonate=safari17_0 | 403 | text/html; charset=UTF-8 | 5683 B | server=cloudflare | title=Attention Required! | Cloudflare
impersonate=firefox133 | 403 | text/html; charset=UTF-8 | 5683 B | server=cloudflare | title=Attention Required! | Cloudflare
```
Fehler: Statuscode 403 bei jeder Variante, Body ist die Cloudflare-Blockseite `Attention Required! | Cloudflare` (5683 B HTML), kein products-JSON. Gleiches Ergebnis wie Matrix 2 aus Schritt 4: der Fingerprint ist nicht die Ursache, `/products.json` ist auf de.topps.com pauschal gesperrt.
## Schritt 10 - HTTP/1.1 erzwingen (2026-11-20)
Ergebnis: 403, auch mit HTTP/1.1.
- Genau eine Anfrage auf `https://de.topps.com/products.json` (ohne Query, ohne Proxy), curl_cffi 0.17.0, `impersonate=chrome`, `http_version=CurlHttpVersion.V1_1`, Header nur `accept` und `accept-language` wie nach Schritt 8.
- `http_version: 2` ist der curl-Enum-Wert fuer HTTP/1.1 (3 waere HTTP/2): die Antwort kam also tatsaechlich ueber HTTP/1.1, nicht ueber h2.
- Kein Code geaendert. toppsfarm.py erzwingt weiterhin keine HTTP-Version, die Exe wurde nicht neu gebaut.

Ausgabe woertlich:
```
curl_cffi 0.17.0
status: 403
http_version: 2
content-type: text/html; charset=UTF-8
server: cloudflare
size: 5683
title: Attention Required! | Cloudflare
body[:200]: '<!DOCTYPE html>\n<!--[if lt IE 7]> <html class="no-js ie6 oldie" lang="en-US"> <![endif]-->\n<!--[if IE 7]>    <html class="no-js ie7 oldie" lang="en-US"> <![endif]-->\n<!--[if IE 8]>    <html class="no-'
```
Fehler: Statuscode 403, Body ist die Cloudflare-Blockseite `Attention Required! | Cloudflare` (5683 B HTML), kein products-JSON. Gleiches Ergebnis wie Matrix 3 aus Schritt 4: die HTTP-Version ist nicht die Ursache, `/products.json` ist auf de.topps.com pauschal gesperrt.

## Schritt 11 - mit und ohne ?limit=250 (2026-11-20)
Ergebnis: kein Unterschied, beide 403.
- Je Variante genau eine Anfrage auf de.topps.com (ohne Proxy), curl_cffi 0.17.0, `impersonate=chrome`, Header nur `accept` und `accept-language` wie nach Schritt 8, HTTP-Version nicht erzwungen (`http_version=3` = h2).
- Kein Code geaendert, die Exe wurde nicht neu gebaut.

Ausgabe woertlich:
```
curl_cffi 0.17.0
ohne Query | https://de.topps.com/products.json | status=403 | http_version=3 | text/html; charset=UTF-8 | server=cloudflare | 5683 B | title=Attention Required! | Cloudflare | body[:80]='<!DOCTYPE html>\n<!--[if lt IE 7]> <html class="no-js ie6 oldie" lang="en-US"> <!'
mit ?limit=250 | https://de.topps.com/products.json?limit=250 | status=403 | http_version=3 | text/html; charset=UTF-8 | server=cloudflare | 5683 B | title=Attention Required! | Cloudflare | body[:80]='<!DOCTYPE html>\n<!--[if lt IE 7]> <html class="no-js ie6 oldie" lang="en-US"> <!'
```
Fehler: Statuscode 403 bei beiden Varianten, Body ist jeweils die Cloudflare-Blockseite `Attention Required! | Cloudflare` (5683 B HTML), kein products-JSON. Gleiches Ergebnis wie Matrix 4 aus Schritt 4: der Query-Parameter ist nicht die Ursache, `/products.json` ist auf de.topps.com pauschal gesperrt.

## Schritt 12 - Sitemap und /products/<handle>.js (2026-11-20)
Ergebnis: `/sitemap.xml` 200, `/sitemap_products_1.xml` 404, `/products/<handle>.js` 200, aber HTML statt JSON.
- Vorbedingung "falls weiter 403" trifft zu (Schritt 11: `/products.json` 403).
- Je Pfad genau eine Anfrage auf de.topps.com (ohne Proxy), curl_cffi 0.17.0, `impersonate=chrome`, Header nur `accept` und `accept-language`.
- `<handle>` = erster Eintrag aus `/products/sitemap/0.xml` (dafuer eine zusaetzliche Anfrage, da `/sitemap_products_1.xml` nicht existiert): `2024-topps-chrome®-formula-1®-qualifying-lap-box`.
- Kein Code geaendert, die Exe wurde nicht neu gebaut.

Ausgabe woertlich (die `®` im Handle zeigt die Konsole als `�`):
```
curl_cffi 0.17.0
/sitemap.xml | status=200 | application/xml | server=cloudflare | 61392 B | title=None | body[:80]='<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/sc'
/sitemap_products_1.xml | status=404 | text/html; charset=utf-8 | server=cloudflare | 238108 B | title=None | body[:80]='<!DOCTYPE html><html lang="de"><head><meta charSet="utf-8"/><link rel="preconnec'
/products/sitemap/0.xml | status=200 | application/xml | server=cloudflare | 36646 B | title=None | body[:80]='<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/sc'
handle: 2024-topps-chrome�-formula-1�-qualifying-lap-box
/products/<handle>.js | status=200 | text/html; charset=utf-8 | server=cloudflare | 240250 B | title=2024 Topps Chrome� Formula 1� - Qualifying Lap Box | body[:80]='<!DOCTYPE html><html lang="de"><head><meta charSet="utf-8"/><link rel="preconnec'
json: nein (JSONDecodeError)
```
Fehler:
- `/sitemap_products_1.xml`: Statuscode 404, Body ist die HTML-404-Seite des Next.js-Frontends (238108 B), keine Sitemap.
- `/products/<handle>.js`: Statuscode 200, aber `content-type: text/html`, Body ist die HTML-Produktseite; `r.json()` scheitert mit `JSONDecodeError`. Der Shopify-Endpunkt `.js` existiert auf de.topps.com nicht.
- Kein 403 auf diesen drei Pfaden. Gleiches Ergebnis wie Matrix 5 aus Schritt 4.

Folge fuer Schritt 13: die dort genannten Quellen (`sitemap_products_1.xml`, `/products/<handle>.js`) gibt es nicht. Die Produkt-Sitemap liegt unter `/products/sitemap.xml` -> `/products/sitemap/<n>.xml`, Variant-IDs stehen im HTML von `/products/<handle>` (siehe Matrix 5/6).

## Schritt 13 - Monitor auf Sitemap umgebaut (2026-11-20)
Ergebnis: erledigt, mit Abweichungen bei den Quellen und einem offenen Punkt (429 auf der Sitemap).
- Vorbedingung "falls Sitemap geht" trifft zu, aber nicht fuer die im Auftrag genannten Pfade (Schritt 12): `/sitemap_products_1.xml` ist 404, `/products/<handle>.js` liefert HTML statt JSON. Umgesetzt mit den tatsaechlichen Quellen: Handles aus `/products/sitemap.xml` -> letzte Teil-Sitemap `/products/sitemap/<n>.xml`, Variant-IDs aus dem HTML von `/products/<handle>`.
- Aenderungen in toppsfarm.py:
  - Neue Einstellung `monitor_sources` (Standard und in `config\settings.yaml`: `sitemap`, `storefront`). Die Quellen werden in dieser Reihenfolge benutzt, die naechste nur, wenn die davor keinen Status 200 liefert.
  - `Monitor._poll()`: Sitemap ist jetzt der erste Weg (vorher Storefront-API zuerst, Sitemap nur Ersatz).
  - `sitemap_new()`: erster Durchlauf je Host merkt sich die Handles, danach werden neue Handles gedifft und ueber die Produktseite aufgeloest. Hoechstens 20 neue Handles je Durchlauf; ein Handle, das sich 5-mal nicht aufloesen laesst, wird uebersprungen (Warnung im Log).
  - `products_json()`: `/products.json` als optionaler Zweitweg. Nicht im Standard, weil auf de.topps.com 403; aktivierbar ueber `monitor_sources: [sitemap, products_json]`.
  - Nach 429 auf der Sitemap ruht der Sitemap-Weg fuer diesen Host 60 s (in der Zeit greift die naechste Quelle).
  - `cmd_selftest()`: prueft dieselben Quellen in derselben Reihenfolge und zeigt, welche Quelle vorher gescheitert ist.
- `py_compile toppsfarm.py` ohne Fehler. Die Exe wurde NICHT neu gebaut; `dist\toppsfarm.exe` hat noch den alten Monitor (Storefront zuerst).

Test 1: `Monitor._poll()` aus dem Quelltext gegen de.topps.com, ohne Proxy, State/Notifier durch Attrappen ersetzt. In Poll 3 wurde das letzte Handle aus dem Gemerkten entfernt, um ein neues Produkt zu simulieren (ein echtes neues Produkt ist im Testzeitraum nicht erschienen). Ausgabe woertlich (`®` zeigt die Konsole als `�`):
```
monitor_sources: ['sitemap', 'storefront']
poll 1 | changed=False | seen=15 | on_new=0 | storefront-calls=0 | 0.7s
poll 2 | changed=False | seen=15 | on_new=0 | storefront-calls=0 | 0.5s
  notify: NEU Darius Acuff Jr. - 2026-27 NBA Topps NOW� - Card 96 {'Host': 'de.topps.com', 'Preis': '9.99', 'Variant': 51171485516016, 'Link': 'https://de.topps.com/products/darius-acuff-jr-2026-27-nba-topps-now-r-card-96'}
  notify: NEU Darius Acuff Jr. - 2026-27 NBA Topps NOW� - Card 96 {'Host': 'de.topps.com', 'Preis': '46.99', 'Variant': 51171485548784, 'Link': 'https://de.topps.com/products/darius-acuff-jr-2026-27-nba-topps-now-r-card-96'}
  notify: NEU Darius Acuff Jr. - 2026-27 NBA Topps NOW� - Card 96 {'Host': 'de.topps.com', 'Preis': '81.99', 'Variant': 51171485581552, 'Link': 'https://de.topps.com/products/darius-acuff-jr-2026-27-nba-topps-now-r-card-96'}
  notify: NEU Darius Acuff Jr. - 2026-27 NBA Topps NOW� - Card 96 {'Host': 'de.topps.com', 'Preis': '150.99', 'Variant': 51171485614320, 'Link': 'https://de.topps.com/products/darius-acuff-jr-2026-27-nba-topps-now-r-card-96'}
poll 3 (Handle 'darius-acuff-jr-2026-27-nba-topps-now-r-card-96' als neu simuliert) | changed=True | on_new=4 | storefront-calls=0 | 1.2s
  on_new: ('darius-acuff-jr-2026-27-nba-topps-now-r-card-96', 51171485516016, '9.99', True)
  on_new: ('darius-acuff-jr-2026-27-nba-topps-now-r-card-96', 51171485548784, '46.99', True)
  on_new: ('darius-acuff-jr-2026-27-nba-topps-now-r-card-96', 51171485581552, '81.99', True)
  on_new: ('darius-acuff-jr-2026-27-nba-topps-now-r-card-96', 51171485614320, '150.99', True)
products_json | (403, [])
poll 4 (sources=products_json,sitemap) | changed=False | on_new=4
```
Der Monitor laeuft ueber die Sitemap, die Storefront-API wird dabei nicht aufgerufen. Der Zweitweg `products_json` liefert 403 und faellt sauber auf die naechste Quelle durch.

Test 2: `python toppsfarm.py selftest` aus dem Quelltext, zwei Laeufe, Host-Zeilen woertlich.
Lauf 1 (vor der Anzeige der gescheiterten Quelle):
```
OK  de.topps.com (200) storefront products-JSON
--- shop-de.topps.com (429)
OK  es.topps.com (200) storefront products-JSON
OK  fr.topps.com (200) storefront products-JSON
OK  it.topps.com (200) storefront products-JSON
--- nl.topps.com (DNSError)
--- at.topps.com (DNSError)
--- be.topps.com (DNSError)
--- pl.topps.com (Timeout)
--- shop-uk.topps.com (404)
```
Lauf 2:
```
OK  de.topps.com (200) sitemap, 15 handles
--- shop-de.topps.com (404)
OK  es.topps.com (200) sitemap, 126 handles
OK  fr.topps.com (200) sitemap, 154 handles
OK  it.topps.com (200) storefront products-JSON | vorher: sitemap 429
--- nl.topps.com (DNSError)
--- at.topps.com (DNSError)
--- be.topps.com (Timeout)
--- pl.topps.com (DNSError)
--- shop-uk.topps.com (404)
```

Fehler / offen:
- `sitemap 429` (it.topps.com in Lauf 2; in Lauf 1 fiel die Sitemap auf de/es/fr/it aus, vermutlich ebenfalls 429, der Status wurde dort noch nicht angezeigt; `--- shop-de.topps.com (429)`): der Shop begrenzt die Anfragerate auf dem Frontend. Lauf 1 kam direkt nach Test 1 (ca. 10 Anfragen an de.topps.com in 20 s). Im watch-Betrieb macht der Sitemap-Weg 2 Anfragen je Host und Durchlauf bei `poll_interval_s: 2.5` - damit ist dauerhaft mit 429 zu rechnen. Das Limit wurde nicht umgangen; eingebaut ist nur die 60-s-Pause mit Ausweichen auf die naechste Quelle. Die genaue Grenze ist nicht gemessen. Fuer den Sitemap-Weg sollte `poll_interval_s` deutlich hoeher stehen.
- `products_json | (403, [])`: `/products.json` bleibt auf de.topps.com 403 (Cloudflare-Blockseite).
- Der Sitemap-Weg erkennt nur neue Handles, keine Restocks vorhandener Produkte, und die Produkt-ID ist dort ein CRC aus Host+Handle. Solange die Sitemap 200 liefert, laeuft die Storefront-API nicht mehr mit; Restocks werden im Standard also nicht mehr gemeldet. Wer das braucht: `monitor_sources: [storefront, sitemap]`.
- Die gemerkten Handles liegen nur im Speicher: nach einem Neustart gilt der erste Durchlauf wieder als Ausgangsstand, in der Zwischenzeit erschienene Produkte werden nicht gemeldet.
- Wie schnell ein neues Produkt in der Sitemap erscheint, ist nicht gemessen (`cache-control: public, max-age=0, must-revalidate`, `x-vercel-cache: MISS`).
- watch-Betrieb als Dauerlauf und die Exe sind nicht getestet, nur `_poll()` einzeln und der Selftest aus dem Quelltext.
- `--- shop-de/shop-uk.topps.com (404)`, `nl/at/be/pl (DNSError/Timeout)`: unveraendert wie in Schritt 4.

## Schritt 14 - Storefront-API als Zweitweg (2026-11-20)
Ergebnis: GraphQL-products-Query liefert 200 mit Produkten. Der Token steht aber NICHT in den JS-Bundles, sondern im HTML der Startseite.
- Storefront-API ist bereits als Zweitweg im Monitor eingebaut (`monitor_sources: [sitemap, storefront]`, `storefront_cfg()` / `storefront_products()`, siehe Matrix 7 und Schritt 13). Kein Code geaendert, die Exe wurde nicht neu gebaut.
- Token-Suche auf de.topps.com (ohne Proxy, curl_cffi 0.17.0, `impersonate=chrome`): Startseite plus alle 49 dort eingebundenen JS-Bundles, je eine Anfrage.
  - In keinem der 49 Bundles steht der Token-Wert oder die Shop-Domain. Zwei Bundles enthalten nur den Schluesselnamen `storefrontAccessToken` (Code, der den Wert zur Laufzeit liest), nicht den Wert.
  - Der Wert steht genau einmal im HTML der Startseite, im Next.js-Datenblock, zusammen mit `storeDomain: topps-deu.myshopify.com`. Von dort liest ihn `storefront_cfg()` pro Host zur Laufzeit; nichts ist fest einkodiert. Der Token ist hier nur gekuerzt wiedergegeben.
- GraphQL-Test: `POST https://topps-deu.myshopify.com/api/2024-10/graphql.json`, Header `x-shopify-storefront-access-token`, Query `products(first:$n, after:$c, sortKey:CREATED_AT, reverse:true)` mit Varianten (`id`, `availableForSale`, `price`).

Ausgabe woertlich (zwei Testlaeufe, `<TOKEN>` = Token-Wert ersetzt):
```
curl_cffi 0.17.0
GET / | status=200 | text/html; charset=utf-8 | 1157158 B
GET / | status=200 | token im HTML: 1x | kontext: 'frontRootDomain\\":\\"topps.com\\",\\"storefrontAccessToken\\":\\"<TOKEN>\\"}}]\n"'
js-bundles: 49 | statuscodes: {200: 49}
token-wert in bundles: nein
storeDomain in bundles: nein
'storefrontAccessToken' in bundles: ['layout-df70fc5d7054e5ed.js', 'consent-tracking-api.js']
'x-shopify-storefront-access-token' in bundles: ['consent-tracking-api.js']
'graphql.json' in bundles: ['consent-tracking-api.js']
storefront_cfg: ('topps-deu.myshopify.com', 'f674...4359 (32 Zeichen)')
POST topps-deu.myshopify.com/api/2024-10/graphql.json | status=200 | application/json; charset=utf-8 | 2182 B | 0.1s | body[:120]='{"data":{"products":{"pageInfo":{"hasNextPage":true,"endCursor":"eyJsYXN0X2lkIjoxMDQwMDQyOTAxNTI4MCwibGFzdF92YWx1ZSI6IjI'
storefront_products | status=200 | 250 produkte | cursor=True
erstes: darius-acuff-jr-2026-27-nba-topps-now-r-card-96 [{'id': 51171485516016, 'price': '9.99', 'available': True}]
ohne Token | status=200 | body[:160]='{"data":{"products":{"pageInfo":{"hasNextPage":false,"endCursor":null},"edges":[]}},"extensions":{"cost":{"requestedQueryCost":20}}}'
```
Statuscode: 200 (3 Produkte direkt, 250 Produkte ueber `storefront_products()`, weitere Seite vorhanden).

Fehler / offen:
- Kein HTTP-Fehler, kein 403/429 in diesem Schritt.
- Abweichung vom Auftrag: "Token aus den Theme-JS-Bundles" geht nicht, `token-wert in bundles: nein`. Quelle ist das HTML der Startseite.
- `ohne Token | status=200` mit leerer Produktliste: die API antwortet auch ohne Token mit 200, nur ohne Produkte. Der Statuscode allein beweist also nicht, dass der Token gilt; massgeblich ist, dass Produkte kommen. Der Selftest prueft das bereits (`st == 200 and bool(items)`). Im Monitor gilt 200 mit leerer Liste dagegen als Erfolg: wird der Token einmal ungueltig, meldet der Storefront-Weg nichts und faellt auch nicht auf die naechste Quelle durch. Nicht geaendert.
- Faellt die Startseite aus (z. B. 429 wie in Schritt 13), kann `storefront_cfg()` bei einem frisch gestarteten Prozess keinen Token lesen (`status 0`); ein einmal gelesener Token bleibt bis zum Prozessende im Speicher.
- Die erste Fassung des Testskripts meldete `token im HTML: nein`: Fehler im Suchmuster des Skripts (Escaping im Next.js-Datenblock), nicht im Programm. Zweiter Lauf mit dem Token-Wert als Suchtext, Ausgabe oben.
- Nur de.topps.com getestet; es/fr/it zuletzt im Selftest von Schritt 13.

## Schritt 15a - Ordner core/ und modules/ mit leerer __init__.py (2026-11-20)
Ergebnis: erledigt.
- `core/__init__.py` und `modules/__init__.py` liegen vor, beide 0 Byte.
- Beide Ordner und beide Dateien gab es schon aus dem frueheren Anlauf zu Schritt 15 (unversioniert), die Dateien waren aber nicht leer. Sie wurden geleert. Vorheriger Inhalt, damit nichts verloren geht:
  - `core/__init__.py` (56 Byte): `"""Baki AIO - gemeinsame Bausteine fuer alle Module."""`
  - `modules/__init__.py` (489 Byte):
    ```python
    """Baki AIO - Module. Jedes Modul stellt eine Klasse mit run() bereit (siehe base.py)."""
    from __future__ import annotations


    def load(key: str):
        """Liefert die Modul-Instanz zum Kurznamen oder None.

        Die Importe stehen in den Zweigen, damit das Menue sofort erscheint und
        ein Modul erst beim Start seine Abhaengigkeiten laedt.
        """
        if key == "topps":
            from modules.topps_module import ToppsModule
            return ToppsModule()
        return None


    KEYS = ["topps"]
    ```
- Commit enthaelt nur: `core/__init__.py`, `modules/__init__.py`, `STATUS.md`, `ORDERS.md`. Alles andere aus dem frueheren Anlauf bleibt uncommittet im Arbeitsverzeichnis (gehoert zu 15b-15e): `baki.py`, `modules/base.py`, `modules/topps_module.py`, Verschiebung `toppsfarm.py -> modules/topps.py`, Aenderungen an `README.md`, `START.bat`, `config/settings.yaml`, `requirements.txt`, `run_loop.ps1`.

Ausgabe woertlich:
```
0 core/__init__.py
0 modules/__init__.py
import core, modules: ok
```

Fehler / offen:
- Das uncommittete `baki.py` aus dem frueheren Anlauf laeuft mit der leeren `modules/__init__.py` nicht mehr (es nutzt `modules.KEYS` und `modules.load`). `echo 0 | python baki.py`, woertlich:
  ```
    File "C:\Users\sargo\Downloads\toppsfarm\baki.py", line 68, in menu
      entries = menu_entries()
    File "C:\Users\sargo\Downloads\toppsfarm\baki.py", line 41, in menu_entries
      for key in modules.KEYS:
                 ^^^^^^^^^^^^
  AttributeError: module 'modules' has no attribute 'KEYS'
  ```
  Nicht behoben, weil `baki.py` zu 15c/15d gehoert.
- Im Arbeitsverzeichnis gibt es `toppsfarm.py` nicht mehr (Verschiebung nach `modules/topps.py` ist vorgemerkt, nicht committet). Im Repo auf origin liegt `toppsfarm.py` weiter unveraendert.

## Schritt 15b - modules/base.py mit BaseModule.run() (2026-11-20)

Ergebnis:
- `modules/base.py` enthaelt nur noch die Klasse `BaseModule` mit der Methode `run(self)`, sonst nichts:
    ```python
    class BaseModule:
        def run(self):
            raise NotImplementedError
    ```
- Der fruehere Inhalt (`Action`, `Module`, `ask`, `pause`), der mit dem Commit `4d6608c step 15a` per `git add -A` mit ins Repo gerutscht war, ist entfernt.
- Mitcommittet: `run_loop.ps1` (Prompt um STATE.md erweitert, lag uncommittet im Arbeitsverzeichnis), neu `STATE.md`.

Ausgabe woertlich (`from modules.base import BaseModule`, dann `BaseModule().run()`):
```
BaseModule: <class 'modules.base.BaseModule'> True
run(): NotImplementedError
```

Fehler / offen:
- Keine Fehler in 15b selbst.
- `baki.py` (Zeile 12: `from modules.base import Action, ask, pause`) und `modules/topps_module.py` (Zeile 4: `from modules.base import Action, Module`) importieren Namen, die es in `base.py` nicht mehr gibt, und laufen daher nicht. Nicht behoben, gehoert zu 15c/15d.
- Der Commit `4d6608c` hat bereits Teile von 15c-15e ins Repo gebracht (`baki.py`, `modules/topps.py`, `modules/topps_module.py`, `START.bat`, `README.md`, `config/settings.yaml`, `requirements.txt`, `claude.log`). `toppsfarm.py` existiert im Repo nicht mehr, die duenne Weiterleitung aus 15d fehlt noch.

## Schritt 15c - baki.py: Banner und Menue 1-14 / 0, nur Anzeige (2026-11-20)

Ergebnis:
- `baki.py` neu geschrieben, ohne Modul-Logik und ohne Import aus `modules`:
  - Banner per `pyfiglet.figlet_format("BAKI AIO", font="ansi_shadow")`.
  - Hardcode-Fallback 1: derselbe ansi_shadow-Banner fest im Quelltext (pyfiglet/Font fehlt).
  - Hardcode-Fallback 2: ASCII-Banner, wenn die Konsolen-Codierung die Blockzeichen nicht kann.
  - Menue: Plaetze 1-14 (alle noch `-`) und `0  Ende`, Auswahl per `input(" Auswahl: ")`.
  - 1-14 -> ` N: noch nicht belegt.`, sonst ` Ungueltige Auswahl.`, danach Menue erneut; 0/EOF/Strg+C -> Ende, Exitcode 0.
- Entfallen (kommt mit 15d wieder): Modul-Registry, Direktaufruf `baki.py <modul> <args>`.

Test (Eingabe `3`, `x`, `0`, mit PYTHONIOENCODING=utf-8), Ausgabe woertlich gekuerzt auf einen Durchlauf:
```

██████╗  █████╗ ██╗  ██╗██╗     █████╗ ██╗ ██████╗
██╔══██╗██╔══██╗██║ ██╔╝██║    ██╔══██╗██║██╔═══██╗
██████╔╝███████║█████╔╝ ██║    ███████║██║██║   ██║
██╔══██╗██╔══██║██╔═██╗ ██║    ██╔══██║██║██║   ██║
██████╔╝██║  ██║██║  ██╗██║    ██║  ██║██║╚██████╔╝
╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝    ╚═╝  ╚═╝╚═╝ ╚═════╝

 ==================================================
   1  -
   ...
  14  -
   0  Ende
 ==================================================
 Auswahl:  3: noch nicht belegt.
 Auswahl:  Ungueltige Auswahl.
 Auswahl: exit=0
```
- Ohne pyfiglet (`sys.modules['pyfiglet']=None`): Hardcode-ansi_shadow-Banner erscheint.
- Mit umgeleiteter Ausgabe in cp1252 (ohne PYTHONIOENCODING): ASCII-Banner erscheint.

Fehler / offen:
- Keine Fehler in 15c selbst.
- Nicht im echten Konsolenfenster geprueft (nur per Pipe). Ob dort ansi_shadow oder ASCII erscheint, haengt von der Codierung ab (hier: Python meldet cp1252 -> ASCII-Banner).
- `START.bat` ruft noch `%BAKI% topps setup` auf, wenn `config\profiles.yaml` fehlt; `baki.py` ignoriert jetzt Argumente und zeigt nur das Menue. Nicht behoben, gehoert zu 15d/15e.
- `modules/topps_module.py` importiert weiter `Action, Module` aus `modules.base` (gibt es nicht) -> laeuft nicht, gehoert zu 15d.
- `README.md` beschreibt noch Registry und Direktaufruf (stimmt erst nach 15d wieder).
- Mitcommittet: die im Arbeitsverzeichnis ergaenzten ORDERS-Eintraege 27-30.

## Schritt 15a - core/ und modules/ mit leerer __init__.py (erneuter Lauf, 2026-11-20)
Ergebnis: erledigt, keine Aenderung am Code noetig.
- ORDERS.md wurde neu aufgesetzt (15a-29, alle `[ ]`), deshalb lief 15a noch einmal.
- Geprueft: `core/__init__.py` und `modules/__init__.py` existieren, je 0 Bytes, beide im Repo (`git ls-files`), angelegt in Commit aa614f5.
- In ORDERS.md 15a auf `[x]` gesetzt. 15b und 15c stehen dort weiter auf `[ ]`, obwohl base.py und baki.py schon vorhanden sind (nicht angefasst, nur 15a bearbeitet).
- Mitcommittet: die im Arbeitsverzeichnis geaenderte ORDERS.md (neue Liste) und run_loop.ps1 (neuer Prompt-Text).

Fehler: keine.

Hinweis zu spaeteren Schritten:
- Keine neuen Schritte angehaengt, 15a ist nicht blockiert.
- Schritte 16-24 beschreiben erfundene Identitaeten, Fingerprint-Verschleierung, Umgehung von Bot-Erkennung/Captcha und Massen-Registrierung von Konten bei Nike/Amazon/Pokemon Center/Riftbound. Diese Schritte werden im Loop voraussichtlich nicht umgesetzt, sondern abgelehnt; bitte vorher klaeren bzw. die Liste anpassen.

## Schritt 15b - modules/base.py mit BaseModule.run() (erneuter Lauf, 2026-11-20)
Ergebnis: erledigt, keine Aenderung am Code noetig.
- `modules/base.py` ist im Repo (`git ls-files`) und enthaelt genau die Klasse `BaseModule` mit der Methode `run(self)`:
    ```python
    class BaseModule:
        def run(self):
            raise NotImplementedError
    ```
- In ORDERS.md 15b auf `[x]` gesetzt. Keine neuen Schritte angehaengt, 15b ist nicht blockiert.

Ausgabe woertlich (`from modules.base import BaseModule`, dann `BaseModule().run()`, mit `.venv\Scripts\python.exe`):
```
BaseModule: <class 'modules.base.BaseModule'> True
run(): NotImplementedError
```

Fehler: keine.

Offen (unveraendert, nicht Teil von 15b):
- `modules/topps_module.py` importiert `Action, Module` aus `modules.base` (gibt es nicht) -> laeuft nicht, gehoert zu 15d.

## Schritt 15c - baki.py: Banner, Menue 1-14 und 0, Auswahl per input (erneuter Lauf, 2026-11-20)
Ergebnis: erledigt, keine Aenderung am Code noetig.
- `baki.py` ist im Repo und erfuellt den Auftrag bereits:
  - Banner per `pyfiglet.figlet_format("BAKI AIO", font="ansi_shadow", width=200)`.
  - Hardcode-Fallback: derselbe ansi_shadow-Banner fest im Quelltext (`BANNER_SHADOW`), wenn pyfiglet oder der Font fehlt; dazu `BANNER_ASCII`, wenn die Ausgabe-Codierung die Blockzeichen nicht kann.
  - Menue: Plaetze 1-14 (alle noch `-`) und `0  Ende`, Auswahl per `input(" Auswahl: ")`.
  - 1-14 -> ` N: noch nicht belegt.`, alles andere -> ` Ungueltige Auswahl.`, danach Menue erneut; 0 / EOF / Strg+C -> Ende mit Exitcode 0.
- pyfiglet 1.0.4 ist in der `.venv` installiert und steht in `requirements.txt` (`pyfiglet>=1.0`).
- In ORDERS.md 15c auf `[x]` gesetzt. Keine neuen Schritte angehaengt, 15c ist nicht blockiert.

Tests mit `.venv\Scripts\python.exe`, Eingabe per Pipe:
- `py_compile baki.py`: ohne Fehler.
- Eingabe `3`, `x`, `0` mit `PYTHONIOENCODING=utf-8`, Ausgabe woertlich, gekuerzt auf einen Menue-Durchlauf:
```

██████╗  █████╗ ██╗  ██╗██╗     █████╗ ██╗ ██████╗
██╔══██╗██╔══██╗██║ ██╔╝██║    ██╔══██╗██║██╔═══██╗
██████╔╝███████║█████╔╝ ██║    ███████║██║██║   ██║
██╔══██╗██╔══██║██╔═██╗ ██║    ██╔══██║██║██║   ██║
██████╔╝██║  ██║██║  ██╗██║    ██║  ██║██║╚██████╔╝
╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝    ╚═╝  ╚═╝╚═╝ ╚═════╝

 ==================================================
   1  -
   ...
  14  -
   0  Ende
 ==================================================
 Auswahl:  3: noch nicht belegt.
 Auswahl:  Ungueltige Auswahl.
 Auswahl: exit=0
```
- Eingabe `15`, `14`, `0`: ` Ungueltige Auswahl.`, ` 14: noch nicht belegt.`, Ende.
- Ohne pyfiglet (`sys.modules['pyfiglet']=None`): `banner()` liefert den fest eingetragenen ansi_shadow-Banner, identisch mit `BANNER_SHADOW`.
- Mit `PYTHONIOENCODING=cp1252`: ASCII-Banner erscheint, Menue danach normal.
- Leere Eingabe (EOF): `exit=0`.

Fehler: keine.

Offen (unveraendert, nicht Teil von 15c):
- Nicht im echten Konsolenfenster geprueft, nur per Pipe. Ob dort ansi_shadow oder der ASCII-Banner erscheint, haengt von der Konsolen-Codierung ab.
- Die Zeilen des pyfiglet-Banners enden auf Leerzeichen (der Hardcode-Banner nicht). Rein optisch, nicht geaendert.
- `baki.py` ignoriert Argumente; `START.bat` ruft noch `baki.py topps setup` auf (15d/15e).
- `modules/topps_module.py` importiert `Action, Module` aus `modules.base` (gibt es nicht) -> laeuft nicht (15d).

## Schritt 15d - toppsfarm.py -> modules/topps.py als ToppsModule(BaseModule) (2026-11-20)
Ergebnis: erledigt.
- `modules/topps.py` (die Verschiebung von `toppsfarm.py` lag schon im Repo) enthaelt jetzt die Klasse `ToppsModule(BaseModule)`:
  - `run(self)`: Topps-Untermenue 1-8 (Selftest, Watch cart, Watch browser, Drop, Profile pruefen, Statistik, Setup, Browser-Engine) und `0  Zurueck`. Drop fragt Host, Variant-ID, Tasks ab.
  - `call(self, argv)`: fuehrt einen der bisherigen toppsfarm-Befehle ueber das unveraenderte `main(argv)` aus und liefert den Exitcode (Strg+C -> 130, argparse-Fehler -> 2).
  - Die Topps-Logik selbst (Monitor, Checkout, Settings) ist nicht angefasst.
- `modules/topps_module.py` geloescht (Klasse liegt jetzt in `modules/topps.py`; die Datei importierte `Action, Module`, die es in `base.py` nicht gibt).
- `baki.py`: Tabelle `MODULES = {1: ("Topps EU", ...)}`. Menuepunkt 1 zeigt `Topps EU` und ruft `ToppsModule().run()` auf, Import erst bei Auswahl. 2-14 weiter `noch nicht belegt`. Eine Exception aus einem Modul wird als ` Fehler: ...` gemeldet, das Menue laeuft weiter.
- `toppsfarm.py` neu im Hauptordner als duenne Weiterleitung: `ToppsModule().call(sys.argv[1:])`. Alte Aufrufe `python toppsfarm.py <befehl>` laufen weiter.
- `README.md` an den Stand angepasst.

Tests mit `.venv\Scripts\python.exe`, `PYTHONIOENCODING=utf-8`:
- `py_compile baki.py toppsfarm.py modules/topps.py`: ohne Fehler.
- `baki.py` mit Eingabe `1`, `9`, `6`, `0`, `2`, `0` per Pipe, Ausgabe woertlich, gekuerzt (Banner und wiederholte Menues weggelassen):
```
 ==================================================
   1  Topps EU
   2  -
   ...
  14  -
   0  Ende
 ==================================================
 Auswahl:
 --- Topps EU ---
   1  Selftest
   2  Watch - Cart-Links (wenig Daten)
   3  Watch - mit Browser
   4  Drop auf Variante
   5  Profile pruefen
   6  Statistik
   7  Setup erneut ausfuehren
   8  Browser-Engine installieren
   0  Zurueck
 Topps-Auswahl:  Ungueltige Auswahl.
 Topps-Auswahl: {}
 Topps-Auswahl:
 Auswahl:  2: noch nicht belegt.
 Auswahl:
exit=0
```
  (`{}` ist die Ausgabe von Statistik: leere State-DB.)
- Weiterleitung `python toppsfarm.py stats`: Ausgabe `{}`, `exit=0`.
- Weiterleitung ohne Befehl, `python toppsfarm.py`, woertlich:
```
usage: toppsfarm [-h]
                 {setup,selftest,profiles-check,stats,install-browser,watch,drop} ...
toppsfarm: error: the following arguments are required: cmd
exit=2
```
  Das ist das alte Verhalten (Befehl ist Pflicht), kein neuer Fehler.
- `python -m modules.topps profiles-check`: keine Ausgabe (keine `config\profiles.yaml`), `exit=0`.

Fehler: keine.

Nicht getestet:
- Selftest, Watch, Drop, Setup, Browser-Engine ueber das Untermenue (Netz-/Live-Zugriffe bzw. interaktiv). Getestet sind nur Statistik, Profile pruefen und die Menuefuehrung.
- Die Exe: `dist\BakiAIO.exe` ist nicht neu gebaut und enthaelt diesen Stand nicht (15e).
- Nur per Pipe, nicht im echten Konsolenfenster.

Offen (15e):
- `START.bat` ruft bei fehlender `config\profiles.yaml` weiter `%BAKI% topps setup` auf; `baki.py` nimmt keine Argumente an und zeigt dann nur das Menue. Setup ist jetzt ueber Menue 1 -> 7 oder `python toppsfarm.py setup` erreichbar.
- `toppsfarm.spec` (unversioniert, per .gitignore) baut jetzt nur noch die Weiterleitung; massgeblich ist `BakiAIO.spec`.
- Keine neuen Schritte angehaengt, 15d ist nicht blockiert. Der Hinweis zu den Schritten 16-24 (siehe erneuter Lauf 15a) gilt weiter.

## Schritt 15e - Exe BakiAIO, START.bat auf baki.py, Build, Menuetest (2026-11-20)
Ergebnis: erledigt.
- Exe heisst `BakiAIO.exe`. Die alte `dist\toppsfarm.exe` (Stand 03:01, alter Monitor) und `toppsfarm.spec` (baute nur noch die Weiterleitung) sind geloescht; beides war unversioniert (.gitignore). Im dist-Ordner liegt nur noch `BakiAIO.exe`.
- `START.bat`: startet `baki.py` ueber die .venv, sonst `dist\BakiAIO.exe`, sonst `BakiAIO.exe` neben der bat (war schon so). Entfernt: der Aufruf `%BAKI% topps setup` samt `pause` bei fehlender `config\profiles.yaml` (baki.py kennt keine Argumente). Stattdessen eine Hinweiszeile: `Hinweis: config\profiles.yaml fehlt. Setup: Menue 1 (Topps EU), dann 7.`
- Build: `.\.venv\Scripts\pyinstaller.exe --noconfirm --clean BakiAIO.spec` (Spec = baki.py, onefile, collect_all curl_cffi/playwright/pyfiglet). Exit-Code 0, kein `Traceback`, keine ERROR-Zeile von PyInstaller. Ende der Ausgabe:
```
34218 INFO: Fixing EXE headers
34586 INFO: Building EXE from EXE-00.toc completed successfully.
34595 INFO: Build complete! The results are available in: C:\Users\sargo\Downloads\toppsfarm\dist
```
- `dist\BakiAIO.exe`, 60296751 Bytes, 20.11.2026 03:42:52. Enthaelt den Stand 15d (ToppsModule ueber Menuepunkt 1).
- `py_compile baki.py toppsfarm.py modules\topps.py`: ohne Fehler.

Menuetest der Exe: `cmd /c "dist\BakiAIO.exe < eingabe.txt"`, Eingabe `1`, `9`, `6`, `5`, `0`, `2`, `15`, `x`, `0`. Ausgabe woertlich, gekuerzt (wiederholte Banner/Menues und die Zeilen `2  -` bis `14  -` weggelassen):
```

 ____    _    _  _____      _    ___ ___
| __ )  / \  | |/ /_ _|    / \  |_ _/ _ \
|  _ \ / _ \ | ' / | |    / _ \  | | | | |
| |_) / ___ \| . \ | |   / ___ \ | | |_| |
|____/_/   \_\_|\_\___| /_/   \_\___\___/

 ==================================================
   1  Topps EU
   ...
   0  Ende
 ==================================================
 Auswahl:
 --- Topps EU ---
   1  Selftest
   2  Watch - Cart-Links (wenig Daten)
   3  Watch - mit Browser
   4  Drop auf Variante
   5  Profile pruefen
   6  Statistik
   7  Setup erneut ausfuehren
   8  Browser-Engine installieren
   0  Zurueck
 Topps-Auswahl:  Ungueltige Auswahl.
 Topps-Auswahl: {}
 Topps-Auswahl:
 Topps-Auswahl:
 Auswahl:  2: noch nicht belegt.
 Auswahl:  Ungueltige Auswahl.
 Auswahl:  Ungueltige Auswahl.
 Auswahl:
exit=0
```
(`{}` = Statistik bei leerer State-DB; Profile pruefen ohne Ausgabe, weil `config\profiles.yaml` fehlt.)

Test START.bat: `cmd /c ".\START.bat < eingabe.txt"`, Eingabe `1`, `0`, `0`: Hinweiszeile, ansi_shadow-Banner (ueber .venv + baki.py), Menue, Topps-Untermenue, zurueck, Ende, `exit=0`.

Fehler:
- Erster Testlauf der Exe per PowerShell-Pipe: die erste Eingabe `1` ergab ` Ungueltige Auswahl.`. Ursache: PowerShell setzt beim Pipen an ein natives Programm ein BOM vor die erste Zeile; Fehler des Tests, nicht des Programms. Wiederholt mit ASCII-Eingabedatei ueber cmd, Ausgabe oben.
- Erster Aufruf `cmd /c "START.bat < ..."`, woertlich:
  ```
  Der Befehl "START.bat" ist entweder falsch geschrieben oder
  konnte nicht gefunden werden.
  ```
  Mit `.\START.bat` laeuft es. Betrifft nur den Aufruf aus cmd ohne Pfad auf diesem Rechner, nicht den Doppelklick.
- Sonst keine.

Nicht getestet / offen:
- Die Exe zeigt bei umgeleiteter Ausgabe den ASCII-Banner (Codierung cp1252). Ob im echten Konsolenfenster der pyfiglet-Banner (ansi_shadow) aus der Exe erscheint, ist nicht geprueft; ebenso START.bat per Doppelklick.
- Selftest, Watch, Drop, Setup, Browser-Engine aus der Exe nicht ausgefuehrt (Netz-/Live-Zugriffe bzw. interaktiv).
- `release.zip` ist unveraendert alt (enthaelt noch toppsfarm.exe); neu erst mit Schritt 29.
- Keine neuen Schritte angehaengt, 15e ist nicht blockiert. Der Hinweis zu den Schritten 16-24 (siehe erneuter Lauf 15a) gilt weiter.