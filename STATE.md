# STATE

Stand: 2026-11-20, Aufgaben 1-7 aus AGENTS.md + Nachgereichtes.

## Erledigt
- 1: selftest gruen. Fix: `load_profiles()` versteht Identitaets-Format (street+house_no). Statuscodes via sitemap: de 200 (16), es 200 (126), fr 200 (154), it 200 (140).
- 2: Cloudflare-403 geloest. `cf_refresh()` oeffnet Browser, speichert cf_clearance+__cf_bm nach var/cf_cookies.json; `session()` reicht sie an curl_cffi weiter. Test: Homepage 200 (vorher 403), Storefront-API liefert Produkte.
- 3: cart-Flow ok. de.topps.com ohne /cart/add.js (Next.js); neu `HttpCheckout._storefront_cart_link` (Storefront-cartCreate) -> echter checkoutUrl. Drop-Test 1 Task (Cameron Boozer, variant 51178597613808): Task 'ok' mit checkout-link. Orchestrator sendet URL als CHECKOUT-Nachricht an Discord.
- 4: baki.py Menue hat 14 Plaetze, Module 1-6 verdrahtet, 7-14 Platzhalter. Alle 6 Fabriken importieren, run() vorhanden. Menue startet (Banner ok).
- 5: settings.json mit Defaults (gultiges JSON, 17 Keys). Neu in baki.py: sys.excepthook schreibt Traceback nach crashlog.log. Test ok.
- 6: release.zip neu gebaut (57 MB). BakiAIO.exe mit allen Fixes, START.bat, README.md, settings.json, config/, data/-Pools, leere accounts/-proxies/Address-Toolbox mit .gitkeep.
- 7: README auf Baki AIO umgeschrieben (Menue 1-14, Topps inkl. Cloudflare/cf-refresh + Storefront-cart-Link, Konfiguration, crashlog, Build/Release). release.zip aktualisiert.

## Nachgereicht
- config/keys.env neu geschrieben (CAPTCHA_PROVIDER, CAPSOLVER_KEY, DISCORD_WEBHOOK, DISCORD_WEBHOOK_ERRORS).
- Webhook-Test: POST {"content":"Baki AIO Test"} -> HTTP 204 (ok).
- cart-Test 1 Task (de.topps.com, variant 51178597613808): Task 3 'ok' mit Checkout-Link (shop-de.topps.com/...). Orchestrator sendet CHECKOUT-Nachricht an Discord. Ein weiterer Task 'fail' (warmup).

## CSV-Import
- Neu: tools/import_profiles.py. Liest "Zahlungen - Kopie.csv" (UTF-8 mit BOM), Mapping shipping/* + cc/* + email + checkoutLimit nach profiles.yaml, Tabs entfernt, Karte ohne Leerzeichen, max_orders 0->2, Zeilen ohne Kartennummer uebersprungen, id p01/p02... Aufruf: `python tools/import_profiles.py <csv> [ziel]`. Test: 1 Profil importiert (p01, Sargbon Akfcan, Karte 9999999999991817, max_orders 2). Fix: CLI-Index argv[0]=Quelle.

## Profil-Generator
- Neu: core/profiles.py (generate_profiles, write_profiles) und CLI `toppsfarm.py profiles-gen --count N [--seed S] [--out DATEI]`. Erzeugt N Profile aus IdentityGenerator, id p01/p02/..., max_orders 2, leere Karte, schreibt config/profiles.yaml. Test N=3 seed=7 in temp. Datei: p01 Dominik Lang, p02 Klaus Marx, p03 Anja Braun, leere Karten, laedt via _row_to_profile (nur 'karte'-Warnung, erwartet).

## LETZTER TEST
- keys.env: CAPTCHA_PROVIDER, CAPSOLVER_KEY, DISCORD_WEBHOOK, DISCORD_WEBHOOK_ERRORS vorhanden (OK).
- Webhook-Test: POST {"content":"Baki AIO Test"} -> HTTP 204 (ok).
- cart-Test 1 Task (de.topps.com, variant 51178597613808): Task 4 'ok' mit Checkout-Link (shop-de.topps.com/...), Notiz 'storefront checkout-link'.
- Kartendaten in config/profiles.yaml p01.card eingetragen (4165983470214727, 09/2029, 954, Sargon Akcan). Per Python geprueft: number gesetzt, issues []. 10 cart-Tasks auf de.topps.com (variant 51178597613808): 10/10 'ok' (Tasks 5-14). Erster Checkout-Link: shop-de.topps.com/cart/c/hWNJNCvKPGDdAoinUBABUWGp (Task 5).

## BLOCKER
- products.json auf de.topps.com 403 auch mit Browser-Cookies (serverseitig); Storefront-API als Ersatz verdrahtet.

## Naechster Schritt
- Alle 7 Aufgaben + Nachgereichtes abgearbeitet. Offen nur Volllaeufe mit Live-Netz (Registrierungen, Monitor-Dauerlauf). keys.env ist .gitignored (bleibt lokal).