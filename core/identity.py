"""Identitaets-Engine: erzeugt kohaerente deutsche Identitaeten."""
from __future__ import annotations

import random
import string
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

UMLAUT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
                        "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"})
SYMBOLS = "!?#%+*"


class IdentityError(Exception):
    pass


def _pool(name: str) -> list[str]:
    p = DATA / name
    if not p.exists():
        raise IdentityError(f"Datendatei fehlt: {p}")
    items = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not items:
        raise IdentityError(f"Datendatei leer: {p}")
    return items


@dataclass
class Identity:
    first_name: str
    last_name: str
    email: str
    password: str
    street: str
    house_no: str
    zip: str
    city: str
    area_code: str
    phone: str
    birth_day: int
    birth_month: int
    birth_year: int

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def address(self) -> str:
        return f"{self.street} {self.house_no}"

    @property
    def birthdate(self) -> date:
        return date(self.birth_year, self.birth_month, self.birth_day)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["full_name"] = self.full_name
        d["address"] = self.address
        d["birthdate"] = self.birthdate.strftime("%d.%m.%Y")
        return d


class IdentityGenerator:
    def __init__(self, mail_domain: str = "mail.tm", seed: int | None = None):
        self.rng = random.Random(seed)
        self.mail_domain = mail_domain
        self._first = _pool("de_firstnames.txt")
        self._last = _pool("de_lastnames.txt")
        self._streets = _pool("de_streets.txt")
        self._places = self._load_places()

    @staticmethod
    def _load_places() -> list[tuple[str, str, str]]:
        out = []
        for line in _pool("de_places.txt"):
            parts = [p.strip() for p in line.split(";")]
            if len(parts) == 3:
                out.append((parts[0], parts[1], parts[2]))
        if not out:
            raise IdentityError("de_places.txt unbrauchbar")
        return out

    def generate(self) -> Identity:
        first = self.rng.choice(self._first)
        last = self.rng.choice(self._last)
        street = self.rng.choice(self._streets)
        zip_code, city, area = self.rng.choice(self._places)
        house = str(self.rng.randint(1, 120))
        if self.rng.random() < 0.15:
            house += self.rng.choice("abc")
        tail = str(self.rng.randint(1000000, 9999999))
        return Identity(
            first_name=first,
            last_name=last,
            email=self._email(first, last),
            password=self._password(),
            street=street,
            house_no=house,
            zip=zip_code,
            city=city,
            area_code=area,
            phone=f"+49{area.lstrip('0')}{tail}",
            birth_day=self.rng.randint(1, 28),
            birth_month=self.rng.randint(1, 12),
            birth_year=self.rng.randint(1980, 2003),
        )

    def _email(self, first: str, last: str) -> str:
        local = f"{first}.{last}{self.rng.randint(10, 99)}".replace(" ", "")
        return f"{local.lower().translate(UMLAUT)}@{self.mail_domain}"

    def _password(self) -> str:
        pool = string.ascii_letters + string.digits + SYMBOLS
        while True:
            pw = "".join(self.rng.choice(pool) for _ in range(12))
            if (any(c.islower() for c in pw) and any(c.isupper() for c in pw)
                    and any(c.isdigit() for c in pw) and any(c in SYMBOLS for c in pw)):
                return pw

