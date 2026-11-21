# STAND
Stand 2026-11-21. Deutsch. Jeder Punkt: Test + STAND + Commit + Push.
## Stand Punkte
28h AKTIV: amazon_signup.py nutzt browserfreien Seed-Flow `seed -> claim -> register` mit beobachteten OpenID-Parametern (pageId/assoc_handle `<cc>flex`, korrigiertes ns.pape, return_to mit ref_=nav_ya_signin, policy_handle Retail-Checkout) statt Home/Signin; GET seed umgeht WAF-202 und landet auf echtem Register-Formular.
28h HELFER: `unescape`, `urljoin`, `_attr`, `_forms`, `_form_fields`, `_find_form`, `_find_href`, `_proxy_http`, `_registration_request`, `_submit_registration` eingebaut;.Formular-Action und Hidden-Felder aus HTML statt fixer POST-URL.
28h KLASSIFIKATION: HTML-Kommentare werden vor CAPTCHA-Check entfernt; generischer Kommentar `Captcha From Rendered using Kata` erzeugt nicht mehr falsch `captcha_abort`; echter `/ap/cvf/request`-Challenge wird erkannt.
28h FORMULAR: Submit sendet Hidden-Felder + `customerName`, `email`, `password`, `passwordCheck`, `metadata1=true`; alle Reposts (Solver/Retry/OTP) gehen an die aus dem Formular gelesene `submit_url`.
28h MOCK-TESTS OK: compileall 0; `_amazon_28g_mock.py` = `PROXY_ONCE 10 10 OK`, `POOL_EXHAUST 3 Pool erschoepft OK`, `BURST30 30 created 8 captcha 8 domains 19 max_active 5 field_orders 13 OK`, `SOLVER_GATE 1 OK`.
28h REALLUF: 1 Task/1 Thread erreichte `seed -> claim -> register`, dann vor Korrektur `captcha_abort`; 10 Tasks/3 Threads = 0 success, 3 captcha_abort, 5 failed, 2 proxy_http_503; 15 Tasks/5 Threads = 0 success, 5 captcha_abort, 8 failed, 2 proxy_http_503.
28h INSPEKTION: Direkt-Läufe NL/SA/ZA/EG/AE/TR/IT erreichen alle HTTP 200 `Create account`; Step0 meldet `Wrong or Invalid e-mail address`, danach `unusual activity` oder JS-Pflicht-Captcha `/ap/cvf/request`; kein Konto erzeugt.
28h BLOCKER: Ohne JavaScript fehlt die von Amazon erwartete `metadata1`-Browser-Signatur; Registrierung endet in `unusual activity` oder echtem ACIC-Captcha. noCaptchaOnly bleibt true; Solver wird nicht bezahlt/eingesetzt.
28g REALLUF ALT: 30 Tasks/5 Threads, 21 Domains, 30× Klasse d register_gate, 0 Artefakte; Proxy-Datei 30 unique, CSV 9 Spalten; Topps-Selftest 4/4 (de/es/fr/it 200).
28g FUNKTION: OneShotProxyPool mit Used-File (Lock, append+flush+fsync, kein Reuse, `proxy #<index> reserviert, <n> frei`, `Pool erschoepft`), Domain-Tiers SA/ZA/EG/IN/AE/TR > NL/BE/IT/PL/SE/IE > DE, 2-4s Domain-Gap, Tageszaehler, 60-Miss-Abbruch, CSV ohne error, Worker 1-30.
28g BROWSER-PFAD: `baki.py --browser/--show` und `AmazonAIOModule.browser/show/run_burst(browser=...)` entfernt; `amazon_browser_gen.py` bleibt ungenutzt; `amazon_core.py` GEN_TIERS angepasst.
28f/28c/28b: erledigt, Commit eb6a733 / ea9500c; Proxy-Vorpruefung 1000 = 449 ok / 551 tot; Browser-Probe 28c endete mit `unusual activity`.
26 APP_ROOT/SETUP: erledigt; Topps-Selftest direkt 4/4 (de/es/fr/it 200).
## Offen
- Reale Amazon-Registrierung ohne Browser/Solver weiter offen; naechster Schritt nur mit erlaubtem JS-faehigen Pfad oder sauberer Residential-IP mit gueltiger Browser-Signatur.
- Topps-Selftest mit Proxy-Pool 403; direkt ohne Proxy 4/4.
- Commit + Push 28h: erfolgt mit diesem Stand.
