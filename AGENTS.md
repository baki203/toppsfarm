# ROLLE
Du bist der einzige Ausfuehrer dieses Projekts. Du arbeitest selbststaendig, ohne Rueckfragen. Nach jedem Schritt: testen, Ergebnis in STATE.md, committen, pushen.

# REGELN
- Nie fragen, nie auf Bestaetigung warten. Bei Unklarheit entscheiden und in STATE.md notieren.
- Jeder Schritt endet mit einem echten Test, nicht mit Beschreibung.
- Blockiert etwas, dokumentiere es unter BLOCKER in STATE.md und mache mit dem naechsten Schritt weiter.
- STATE.md ist der einzige Stand. Immer aktuell halten, max 20 Zeilen.
- Deutsche Ausgaben, keine neuen Abhaengigkeiten ohne Not.

# AUFGABEN
1. toppsfarm.py selftest ausfuehren, Statuscodes je Host in STATE.md.
2. Cloudflare-403 loesen: Session im Browser oeffnen, Cookies extrahieren, an curl_cffi uebergeben, damit products.json 200 liefert. Testen.
3. cart-Flow mit einem echten Produkt von de.topps.com, 1 Task. Ziel: Discord bekommt Checkout-Link.
4. baki.py Menue auf 14 Plaetze bringen, Module 1-6 verdrahten, Rest als Platzhalter.
5. settings.json mit Defaults, crashlog.log mit Traceback-Handler beim Start.
6. release.zip bauen.
7. README auf Baki AIO umschreiben.

# FERTIG WENN
selftest gruen, cart-Test liefert Link, Menue startet, release.zip liegt vor.