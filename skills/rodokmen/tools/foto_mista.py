#!/usr/bin/env python3
"""Fotky obcí a kostelů pro mapu na webu (Wikidata + Wikimedia Commons, s autorem a licencí).

Použití (z kořene projektu):
  foto_mista.py "Obec"          vypíše kandidáty: fotka obce, kostely v obci (Wikidata), jinak fotky do 1 km (Commons)
  foto_mista.py "Obec" <n>      stáhne kandidáta n do vyrezy/misto_<obec>.jpg a zapíše do data/mista.json
                                "foto" a "foto_popis" (popis s autorem a licencí – na webu se musí zobrazit)
Obec musí být v data/mista.json se souřadnicemi (tools/mista.py) – podle nich se vybere ta správná ze stejnojmenných.
Fotky z Commons jsou pod licencemi CC/PD: uvedení autora a licence je podmínkou, proto je popis vždy pod fotkou.
"""
import html, json, math, os, re, subprocess, sys, time, unicodedata, urllib.parse, urllib.request
for _s in (sys.stdout, sys.stderr):   # UTF-8 výstup i na Windows bez -X utf8 (cp1250 neumí třeba „→“)
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "rodokmen-skill/1.0 (family genealogy website; https://github.com/sarsonj/rodokmen-skill)"}
CACHE = os.path.join(ROOT, "pracovni", ".cache_foto")


def get(url, tries=4):
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                data = r.read()
            time.sleep(0.5)
            return data
        except OSError:
            if attempt == tries - 1:
                raise
            time.sleep(3 * (attempt + 1))   # Commons občas odpoví „too busy“


def sparql(q):
    url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": q, "format": "json"})
    return json.loads(get(url))["results"]["bindings"]


def dist(a, b):
    k = math.cos(math.radians(a[0]))
    return math.hypot(a[0] - b[0], (a[1] - b[1]) * k) * 111


def point(wkt):
    lon, lat = map(float, re.findall(r"[-\d.]+", wkt)[:2])
    return lat, lon


def commons_info(files):
    """Náhled 1600 px, autor a licence souborů z Commons."""
    out = {}
    for i in range(0, len(files), 20):
        par = {"action": "query", "format": "json", "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 1600,
               "iiextmetadatafilter": "LicenseShortName|Artist|Attribution", "titles": "|".join("File:" + f for f in files[i:i + 20])}
        d = json.loads(get("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(par)))
        for p in d.get("query", {}).get("pages", {}).values():
            ii = (p.get("imageinfo") or [{}])[0]
            meta = ii.get("extmetadata", {})
            credit = meta.get("Attribution", {}).get("value") or meta.get("Artist", {}).get("value", "")   # Attribution = text, který autor žádá
            artist = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(credit))).strip() or "neznámý autor"
            out[p["title"][5:]] = dict(url=ii.get("thumburl") or ii.get("url"), page=ii.get("descriptionurl", ""),
                                       license=meta.get("LicenseShortName", {}).get("value", "?"), artist=artist[:200])
    return out


def candidates(name, pos):
    found = sparql(f'''SELECT ?o ?c ?img ?lau WHERE {{ ?o rdfs:label {json.dumps(name, ensure_ascii=False)}@cs; wdt:P17 wd:Q213;
                       wdt:P625 ?c. OPTIONAL {{ ?o wdt:P18 ?img }} OPTIONAL {{ ?o wdt:P782 ?lau }} }}''')
    # stejnojmenné položky (nádraží, část obce) mívají stejné souřadnice – přednost má obec s kódem LAU
    found = sorted(found, key=lambda b: ("lau" not in b, round(dist(pos, point(b["c"]["value"])), 1)))
    cands = []
    if found and dist(pos, point(found[0]["c"]["value"])) < 5:
        obec = found[0]["o"]["value"].rsplit("/", 1)[-1]
        if found[0].get("img"):
            cands.append((name, found[0]["img"]["value"]))
        for b in sparql(f'''SELECT ?k ?kLabel ?img WHERE {{ ?k wdt:P131 wd:{obec}; wdt:P31/wdt:P279* wd:Q16970; wdt:P18 ?img.
                            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "cs,en". }} }}'''):
            cands.append((f"{name}, {b['kLabel']['value']}", b["img"]["value"]))
    cands = list({u: (p, u) for p, u in reversed(cands)}.values())[::-1]   # stejná fotka u obce i kostela jen jednou
    files = [urllib.parse.unquote(u.rsplit("/", 1)[-1]).replace("_", " ") for _, u in cands]
    if not files:   # obec bez fotky na Wikidatech: fotky z Commons do 1 km od středu obce
        par = {"action": "query", "format": "json", "list": "geosearch", "gscoord": f"{pos[0]}|{pos[1]}", "gsradius": 1000,
               "gsnamespace": 6, "gslimit": 10}
        geo = json.loads(get("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(par)))
        files = [g["title"][5:] for g in geo.get("query", {}).get("geosearch", [])]
        cands = [(name, f) for f in files]
    info = commons_info(files)
    return [dict(popis=p, soubor=f, **info[f]) for (p, _), f in zip(cands, files) if f in info and info[f]["url"]]


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    name = sys.argv[1]
    mista = json.load(open(os.path.join(ROOT, "data", "mista.json"), encoding="utf-8"))
    e = mista.get(name)
    if not e or "lat" not in e:
        sys.exit(f"Obec „{name}“ není v data/mista.json se souřadnicemi – nejdřív tools/mista.py pridej \"{name}\".")
    os.makedirs(CACHE, exist_ok=True)
    cache = os.path.join(CACHE, re.sub(r"\W+", "_", name) + ".json")
    cands = json.load(open(cache, encoding="utf-8")) if os.path.exists(cache) else candidates(name, (e["lat"], e["lon"]))
    with open(cache, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cands, f, ensure_ascii=False, indent=1)
    if len(sys.argv) < 3:
        if not cands:
            print("Nic nenalezeno. Zkus fotku od rodiny nebo eSbírky / Památkový katalog v prohlížeči (reference/portaly.md → Fotky).")
        for i, c in enumerate(cands, 1):
            print(f"{i}. {c['popis']} | {c['artist']}, {c['license']} | {c['page']}")
        return
    c = cands[int(sys.argv[2]) - 1]
    slug = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    key = "misto_" + re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
    path = os.path.join(ROOT, "vyrezy", key + ".jpg")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(get(c["url"]))
    popis = f"{c['popis']}. Foto: {c['artist']}, {c['license']}, Wikimedia Commons."
    tmp = os.path.join(ROOT, "pracovni", "foto_misto.json")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"foto": key, "foto_popis": popis, "foto_zdroj": c["page"]}, f, ensure_ascii=False)
    subprocess.run([sys.executable, "-I", "-X", "utf8", os.path.join(ROOT, "tools", "zapis.py"), "mista", name, tmp, "--sloucit"], check=True)
    print(f"{path}\n{popis}\nPodívej se na fotku, než ji necháš na webu (je to opravdu ta obec / kostel?).")


if __name__ == "__main__":
    main()
