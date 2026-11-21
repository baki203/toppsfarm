# STAND
Stand 2026-11-21. Deutsch. Jeder Punkt: Test + STAND + Commit + Push.
## Stand Punkte
28f AMAZON REQUEST-GEN: umgesetzt. Gen nur curl_cffi REQUEST (impersonate=chrome), Playwright nur noch optional via --browser in amazon_browser_gen.py; baki.py --browser/--show/--threads/--tasks. amazon_signup.py neu mit DomainAllocator (GEN_PRIORITY ZA/EG/SA/IN/AE/TR..., lock, eine Domain je Task, var/amazon_domains.json, >80% Fehler nach 20 Versuchen ans Ende), ProxyRing (frischer Sticky-Proxy je Task), synth /ap/register (openid.return_to, assoc_handle=saflex, marketplaceId, Sprache), Log "Using synthesised register URL for <CC>", fill 5-12s/type 8-18s mit gemischter Feldreihenfolge, Klassen a-d, OTP per IMAP, ACIC/FunCaptcha max 2 Runden, unusual max 6 Retries, 202/403/503/404 -> mark_dead, 20 Misses -> Abbruch. CSV var/amazon_gen_attempts.csv mit ts,tid,domain,proxy(maskiert),email,dauer_fill,dauer_type,klasse,status,error (alte Zeilen migriert). Test: 5 Threads/10 Tasks, 10 Domains, Klassen a/b/c/d via Fixtures korrekt, Reallauf 10x d (register_gate_404/503), 0 Artefakte; 2-Task-Nachlauf mit gemischter POST-Feldreihenfolge ebenfalls d. compileall 0.
28c AMAZON HUMAN-FLOW PROBE: erledigt, Commit ea9500c. tools/amazon_probe.py Cookies zuerst, Maus/Jitter, frischer Browser/Proxy/Identitaet, Catchall-Rotation; Amazon blockte mit "unusual activity", kein Konto.
28b PROXY OHNE VORPRUEFUNG: erledigt. settings proxy.precheck=false, sticky_session, run_with_failover (mark_dead, max 2 Wechsel), ISP-Vorrang; Gen loggt maskierten Proxy + Quelle.
28 ISP-PROXY VORRANG: erledigt. proxies/amazon/isp.txt (gitignored) hat Vorrang; Setup kopiert Datei.
27 PROXY-VORPRUEFUNG 1000: erledigt. 449 ok / 551 tot -> Proxy-Reputation, kein Codefehler.
26 APP_ROOT/SETUP: erledigt. Einheitliche Pfade, Topps-Selftest direkt 4/4 (de/es/fr/it 200), Setup ohne Quellmuell.
26b6 BLOCKER AMAZON: alle Auth-/Register-Endpunkte liefern 404-Deko-Seite "Amazon Two-Step Verification"; auch mit Session-Tokens, echtem Chrome und Request-Mode nicht abspielbar.
## Offen
- Kein Amazon-Artefakt aus Reallauf: Antwortklassen logisch korrekt, aber Amazon serverseitig gated (404/503). Naechster Schritt nur mit sauberer Residential-IP oder erlaubtem Traffic-Mitschnitt.
- Topps-Selftest mit Proxy-Pool 403; direkt ohne Proxy 4/4. Proxy-Pool weiterhin unzuverlaessig.
