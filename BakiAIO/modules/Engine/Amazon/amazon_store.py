#!/usr/bin/env python3
"""Skyridge-kompatibler Account-Store fuer Amazon (Dateilayout exakt wie
Skyridge, damit die selben Dateien gegen beide Tools funktionieren).

Datei-Layout in accounts/Amazon/ (Basis = accounts_dir("amazon")):
  gen_AmazonAccounts.csv        - Generator-Output
  custom_AmazonAccounts.csv     - manuelle Konten
  tasks_AmazonAccounts.csv      - Run-Input (welche Konten verarbeitet werden)
  checked_AmazonAccounts.csv    - Checker-Output (status)
  invited_AmazonAccounts.csv    - Invites-Ergebnislog (je Konto)
  farmed_AmazonAccounts.csv     - Farmer-Output (farmed + Proxy-Stickiness)
  taskcc_AmazonAccounts.csv     - Konten + Karte
  checkout_AmazonAccounts.csv   - ACO-Output (Adresse + Karte + asins)
  orders_AmazonAccounts.csv     - Bestelllog
  asinHistory.txt               - kommaseparierte ASIN-Liste (alle bearbeiteten)
  invites/<ASIN>_AmazonAccounts.csv  - Konten, die Invite fuer ASIN angefordert
  .sessions/<email>__<CC>.json       - Cookie-Liste [{name,value,domain,path}]

Alle CSV-Spalten: klein geschrieben (Skyridge-Format). Zeilen werden nur
angehaengt (append), Duplikate ueber Email/ASIN werden uebersprungen.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from modules.Engine.Amazon.amazon_core import accounts_dir, json_dumps, json_loads

HEADERS = {
    "gen":       ["email", "email_password", "password", "firstName", "lastName",
                  "phonenumber", "country_iso", "phone_iso", "proxy", "domain",
                  "proxy_session"],
    "custom":    ["email", "email_password", "password", "firstName", "lastName",
                  "country_iso", "phone_iso", "phonenumber", "proxy"],
    "tasks":     ["email", "email_password", "password", "country_iso", "proxy"],
    "checked":   ["email", "email_password", "password", "firstName", "lastName",
                  "country_iso", "phone_iso", "phonenumber", "status", "proxy"],
    "invited":   ["email", "asin", "country_iso", "status", "product", "price",
                  "checked_at"],
    "farmed":    ["email", "email_password", "password", "country_iso", "farmed",
                  "proxy_host", "proxy_port", "proxy_pool", "proxy_user"],
    "taskcc":    ["email", "email_password", "password", "country_iso", "proxy",
                  "cardNumber", "cardMonth", "cardYear", "cardCvc",
                  "cardHolderName"],
    "checkout":  ["email", "email_password", "password", "firstName", "lastName",
                  "phoneNumber", "country_iso", "proxy", "asins",
                  "addressLine1", "addressLine2", "city", "state", "postalCode",
                  "addressCountry", "bank_code", "cardNumber", "cardMonth",
                  "cardYear", "cardCvc", "cardHolderName", "giftcard",
                  "webhook_url", "delivery_preference"],
    "orders":    ["email", "purchaseId", "asins", "totalAmount", "currency",
                  "paymentMethod", "bank_psp_url", "status", "error", "timestamp"],
}


class AmazonStore:
    """Dateizugriff auf accounts/Amazon/ im Skyridge-Layout."""

    HEADERS = HEADERS

    def __init__(self, site: str = "amazon"):
        self.site = site
        self.base = accounts_dir(site)
        self.invites_dir = self.base / "invites"
        self.sessions_dir = self.base / ".sessions"
        self.invites_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------- Pfade
    def _f(self, kind: str) -> Path:
        return self.base / f"{kind}_AmazonAccounts.csv"

    def _ensure_header(self, p: Path, kind: str) -> None:
        want = HEADERS[kind]
        if not p.exists():
            p.write_text(",".join(want) + "\n", encoding="utf-8")
            return
        try:
            with open(p, encoding="utf-8", newline="") as f:
                first = f.readline().strip()
        except Exception:
            return
        have = [h.strip() for h in first.split(",")] if first else []
        if have == want:
            return
        rows = self.read(kind)
        with open(p, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=want)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in want})

    # ------------------------------------------------------------- Lesen
    def read(self, kind: str) -> list[dict]:
        """Liest alle Zeilen einer Art, keys kleingeschrieben und getrimmt."""
        p = self._f(kind)
        if not p.exists():
            return []
        try:
            with open(p, encoding="utf-8", newline="") as f:
                rows = [{k.strip(): (v or "").strip() for k, v in r.items()}
                        for r in csv.DictReader(f)]
            return rows
        except Exception:
            return []

    def read_tasks(self) -> list[dict]:
        """Run-Input: tasks_AmazonAccounts.csv. Fallback auf gen/custom."""
        rows = self.read("tasks")
        if rows:
            return rows
        rows = self.read("gen")
        if rows:
            return rows
        return self.read("custom")

    def list_inputs(self) -> list[str]:
        """Alle vorhandenen tasks_*-CSV-Dateien (Skyridge hat oft mehrere,
        z. B. 'tasks_AmazonAccounts JP only_clean_clean_clean.csv')."""
        out = []
        for f in self.base.glob("tasks_AmazonAccounts*.csv"):
            out.append(f.name)
        return sorted(out)

    def read_file(self, name: str) -> list[dict]:
        """Liest eine beliebige CSV-Datei im Amazon-Ordner (keys klein)."""
        p = self.base / name
        if not p.exists():
            return []
        try:
            with open(p, encoding="utf-8", newline="") as f:
                return [{k.strip(): (v or "").strip() for k, v in r.items()}
                        for r in csv.DictReader(f)]
        except Exception:
            return []

    # ------------------------------------------------------------- Anhaengen
    def append(self, kind: str, row: dict, dedupe_keys: list[str] | None = None) -> bool:
        """Haengt eine Zeile an (Header neu angelegt falls noetig).
        Gibt False zurueck, wenn bereits vorhanden (Dedupe ueber die Keys)."""
        p = self._f(kind)
        self._ensure_header(p, kind)
        if dedupe_keys:
            for existing in self.read(kind):
                if all(str(existing.get(k) or "") == str(row.get(k) or "")
                       for k in dedupe_keys):
                    return False
        with open(p, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=HEADERS[kind])
            w.writerow({k: row.get(k, "") for k in HEADERS[kind]})
        return True

    def append_many(self, kind: str, rows: list[dict], dedupe_keys=None) -> int:
        n = 0
        for r in rows:
            if self.append(kind, r, dedupe_keys):
                n += 1
        return n

    # ------------------------------------------------------------- Session-Dateien
    def session_path(self, email: str, cc: str = "DE") -> Path:
        return self.sessions_dir / f"{_slug(email)}__{cc.upper()}.json"

    def save_session(self, email: str, cookies: list[dict], cc: str = "DE") -> Path:
        p = self.session_path(email, cc)
        p.write_text(json_dumps(cookies), encoding="utf-8")
        return p

    def load_session(self, email: str, cc: str = "DE") -> list[dict] | None:
        p = self.session_path(email, cc)
        if not p.exists():
            return None
        try:
            return json_loads(p)
        except Exception:
            return None

    # ------------------------------------------------------------- Invites pro ASIN
    def invite_path(self, asin: str) -> Path:
        asin = asin.strip().upper()
        asin = re.sub(r"[^A-Z0-9]+", "_", asin)
        return self.invites_dir / f"{asin}_AmazonAccounts.csv"

    def add_invite(self, asin: str, email: str, pwd: str, cc: str,
                   proxy: str = "") -> bool:
        """Merkt Konto in invites/<ASIN>_AmazonAccounts.csv (Dedupe ueber email)."""
        p = self.invite_path(asin)
        self._ensure_header(p, "tasks")
        seen = set()
        if p.exists():
            try:
                with open(p, encoding="utf-8", newline="") as f:
                    for r in csv.DictReader(f):
                        seen.add((r.get("email") or "").strip())
            except Exception:
                pass
        if email in seen:
            return False
        with open(p, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=HEADERS["tasks"])
            w.writerow({"email": email, "email_password": "", "password": pwd,
                        "country_iso": cc, "proxy": proxy})
        return True

    # ------------------------------------------------------------- asinHistory
    def asin_history(self) -> list[str]:
        p = self.base / "asinHistory.txt"
        if not p.exists():
            return []
        try:
            raw = p.read_text(encoding="utf-8")
        except Exception:
            return []
        return [x.strip() for x in re.split(r"[,;]", raw) if x.strip()]

    def add_asin_history(self, asin: str) -> bool:
        p = self.base / "asinHistory.txt"
        hist = self.asin_history()
        if asin in hist:
            return False
        hist.append(asin)
        p.write_text(", ".join(hist), encoding="utf-8")
        return True


def _slug(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9._+-]+", "_", s)
    return s[:120]