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

## LETZTER TEST
- keys.env: CAPTCHA_PROVIDER, CAPSOLVER_KEY, DISCORD_WEBHOOK, DISCORD_WEBHOOK_ERRORS vorhanden (OK).
- Webhook-Test: POST {"content":"Baki AIO Test"} -> HTTP 204 (ok).
- cart-Test 1 Task (de.topps.com, variant 51178597613808): Task 4 'ok' mit Checkout-Link (shop-de.topps.com/...), Notiz 'storefront checkout-link'.

## BLOCKER
- products.json auf de.topps.com 403 auch mit Browser-Cookies (serverseitig); Storefront-API als Ersatz verdrahtet.

## Naechster Schritt
- Alle 7 Aufgaben + Nachgereichtes abgearbeitet. Offen nur Volllaeufe mit Live-Netz (Registrierungen, Monitor-Dauerlauf). keys.env ist .gitignored (bleibt lokal).