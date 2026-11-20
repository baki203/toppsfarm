# STAND
Stand 2026-11-20, ARBEITSWEISE (8 Punkte) + 4 QUALITY-Luecken. Deutsch. Je Punkt: Test + docs/STAND.md + commit + push.

## Stand Punkte
26 APP_ROOT-EXE + SETUP-BUILD + STARTFESTIGKEIT + TEST + AUFRAEUMEN: erledigt.
   utilities/root.py zentral: frozen -> APP_ROOT==ROOT==EXE-Ordner, KEIN Walk ueber
   config/; ungefroren APP_ROOT=BakiAIO\, ROOT=Repo-Root. shopify_core/proxy/amazon_core/
   profiles/account_base/quality/proxycheck auf Helfer umgestellt. ensure_runtime legt
   accounts/proxies/Address Toolbox/var + crashlog.log an; ensure_settings erzeugt aus
   settings.example.json (Hinweis, kein Abbruch); baki.py nutzt APP_ROOT-Crashlog.
   build_setup.ps1: onefile EXE -> frisches dist\BakiAIOSetup\ mit BakiAIO.exe,
   settings.json (aus example), leerem crashlog.log/FirstNames/LastNames, accounts/proxies/
   "Address Toolbox" mit .gitkeep, ohne .md/.py/config; + BakiAIOSetup.zip (Setup bleibt).
   identity.py: Generator liest FirstNames.txt/LastNames.txt aus APP_ROOT, Fallback
   gebuendelte data/de_*.txt (Spec bündelt BakiAIO/data). Daten nach docs\ verschoben
   (AGENTS/STAND/VORGEHEN/QUALITY/KNOWLEDGE/ORDERS/STATUS/VERLAUF_archiv/claude.log/test.txt);
   AGENTS-STAND-Pfade auf docs/STAND.md. Getestet: compileall 0, Source-Root ok, frozen-
   Simulation APP_ROOT==ROOT==EXE-Ordner, Identity-Override (FirstNames aus APP_ROOT),
   Mailbox-Mastermail fehlt -> klare Meldung kein Abbruch, Topps-Selftest 4/4 200,
   dist\BakiAIOSetup\BakiAIO.exe gestartet: Menue 1-13 + Amazon-AIO-Untermenue erreichbar,
   crashlog.log im Setup-Ordner angelegt, Setup-Ordner+Zip korrekt (kein Quellmuell).
26b SETUP-MIT-ECHTEN-WERTEN + AMAZON-GEN: erledigt. settings.json (BakiAIO\ + dist\Setup)
    mit ECHTEN Werten aus Skyridge-Settings befuellt: 570 Mastermails, CaptchaProvider
    (2Captcha/CapSolver/NoneCap), SMSProvider, GeoCoder, Amazon; SkyridgeInbox entfernt;
    mail.provider=catchall, imap_host=imap.gmail.com, port 993, since_days 1 (Mastermail
    -> Gmail-IMAP). build_setup.ps1 kopiert jetzt BakiAIO/settings.json (echt, sonst
    example) + proxies\proxies.txt (1000) ins Setup. Amazon-Gen-Fixes: AmazonAIO
    SessionStore-Import fehlte (NameError), baki.py _auto_update Path-Import fehlte;
    _gen_one loggt Ursache (Register-Page http-Code statt stilles 'failed'). Getestet:
    compileall 0, Settings-Mapping ok, IMAP-Login an Gmail OK (592 Mails), Catch-All-Inbox
    korrekt, Amazon-Gen laeuft bis HTTP-Schicht + loggt Ursache, Setup neu gebaut (EXE +
    settings 87KB + proxies.txt, kein SkyridgeInbox). BLOCKER: Amazon liefert fuer
    Proxybaron-IPs Homepage 202 + Auth-Endpunkte 404 (Anti-Bot/Proxy-Reputation), Selftest
    100% Sperrquote - echte Registrierung mit aktuellem Proxy-Pool nicht moeglich (kein
    Code-Fehler).

25 AGENTS+SETTINGS+OTP-IMAP: erledigt. AGENTS.md ersetzt (strikte Ausgabe: keine Vorrede,
   max 1 Zeile/Werkzeugruf, Ende 'fertig'+Tabelle(5)+Commit-Hash, STAND.md einziger Stand,
   nie fragen, echter Test je Schritt). settings.json auf exaktes Skyridge-Schema (license-key,
   discord-webhook, deviceRotation, remoteControl, CaptchaProvider, SMSProvider, GeoCoder,
   Mastermails, OAuthForwarder, SkyridgeInbox, Ejoin, Amazon, AycdInbox) + settings.example.json
   (committet, leer). Settings.load() mappt Skyridge->Dataclass (Mastermails->mail.catchall,
   CaptchaProvider->captcha, GeoCoder->geo, SMSProvider->sms, Amazon->amazon), liest settings.json
   zuerst aus APP_ROOT (BakiAIO\), Toppsfarm-Felder bleiben kompatibel. mailbox.py catchall jetzt
   Mastermails-basiert (round-robin, imap_host-Ableitung gmail->imap.gmail.com, since_days-Fenster,
   confirm_regex fuer Links+Codes, delete_after_fetch, OAuthForwarder als 2. Quelle, klarer Fehler
   'IMAP nicht konfiguriert'). AmazonAIO Gen/Reset nutzen catchall non-PVA ohne Telefon. Getestet:
   compileall 0, Settings-Mapping (hosts/captcha/geo/amazon/proxy ok), Mailbox 3 Faelle ok,
   Topps-Selftest 4/4 200, baki+Amazon import ok. BLOCKER: ohne echte Mastermails in settings.json
   bleibt OTP blockiert (imap) - Mastermails aus Sicherheitsgruenden nicht kopiert, User traegt sie
   in BakiAIO/settings.json ein (gitignored).
25b TOPPS-DROP PER LANDING-PAGE: erledigt. shopify_core.py --resolve <url> (nur Modul topps,
    mit --at) statt fester ID. 6-stufige Kaskade (jede Stufe nur wenn vorige leer): 1) URL ist
    selbst /products/<handle> -> exaktes Handle zuerst; 2) Handle-Extraktion aus Landing-HTML;
    3) search/suggest.json (de.topps deaktiviert, leer); 4) neue Produkte storefront
    CREATED_AT reverse; 5) Sitemap-Sprung (sitemap_products_1.xml, Fallback letzte Teil-Sitemap
    /products/sitemap/N.xml - erster Pfad liefert SPA-HTML); 6) Slug-Kandidaten. Dann
    product(handle:) -> Varianten-ID/Preis/availableForSale, max_price-Pruefung, ID-Polling auf
    available (1,5s) -> cartCreate -> CHECKOUT-Link + Discord. Ohne --resolve unveraendert
    (targets.yaml). Getestet: compileall 0, Topps-Selftest 4/4 200, CLI --resolve auf echter
    Landing-Page loest exaktes Handle (Yaxel Lendeborg Card 95, Variante 51171485155568,
    9.99) + echter shop-de Checkout-Link, alle 6 Stufen einzeln belegt.

25c TOPPS-DROP 4-PUNKTE-UPGRADE: erledigt. shopify_core.py: 1) Zielaufloesung --
    --target <handle|variant> (Default, targets.yaml) ODER --resolve <landing-url>
    Kaskade (cf_refresh ueber Task-Proxy -> HTML: /products/<handle>+eingebettete
    handles+Collection-IDs -> Collection-storefront-Produkte -> suggest.json ->
    sitemap -> slug-Kandidaten; erster Treffer -> exklusiv ID-Pfad). Kein Ziel =
    Fehler, kein Blindlauf. 2) Speed-Pfad: 90 s vor --at cf+Session+cartCreate
    (Cart-Link im Speicher), --at HH:MM|HH:MM:SS (monotone Uhr), Poll 1,0 s
    availableForSale (ein Endpunkt, gleiche Session+Proxy), max_price aus Prewarm-
    Cache, Adresse+Karte vorab. 3) Checkout+Webhook: run_prebuilt nutzt URL aus
    Redirect (Shop-Domain), vollautomatisch (Queue->Form->Karte->pay). ERFOLG-Webhook
    (Produkt/Preis/Order/Konto/Zeit) NUR bei Order-Beleg, sonst 'prepared';
    Fehler-Webhook an _ERRORS (Ursache+Cart-Link). Quality-Zaehler
    attempts/success/banned/retries+Sperrquote. Webhook-Setup wird geloggt.
    4) Test: precheck aus drop entfernt (1000er-Vorpruefung war der Speed-Blocker,
    bleibt in watch; acquire/mark_dead regeln Proxy-Gesundheit). Getestet:
    compileall 0, Topps-Selftest 4/4 200, --target-Drydrop -> echter
    shop-de.Checkout-Link, --resolve-Dryrun -> exaktes Handle+Variante+Preis,
    --at-HH:MM:SS-Prewarm -> warte bis --at -> Checkout, Poll 1,0 s belegt.
25d TOPPS-DROP VOLLAUTOMATISCH (AUFGABE 1-6): erledigt. shopify_core.py: 1) Zielwege
    --target <name|variant-id|handle> (mehrfach) schnell -> direkt Poll (kein Resolve,
    Log 'target'); Fallback --set <setname> oder --resolve <set-url> (Kaskade). Ohne
    beides Fehler, kein Blindlauf. 2) ID-Validierung nur T-90..T-10 (nie in letzten 10s),
    stale -> auto Neuaufloesung + Write-back (Timestamp/Quelle/alte ID). 3) Kaufentscheidung:
    Signale (a) Titel hobby|jumbo, (b) Tags/typ/Collection hobby|display|box, (c) Preisband;
    Kauf bei >=2/3; Einzelprodukt-Regel (nur Variante + Preis im Band -> kaufen). Nutzerlisten
    je Set (negativ/positiv/allow, Precedence allow>negativ>positiv>Preisband, leer=Defaults,
    Wortgrenzen+Plural-s). Code-Negativ value/mega/eco/tin/starter/blaster/retail/loose;
    Zubehoer sleeve/binder/toploader/playmat immer raus. Whitelist hobby vor jumbo (hobby 20s,
    jumbo Fallback 0s), jumbo-only sofort. min_price-Vorschlag (Median 5er Hobby-Preise -30%)
    als Kommentar in targets.yaml. YAML-Fehler -> Abbruch mit Zeilennummer. targets.yaml neues
    Schema (set/handle/variant_id/priority/min_price/max_price/qty + Listen). 4) Speed: 90s vor
    --at cf+Session+cartCreate fuer alle Plan-Varianten, Poll 1,0s, eine Order je Konto.
    5) Checkout+Webhook: vollautomatisch, ERFOLG nur mit Order, Fehler an _ERRORS.
    Getestet: compileall 0, Entscheidungstests 22/22 (Signale, Listen, Whitelist, Preisband,
    Plural-s), --target numerisch+Name -> CHECKOUT, --resolve loest+entscheidet (Einzelkarte
    korrekt verworfen), --set Setname-only kein Treffer (erwartet), Write-back-Patch ok,
    Topps-Selftest 4/4 200.

## BLOCKER
- Skyridge-GitBook auth-geschuetzt (SPA nur JS-Shell, Content-API 403, kein Wayback-Mirror). Erkenntnisse stattdessen aus lokaler settings.json + crashlog.log (PyInstaller-Tracebacks) + PepperScripts-Doku.
- echter Live-Checkout (nicht dry) braucht echte Karte+Verfuegbarkeit+mglw. 3DS; de.topps hat keine oeffentlichen Collections (Kaskadenstufe leer, laeuft weiter).

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
24 AMAZON SKYRIDGE-DATEILAYOUT EXAKT NACHGEBILDET: erledigt. Neues Modul
   modules/Engine/Amazon/amazon_store.py (AmazonStore) reproduziert das reale
   Skyridge-Layout 1:1 (Quelle: C:\Users\sargo\Desktop\SkyridgeSetup):
   gen_/custom_/tasks_/checked_/invited_/farmed_/taskcc_/checkout_/orders_
   _AmazonAccounts.csv + invites/<ASIN>_AmazonAccounts.csv + .sessions/<email>__<CC>.json
   + asinHistory.txt. Spalten klein geschrieben, nur Append, Dedupe ueber
   Email/ASIN. AmazonAIO verdrahtet: Generator->gen_, Invites->invited_+invites/
   +asinHistory, Farmer->farmed_, Checker->checked_, ACO->checkout_+asinHistory,
   Session Manager->.sessions/<email>__<CC>.json. AmazonClient.restore()/save()
   lesen/schreiben bevorzugt die Skyridge-.sessions-Datei (Fallback SessionStore).
   Getestet: Store-Kern (alle Dateiarten, Dedupe, ASIN-Grossschreibung,
   asinHistory, Session), Client-Restore aus .sessions, compileall 0. Grund fuer
   genaue Nachbildung: reales Skyridge ist bewiesen funktionsfaehig.
   Session Manager ist NICHT die Login-Quelle. Flow: Account Generator (HTTP,
   Request-Mode) -> Konten in accounts/Amazon/<email>.txt -> load_accounts liest
   Tasks-CSV + .txt + yaml (Dedupe ueber Email, Keys normalisiert lowercase).
   Invites/Farmer/Invite Checker lesen dieselben Konten, nutzen pro Zeile die
   PID (CSV-Spalte) als ASIN und loggen per HTTP (signin) ein - ohne Session
   Manager. Session Manager bleibt nur fuer manuelles Browser-Checkout.
   Fixes: accounts_dir() als kanonischer Ordner (repo-Root/accounts/amazon, vorher
   inkonsistent BakiAIO vs. root), ROOT-Walk bis config/ vorhanden, Generator
   schreibt ueber accounts_dir. Getestet: compileall 0, load_accounts liefert
   txt-Artefakt + CSV-Zeile mit PID korrekt, Dedupe funktioniert.

## WEITER
Offen: echter PSN-Anmeldetest braucht echte Credentials; Amazon echte Invite-Request/
Checkout/ACO braucht eingeloggte Session via Session Manager (nur User kann Captcha/
OTP loesen; Endpunkte laut KNOWLEDGE behauptet, variieren je Domain); de.topps
products.json und PokemonCenter ueber Proxy-IP 403 (Cloudflare-Proxy-Reputations-
Blocker, Sitemap/Storefront funktionieren); voller Nike-Draw-Entry braucht aktiven
Launch + echte Credentials; volle 1000er-Proxy-Vorpruefung (~40 min) nur in Background/
Chunks. Danach: weitere Discord-Themen laut KNOWLEDGE (Shopify Preload, Amazon-Invite-
Fenster 21-22U) je nach Bedarf.