#!/usr/bin/env python3
"""quality - Sperr-/Erfolgs-Zaehler je Modul (siehe QUALITY.md).
Persistiert in var/quality.sqlite (Tabelle counters) und meldet am Modulende
Versuche, Erfolge, Sperren, Retries und die Sperrquote in Prozent."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BANNER_MUSTER = (
    ("cloudflare", "cf-please-wait"),
    ("cloudflare", "access denied"),
    ("cloudflare", "attention required"),
    ("akamai", "business processing error"),
    ("akamai", "pardon our interruption"),
    ("akamai", "you have been blocked"),
    ("captcha", "captcha"),
    ("suspended", "suspended"),
    ("suspended", "this account has been blocked"),
    ("rate", "rate limit"),
    ("rate", "too many requests"),
    ("rate", "invalid credentials too many"),
)


class Quality:
    """Einfacher Zaehler je Modul-Lauf. `q.increment('attempts')`, `q.banned(text)`,
    am Ende `q.finish()`. Ausgabe: `<modul> Ende: ... Sperrquote: <x>%`."""

    def __init__(self, modul: str, db: str | None = None):
        self.modul = modul
        self.t0 = time.time()
        self.lauf = int(self.t0)
        self.counters = {"attempts": 0, "success": 0, "retries": 0, "banned": 0}
        self.banned_types: dict[str, int] = {}
        self.db = db or str(ROOT / "var" / "quality.sqlite")
        Path(self.db).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db) as con:
            con.execute("CREATE TABLE IF NOT EXISTS counters("
                        "modul TEXT, lauf INTEGER, ts REAL, attempts INTEGER, "
                        "success INTEGER, banned INTEGER, retries INTEGER, "
                        "banned_types TEXT)")

    def increment(self, key: str, n: int = 1):
        if key in self.counters:
            self.counters[key] += n

    def success(self):
        self.counters["success"] += 1

    def retry(self):
        self.counters["retries"] += 1

    def banned(self, text: str = "", typ: str | None = None):
        """Zaehlt eine Sperre. Erkennt den Typ anhand BANNER_MUSTER, wenn nicht
        angegeben."""
        self.counters["banned"] += 1
        if typ is None:
            low = text.lower()
            for name, m in BANNER_MUSTER:
                if m in low:
                    typ = name
                    break
        key = f"banned:{typ}" if typ else "banned"
        self.banned_types[key] = self.banned_types.get(key, 0) + 1

    def quota(self) -> float:
        a = self.counters["attempts"]
        return (self.counters["banned"] / a * 100.0) if a else 0.0

    def store(self):
        try:
            with sqlite3.connect(self.db) as con:
                con.execute("INSERT INTO counters VALUES (?,?,?,?,?,?,?,?)",
                            (self.modul, self.lauf, self.t0,
                             self.counters["attempts"], self.counters["success"],
                             self.counters["banned"], self.counters["retries"],
                             ",".join(f"{k}:{v}" for k, v in self.banned_types.items())))
        except sqlite3.Error:
            pass

    def finish(self) -> str:
        self.store()
        a, s, b, r = (self.counters["attempts"], self.counters["success"],
                      self.counters["banned"], self.counters["retries"])
        q = self.quota()
        line = (f"[{self.modul}] Ende: {a} Versuche, {s} ok, {b} gesperrt, "
                f"{r} retries | Sperrquote: {q:.1f}%")
        if self.banned_types:
            line += " (" + ", ".join(f"{k}={v}" for k, v in self.banned_types.items()) + ")"
        if a and q > 25.0:
            line += "\n  Warnung: Sperrquote >25% - sticky IP pruefen, Adresse/CC neu, Pause 3-5 min"
        print(line)
        return line

    def cumulative(self) -> dict:
        with sqlite3.connect(self.db) as con:
            row = con.execute("SELECT SUM(attempts), SUM(success), SUM(banned), "
                              "SUM(retries) FROM counters WHERE modul=?",
                              (self.modul,)).fetchone()
        a, s, b, r = row or (0, 0, 0, 0)
        q = (b / a * 100.0) if a else 0.0
        return {"attempts": a or 0, "success": s or 0, "banned": b or 0,
                "retries": r or 0, "quota": q}

    def report(self) -> str:
        """`--quality`-Ausgabe: bisherige Zaehler + kumulierte Quote."""
        c = self.cumulative()
        return (f"[{self.modul}] kumuliert: {c['attempts']} Versuche, {c['success']} ok, "
                f"{c['banned']} gesperrt, {c['retries']} retries | "
                f"Sperrquote: {c['quota']:.1f}%")


def detect_banned(text: str) -> str | None:
    """Gibt den Sperr-Typ (cloudflare/akamai/captcha/...) zurueck oder None."""
    low = text.lower()
    for name, m in BANNER_MUSTER:
        if m in low:
            return name
    return None
