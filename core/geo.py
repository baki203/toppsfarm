"""geo - IP-Geo-Pruefung via ip-api.com (A4).
Vergleicht das Land/Region einer Proxy-IP mit der Profiladresse. Vor Taskstart
pruefen; bei Abweichung Task nicht starten und als banned:geo zaehlen."""
from __future__ import annotations

from curl_cffi.requests import AsyncSession

API = "http://ip-api.com/json/"


async def ip_geo(proxy: str | None = None, ip: str | None = None) -> dict | None:
    """Fragt die Geo-Daten einer IP (oder der eigenen/Proxy-Ausgangs-IP) ab.
    -> {'countryCode','country','region','regionName','city','query','status'}
    oder None bei Fehler. Ueber einen Proxy laeuft der Request durch die
    Ausgangs-IP des Proxys."""
    kw = {"impersonate": "chrome", "timeout": 15}
    if proxy:
        kw["proxy"] = proxy
    url = f"{API}{ip}" if ip else API
    try:
        async with AsyncSession(**kw) as s:
            r = await s.get(url)
            if r.status_code != 200:
                return None
            d = r.json()
            if d.get("status") != "success":
                return None
            return d
    except Exception:
        return None


def region_matches(geo: dict | None, country: str, region: str = "") -> tuple[bool, str]:
    """Vergleicht die Geo-Daten mit Land (+ optional Region/Stadt).
    -> (ok, hinweis). Country ist 2-Buchstaben-ISO. None -> unbestimmbar."""
    if not geo:
        return False, "geo unbestimmbar"
    gcc = (geo.get("countryCode") or "").upper()
    want = (country or "").upper()
    if not want:
        return True, "kein Land im Profil"
    if gcc != want:
        return False, f"Land {gcc} != {want}"
    if region:
        # Region/Stadt nur warnen (nicht blocken): ip-api liefert city + regionName
        g_region = f"{geo.get('regionName','')} {geo.get('city','')}".lower()
        if region.lower() not in g_region and g_region not in region.lower():
            return False, f"Region {g_region.strip()} != {region}"
    return True, "geo ok"