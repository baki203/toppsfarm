# STATE

Stand: 2026-11-20, Aufgaben 1-7 aus AGENTS.md.

## Erledigt
- 1: selftest gruen. Fix: `load_profiles()` versteht Identitaets-Format (street+house_no). Statuscodes via sitemap: de 200 (16), es 200 (126), fr 200 (154), it 200 (140).
- 2: Cloudflare-403 geloest. `cf_refresh()` oeffnet Browser, speichert cf_clearance+__cf_bm nach var/cf_cookies.json; `session()` reicht sie an curl_cffi weiter. Test: Homepage 200 (vorher 403), Storefront-API liefert Produkte. products.json bleibt serverseitig gesperrt (BLOCKER).
- 3: cart-Flow ok. de.topps.com ohne /cart/add.js (Next.js); neu `HttpCheckout._storefront_cart_link` (Storefront-cartCreate) -> echter checkoutUrl. Drop-Test 1 Task (Cameron Boozer, variant 51178597613808): Task 'ok' mit checkout-link. Orchestrator sendet URL als CHECKOUT-Nachricht an Discord.
- 4: baki.py Menue hat 14 Plaetze, Module 1-6 verdrahtet (Topps/Nike/Amazon/Riftbound/Pokemon/Toolbox), 7-14 Platzhalter ("-" + "noch nicht belegt"). Alle 6 Fabriken importieren, run() vorhanden. Menue startet (Banner ok).

## Offen
- 5: settings.json Defaults + crashlog.log Traceback-Handler.
- 6: release.zip bauen.
- 6: release.zip bauen.
- 7: README auf Baki AIO umschreiben.

## BLOCKER
- products.json auf de.topps.com 403 auch mit Browser-Cookies (serverseitig); Storefront-API als Ersatz verdrahtet.
- Discord-Link erst wenn DISCORD_WEBHOOK in config/keys.env gesetzt (fehlt, .gitignored).

## Naechster Schritt
- 5: settings.json Defaults + crashlog.log Traceback-Handler.