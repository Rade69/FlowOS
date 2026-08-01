# FlowOS — nalog za pi agenta: priprema review bundle paketa

## Cilj

Nakon završetka svakog `FLOW-xxx` zadatka pripremi jedan kompaktan paket za nezavisni pregled implementacije.

Paket mora omogućiti provjeru:

1. da li je zadatak urađen u skladu sa planom;
2. da li je poštovana arhitektura `View → Controller → Services`;
3. da li je izmjena ograničena na dogovoreni scope;
4. da li su testovi i verifikacija stvarni;
5. da li je agent report usklađen sa kodom;
6. da li postoje regresije, arhitektonska odstupanja ili nedovršene stavke.

Ne šalji fajlove pojedinačno. Generiši jedan `.zip` paket po zadatku.

---

# 1. Lokacija i naziv paketa

Kreiraj direktorij:

```text
review_bundles/FLOW-XXX/
```

Primjer:

```text
review_bundles/FLOW-103/
```

Na kraju napravi:

```text
review_bundles/FLOW-103.zip
```

Ako isti zadatak ima više iteracija:

```text
review_bundles/FLOW-103-r2.zip
review_bundles/FLOW-103-r3.zip
```

Ne prepisuj prethodni paket bez razloga.

---

# 2. Obavezna struktura paketa

```text
FLOW-103/
├── README_REVIEW.md
├── agent_report.md
├── project_room.md                 # samo ako postoji
├── task_contract.md                # ako postoji
├── plan_item.md
├── git_status.txt
├── git_log.txt
├── changed_files.txt
├── changes.diff
├── verify_results.txt
├── test_results.txt
├── lint_results.txt
├── mypy_results.txt
├── architecture_check.txt
├── architecture_tree.txt
├── commits.txt
├── screenshots/                    # samo ako je GUI mijenjan
├── source/
│   └── relevantni puni fajlovi
└── metadata/
    ├── environment.txt
    ├── commands_run.txt
    └── bundle_manifest.txt
```

Sekcije bez sadržaja ne briši nasumično. Ako nešto nije primjenjivo, navedi `N/A` i razlog.

---

# 3. README_REVIEW.md

Kreiraj kratak pregled paketa:

```markdown
# Review bundle — FLOW-103

## Zadatak
FLOW-103 — Service runtime

## Status
OK | PARCIJALNO | BLOKIRANO

## Scope
Koji moduli i fajlovi su mijenjani.

## Šta je urađeno
Kratko i konkretno.

## Šta nije urađeno
Sve otvorene stavke.

## Usklađenost sa planom
- Završeni acceptance kriterijumi
- Nezavršeni acceptance kriterijumi
- Rad van plana

## Arhitektonski slojevi
- View: izmijenjen / nije izmijenjen
- Controller: izmijenjen / nije izmijenjen
- Services: izmijenjen / nije izmijenjen
- Prekršene granice: nema / opis

## Verifikacija
Koje komande su pokrenute i rezultat.

## Poznati rizici
Lista.

## Gdje je rad stao
Konkretno stanje.

## Sljedeći korak
Jedna konkretna akcija.

## Prije nastavka provjeriti
Lista ili `Nema`.
```

---

# 4. Agent report

Kopiraj tačan završni agent report u:

```text
agent_report.md
```

Mora sadržavati najmanje:

- datum;
- agent/model;
- scope;
- impact analizu;
- reprodukciju prije izmjene, ako je bugfix;
- šta je urađeno;
- zašto;
- kako;
- šta nije dirano;
- verifikaciju;
- nezavisnu provjeru, ako je potrebna;
- pronađene probleme;
- odbačene opcije;
- konflikte;
- commitove;
- rizike;
- follow-up;
- potrebnu korisničku potvrdu;
- usklađenost sa planom;
- gdje je rad stao;
- sljedeći konkretan korak;
- šta mora biti provjereno prije nastavka.

Ne piši novi uljepšani izvještaj samo za bundle. Uključi isti report koji je commitovan u repo.

---

# 5. Plan i task kontekst

## plan_item.md

Navedi:

```markdown
# Plan item

- ID:
- Naziv:
- Faza:
- Status prije rada:
- Predloženi status poslije rada:
- Zavisnosti:
- Risk level:

## Acceptance kriterijumi
- [x] ...
- [ ] ...

## Dokaz po kriterijumu
- Kriterijum:
  - dokaz:
  - rezultat:
```

## task_contract.md

Ako postoji TaskContract, kopiraj ga u cijelosti.

## project_room.md

Ako je zadatak HIGH/CRITICAL ili teško reverzibilan, uključi odgovarajući project room u cijelosti.

---

# 6. Git dokazi

## git_status.txt

Pokreni:

```bash
git status --short
git status --branch --porcelain=v2
```

Sačuvaj izlaz.

## git_log.txt

Pokreni:

```bash
git log --oneline --decorate -20
```

## commits.txt

Navedi sve commitove koji pripadaju zadatku:

```text
<hash> <poruka>
```

Ako nema commita, napiši razlog. To se smatra otvorenim rizikom.

## changed_files.txt

Pokreni odgovarajuću komandu između početnog i završnog commita:

```bash
git diff --name-status <base_commit>..<result_commit>
```

Ako zadatak još nije commitovan:

```bash
git diff --name-status
git diff --name-status --cached
```

## changes.diff

Generiši puni diff:

```bash
git diff --binary <base_commit>..<result_commit>
```

Ako zadatak nije potpuno commitovan, uključi i staged i unstaged diff.

Diff mora obuhvatiti samo scope zadatka. Ako sadrži tuđi WIP, jasno označi problem i ne pokušavaj ga sakriti.

---

# 7. Puni izvorni fajlovi

U `source/` kopiraj:

1. sve izmijenjene produkcione fajlove;
2. sve izmijenjene testove;
3. direktno povezane interfejse, DTO modele i composition root fajlove;
4. migracije, ako su mijenjane;
5. konfiguracione fajlove koji određuju ponašanje izmjene.

Ne kopiraj samo diff fragmente. Potreban je cijeli sadržaj relevantnih fajlova.

Za širi arhitektonski zadatak uključi i reprezentativne fajlove iz susjednih slojeva koji dokazuju smjer zavisnosti.

Primjer:

```text
source/
├── src/flowos/service/services/runtime/service.py
├── src/flowos/service/controllers/http/runtime_routes.py
├── src/flowos/shared/contracts/runtime.py
├── src/flowos/service/composition_root.py
├── tests/unit/service/test_runtime_service.py
└── tests/contract/test_runtime_api.py
```

---

# 8. Testovi i verifikacija

## verify_results.txt

Pokreni:

```bash
python scripts/verify.py
```

Sačuvaj:

- punu komandu;
- exit code;
- stdout;
- stderr;
- trajanje.

Ako skripta ne postoji ili ne radi, napiši to jasno. Ne zamjenjuj je tihim ručnim izborom testova bez objašnjenja.

## test_results.txt

Pokreni relevantne pytest testove, a zatim po mogućnosti cijeli test skup:

```bash
pytest -q
```

Za ciljane testove navedi tačnu komandu.

Sačuvaj:

- broj prošlih;
- broj palih;
- broj preskočenih;
- puni naziv svakog palog testa;
- traceback relevantnog kvara.

## lint_results.txt

```bash
ruff check .
ruff format --check .
```

## mypy_results.txt

```bash
mypy src
```

Ako se mypy pokreće drugim projektno definisanim putem, koristi kanonsku komandu iz `pyproject.toml` ili `scripts/verify.py`.

## architecture_check.txt

Pokreni import-linter ili projektni AST boundary test.

Mora se vidjeti:

- korištena komanda;
- rezultat;
- koja pravila su provjerena.

---

# 9. Struktura relevantnog projekta

U `architecture_tree.txt` uključi:

```text
top-level strukturu
relevantne podfoldere do 3–4 nivoa
```

Isključi:

```text
.git/
.venv/
venv/
__pycache__/
dist/
build/
artifacts/
logs/
backups/
```

Ne šalji samo generički tree cijelog repoa ako je ogroman. Fokusiraj se na relevantne module, ali uključi dovoljno konteksta za provjeru troslojne arhitekture.

---

# 10. GUI promjene

Ako je View ili izgled mijenjan, uključi folder:

```text
screenshots/
```

Obavezno:

- screenshot prije;
- screenshot poslije;
- stvarni render aplikacije;
- najmanje 1920×1080 i 1600×900, ako je relevantno;
- screenshot error/empty/loading stanja ako su mijenjana;
- DPI podatak.

Offscreen render nije dovoljan ako promjena zavisi od stvarnog desktop prikaza.

U `README_REVIEW.md` navedi šta korisnik treba vizuelno potvrditi.

---

# 11. Environment i komande

## metadata/environment.txt

Uključi:

```text
OS
Python verzija
PySide6 verzija
FastAPI verzija
SQLAlchemy verzija
Git verzija
aktivni branch
commit prije rada
commit poslije rada
```

Ne uključuj:

- API ključeve;
- tokene;
- lozinke;
- sadržaj `.env`;
- privatne putanje koje nisu potrebne;
- cijeli environment dump.

## metadata/commands_run.txt

Navedi hronološki sve važne komande:

```text
git status --short
pytest ...
ruff ...
mypy ...
python scripts/verify.py
git diff ...
```

## metadata/bundle_manifest.txt

Navedi svaki fajl u bundle-u, njegovu veličinu i SHA-256 hash.

---

# 12. Šta ne uključivati

Ne uključuj:

```text
.git/
.venv/
venv/
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
dist/
build/
node_modules/
velike baze podataka
produkcione korisničke podatke
API ključeve
credentials
nefiltrirane logove sa tajnama
privatno rezonovanje modela
cijeli stdout ako sadrži osjetljive podatke
```

SQLite bazu uključi samo ako je napravljena anonimna test fixture baza i stvarno je potrebna za reprodukciju.

---

# 13. Sigurnosna provjera prije pakovanja

Prije kreiranja ZIP-a:

1. pregledaj sve fajlove za `password`, `secret`, `token`, `api_key`;
2. potvrdi da nema `.env` fajlova;
3. potvrdi da nema korisničkih produkcionih podataka;
4. potvrdi da logovi ne sadrže tajne;
5. potvrdi da bundle ne sadrži `.git` ni virtual environment;
6. potvrdi da je diff vezan za tačan zadatak;
7. potvrdi da su puni relevantni fajlovi uključeni.

Ako pronađeš potencijalnu tajnu, ne pakuj dok je ne rediguješ ili ne ukloniš.

---

# 14. Kreiranje ZIP paketa

Na Windows PowerShell-u možeš koristiti:

```powershell
Compress-Archive `
  -Path review_bundles/FLOW-103/* `
  -DestinationPath review_bundles/FLOW-103.zip `
  -Force
```

Na Pythonu možeš napraviti projektnu skriptu:

```text
scripts/create_review_bundle.py
```

Preporučena komanda:

```bash
python scripts/create_review_bundle.py FLOW-103
```

Skripta ne smije automatski uključivati cijeli repo bez allowliste i exclude pravila.

---

# 15. Kada poslati cijeli repo snapshot

Review bundle je dovoljan za lokalne, ograničene zadatke.

Uz bundle napravi i sanitized repo ZIP kada zadatak dira:

- arhitekturu više slojeva;
- composition root;
- modele baze i migracije;
- shared contracts;
- veliki broj modula;
- servisni lifecycle;
- wrapper + servis + GUI zajedno;
- zabranjene/ciklične zavisnosti;
- širi refactor;
- HIGH/CRITICAL oblast.

Naziv:

```text
FlowOS-repo-snapshot-FLOW-103.zip
```

I dalje isključi sve iz sekcije „Šta ne uključivati“.

---

# 16. Završna provjera

Prije predaje potvrdi:

```text
[ ] agent_report je uključen
[ ] plan item i acceptance kriterijumi su uključeni
[ ] project_room je uključen ako je potreban
[ ] git status i log su uključeni
[ ] puni diff je uključen
[ ] svi relevantni puni fajlovi su uključeni
[ ] verify rezultat je uključen
[ ] testovi su uključeni
[ ] Ruff rezultat je uključen
[ ] mypy rezultat je uključen
[ ] architecture check je uključen
[ ] GUI screenshotovi su uključeni ako je primjenjivo
[ ] nema tajni ni produkcionih podataka
[ ] bundle_manifest postoji
[ ] ZIP se može otvoriti
```

---

# 17. Završni odgovor korisniku

Nakon generisanja paketa odgovori:

```text
STATUS: OK | PARCIJALNO | BLOKIRANO
REVIEW BUNDLE: review_bundles/FLOW-XXX.zip
REPO SNAPSHOT: putanja | N/A
ZADATAK: FLOW-XXX
COMMITOVI: lista
VERIFY: prošao | nije prošao
TESTOVI: rezultat
OTVORENI PROBLEMI: lista | Nema
TAJNE/PRODUKCIONI PODACI: nisu uključeni
```

Ne počinji sljedeći `FLOW-xxx` zadatak ako korisnik traži nezavisni pregled trenutne cjeline.
