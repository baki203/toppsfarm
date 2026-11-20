"""Profil-Generator: erzeugt N Profile aus IdentityGenerator fuer accounts/<mod>/profiles.yaml."""
from __future__ import annotations

from pathlib import Path

import yaml

from utilities.identity import IdentityGenerator
from utilities.root import ROOT


def generate_profiles(count: int, seed: int | None = None,
                      mail_domain: str = "mail.tm") -> list[dict]:
    """Erzeugt `count` Profile als YAML-faehige Dicts (Identitaets-Format) mit
    leerer Karte, max_orders 2 und laufender id (p01, p02, ...)."""
    gen = IdentityGenerator(mail_domain=mail_domain, seed=seed)
    out = []
    for i in range(1, count + 1):
        ident = gen.generate()
        d = ident.as_dict()
        d.update({
            "id": f"p{i:02d}",
            "enabled": True,
            "country": "DE",
            "card": {"number": "", "exp_month": 0, "exp_year": 0,
                     "cvv": "", "holder": ""},
            "proxy": None,
            "max_orders": 2,
        })
        out.append(d)
    return out


def write_profiles(rows: list[dict], module: str = "topps",
                   path: Path | None = None) -> Path:
    """Schreibt Profile nach accounts/<module>/profiles.yaml (oder in eine
    uebergebene Datei, z. B. fuer Tests)."""
    p = path or (ROOT / "accounts" / module / "profiles.yaml")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(rows, allow_unicode=True, sort_keys=False),
                 encoding="utf-8")
    return p


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="profiles-gen")
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--module", default="topps")
    ap.add_argument("--out", default=None, help="Zieldatei (nur fuer Tests)")
    a = ap.parse_args()
    if a.count < 1:
        raise SystemExit("--count muss >= 1 sein")
    rows = generate_profiles(a.count, a.seed)
    dest = write_profiles(rows, a.module, Path(a.out) if a.out else None)
    print(f"{len(rows)} Profile nach {dest}")
