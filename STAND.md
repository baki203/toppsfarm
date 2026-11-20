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

## WEITER
Naechste Phase laut VORGEHEN.txt: B Amazon-Generator (non-PVA, mehrere Catch-All-Domains,
ADDRESS-Modus in 2. Session, Selftest). Plus: 14 PSN-Login+Queue, 15 release.zip + EXE-Auto-Update.