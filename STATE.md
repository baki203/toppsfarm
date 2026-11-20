# STATE

Stand: 2026-11-20, Aufgaben 1-7 aus AGENTS.md.

## Erledigt
- 1: selftest gruen. Fix: `load_profiles()` in modules/topps.py versteht Identitaets-Format (street+house_no). Statuscodes: de 200 (16), es 200 (126), fr 200 (154), it 200 (140), je via sitemap. p01 nur "karte" (leere Karte).
- 2: Cloudflare-403 geloest. Neu in modules/topps.py: cf_cookies(), cf_refresh(host) (oeffnet sichtbaren Browser, wartet auf cf_clearance, speichert Cookies nach var/cf_cookies.json), session() haengt Cookies an. Befehl `cf-refresh`. Test: Homepage 200 (vorher 403), Storefront-API liefert Produkte. products.json bleibt serverseitig beim Next.js-Shop gesperrt, Produktdaten via Storefront-API (topps-deu.myshopify.com, 200).

## Offen
- 3: cart-Flow mit echtem Produkt, 1 Task, Discord bekommt Checkout-Link.
- 4: baki.py Menue auf 14 Plaetze, Module 1-6 verdrahten, Rest Platzhalter.
- 5: settings.json Defaults + crashlog.log Traceback-Handler.
- 6: release.zip bauen.
- 7: README auf Baki AIO umschreiben.

## BLOCKER
- /products.json auf de.topps.com liefert auch mit Browser-Cookies dauerhaft 403 (serverseitig gesperrt); Ersatz ist die Storefront-API, im Monitor schon als Quelle verdrahtet.

## Naechster Schritt
- 3: cart-Flow, 1 Task, Discord-Checkout-Link.