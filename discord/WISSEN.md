# WISSEN - Discord-Export (konsolidiert, 2026-11-20)

Quelle: 10 Export-Dateien, Vorfilter 10.368 Nachrichten -> 14 Stuecke, voller Lauf $0.10.
Regel: "behauptet" = Einzelmeinung oder nicht gegengeprueft; Fakt erst nach Gegenprobe.

## Amazon - Captcha
- 2Captcha ist fuer Amazon-Gen/Request-Modus Standard; andere Provider nur als Fallback (x7).
- WAF-Captcha ist Amazon-inhouse und NICHT ueber 2Captcha loesbar; eigener Typ (x4).
- Fehlercodes: ARKOSE_LEVEL_1/4/5 ("Captcha verification failed"), "Captcha failed, retrying",
  Captcha-Loop nach green tick (x4). (behauptet)
- 2Captcha-Ausfallwellen: 4000 Accounts angefordert, 0 generiert, alle "captcha failed" (x3).
- noCaptchaOnly=true bricht Tasks mit "Captcha challenge required" ab, schont Credits (x3);
  korreliert mit Non-PVA (x6). (behauptet)
- Free-Captcha-Wellen ~10-25, danach "blocked captcha"/"PVA required" (x6). (behauptet)
- Quoten-Erfahrungswerte: 1/200, 3/100 ohne Captcha (x2). (behauptet)
- Captcha 403 = je nach Modul/Phase Provider-Fehler ODER Proxy-Fehler (x6). (behauptet)
- Login-Captcha wird durch Proxy/Region ausgeloest, nicht durch Account-Alter (x1). (behauptet)

## Amazon - Proxy
- Proxy-Land muss zum Country-ISO/phone-ISO passen, sonst keine Invites (x6).
- Empfehlung: ~1 Konto pro Proxy, frische Liste pro Gen-Session, gleicher Proxy beim Checkout (x4).
- Provider-Pools werden geteilt und von Amazon geflaggt; Clip-Rate pro Provider vergleichen (x3).
- Provider genannt: byte, oxylabs, icey, mars, webshare, proxybaron, emivo, boilingbot (x8).
- Proxy-Wechsel nach Gen/bei alten Konten = hohe Clip-Wahrscheinlichkeit (x5). (behauptet)
- Session-Manager/Farmer/Checker nutzen den ZULETZT genutzten Task-Proxy, nicht die CSV (x6). (behauptet)
- Auth-Fehler: "proxies need authenticating", 407 "Proxy Authentication Required" = leeres
  Guthaben, "proxy authentication 302", "proxy auth failed = proxy data empty" (x5).
- Fehler "Banned proxy getSignUpPage (fetch base data), rotating -> 403" (x6).
- "Couldn't submit data - change your proxies" = proxy-bedingt (x14).
- IP-Risiko-Check: scamalytics.com, gleiche IP bei mehreren Providern (x1). (behauptet)

## Amazon - SMS/Telefon
- NUTZER-KORREKTUR: SMS-Provider fuer Amazon NICHT noetig; non-PVA funktioniert. Telefon nur
  bei zwingender Aufforderung im Flow. (Fakt, Vorrang)
- "Error waiting for SMS code" trotz 4 Providern -> Fix noPhoneOnly=true (x2).
- Provider im Export: 5sim gut, smspool/smsman schlecht, herosms+grizzly ok (x6).
- SMS-Land muss zum Proxy-Land passen (x5). (behauptet)
- OTP-Fehler: "Email code not found"/"Email not found - Timeout" trotz eingehender Mails (x9).
- "too many OTP" sendet Nummer nicht an Amazon (kein Kostenverlust), Proxy-/SIM-bedingt (x2).

## Amazon - E-Mail/Domain
- Catch-All-Domains funktionieren, Aliases NICHT (600+ Aliases ohne OTP) (x4).
- NUTZER-KORREKTUR: Voraussetzung fuer Skalierung = genuegend EIGENE Catch-All-Domains (Fakt).
- Domain-Klima: ~1000 Accounts/Domain vor Clip-Gefahr, neue Domain je ~1k, Ruhe nach Flag ~5 Tage
  (x4). (behauptet)
- Custom-Domain wird teils gekappt; .porn/.xyz-Domains schlecht (x4). (behauptet)
- Mastermail: Gmail-App-Passwort in settings.json, IMAP+OAuth, Outlook-Weiterleitung rate-limited
  (x5). (behauptet)
- OTP via Non-JIG-Mail (Mastermail) statt Catchall bei manchen Flows (x1). (behauptet)

## Amazon - Limits/Konten
- NUTZER-KORREKTUR: "500/Tag"-Limit ist KEIN echtes Limit; mit eigenem Bot mehr moeglich (Fakt).
- Export nennt ~500/Tag, ~1000/Tag, 3 PVA-frei pro 100 (x3) - alles (behauptet), siehe Korrektur.
- Thread-Default 5, 20 Threads nur ~5% RAM (x3). (behauptet)
- Gen-Renditen (behauptet): 200 Outlooks->21 Accounts, 730 Gmails->73, 40 in 14 min, 120/Tag fehlerfrei (x5).
- Ban-Ursachen laut Thread: ausschliesslich SIM/Proxy, nicht E-Mail-Domain (x8). (behauptet)

## Amazon - Invites/Order-History/Drops
- Invites bevorzugt an Accounts mit Bestellhistorie; neue Order-History-/Trust-Score-Pflicht (x5). (behauptet)
- Drop-Fenster: ueberwiegend 21-22 Uhr, Invites laufen ~15 min; "Monday Night/Friday Morning" (x3). (behauptet)
- Invite-Tokens nur im HTML der komplett gerenderten Produktseite (x1). (behauptet)
- Invite-Status-Flow: "Loading product page" -> "Checking invite status" -> "AOD returned unknown
  state" -> location retry (x1). (behauptet)
- Account-Status: pva_locked, session_dead, "session expired", clipped, "Ghost account detected -
  no auth cookies after registration - swap phone/proxy provider" (x6).
- "Invite not available for this product (confirmed after location retry)" (x3).
- Order-History-Module fuer GB/FR/DE, ES/Japan angefragt (x1). (behauptet)

## Amazon - Endpunkte
- Signin: /ap/signin?openid.pape.max_auth_age=0&openid.return_to=...&openid.assoc_handle=saflex|flex
  Fehler: "unexpected EOF", 503 "Signin page error, rotating session" (x4).
- Add-Address: /checkout/p/{ASIN}/add-new-shipping-address?pipelineType=Chewbacca&referrer=address
  &isInline=1&isAsync=1 (amazon.fr) (x1). (behauptet)
- Location-POST: "empty/invalid body - aborting location change (session-level failure)" (x3).
- Marketplace-Declaration: MYCD-preferences-Endpoint; Fehler "could not declare account into DE -
  interactive marketplace migration" (x1). (behauptet)
- Checkout-Fehler: "FAIL CHECKOUT_FAILED: item selection transition failed", "payment registration
  failed" (x1). (behauptet)
- HTTP 402 "Payment Required" trotz funktionierender Proxies in Dritt-Checkern (x2). (behauptet)

## Amazon - Sonstiges
- settings-Block: "noPhoneOnly", "noCaptchaOnly", "checkPhone" (bool) (x2).
- Changelog-Historie: Amazon-Gen seit v0.26.0 (Apr 2025), request-basiert seit v0.30.0 (x14).
- Akamai als Amazon-Security-Backend genannt; Akamai-403 nur im Verification-Step (x3).
- CSV: Proxy aus gen-/task-CSV vorrangig, txt-Liste Rotations-Fallback; Proxy-Spalte leeren fuer
  frischen Neulauf (x4).

## Nike/SNKRS
- Anti-Bot: Kasada UND Akamai; Kasada-Update vor hype-Drops erwartet (x2).
- Kasada-Fehler: "kasada error", Logformat `Unknown statuscode -> (400) | Kasada block -> (429)`,
  "Kasada-ERROR CD, trying to fix the session" (x6). (behauptet)
- Akamai: `akamai block -> 403`, Cookie-Loop nach "passed Nike challenge" (x4). (behauptet)
- Antwortcodes: HTTP 200 bei Registrierung = "already registered", 300/400 = nicht registriert (x1). (behauptet)
- Request-Budget: 4-6 Requests/Acount, Reverifier 1, Tageslimit /500 mit Reset (x1). (behauptet)
- Browser zwingend fuer Nike; reine Request-Module (FCFS) separat (Doku, Fakt).
- Captcha-Handling: anfangs 2Captcha, Provider 1stCaptcha/EzCaptcha/AntiCaptcha/CapSolver/CaptchaAI
  in settings.json konfigurierbar (x2). (behauptet)
- Account-Scraper beim Clip-Check: Name, Geburtsdatum, Registrierungsdatum/-Client, SMS, Telefon ->
  scraped_NikeAccounts.csv (x1). (behauptet)
- HYBRID-Modus und Farmer-Modul eingefuehrt; "eigenes Guide mit Pros/Cons verpflichtend" (x2).
- KAS-Loesung (März 2023) nicht integriert, "Nutzung auf eigenes Risiko" (x1). (behauptet)
- Kontinuierliche Adaption an BP-Änderungen (fast jeder Changelog, x13+). (Fakt, Verlauf)

## PokemonCenter (PKC)
- PKC Newsletter-Signup-Modul (v0.31.0); Queue-Bypass + Discord-Invite-Scanner-Queue (1h Slowmode)
  als Engpass genannt (x2). (behauptet)
- In-house-Captcha-Loesung aktiv, Provider nur Fallback; Datadome+Incap komplett inhouse (x2).
- PKC-Arbeit blockierte 2026 andere Releases (x1). (behauptet)

## Riftbound/TM/Andere
- Riftbound: EzCaptcha + NoneCaptcha; Harvester bleibt, nicht voll auf Provider setzen (x1). (behauptet)
- TM: ReCapV3-Harvester (Incap/Nutdata), CaptchaFun nur wenn andere Provider versagen (x3).
- Capmonster empfohlen wenn Bestaetigungs-Mails fehlen; 2captcha ging nicht, Capsolver ging (x1). (behauptet)
- EZCaptcha empfohlen, weil bessere Solve-Rates; 403 verbraucht Provider-Guthaben (x2). (behauptet)
- FreeNet: Cloudflare-Adaption (v0.35.6, v0.40.1) (x2).
- Proxy-Qualitaet spielt laut einem Test mit Webshare kaum eine Rolle (x1). (behauptet)

## Luecken im Export
- KEINE belegbaren Angaben (Endpunkte/Selektoren/Queues) fuer: Topps, PokemonCenter (tech.),
  MediaMarkt, Saturn, Smyths, Shopify (nur vereinzelte Erwaehnungen) (x2).
- Topps-EQL-Modul existiert in Skyridge nicht (seit >=17 Tagen angefragt) (x1). (behauptet)
