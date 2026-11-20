# STAND
Stand 2026-11-20, ARBEITSWEISE (8 Punkte) + 4 QUALITY-Luecken. Deutsch. Je Punkt: Test + STAND.md + commit + push.

## BLOCKER
- Skyridge-GitBook auth-geschuetzt (SPA nur JS-Shell, Content-API 403, kein Wayback-Mirror). Erkenntnisse stattdessen aus lokaler settings.json + crashlog.log (PyInstaller-Tracebacks) + PepperScripts-Doku.

## Stand Punkte
9 QUALITY-LUECKEN (A1 Catch-All, A10 SMS, A4 Geo, Proxy-Vorpruefung): erledigt.
   A1 core/mailbox.py provider catchall (<12-random>@domain) + _imap_wait_for_link. A10 core/sms.py
   (5sim/smspva/herosms, keys SMS_*_KEY), account_base nutzt nur auf Aufforderung (only_on_request=false
   + sites nike/amazon). A4 core/geo.py (ip-api) + geo_check in shopify_core/retail_core/account_base,
   banned:geo. Proxy core/proxycheck.py (var/proxystats.csv, mark_dead) + cmd_watch/cmd_drop + Toolbox
   Punkt 4. QUALITY.md Abschnitt E. Getestet: geo DE/FR/None, SMS ohne key sauber, proxy-precheck 2 tot,
   Topps-Selftest 4/4 200. Committet 92e018f + folgend.

## Stand Punkte
1 STRUKTUR: erledigt. accounts\ + proxies\ je Modul (topps, pokemoncenter, nike, amazon, riftbound, psn, mediamarkt, saturn, snkrs, smyths, shopify), je .gitkeep + README.txt (Format http://user:pass@host:port). Verifiziert.
2 SKYRIDGE LERNEN: erledigt. KNOWLEDGE.md: settings-Schema (Captcha/SMS-Provider, Geocoder, Mastermails+Catchall), Amazon (ADDRESS/SECRET/MONITOR-AWAIT, Adresse in 2. Session, Karte erst beim Kauf, Retry=SECRET, keine gleiche CC/Adresse ueber Konten), Nike SNKRS (FAST/SHOCK, ENTRY TIME, Browser zwingend, Billing==Shipping), Nike FCFS, Shopify (Preload, Shop <CC>-Regionen), PokemonCenter. Committet.
3 QUALITY.md: erledigt. QUALITY.md mit A1..A10-Pruefliste (Catch-All statt Wegwerf, persistentes Profil je Konto, sticky Wohn-IP je Konto, IP-Land/Region zur Adresse, Adressvariation, Browsen vor Registrierung, Adresse in 2. Session, Karte erst beim Kauf, Erstkauf klein/zeitversetzt, Telefon nur auf Aufforderung) + Messpunkten (attempts/success/banned/retries, Sperrquote %, Modulende-Ausgabe, var/quality.sqlite, Schwelle >25%). Umsetzung: modules/quality.py (Quality-Klasse, --quality-CLI), eingebunden in retail_core + account_base. Committet.
4 MENUE: erledigt (14 Plaetze, Belegung aus altem STAND).
5 SHOPIFY-KERN: erledigt (shopify_core.py, topps.py Wrapper, shopify.py generisch).
6 NICHT-SHOPIFY: erledigt (retail_core.py + psn/mediamarkt/saturn/snkrs/smyths).
7 TEST+BUILD: erledigt. Topps 4/4, generisches Shopify via storefront (200), Retail-Dryruns MediaMarkt+Saturn -> /de/checkout, de.topps Storefront-cartCreate -> echter CHECKOUT-Link, release.zip 57 MB neu gebaut + EXE-Selftest 4/4 gruen, README um QUALITY ergaenzt. Committet.
8 REIHENFOLGE: 2,3 -> 5 -> 4,6 -> 7. 5 vor 6 bei Zeitdruck.

## Erledigt (belegt, kompakt)
- Menu 1-14 (alle 12 belegt, 13-14 Platzhalter) startet; alle Modul-Factories instanziieren; EXE menu-only.
- Topps-Selftest 4/4 gruen; MediaMarkt+Saturn-Dryrun -> /de/checkout; release.zip (57 MB, ohne secrets) getestet.
- Analyse-Werkzeuge: pyinstxtractor-ng (venv), UPX (winget). Main-EXE = .NET-Launcher (.fptable, 1x MZ); UPX/NSIS-Marker false positive; Inbox-EXE = Tauri (inbox.skyridge.eu).

## Naechster Schritt
10 DISCORD-AUSWERTUNG: erledigt. discord/auswerten.py (nur Stdlib): Vorfilter (bot/emoji/links/
   gruesse/<15Z/duplikate, Format an ersten 30 Zeilen), Relevanzfilter (15 Begriffe), Stuecke
   100k/max 40, POST an Venice-API (VENICE_API_KEY/MODEL aus keys.env, Parser load_env),
   Anweisung max 60 Bullets mit [Kanal|Monat], WISSEN_roh.md + fortschritt.json (Neustart
   springt Erledigtes ueber), Kosten 0,175/0,35 je 1M, Stopp bei 1,00 $. .gitignore: discord/*
   ausser auswerten.py + WISSEN.md. Getestet: Vorfilter 10368 Nachr. -> 14 Stuecke, $0.067/Lauf;
   Teststueck 0 ($0.007) liefert 60+ Amazon-Fakten (2captcha, ARKOSE_LEVEL_1/4, SMS-Provider,
   ~500 Konten/Tag, catchall vs aliases, Invite-Fenster 21-22U). Voller Lauf $0.10 (14 Stuecke),
   WISSEN.md konsolidiert (108 Zeilen, nach Thema, Zaehler, behauptet-Markierung), WISSEN_roh.md
   geloescht. Committet fdfb882.
11 UMSETZUNG DISCORD-ERKENNTNISSE: erledigt. KNOWLEDGE.md Abschnitt 9 (nur xN>=3, als behauptet,
   Nutzer-Korrekturen als Fakt): Captcha/ARKOSE, Proxy-Regeln (1 Konto/Proxy, kein Wechsel),
   Catch-All vs Aliases, Domain-Klima (~1k/Domain, 5 Tage Ruhe), Invite-Fenster 21-22U, Ban-Ursachen
   SIM/Proxy, Amazon-Endpunkte, Kasada/Akamai. QUALITY.md: detect-Musterliste erweitert
   (ARKOSE_LEVEL_1/4/5, captcha verification failed, couldn't submit data, proxy auth failed, 407,
   ghost account, pva_locked, kasada block, akamai block) in modules/quality.py + Abschnitt B,
   A3 (1 Konto/Proxy, kein Wechsel nach Gen), C4/C9. Getestet: compileall ok, Topps-Selftest 4/4.

## Stand Punkte
12 SKYRIDGE-UMBAU: erledigt. Wurzel BakiAIO\: baki.py, crashlog.log, settings.json, START.bat,
   requirements.txt, README.md. utilities\ (core\ + quality.py + logger\CrashLogger.py). modules\base.py
   (BaseModule.make_tasks/runTask + BaseTask.__init__/startRequest/_preCheck/runTask-Retry), Engine\Shopify\
   shopify_core.py, Engine\Retail\ retail_core.py + tasks.py, Engine\Generator\tasks.py. Generators\<Site>\
   modules\<Feature>\<Feature>Module.py + <Feature>Task.py je Feature (Amazon Invites/Address/Secret,
   Nike FCFS/SNKRS, Topps Drop, PokemonCenter/PSN QueueCheckout, MediaMarkt/Saturn/Smyths Monitor,
   Riftbound RaffleEntry, Shopify GuestCheckout, Toolbox ProxyTest) + __init__.py ueberall. settings.json
   primaer (yaml nur Fallback), settings.yaml bleibt in config. ROOT-Suche bis config gefunden. Importe
   core.->utilities., modules/__init__.py alte Pfade als Aliase. Getestet: compileall sauber, Menue 1-14
   startet (13-14 frei), alle Modul-Factories importierbar, Topps-Selftest 4/4 200. Committet.

## Stand Punkte
13 TOPPS-DROP-FERTIG: erledigt. shopify_core.py cmd_drop um --at HH:MM (Scheduler _drop_wait_until),
   --target (Name aus targets.yaml), --dry, max_price-Pruefung (HttpCheckout._price_ok ueber storefront/
   products.json, kein Block wenn unbekannt), Prewarm cf_refresh vor Drop. Orchestrator.spawn reicht
   max_price durch. targets.yaml: Chrome-UEFA + Topps-EU-Hosts (de/es/fr/it), max_price/asin-Felder.
   Getestet: compileall sauber, HttpCheckout liefert echten de.topps.com Checkout-Link (storefront
   cartCreate -> https://shop-de.topps.com/cart/c/...), cmd_drop 1 Task -> 1 ok/0 gesperrt (dry).
   config/profiles.yaml Testprofil angelegt. Committet.

## Stand Punkte
14 PSN-LOGIN+QUEUE: erledigt (Implementierung). QueueCheckoutModule: PSNCheckout.login(email,
   password, proxy) mit persistentem Browser-Context (var/browser-psn), Sony-Login (ca.account
   .sony.com/ssocookie), auto re-login (Session-Erkennung ueber /login in URL), Speicherung der
   Cookie-Session. PlayStatinModule.run: Menu-Punkt 3 Login. accounts/psn/profiles.yaml (gitignored,
   1 Konto/Proxy, Geo DE). Queue-it-Checkout via geerbte RetailCheckout.run (dry_run Stopp vor Zahlung).
   Getestet: compileall sauber, Import ok, Login-Dryrun navigiert zur Sony-Login-Seite, erkennt
   Login-Formular korrekt, note 'login moeglicherweise fehlgeschlagen' (Test-Credentials). BLOCKER:
   echter Anmeldetest nur mit echten PSN-Credentials moeglich (liegen nicht vor).

## Stand Punkte
15 RELEASE + EXE-AUTO-UPDATE: erledigt. baki.py: _auto_update() ersetzt beim Start die laufende
   BakiAIO.exe durch eine daneben abgelegte BakiAIO.exe.new (nur wenn sys.frozen, sichere alte als
   .old). spec auf BakiAIO\\baki.py umgestellt. EXE 60MB gebaut; EXE-Selftest 4/4 gruen (de/es/fr/it
   200), alle Module (Topps/PSN/Toolbox) in der EXE geladen. release.zip (60MB) neu gebaut und getestet
   (Menue startet). Keine Secrets in EXE. Committet.

## Stand Punkte
16 AMAZON-AIO (7 Module, 21 Domains): erledigt. Neu modules/Engine/Amazon/amazon_core.py
   (DOMAINS 21 CC->domain/Waehrung/Locale, SkyLogger farbige Skyridge-Zeile [zeit][tid][Site Feature]
   [ASIN][email] Meldung, StatusBar-Kopfzeile, SessionStore var/sessions/amazon/<email>/ Cookies+Profil,
   AmazonClient Signin/add_shipping_address/set_location, load_accounts aus accounts/Amazon).
   modules/Generators/Amazon/AmazonAIO.py Untermenue 7 Punkte: 1 Gen, 2 Reset, 3 Invites, 4 Invite
   Checker, 5 Farmer, 6 Session Manager, 7 ACO. baki.py _amazon -> AmazonAIOModule. modules/__init__
   Alias modules.amazon_aio. Getestet: compileall sauber, 21 Domains, Skyridge-Logzeile + Statusbar
   rendern korrekt, amazon.de Produktseite 200, alle 12 Menue-Factories laden. BLOCKER: amazon.de
   Auth-/forgotpassword-Endpunkte liefern 202/404 (Anti-Bot) - Modul nutzt SessionStore (echte
   Browser-Cookies) + Browser-Generator dafuer; ACO/Farmer/Reset brauchen echte eingeloggte Session.

## Stand Punkte
17 PROXY-INTEGRATION + GENERATOR-LAUF: erledigt. Zentral utilities/proxy.py (source auto|shared|module
   aus settings.json proxy.source, normalize host:port:user:pass + http://user:pass@host:port +
   user:pass@host, Playwright-Dict, mask user:***@host, auth-Fehlerdetekt, parse). Quellen: je Modul
   proxies/<modul>/ > shared proxies/proxies.txt (alle leer -> shared aktiv). Verdrahtet: shopify_core
   (ProxyPool round-robin), retail_core (Monitor/Checkout), account_base (AccountGenerator+run_generator),
   AmazonAIO/amazon_core, PSN login, browser.Browser. Auth-Fehler -> proxy-auth (kein Ban). Vorpruefung
   proxycheck 5 Hosts (amazon.de/nike.com/pokemoncenter.com/playstation.com/de.topps.com). Daten
   data/de_*.txt (first/last/street/places zip;city;area_code) angelegt (IdentityError behoben). Amazon
   generate() schreibt jetzt Artifact accounts/Amazon/<email>.txt. Getestet (je 1 Task, 1 lebender Proxy):
   NikeGen 1/1 Artifact, RiftboundGen 1/1 Artifact, AmazonGen 1/1 Artifact (mailtm, non-PVA), SNKRS-
   Checkout-Dryrun ok, MediaMarkt+Saturn-Dryrun -> /de/checkout ok, Topps-Selftest 4/4 200, Topps-
   Drydrop -> echter shop-de.topps.com/cart/c/ Checkout-Link (storefront, obwohl products.json 403),
   PSN-Checkout-Dryrun ok + Login navigiert zur Sony-Seite (Test-Credentials). compileall sauber.
   Committet 2013e6e.

## Stand Punkte
18 NIKE DRAW-ENTRY (LEO/DAN): erledigt (Phase C). Neu modules/Generators/Nike/modules/DrawEntry/
   DrawEntryModule.py + DrawEntryTask.py. Klasse DrawEntry: Login (persistente Session
   var/browser-nike-<email>), Produktseite laden, Drop-Zeit parsen (_parse_drop_time: benannte Felder
   launchDate/goLiveTime/productLaunchDate/productLaunchTime + JSON-LD/meta, Fallback naechste
   zukuenftige ISO-Zeit aus __NEXT_DATA__/Text), optional warten bis Entry-Zeit (--at), Groesse
   waehlen, Entry abgeben (Billing==Shipping, BPE vermeiden). Konten aus accounts/Nike/*.txt.
   baki.py Menue-Punkt 13 'Nike Draw-Entry (LEO/DAN)'. Getestet: compileall sauber, Menue-Punkt 13
   laedt, _parse_drop_time alle Faelle (named/fallback/past/none), live Produktseite ueber Proxy
   laedt (450KB), Launch-Links von /de/launch extrahiert. BLOCKER: threads-/productfeed-API
   (api.nike.com/.../threads) ueber Proxy 404 (Akamai) - Drop-Zeit daher aus HTML/__NEXT_DATA__;
   echter Entry braucht aktiven Launch + echte Nike-Credentials (accounts/*.txt sind generator-artefakte).

## Stand Punkte
19 PHASE D+E+F RETAIL/SHOPIFY: erledigt (soweit nicht extern blockiert).
   D: cf_refresh jetzt proxy-gebunden (cf_clearance ist IP-gebunden; Browser laeuft durch
   denselben Proxy, damit Cookies zu curl_cffi-Requests passen). products.json bleibt 403,
   weil die Proxy-IPs von Cloudflare domainspezifisch geblockt werden (Homepage 403, Sitemap
   200, Storefront-API 200 - externer Proxy-Reputations-Blocker, kein Code-Fehler). Shopify
   Guest-Checkout ueber Storefront-cartCreate GETESTET live ueber Proxy: echter Checkout-Link
   https://shop-de.topps.com/cart/c/... (Variante 51178597613808, 9.99 EUR). E: PokemonCenter
   Settings-Feld pokemon_hosts (www.pokemoncenter.com + /de-de + /en-gb), Monitor nutzt
   Default beide Stores; Queue-it-Erkennung per Unit-Test gruen (queueclient.js/knowntoken).
   PokemonCenter selbst 403 ueber Proxy-IP (extern). F: RetailCheckout._dismiss_consent
   (Consent-Wall wegklicken, dt/EN-Selektoren) + _jsonld (Product/Offer, Preis+Availability);
   live MediaMarkt-Checkout ok (consent weg, checkout vorbereitet, 0% Sperrquote).
   F: RetailMonitor._last_status + banned:http-Zaehlung (401/403/429) - MediaMarkt/Saturn/
   Smyths setzen _last_status; MediaMarkt 200 items, Saturn 200 items, Smyths 200 status.
   compileall sauber. Committet.

## Stand Punkte
20 BUILD + RELEASE: erledigt (Phase G). BakiAIO.spec (PyInstaller 6.22.3, collect_all
   curl_cffi/playwright/pyfiglet) rebuilt (--noconfirm --clean, exit 0), dist/BakiAIO.exe
   62.3 MB. EXE-Selftest: Menue zeigt alle 13 Slots (13 Nike Draw-Entry, 14 frei), Topps-Modul
   laedt. release.zip neu gebaut (61.7 MB, 1 Entry BakiAIO.exe, gitignored). Topps-Selftest
   aus Quelle 4/4 200. Git-Tag fuer Release angelegt.

## Stand Punkte
21 PROXY-FORMAT: erledigt. utilities/proxy.py normalize_proxy: bevorzugtes Eingabeformat
   IP:PORT:USERNAME:PASSWORD (regex statt split, damit Passwoerter mit Doppelpunkt sicher
   verarbeitet werden; letzter Doppelpunkt trennt das Passwort). Auch akzeptiert:
   http://user:pass@host:port, user:pass@host:port, host:port. Verifiziert: 1000 Zeilen
   proxies/proxies.txt alle parse ok. Docs aktualisiert: proxies/README.txt + alle
   proxies/<modul>/README.txt + BakiAIO/README.md dokumentieren IP:PORT:USERNAME:PASSWORD.

## Stand Punkte
22 AMAZON-AIO KOMPLETT (7 Module + ACO, Skyridge-Muster): erledigt.
   Nur Session Manager browser-basiert (wie Skyridge), Rest HTTP ueber AmazonClient
   mit wiederhergestellten Cookies (SessionStore restore). AmazonAIO.py komplett
   neu: 1 Gen (HTTP non-PVA Catch-All-OTP), 2 Reset (forgotpassword+OTP), 3 Invites
   (volles Skyridge-Log: Loading product page attempt x/3 -> Fetched invite details
   [Titel|Price|ID] -> Checking availability -> Requesting invite -> Invite
   requested! / Already requested, skipping / Already entered), 4 Checker (won/lost),
   5 Farmer (cart+wishlist), 6 Session Manager (Browser eingeloggt oeffnen, optional
   offen lassen), 7 ACO (Produkt-ID+Dummy-Items, PLZ/Locker, card/ideal=BankQ/Revolut),
   8 ADDRESS, 9 Selftest. amazon_core.py: AmazonBrowser (persistenter Kontext je
   Konto var/browser-amazon-<cc>/<email>, restore_or_login, goto_product, invite,
   precheckout) + AmazonClient HTTP-Methoden (fetch_invite_details mit HTML-unescape,
   request_invite, check_invite, add_to_cart/wishlist, checkout) + SkyLogger
   render_status erweitert (invited/already invited/entered/requested/won/lost/
   restored/added/created/error/skipped, StatusBar.header Kopfzeile). Getestet:
   compileall 0, 21 Domains, Statusleiste korrekt, Invite-Flow unit-getestet
   (requested/already), LIVE amazon.de fetch_invite_details liefert echte Details
   ("Pokemon-Sammelkartenspiel: Display-Box..." 264,90 EUR). BLOCKER: echter
   Invite-Request/Checkout braucht eingeloggte Session (Anti-Bot) - ueber
   Session Manager (nur User kann Captcha/OTP loesen) herstellen.

## Stand Punkte
23 AMAZON SESSION-SYNC: erledigt. Session Manager exportiert nach erfolgreichem
   Login die Browser-Cookies in den SessionStore (AmazonBrowser.export_cookies ->
   var/sessions/amazon/<email>/cookies.json). Damit koennen die HTTP-Module
   (Invites, Farmer, Invite Checker) per c.restore() dieselbe Session wiederher-
   stellen, ohne sich neu einzuloggen (Skyridge-Verhalten). Getestet: compileall 0,
   export_cookies vorhanden, restore() laedt SessionStore-Cookies korrekt.

## WEITER
Offen: echter PSN-Anmeldetest braucht echte Credentials; Amazon echte Invite-Request/
Checkout/ACO braucht eingeloggte Session via Session Manager (nur User kann Captcha/
OTP loesen; Endpunkte laut KNOWLEDGE behauptet, variieren je Domain); de.topps
products.json und PokemonCenter ueber Proxy-IP 403 (Cloudflare-Proxy-Reputations-
Blocker, Sitemap/Storefront funktionieren); voller Nike-Draw-Entry braucht aktiven
Launch + echte Credentials; volle 1000er-Proxy-Vorpruefung (~40 min) nur in Background/
Chunks. Danach: weitere Discord-Themen laut KNOWLEDGE (Shopify Preload, Amazon-Invite-
Fenster 21-22U) je nach Bedarf.