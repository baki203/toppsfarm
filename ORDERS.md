- [x] 3 | Exe bauen mit .\.venv\Scripts\pyinstaller.exe --noconfirm --onefile --name toppsfarm --collect-all curl_cffi --collect-all playwright toppsfarm.py. Muss ohne Traceback durchlaufen.
- [ ] 4 | .\dist\toppsfarm.exe selftest ausführen, Host-Zeilen wörtlich mit Statuscodes nach STATUS.md. de.topps.com muss 200 mit products-JSON liefern.
- [ ] 5 | cart-Flow testen: günstiges verfügbares Produkt von de.topps.com, Variant-ID aus /products.json?limit=20, dann .\dist\toppsfarm.exe drop --host de.topps.com --variant <id> --tasks 1 --mode cart. Erwartung: Discord "checkout vorbereitet" mit URL. Bei "kein checkout-token" oder "fill 4xx" Token-Parsing debuggen.
- [ ] 6 | hCaptcha-Injektion prüfen: Token muss als checkout[hcaptcha_response] mit _method=patch gepostet werden, Sitekey-Erkennung muss greifen.
- [ ] 7 | release.zip bauen aus dist\toppsfarm.exe, config, START.bat, README.md.
Schritt 4 hängt an Cloudflare 403 auf /products.json. Diagnose-Matrix, jede Variante einzeln, jede Zeile mit Statuscode nach STATUS.md:

1. Minimale Header: nur accept und accept-language selbst setzen, restliche Header dem impersonate überlassen. Test gegen https://de.topps.com/products.json ohne Query.
2. impersonate-Varianten durchprobieren: chrome, chrome131, chrome124, safari17_0, firefox133. Nicht installierte überspringen.
3. HTTP/1.1 erzwingen statt h2.
4. Mit und ohne ?limit=250 vergleichen.
5. Falls weiter 403: /sitemap.xml, /sitemap_products_1.xml und /products/<handle>.js testen.
6. Falls Sitemap erreichbar: Monitor auf Sitemap umbauen. Neue Handles aus sitemap_products_1.xml diffen, Variant-ID aus /products/<handle>.js.
7. Zusätzlich Storefront-API: Access-Token aus den Theme-JS-Bundles von de.topps.com extrahieren (Suche nach X-Shopify-Storefront-Access-Token), GraphQL-products-Query testen.

Zwischen den Punkten jeweils committen und pushen. Kein Browser, alles mit curl_cffi.