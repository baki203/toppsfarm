"""Mailbox-Engine: temporaere Adressen ueber mail.tm ODER eigener Catch-All
per IMAP (A1). Provider wird ueber Settings.mail.provider gewaehlt:
'mailtm' (Fallback) oder 'catchall'."""
from __future__ import annotations

import asyncio
import imaplib
import random
import re
import string
import time

from curl_cffi.requests import AsyncSession

API = "https://api.mail.tm"
UA = "BakiAIO/1.0 (mail.tm client)"


class MailboxError(Exception):
    pass


def _session() -> AsyncSession:
    return AsyncSession(timeout=20,
                        headers={"accept": "application/json", "user-agent": UA})


async def create_inbox(cfg=None) -> dict:
    """-> {'address': ..., 'password': ..., 'provider': 'mailtm'|'catchall'}.
    Legt ein Konto auf mail.tm an oder erzeugt eine Catch-All-Adresse (A1).
    `cfg` ist ein Settings-Objekt (oder None fuer mail.tm)."""
    provider = (cfg.mail.get("provider", "mailtm") if cfg and getattr(cfg, "mail", None)
                else "mailtm")
    if provider == "catchall":
        return _catchall_inbox(cfg.mail.get("catchall", {}))
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
        return {"address": acc["address"], "password": password, "provider": "mailtm"}


def _catchall_inbox(conf: dict) -> dict:
    """Erzeugt eine Catch-All-Adresse `<zufall>@<domain>` (A1). Der IMAP-Zugriff
    erfolgt ueber das Master-Postfach, an das der Catch-All weiterleitet."""
    domain = (conf.get("domain") or "").strip()
    if not domain:
        raise MailboxError("catchall: keine Domain in settings.json (mail.catchall.domain)")
    local = "".join(random.choice(string.ascii_lowercase + string.digits)
                    for _ in range(12))
    return {"address": f"{local}@{domain}", "password": "",
            "provider": "catchall",
            "imap": {"host": conf.get("imap_host", ""), "port": int(conf.get("imap_port", 993)),
                     "user": conf.get("user", ""), "password": conf.get("password", "")}}


async def wait_for_link(inbox: dict, timeout: float = 120.0,
                        regex: str = r"https?://\S+") -> str | None:
    """Pollt die Postfach-Meldungen und liefert den ersten Link aus der
    juengsten Nachricht zurueck (oder None nach Ablauf von `timeout`)."""
    if inbox.get("provider") == "catchall":
        return await _imap_wait_for_link(inbox, timeout, regex)
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


async def _imap_wait_for_link(inbox: dict, timeout: float,
                              regex: str) -> str | None:
    """Catch-All: durchsucht das Master-IMAP-Postfach nach Meldungen, die an die
    Adresse `inbox['address']` gerichtet sind, und extrahiert den ersten Link."""
    imap = inbox["imap"]
    host, port = imap.get("host"), imap.get("port", 993)
    user, pw = imap.get("user"), imap.get("password")
    if not (host and user and pw):
        raise MailboxError("catchall: IMAP-Zugang unvollstaendig in settings.json")
    end = time.monotonic() + timeout
    # frische Meldungen merken (SUBJECT-/UID-basiert), damit keine verpasst werden
    seen: set[str] = set()
    while time.monotonic() < end:
        try:
            mail = await asyncio.to_thread(_imap_connect, host, port, user, pw)
            try:
                status, items = await asyncio.to_thread(mail.search, None, "ALL")
                if status != "OK":
                    await asyncio.sleep(3.0)
                    continue
                uids = items[0].split()
                for uid in uids[-10:]:
                    key = uid.decode()
                    if key in seen:
                        continue
                    status, data = await asyncio.to_thread(mail.fetch, uid, "(RFC822)")
                    if status != "OK":
                        continue
                    for part in data:
                        if isinstance(part, tuple):
                            raw = part[1]
                            text = _decode_raw(raw)
                            if inbox["address"] in text or _recipient_matches(text, inbox["address"]):
                                m = re.search(regex, text)
                                if m:
                                    seen.add(key)
                                    return m.group(1)
                    seen.add(key)
            finally:
                try:
                    await asyncio.to_thread(mail.logout)
                except Exception:
                    pass
        except Exception:
            pass
        await asyncio.sleep(3.0)
    return None


def _imap_connect(host: str, port: int, user: str, pw: str) -> imaplib.IMAP4_SSL:
    mail = imaplib.IMAP4_SSL(host, port)
    mail.login(user, pw)
    mail.select("INBOX")
    return mail


def _decode_raw(raw: bytes) -> str:
    import email as _email
    try:
        msg = _email.message_from_bytes(raw)
        payload = ""
        if msg.is_multipart():
            for part in msg.walk():
                ct = part.get_content_type()
                if ct in ("text/plain", "text/html"):
                    try:
                        payload += part.get_payload(decode=True).decode(
                            part.get_content_charset() or "utf-8", errors="replace")
                    except Exception:
                        pass
        else:
            payload = msg.get_payload(decode=True).decode(
                msg.get_content_charset() or "utf-8", errors="replace")
        return payload
    except Exception:
        return raw.decode("utf-8", errors="replace")


def _recipient_matches(text: str, address: str) -> bool:
    low = text.lower()
    for m in re.finditer(r"To:\s*([^\r\n]+)", low):
        if address.lower() in m.group(1).lower():
            return True
    return False


async def _token(inbox: dict) -> str:
    async with _session() as s:
        r = await s.post(f"{API}/token",
                         json={"address": inbox["address"],
                               "password": inbox["password"]})
        if r.status_code != 200:
            raise MailboxError(f"token {r.status_code}")
        return r.json()["token"]