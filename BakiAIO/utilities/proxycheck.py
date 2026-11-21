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


async def precheck_proxies(pool, cfg, host: str | list[str] = DEFAULT_HOSTS,
                           conc: int = 20, progress=None) -> dict:
    """Testet pool.items einmal gegen die Ziel-Domain(s) und sperrt tote Proxys.
    conc Proxys werden gleichzeitig geprueft (Default 20).
    -> {'checked': n, 'alive': n, 'dead': n, 'dead_list': [...], 'hosts': [...]}."""
    hosts = [host] if isinstance(host, str) else list(host or DEFAULT_HOSTS)
    q = Quality(f"proxy:{pool.module}")
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    dead: list[str] = []
    alive: list[str] = []
    sem = asyncio.Semaphore(max(1, int(conc)))

    async def _one(proxy: str) -> bool:
        async with sem:
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
            if progress:
                progress(len(alive) + len(dead), len(pool.items), ok, proxy)
            return ok

    await asyncio.gather(*(_one(p) for p in list(pool.items)))
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


def _checked_today() -> set[str]:
    """Proxys, die heute schon in proxystats.csv stehen (Resume)."""
    done: set[str] = set()
    if not STATS_FILE.exists():
        return done
    today = time.strftime("%Y-%m-%d")
    try:
        with STATS_FILE.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if str(row.get("ts", "")).startswith(today) and row.get("proxy"):
                    done.add(row["proxy"])
    except Exception:
        pass
    return done


def main(argv: list[str] | None = None) -> int:
    """Chunked Vorpruefung: python -m utilities.proxycheck --limit 250 --offset 0
    Mit --resume werden heute schon gepruefte Proxys uebersprungen."""
    import argparse
    ap = argparse.ArgumentParser(description="Proxy-Vorpruefung (chunked)")
    ap.add_argument("--module", default="topps")
    ap.add_argument("--hosts", default=",".join(DEFAULT_HOSTS))
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0, help="0 = alle")
    ap.add_argument("--conc", type=int, default=20)
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args(argv)

    from modules.Engine.Shopify.shopify_core import ProxyPool, Settings, State
    hosts = [h.strip() for h in a.hosts.split(",") if h.strip()]
    cfg = Settings.load()
    state = State(str(cfg.path(cfg.state_db)))
    pool = ProxyPool(state, a.module)
    items = list(pool.items)
    if a.resume:
        done = _checked_today()
        items = [p for p in items if p not in done]
    items = items[a.offset:]
    if a.limit:
        items = items[:a.limit]
    if not items:
        print(f"[proxycheck] keine Proxys zu pruefen (module={a.module}).")
        return 0
    pool.items = items
    print(f"[proxycheck] {len(items)} Proxys, {len(hosts)} Hosts, conc={a.conc}")

    def _progress(n: int, total: int, ok: bool, proxy: str):
        if n % 25 == 0 or n == total:
            print(f"[proxycheck] {n}/{total} ({proxy} {'ok' if ok else 'tot'})",
                  flush=True)

    r = asyncio.run(precheck_proxies(pool, cfg, hosts, conc=a.conc,
                                     progress=_progress))
    print(f"[proxycheck] fertig: {r['checked']} geprueft, {r['alive']} ok, "
          f"{r['dead']} tot -> var/proxystats.csv")
    return 0


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


if __name__ == "__main__":
    import sys
    sys.exit(main())
