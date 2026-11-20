"""sms - SMS-Provider-Abstraktion (A10). 5sim, smspva, herosms.
Je Provider: Nummer kaufen (buy), Code pollen (poll_code), Nummer freigeben
(release). Nur bei Aufforderung nutzen (only_on_request=true). Zaehler:
attempts/Fehlschlaege ueber Quality."""
from __future__ import annotations

import asyncio
import random
import time
import uuid

from curl_cffi.requests import AsyncSession

from utilities.quality import Quality


class SmsError(Exception):
    pass


class SmsProvider:
    """Basis: Config aus settings.sms + keys aus keys.env (SMS_*_KEY)."""

    name = "base"

    def __init__(self, cfg):
        self.cfg = cfg.sms or {}
        self.country = self.cfg.get("country", "RU")
        self.q = Quality(f"sms:{self.name}")

    def _key(self, env_key: str, name: str) -> str:
        from modules.Engine.Shopify.shopify_core import ENV
        k = (ENV.get(env_key) or "").strip()
        if not k:
            raise SmsError(f"{name}: kein API-Key (keys.env {env_key})")
        return k

    async def buy(self, service: str) -> dict:
        """-> {'number':..., 'order_id':...}. Fehlschlaege werden gezahlt."""
        try:
            r = await self._buy(service)
            self.q.record(True)
            return r
        except Exception as exc:
            self.q.record(False, str(exc))
            raise

    async def poll_code(self, order_id, service: str, timeout: float = 180.0) -> str | None:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                code = await self._poll(order_id, service)
                if code:
                    return code
            except Exception:
                pass
            await asyncio.sleep(random.uniform(3.0, 6.0))
        self.q.banned("sms-timeout")
        self.q.store()
        return None

    async def release(self, order_id):
        try:
            await self._release(order_id)
        except Exception:
            pass

    async def _buy(self, service: str) -> dict:  # pragma: no cover
        raise NotImplementedError

    async def _poll(self, order_id, service: str) -> str | None:  # pragma: no cover
        raise NotImplementedError

    async def _release(self, order_id):  # pragma: no cover
        raise NotImplementedError


class Sms5sim(SmsProvider):
    name = "5sim"

    def __init__(self, cfg):
        super().__init__(cfg)
        self.api = "https://5sim.net/v1"

    def _key(self):
        return super()._key("SMS_5SIM_KEY", "5sim")

    def _country(self) -> str:
        return (self.cfg.get("5sim", {}).get("country") or self.country or "ru").lower()

    def _operator(self) -> str:
        return (self.cfg.get("5sim", {}).get("operator") or "any").lower()

    async def _buy(self, service: str) -> dict:
        key = self._key()
        op = self._operator()
        url = f"{self.api}/user/buy/activation/{self._country()}/{op}/{service}"
        async with AsyncSession(timeout=20) as s:
            s.headers.update({"Authorization": f"Bearer {key}",
                              "Accept": "application/json"})
            r = await s.get(url)
            if r.status_code not in (200, 201):
                raise SmsError(f"5sim buy {r.status_code}: {r.text[:160]}")
            d = r.json()
            return {"number": d.get("number", ""), "order_id": str(d.get("id", "")),
                    "service": service}

    async def _poll(self, order_id, service) -> str | None:
        key = self._key()
        async with AsyncSession(timeout=20) as s:
            s.headers.update({"Authorization": f"Bearer {key}",
                              "Accept": "application/json"})
            r = await s.get(f"{self.api}/user/check/{order_id}")
            if r.status_code != 200:
                return None
            d = r.json()
            sms = d.get("sms") or []
            for m in sms:
                code = m.get("code")
                if code:
                    return str(code).strip()
        return None

    async def _release(self, order_id):
        key = self._key()
        async with AsyncSession(timeout=20) as s:
            s.headers.update({"Authorization": f"Bearer {key}",
                              "Accept": "application/json"})
            await s.get(f"{self.api}/user/release/{order_id}")


class SmsSmspva(SmsProvider):
    name = "smspva"

    def __init__(self, cfg):
        super().__init__(cfg)
        self.api = "https://smspva.com/priemnik.php"

    def _key(self):
        return super()._key("SMS_SMSPVA_KEY", "smspva")

    def _country(self) -> str:
        return str(self.cfg.get("smspva", {}).get("country") or self.cfg.get("country") or "RU")

    async def _buy(self, service: str) -> dict:
        key = self._key()
        async with AsyncSession(timeout=20) as s:
            r = await s.get(self.api, params={"apikey": key, "metod": "get_number",
                                              "country": self._country(),
                                              "service": service, "id": str(uuid.uuid4())})
            d = r.json()
            if str(d.get("response")) != "1":
                raise SmsError(f"smspva buy: {d.get('response')} {d.get('text')}")
            return {"number": str(d.get("number")), "order_id": str(d.get("id")),
                    "service": service}

    async def _poll(self, order_id, service) -> str | None:
        key = self._key()
        async with AsyncSession(timeout=20) as s:
            r = await s.get(self.api, params={"apikey": key, "metod": "get_sms",
                                              "id": order_id})
            d = r.json()
            if str(d.get("response")) == "1":
                return str(d.get("sms")).strip()
        return None

    async def _release(self, order_id):
        key = self._key()
        async with AsyncSession(timeout=20) as s:
            await s.get(self.api, params={"apikey": key, "metod": "deny", "id": order_id})


class SmsHerosms(SmsProvider):
    name = "herosms"

    def __init__(self, cfg):
        super().__init__(cfg)
        self.api = "https://sms.herosms.ru/stubs/handler_api.php"

    def _key(self):
        return super()._key("SMS_HEROSMS_KEY", "herosms")

    def _country(self) -> str:
        return str(self.cfg.get("herosms", {}).get("country") or self.cfg.get("country") or "RU")

    async def _buy(self, service: str) -> dict:
        key = self._key()
        async with AsyncSession(timeout=20) as s:
            r = await s.get(self.api, params={"api_key": key, "action": "getNumber",
                                              "service": service,
                                              "country": self._country()})
            d = r.json()
            if str(d.get("response")) != "1":
                raise SmsError(f"herosms buy: {d.get('response')} {d.get('text')}")
            return {"number": str(d.get("number")), "order_id": str(d.get("id")),
                    "service": service}

    async def _poll(self, order_id, service) -> str | None:
        key = self._key()
        async with AsyncSession(timeout=20) as s:
            r = await s.get(self.api, params={"api_key": key, "action": "getSmsCode",
                                              "id": order_id})
            d = r.json()
            if str(d.get("response")) == "1":
                return str(d.get("smscode")).strip()
        return None

    async def _release(self, order_id):
        key = self._key()
        async with AsyncSession(timeout=20) as s:
            await s.get(self.api, params={"api_key": key, "action": "cancelNumber",
                                          "id": order_id})


_PROVIDERS = {"5sim": Sms5sim, "smspva": SmsSmspva, "herosms": SmsHerosms}


def get_provider(cfg) -> SmsProvider | None:
    """Liefert den konfigurierten Provider oder None (disabled)."""
    sms = getattr(cfg, "sms", None) or {}
    if not sms.get("enabled", False):
        return None
    name = (sms.get("provider") or "5sim").lower()
    cls = next((c for k, c in _PROVIDERS.items() if k.lower() == name), None)
    if not cls:
        raise SmsError(f"unbekannter SMS-Provider: {name}")
    return cls(cfg)


def need_sms(cfg) -> bool:
    """A10: Telefon nur bei Aufforderung -> Nur wenn only_on_request deaktiviert."""
    sms = getattr(cfg, "sms", None) or {}
    return sms.get("enabled", False) and not sms.get("only_on_request", True)

