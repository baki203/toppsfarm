"""proxycheck - Proxy-Vorpruefung vor jedem Modullauf (Punkt 4).
Jeder Proxy wird einmal gegen die Ziel-Domain getestet; Ergebnis wird in
var/proxystats.csv dokumentiert und tote Proxys fuer den Lauf gesperrt."""
from __future__ import annotations

import csv
import time
from pathlib import Path

from modules.quality import Quality

ROOT = Path(__file__).resolve().parent.parent
STATS_FILE = ROOT / "var" / "proxystats.csv"


async def precheck_proxies(pool, cfg, host: str) -> dict:
    """Testet pool.items einmal gegen https://<host>/ und sperrt tote Proxys.
    -> {'checked': n, 'alive': n, 'dead': n, 'dead_list': [...]}."""
    from curl_cffi.requests import AsyncSession
    q = Quality(f"proxy:{pool.module}")
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    dead: list[str] = []
    alive: list[str] = []
    for proxy in list(pool.items):
        q.increment("attempts")
        ok = await _check(cfg, host, proxy)
        if ok:
            alive.append(proxy)
            q.success()
        else:
            dead.append(proxy)
            pool.mark_dead(proxy)
            q.banned("proxy")
    _write_stats(cfg, host, alive, dead)
    q.finish()
    return {"checked": len(pool.items), "alive": len(alive), "dead": len(dead),
            "dead_list": dead}


async def _check(cfg, host: str, proxy: str) -> bool:
    from curl_cffi.requests import AsyncSession
    kw = {"impersonate": cfg.impersonate, "timeout": int(cfg.proxy.get("check_timeout_s", 15))}
    if proxy:
        kw["proxy"] = proxy
    try:
        async with AsyncSession(**kw) as s:
            r = await s.get(f"https://{host}/", timeout=int(cfg.proxy.get("check_timeout_s", 15)))
            return 200 <= r.status_code < 500
    except Exception:
        return False


def _write_stats(cfg, host: str, alive: list, dead: list):
    try:
        fresh = not STATS_FILE.exists()
        with STATS_FILE.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if fresh:
                w.writerow(["ts", "host", "proxy", "status"])
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            for p in alive:
                w.writerow([ts, host, p, "ok"])
            for p in dead:
                w.writerow([ts, host, p, "dead"])
    except Exception:
        pass