# STAND
Stand 2026-11-21. Deutsch. Jeder Punkt: Test + STAND + Commit + Push.
## Stand Punkte
28g AKTIV: amazon_signup.py REQUEST-only, OneShotProxyPool mit var/amazon_used_proxies.txt (Lock, append+flush+fsync, Vorpruefung, kein Reuse, "proxy #<index> reserviert, <n> frei", "Pool erschoepft"), DomainAllocator mit attempts/clean/otp/success/captcha + Tier-Sortierung SA/ZA/EG/IN/AE/TR > NL/BE/IT/PL/SE/IE > DE, 2-4s Domain-Gap, noCaptchaOnly-Default mit "Captcha challenge required — aborting (noCaptchaOnly)" + captcha_abort, Solver nur bei noCaptchaOnly=false, Tageszaehler, 60-Miss-Abbruch, CSV ohne error, Worker-Pool 1-30.
28g MOCK-TESTS OK: compileall 0; Klassenfixtures a/b/c/d OK; Proxy 10 Tasks/5 Threads = 10 Indizes, 0 Duplikate; Erschoepfung mit 3 Proxies = 3 Tasks + "Pool erschoepft"; 30 Tasks/5 Threads = 30 Tasks, 8 success, 8 captcha_abort, 19 Domains, max_active 5, gemischte Feldreihenfolgen; Solver-Gate 1 Aufruf nur bei noCaptchaOnly=false; Stats-/Tageszaehler-/CSV-Schema geprueft.
28g REALLUF OK: 30 Tasks/5 Threads, 21 Domains, 30× Klasse d register_gate, 0 captcha, 0 Artefakte, Quote 0.0%; Proxy-Datei 30 Zeilen, 30 unique, 0 Duplikate; CSV-Header exakt 9 Spalten; Topps-Selftest 4/4 (de/es/fr/it 200).
28g BROWSER-PFAD: baki.py --browser/--show und AmazonAIOModule.browser/show/run_burst(browser=...) entfernt; amazon_browser_gen.py bleibt ungenutzt (nicht geloescht). amazon_core.py GEN_TIERS/GEN_PRIORITY auf neue Reihenfolge angeglichen.
28f AMAZON REQUEST-GEN: erledigt, Commit eb6a733. Alte Proxy-, URL-, Klassen- und OTP-Logik teils durch 28g ersetzt.
28c AMAZON HUMAN-FLOW PROBE: erledigt, Commit ea9500c. Amazon blockte mit "unusual activity", kein Konto.
28b/27 PROXY: erledigt. proxy.precheck=false, sticky_session, ISP-Vorrang; Vorpruefung 1000 = 449 ok / 551 tot.
26 APP_ROOT/SETUP: erledigt. Einheitliche Pfade, Topps-Selftest direkt 4/4 (de/es/fr/it 200).
26b6 BLOCKER AMAZON: Auth-/Register-Endpunkte liefern 404-Deko-Seite "Amazon Two-Step Verification"; echter Erfolg im Reallauf offen (Mock beweist success-Pfad).
## Offen
- Reale Amazon-Register-URLs weiterhin gated (404/503); nur mit sauberer Residential-IP oder erlaubtem Traffic-Mitschnitt weiter.
- Topps-Selftest mit Proxy-Pool 403; direkt ohne Proxy 4/4.
- Commit + Push 28g: erfolgt mit diesem Stand.
