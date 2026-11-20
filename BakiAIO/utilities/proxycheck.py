"""proxycheck - Proxy-Vorpruefung vor jedem Modullauf (Punkt 4).
Jeder Proxy wird einmal gegen die Ziel-Domain getestet; Ergebnis wird in
var/proxystats.csv dokumentiert und tote Proxys fuer den Lauf gesperrt."""
from __future__ import annotations

import asyncio
import csv
import time
from pathlib import Path

from utilities.proxy import is_proxy_auth_error
from utilities.quality import Quality

from utilities.root import APP_ROOT as ROOT
STATS_FILE = ROOT / "var" / "proxystats.csv"

DEFAULT_HOSTS = ["amazon.de", "nike.com", "pokemoncenter.com",
                 "playstation.com", "de.topps.com"]


async def precheck_proxies(pool, cfg, host: str | list[str] = DEFAULT_HOSTS) -> dict:
    """Testet pool.items einmal gegen die Ziel-Domain(s) und sperrt tote Proxys.
    -> {'checked': n, 'alive': n, 'dead': n, 'dead_list': [...], 'hosts': [...]}."""
    from curl_cffi.requests import AsyncSession
    hosts = [host] if isinstance(host, str) else list(host or DEFAULT_HOSTS)
    q = Quality(f"proxy:{pool.module}")
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    dead: list[str] = []
    alive: list[str] = []
    for proxy in list(pool.items):
        q.increment("attempts")
        checks = await asyncio.gather(*(_check(cfg, h, proxy) for h in hosts))
        ok = all(checks)
        if ok:
            alive.append(proxy)
            q.success()
        else:
            dead.append(proxy)
            pool.mark_dead(proxy)
            q.banned("proxy")
    _write_stats(cfg, hosts, alive, dead)
    q.finish()
    return {"checked": len(pool.items), "alive": len(alive), "dead": len(dead),
            "dead_list": dead, "hosts": hosts}


async def _check(cfg, host: str, proxy: str) -> bool:
    from curl_cffi.requests import AsyncSession
    kw = {"impersonate": cfg.impersonate, "timeout": int(cfg.proxy.get("check_timeout_s", 15))}
    if proxy:
        kw["proxy"] = proxy
    try:
        async with AsyncSession(**kw) as s:
            r = await s.get(f"https://{host}/", timeout=int(cfg.proxy.get("check_timeout_s", 15)))
            if r.status_code == 407 or is_proxy_auth_error(str(r.status_code)):
                return False  # Proxy-Auth-Fehler -> tot, nie als Ban
            return 200 <= r.status_code < 500
    except Exception as exc:
        if is_proxy_auth_error(str(exc)):
            return False  # Proxy-Auth-Fehler -> tot
        return False


def _write_stats(cfg, hosts: list[str], alive: list, dead: list):
    try:
        fresh = not STATS_FILE.exists()
        with STATS_FILE.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if fresh:
                w.writerow(["ts", "host", "proxy", "status"])
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            host = ",".join(hosts)
            for p in alive:
                w.writerow([ts, host, p, "ok"])
            for p in dead:
                w.writerow([ts, host, p, "dead"])
    except Exception:
        pass
