"""Testy nástrojů skillu na ukázkové rodině. Spuštění z kořene repozitáře: python3 -m unittest discover tests"""
import json, os, re, shutil, subprocess, sys, tempfile, unittest

SKILL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills", "rodokmen")


def run(proj, tool, *args):
    r = subprocess.run([sys.executable, "-I", "-X", "utf8", os.path.join(proj, "tools", tool), *args],
                       cwd=proj, capture_output=True, text=True, encoding="utf-8")
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
        with open(os.path.join(self.dir, "strom.ged"), "w", encoding="utf-8") as f:
            f.write(GED)
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


if __name__ == "__main__":
    unittest.main()
