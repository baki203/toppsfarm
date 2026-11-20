"""Diagnose-Matrix fuer Schritt 4 (Cloudflare 403 auf /products.json).
Aufruf: python diag_cf.py <punkt>   (1..5, 7)
Jede Variante genau eine Anfrage, kein Proxy, nur curl_cffi.
"""
import re
import sys
import time

from curl_cffi import CurlHttpVersion
from curl_cffi.requests import BrowserType, Session

HOST = "de.topps.com"
BASE = f"https://{HOST}"
MIN = {"accept": "application/json", "accept-language": "de-DE,de;q=0.9,en;q=0.8"}
KNOWN = {b.value for b in BrowserType} | {"chrome", "safari", "firefox", "edge"}


def one(label, url, imp="chrome", hdr=None, **kw):
    try:
        with Session(impersonate=imp, timeout=25) as s:
            r = s.get(url, headers=hdr if hdr is not None else MIN, **kw)
        body = r.text or ""
        m = re.search(r"<title>(.*?)</title>", body, re.S | re.I)
        if '"products"' in body[:200]:
            kind = "products-JSON"
        elif m:
            kind = "title=" + m.group(1).strip()[:50]
        else:
            kind = "body=" + body[:40].replace("\n", " ")
        print(f"{label} | {r.status_code} | http={r.http_version} | "
              f"{r.headers.get('content-type', '-')} | {len(body)} B | {kind}")
        return r
    except Exception as exc:
        print(f"{label} | {type(exc).__name__}: {str(exc)[:110]}")
        return None
    finally:
        time.sleep(2)


def p1():
    one("minimal-header chrome /products.json", f"{BASE}/products.json")


def p2():
    for imp in ("chrome", "chrome131", "chrome124", "safari17_0", "firefox133"):
        if imp not in KNOWN:
            print(f"{imp} | uebersprungen (nicht installiert)")
            continue
        one(f"impersonate={imp} /products.json", f"{BASE}/products.json", imp=imp)


def p3():
    one("http1.1 chrome /products.json", f"{BASE}/products.json",
        http_version=CurlHttpVersion.V1_1)
    one("h2 chrome /products.json (Vergleich)", f"{BASE}/products.json",
        http_version=CurlHttpVersion.V2TLS)


def p4():
    one("ohne Query /products.json", f"{BASE}/products.json")
    one("mit Query /products.json?limit=250", f"{BASE}/products.json?limit=250")


def p5():
    html = {"accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": MIN["accept-language"]}
    one("/ (Startseite)", f"{BASE}/", hdr=html)
    one("/robots.txt", f"{BASE}/robots.txt", hdr=html)
    one("/sitemap.xml", f"{BASE}/sitemap.xml", hdr=html)
    r = one("/sitemap_products_1.xml", f"{BASE}/sitemap_products_1.xml", hdr=html)
    handle = None
    if r is not None and r.status_code == 200:
        hs = re.findall(r"<loc>https?://[^<]+/products/([^<?/]+)</loc>", r.text)
        print(f"handles in sitemap_products_1.xml: {len(hs)}")
        handle = hs[0] if hs else None
    if handle:
        one(f"/products/{handle}.js", f"{BASE}/products/{handle}.js")
    else:
        print("/products/<handle>.js | nicht getestet: kein Handle verfuegbar (Sitemap nicht lesbar)")


if __name__ == "__main__":
    {"1": p1, "2": p2, "3": p3, "4": p4, "5": p5}[sys.argv[1]]()
