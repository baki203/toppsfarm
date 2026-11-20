# discord/auswerten.py - Community-Export durch die Venice-API auswerten.
# Nur Standardbibliothek. Ablauf:
#   --vorfilter  : Vorfilter + Relevanzfilter, Zwischenstand + Stueckzahl + Kostenschaetzung
#   --stueck N   : genau ein Stueck (Index N) an die Venice-API senden, Ausgabe zeigen
#   --lauf       : alle offenen Stuecke (max 40 je Lauf), bis 1,00 $ hart stoppen
# Neustart ueberspringt Erledigtes (discord/fortschritt.json). Keys aus config/keys.env
# (VENICE_API_KEY, VENICE_MODEL), gleicher Parser wie load_env() in modules/shopify_core.py.
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DISCORD = ROOT / "discord"
KEYS = ROOT / "config" / "keys.env"
VORGEFILTERT = DISCORD / "vorgefiltert.json"
WISSEN = DISCORD / "WISSEN_roh.md"
FORTSCHRITT = DISCORD / "fortschritt.json"

API_URL = "https://api.venice.ai/api/v1/chat/completions"
CHUNK_ZEICHEN = 100_000
MAX_STUECKE_LAUF = 40
KOSTEN_EINGANG = 0.175   # USD je 1 Mio Eingangstokens
KOSTEN_AUSGANG = 0.35    # USD je 1 Mio Ausgangstokens
KOSTEN_STOP = 1.00

# Relevanz-Suchbegriffe (case-insensitive)
RELEVANZ = ("topps", "shopify", "pokemoncenter", "snkrs", "nike", "amazon",
            "mediamarkt", "saturn", "smyths", "queue", "captcha", "proxy",
            "sperre", "konto", "drop")

# Gruesse / Hoeflichkeit (raus, wenn die Nachricht nur daraus besteht)
GRUESSE = {"hi", "hey", "hallo", "moin", "servus", "yo", "hello", "danke",
           "thx", "thanks", "ty", "dankeschön", "gg", "gl", "np", "gern",
           "gerne", "ok", "k", "gut", "nice", "cool", "lol", "lmao"}

BOT_MARKER = ("bot", "skyridge-bot", "discord", "moderator", "admin", "helper")

# Emoji (nicht alle, aber die haeufigen Discord-Ranges) entfernen
_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u200D\u2700-\u27BF\u2B00-\u2BFF\u2190-\u21FF\u2934-\u2935]",
    re.UNICODE)

_KOPF = re.compile(r"^\[(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2})\] (.+)$")

MONATE = ["", "Januar", "Februar", "März", "April", "Mai", "Juni",
          "Juli", "August", "September", "Oktober", "November", "Dezember"]


# ---------------------------------------------------------------- keys
def load_env() -> dict:
    """Gleicher Parser wie modules/shopify_core.load_env()."""
    out = {}
    if KEYS.exists():
        for line in KEYS.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


# ---------------------------------------------------------------- format
def _format_der_datei(txt: str) -> str | None:
    """Erkennt das Format an den ersten 30 Zeilen. -> 'kopf' | None."""
    kopf = 0
    for l in txt.splitlines()[:30]:
        if _KOPF.match(l):
            kopf += 1
    return "kopf" if kopf else None


def _channel_name(dateiname: str) -> str:
    base = Path(dateiname).stem
    m = re.search(r"\[(\d+)\]$", base)
    if m:
        base = base[: m.start()].strip()
    return base.replace("Skyridge - ", "").strip()


def parse_nachrichten(txt: str, fmt: str) -> list[dict]:
    """-> [{'ts','monat','name','text'}] fuer Format 'kopf'."""
    out = []
    if fmt != "kopf":
        return out
    current = None
    for l in txt.splitlines():
        m = _KOPF.match(l)
        if m:
            if current and current["text"].strip():
                out.append(current)
            tag, mon, jahr, std, min = int(m.group(1)), int(m.group(2)), \
                int(m.group(3)), m.group(4), m.group(5)
            current = {
                "ts": f"{jahr:04d}-{mon:02d}-{tag:02d} {std}:{min}",
                "monat": f"{MONATE[mon]} {jahr}",
                "name": m.group(6).strip(),
                "text": "",
            }
        else:
            if current is not None:
                current["text"] += ("\n" if current["text"] else "") + l
    if current and current["text"].strip():
        out.append(current)
    return out


# ---------------------------------------------------------------- vorfilter
def _ist_bot(name: str) -> bool:
    n = name.lower()
    return any(b in n for b in BOT_MARKER)


def _normalisiere(txt: str) -> str:
    t = _EMOJI.sub("", txt)
    return " ".join(t.split()).strip()


def _nur_link_oder_media(txt: str) -> bool:
    rest = re.sub(r"https?://\S+", "", txt)
    rest = re.sub(r"cdn\.discordapp\.com/\S+", "", rest)
    rest = re.sub(r"(gif|sticker|\.png|\.jpg|\.jpeg|\.webp|\.gifv|\.mp4)", " ", rest, flags=re.I)
    return not rest.strip()


def vorfilter(nachrichten: list[dict]) -> list[dict]:
    gesehen: set[str] = set()
    gut = []
    for n in nachrichten:
        name = n["name"]
        if _ist_bot(name):
            continue
        text = _normalisiere(n["text"])
        if len(text) < 15:
            continue
        if _nur_link_oder_media(text):
            continue
        low = text.lower()
        if not any(k in low for k in RELEVANZ):
            continue
        if low in GRUESSE or all(w.strip(".,!? ") in GRUESSE for w in low.split() if w.strip(".,!? ")):
            continue
        norm = f"{n['monat']}|{name.lower()}|{text}".lower()
        if norm in gesehen:
            continue
        gesehen.add(norm)
        gut.append({"monat": n["monat"], "name": name, "text": text})
    return gut


# ---------------------------------------------------------------- chunks
def stuecke(gut: list[dict]) -> list[str]:
    """Stuecke zu CHUNK_ZEICHEN. Eine Nachricht bleibt immer zusammen."""
    stuecke_liste = []
    aktuell = ""
    for n in gut:
        # anonymisieren: Name -> User (Personennamen weg, Datenschutz)
        zeile = f"{n['monat']} | User | {n['text']}"
        if len(zeile) > CHUNK_ZEICHEN:
            if aktuell:
                stuecke_liste.append(aktuell)
            aktuell = ""
            # sehr lange Einzelnachricht -> hart abschneiden
            for i in range(0, len(zeile), CHUNK_ZEICHEN):
                stuecke_liste.append(zeile[i:i + CHUNK_ZEICHEN])
            continue
        if aktuell and len(aktuell) + len(zeile) + 1 > CHUNK_ZEICHEN:
            stuecke_liste.append(aktuell)
            aktuell = ""
        aktuell += ("\n" if aktuell else "") + zeile
    if aktuell:
        stuecke_liste.append(aktuell)
    return stuecke_liste


ANWEISUNG = (
    "Du bist ein Analyzer fuer ein Restock-Bot. Aus dem folgenden Discord-Export "
    "extrahiere NUR programmrelevante Fakten zu Topps/PokemonCenter/SNKRS/Nike/Amazon/"
    "MediaMarkt/Saturn/Smyths/Shopify: Endpunkte, Selektoren, Queue-Verhalten, "
    "Captcha-Provider, Proxy-Erfahrungen, Limits, typische Fehler (Errorcodes, Sperren). "
    "Antwort nur als Stichpunktliste, maximal 60 Bullets, je Bullet ein Pflicht-Tag "
    "[Kanal|Monat]. Personennamen weglassen. Wiederholungen zusammenfassen und mit "
    "einem Zaehler (xN) versehen. Keine Meinungen, keine Gruesse, nur belegbare Fakten.\n\n"
)


# ---------------------------------------------------------------- api
def kosten(prompt: int, completion: int) -> float:
    return prompt / 1e6 * KOSTEN_EINGANG + completion / 1e6 * KOSTEN_AUSGANG


def send_stueck(key: str, model: str, text: str) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": ANWEISUNG + text}],
        "temperature": 0.2,
        "max_tokens": 4096,
    }
    req = urllib.request.Request(
        API_URL, data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------------------------------------------------------------- fortschritt
def _load_fortschritt() -> dict:
    if FORTSCHRITT.exists():
        try:
            return json.loads(FORTSCHRITT.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"erledigt": [], "kosten_usd": 0.0}


def _save_fortschritt(f: dict):
    FORTSCHRITT.write_text(json.dumps(f, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- haupt
def haupt() -> int:
    args = [a for a in sys.argv[1:]]

    if not args or any(a in ("-h", "--help") for a in args):
        print(__doc__)
        return 0

    only_vorfilter = "--vorfilter" in args
    only_stueck = None
    if "--stueck" in args:
        i = args.index("--stueck")
        only_stueck = int(args[i + 1])

    env = load_env()
    key = env.get("VENICE_API_KEY", "")
    model = env.get("VENICE_MODEL", "")

    if not only_vorfilter:
        if not key:
            print("FEHLER: VENICE_API_KEY fehlt (config/keys.env).", file=sys.stderr)
            return 2
        if not model:
            print("FEHLER: VENICE_MODEL fehlt (config/keys.env).", file=sys.stderr)
            return 2

    # --- 1) Quellen: nur neue .txt, Vorfilter immer frisch (Quellen koennen sich aendern)
    if VORGEFILTERT.exists():
        try:
            cache = json.loads(VORGEFILTERT.read_text(encoding="utf-8"))
        except Exception:
            cache = None
    else:
        cache = None

    quellen = sorted(DISCORD.glob("*.txt"))
    signatur = [p.name for p in quellen]
    if cache and cache.get("quellen") == signatur:
        gut = cache["gut"]
    else:
        alle = []
        for p in quellen:
            raw = p.read_bytes()
            for enc in ("utf-8", "utf-16-le", "latin-1"):
                try:
                    txt = raw.decode(enc)
                    break
                except Exception:
                    continue
            fmt = _format_der_datei(txt)
            if fmt is None:
                continue
            nachrichten = parse_nachrichten(txt, fmt)
            gefiltert = vorfilter(nachrichten)
            for n in gefiltert:
                n["kanal"] = _channel_name(p.name)
            alle.extend(gefiltert)
        gut = alle
        VORGEFILTERT.write_text(
            json.dumps({"quellen": signatur, "gut": gut},
                       ensure_ascii=False, indent=1), encoding="utf-8")

    chunks = stuecke(gut)
    n = len(chunks)
    zeichen = sum(len(c) for c in chunks)
    est_eingang = zeichen / 4  # ~4 Zeichen/Token
    est_ausgang = min(n, MAX_STUECKE_LAUF) * 1500
    est_usd = (est_eingang / 1e6 * KOSTEN_EINGANG) + (est_ausgang / 1e6 * KOSTEN_AUSGANG)

    print(f"Stuecke gesamt: {n}  (je bis {CHUNK_ZEICHEN} Zeichen, "
          f"max {MAX_STUECKE_LAUF}/Lauf)")
    print(f"Zeichen: {zeichen:,}  |  geschaetzte Kosten fuer den Lauf: "
          f"${est_usd:.3f}  (Eingang ~{est_eingang/1e6:.2f}M @ $0.175, "
          f"Ausgang ~{est_ausgang/1e6:.2f}M @ $0.35)")
    print(f"Kosten-Stopp bei ${KOSTEN_STOP:.2f}")

    if only_vorfilter:
        print(f"\nVorfilter fertig: {len(gut)} relevante Nachrichten "
              f"(quellen: {len(signatur)} Dateien). Kein API-Call.")
        return 0

    if only_stueck is not None:
        if only_stueck < 0 or only_stueck >= n:
            print(f"FEHLER: Stueck {only_stueck} gibt es nicht (0..{n-1}).",
                  file=sys.stderr)
            return 2
        res = send_stueck(key, model, chunks[only_stueck])
        k = kosten(res.get("usage", {}).get("prompt_tokens", 0),
                   res.get("usage", {}).get("completion_tokens", 0))
        antwort = res.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"\n=== Stueck {only_stueck}/{n} ===  ({k:.4f} USD)")
        print(antwort)
        print("\n--- fortfahren: --lauf | anderes Stueck: --stueck N ---")
        return 0

    # --- 2) Lauf: offene Stuecke, max 40, bis 1$ hart stoppen
    f = _load_fortschritt()
    offen = [i for i in range(n) if i not in f["erledigt"]][:MAX_STUECKE_LAUF]
    if not offen:
        print("Alles verarbeitet. Neuer Vorfilter noetig? (Quellen pruefen)")
        return 0

    with WISSEN.open("a", encoding="utf-8") as w:
        for i in offen:
            if f["kosten_usd"] >= KOSTEN_STOP:
                print(f"Hart-Stopp erreicht: kumuliert ${f['kosten_usd']:.2f} "
                      f">= ${KOSTEN_STOP:.2f}")
                break
            print(f"[{i}/{n}] Sende Stueck ...", flush=True)
            try:
                res = send_stueck(key, model, chunks[i])
            except Exception as exc:
                print(f"  FEHLER bei Stueck {i}: {type(exc).__name__}: {exc}")
                continue
            k = kosten(res.get("usage", {}).get("prompt_tokens", 0),
                       res.get("usage", {}).get("completion_tokens", 0))
            antwort = res.get("choices", [{}])[0].get("message", {}).get("content", "")
            w.write(f"\n\n## Stueck {i}\n{antwort}\n")
            w.flush()
            f["erledigt"].append(i)
            f["kosten_usd"] = round(f["kosten_usd"] + k, 6)
            _save_fortschritt(f)
            print(f"  ok, +{k:.4f} USD (kumuliert {f['kosten_usd']:.4f})")
            time.sleep(1)
    print("\nLaufende Gesamtkosten:", f"${f['kosten_usd']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(haupt())