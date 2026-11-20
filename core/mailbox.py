"""Mailbox-Engine: temporaere Adressen ueber mail.tm."""
from __future__ import annotations

import asyncio
import re
import time

from curl_cffi.requests import AsyncSession

API = "https://api.mail.tm"
UA = "BakiAIO/1.0 (mail.tm client)"


class MailboxError(Exception):
    pass


def _session() -> AsyncSession:
    return AsyncSession(timeout=20,
                        headers={"accept": "application/json", "user-agent": UA})


async def create_inbox() -> dict:
    """-> {'address': ..., 'password': ...}. Legt ein Konto auf mail.tm an."""
    async with _session() as s:
        r = await s.get(f"{API}/domains")
        if r.status_code != 200:
            raise MailboxError(f"domains {r.status_code}")
        doms = r.json()
        if not doms:
            raise MailboxError("mail.tm ohne Domains")
        dom = doms[0]["domain"]
        password = f"Baki!{int(time.time())}x"
        r = await s.post(f"{API}/accounts",
                         json={"address": f"baki{int(time.time())}@{dom}",
                               "password": password})
        if r.status_code not in (200, 201):
            raise MailboxError(f"account {r.status_code}: {r.text[:200]}")
        acc = r.json()
        return {"address": acc["address"], "password": password}


async def wait_for_link(inbox: dict, timeout: float = 120.0,
                        regex: str = r"https?://\S+") -> str | None:
    """Pollt die Postfach-Meldungen und liefert den ersten Link aus der
    juengsten Nachricht zurueck (oder None nach Ablauf von `timeout`)."""
    token = await _token(inbox)
    end = time.monotonic() + timeout
    async with _session() as s:
        s.headers["authorization"] = f"Bearer {token}"
        while time.monotonic() < end:
            r = await s.get(f"{API}/messages", params={"page": 1})
            if r.status_code == 200:
                body = r.json()
                msgs = body if isinstance(body, list) else body.get("hydra:member", [])
                for msg in msgs or []:
                    m = await s.get(f"{API}/messages/{msg['id']}")
                    if m.status_code != 200:
                        continue
                    data = m.json()
                    text = (data.get("html") or data.get("text") or "")
                    link = re.search(regex, text)
                    if link:
                        return link.group(1)
            await asyncio.sleep(3.0)
    return None


async def _token(inbox: dict) -> str:
    async with _session() as s:
        r = await s.post(f"{API}/token",
                         json={"address": inbox["address"],
                               "password": inbox["password"]})
        if r.status_code != 200:
            raise MailboxError(f"token {r.status_code}")
        return r.json()["token"]