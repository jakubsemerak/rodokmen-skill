"""Testy nástrojů skillu na ukázkové rodině. Spuštění z kořene repozitáře: python3 -m unittest discover tests"""
import json, os, pathlib, shutil, sqlite3, subprocess, sys, tempfile, unittest

SKILL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills", "rodokmen")


def run(proj, tool, *args, env=None):
    e = {k: v for k, v in os.environ.items() if k != "MAPY_API_KEY"} | (env or {})
    r = subprocess.run([sys.executable, "-I", "-X", "utf8", os.path.join(proj, "tools", tool), *args],
                       cwd=proj, env=e, capture_output=True, text=True, encoding="utf-8", timeout=60)
    return r.stdout + r.stderr


GED = """0 HEAD
1 CHAR UTF-8
0 @I1@ INDI
1 NAME Petr /Novák/
1 FAMC @F1@
0 @I2@ INDI
1 NAME Josef /Novák/
1 SEX M
1 OCCU zámečník
1 NOTE bydlí Masarykova 12, tel. 777 123 456
1 FAMS @F1@
1 FAMC @F0@
0 @I3@ INDI
1 NAME Jan /Novák/
1 SEX M
1 BIRT
2 DATE ABT 1850
1 DEAT
2 DATE BEF 1910
1 FAMS @F0@
1 FAMC @F00@
0 @I5@ INDI
1 NAME Václav /Novák/
1 SEX M
1 BIRT
2 PLAC Ostřetín čp. 5
1 OCCU sedlák
1 FAMS @F00@
0 @F00@ FAM
1 HUSB @I5@
1 CHIL @I3@
0 @I4@ INDI
1 NAME Anna /Malá/
1 SEX F
1 OCCU švadlena
1 FAMS @F0@
0 @F0@ FAM
1 HUSB @I3@
1 WIFE @I4@
1 CHIL @I2@
1 MARR
2 DATE 1880
2 PLAC Holice
0 @F1@ FAM
1 HUSB @I2@
1 CHIL @I1@
1 MARR
2 DATE 12 JUN 1975
2 PLAC Holice
0 TRLR
"""


class GedImport(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        shutil.copytree(os.path.join(SKILL, "tools"), os.path.join(self.dir, "tools"))
        pathlib.Path(self.dir, "strom.ged").write_text(GED, encoding="utf-8")
        out = run(self.dir, "ged_import.py", "strom.ged", "Petr Novák", "--osoby")
        self.P = {}
        exec(out, {"P": self.P}, ns := {})
        self.P = ns["P"]

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_zijici_bez_roku_jen_jmeno(self):
        otec = self.P[2]
        self.assertEqual(otec["n"], "Josef Novák")
        self.assertNotIn("Masarykova", repr(otec))
        self.assertFalse(any("1975" in f or "zámečník" in f for f in otec["f"]), otec["f"])

    def test_zemrely_a_stary_predek_s_udaji(self):
        self.assertEqual(self.P[4]["y"], "asi 1850 – před 1910")
        self.assertIn("† před 1910", self.P[4]["f"])
        self.assertIn("švadlena", self.P[5]["f"])   # bez úmrtí, ale sňatek 1880 – nežije
        self.assertIn("sedlák", self.P[8]["f"])   # bez jakéhokoli data, ale syn narozen asi 1850
        self.assertNotIn("note", self.P[8])

    def test_bez_udalosti_zijici(self):
        self.assertEqual(self.P[1]["f"], [])
        self.assertIn("Žijící", self.P[1]["note"])


class Ukazka(unittest.TestCase):
    """Každý test dostane vlastní kopii ukázkového projektu (novy_projekt.py --ukazka)."""

    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.mkdtemp()
        subprocess.run([sys.executable, "-I", os.path.join(SKILL, "tools", "novy_projekt.py"), os.path.join(cls.base, "p"), "--ukazka"],
                       check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base)

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.p = os.path.join(self.dir, "p")
        shutil.copytree(os.path.join(self.base, "p"), self.p, ignore=shutil.ignore_patterns("node_modules"))

    def tearDown(self):
        shutil.rmtree(self.dir)

    def osoby(self, old, new=None, append=""):
        path = pathlib.Path(self.p, "data", "osoby.py")
        t = path.read_text(encoding="utf-8")
        if old:
            self.assertIn(old, t)
            t = t.replace(old, new, 1)
        path.write_text(t + append, encoding="utf-8")

    def export(self):
        out = run(self.p, "export_web.py")
        self.assertIn("stěhování", out, out)
        return out, json.loads(pathlib.Path(self.p, "web", "src", "data", "site.json").read_text(encoding="utf-8"))

    def test_domov_a_stehovani(self):
        _, s = self.export()
        self.assertEqual(s["people"]["barbora-mala-1862"]["home"], "Ostřetín")
        self.assertEqual(s["people"]["jan-novak-1890"]["home"], "Holice")
        mv = [m for m in s["moves"] if m["src"] == "Ostřetín" and m["dst"] == "Holice" and m["line"] == 8]
        self.assertEqual(len(mv), 1)
        self.assertIn("barbora-mala-1862", mv[0]["people"])
        self.assertFalse([m for m in s["moves"] if m["src"] == m["dst"]])
        self.assertEqual(s["coords"]["Holice"], [50.0663, 15.9859])

    def test_casova_osa_udalosti(self):
        _, s = self.export()
        ev = s["events"]
        self.assertEqual([e["year"] for e in ev], sorted(e["year"] for e in ev))
        b = next(e for e in ev if e["kind"] == "narozeni" and e["people"] == ["barbora-mala-1862"])
        self.assertEqual((b["year"], b["date"], b["place"]), (1862, "1862", "Ostřetín"))
        wed = [e for e in ev if e["kind"] == "snatek" and "barbora-mala-1862" in e["people"]]
        self.assertEqual(len(wed), 1)
        self.assertEqual((wed[0]["people"], wed[0]["place"]), (["vaclav-novak-1858", "barbora-mala-1862"], "Holice"))
        self.assertTrue(any(e["kind"] == "stehovani" and e["src"] == "Ostřetín" and e["place"] == "Holice" for e in ev))

    def test_databaze_json_a_sqlite(self):
        _, s = self.export()
        pub = json.loads(pathlib.Path(self.p, "web", "public", "data", "rodokmen.json").read_text(encoding="utf-8"))
        self.assertEqual(pub["people"], s["people"])
        self.assertEqual(len(pub["events"]), len(s["events"]))
        db = sqlite3.connect(os.path.join(self.p, "vystupy", "rodokmen.sqlite"))
        self.assertEqual(db.execute("SELECT jmeno FROM osoby WHERE k = 17").fetchone(), ("Barbora Malá",))
        self.assertEqual(db.execute("SELECT count(*) FROM udalosti").fetchone()[0], len(s["events"]))
        rows = db.execute("SELECT u.rok FROM udalosti u, json_each(u.osoby) j WHERE j.value = 'barbora-mala-1862' AND u.druh <> 'stehovani'").fetchall()
        self.assertEqual(sorted(r[0] for r in rows), [1862, 1884, 1930])
        db.close()
        self.export()   # znovu vytvořit, ne přidat
        db = sqlite3.connect(os.path.join(self.p, "vystupy", "rodokmen.sqlite"))
        self.assertEqual(db.execute("SELECT count(*) FROM udalosti").fetchone()[0], len(s["events"]))
        db.close()

    def test_soukrome_nejde_na_web(self):
        self.osoby("'n': 'Barbora Malá', 'y': '1862–1930',", "'n': 'Barbora Malá', 'y': '1862–1930', 'soukrome': ['TAJNÁ-POZNÁMKA-XYZ léčebna'],")
        with open(os.path.join(self.p, "data", "research_log.md"), "a", encoding="utf-8") as f:
            f.write("| 98 | 2026-10-02 | rodina | – | Karel | SOUKROMÝ-ŘÁDEK bydlí Lipová 3 | – | <!-- soukromé -->\n")
            f.write("| 99 | 2026-10-02 | rodina | – | Karel | VEŘEJNÝ-ŘÁDEK | – | <!-- pro Clauda -->\n")
        self.export()
        web = pathlib.Path(self.p, "web")
        texts = [f.read_text(encoding="utf-8", errors="ignore") for f in web.rglob("*")
                 if f.is_file() and "node_modules" not in f.parts and f.suffix in (".json", ".md", ".html", ".js", ".svg", ".conf")]
        self.assertFalse([t for t in texts if "TAJNÁ-POZNÁMKA-XYZ" in t])
        denik = (web / "src" / "generated" / "denik.md").read_text(encoding="utf-8")
        self.assertNotIn("SOUKROMÝ-ŘÁDEK", denik)
        self.assertIn("VEŘEJNÝ-ŘÁDEK", denik)
        self.assertNotIn("pro Clauda", denik)
        db = sqlite3.connect(os.path.join(self.p, "vystupy", "rodokmen.sqlite"))
        self.assertIn("TAJNÁ-POZNÁMKA-XYZ", db.execute("SELECT soukrome FROM osoby WHERE k = 17").fetchone()[0])
        db.close()
        k = run(self.p, "kontrola.py")
        self.assertNotIn("SOUKROMÉ (", k)
        self.assertNotIn("Lipová", k)

    def test_kontrola_soukrome_v_publikovanem_textu(self):
        self.osoby("'n': 'Barbora Malá', 'y': '1862–1930',", "'n': 'Barbora Malá', 'y': '1862–1930', 'soukrome': ['léčila se v Kosmonosích'],")
        with open(os.path.join(self.p, "data", "zajimavosti.md"), "a", encoding="utf-8") as f:
            f.write("\n## Babička\nBarbora Malá léčila se v Kosmonosích.\n")
        self.assertIn("SOUKROMÉ (zajimavosti.md): „léčila se v Kosmonosích“ je v osoby.py u osoby 17", run(self.p, "kontrola.py"))

    def test_kontrola_mapy_cz_bez_klice(self):
        path = pathlib.Path(self.p, "data", "web.json")
        cfg = json.loads(path.read_text(encoding="utf-8"))
        cfg["mapa"] = {"podklad": "mapy.cz"}
        path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        self.assertIn("chybí API klíč", run(self.p, "kontrola.py"))
        cfg["mapa"]["klic"] = "TESTKLIC"
        path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        k = run(self.p, "kontrola.py")
        self.assertNotIn("chybí API klíč", k)
        self.assertIn("mapa.klic je v gitu", k)
        _, s = self.export()
        self.assertEqual(s["config"]["mapa"]["klic"], "TESTKLIC")

    def test_mapy_klic_z_tajne_a_promenne(self):
        path = pathlib.Path(self.p, "data", "web.json")
        cfg = json.loads(path.read_text(encoding="utf-8"))
        cfg["mapa"] = {"podklad": "mapy.cz"}
        path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        pathlib.Path(self.p, "data", "tajne.json").write_text('{"mapy_klic": "TESTKLIC"}', encoding="utf-8")
        k = run(self.p, "kontrola.py")
        self.assertNotIn("chybí API klíč", k)
        self.assertNotIn("mapa.klic", k)
        _, s = self.export()
        self.assertEqual(s["config"]["mapa"], {"podklad": "mapy.cz", "klic": "TESTKLIC"})
        site = pathlib.Path(self.p, "web", "src", "data", "site.json")
        run(self.p, "export_web.py", env={"MAPY_API_KEY": "ENVKLIC"})
        self.assertEqual(json.loads(site.read_text(encoding="utf-8"))["config"]["mapa"]["klic"], "TESTKLIC")
        pathlib.Path(self.p, "data", "tajne.json").unlink()
        run(self.p, "export_web.py", env={"MAPY_API_KEY": "ENVKLIC"})
        self.assertEqual(json.loads(site.read_text(encoding="utf-8"))["config"]["mapa"]["klic"], "ENVKLIC")
        self.assertNotIn("klic", json.loads(path.read_text(encoding="utf-8"))["mapa"])

    def test_tajne_v_gitignore(self):
        lines = pathlib.Path(SKILL, "template", ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("data/tajne.json", lines)

    def test_brana_cloudflare(self):
        import hashlib
        self.export()
        mw = pathlib.Path(self.p, "web", "functions", "_middleware.js")
        digest = hashlib.sha256("rodokmen:kovar".encode()).hexdigest()
        self.assertIn(f"const HASH = '{digest}';", mw.read_text(encoding="utf-8"))
        self.assertNotIn("kovář", mw.read_text(encoding="utf-8"))
        path = pathlib.Path(self.p, "data", "web.json")
        cfg = json.loads(path.read_text(encoding="utf-8"))
        cfg["prihlaseni"]["odpoved"] = ""
        path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        self.export()
        self.assertFalse(mw.exists())

    def test_heslo_z_tajne(self):
        import hashlib
        path = pathlib.Path(self.p, "data", "web.json")
        cfg = json.loads(path.read_text(encoding="utf-8"))
        cfg["prihlaseni"]["odpoved"] = ""
        path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        pathlib.Path(self.p, "data", "tajne.json").write_text('{"heslo": "Tajné Heslo 7"}', encoding="utf-8")
        out = run(self.p, "export_web.py", "--nasazeni")
        self.assertNotIn("CHYBA", out)
        mw = pathlib.Path(self.p, "web", "functions", "_middleware.js").read_text(encoding="utf-8")
        self.assertIn(hashlib.sha256("rodokmen:tajneheslo7".encode()).hexdigest(), mw)
        self.assertNotIn("Tajné", pathlib.Path(self.p, "web", "src", "data", "site.json").read_text(encoding="utf-8"))
        self.assertNotIn("odpověď na přihlašovací otázku", run(self.p, "kontrola.py"))
        self.assertIn('type="password"', pathlib.Path(self.p, "web", "public", "prihlaseni.html").read_text(encoding="utf-8"))

    def test_otazka_bez_skryti(self):
        self.export()
        self.assertIn('type="text"', pathlib.Path(self.p, "web", "public", "prihlaseni.html").read_text(encoding="utf-8"))

    @unittest.skipUnless(shutil.which("node"), "chybí node")
    def test_brana_cloudflare_v_node(self):
        import hashlib
        self.export()
        mw = pathlib.Path(self.p, "web", "functions", "_middleware.js")
        h = hashlib.sha256("rodokmen:kovar".encode()).hexdigest()
        js = """
const { onRequest } = await import(process.argv[1]);
const ctx = (path, cookie) => ({ request: new Request('https://x.test' + path, { headers: cookie ? { cookie } : {} }),
  next: async () => new Response('ok', { status: 200 }), env: { ASSETS: { fetch: async () => new Response('login') } } });
const r = await Promise.all([onRequest(ctx('/', '')), onRequest(ctx('/', 'rodokmen=' + process.argv[2])),
  onRequest(ctx('/', 'rodokmen=' + '0'.repeat(64))), onRequest(ctx('/prihlaseni', ''))]);
console.log(r.map((x) => x.status).join(','));
"""
        r = subprocess.run(["node", "--input-type=module", "-e", js, mw.as_uri(), h], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.stdout.strip(), "401,200,401,200", r.stderr)

    def test_aktualizace_doplni_gitignore(self):
        gi = pathlib.Path(self.p, ".gitignore")
        gi.write_text("pracovni/\nmoje/\n", encoding="utf-8")
        subprocess.run([sys.executable, "-I", os.path.join(SKILL, "tools", "novy_projekt.py"), self.p], check=True, capture_output=True)
        lines = gi.read_text(encoding="utf-8").splitlines()
        self.assertIn("vystupy/rodokmen.sqlite", lines)
        self.assertIn("data/tajne.json", lines)
        self.assertIn("moje/", lines)
        self.assertEqual(lines.count("pracovni/"), 1)

    def test_domov_z_volneho_textu_kdyz_narozeni_bez_obce(self):
        self.osoby("'f': ['* 1862 Ostřetín čp. 23',", "'f': ['* 1862', 'bydlela v Býšti',")
        _, s = self.export()
        self.assertEqual(s["people"]["barbora-mala-1862"]["home"], "Býšť")

    def test_same_retez_a_kruh(self):
        out, s = self.export_with_same("SAME = {300: 301, 301: 16, 302: 303, 303: 302}\n")
        self.assertEqual(s["aliases"]["300"], s["aliases"]["301"])
        self.assertEqual(s["aliases"]["301"], "vaclav-novak-1858")
        self.assertNotIn("302", s["aliases"])
        k = run(self.p, "kontrola.py")
        self.assertIn("302 -> 303 je v kruhu", k)
        self.assertIn("300 -> 301 je alias dalšího aliasu", k)

    def export_with_same(self, same):
        self.osoby(None, append="\n" + same)
        return self.export()

    def test_snatek_rodicu_u_matky_s_otaznikem(self):
        self.osoby("'n': 'Barbora Malá', 'y': '1862–1930'", "'n': 'Barbora Malá (?)', 'y': '1862–1930'")
        self.osoby("'× 1884 Holice Barbora Malá', '† 1921 Holice']", "'× 1880 Holice Marie Dvořáková', '× 1884 Holice Barbora Malá', '† 1921 Holice']")
        _, s = self.export()
        fam = next(f for f in s["families"].values() if f["child"] == "jan-novak-1890")
        self.assertEqual(fam["marriage"], ["× 1884 Holice Barbora Malá"])

    def test_kontrola_obec_narozeni_chybi_v_mistech(self):
        self.osoby("'* 1862 Ostřetín čp. 23'", "'* 1862 Ústí nad Orlicí čp. 23'")
        k = run(self.p, "kontrola.py")
        self.assertIn("obec narození „Ústí nad Orlicí“ není v data/mista.json", k)
        self.assertNotIn("obec narození „Holice", k)

    def test_kontrola_citlive_v_deniku(self):
        with open(os.path.join(self.p, "data", "research_log.md"), "a", encoding="utf-8") as f:
            f.write("| 99 | 2026-10-01 | rodina | – | Karel | rozvod 1990, podle rodiny | – |\n")
        self.assertIn("CITLIVÉ (research_log.md)", run(self.p, "kontrola.py"))

    def test_kontrola_zijici_s_datem(self):
        self.osoby("'f': ['* 1952 Holice']", "'f': ['* 3. 5. 1952 Holice']")
        k = run(self.p, "kontrola.py")
        self.assertIn("ŽIJÍCÍ osoba 2", k)
        self.assertNotIn("ŽIJÍCÍ osoba 4", k)

    def test_kontrola_rodina_odkazy(self):
        self.assertNotIn("RODINA", run(self.p, "kontrola.py"))
        self.osoby('otec="karel-hruby"', 'otec="neexistuje"')
        self.osoby(None, append='RODINA["x"] = dict(n="Petr X", y="1900–1950", sex="M", partner=[999])\n')
        k = run(self.p, "kontrola.py")
        self.assertIn("CHYBA: RODINA 'jaroslav-hruby' (Jaroslav Hrubý): otec 'neexistuje' není v RODINA", k)
        self.assertIn("RODINA 'x' (Petr X): partner 999 neexistuje", k)

    def test_export_rodina(self):
        _, s = self.export()
        o = {x["id"]: x for x in s["others"]}
        self.assertEqual((o["o:marie-novakova"]["father"], o["o:marie-novakova"]["mother"]), ("k16", "k17"))
        self.assertEqual(o["o:jaroslav-hruby"]["father"], "o:karel-hruby")
        side = {e["name"]: e["rel"] for e in s["people"]["jan-novak-1890"]["side"]}
        self.assertEqual(side["Marie Nováková"], "sestra")
        pub = json.loads(pathlib.Path(self.p, "web", "public", "data", "rodokmen.json").read_text(encoding="utf-8"))
        self.assertEqual(pub["others"], s["others"])
        db = sqlite3.connect(os.path.join(self.p, "vystupy", "rodokmen.sqlite"))
        self.assertEqual(db.execute("SELECT otec, matka FROM rodina WHERE id = 'o:vaclav-novak-1896'").fetchone(), ("k16", "k17"))
        db.close()

    def test_rodina_soukrome_nejde_na_web(self):
        self.osoby('note="Bratr Jana, padl', 'soukrome=["TAJNÉ-RODINA-QWE"], note="Bratr Jana, padl')
        self.export()
        web = pathlib.Path(self.p, "web")
        self.assertFalse([f for f in web.rglob("*") if f.is_file() and "node_modules" not in f.parts
                          and "TAJNÉ-RODINA-QWE" in f.read_text(encoding="utf-8", errors="ignore")])
        db = sqlite3.connect(os.path.join(self.p, "vystupy", "rodokmen.sqlite"))
        self.assertIn("TAJNÉ-RODINA-QWE", db.execute("SELECT soukrome FROM rodina WHERE id = 'o:vaclav-novak-1896'").fetchone()[0])
        db.close()

    def test_kontrola_zijici_rodina(self):
        self.osoby(None, append='RODINA["eva"] = dict(n="Eva Hrubá", y="* 1950", sex="F", otec="jaroslav-hruby", f=["bydlí Lipová 3, tel. 777 123 456"])\n')
        self.assertIn("ŽIJÍCÍ osoba RODINA eva (Eva Hrubá)", run(self.p, "kontrola.py"))

    def test_napady_dlouhovekost_jen_z_presneho_umrti(self):
        self.osoby(None, append='\nP[998] = dict(n="Ota Starý", st="doc", f=["* 1. 1. 1800", "† před 2. 2. 1907"])'
                                 '\nP[999] = dict(n="Iva Stará", st="doc", f=["* 1. 1. 1800", "† 2. 2. 1895"])\n')
        out = run(self.p, "napady.py")
        self.assertIn("Iva Stará (999) se dožil(a) 95 let", out)
        self.assertNotIn("Ota Starý (998) se dožil", out)


if __name__ == "__main__":
    unittest.main()
