#!/usr/bin/env python3
"""Export dat rodokmenu (data/*) do webu ve složce web/.

Čte data/osoby.py, data/zaznamy.json, data/svazky.json, data/prepisy.json, data/zvyrazneni.json,
data/mista.json, data/web.json, data/dokumenty.json a markdownové poznámky. Zapisuje
web/src/data/site.json, web/src/generated/*, web/public/{img,zdroje}, web/public/prihlaseni.html,
web/public/data/rodokmen.json, web/nginx.conf, web/netlify/edge-functions/brana.js, web/functions/_middleware.js
a vystupy/rodokmen.sqlite (i se soukromými údaji – jen pro dotazy, nenasazuje se).

Spouští se z web/ příkazem `npm run data` (nebo přímo `python3 -I tools/export_web.py`, na Windows `python -I -X utf8 …`).
"""
import hashlib, html, json, os, re, shutil, sqlite3, subprocess, sys, unicodedata
for _s in (sys.stdout, sys.stderr):   # UTF-8 výstup i na Windows bez -X utf8 (cp1250 neumí třeba „→“)
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
DATA = os.path.join(ROOT, "data")
WEB = os.path.join(ROOT, "web")
VYREZY = os.path.join(ROOT, "vyrezy")      # výřezy zápisů a dokumentů (asi 1800 px) – zobrazují se na webu
ZDROJE = os.path.join(ROOT, "zdroje")      # tytéž výřezy v plném rozlišení (proklik)

LINE_COLORS = {8: "#EFB45F", 9: "#F09A78", 10: "#E58AA6", 11: "#B99AE0",
               12: "#86B8E8", 13: "#6FCBB9", 14: "#9CD17A", 15: "#D3D46A"}
STATUS = {"doc": "doloženo matrikou", "prob": "pravděpodobné", "fam": "údaj od rodiny",
          "mh": "jen z cizího rodokmenu", "unk": "neznámé"}
SIDE_KIND = {"bratr": "sib", "sestra": "sib", "manžel": "spouse", "manželka": "spouse", "syn": "child", "dcera": "child"}
SIB_STATUS = {"hotovo": "done", "částečně": "partial"}
KINDS = {"N": "křest / narození", "O": "sňatek", "Z": "úmrtí", "I": "rejstřík", "S": "sčítání lidu", "J": "jiný pramen"}


def jload(name, default):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_people():
    ns = {}
    exec(open(os.path.join(DATA, "osoby.py"), encoding="utf-8").read(), ns)
    for name, default in (("P", {}), ("SIDE", []), ("LINES", {}), ("ISSUES", []), ("HYPOTEZY", []), ("SAME", {}), ("RODINA", {})):
        ns.setdefault(name, default)
    return ns


def record_rows():
    svazky = jload("svazky.json", {})
    rows = []
    for z in jload("zaznamy.json", []):
        sv = svazky.get(z.get("svazek", ""), {})
        key = z["klic"]
        rows.append(dict(
            key=key, kind=z.get("druh", "J"), date=z.get("datum", ""), title=z.get("nazev", key),
            summary=z.get("shrnuti", ""), scan=z.get("snimek", ""),
            archive=sv.get("archiv", ""), volume=sv.get("svazek", ""), vdesc=sv.get("popis", ""),
            portal=sv.get("portal", "archivu"), url=z.get("odkaz") or sv.get("url", ""),
            img=os.path.exists(os.path.join(VYREZY, key + ".jpg")),
            full=os.path.exists(os.path.join(ZDROJE, key + ".jpg")),
        ))
    return rows


def strip_comments(md):
    """Poznámky <!-- … --> v markdownu jsou pro Clauda, ne pro web; řádek s <!-- soukromé --> nejde na web celý."""
    md = re.sub(r"^.*<!--\s*soukrom[ée]\s*-->.*(?:\n|$)", "", md, flags=re.M)
    return re.sub(r"<!--.*?-->\n?", "", md, flags=re.S)


def slugify(text):
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def norm_answer(text):
    """Stejná normalizace jako v prihlaseni.html: bez diakritiky, malá písmena, jen a-z0-9."""
    t = unicodedata.normalize("NFD", text)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]", "", t)


def years(y):
    y = (y or "").strip()
    ys = re.findall(r"\d{4}", y)
    if not ys:
        return ""
    approx = "≈" if re.match(r"^(asi|≈)", y) else ""
    head, dash, tail = y.partition("–")
    if y.startswith(("?", "†")) or (dash and not re.search(r"\d", head)) or re.match(r"po\b", y):
        # neznámé narození: ukázat jen úmrtí („? – před 1743“ → „† před 1743“, „– po 1921“ → „žil 1921“)
        if re.search(r"\bpo\b", tail or y):
            return "žil " + ys[-1]
        return "† " + ("před " if "před" in y else "") + ys[-1]
    if y.startswith("*"):
        return "* " + ys[0]
    if len(ys) == 1:
        return approx + ys[0]
    second = "?" if "před" in tail else ("po " if re.search(r"\bpo\b", tail) else "") + \
        ("≈" if re.search(r"(asi|≈)", tail) else "") + ys[-1]
    return f"{approx}{ys[0]}–{second}"


def gen(k):
    return k.bit_length() - 1


def relation(k):
    g, male = gen(k), (k % 2 == 0)
    if g == 0:
        return "výchozí osoba rodokmenu"
    if g == 1:
        return "otec" if male else "matka"
    base = "dědeček" if male else "babička"
    if g <= 5:
        return "pra" * (g - 2) + base
    return f"{'předek' if male else 'předkyně'} v {g}. generaci ({'pra' * (g - 2)}{base})"


def placeholder(p):
    return p["n"].startswith(("otec neuveden", "matka neuvedena")) or p["n"] in ("", "?")


def magick_bin():   # ImageMagick 7 (magick), jinak 6 (convert) – ten ale ne na Windows, tam je convert.exe jiný program
    return shutil.which("magick") or (os.name != "nt" and shutil.which("convert")) or None


def size(path):
    w, h = subprocess.run([magick_bin(), path + "[0]", "-format", "%w %h", "info:"],
                          capture_output=True, text=True, check=True).stdout.split()
    return int(w), int(h)


def draw_boxes(src, dst, boxes, small):
    """Kopie výřezu v plném rozlišení s nakreslenými rámečky (pokud má stejný poměr stran jako webový výřez,
    na kterém se rámečky měřily). Vrací False, pak se kopíruje bez rámečků."""
    if not os.path.exists(small) or not magick_bin():
        return False
    (W, H), (w, h) = size(src), size(small)
    if abs(W / H - w / h) > 0.015 * (w / h):
        return False
    sw = max(4, round(W / 450))
    cmd = [magick_bin(), src, "-fill", "none", "-stroke", "#d7302a", "-strokewidth", str(sw)]
    for x0, y0, x1, y1 in boxes:
        cmd += ["-draw", f"rectangle {x0 * W:.0f},{y0 * H:.0f},{x1 * W:.0f},{y1 * H:.0f}"]
    subprocess.run(cmd + ["-quality", "90", dst], check=True)
    return True


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def login_files(cfg):
    """Přihlašovací brána: otázka na webu, na serveru (nginx i Netlify) jen otisk odpovědi (SHA-256).
    Stejný otisk spočítá přihlašovací stránka a uloží ho do cookie – samotná odpověď se nikam neukládá."""
    login = cfg.get("prihlaseni") or {}
    answer = norm_answer(login.get("odpoved", ""))
    tpl = open(os.path.join(WEB, "prihlaseni.sablona.html"), encoding="utf-8").read()
    if "rodokmen:" not in tpl:   # stará šablona (do 0.4.0) ukládá do cookie odpověď – s novou bránou by se nikdo nepřihlásil
        sys.exit("CHYBA: web/ má starou šablonu přihlášení. Aktualizujte projekt: python3 -I <skill>/tools/novy_projekt.py <složka projektu>")
    contact = cfg.get("kontakt") or {}
    hint = ""
    if contact.get("email"):
        hint = (f'Neznáte odpověď? Napište {html.escape(contact.get("jmeno", ""))} na '
                f'<a href="mailto:{html.escape(contact["email"])}">{html.escape(contact["email"])}</a>.')
    page = (tpl.replace("{{NAZEV}}", html.escape(cfg.get("nazev", "Rodokmen")))
               .replace("{{UVOD}}", html.escape(login.get("uvod", "Tenhle web je jen pro rodinu a příbuzné.")))
               .replace("{{OTAZKA}}", html.escape(login.get("otazka", "Odpověď na rodinnou otázku")))
               .replace("{{TYP}}", "password" if login.get("skryt") else "text")
               .replace("{{NAPOVEDA}}", hint))
    write(os.path.join(WEB, "public", "prihlaseni.html"), page)

    edge = os.path.join(WEB, "netlify", "edge-functions", "brana.js")
    cf = os.path.join(WEB, "functions", "_middleware.js")   # Cloudflare Pages
    if answer:
        digest = hashlib.sha256(("rodokmen:" + answer).encode()).hexdigest()
        nginx_map = f'  "{digest}" 1;'
        write(edge, open(os.path.join(WEB, "netlify", "brana.sablona.js"), encoding="utf-8").read().replace("{{HASH}}", digest))
        write(cf, open(os.path.join(WEB, "cloudflare", "brana.sablona.js"), encoding="utf-8").read().replace("{{HASH}}", digest))
    else:   # bez přihlášení – web je otevřený
        nginx_map = "  default 1;"
        for f in (edge, cf):
            if os.path.exists(f):
                os.remove(f)
    nginx = open(os.path.join(WEB, "nginx.sablona.conf"), encoding="utf-8").read().replace("{{ODPOVED}}", nginx_map)
    write(os.path.join(WEB, "nginx.conf"), nginx)
    return bool(answer)


def write_db(P, slugs, people, families, events, moves, R, others):
    """Celá data i se soukromými poznámkami pro dotazy (agent, rodina) – vystupy/ se nikam nenasazuje."""
    path = os.path.join(ROOT, "vystupy", "rodokmen.sqlite")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    db = sqlite3.connect(path)
    db.executescript("""
CREATE TABLE osoby (k INTEGER PRIMARY KEY, slug TEXT, jmeno TEXT, roky TEXT, stav TEXT, generace INTEGER, pohlavi TEXT,
  rod INTEGER, domov TEXT, otec INTEGER, matka INTEGER, zapisy TEXT, poznamka TEXT, soukrome TEXT);
CREATE TABLE rodina (id TEXT PRIMARY KEY, jmeno TEXT, roky TEXT, stav TEXT, pohlavi TEXT, otec TEXT, matka TEXT, partneri TEXT,
  zapisy TEXT, fakta TEXT, poznamka TEXT, soukrome TEXT);
CREATE TABLE fakta (osoba INTEGER, poradi INTEGER, druh TEXT, rok INTEGER, text TEXT);
CREATE TABLE udalosti (rok INTEGER, datum TEXT, druh TEXT, misto TEXT, odkud TEXT, popis TEXT, osoby TEXT);
CREATE TABLE rodiny (id TEXT PRIMARY KEY, otec TEXT, matka TEXT, deti TEXT, snatek TEXT, rod INTEGER, generace INTEGER);
CREATE TABLE zaznamy (klic TEXT PRIMARY KEY, druh TEXT, datum TEXT, nazev TEXT, shrnuti TEXT, svazek TEXT, snimek TEXT, odkaz TEXT, osoby TEXT);
CREATE TABLE svazky (id TEXT PRIMARY KEY, archiv TEXT, svazek TEXT, popis TEXT, portal TEXT, url TEXT);
CREATE TABLE prepisy (klic TEXT PRIMARY KEY, orig TEXT, cs TEXT);
CREATE TABLE mista (nazev TEXT PRIMARY KEY, lat REAL, lon REAL, re TEXT, hypoteza INTEGER, rod INTEGER);
CREATE TABLE stehovani (odkud TEXT, kam TEXT, rod INTEGER, rok INTEGER, osoby TEXT);
""")
    js = lambda v: json.dumps(v, ensure_ascii=False)
    by_k = {p["k"]: p for p in people.values()}
    for k, p in sorted(P.items()):
        if not isinstance(k, int):
            continue
        w = by_k.get(k, {})
        soukr = p.get("soukrome") or []
        db.execute("INSERT INTO osoby VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            k, slugs.get(k), p.get("n", ""), p.get("y", ""), p.get("st", "unk"), gen(k), w.get("sex"), w.get("line"), w.get("home"),
            2 * k if 2 * k in P else None, 2 * k + 1 if 2 * k + 1 in P else None, js(p.get("r", [])), p.get("note", ""),
            js(soukr if isinstance(soukr, list) else [soukr])))
        for i, f in enumerate(p.get("f", [])):
            y = re.search(r"\b(1[4-9]\d\d|20\d\d)\b", f)
            db.execute("INSERT INTO fakta VALUES (?,?,?,?,?)", (k, i, f[:1] if f[:1] in "*×†" else "", int(y.group()) if y else None, f))
    for o in others:
        soukr = R[o["id"][2:]].get("soukrome") or []
        db.execute("INSERT INTO rodina VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
            o["id"], o["name"], o["y"], o["st"], o["sex"], o["father"], o["mother"], js(o["partners"]), js(R[o["id"][2:]].get("r", [])),
            js(o["facts"]), o["note"], js(soukr if isinstance(soukr, list) else [soukr])))
    db.executemany("INSERT INTO udalosti VALUES (?,?,?,?,?,?,?)",
                   [(e["year"], e["date"], e["kind"], e["place"], e.get("src"), e["label"], js(e["people"])) for e in events])
    db.executemany("INSERT INTO rodiny VALUES (?,?,?,?,?,?,?)",
                   [(f["id"], f["father"], f["mother"], js(f["children"]), js(f["marriage"]), f["line"], f["gen"]) for f in families.values()])
    refs = {}
    for p in people.values():
        for r in p["records"]:
            refs.setdefault(r, []).append(p["slug"])
    db.executemany("INSERT OR REPLACE INTO zaznamy VALUES (?,?,?,?,?,?,?,?,?)",
                   [(z.get("klic"), z.get("druh"), z.get("datum"), z.get("nazev"), z.get("shrnuti"), z.get("svazek"), z.get("snimek"),
                     z.get("odkaz"), js(refs.get(z.get("klic"), []))) for z in jload("zaznamy.json", [])])
    db.executemany("INSERT INTO svazky VALUES (?,?,?,?,?,?)", [(k, v.get("archiv"), v.get("svazek"), v.get("popis"), v.get("portal"), v.get("url"))
                                                           for k, v in jload("svazky.json", {}).items()])
    db.executemany("INSERT INTO prepisy VALUES (?,?,?)", [(k, js(v.get("orig", "")) if not isinstance(v.get("orig", ""), str) else v.get("orig", ""),
                                                           v.get("cs", "") if isinstance(v.get("cs", ""), str) else js(v.get("cs")))
                                                          for k, v in jload("prepisy.json", {}).items() if isinstance(v, dict)])
    db.executemany("INSERT INTO mista VALUES (?,?,?,?,?,?)", [(n, e.get("lat"), e.get("lon"), e.get("re"), int(bool(e.get("hypoteza"))), e.get("rod"))
                                                          for n, e in jload("mista.json", {}).items()])
    db.executemany("INSERT INTO stehovani VALUES (?,?,?,?,?)", [(m["src"], m["dst"], m["line"], m.get("year"), js(m["people"])) for m in moves])
    db.commit()
    db.close()


def main():
    ns = load_people()
    P, LINES, SIDE, ISSUES = ns["P"], ns["LINES"], ns["SIDE"], ns["ISSUES"]
    if 1 not in P:
        sys.exit("V data/osoby.py chybí výchozí osoba (číslo 1).")
    SAME = {}                               # alias Kekulé → kanonické Kekulé (předek v rodokmenu vícekrát)
    for a, c in ns["SAME"].items():
        seen = {a}
        while c in ns["SAME"] and c not in seen:   # řetěz 131 → 130 → 104
            seen.add(c)
            c = ns["SAME"][c]
        if c in seen or c not in P or placeholder(P[c]):
            print(f"POZOR: SAME {a}: {ns['SAME'][a]} vynechávám – nevede na skutečnou osobu (viz tools/kontrola.py)")
        else:
            SAME[a] = c
    cfg = jload("web.json", {})
    heslo = jload("tajne.json", {}).get("heslo")
    if heslo:
        cfg["prihlaseni"] = {"skryt": True, **(cfg.get("prihlaseni") or {}), "odpoved": heslo}
    login = cfg.get("prihlaseni") or {}
    if "--nasazeni" in sys.argv and not norm_answer(login.get("odpoved", "")) and not login.get("otevreny"):
        sys.exit("CHYBA: v data/web.json není odpověď na přihlašovací otázku – web by byl otevřený komukoli.\n"
                 "Nastavte heslo v data/tajne.json ({\"heslo\": \"…\"}) nebo prihlaseni.odpoved, nebo (jen když to opravdu chcete) prihlaseni.otevreny: true.")
    docs_cfg = jload("dokumenty.json", [])
    recs = {r["key"]: r for r in record_rows()}

    slugs, used = {}, set()
    for k in sorted(P):
        p = P[k]
        if placeholder(p) or k in SAME:
            continue
        yv = (p.get("y") or "").strip()
        ys = [] if yv.startswith(("?", "†")) else re.findall(r"\d{4}", yv)   # rok úmrtí do adresy nedávat
        s = slugify(p["n"] + (" " + ys[0] if ys else ""))
        if s in used or not s:
            s = f"{s}-{k}"
        used.add(s)
        slugs[k] = s
    for a, c in SAME.items():
        slugs[a] = slugs[c]
    aliases_of = {}
    for a, c in SAME.items():
        aliases_of.setdefault(c, []).append(a)

    def line_of(k):
        g = gen(k)
        return k >> (g - 3) if g >= 3 else None

    people = {}
    for k, p in sorted(P.items()):
        if k not in slugs or k in SAME:
            continue
        path, c = [], k
        while c >= 1:
            path.append(slugs.get(c))
            c //= 2
        people[slugs[k]] = dict(
            k=k, slug=slugs[k], name=p["n"], y=p.get("y", ""), years=years(p.get("y")), st=p.get("st", "unk"),
            status=STATUS.get(p.get("st"), ""), gen=gen(k), sex="M" if k == 1 and p.get("sex", "M") == "M" or k > 1 and k % 2 == 0 else "F",
            rel=relation(k), line=line_of(k), facts=p.get("f", []), note=p.get("note", ""), records=[r for r in p.get("r", []) if r in recs],
            father=slugs.get(2 * k), mother=slugs.get(2 * k + 1),
            fatherUnknown=(2 * k in P and placeholder(P[2 * k])), motherUnknown=(2 * k + 1 in P and placeholder(P[2 * k + 1])),
            child=slugs.get(k // 2) if k > 1 else None, spouse=slugs.get(k ^ 1) if k > 1 else None,
            family=None, ownFamily=None, path=path,
            side=[dict(name=s["n"], text=s["t"], records=[r for r in s.get("r", []) if r in recs], rel=s.get("v") or "příbuzný",
                       years=years(s.get("y")), kind=SIDE_KIND.get((s.get("v") or "").lower(), "other")) for s in SIDE if s["k"] == k],
            sibStatus=SIB_STATUS.get(p.get("sour"), "none"),
            docs=[dict(img=d["img"], caption=d["popis"]) for d in docs_cfg if k in d.get("osoby", [])],
            photo=next((dict(img=d["img"], caption=d["popis"]) for d in docs_cfg if d.get("portret") and k in d.get("osoby", [])
                        and os.path.exists(os.path.join(VYREZY, d["img"] + ".jpg"))), None),
            children=[slugs[c] for c in [k // 2] + [a // 2 for a in aliases_of.get(k, [])] if k > 1 and c in slugs],
            also=[dict(k=a, rel=relation(a), line=line_of(a), child=slugs.get(a // 2)) for a in aliases_of.get(k, [])],
        )
        if aliases_of.get(k):
            for a in aliases_of[k]:
                people[slugs[k]]["records"] = list(dict.fromkeys(people[slugs[k]]["records"] + [r for r in P.get(a, {}).get("r", []) if r in recs]))
            people[slugs[k]]["facts"] = [f for f in people[slugs[k]]["facts"] if not f.startswith("TÁŽ OSOBA")]

    # RODINA: osoby mimo přímou linii. Odkazy: "k12" přímý předek, "o:zkratka" osoba z RODINA, "?12" neznámý předek na místě 12.
    R = {oid: o for oid, o in ns["RODINA"].items() if isinstance(o, dict) and o.get("n")}

    def ref(v):
        if isinstance(v, int) and not isinstance(v, bool):
            v = SAME.get(v, v)
            return f"k{v}" if v in slugs else f"?{v}"
        return f"o:{v}" if isinstance(v, str) and v in R else None

    others = [dict(id=f"o:{oid}", name=o["n"], y=o.get("y", ""), years=years(o.get("y")), sex=o.get("sex", ""),
                   st=o.get("st", "fam"), status=STATUS.get(o.get("st", "fam"), ""), father=ref(o.get("otec")), mother=ref(o.get("matka")),
                   partners=[x for x in map(ref, o.get("partner", [])) if x], facts=o.get("f", []), note=o.get("note", ""),
                   records=[r for r in o.get("r", []) if r in recs]) for oid, o in R.items()]
    for pp in people.values():   # na stránce osoby a rodiny jako příbuzní
        me, k = f"k{pp['k']}", pp["k"]
        birth = (ref(2 * k), ref(2 * k + 1))
        for o in others:
            par = (o["father"], o["mother"])
            if par == birth:
                rel = "bratr" if o["sex"] == "M" else "sestra"
            elif me in par:
                rel = "syn" if o["sex"] == "M" else "dcera"
            elif me in o["partners"] or any(me in (c["father"], c["mother"]) and o["id"] in (c["father"], c["mother"]) for c in others):
                rel = "manžel" if o["sex"] == "M" else "manželka"
            elif any(b and not b.startswith("?") and b in par for b in birth):
                rel = "nevlastní bratr" if o["sex"] == "M" else "nevlastní sestra"
            else:
                continue
            pp["side"].append(dict(name=o["name"], text=o["note"] or "; ".join(o["facts"]), records=o["records"], rel=rel,
                                   years=o["years"], kind=SIDE_KIND.get(rel, "other"), id=o["id"]))

    def surname(k):   # bez „(?)“; prázdné jméno → ""
        w = re.sub(r"\([^)]*\)|\?", " ", P.get(k, {}).get("n", "")).split()
        return w[-1] if w and not placeholder(P[k]) else ""

    def year1(x):
        return next(iter(re.findall(r"\d{4}", x)), None)

    families = {}
    for k in sorted(P):
        f, m = 2 * k, 2 * k + 1
        if k not in slugs or k in SAME or (f not in slugs and m not in slugs):
            continue
        fs, ms = slugs.get(f), slugs.get(m)
        fid = "-a-".join(x for x in (fs, ms) if x) if fs and ms else (fs or ms) + "-rodina"
        ff, mf = ([x for x in P.get(c, {}).get("f", []) if x.startswith("×")] for c in (f, m))
        sf, sm = surname(f)[:5], surname(m)[:5]
        both = [x for x in ff if any(year1(x) and year1(x) == year1(y) for y in mf)]   # stejný rok sňatku u otce i matky
        marriage = [x for x in ff + mf if sm and sm in x] or [x for x in mf if sf and sf in x] or both or ff + mf
        frec = P.get(f, {}).get("r", []) + P.get(m, {}).get("r", [])
        child_rec = [r for r in P[k].get("r", []) if r in recs and recs[r]["kind"] == "N"]
        rlist = [r for r in dict.fromkeys(frec) if r in recs and recs[r]["kind"] == "O"] + child_rec
        if fid in families:   # stejný pár potkán dvakrát (předek v rodokmenu vícekrát) – jedna rodina, víc dětí
            fam = families[fid]
            fam["children"].append(slugs[k])
            fam["records"] = list(dict.fromkeys(fam["records"] + rlist))
            fam["side"] += people[slugs[k]]["side"]
        else:
            families[fid] = dict(id=fid, father=fs, mother=ms, fatherUnknown=f in P and placeholder(P[f]),
                                 child=slugs[k], children=[slugs[k]], marriage=marriage, records=rlist,
                                 line=line_of(f) if f in P else line_of(m), gen=gen(f), side=list(people[slugs[k]]["side"]))
        people[slugs[k]]["family"] = fid
        for x in (fs, ms):
            if x:
                people[x]["ownFamily"] = fid

    refs = {}
    for s, p in people.items():
        for r in p["records"] + [r for e in p["side"] for r in e["records"]]:
            refs.setdefault(r, []).append(s)
    hl = jload("zvyrazneni.json", {})
    prep = jload("prepisy.json", {})
    records = []
    for key, r in recs.items():
        r = dict(r)
        r["boxes"] = hl.get(key, {}).get("boxes", [])
        tr = prep.get(key, {})
        r["orig"], r["cs"] = tr.get("orig", ""), tr.get("cs", "")
        r["kindName"] = KINDS.get(r["kind"], r["kind"])
        r["people"] = list(dict.fromkeys(refs.get(key, [])))
        records.append(r)

    lines = {}
    for k, (name, desc) in sorted(LINES.items()):
        if k not in LINE_COLORS:
            continue
        members = [(p["k"], p) for p in people.values() if p["line"] == k]
        members += [(a["k"], p) for p in people.values() for a in p["also"] if a["line"] == k]
        members.sort(key=lambda x: x[0])
        lines[slugify(name)] = dict(k=k, slug=slugify(name), name=name, desc=desc, color=LINE_COLORS[k],
                                    root=slugs.get(k), people=[p["slug"] for _, p in members],
                                    gens={p["slug"]: gen(kk) for kk, p in members})
    lines = {s: l for s, l in lines.items() if l["root"]}
    for p in people.values():
        p["lineSlug"] = next((l["slug"] for l in lines.values() if l["k"] == p["line"]), None)

    mista = jload("mista.json", {})
    place_rx = [(n, re.compile(e.get("re") or re.escape(n))) for n, e in mista.items() if "lat" in e and not e.get("hypoteza")]

    def home(facts):
        """Obec, kde osoba žila: první místo z mista.json v narození, jinak ve volném textu (bydliště, řemeslo), sňatku, úmrtí."""
        for kind in ("*", "", "×", "†"):
            for f in facts:
                if (f[:1] if f[:1] in "*×†" else "") != kind:
                    continue
                hits = [(m.start(), m.start() - m.end(), n) for n, rx in place_rx for m in [rx.search(f)] if m]
                if hits:
                    return min(hits)[2]
        return None

    for p in people.values():
        p["home"] = home(p["facts"])
    moves = {}
    for p in people.values():
        for c in p["children"]:
            src, dst = p["home"], people[c]["home"]
            if src and dst and src != dst:
                moves.setdefault((src, dst, p["line"] or 0), []).append(p["slug"])
    moves = [dict(src=s, dst=d, line=l, people=v) for (s, d, l), v in moves.items()]

    def place_of(f):
        hits = [(m.start(), m.start() - m.end(), n) for n, rx in place_rx for m in [rx.search(f)] if m]
        return min(hits)[2] if hits else None

    events, wed = [], {}
    for p in sorted(people.values(), key=lambda p: p["k"]):
        for f in p["facts"]:
            m = re.match(r"([*×†])\s*((?:asi\s+|kol\.\s*|před\s+|po\s+)?[\d./ ]*?\b(1[4-9]\d\d|20\d\d)\b)", f)
            if not m:
                continue
            kind = {"*": "narozeni", "×": "snatek", "†": "umrti"}[m.group(1)]
            ev = dict(year=int(m.group(3)), date=m.group(2).strip(), kind=kind, people=[p["slug"]],
                      place=place_of(f), label=f"{m.group(1)} {p['name']}")
            if kind == "snatek":   # sňatek u manžela i manželky jen jednou
                pair = wed.get((ev["year"], p["spouse"]))
                if pair and p["slug"] not in pair["people"]:
                    pair["people"].append(p["slug"])
                    pair["label"] += f" a {p['name']}"
                    pair["place"] = pair["place"] or ev["place"]
                    continue
                wed[(ev["year"], p["slug"])] = ev
            events.append(ev)
    born = {e["people"][0]: e["year"] for e in events if e["kind"] == "narozeni"}
    for mv in moves:
        ys = [born[c] for s in mv["people"] for c in people[s]["children"] if c in born]
        mv["year"] = min(ys) if ys else None
        if ys:
            events.append(dict(year=mv["year"], date="", kind="stehovani", people=mv["people"], place=mv["dst"], src=mv["src"],
                               label=f"{mv['src']} → {mv['dst']}"))
    events.sort(key=lambda e: (e["year"], ["narozeni", "snatek", "stehovani", "umrti"].index(e["kind"])))
    coords = {n: [mista[n]["lat"], mista[n]["lon"]] for n, _ in place_rx}

    places = []
    for name, e in mista.items():
        if "lat" not in e:
            continue
        rx = re.compile(e.get("re") or re.escape(name))
        hits = [p for p in people.values() if rx.search(" ".join(p["facts"]))]
        byline = {}
        for p in sorted(hits, key=lambda p: p["k"]):
            byline.setdefault(p["line"] or 0, []).append(p["slug"])
        if e.get("hypoteza"):
            byline = {e.get("rod", 0): []}
        if not byline:
            continue
        yrs = [int(y) for p in hits for y in re.findall(r"\b1[4-9]\d\d\b", p["y"] or "")]
        foto = e.get("foto") if e.get("foto") and os.path.exists(os.path.join(VYREZY, e["foto"] + ".jpg")) else None
        places.append(dict(name=name, lat=e["lat"], lon=e["lon"], lines=[dict(k=k, people=v) for k, v in sorted(byline.items())],
                           years=[min(yrs), max(yrs)] if yrs else None, hypothesis=bool(e.get("hypoteza")),
                           photo=foto, photoCaption=e.get("foto_popis", "") if foto else "",
                           photoSource=e.get("foto_zdroj", "") if foto and str(e.get("foto_zdroj", "")).startswith("https://") else ""))

    known = [p for p in people.values() if p["k"] > 1]
    stats = dict(ancestors=len(known), documented=sum(p["st"] == "doc" for p in known), records=len(records),
                 generations=max(p["gen"] for p in people.values()) + 1)
    hypotheses = [dict(line=h.get("rod"), title=h.get("nadpis", "Hypotéza"), text=h.get("text", ""),
                       items=[dict(name=a, text=b) for a, b in h.get("polozky", [])],
                       records=[r for r in h.get("zaznamy", []) if r in recs]) for h in ns["HYPOTEZY"]]

    has_story = os.path.exists(os.path.join(DATA, "pribeh.md"))
    public_cfg = {k: v for k, v in cfg.items() if k != "prihlaseni"}
    public_cfg["maPribeh"] = has_story
    public_cfg["maZmeny"] = os.path.exists(os.path.join(DATA, "zmeny.md"))
    klic = jload("tajne.json", {}).get("mapy_klic") or os.environ.get("MAPY_API_KEY")
    if klic:
        public_cfg["mapa"] = {**(cfg.get("mapa") or {}), "klic": klic}
    site = dict(config=public_cfg, places=places, moves=moves, events=events, coords=coords, root=slugs[1], aliases={a: slugs[a] for a in SAME}, people=people,
                families=families, others=others, records=records, lines=lines,
                issues=[dict(title=i, text="") if isinstance(i, str) else dict(title=i[0], text=i[1]) for i in ISSUES], stats=stats, hypotheses=hypotheses,
                docs=[dict(img=d["img"], caption=d["popis"], people=[slugs[k] for k in d.get("osoby", []) if k in slugs])
                      for d in docs_cfg if os.path.exists(os.path.join(VYREZY, d["img"] + ".jpg"))])

    write(os.path.join(WEB, "src", "data", "site.json"), json.dumps(site, ensure_ascii=False, indent=1))
    write(os.path.join(WEB, "public", "data", "rodokmen.json"), json.dumps(
        {k: site[k] for k in ("people", "families", "others", "events", "records", "places", "moves", "lines", "root")}, ensure_ascii=False))
    write_db(P, slugs, people, families, events, moves, R, others)
    gen_dir = os.path.join(WEB, "src", "generated")
    for src, dst in (("archivni_dotazy.md", "dotazy.md"), ("research_log.md", "denik.md"), ("zajimavosti.md", "zajimavosti.md"), ("zmeny.md", "zmeny.md")):
        path = os.path.join(DATA, src)
        text = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
        write(os.path.join(gen_dir, dst), strip_comments(re.sub(r"^# .*\n", "", text, count=1)))
    story = os.path.join(DATA, "pribeh.md")
    write(os.path.join(gen_dir, "pribeh.md"), strip_comments(open(story, encoding="utf-8").read()) if has_story else "---\ntitle: Příběh\nlead: ''\n---\n")

    hrefs = os.path.join(gen_dir, "fan_hrefs.json")
    json.dump({k: f"/osoba/{s}/" for k, s in slugs.items()}, open(hrefs, "w", encoding="utf-8", newline="\n"))
    subprocess.run([sys.executable, "-I", "-X", "utf8", os.path.join(TOOLS, "fan_chart.py"),
                    os.path.join(gen_dir, "fan.svg"), "--web", hrefs], check=True, capture_output=True)

    gated = login_files(cfg)

    copied = 0
    zv = os.path.join(DATA, "zvyrazneni.json")
    hl_mtime = os.path.getmtime(zv) if os.path.exists(zv) else 0
    for sub, src_dir in (("img", VYREZY), ("zdroje", ZDROJE)):
        dst_dir = os.path.join(WEB, "public", sub)
        os.makedirs(dst_dir, exist_ok=True)
        for key in list(recs) + [d["img"] for d in docs_cfg] + [p["photo"] for p in places if p["photo"]] \
                + ([cfg["uvod"]["foto"]] if cfg.get("uvod", {}).get("foto") else []):
            src = os.path.join(src_dir, key + ".jpg")
            dst = os.path.join(dst_dir, key + ".jpg")
            if not os.path.exists(src):
                continue
            boxes = hl.get(key, {}).get("boxes", [])
            stale = not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst) \
                or (sub == "zdroje" and boxes and hl_mtime > os.path.getmtime(dst))
            if not stale:
                continue
            if sub == "zdroje" and boxes and draw_boxes(src, dst, boxes, os.path.join(VYREZY, key + ".jpg")):
                copied += 1
                continue
            shutil.copy2(src, dst)
            copied += 1
    print(f"{len(people)} osob, {len(families)} rodin, {len(records)} zápisů, {len(lines)} rodů, {len(places)} míst, "
          f"{len(moves)} stěhování; "
          f"zkopírováno {copied} obrázků; přihlášení {'zapnuté' if gated else 'VYPNUTÉ (web je otevřený)'}")

    # odkazy v textech, které nikam nevedou (adresa osoby se změní třeba doplněním roku narození: jan-novak → jan-novak-1798)
    targets = dict(osoba=people, zdroj=recs, rod=lines, rodina=families)
    texts = {f: open(os.path.join(gen_dir, f), encoding="utf-8").read() for f in ("pribeh.md", "zajimavosti.md")}
    texts["web.json"] = json.dumps(cfg, ensure_ascii=False)
    texts["osoby.py (hypotézy)"] = json.dumps(hypotheses, ensure_ascii=False)
    broken = [(f, m.group(0)) for f, t in texts.items()
              for m in re.finditer(r"/(osoba|zdroj|rod|rodina)/([^/\s)\"'#?<>\]]+)", t) if m.group(2) not in targets[m.group(1)]]
    for f, link in dict.fromkeys(broken):
        print(f"POZOR: nefunkční odkaz {link}/ v {f} – oprav ho (adresy stránek jsou ve web/src/data/site.json)")


if __name__ == "__main__":
    main()
