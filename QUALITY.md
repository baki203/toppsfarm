# QUALITY.md - Qualitaets-Pruefliste je Modul

Mindeststandard fuer jedes Baki-AIO-Modul. Abgestimmt auf Erkenntnisse aus KNOWLEDGE.md
(Skyridge-Live-Config + PepperScripts-Doku). Wo Skyridge/Pepper schwaecher sind, wird hier
strenger: explizite Ja/Nein-Punkte + messbare Sperrquote statt "Best Effort".

## A. Grundpruefliste (gilt fuer ALLE Module, Ja/Nein)

| # | Punkt | Mindeststandard | Skyridge/Pepper-Bezug |
|---|-------|-----------------|------------------------|
| A1 | Eigene Catch-All-Domain je Mastermail | Statt Wegwerf-/tmp-Mail: eigene Domain mit Catch-All pro Mastermail, Weiterleitung in ein Konto. Generator und OTP/Link-Verifikation darueber. | Skyridge `Mastermails[].catchall`; Pepper: "Catchall will not pass for sure" bei Amazon -> eigene Domain noetig, Wegwerf geht nicht. |
| A2 | Ein persistentes Browserprofil je Konto | Je Konto eigenes Profil-Verzeichnis (var/browser-<site>/<account>), nie geteilt. | Skyridge `SessionStore` legt Session je Konto an. |
| A3 | Eine sticky Wohn-IP je Konto | Eine sticky Residential-IP (nicht rotierend) je Konto, fuer die Lebensdauer gehalten. | Skyridge `GeoCoder.position_1/2` = zwei feste Standorte; Pepper: ISP/DC + Proxy-Checker. |
| A4 | IP-Land und Region passend zur Adresse | IP-Geo (Land/Region) muss zur Profiladresse passen, sonst kein Taskstart. | Pepper Region-Switcher `Shopify <CC>`, COUNTRY je Task. |
| A5 | Adressvariation | Adresse je Konto eindeutig (Hausnummer/Zeile variieren), keine gleiche Adresse/CC ueber Konten. | Pepper `XXX`-Jig + Anti-Fraud-Warnung (gleiche CC+Adresse storniert Amazon). |
| A6 | Browsen vor der Registrierung | Vor Formular: 2-4 Unterseiten besuchen, scrollen, Mausbewegungen (core/human), Mindestverweilzeit. | Pepper Human-Modus nach Add-to-Cart. |
| A7 | Adresse erst in zweiter Session | Registrierung OHNE Adresse; Adresse/Zahlung erst in separater spaeterer Session anlegen. | Pepper Amazon `ADDRESS`-Modus getrennt vom Drop; Skyridge Modul je Feature. |
| A8 | Karte erst vor dem Kauf | Karte wird erst beim Checkout/Kauf gesetzt (Default-Zahlung), nie bei der Registrierung. | Pepper: Default-Zahlungsmethode, `ADDRESS`-Modus. |
| A9 | Erstkauf klein und zeitversetzt | Erster Kauf: geringer Wert, 12-72 h nach Kontoerstellung; danach steigern. | Pepper: aged accounts, "rest your account 3-5 mins"; Anti-Fraud "canning". |
| A10 | Telefon nur bei Aufforderung | Telefonnummer nur eintragen, wenn der Shop sie zwingend verlangt (SMS-OTP), sonst leer lassen. | Pepper `checkPhone`/`noPhoneOnly`; Amazon `validateAccountsWithPhoneNumberIfNeeded`. |

Erfuellungsgrad je Modul wird als Prozentsatz A1..A10 gemeldet.

## B. Messpunkte (Zaehler + Sperrquote, in jedem Modul)

Je Modul laufen diese Zaehler mit (fuer Browser- UND HTTP-Pfad):

- `attempts`   - gestartete Aktionen (Registrierungen, Logins, Checkouts, Entries).
- `banned`     - eindeutige Sperren (Sperrseite, "blocked", BPE, "your request could not be processed",
  Kontosperrung, IP-Block). Ein Zaehler je Sperr-Typ.
- `success`    - erfolgreich abgeschlossene Aktionen.
- `retries`    - Wiederholungsversuche nach Fehler (Soft-Ban-Retry: 3-5 min Pause).
- `quota`      - Sperrquote in Prozent: `banned / attempts * 100`, kumuliert UND je Modul-Lauf.

### Modulende-Ausgabe (Pflicht)
Nach jedem Lauf (Monitor-Stopp, Checkout-Ende, Generator-Ende, Toolbox-Test) wird ausgegeben:

```
[<modul>] Ende: <attempts> Versuche, <success> ok, <banned> gesperrt, <retries> retries
[<modul>] Sperrquote: <quota>%  (kumuliert: <quota_total>%)
```

- Werte in `var/quality.sqlite` persistieren (Tabelle `counters(modul, lauf, ts, attempts, success, banned, retries)`).
- Bei `quota > 25%` im Lauf: Warnung + Empfehlung (sticky IP pruefen, Adresse/CC neu, Pause 3-5 min).
- `--quality`-Flag fuer jede Modul-CLI: zeigt bisherige Zaehler + kumulierte Quote.

### Implementierung
- `modules/quality.py`: `Quality`-Klasse (increment, finish, store, report). Ein Instanz je Modul-Lauf,
  erreichbar in Monitor/Checkout/Generator ueber `self.q`.
- Sperr-Erkennung: `Quality.detect(text)` prueft URL/HTML gegen Musterliste:
  `cf-please-wait`, `access denied`, `blocked`, `business processing error`, `captcha`,
  `suspended`, `invalid credentials too many`, `Pardon Our Interruption`, `rate limit`.
- Banner-Erkennung: Zaehler je Muster-Typ (z. B. `banned:cloudflare`, `banned:akamai`).

## C. Modul-Mindestprofile (spezifisch)

### C1 Topps EU + C2 Shopify generisch (Shopify-Kern)
- A1..A10 alle erforderlich (Guest-Checkout meist ohne Konto; Konto nur bei Shops, die es verlangen).
- Queue-it-Erkennung beim Checkout (queued()), hCaptcha via CapSolver bei cf_clearance-Handoff.
- Checkout-Dryrun bis zum cart-Permalink/checkout-Link ohne Zahlung.

### C3 Nike Gen (Generator)
- A1-A6, A10. Kein A7/A8/A9 (reine Kontoerstellung). Karte NIE bei Erstellung.
- Messpunkte: attempts/banned/success je Registrierung; Sperrquote massgeblich fuer Generatorqualitaet.

### C4 Amazon Gen (Generator)
- A1-A6, A10 (Amazon: kein Catch-All-Wegwerf; OTP per E-Mail, SMS nur bei Trigger).
- A7/A8 entfallen fuer Generator; ADDRESS-Modus als separates Modulziel.
- Retry-Logik: bei Login-Loop 3-5 min Pause (weiches Rate-Limit), max 3 Retries.

### C5 Riftbound Gen (Generator, Raffle-Entries)
- A1-A6, A10. Zusaetzlich SessionStore-artiges Profil je Konto (A2).
- Messpunkte: je Raffle-Entry ein attempt; Entry-Fehler zaehlen als banned:form wenn Sperrseite,
  sonst attempts.

### C6 PlayStation DE (Queue-it, Sitemap)
- Monitor: Sitemap-Drops, de-de. Checkout: Queue-it-Warteschlange ueberstehen, dann Checkout-Link.
- A2 (Profil je Konto), A3, A4, A5, A8 (Karte erst beim Kauf), A9, A10. A1/A6/A7 sinngemaess.

### C7 MediaMarkt + C8 Saturn (gemeinsamer retail_core)
- Consent-Wall (Cookie-Banner) automatisch wegklicken, JSON-LD fuer Preise/Lager nutzen.
- Store- vs. Lieferverfuegbarkeit getrennt auswerten.
- Messpunkte: Monitor-Sperren (Cloudflare-403, Rate-Limit) als banned:http zaehlen;
  Checkout-Dryrun bis /checkout-Link.

### C9 Nike SNKRS (Akamai, Browser zwingend)
- Nike-Login (Konto, A2-Profil), Drop-Zeit von der Produktseite, Draw-Entry (LEO/DAN).
- Billing == Shipping (verhindert BPE).
- Messpunkte: banned:bpe (Business Processing Error) separat; Proxy-Checker-Vorbedingung
  (Entry- und Payment-Schritt testen) - `--check-proxies`.
- A2, A3, A4, A5, A8, A9, A10; A1 via Catch-All je Konto.

### C10 Smyths Toys (eigene Selektoren)
- Store- und Lieferverfuegbarkeit getrennt (eigene Auswertung), WAF-Erkennung
  ("Pardon Our Interruption") als banned:akamai zaehlen, Browser-Fallback fuer Checkout.

### C11 Toolbox
- Quality-Messpunkte fuer Proxy-Test (attempts je Proxy, banned:proxy bei Fehler),
  captcha_balance, test_webhook. Kein Konto-Kontext.

## D. Skyridge-Massstab: wo wir ueberbieten
- Skyridge/Pepper: Messung nur implizit (crashlog, "looping on login"). Wir: explizite Zaehler +
  Sperrquote + Persistenz in var/quality.sqlite + Warnschwelle 25%.
- Skyridge: Catch-All in config (Mastermails). Wir: Pflicht-Pruefpunkt A1 mit Wegwerf-Verbot.
- Skyridge: Adresse+Zahlung im selben Modul (`ADDRESS`). Wir: A7 trennt Registrierung strikt
  von Adresse/Session, A8 Karte erst beim Kauf.
- Pepper Nike: `disableVideos/Images` nur Option. Wir: A3 sticky IP + Proxy-Checker als Vorbedingung.