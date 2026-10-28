# Rodinný web – stavba, nastavení, zveřejnění

Web je statický (Astro + vyhledávání Pagefind), data bere z `data/` přes `tools/export_web.py`.
Stránky: úvod (lákadlo, statistiky, zajímavosti, mapa, rody, vějíř), příběh, zajímavosti, rody, stránka rodu,
mapa (OpenStreetMap; šipky stěhování a „Cesta předka“ obec po obci, odkaz `/mapa/?cesta=<slug>`; fotky obcí), vějíř přes celou obrazovku s hledáním, stromový graf `/strom/` (výchozí osoba a 4 generace předků, tlačítka −/+ a „Vše“, rozbalování rodičů, sourozenců a potomků z `RODINA`, ⌖ odkaz na cestu na mapě; `/strom/#f=k12` začne od předka 12, ze stránky osoby odkaz „Stromový graf od této osoby“), seznam předků, zápisy (s výřezem, rámečkem, přepisem
a překladem), stránka osoby, rodiny, „Co hledáme“, výzkumný deník, hledání.

## Příkazy (ve složce `web/`)
| příkaz | co dělá |
|---|---|
| `npm install` | jednou na začátku (stáhne knihovny, ~1 minuta) |
| `npm run data` | převede data do webu (vždy po změně dat; funkční Python 3 vyhledá `scripts/data.mjs`) |
| `npm run build` | sestaví web do `dist/` |
| `npm run nahled` | data + build + náhled na http://localhost:4321 (Ctrl+C ukončí) |
| `npm run dev` | vývojový režim při úpravách vzhledu |
| `npm run nasadit` | data + build + nahrání na Netlify |

Náhled spouštěj na pozadí a uživateli pošli odkaz. Vzhled si ověř sám (snímek obrazovky přes prohlížeč, je-li k dispozici).

## `data/web.json`
```json
{
 "nazev": "Rodokmen Novákových",
 "popis": "Popis pro vyhledávače a sdílení (web je ale noindex).",
 "zapati": "Dohledáno v digitalizovaných matrikách SOA Zámrsk (portál ARON)",
 "kontakt": {"jmeno": "Petrovi", "email": "petr@example.cz"},
 "prihlaseni": {"uvod": "Tenhle web je jen pro rodinu.", "otazka": "Jak se jmenoval pes u babičky v Holicích?", "odpoved": "Alík"},
 "uvod": {"nadpis": "Lákavý nadpis", "odstavce": ["2–3 věty, které chytí"], "foto": "klic_obrazku_ve_vyrezech", "foto_popis": "…"},
 "pribeh": {"menu": "Příběh Nováků", "rod": 8, "tlacitko": "Přečíst příběh Nováků"},
 "zajimavosti_na_uvodu": [{"nadpis": "Nejstarší předek", "text": "Kovář Jan, asi 1825."}],
 "mapa": {"podklad": "osm"}
}
```
- `kontakt.jmeno` je ve 3. pádě („Napište Petrovi na …“).
- **Přihlášení:** otázka, na kterou zná odpověď jen rodina (ne snadno dohledatelná na sociálních sítích).
  Odpověď se porovnává bez diakritiky a velkých písmen. Na serveru i v cookie prohlížeče je jen její otisk (SHA-256),
  samotná odpověď se nikam neukládá. Krátkou nebo běžnou odpověď (jméno, obec) ale jde z otisku uhádnout zkoušením,
  proto ať ji uživatel nepoužívá jako heslo jinde. Bez odpovědi nasazení (`npm run nasadit`, `nasadit-cloudflare`, `deploy-caprover`)
  skončí chybou; otevřený web jen výslovně přes `"otevreny": true` v `prihlaseni`.
  Je to lehká ochrana proti náhodným návštěvníkům, ne bankovní zabezpečení – citlivé věci na web nepatří.
- `uvod.foto` = klíč obrázku ve `vyrezy/` (ulož přes `vyrez.py`).
- Fotky: portréty předků (`dokumenty.json` → `portret`) a fotky obcí a kostelů (`mista.json` → `foto`, nástroj `foto_mista.py`).
  U fotek z Commons musí zůstat popis s autorem a licencí – web ho ukazuje pod fotkou.
- `pribeh`: `menu` a `tlacitko` pojmenuj podle hlavního rodu („Příběh Novákových“), `rod` = číslo rodu (8–15).
  Bez vyplněného `uvod` ukáže úvodní stránka aspoň název a `lead` příběhu. Viz `pribehy.md`.
- Šablona `web.json` je prázdná – název nastav hned, jak znáš příjmení výchozí osoby (`kontrola.py` hlásí zbytky ukázky).
- `mapa.podklad`: `osm` (výchozí, OpenStreetMap bez klíče), `mapy.cz` (základní mapa Mapy.com) nebo `mapy.cz-outdoor`
  (turistická). Pro Mapy.com založ uživatel účet na developer.mapy.com a API klíč dá do `mapa.klic`. **Klíč je na webu
  veřejný** (prohlížeč ho posílá s každou dlaždicí) – v účtu Mapy.com ho ať omezí na doménu webu (a `localhost` pro
  náhled). Bez klíče web použije OpenStreetMap a `kontrola.py` upozorní. Klíč nikdy nepiš do kódu webu, jen do `web.json`.
- `citlive_schvaleno`: seznam úryvků textu, které uživatel na webu schválil (např. `["oběsil se ve stodole"]`) –
  `kontrola.py` je pak nehlásí jako `CITLIVÉ`. Úryvek musí obsahovat hlášené slovo; když se text změní, hlásí se znovu.

## Zveřejnění na Netlify (výchozí, zdarma)
1. Uživatel si založí účet na netlify.com (stačí přihlášení přes Google/GitHub) – udělá sám.
2. Přihlášení CLI (otevře prohlížeč) – dej uživateli: `! cd web && npx -y netlify-cli@latest login`.
   Když `!` nejde (cloudové prostředí): `npx -y netlify-cli@latest login --request "Rodokmen"` vypíše odkaz a číslo
   lístku – uživatel odkaz otevře a schválí, pak `npx -y netlify-cli@latest login --check <lístek>`.
3. Založení webu a propojení složky (interaktivní, jednou) – dej uživateli:
   `! cd web && npx -y netlify-cli@latest sites:create` (zvolí tým a název → adresa `https://<název>.netlify.app`),
   případně `npx netlify-cli link`, pokud web už existuje. Je-li uživatel už přihlášený, jde web založit i bez dotazů
   (můžeš spustit sám): `cd web && npx -y netlify-cli@latest sites:create --name <název> --account-slug <tým>`.
   **Windows:** když `!` běží ve Windows PowerShellu 5.1 (`&&` tam nefunguje a `npx` blokuje Execution Policy), ať uživatel
   otevře PowerShell 7 nebo Příkazový řádek, přejde do složky `web` a spustí `npx -y netlify-cli@latest login` (a `sites:create`).
4. Nasazení: `cd web && npm run nasadit` (můžeš spustit sám; vypíše adresu webu).
5. Ověř: otevři adresu **v anonymním okně** → musí se ukázat rodinná přihlašovací otázka; po správné odpovědi web.
   Ukáže-li se místo ní přihlášení k Netlify (401, „Login Redirect“), zdědil web ochranu týmu („Team protection“).
   Uživatel ji vypne v administraci webu: Project configuration → Access & security → Visitor access. Web pak chrání
   rodinná otázka – proto znovu ověř v anonymním okně, že se ukáže.
   Přihlášení zajišťuje Netlify Edge Function `web/netlify/edge-functions/brana.js` (generuje ji export).
Další aktualizace = jen `npm run nasadit`. Vlastní doménu lze nastavit v administraci Netlify.

**Pozor:** „Netlify Drop“ (přetažení složky v prohlížeči) neumí Edge Functions → web by byl bez přihlášení. Nepoužívat.

## Zveřejnění na Cloudflare Pages (alternativa, zdarma)
Stejná brána s rodinnou otázkou jako na Netlify: export vyrobí `web/functions/_middleware.js` (Pages Functions,
otisk odpovědi v cookie), nepřihlášenému ukáže přihlašovací stránku s kódem 401 na původní adrese.
1. Uživatel si založí účet na cloudflare.com – udělá sám.
2. Přihlášení CLI (otevře prohlížeč) – dej uživateli: `! cd web && npx -y wrangler@4.150.0 login`.
3. Založení projektu (jednou; můžeš spustit sám, když je přihlášený):
   `cd web && npx -y wrangler@4.150.0 pages project create <název> --production-branch main` → adresa `https://<název>.pages.dev`.
4. Nasazení: `cd web && CF_PAGES_PROJECT=<název> npm run nasadit-cloudflare`. Název projektu se čte **jen z proměnné
   prostředí** `CF_PAGES_PROJECT` (Windows PowerShell: `$env:CF_PAGES_PROJECT="<název>"; npm run nasadit-cloudflare`
   nefunguje – `$CF_PAGES_PROJECT` v npm skriptu rozbalí jen bash/zsh; na Windows spusť nasazení z Git Bash).
   Skript se spouští ve `web/`: wrangler bere složku `functions/` z aktuální složky a nahraje ji vedle `dist/`.
5. Ověř v anonymním okně, že se ukáže rodinná otázka (jako u Netlify, krok 5).
Místo rodinné otázky lze použít **Cloudflare Access** (Zero Trust → Access → aplikace pro doménu `*.pages.dev`,
přihlášení e-mailem s jednorázovým kódem jen pro vyjmenované adresy) – silnější, ale každého příbuzného musí uživatel
přidat; rodinná otázka pak může zůstat jako druhá vrstva.

## Náhled v Claude desktop
Projekt má `.claude/launch.json` – náhled webu v Claude desktop spustí `npm --prefix web run dev` (port 4321). Data se
předtím musí vyexportovat (`cd web && npm run data`). Když náhled nenaběhne (třeba na Windows, kde je `npm` jako `npm.cmd`),
zkus v `launch.json` `"runtimeExecutable": "node"` a `"runtimeArgs": ["web/node_modules/astro/bin/astro.mjs", "dev", "--root", "web"]`
(Astro 7 má spouštěč `astro.mjs`, ne `astro.js`). Server běží jen na tomto počítači – nepřidávej `--host`.

## Vlastní server (pokročilé)
- Docker: `web/Dockerfile` (build Astro → nginx s `nginx.conf` z `nginx.sablona.conf`). Před buildem image vždy `npm run data`.
- CapRover: `npm run deploy-caprover` (vyžaduje nainstalovaný a přihlášený `caprover` CLI).

## Úpravy vzhledu
Styly `web/src/styles/global.css` (barvy v `:root`), rozložení `web/src/layouts/Base.astro`, stránky `web/src/pages/`.
Barvy rodů jsou v `tools/export_web.py` (`LINE_COLORS`) a `tools/fan_chart.py` (`BASE`). Upravuj jen na přání uživatele
a po úpravě zkontroluj web na mobilu i počítači.

## Vějíř jako plakát
`python3 -I tools/fan_chart.py vystupy/` → SVG a HTML (a PNG, je-li nainstalovaný Google Chrome, na Windows i Microsoft Edge) k tisku.

## Aktualizace staršího projektu
Znovu spusť `python3 -I SKILL_DIR/tools/novy_projekt.py <složka projektu>`. Data (`data/`, výřezy) zůstanou, `tools/` se přepíše
a soubory ve `web/`, které se liší od nové šablony, taky – staré verze uloží do `pracovni/zaloha_web_<datum>/` a vypíše jejich seznam.
Upravoval-li jsi s uživatelem vzhled (styly, stránky), převezmi úpravy ze zálohy (porovnej soubory) a ověř web. Pak ve `web/`
`npm install` a `npm run data`. Starou šablonu přihlášení `export_web.py` odmítne s výzvou k aktualizaci.
Projekt z verze do 0.5.0 s matrikami z ARON: spusť i `python3 -I tools/aron_img.py opravit-odkazy` (odkazy na snímky
vedly na první snímek svazku).
