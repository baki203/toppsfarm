# Baki AIO

All-in-One-Tool fuer EU-Restock-Monitoring und Account-Generierung. Windows, Python 3.11+.
Start: `START.bat` oder `python baki.py` (Banner + Menue 1-14). Als fertige EXE: `dist\BakiAIO.exe`.

## Installation

```bat
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
```

## Start und Menue

Menueplatz | Modul | Art
---|---
1 | Topps EU | Shopify (Monitor + Checkout)
2 | Pokemon Center | eigener Monitor + Checkout
3 | Nike Account Generator | Generator
4 | Amazon Account Generator | Generator
5 | Riftbound Account Generator | Generator
6 | PlayStation DE | Nicht-Shopify (Sitemap + Queue-it)
7 | MediaMarkt | Nicht-Shopify (Sitemap + Checkout)
8 | Saturn | Nicht-Shopify (Sitemap + Checkout)
9 | Nike SNKRS | Nicht-Shopify (Browser, Akamai)
10 | Smyths Toys | Nicht-Shopify (Sitemap + Checkout)
11 | Shopify generisch | Shopify (config/shopify_sites.txt)
12 | Toolbox | Proxy/Captcha/Webhook-Tests
13-14 | frei | Platzhalter

Auswahl 0 beendet das Menue. Jedes Modul hat ein eigenes Untermenue.

## Architektur

Die Module liegen unter `modules/`:

- `shopify_core.py` - gemeinsame Shopify-Engine (Session, Storefront-/Sitemap-Quellen,
  hCaptcha via CapSolver, Queue-it-Erkennung, HTTP- und Browser-Checkout, Monitor,
  Orchestrator). Modulname ueber `MODULE` gesetzt. `topps.py` und `shopify.py` nutzen sie.
- `retail_core.py` - gemeinsame Basis fuer Nicht-Shopify-Shops (Monitor + Browser-Checkout).
  `psn.py`, `mediamarkt.py`, `saturn.py`, `snkrs.py`, `smyths.py` bauen darauf.
- `baki.py` verdrahtet die 14 Menueplaetze; Importe passieren erst bei Auswahl.

Je Modul gibt es eigene Unterordner `accounts\<modul>\` (Profile) und `proxies\<modul>\`
(Proxy-Listen). Proxy-Zeilenformat: immer `IP:PORT:USERNAME:PASSWORD` (eine Zeile je
Proxy, z. B. `1.2.3.4:8080:user:pass`). `http://user:pass@host:port`, `user:pass@host:port`
und `host:port` werden ebenfalls akzeptiert und automatisch normalisiert (siehe
`utilities/proxy.py`).

## Topps EU (Platz 1)

HTTP-first Monitor fuer die EU-Shops (de/es/fr/it.topps.com) mit Shopify-Backend.
Erkennen neuer Produkte via Sitemap und Storefront-API, Discord-Alerts ueber Webhook,
Checkout-Vorbereitung.

- Setup beim ersten Start: Menuepunkt "Setup" fuellt `config/keys.env`
  (Captcha-Provider/-Key, Discord-Webhook) und `accounts\topps\profiles.yaml`
  (Adressen/Karten; je Modul ein eigener Profil-Ordner).
- Selftest: prueft Profile und Host-Erreichbarkeit.
- Modi: `cart` (wenig Daten, Checkout-Link) / `browser` (Fallback mit Playwright).
- Karte per API = `--card-http`, experimentell.

### Cloudflare (de.topps.com)

`/products.json` ist beim Next.js-Shop serverseitig gesperrt (403, auch im Browser).
Zwei Ersatzwege sind eingebaut:

- Storefront-API (Shopify-GraphQL, Token steht oeffentlich im HTML): liefert Produkte + Varianten.
- `cf-refresh`: oeffnet einen sichtbaren Browser, wartet auf die `cf_clearance`-Challenge,
  speichert `cf_clearance` + `__cf_bm` nach `var/cf_cookies.json`. Danach bekommt die
  HTTP-Schicht (curl_cffi) Zugriff auf Homepage und Sitemap (200 statt 403).

### Checkout-Link (cart)

Fuer Next.js-Shops ohne `/cart/add.js` erzeugt `HttpCheckout` den Checkout-Link direkt
ueber die Storefront-cartCreate-API. Bei erfolgreicher Vorbereitung sendet der Orchestrator
eine CHECKOUT-Nachricht mit dem Link an den Discord-Webhook.

## Konfiguration

- `settings.json` (Projektwurzel) und `config/settings.yaml`: Defaults fuer Hosts, Abfrage-
  intervalle, Captcha, Queue und Notification. Beide sind gueltig; die YAML ist die Quelle
  fuer `Settings.load()`.
- `config/keys.env` - Schluessel (wird vom Setup-Wizard geschrieben, nicht in git).
- `accounts/<modul>/profiles.yaml` - Profile je Modul; versteht auch das
  Identitaets-Format (street + house_no). Fallback: `config/profiles.yaml`.
- `config/targets.yaml` - Monitoring-Ziele mit Match-/Task-Parametern.
- `config/shopify_sites.txt` - Domains fuer das generische Shopify-Modul (Platz 11),
  eine je Zeile. `config/proxy.txt` ist der globale Proxy-Fallback.

## Qualitaet und Sperrmessung (QUALITY.md)

Qualitaetspruefliste mit Ja/Nein-Punkten (Catch-All statt Wegwerf-Mail, persistentes
Browserprofil je Konto, sticky Wohn-IP je Konto, IP-Land/Region zur Adresse, Adressvariation,
Browsen vor Registrierung, Adresse erst in zweiter Session, Karte erst beim Kauf, Erstkauf
klein/zeitversetzt, Telefon nur bei Aufforderung) und den Quellen darunter (`KNOWLEDGE.md`).

Jedes Modul fuehrt Zaehler: `attempts`, `success`, `banned` (je Sperr-Typ), `retries` und meldet
am Ende Versuche, Erfolge, Sperren und die **Sperrquote in Prozent** (Warnung ab >25%). Die Werte
werden in `var/quality.sqlite` persistiert. Der kumulierte Stand je Modul per CLI:

```bat
.venv\Scripts\python.exe -m modules.topps quality
```

## Fehler und Logs

- Ein unbehandelter Traceback wird beim Start nach `crashlog.log` geschrieben (Hook in baki.py).
- Lauf-Logs liegen unter `var/logs/`, der Zustand (Produkte, Varianten, Tasks) in `var/state.sqlite`.

## Direktaufruf ohne Menue

`python toppsfarm.py selftest` und alle weiteren toppsfarm-Befehle
(`setup`, `profiles-check`, `stats`, `cf-refresh`, `watch`, `drop`, `install-browser`)
laufen unveraendert ueber die Weiterleitung `toppsfarm.py` -> `modules/topps.py`.

## Build (EXE)

```bat
.venv\Scripts\pyinstaller.exe --noconfirm --onefile --name BakiAIO --collect-all curl_cffi --collect-all playwright --collect-all pyfiglet baki.py
```

## Release

`release.zip` enthaelt `BakiAIO.exe`, `START.bat`, `README.md`, `settings.json`,
`config/` (settings.yaml, targets.yaml, proxy.txt), die Datenpool-Dateien unter `data/`
sowie die Ordner `accounts/`, `proxies/` und `Address Toolbox/` mit `.gitkeep`.