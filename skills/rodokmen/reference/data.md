# Formát dat projektu

Všechna data jsou v `data/`. Web se z nich generuje (`npm run data`), nikdy needituj `web/src/data/site.json` ručně.
Po změnách spusť `python3 -I tools/kontrola.py`. Ukázku vyplněných dat má `SKILL_DIR/template/ukazka/`.
Položky do JSON souborů přidávej a měň přes `python3 -I tools/zapis.py` (zachová formát souboru, viz SKILL.md).

## `osoby.py` – předci
Kekulého čísla: 1 = výchozí osoba, otec osoby n = 2n, matka = 2n+1.
| číslo | kdo |
|---|---|
| 1 | výchozí osoba (u ženy `sex="F"`) |
| 2, 3 | otec, matka |
| 4–7 | prarodiče (4, 5 otcovi rodiče; 6, 7 matčini) |
| 8–15 | pradědečci a prababičky = **8 rodů** (`LINES`) |
| 16–31, 32–63 … | každá další generace dvojnásobek |

Otec předka 22 je 44, matka 45; dítě předka 45 je 22 (45 // 2). Muži mají sudá čísla.

```python
P = {
 8: dict(n="Jan Novák", y="1890–1944", st="doc",
         f=["* 14. 2. 1890 Holice čp. 112", "kovář", "× 20. 6. 1919 Holice Josefa Pokorná", "† 1944 Holice"],
         r=["holice_krest_jan_novak_1890", "holice_snatek_jan_novak_josefa_pokorna_1919"],
         note="Proč nejistota / rozpor / odkud údaj"),
 9: dict(n="Josefa Pokorná", y="* 1895", st="doc", f=[...], r=[...]),
 33: dict(n="otec neuveden", st="unk", f=[], note="Nemanželský syn; otec v matrice není."),
}
```
- `n` jméno (ženy rodným příjmením), `y` roky pro přehledy (`"* 1895"`, `"1890–1944"`, `"asi 1720–1785"`, `"1680 – před 1740"`,
  `"† 1940"` když známe jen úmrtí; nic nevíme → `""`).
- `f` fakta: začínají `*` (narození), `×` (sňatek), `†` (úmrtí) nebo jsou volný text (řemeslo, bydliště).
  Názvy obcí ve faktech používá mapa (`mista.json` → `re`).
- `r` klíče zápisů ze `zaznamy.json`. `st` viz `matriky.md`: `doc` přečteno v matrice, `prob` pravděpodobné,
  `fam` od rodiny (i strom, který si rodina vede sama, např. GEDCOM z jejího MyHeritage), `mh` cizí strom z internetu, `unk`.
- `soukrome` – seznam soukromých údajů, které na web **nikdy nejdou** (adresa, přesné datum narození žijícího, nemoc,
  co rodina řekla důvěrně): `soukrome=["bydlí Masarykova 12", "léčil se v Kosmonosích"]`. Export je nepublikuje, najdeš je
  jen v `vystupy/rodokmen.sqlite`; `kontrola.py` upozorní, když se stejný text objeví v něčem, co jde na web.
- `LINES = {8: ("Novákové", "Kováři z Holic…"), …}` – jen čísla 8–15; název rodu = příjmení v množném čísle.
- `RODINA` – osoby mimo přímou linii (sourozenci předků, jejich partneři a děti, předci partnerů):
  `"zkratka": dict(n="Marie Nováková", y="1892–1970", sex="F", otec=16, matka=17, partner=[...], st="doc", f=[...], r=[...], note="…")`.
  `otec`/`matka` = číslo přímého předka nebo zkratka jiné osoby z RODINA; sourozenec předka 8 má `otec=16, matka=17`,
  i když 16/17 ještě neznáme. `partner` jen pro partnery bez společného dítěte. `soukrome` jako u předků (na web nejde).
  Stromový graf (`/strom/`) z nich skládá rozklikávací větve; na stránce osoby a rodiny se ukážou jako příbuzní.
  Žijící jen jménem a rokem narození – `kontrola.py` hlídá RODINA stejně jako `P`. U předka v `P` lze zapsat
  `sour="hotovo"` / `"částečně"` (stav hledání sourozenců).
- `SIDE` – jen poznámky, které do RODINA nejdou (nejistý vztah, kmotr „asi příbuzný“, celá větev jednou větou):
  `dict(k=<číslo předka>, n="Josef Novák", v="bratr", y="1865–1920", t="text", r=[klíče])` – ve stromu jako „pozn.“ u předka.
  **RODINA, nebo SIDE?** Víš-li, kdo jsou rodiče nebo partner (aspoň „sourozenec předka 8“), patří osoba do RODINA;
  jen tušená souvislost bez jistého vztahu do SIDE.
- `ISSUES` – dvojice `("Otázka", "Vyřešeno: … / Hypotéza: … / Otevřené: …")` → stránka „Co hledáme“ (vyřešené se skryjí).
  Jde na web – nepiš sem citlivé věci (příčiny úmrtí, rodinné spory) bez souhlasu.
- `HYPOTEZY` – `dict(rod=8, nadpis="…", text="…", polozky=[("jméno", "text")], zaznamy=[klíče])` → stránka rodu.
- `SAME = {350: 140}` – předek, který je v rodokmenu dvakrát (alias → hlavní číslo; alias v `P` může mít `f=["TÁŽ OSOBA jako 140"]`).

## `zaznamy.json` – zápisy
```json
[{"klic": "holice_krest_jan_novak_1890", "svazek": "1a0b2337", "snimek": 57, "druh": "N",
  "datum": "14. 2. 1890", "nazev": "Křest Jana Nováka",
  "shrnuti": "Jan, syn Václava Nováka, kováře v Holicích čp. 112, a Barbory roz. Malé z Ostřetína.",
  "odkaz": "https://aron.vychodoceskearchivy.cz/apu/…/dao/…/file/…"}]
```
- `klic`: malá písmena bez diakritiky, `obec_druh_kdo_rok` (druh: krest, snatek, umrti, index, scitani…). Je to i název obrázku.
- `druh`: N, O, Z, I (index/rejstřík), S (sčítání), J (jiný pramen).
- `datum` jako v češtině („14. 2. 1890“, „3/1867“, „1797“) – web podle něj řadí.

## `svazky.json`
`{"1a0b2337": {"archiv": "SOA Zámrsk – Sbírka matrik…", "portal": "ARON", "svazek": "N Holice 1880–1900, sign. …",
"popis": "obce", "url": "odkaz na svazek"}}` – u ARON zapisuje `aron_img.py <apu> svazek`.

## `prepisy.json`
`{"<klic>": {"orig": "[Datum] 14. února 1890\n[Dům] 112\n[Otec] …", "cs": "Český překlad celou větou…"}}`
- `orig` věrný přepis po sloupcích, `[Název sloupce]` v hranatých závorkách, nejisté „(?)“, nečitelné „[…]“, zkratky ponechat.
- `cs` srozumitelný překlad pro rodinu; vysvětli staré pojmy (domkář, podruh).

## `zvyrazneni.json`
`{"<klic>": {"boxes": [[x0, y0, x1, y1]], "status": "ok", "note": ""}}` – zlomky šířky/výšky obrázku `vyrezy/<klic>.jpg`.
Zapisuje `ramecek.py`. Rámeček má obepnout celý čtený zápis (ne jen jméno).

## `mista.json`
`{"Holice": {"re": "Holic", "dotaz": "Holice, Česko", "lat": 50.066, "lon": 15.986}}` – `re` je regulární výraz hledaný
ve faktech osob (kmen slova, aby sedělo skloňování: „Holic“ najde Holice i v Holicích). Spravuje `mista.py`.
Pozor na kolize (Hradec Králové × Nový Hradec Králové – použij `(?<!Nový )Hradec`; krátká jména jako `\bBuku?\b`).
Hypotéza: `"hypoteza": true, "rod": 8`. Fotka obce nebo kostela pro okénko mapy: `"foto": "misto_holice"` (klíč obrázku
ve `vyrezy/`), `"foto_popis"` s autorem a licencí a `"foto_zdroj"` (stránka fotky, na webu odkaz „zdroj a licence“) –
zapisuje `foto_mista.py`. Když OpenStreetMap obec nenajde („Žár“, malé osady), zkus třetí parametr – dotaz: `mista.py pridej "Žár" "Žár" "Žár, Zdíkov, okres Prachatice"`
nebo dotaz s větší obcí či okresem. U **víceznačných názvů** (Podolí, Dub, Lhota) vezme OpenStreetMap kteroukoli ves
(„Podolí, Česko“ = Podolí u Brna) – v posledním sloupci výpisu zkontroluj okres a dej dotaz se sousední obcí
(`mista.py pridej "Podolí" "Podol" "Podolí, Odlochovice"`). Místopis nejlíp zná rodina – když si nejsi jistý, zeptej se.

### Mapa stěhování
Export určí každé osobě **domov**: první obec z `mista.json` ve faktu o narození (`*`), není-li tam, tak ve volném textu
(bydliště, řemeslo), pak ve sňatku (`×`) a úmrtí (`†`). Šipka stěhování vede z domova rodiče do domova dítěte v linii.
Proto piš obec do faktu o narození vždy, když ji znáš (`"* 1862 Ostřetín čp. 23"`), a každou obec z faktů přidej
do `mista.json` – `kontrola.py` hlásí obce narození (`* rok Obec`), které tam chybí; ostatní obce hlídej sám. Osoba bez známé obce na mapě nebude a cesta ji přeskočí.

### Časová osa pod mapou
Stránka `/mapa/` má pod mapou časovou osu: narození, sňatky a úmrtí z faktů s rokem (`* 12. 3. 1873 Hořice`) a stěhování
(rok = narození dítěte v cílové obci). Posuvník „Mapa do roku“ a tlačítko ▶ ukazují, jak se rod šířil. Export je zapisuje
do `site.json` jako `events` (`year`, `date` jak je zapsáno, `kind`, `people`, `place`, `label`). Sňatek se páruje mezi
manžely podle roku – zapiš ho u obou se stejným rokem.

## `dokumenty.json` – rodinné fotky a dokumenty na webu
`[{"img": "foto_svatba_1919", "popis": "Svatba Jana a Josefy, Holice 1919.", "osoby": [8, 9]}]`
Obrázek ulož přes `vyrez.py dokumenty/<sken>.jpg foto_svatba_1919` (vznikne `vyrezy/` i `zdroje/`).
Portrét: `"portret": true` a v `osoby` jen ta jedna osoba (`[{"img": "portret_jan_novak", "popis": "Jan Novák kolem 1915.",
"osoby": [8], "portret": true}]`) – ukáže se nahoře na stránce osoby a v okénkách mapy. Výřez jen obličeje a ramen.

## `web.json` – nastavení webu
Viz `web.md`.

## Markdown poznámky
- `research_log.md` – tabulka `| # | datum | zdroj | rozsah | hledáno | výsledek | citace |`, nové řádky na konec, i negativní.
  Web ji zobrazuje jako „Výzkumný deník“.
- `zajimavosti.md` – `## Nadpis` + text, odkazy `[Jméno](/osoba/<slug>/)`.
- `zmeny.md` – změny a opravy pro rodinu, nejnovější nahoře: `## RRRR-MM-DD` + odrážky „co bylo → co platí a podle čeho“,
  odkazy `[Jméno](/osoba/<slug>/)`. Web ji ukáže jako „Změny“; když soubor neexistuje, položka menu se skryje.
- `pribeh.md` – „Příběh <hlavního rodu>“: frontmatter `title`, `lead` + kapitoly `##`; když soubor neexistuje,
  položka menu se skryje. Jak psát: `pribehy.md`.
- Poznámky pro Clauda v markdownu piš jako `<!-- … -->` – na web nejdou.
- Řádek deníku se soukromým údajem (adresa žijících, citlivé sdělení rodiny) označ na konci `<!-- soukromé -->` –
  na web („Výzkumný deník“) nejde celý řádek, v projektu zůstává.
- `archivni_dotazy.md`, `udaje_od_rodiny.md` – volný text.

## Databáze pro dotazy (`vystupy/rodokmen.sqlite`, `web/public/data/rodokmen.json`)
Každý export (`npm run data`) je vyrobí znovu – ručně je neupravuj, zdrojem jsou soubory v `data/`.
- `web/public/data/rodokmen.json` – veřejná data webu (`people`, `families`, `others` = RODINA bez `soukrome`, `events`, `records`, `places`, `moves`,
  `lines`, `root`) pro skripty v prohlížeči a agenty; soukromí stejné jako web (za přihlášením).
- `vystupy/rodokmen.sqlite` – **jen v projektu, nenasazuje se a je v `.gitignore`**: všechny osoby z `osoby.py`
  včetně soukromých údajů (`soukrome`). Seznamy jsou JSON text (dotaz přes `json_each`).

| tabulka | sloupce |
|---|---|
| `osoby` | `k` (Kekulé), `slug`, `jmeno`, `roky`, `stav`, `generace`, `pohlavi`, `rod`, `domov`, `otec`, `matka` (čísla), `zapisy`, `poznamka`, `soukrome` |
| `rodina` | `id` (`o:zkratka`), `jmeno`, `roky`, `stav`, `pohlavi`, `otec`, `matka` (`k16` předek, `o:zkratka`, `?16` neznámý předek), `partneri`, `zapisy`, `fakta`, `poznamka`, `soukrome` |
| `fakta` | `osoba`, `poradi`, `druh` (`*`/`×`/`†`/prázdné), `rok`, `text` |
| `udalosti` | `rok`, `datum`, `druh` (`narozeni`/`snatek`/`umrti`/`stehovani`), `misto`, `odkud`, `popis`, `osoby` (slugy) |
| `rodiny` | `id`, `otec`, `matka`, `deti`, `snatek`, `rod`, `generace` |
| `zaznamy` | `klic`, `druh`, `datum`, `nazev`, `shrnuti`, `svazek`, `snimek`, `odkaz`, `osoby` |
| `svazky`, `prepisy`, `mista`, `stehovani` | jako stejnojmenné soubory v `data/` (`stehovani`: `odkud`, `kam`, `rod`, `rok`, `osoby`) |

```sql
-- kdo se narodil v Holicích, podle roku
SELECT rok, popis FROM udalosti WHERE druh = 'narozeni' AND misto = 'Holice' ORDER BY rok;
-- všechny události jedné osoby
SELECT u.rok, u.popis, u.misto FROM udalosti u, json_each(u.osoby) j WHERE j.value = 'barbora-mala-1862';
-- předci bez zápisu, od nejbližších generací
SELECT k, jmeno, roky FROM osoby WHERE zapisy = '[]' AND stav <> 'unk' ORDER BY generace, k;
```

## Odkazy na osoby (slug)
Slug = jméno bez diakritiky + rok, např. `jan-novak-1890`; při kolizi přidá číslo osoby. Přesné slugy po `npm run data`
v `web/src/data/site.json` (`people`). Při přejmenování osoby se slug změní – oprav odkazy v textech.
