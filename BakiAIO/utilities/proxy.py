#!/usr/bin/env python3
"""proxy - zentrale Proxy-Quelle + Normalisierung + Auth-Erkennung.

Quellen-Regel (Settings proxy.source: auto|shared|module, Default auto):
  auto   -> proxies/<modul>/*.txt zuerst; ist der Ordner leer, proxies/proxies.txt
  shared -> ausschliesslich proxies/proxies.txt
  module -> ausschliesslich proxies/<modul>/*.txt

Akzeptierte Zeilenformate (werden normalisiert):
  host:port:user:pass              (ProxyBaron-Stil, ueblich fuer shared)
  http://user:pass@host:port
  user:pass@host:port
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from utilities.root import ROOT, APP_ROOT
SHARED_FILE = ROOT / "proxies" / "proxies.txt"

PROXY_AUTH_MUSTER = (
    "proxies need authenticating",
    "proxy auth",
    "proxy authentication",
    "proxy responded with non 200 code: 407",
    "proxy authentication 407",
    "authentication required",
    "empty auth",
    "407",
)

_PROXY_SOURCE_CACHE: dict[str, str] = {}


def proxy_source() -> str:
    """Liest proxy.source aus settings.json (primaer) bzw. config/settings.yaml.
    Cache, damit nicht bei jeder Datei-Liste neu gelesen wird."""
    key = str(ROOT / "settings.json")
    if key not in _PROXY_SOURCE_CACHE:
        src = "auto"
        try:
            j = ROOT / "settings.json"
            if j.exists():
                d = json.loads(j.read_text(encoding="utf-8"))
                s = (d.get("proxy") or {}).get("source")
                if s in ("auto", "shared", "module"):
                    src = s
        except Exception:
            pass
        if src == "auto":  # yaml-Fallback
            try:
                import yaml
                y = ROOT / "config" / "settings.yaml"
                if y.exists():
                    d = yaml.safe_load(y.read_text(encoding="utf-8")) or {}
                    s = (d.get("proxy") or {}).get("source")
                    if s in ("auto", "shared", "module"):
                        src = s
            except Exception:
                pass
        _PROXY_SOURCE_CACHE[key] = src
    return _PROXY_SOURCE_CACHE[key]


def normalize_proxy(line: str) -> str | None:
    """Normalisiert ein Proxy-Format in http://user:pass@host:port.
    Bevorzugtes Eingabeformat: IP:PORT:USERNAME:PASSWORD (oder host:port:user:pass).
    Auch erlaubt: http://user:pass@host:port, user:pass@host:port, host:port.
    Liefert None fuer Leerzeilen/Kommentare/ungueltige Zeilen."""
    line = (line or "").strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith(("http://", "https://")):
        return line
    if "@" in line:  # user:pass@host:port
        return "http://" + line
    # IP:PORT:USERNAME:PASSWORD - regex statt split, damit Passwoerter
    # mit Doppelpunkt funktionieren (nur der letzte Teil ist das Passwort).
    m = re.match(r"^([^:]+):(\d+):([^:]+):(.+)$", line)
    if m:
        host, port, user, pw = m.group(1), m.group(2), m.group(3), m.group(4)
        return f"http://{user}:{pw}@{host}:{port}"
    # host:port (ohne Auth)
    m = re.match(r"^([^:]+):(\d+)$", line)
    if m:
        return f"http://{m.group(1)}:{m.group(2)}"
    return None


def isp_proxy_file(module: str) -> Path | None:
    """Sticky-ISP-Datei eines Moduls (proxies/<module>/isp.txt).
    ROOT und APP_ROOT werden beide geprueft. Hat Vorrang vor allen anderen
    Quellen, unabhaengig von proxy.source (eine sticky IP je Task)."""
    for base in (ROOT, APP_ROOT):
        p = base / "proxies" / module / "isp.txt"
        if p.exists():
            return p
    return None


def proxy_origin(module: str) -> str:
    """Quelle fuer Logs: 'isp' wenn eine ISP-Datei greift, sonst 'pool'."""
    return "isp" if isp_proxy_file(module) else "pool"


def proxy_files_for(module: str) -> list[Path]:
    """Liefert die Proxy-Dateien in der konfigurierten Reihenfolge
    (auto|shared|module), ohne Modul-Hardcodes. Eine vorhandene ISP-Datei
    (proxies/<module>/isp.txt) hat Vorrang vor allen anderen Quellen."""
    isp = isp_proxy_file(module)
    if isp:
        return [isp]
    source = proxy_source()
    files: list[Path] = []
    mod_dir = ROOT / "proxies" / module
    mod_files = []
    if mod_dir.is_dir():
        mod_files = sorted(f for f in mod_dir.glob("*.txt")
                           if f.name.lower() != "readme.txt" and f.exists())
    if source == "module":
        files = mod_files
    elif source == "shared":
        files = [SHARED_FILE] if SHARED_FILE.exists() else []
    else:  # auto: Modulordner zuerst, sonst shared
        files = mod_files if mod_files else ([SHARED_FILE] if SHARED_FILE.exists() else [])
    return files


def proxy_playwright(proxy: str | None) -> dict | None:
    """Wandelt eine normalisierte Proxy-URL in das Playwright-Proxy-Dict."""
    if not proxy:
        return None
    m = re.match(r"(?P<scheme>https?)://(?:(?P<user>[^:@]+):(?P<pw>[^@]*)@)?"
                 r"(?P<hp>[^/]+)", proxy)
    if not m:
        return None
    d = {"server": f"{m['scheme']}://{m['hp']}"}
    if m["user"] is not None:
        d["username"] = m["user"]
        d["password"] = m["pw"]
    return d


def mask_proxy(proxy: str | None) -> str:
    """Proxy ohne Passwort fuer Logs (nie Schluessel/Passwoerter ausgeben)."""
    if not proxy:
        return ""
    m = re.match(r"(https?)://([^:@]+):([^@]*)@(.+)", proxy)
    if m:
        return f"{m[1]}://{m[2]}:***@{m[4]}"
    return proxy


def is_proxy_auth_error(text: str | None) -> bool:
    """Erkennt Proxy-Auth-Fehler (407, leeres Auth, 'proxies need
    authenticating'). True = als proxy-auth loggen, nicht als Ban."""
    if not text:
        return False
    low = text.lower()
    return any(m in low for m in PROXY_AUTH_MUSTER)


def parse_proxy_lines(text: str) -> list[str]:
    """Liest Zeilen und normalisiert sie; Kommentare/Leerzeilen weg."""
    out = []
    for l in text.splitlines():
        n = normalize_proxy(l)
        if n:
            out.append(n)
    return out


def sticky_session(proxy: str, session_id: str, country: str | None = None) -> str:
    """ProxyBaron: Modifier gehoeren ins Passwort, Land VOR Session.
    Baut z. B. ...:base_country-de_session-abc123@host:port. Nur fuer Pool-
    Proxies verwenden, nie fuer ISP/statische Proxies."""
    if not proxy:
        return proxy
    m = re.match(r"(https?)://(?:([^:@/]+):([^@/]*)@)?([^/]+)$", proxy)
    if not m or not m[2]:
        return proxy
    scheme, user, pw, hp = m[1], m[2], m[3], m[4]
    base = re.sub(r"(?:_(?:country|session|lifetime|cc)-[^_]+)+$", "", pw)
    sid = re.sub(r"[^A-Za-z0-9]", "", session_id or "")
    suffix = ""
    if country:
        suffix += f"_country-{str(country).lower()}"
    if sid:
        suffix += f"_session-{sid}"
    return f"{scheme}://{user}:{base}{suffix}@{hp}"


class ProxyFailure(Exception):
    """Proxy-seitiger Fehler (407, Auth, Timeout, Verbindungsabbruch)."""


_NET_FAIL_MARKER = (
    "timeout", "timed out", "connection", "connect tunnel", "couldn't connect",
    "failed to perform", "curl: (7)", "curl: (28)", "curl: (35)", "curl: (56)",
    "eof", "reset by peer", "remote end closed", "ssl",
)


def is_proxy_failure(exc: Exception | None = None, status: int | None = None) -> bool:
    """True, wenn ein Fehler proxy-seitig ist (407/Auth/Timeout/Abbruch)."""
    if status is not None and int(status) == 407:
        return True
    if exc is None:
        return False
    if isinstance(exc, ProxyFailure):
        return True
    text = f"{type(exc).__name__}: {exc}"
    if is_proxy_auth_error(text):
        return True
    low = text.lower()
    return any(k in low for k in _NET_FAIL_MARKER)


async def run_with_failover(pool, fn, log=None, max_switches: int = 2,
                            module: str = "amazon"):
    """Fuehrt fn(proxy) aus. Bei proxy-seitigem Fehler: Proxy mark_dead und
    mit dem naechsten aus dem Pool wiederholen, max. max_switches Wechsel.
    Zaehlt als proxy-auth, nicht als Ban. Innerhalb des Tasks bleibt der
    Proxy sonst gleich (Sticky)."""
    from utilities.quality import Quality
    q = Quality(f"proxy:{module}")
    proxy = await pool.acquire() if pool is not None else None
    switches = 0
    try:
        while True:
            try:
                return await fn(proxy)
            except Exception as exc:
                if not is_proxy_failure(exc) or pool is None:
                    raise
                q.banned("proxy-auth", "proxy-auth")
                if proxy:
                    pool.mark_dead(proxy)
                if switches >= max_switches:
                    raise
                switches += 1
                proxy = await pool.acquire()
                if log is not None:
                    try:
                        log.line("Proxy", "", "",
                                 f"proxy-auth -> Wechsel {switches}/{max_switches} "
                                 f"({mask_proxy(proxy) or 'kein Proxy'})", "warn")
                    except Exception:
                        pass
    finally:
        try:
            q.finish()
        except Exception:
            pass
