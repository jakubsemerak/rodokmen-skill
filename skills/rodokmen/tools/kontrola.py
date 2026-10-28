#!/usr/bin/env python3
"""Kontrola konzistence dat rodokmenu. Spouštějte po každé větší změně a před stavbou webu.

Použití: kontrola.py
Vypíše CHYBY (rozbijí web nebo jsou věcně špatně) a UPOZORNĚNÍ (něco chybí, doplnit).
Návratový kód 1, pokud jsou chyby.
"""
import datetime, json, os, re, sys
for _s in (sys.stdout, sys.stderr):   # UTF-8 výstup i na Windows bez -X utf8 (cp1250 neumí třeba „→“)
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def jload(name, default):
    p = os.path.join(DATA, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default


def main():
    err, warn = [], []
    ns = {}
    try:
        exec(open(os.path.join(DATA, "osoby.py"), encoding="utf-8").read(), ns)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"CHYBA: data/osoby.py nejde načíst: {e}")
    P, SIDE, LINES, SAME = ns.get("P", {}), ns.get("SIDE", []), ns.get("LINES", {}), ns.get("SAME", {})
    zaz = jload("zaznamy.json", [])
    svazky, prep, hl = jload("svazky.json", {}), jload("prepisy.json", {}), jload("zvyrazneni.json", {})
    keys = [z.get("klic") for z in zaz]
    dup = {k for k in keys if keys.count(k) > 1}
    if dup:
        err.append(f"zápisy se stejným klíčem: {sorted(dup)}")
    keys = set(keys)

    if 1 not in P:
        err.append("chybí osoba 1 (výchozí osoba rodokmenu)")
    for k, p in P.items():
        if not isinstance(k, int) or k < 1:
            err.append(f"osoba {k!r}: číslo musí být kladné celé číslo")
            continue
        if k > 1 and k // 2 not in P and k not in SAME:
            warn.append(f"osoba {k} ({p.get('n')}): v rodokmenu chybí její dítě {k // 2} – je číslo správně?")
        st = p.get("st", "unk")
        if st not in ("doc", "prob", "fam", "mh", "unk"):
            err.append(f"osoba {k}: neznámý stav '{st}'")
        for r in p.get("r", []):
            if r not in keys:
                err.append(f"osoba {k} ({p.get('n')}) cituje neexistující zápis '{r}'")
        if st == "doc" and not p.get("r"):
            warn.append(f"osoba {k} ({p.get('n')}) je 'doc' (doloženo), ale necituje žádný zápis")
    for s in SIDE:
        if s.get("k") not in P:
            err.append(f"boční příbuzný '{s.get('n')}' patří k neexistující osobě {s.get('k')}")
        for r in s.get("r", []):
            if r not in keys:
                err.append(f"boční příbuzný '{s.get('n')}' cituje neexistující zápis '{r}'")
    R = ns.get("RODINA", {})
    odkazy = {v for o in R.values() for v in [o.get("otec"), o.get("matka"), *o.get("partner", [])] if isinstance(v, str)}
    for oid, o in R.items():
        kde = f"RODINA '{oid}' ({o.get('n')})"
        if not isinstance(o, dict) or not o.get("n"):
            err.append(f"{kde}: musí být dict(n=\"jméno\", …)")
            continue
        if o.get("sex") not in ("M", "F"):
            err.append(f"{kde}: chybí sex=\"M\" nebo \"F\"")
        if o.get("st", "fam") not in ("doc", "prob", "fam", "mh", "unk"):
            err.append(f"{kde}: neznámý stav '{o.get('st')}'")
        for pole in ("otec", "matka"):
            v = o.get(pole)
            if isinstance(v, str) and v not in R or v is not None and not isinstance(v, (str, int)):
                err.append(f"{kde}: {pole} {v!r} není v RODINA")
            elif isinstance(v, int) and v < 2:
                err.append(f"{kde}: {pole} {v} – číslo předka musí být aspoň 2")
        for v in o.get("partner", []):
            if isinstance(v, str) and v not in R or isinstance(v, int) and v not in P and v not in SAME or not isinstance(v, (str, int)):
                err.append(f"{kde}: partner {v!r} neexistuje")
        if not (o.get("otec") or o.get("matka") or o.get("partner")) and oid not in odkazy:
            err.append(f"{kde}: není s nikým spojen (chybí otec, matka i partner)")
        for r in o.get("r", []):
            if r not in keys:
                err.append(f"{kde} cituje neexistující zápis '{r}'")
    for a, c in SAME.items():
        seen = {a}
        while c in SAME and c not in seen:
            seen.add(c)
            c = SAME[c]
        if c in seen:
            err.append(f"SAME: {a} -> {SAME[a]} je v kruhu (alias vede zase na alias) – web ho vynechá")
        elif c not in P:
            err.append(f"SAME: {a} -> {SAME[a]}, ale osoba {c} neexistuje – web alias vynechá")
        elif P[c].get("n", "").startswith(("otec neuveden", "matka neuvedena")) or P[c].get("n") in ("", "?"):
            err.append(f"SAME: {a} -> {SAME[a]}, ale osoba {c} je „{P[c].get('n')}“ (neznámý rodič) – web alias vynechá")
        elif c != SAME[a]:
            warn.append(f"SAME: {a} -> {SAME[a]} je alias dalšího aliasu – zapiš rovnou {a}: {c}")
    for k in LINES:
        if k not in range(8, 16):
            err.append(f"LINES: rod {k} – rody mají čísla 8 až 15 (pradědečci a prababičky)")

    cited = {r for p in list(P.values()) + [o for o in R.values() if isinstance(o, dict)] for r in p.get("r", [])} | {r for s in SIDE for r in s.get("r", [])}
    for z in zaz:
        k = z.get("klic", "?")
        for f in ("klic", "druh", "datum", "nazev", "shrnuti"):
            if not z.get(f):
                err.append(f"zápis {k}: chybí pole '{f}'")
        if z.get("svazek") and z["svazek"] not in svazky:
            err.append(f"zápis {k}: svazek '{z['svazek']}' není v data/svazky.json")
        if z.get("ukazka"):   # vymyšlený zápis ukázkové rodiny – nemá snímek ani přepis
            continue
        if not z.get("odkaz") and not svazky.get(z.get("svazek", ""), {}).get("url"):
            warn.append(f"zápis {k}: chybí odkaz na snímek (pole 'odkaz')")
        if not os.path.exists(os.path.join(ROOT, "vyrezy", k + ".jpg")):
            warn.append(f"zápis {k}: chybí výřez vyrezy/{k}.jpg")
        elif k not in hl:
            warn.append(f"zápis {k}: chybí rámeček (tools/ramecek.py)")
        if k not in prep:
            warn.append(f"zápis {k}: chybí přepis a překlad v data/prepisy.json")
        if k not in cited:
            warn.append(f"zápis {k}: necituje ho žádná osoba (doplnit do 'r' u osoby nebo bočního příbuzného)")

    for name, e in jload("mista.json", {}).items():
        if "lat" not in e:
            warn.append(f"místo {name}: nemá souřadnice (spusťte tools/mista.py)")
        try:
            re.compile(e.get("re") or "")
        except re.error as ex:
            err.append(f"místo {name}: špatný výraz '{e.get('re')}': {ex}")

    mista_rx = []
    for n, e in jload("mista.json", {}).items():
        if "lat" not in e or e.get("hypoteza"):   # export je pro domov a stěhování nepoužije
            continue
        try:
            mista_rx.append(re.compile(e.get("re") or re.escape(n)))
        except re.error:
            pass
    for k, p in P.items():
        for f in p.get("f", []):
            m = re.match(r"\*\s*(?:asi\s+|kol\.\s*)?[\d./ ]*\d{4}\s+(.*)", f)
            slova = []
            for w in re.split(r"[\s,(]+", m.group(1)) if m else []:
                if not (w[:1].isupper() or slova and w in ("nad", "pod", "u")):
                    break
                slova.append(w)
            obec = " ".join(slova).removesuffix(" nad").removesuffix(" pod").removesuffix(" u")
            if obec and not any(rx.search(f) for rx in mista_rx):
                warn.append(f"osoba {k}: obec narození „{obec}“ není v data/mista.json – mapa ji neukáže "
                            f"(tools/mista.py pridej \"…\")")

    cfg = jload("web.json", {})
    if not (cfg.get("prihlaseni") or {}).get("odpoved") and not (cfg.get("prihlaseni") or {}).get("otevreny"):
        warn.append("web.json: není nastavená odpověď na přihlašovací otázku – nasazení webu skončí chybou")

    mapa = cfg.get("mapa") or {}
    if mapa.get("podklad", "osm") not in ("osm", "mapy.cz", "mapy.cz-outdoor"):
        warn.append(f"web.json: mapa.podklad „{mapa.get('podklad')}“ neznám – použij osm, mapy.cz nebo mapy.cz-outdoor")
    elif str(mapa.get("podklad", "")).startswith("mapy.cz") and not mapa.get("klic"):
        warn.append("web.json: mapa.podklad je mapy.cz, ale chybí mapa.klic (API klíč z developer.mapy.com) – mapa bude z OpenStreetMap")

    if re.search(r"Novák|Petrovi", json.dumps(cfg, ensure_ascii=False)) and "Novák" not in P.get(1, {}).get("n", ""):
        warn.append("web.json: jsou v něm ještě ukázkové texty (Novákovi) – nastav název, příběh a kontakt")

    # Citlivé věci, které jdou na web: všechny texty, které export_web.py publikuje.
    citlive = re.compile(r"sebevra|vzal[a]? si život|oběsil|zastřelil[a]? se|utopil[a]? se|alkohol|vězen|vězn|kriminál|odsouz|"
                         r"rozvod|rozvedl|rozveden|psychiatr|léčebn|duševn|depres|rakovin|nemanželsk|cizoložst|dluh|exekuc|"
                         r"interrupc|potrat", re.I)

    hranice = datetime.date.today().year - 100   # posledních ~100 let; staré matriční údaje (nemanželské dítě v 18. stol.) nevadí

    def recent(text):   # bez dat zápisu do deníku (2026-01-01)
        return any(int(y) >= hranice for y in re.findall(r"\b(19\d\d|20\d\d)\b(?!-\d\d-)", text))
    schvaleno = [s for s in (cfg.get("citlive_schvaleno") if isinstance(cfg.get("citlive_schvaleno"), list) else [])
                 if isinstance(s, str) and len(s.strip()) >= 3]

    def schvalene(text, m):   # uživatel to na web pustil: v web.json „citlive_schvaleno“ je úryvek textu s tímto slovem
        for s in schvaleno:
            i = text.find(s)
            while i >= 0:
                if i <= m.start() and m.end() <= i + len(s):
                    return True
                i = text.find(s, i + 1)
        return False

    def strings(x):
        if isinstance(x, str):
            return [x]
        vals = x.values() if isinstance(x, dict) else x if isinstance(x, (list, tuple)) else []
        return [s for v in vals for s in strings(v)]
    texty = [("ISSUES", " ".join(strings(i))) for i in ns.get("ISSUES", [])]
    for k, p in P.items():
        text = " ".join(p.get("f", [])) + " " + p.get("note", "")
        roky = [int(y) for y in re.findall(r"\b1[5-9]\d\d|20\d\d\b", p.get("y", "") + " " + text)]
        texty.append((f"osoba {k}", text + (f" {hranice}" if roky and min(roky) >= 1870 or k < 8 else "")))
    texty += [(f"boční příbuzný {s.get('n')}", s.get("n", "") + " " + s.get("t", "")) for s in SIDE]
    texty += [(f"RODINA {oid}", " ".join([o.get("n", ""), o.get("y", ""), *o.get("f", []), o.get("note", "")]))
              for oid, o in R.items() if isinstance(o, dict)]
    texty += [("HYPOTEZY", " ".join(strings(h))) for h in ns.get("HYPOTEZY", [])]
    texty += [(f"LINES {k}", " ".join(strings(v))) for k, v in LINES.items()]
    texty += [("web.json", t) for kk, v in cfg.items() if kk not in ("prihlaseni", "citlive_schvaleno", "mapa") for t in strings(v)]
    texty += [(f"zápis {z.get('klic')}", " ".join(strings([z.get("nazev"), z.get("shrnuti"), z.get("datum")]))) for z in zaz]
    texty += [(f"přepis {kk}", " ".join(strings(v.get("cs", "")))) for kk, v in prep.items() if isinstance(v, dict)]
    texty += [("dokumenty.json", " ".join(strings(d.get("popis", "")))) for d in jload("dokumenty.json", []) if isinstance(d, dict)]
    texty += [(f"místo {n}", e.get("foto_popis") or "") for n, e in jload("mista.json", {}).items() if isinstance(e, dict)]
    for f in ("zajimavosti.md", "pribeh.md", "research_log.md", "archivni_dotazy.md"):
        if os.path.exists(os.path.join(DATA, f)):
            md = re.sub(r"^.*<!--\s*soukrom[ée]\s*-->.*(?:\n|$)", "", open(os.path.join(DATA, f), encoding="utf-8").read(), flags=re.M)
            md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
            texty += [(f, odst) for odst in re.split(r"\n\s*\n|\n(?=\|)", md)]
    soukrome = {}
    for k, p in [*P.items(), *((f"RODINA {oid}", o) for oid, o in R.items())]:
        s = p.get("soukrome") or [] if isinstance(p, dict) else []
        for t in [s] if isinstance(s, str) else s:
            if isinstance(t, str) and len(t.strip()) >= 4:
                soukrome[t.strip()] = k
    for kde, text in texty:
        for t, k in soukrome.items():
            if t.lower() in text.lower():
                warn.append(f"SOUKROMÉ ({kde}): „{t}“ je v osoby.py u osoby {k} jako soukromé (soukrome), ale stejný text jde na web – smaž ho tam")
    for kde, text in texty:
        if not recent(text):
            continue
        m = next((m for m in citlive.finditer(text) if not schvalene(text, m)), None)
        if m:
            warn.append(f"CITLIVÉ ({kde}): „…{text[max(0, m.start() - 40):m.end() + 40].strip()}…“ – jde na web; "
                        f"zeptej se uživatele, jestli to tam smí být (reference/soukromi.md); když ano, "
                        f"přidej úryvek textu s tím slovem do web.json „citlive_schvaleno“")

    # Žijící lidé: na webu jen jméno a rok narození. Hlídá osoby v P a RODINA (ne boční příbuzné ani volný text).
    osobni = re.compile(r"\b\d{1,2}\.\s*\d{1,2}\.\s*\d{4}|\bč\.\s?p\.|\bčp\.|\b[A-ZÁ-Ž]\w*(?:ská|cká|ova|ní|ého) \d{1,3}(?:/\d+)?[a-z]?\b(?![.\d])|\bul\.|"
                        r"\+\d{3}\s?\d{3}\s?\d{3}\s?\d{3}|\b[2-79]\d{2} \d{3} \d{3}\b|[\w.+-]+@[\w-]+\.\w+|\btel\.")
    for k, p in [*P.items(), *((f"RODINA {oid}", o) for oid, o in R.items() if isinstance(o, dict))]:
        yv, note = (p.get("y") or "").strip(), p.get("note") or ""
        rok = re.search(r"\d{4}", yv)
        if not ("žijící" in note.lower() or (yv.startswith("*") or re.fullmatch(r"\d{4}\s*[–-]?", yv)) and rok and int(rok.group()) > hranice):
            continue
        m = osobni.search(" ".join(p.get("f", [])) + " | " + note)
        if m:
            warn.append(f"ŽIJÍCÍ osoba {k} ({p.get('n')}): „{m.group(0)}“ – u žijících jen jméno a rok narození "
                        f"(bez data, adresy, telefonu, e-mailu; reference/soukromi.md)")
        elif len(re.sub(r"Žijící – údaje jen základní\.?", "", note).strip()) > 80:
            warn.append(f"ŽIJÍCÍ osoba {k} ({p.get('n')}): dlouhá poznámka – u žijících jen jméno a rok narození "
                        f"(reference/soukromi.md)")

    if not os.path.exists(os.path.join(DATA, "pribeh.md")) and LINES:
        hlavni = min(LINES)
        n = max((k.bit_length() for k in P if k >= 8 and k >> (k.bit_length() - 4) == hlavni), default=0)
        if n >= 6:
            warn.append(f"rod {LINES[hlavni][0]} má už {n} generací – je čas napsat příběh rodu "
                        f"(data/pribeh.md, reference/pribehy.md); koncept nejdřív ukaž uživateli v chatu")

    log = os.path.join(DATA, "research_log.md")
    rows = sum(1 for l in open(log, encoding="utf-8") if re.match(r"^\| \d+ \|", l)) if os.path.exists(log) else 0
    print(f"{len(P)} osob, {len(zaz)} zápisů, {len(svazky)} svazků, {rows} řádků deníku")
    for e in err:
        print("CHYBA:", e)
    for w in warn:
        print("upozornění:", w)
    if not err and not warn:
        print("Vše v pořádku.")
    sys.exit(1 if err else 0)


if __name__ == "__main__":
    main()
