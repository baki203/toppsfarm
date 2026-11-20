# STATE

Stand: 2026-11-20, Aufgaben 1-7 aus AGENTS.md.

## Erledigt
- 1: selftest gruen. Fix: `load_profiles()` in modules/topps.py versteht Identitaets-Format (street+house_no). Statuscodes: de.topps.com 200 (sitemap 16), es.topps.com 200 (126), fr.topps.com 200 (154), it.topps.com 200 (140). p01 nur "karte" (leere Karte, Datenwarnung).

## Offen
- 2: Cloudflare-403 loesen (Cookies an curl_cffi) damit products.json 200 liefert.
- 3: cart-Flow mit echtem Produkt, 1 Task, Discord bekommt Checkout-Link.
- 4: baki.py Menue auf 14 Plaetze, Module 1-6 verdrahten, Rest Platzhalter.
- 5: settings.json Defaults + crashlog.log Traceback-Handler.
- 6: release.zip bauen.
- 7: README auf Baki AIO umschreiben.

## BLOCKER
- 2 ist nicht 1:1 loesbar wenn /products.json auf de.topps.com per Cloudflare permanent 403 liefert; Fallback Storefront-API schon im Monitor.

## Naechster Schritt
- 2: Cloudflare-Cookies.