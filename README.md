# Baki AIO

All-in-One-Tool fuer EU-Restock-Monitoring und Account-Generierung. Windows, Python 3.11+.
Start: `START.bat` oder `python baki.py` (Banner + Menue 1-14). Als fertige EXE: `dist\BakiAIO.exe`.

## Installation

```bat
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
```

## Start und Menue

Menueplatz | Modul
---|---
1 | Topps EU (Monitor + Checkout)
2 | Nike Account Generator
3 | Amazon Account Generator
4 | Riftbound Account Generator
5 | Pokemon Center (Monitor + Checkout)
6 | Toolbox (Proxy/Captcha/Webhook-Tests)
7-14 | frei (Platzhalter)

Auswahl 0 beendet das Menue. Jedes Modul hat ein eigenes Untermenue.

## Topps EU (Platz 1)

HTTP-first Monitor fuer die EU-Shops (de/es/fr/it.topps.com) mit Shopify-Backend.
Erkennen neuer Produkte via Sitemap und Storefront-API, Discord-Alerts ueber Webhook,
Checkout-Vorbereitung.

- Setup beim ersten Start: Menuepunkt "Setup" fuellt `config/keys.env`
  (Captcha-Provider/-Key, Discord-Webhook) und `config/profiles.yaml` (Adressen/Karten).
- Selftest: prüft Profile und Host-Erreichbarkeit.
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
- `config/profiles.yaml` - Profile; versteht auch das Identitaets-Format (street + house_no).
- `config/targets.yaml` - Monitoring-Ziele mit Match-/Task-Parametern.
- `config/proxy.txt` - Proxy-Liste (eine je Zeile).

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