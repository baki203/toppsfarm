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

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) \
    else Path(__file__).resolve().parent.parent
while not (ROOT / "config").exists() and ROOT.parent != ROOT:
    ROOT = ROOT.parent
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
    Liefert None fuer Leerzeilen/Kommentare/ungueltige Zeilen."""
    line = (line or "").strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith(("http://", "https://")):
        return line
    if "@" in line:  # user:pass@host:port
        return "http://" + line
    parts = line.split(":")
    if len(parts) == 4:  # host:port:user:pass
        host, port, user, pw = parts
        return f"http://{user}:{pw}@{host}:{port}"
    if len(parts) == 2:  # host:port (ohne Auth)
        return f"http://{parts[0]}:{parts[1]}"
    return None


def proxy_files_for(module: str) -> list[Path]:
    """Liefert die Proxy-Dateien in der konfigurierten Reihenfolge
    (auto|shared|module), ohne Modul-Hardcodes."""
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
