from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path

from utilities.root import APP_ROOT

PATH = APP_ROOT / "var" / "amazon_rotation.json"
DAY = 86400.0


def _load() -> dict:
    try:
        d = json.loads(PATH.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            d.setdefault("rr", 0)
            d.setdefault("used", [])
            d.setdefault("domains", {})
            return d
    except Exception:
        pass
    return {"rr": 0, "used": [], "domains": {}}


def _save(d: dict) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(PATH))


def _domain(addr: str) -> str:
    addr = str(addr or "").strip().lower()
    if "@" in addr:
        return addr.rsplit("@", 1)[-1]
    return addr if "." in addr else ""


def _recent(d: dict, days: int = 7) -> set[str]:
    cutoff = time.time() - days * DAY
    out = set()
    for x in d.get("used") or []:
        try:
            if float(x.get("ts", 0)) >= cutoff:
                out.add(str(x.get("addr", "")).lower())
        except Exception:
            continue
    return out


def last_domain(d: dict, known: set[str]) -> str:
    for x in reversed(d.get("used") or []):
        dom = _domain(str(x.get("addr", "")))
        if dom in known:
            return dom
    return ""


def pick(entries: list[dict], local: str = "", last: str | None = None) -> dict:
    d = _load()
    now = time.time()
    domains = sorted({_domain(str(e.get("catchall", ""))) for e in entries if _domain(str(e.get("catchall", "")))})
    if not domains:
        raise RuntimeError("rotation: keine Catch-All-Domains")
    previous = last if last is not None else last_domain(d, set(domains))
    used = _recent(d)
    counts = d.setdefault("domains", {})
    for dom in domains:
        counts.setdefault(dom, 0)

    def key(dom: str):
        return (int(counts.get(dom, 0)), dom == previous)

    available = [dom for dom in domains if dom != previous or len(domains) == 1]
    dom = min(available, key=key)
    cands = [e for e in entries if _domain(str(e.get("catchall", ""))) == dom]
    if not cands:
        raise RuntimeError("rotation: kein Eintrag fuer Domain " + dom)
    rr = int(d.get("rr", 0))
    if rr <= 0:
        rr = random.randrange(max(1, len(cands)))
    ordered = cands[rr % len(cands):] + cands[:rr % len(cands)]
    entry = None
    for e in ordered:
        raw = str(e.get("catchall", "")).strip().lower()
        candidate = f"{local}@{dom}" if local else (raw if "@" in raw else f"catchall@{dom}")
        if raw not in used and candidate not in used:
            entry = e
            break
    if entry is None:
        entry = ordered[0]
    d["rr"] = rr + 1
    d["domains"][dom] = int(d["domains"].get(dom, 0)) + 1
    raw = str(entry.get("catchall", "")).strip()
    base = f"{local}@{dom}" if local else (raw if "@" in raw else f"catchall@{dom}")
    d.setdefault("used", []).append({"addr": base, "ts": now})
    email = base
    if local and base != f"{local}@{dom}":
        email = f"{local}@{dom}"
        d["used"].append({"addr": email, "ts": now})
    _save(d)
    out = dict(entry)
    out["catchall_base"] = base
    out["catchall_domain"] = dom
    out["address"] = email
    return out


def record(email: str) -> None:
    if "@" not in email:
        return
    d = _load()
    d.setdefault("used", []).append({"addr": email.lower(), "ts": time.time()})
    _save(d)
