"""Mailbox-Engine: temporaere Adressen ueber mail.tm ODER eigener Catch-All
per IMAP (A1). Provider wird ueber Settings.mail.provider gewaehlt:
'mailtm' (Fallback) oder 'catchall'.

Der 'catchall'-Provider nutzt die Skyridge-Mastermails (settings.json
"Mastermails": Eintraege mit 'catchall'-Adresse + 'mastermail'/'password'
fuer den IMAP-Zugriff). OAuthForwarder (target_email) ist die zweite Quelle,
falls die Mail dorthin weitergeleitet wird."""
from __future__ import annotations

import asyncio
import imaplib
import random
import re
import string
import time
from datetime import date, timedelta

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
    `cfg` ist ein Settings-Objekt (oder None -> Settings.load())."""
    if cfg is None:
        from modules.Engine.Shopify.shopify_core import Settings
        cfg = Settings.load()
    provider = (cfg.mail.get("provider", "mailtm") if getattr(cfg, "mail", None)
                else "mailtm")
    if provider == "catchall":
        return _catchall_inbox(cfg)
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


_CATCHALL_RR = 0


def _catchall_domains(conf: dict) -> list[str]:
    """B2: listet alle Catch-All-Domains auf (mail.catchall.domains Liste, sonst
    mail.catchall.domain Einzelwert). Verhindert Einzel-Domain-Clipping, indem
    die Konto-Verteilung ueber mehrere Domains laeuft."""
    doms = conf.get("domains") or []
    doms = [str(d).strip() for d in doms if str(d).strip()]
    single = (conf.get("domain") or "").strip()
    if single and single not in doms:
        doms.insert(0, single)
    return doms


def _catchall_inbox(cfg) -> dict:
    """Erzeugt eine Catch-All-Adresse aus den Skyridge-Mastermails (round-robin,
    B2). Der IMAP-Zugriff erfolgt ueber das Master-Postfach (mastermail/password),
    an das der Catch-All weiterleitet. Liefert ein klares MailboxError, wenn kein
    gueltiger IMAP-Zugang konfiguriert ist."""
    global _CATCHALL_RR
    if cfg is None:
        from modules.Engine.Shopify.shopify_core import Settings
        cfg = Settings.load()
    mail_cfg = cfg.mail or {}
    mms = [m for m in (mail_cfg.get("mastermails") or []) if isinstance(m, dict)]
    entries = [m for m in mms if str(m.get("catchall") or "").strip()]
    if not entries:
        raise MailboxError("catchall: keine Mastermails/Catch-All-Adressen in settings.json")
    base = next((m for m in mms if m.get("mastermail") and m.get("password")), None)
    entry = entries[_CATCHALL_RR % len(entries)]
    _CATCHALL_RR += 1
    address = str(entry.get("catchall") or "").strip()
    imap_user = str(entry.get("mastermail") or (base or {}).get("mastermail") or "").strip()
    imap_pass = str(entry.get("password") or (base or {}).get("password") or "").strip()
    host = str(entry.get("imap_host") or mail_cfg.get("imap_host") or "").strip()
    if not host:
        host = _imap_host_for(mms, imap_user)
    port = int(entry.get("imap_port") or mail_cfg.get("imap_port") or 993)
    oauth = mail_cfg.get("oauth_forwarder") or {}
    # OAuthForwarder als zweite Quelle: dorthin weitergeleitete Mail lesen
    if isinstance(oauth, dict) and oauth.get("target_email") and not imap_user:
        imap_user = str(oauth["target_email"]).strip()
    if not (host and imap_user and imap_pass):
        raise MailboxError(
            "catchall: IMAP nicht konfiguriert (Mastermails ohne IMAP/mail.catchall)")
    return {
        "address": address, "password": imap_pass, "provider": "catchall",
        "imap": {"host": host, "port": port, "user": imap_user, "password": imap_pass},
        "since_days": int(mail_cfg.get("since_days", 1)),
        "delete_after_fetch": bool(mail_cfg.get("delete_after_fetch", False)),
        "regex": mail_cfg.get("confirm_regex", r"https?://\S+|\b\d{6}\b"),
        "oauth": oauth,
    }


def _imap_host_for(mastermails: list, user: str = "") -> str:
    """Leitet den IMAP-Server aus einer Mastermail ab (gmail -> imap.gmail.com,
    sonst imap.<domain>). Leer, wenn keine E-Mail-Adresse vorliegt."""
    for m in mastermails or []:
        mm = str((m or {}).get("mastermail") or "").strip()
        if not mm and user:
            mm = user
        if "@" in mm:
            dom = mm.rsplit("@", 1)[1].lower()
            if dom in ("gmail.com", "googlemail.com"):
                return "imap.gmail.com"
            return f"imap.{dom}"
    return ""


async def wait_for_link(inbox: dict, timeout: float = 120.0,
                        regex: str | None = None) -> str | None:
    """Pollt die Postfach-Meldungen und liefert den ersten Link/Code aus der
    juengsten Nachricht zurueck (oder None nach Ablauf von `timeout`).
    `regex` kommt, wenn None, aus der Inbox-Konfiguration (confirm_regex)."""
    if regex is None:
        regex = inbox.get("regex") or r"https?://\S+"
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
    since_days = int(inbox.get("since_days", 1))
    delete_after = bool(inbox.get("delete_after_fetch", False))
    end = time.monotonic() + timeout
    # frische Meldungen merken (UID-basiert), damit keine verpasst werden
    seen: set[str] = set()
    while time.monotonic() < end:
        try:
            mail = await asyncio.to_thread(_imap_connect, host, port, user, pw)
            try:
                since = (date.today() - timedelta(days=since_days)).strftime("%d-%b-%Y")
                status, items = await asyncio.to_thread(mail.search, None, f"SINCE {since}")
                if status != "OK":
                    await asyncio.sleep(3.0)
                    continue
                uids = items[0].split()
                for uid in uids[-15:]:
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
                                    if delete_after:
                                        try:
                                            await asyncio.to_thread(
                                                mail.store, uid, "+FLAGS", r"\\Deleted")
                                            await asyncio.to_thread(mail.expunge)
                                        except Exception:
                                            pass
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