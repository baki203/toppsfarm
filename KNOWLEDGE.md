# KNOWLEDGE - Erkenntnisse aus Skyridge (Referenz) + PepperScripts (Vergleich)

Quellen:
- **Skyridge-Lokal**: `C:\Users\sargo\Desktop\SkyridgeSetup\SkyridgeSetup\` -> `settings.json` (Live-Config),
  `crashlog.log` (Tracebacks -> interner Python-Aufbau), `Skyridge-v0.41.3.5.exe` + `SkyridgeInbox.exe`.
- **Skyridge-GitBook** (https://skyridgescripts.gitbook.io/skyridgescripts): **BLOCKER** - Inhalt ist
  passwort-/auth-geschuetzt. Die GitBook-SPA liefert nur das JS-Shell (len 8595), Content-API antwortet 403
  (space `ol7xUOM4FIZAnDhDK8Sq`, org `irlSWpy2OmrOppsYP360`). Kein Wayback-Mirror. -> Erkenntnisse daher aus
  der lokalen Live-Config + Tracebacks + PepperScripts-Doku (selbes Werkzeug, freier Dokumentiert).
- **PepperScripts-Doku**: https://docs.pepperscripts.com (voll zugaenglich, `.md` pro Seite).

Grundsatz: nichts kopiert, nur abgelesen und als Anforderung/Qualitaetsmassstab uebernommen.

---

## 0. Architektur (aus crashlog.log, PyInstaller-Tracebacks)

Skyridge ist eine Python-App (PyInstaller onefile). Internes Layout unter `modules/`:
`modules/Generators/<Site>/modules/<Feature>/<Feature>Module.py` (Orchestrator, `runTask`),
`<Feature>Task.py` (Einzelkonto-Worker, `__init__`, `startRequest`, `_preCheck`, Retry in `runTask`),
`SessionStore.py` (legt Session-Verzeichnisse an). Logger unter `utilities/logger/CrashLogger.py`.

Beobachtete Module (aus Tracebacks): `Amazon/modules/Invite` (InviteModule.py, InviteTask.py),
`Riftbound/modules/RaffleEntry` (RaffleEntryModule.py, RaffleEntryTask.py, SessionStore.py).

Ablaufmuster je Modul: `Module.runTask` -> `Task.__init__` (bereitet Session vor, legt Ordner an) ->
`Task.startRequest` -> `_preCheck` (z. B. `balance`-Feld pruefen, KeyError wenn Zahlungsinfo fehlt) ->
eigentliche Aktion. `SessionStore` je Konto = eigenes persistentes Browserprofil je Session.

Modul-Header im Crashlog: `[Zeit] [Site | Feature]` (z. B. `[Amazon | Invites]`, `[Riftbound | RaffleEntry]`).

## 1. Settings-Schema (aus settings.json, Struktur abgelesen - Werte rot/gekennzeichnet)

Globale Schluessel (Root):
- `license-key`, `discord-webhook`, `deviceRotation` (bool), `remoteControl` (bool).

Provider-Blocks (nur Feldnamen, keine Keys ausgeben):
- `CaptchaProvider`: 2Captcha, CapMonster, CapSolver, AntiCaptcha, EzCaptcha, CaptchaFun, Resolvr, NoneCap.
- `SMSProvider`: 5sim, sms-man, juicy, sms-pool, sms-bower, daisy, herosms, grizzly, smspva, 1001sms,
  textverified. Je Anbieter: `Operator`, `max-price`, `min-price`, `provider-ids`, `fixed-price`,
  `virtual` (bool). 1001sms nutzt `provider` (z. B. "EXTRA").
- `GeoCoder`: mapbox-Token, `position_1`, `position_2` (Koordinatenpaare fuer zwei Standorte).
- `Mastermails` (Liste): je Eintrag `mastermail`, `password`, `catchall` (eigene Catch-All-Domain pro Mastermail).
- `OAuthForwarder`: target_email, smtp_server/port/username/password, tls/ssl, since_days, delete_after_forward,
  unread_only, monitor_mode, monitor_interval (s).
- `SkyridgeInbox`: enabled, userApiKey.
- `Ejoin` (SMS-Gateway): host, port, path, auth, sms_timeout, sim_cooldown, wait_for_free_sim, code_regex,
  auto_learn, sims.
- `AycdInbox`: enabled, apiKey.
- Modulbeispiel `Amazon`: `noPhoneOnly` (bool), `checkPhone` (bool), `noCaptchaOnly` (bool).

-> Unsere `config/settings.yaml` spiegelt diese Blockstruktur (CaptchaProvider, SMSProvider, Geocoder).

---

## 2. Amazon (PepperScripts-Doku, Vergleich zu Skyridge)

8+ Modi (CSV-Spalte MODE): leer (Drop/Restock), `ADDRESS` (addiert Default-Adresse+Zahlung),
`INVITATION` / `INVITATION CHECK` (Invite-only-Drop), `MONITOR` / `MONITOR DISCORD` / `AWAIT`
(Monitor->Await-Zweistufig, schont Proxies und Konten), `SESSION` (Session fuer bestehendes Konto),
`MANUAL`, `SECRET`, `ACCOUNT` (generiert Konto + fuehrt SECRET aus).

**Schrittfolge (wichtig fuer QUALITY.md):**
1. **Adresse**: Konto braucht Default-Lieferadresse + Default-Zahlung. Entweder schon gesetzt
   (leerer MODE) oder `ADDRESS`-Modus legt sie an. **Adresse erst in eigener zweiter Session/Modus**,
   nicht im ersten Drop.
2. **Karte**: Wird beim Checkout als Default-Zahlungsmittel genutzt; erst vor dem Kauf relevant.
   `ADDRESS` setzt Adresse + Karte einmalig.
3. **Retry**: `SECRET`-Modus empfohlen fuer Konto-Gesundheit; bei Login-Loop 3-5 Min Ruhe (weiches
   Rate-Limit). Angebots-ID (`OFFER`) = schnellster Checkout; leerer MODE aggressiver fuer Konten.

Anti-Fraud-Hinweise (direkt uebernehmen in QUALITY.md):
- NICHT dieselbe Kreditkarte oder dieselbe Adresse ueber mehrere Konten nutzen -> Auto-Anti-Fraud storniert.
- Geealterte Konten + eindeutige Adresse/Empfaenger; Bestellloeschung haeufig = "canning".
- OTP via E-Mail (Catch-All), SMS nur bei Trigger (`validateAccountsWithPhoneNumberIfNeeded`).
- Passwort: gross/klein/Zahl, min. 8 Zeichen.

**Verbindliche Nutzer-Korrektur (2026-11-20, Vorrang vor Chat-/Doku-Fakten):**
- Das in der Doku/Chat genannte "~500 Konten/Tag"-Limit ist **kein echtes Limit** - mit eigenem Bot
  sind deutlich mehr Konten pro Tag moeglich. Limit ggf. nur durch eigene Ressourcen/Domains gesetzt.
- **SMS-Provider sind fuer Amazon nicht noetig**: non-PVA-Registrierung funktioniert. OTP laeuft
  per E-Mail (Catch-All). Telefonnummer nur eintragen, wenn Amazon sie im Flow zwingend verlangt.
- Voraussetzung fuer Skalierung: **ausreichend eigene Catch-All-Domains** (mehrere, nicht eine einzige).

CSV-Felder: SITE, MODE, PID(ASIN), OFFER, QUANTITY, MAX QUANTITY, MAX PRICE, DELAY(ms), EMAIL, PASSWORD,
FIRST/LAST NAME, ADDRESS LINE 1/2, HOUSE NUMBER, CITY, ZIPCODE, STATE, COUNTRY(ISO2), PHONE, PAYMENT,
CARD HOLDER/NUMBER, EXP MONTH/YEAR, CVV, WEBHOOK, PROXY (Dateiname), IMAP, START TIME.

## 3. Nike SNKRS (PepperScripts, Vergleich)

Modi: leer (Drop), `FAST`, `SHOCK DROP`, `CHECKER` (Konto-Gesundheit: Telefon-validiert, Adress-Score),
`EA`, `MANUAL`, `SESSION`, `ADDRESS` (löscht+setzt Adressen+Zahlung), `VALIDATE` (SMS), `ACCOUNT`.
PID = Produkt-SKU (z. B. `HJ4303-400`). `ENTRY TIME` fuer Draw (LEO/DAN). Skus/drop-Zeit von der
Produktseite. **Browser zwingend** fuer Nike; reine Requests-Module (FCFS) separat.
Proxies: ISP/DC bevorzugt, Built-in Proxy-Checker testet spezifische entry+payment-Schritte. BPE
(Business Processing Error) vermeiden: Rechnungsadresse muss zur Zahlungsmethode passen (CC + PayPal).
Settings je Site: `disableVideos`, `disableImages`, `validateAccountsAfterCreation`, `smsProvider`,
`smsService`, `smsRegion`. Sizes: leer=zufaellig, FA/LA, Range `36-44`, Liste `42,43,41.8`.

## 4. Nike FCFS (PepperScripts, Vergleich)

Account-only. Auto-Login, Auto-Cart leeren, Monitor-Mirroring, Finalize-Checkout, Loop, Konto-CC-Wiederverwendung.
Zahlung: PayPal / Credit Card / Sofort (Sofort regionsabhaengig). 3DS-WHitelisting fuer Speed.
Konten sind weich gabanfaellig: echte/ saubere Infos = weniger BPE. **Billing == Shipping** nutzen.

## 5. Shopify (PepperScripts, Vergleich)

Guest-Checkout meist ohne Konto (manche Shops brauchen Konto). Requests-Modus, nach Add-to-Cart optional
Human-Modus. Speed: **Checkout vorgewärmt/preloaden**. Queue-Drops via Discord-Channel. Region-Switcher:
Profile im Format `Shopify <CC>` fuer laendersperrte Shops. Monitoring: Keyword-Gruppen mit `,` und
Negativ `-keyword`. Proxy-Liste `shopify.txt` fuer Monitoring (Rate-Limit). Password-Seite via CLI handeln.
Profil erforderlich + Catch-All. Sizes wie Nike.

## 6. Pokemon Center (keine Pepper/Skyridge-Doku -> eigene Analyse, STAND/Ordner)

Nicht in Referenzen dokumentiert. Eigene Produktliste, Queue-it, Konto noetig, de-de/en-gb, Lieferung DE.
-> Qualitaetsmassstab (QUALITY.md) gilt hier sinngemaess: eigene Catch-All, sticky IP je Konto,
Adressvariation, Karte erst vor Kauf, Erstkauf klein/zeitversetzt.

## 7. Modulablauf fuer unsere Module (abgeleitet)

- **Topps / Shopify generisch**: HTTP-first, Storefront-API Produktlisten, cart-Permalink, cf_clearance-Handoff
  (schon gebaut in `modules/shopify_core.py`).
- **PlayStation DE**: Queue-it, Produkte via Sitemap, de-de.
- **MediaMarkt / Saturn**: gemeinsamer Basis-Code, Consent-Wall + JSON-LD beachten.
- **Nike SNKRS**: Nike-Login, Drop-Zeit von Produktseite, Browser zwingend, Akamai.
- **Smyths Toys**: eigene Selektoren, Store- und Lieferverfuegbarkeit getrennt.

## 8. Fuer QUALITY.md uebernommene Massstaebe (aus Skyridge/Pepper)

- Eigene Catch-All-Domain pro Mastermail (Skyridge `Mastermails[].catchall`; Amazon: "Catchall will not pass").
- Persistentes Browserprofil je Konto (Skyridge `SessionStore`).
- Sticky Wohn-IP je Konto (Skyridge position_1/2 als zwei Standorte, GeoCoder).
- IP-Land/Region passend zur Adresse (Region-Switcher `Shopify <CC>`, COUNTRY je Task).
- Adressvariation (Pepper `XXX`-Jig; Anti-Fraud: eindeutige Adresse je Konto).
- Browsen vor Registrierung (Human-Modus nach Add-to-Cart).
- Adresse erst in zweiter Session (Amazon `ADDRESS`-Modus getrennt vom Drop).
- Karte erst vor dem Kauf (Default-Zahlung erst beim Checkout relevant).
- Erstkauf klein + zeitversetzt (aging; weiche Bans).
- Telefon nur bei Aufforderung (Amazon `checkPhone`/`noPhoneOnly`).