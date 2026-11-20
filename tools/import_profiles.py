#!/usr/bin/env python3
"""Profil-Import aus CSV im Format von "Zahlungen - Kopie.csv".
Liest UTF-8 mit BOM, entfernt Tabs, schreibt config/profiles.yaml.
Zeilen ohne Kartennummer werden uebersprungen."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import yaml

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) \
    else Path(__file__).resolve().parent.parent

COL = {
    "first_name": "shipping/firstname",
    "last_name": "shipping/lastname",
    "address": "shipping/address",
    "house_no": "shipping/address2",
    "zip": "shipping/zip",
    "city": "shipping/city",
    "country": "shipping/country",
    "phone": "shipping/phone",
    "card_number": "cc/number",
    "card_month": "cc/month",
    "card_year": "cc/year",
    "card_cvc": "cc/cvc",
    "card_name": "cc/name",
    "email": "email",
    "checkout_limit": "checkoutLimit",
}


def clean(v) -> str:
    return "" if v is None else str(v).replace("\t", " ").strip()


def read_profiles(csv_path: Path) -> list[dict]:
    rows = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for line in reader:
            number = clean(line.get(COL["card_number"]))
            if not number:
                continue
            number = number.replace(" ", "")
            limit = clean(line.get(COL["checkout_limit"]))
            try:
                max_orders = int(limit)
            except ValueError:
                max_orders = 0
            max_orders = max_orders if max_orders >= 1 else 2
            address = clean(line.get(COL["address"]))
            house_no = clean(line.get(COL["house_no"]))
            street = f"{address} {house_no}".strip() if address and house_no else address
            card_name = clean(line.get(COL["card_name"]))
            rows.append({
                "first_name": clean(line.get(COL["first_name"])),
                "last_name": clean(line.get(COL["last_name"])),
                "email": clean(line.get(COL["email"])),
                "street": street,
                "house_no": house_no,
                "address": street,
                "zip": clean(line.get(COL["zip"])),
                "city": clean(line.get(COL["city"])),
                "area_code": "",
                "phone": clean(line.get(COL["phone"])),
                "full_name": f"{clean(line.get(COL['first_name']))} "
                             f"{clean(line.get(COL['last_name']))}".strip(),
                "country": clean(line.get(COL["country"])) or "DE",
                "card": {
                    "number": number,
                    "exp_month": clean(line.get(COL["card_month"])),
                    "exp_year": clean(line.get(COL["card_year"])),
                    "cvv": clean(line.get(COL["card_cvc"])),
                    "holder": card_name,
                },
                "proxy": None,
                "max_orders": max_orders,
                "enabled": True,
            })
    for i, r in enumerate(rows, 1):
        r["id"] = f"p{i:02d}"
    return rows


def write_profiles(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(rows, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")


def main(argv) -> int:
    if len(argv) < 1:
        print(__doc__)
        return 1
    src = Path(argv[0])
    if not src.exists():
        print(f"Datei nicht gefunden: {src}")
        return 1
    dest = Path(argv[1]) if len(argv) > 1 else ROOT / "config" / "profiles.yaml"
    rows = read_profiles(src)
    write_profiles(rows, dest)
    print(f"{len(rows)} Profile importiert nach {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))