---
flowos_report_version: 1
agent: claude
model: claude-sonnet-5
session_id: unknown
report_type: review
tasks:
  - unassigned
commits: []
created_at: 2026-08-11T13:30:59+02:00
---

# AgentReport v2 — Phase 1 — formalni nezavisni review

## Datum

2026-08-11

## Agent / model / sesija

- Agent: claude (Claude Code)
- Model: claude-sonnet-5
- Sesija: unknown

## Scope

Formalni nezavisni review necommitovanih izmjena "AgentReport v2 — Phase 1"
(codex/gpt-5, `agent_reports/2026-08-11_agent-report-v2-phase-1.md`). Kod NIJE
mijenjan, migracija NIJE pravljena, commit NIJE napravljen. Sve tvrdnje su
provjerene protiv stvarnog koda na disku, ne protiv teksta izvještaja.

## Pregled kompletnog diff-a — potvrda scope-a

```text
git status --short
 M AGENTS.md
 M CLAUDE.md
 M src/flowos/service/services/infrastructure/persistence/models.py
 M src/flowos/service/services/infrastructure/persistence/report_models.py
 M src/flowos/service/services/plan_progress.py
 M src/flowos/service/services/reports/service.py
?? agent_reports/2026-08-11_agent-report-v2-phase-1.md
?? alembic/versions/a17e4c8f9b21_agent_report_v2_bindings.py
?? tests/integration/test_agent_report_v2.py
```

`AGENTS.md`/`CLAUDE.md` izmjene su isključivo auto-generisani GitNexus blok
(naziv repoa FolowOS→FlowOS, osvježen broj simbola/relacija/execution flows,
unutar `<!-- gitnexus:start -->...<!-- gitnexus:end -->` markera) — bezopasno,
ne dira pravila. Nema neželjenih izmjena van najavljenog scope-a: samo
`AgentReport`/`AgentReportBindingLink` ORM+migracija, `ReportService`,
`SessionTaskBinding.report_links` relationship (dodatak, ne izmjena postojećih
polja), `PlanProgressService` matrica, i novi test fajl.

## 1. `AgentReport` nova polja — `report_type`, `work_status`

Nullable `String(50)`/`String(20)` kolone, bez defaulta, bez backfill-a.
Postojeći redovi ostaju `NULL`. `ReportService.create_draft()` i
`update_report()` prihvataju oba polja; `work_status` se validira isključivo
kroz `_validate_work_status()` (`{"completed", "partial", "blocked"}` ili
`None`). Potvrđeno grep-om: `work_status =` se dodjeljuje SAMO unutar
`reports/service.py` — nema drugog write puta u `src/`. Test
`test_legacy_report_and_implementation_semantics_remain_supported` potvrđuje i
legacy `NULL` slučaj i validaciju (`ValueError` za `work_status="verified"`).
Ovaj dio je ispravan i dokazan.

## 2. `AgentReportBindingLink`

FK: `report_id → agent_reports.id ON DELETE CASCADE`,
`session_task_binding_id → session_task_bindings.id ON DELETE RESTRICT`.
Unique constraint `(report_id, session_task_binding_id)` postoji i u ORM-u i u
migraciji, konzistentno. `SessionTaskBinding.report_links` je čist dodatak
(nova `relationship`, ne dira postojeća polja/constraints iz već prihvaćenog
modela). Migracija `upgrade()`/`downgrade()` su simetrični — downgrade briše
indekse pa tabelu pa nove kolone, obrnutim redoslijedom od upgrade-a. Nema
backfill-a, nema pretpostavki o postojećim podacima. Ovaj dio je ispravan.

## 3. `ReportService.link_report_to_binding()`

Odbija nepostojeći report, nepostojeći binding, binding druge sesije, i
duplikat (provjera prije mutacije). Testovi
`test_report_links_one_and_multiple_bindings_and_rejects_duplicates` i
`test_report_rejects_binding_from_another_session` su stvarni (ne mockovani) i
prolaze. Ispravno.

## 4. `ReportService._reopen_plan_item()` i legacy fallback

Ispravno zatvara originalni bug (`AgentSession.plan_item_id` kao autoritet) —
sada koristi eksplicitne `AgentReportBindingLink` zapise kad postoje, a legacy
fallback zahtijeva TAČNO JEDAN relevantan istorijski binding za cijelu sesiju,
inače ne radi ništa i piše warning. **Ali** unutar rezolucije `binding.task_id
→ Task.plan_item_id`, kod radi **živi (trenutni) lookup** `Task` reda u
trenutku verdicta, ne u trenutku kad je binding bio aktivan. Ovo je zaseban,
dublji nalaz — vidi F1 ispod.

## 5. `PlanProgressService` transition matrica

Vidi F2 ispod — potvrđen konkretan, dokazan problem.

## 6. Regression testovi

Pregledani i pokrenuti `tests/integration/test_agent_report_v2.py` (9 novih
testova) i `tests/unit/test_reports.py` (6 postojećih) — svi genuini (nisu
mockovani), stvarno vježbaju tvrđeno ponašanje:

- `test_linked_report_reopens_original_plan_item_not_current_session_pointer` —
  stvarno reprodukuje A→B switch + report vezan za A + `NEEDS_WORK` na starom
  reportu → provjerava da se reopenuje A, ne B. PROLAZI.
- `test_legacy_report_with_multiple_bindings_does_not_use_current_pointer` —
  potvrđuje fail-safe fallback (nema reopen-a kad je binding istorija
  dvosmislena). PROLAZI.
- `test_multi_binding_report_reopens_each_unique_plan_item` — multi-target
  slučaj, dedup preko `set`. PROLAZI.
- `test_report_rejects_binding_from_another_session` — cross-session
  odbijanje. PROLAZI.
- `test_deleting_report_cascades_links_but_linked_binding_is_restricted` — FK
  CASCADE (report brisanje briše linkove) i RESTRICT (binding se ne može
  obrisati dok ima link) — oba ponašanja stvarno provjerena preko
  `IntegrityError`. PROLAZI.

Nijedan test ne pokriva scenario iz F1 (Task.plan_item_id drift) niti scenario
iz F2 (generic `/start` endpoint na IMPLEMENTED/VERIFIED stavci) — oba su sama
po sebi nalazi, obrađeni ispod.

## 7. `python scripts/verify.py`

```text
Prošlo: 7/7
[PASS] VERIFIKACIJA PROŠLA
```

Dodatno pokrenuto ciljano (izvan standardnog verify.py, radi šireg konteksta
oko F2):

```text
python -m pytest tests/integration/test_agent_report_v2.py tests/unit/test_reports.py \
  tests/unit/test_plan_progress.py tests/integration/test_plan_progress_api.py -v
→ 62 passed, 1 warning
```

Sve postojeće poznate provjere prolaze — što je i očekivano, jer F1 i F2 nisu
regresije koje postojeći testovi hvataju, nego rupe koje postojeći testovi
NIKAD nisu ni pokrivali.

---

# CODE FINDINGS

```text
F1 — HIGH
Task.plan_item_id "live lookup" umjesto istorijskog snapshot-a u _reopen_plan_item()

Dokaz:
Probom (izolovano, van repoa) reprodukovan tačno scenario iz naloga:
  T1: Task A.plan_item_id = ITEM_1; SessionTaskBinding → Task A; report linkovan
      na taj binding preko AgentReportBindingLink.
  T2: TaskService.update_task(task_a.id, plan_item_id=ITEM_2.id) — Task A sada
      pokazuje na ITEM_2.
  T3: ReportService.set_verdict(report.id, "NEEDS_WORK") na STAROM reportu.

Rezultat probe:
  item_1 (ISTORIJSKI ispravan target) status = IMPLEMENTED  (netaknuto)
  item_2 (trenutni/live Task.plan_item_id) status = IN_PROGRESS  (pogrešno reopenovan)

*** BUG POTVRDJEN: reopenovan je POGRESAN (trenutni) plan item, ne istorijski. ***

Uzrok: u _reopen_plan_item(), grana `elif binding.task_id:` radi
`task = self._session.get(Task, binding.task_id)` i čita `task.plan_item_id`
U TRENUTKU VERDICTA, ne u trenutku kad je binding bio aktivan segment sesije.
AgentReportBindingLink → SessionTaskBinding daje tačan ISTORIJSKI binding, ali
Task.plan_item_id nije istorijski podatak — to je mutabilan "trenutni" pointer
(potvrđeno: TaskService.update_task() dozvoljava promjenu plan_item_id bez
ikakvog traga o prethodnoj vrijednosti). Dakle AgentReportBindingLink →
SessionTaskBinding → Task.plan_item_id je autoritativan lanac SAMO za
session_id/task_id/binding period, ne i za plan_item_id ako se Task naknadno
premjesti u drugu fazu plana.

Reachability danas: Nije trenutno dostižno kroz ijedan ožičen produkcioni put —
HTTP `PATCH /tasks/{id}` hardkodira `plan_item_id=None` (potvrđeno čitanjem
tasks.py:76), pa Task.plan_item_id se danas NE MOŽE promijeniti preko API-ja.
`link_report_to_binding()` takođe nema produkcionog pozivaoca (vidi Known
Limitation A). Dakle oba preduslova za ovaj scenario su danas neožičena.

Zašto je i dalje HIGH, ne LOW: Ovo je TAČNO ista klasa greške (mutabilan
"trenutni" pointer tretiran kao istorijski autoritet) koju je cijela ova faza
postojala da ukloni — samo jedan hop dalje (Task.plan_item_id umjesto
AgentSession.plan_item_id). Čim se doda bilo koji od dva nedostajuća dijela
(task reassignment endpoint, ili YAML ingestion koji zove
link_report_to_binding), bug postaje tiho aktivan bez ikakve dalje izmjene
ovog koda. Regresija bi bila neprimjetna jer testovi danas ne pokrivaju ovaj
put (potvrđeno — nema testa).

Posljedica: Report koji je istorijski opisivao rad na ITEM_1 bi, nakon što
neko premjesti Task u drugu fazu plana, prilikom NEEDS_WORK/REJECTED verdicta
tiho reopenovao pogrešnu (trenutnu) plan stavku, ne onu na koju se report
stvarno odnosio — identičan simptom kao originalni bug koji je ova faza
trebala zatvoriti.

Preporuka (NIJE implementirano):
Predlog iz naloga (resolved_plan_item_id na AgentReportBindingLink) je
ispravnog OBLIKA, uz jednu preciznu izmjenu: snapshot treba uzeti u trenutku
link_report_to_binding() poziva (ne naknadno, ne lijeno pri verdictu), i to je
NAJMANJA arhitektonski ispravna korekcija koja ne dira već prihvaćeni
SessionTaskBinding model:

  AgentReportBindingLink
  - report_id
  - session_task_binding_id
  - resolved_plan_item_id   # nullable, snapshot uzet PRI LINKOVANJU

link_report_to_binding() bi u istom pozivu resolvovao trenutni
binding.plan_item_id ili Task.plan_item_id (ista logika koja danas postoji u
_reopen_plan_item()) i zamrznuo rezultat. _reopen_plan_item() bi onda čitao
ISKLJUČIVO resolved_plan_item_id sa linka, nikad ponovo Task iz baze.

Ostaje rezidualni, uži prozor rizika: ako se Task.plan_item_id promijeni IZMEĐU
trenutka kad je binding bio aktivan i trenutka kad se report kasnije linkuje
(što bi realno trebalo biti blizu jedno drugom, jer link pravi buduća
ingestion faza uskoro nakon što report referencira binding) — snapshot bi i
dalje mogao uhvatiti već-promijenjenu vrijednost. Potpuno uklanjanje tog
prozora zahtijeva pravu Task-nivoa istoriju polja (npr. TaskFieldHistory), što
je veći, danas neopravdan scope po istom principu koji je ova faza već
primijenila na SessionTaskBinding ("ne izmišljati istoriju koju baza nema").
Predložena korekcija zatvara praktično relevantan dio rizika (verdict može
doći sedmicama nakon linka) uz minimalan diff.

NE mijenjati SessionTaskBinding model za ovo — nije potrebno i predlog
korisnika to eksplicitno izbjegava s razlogom.
```

```text
F2 — HIGH
Globalno proširenje ALLOWED_TRANSITIONS otvara IMPLEMENTED/VERIFIED → IN_PROGRESS
svakom pozivaocu generičkog plan-item status API-ja, ne samo report-verdict toku

Dokaz:
git diff src/flowos/service/services/plan_progress.py:
  "IMPLEMENTED": {"VERIFIED", "BLOCKED"} → {"IN_PROGRESS", "VERIFIED", "BLOCKED"}
  "VERIFIED": {"ACCEPTED", "REJECTED", "BLOCKED"} → {"IN_PROGRESS", "ACCEPTED", "REJECTED", "BLOCKED"}

ALLOWED_TRANSITIONS je JEDINA, DIJELJENA matrica — potvrđeno grep-om da je
validate_transition() pozvan iz ČETIRI različita mjesta:
  - src/flowos/service/services/sessions/completion.py (auto-tranzicije)
  - src/flowos/service/controllers/http/plan_progress.py:102 (_do_transition,
    generička HTTP akcija, to_status je proizvoljan poziv)
  - src/flowos/service/services/reports/service.py (_reopen_plan_item, novi kod)

`POST /plan-items/{id}/start` (postojeći, već korišten endpoint) poziva
_do_transition(item_id, "IN_PROGRESS", ...) BEZ ikakvog konteksta o reportu,
bindingu ili verdictu.

Probom potvrđeno (izolovan FastAPI TestClient, samo plan_progress router):
  PlanItem status = IMPLEMENTED
  POST /plan-items/item1/start {"reason": "nasumican poziv, bez ikakve veze sa
  report verdictom"}
  → HTTP 200, status.item1 = IN_PROGRESS

Prije ove izmjene bi isti poziv vratio HTTP 409 (IMPLEMENTED → IN_PROGRESS
nije bilo u matrici).

Test coverage provjera: tests/integration/test_plan_progress_api.py
test_invalid_transition_returns_409 testira NOT_STARTED→ACCEPTED (potpuno
druga tranzicija), ne IMPLEMENTED/VERIFIED→IN_PROGRESS. Nema nijednog
postojećeg ili novog testa koji bi ovu promjenu uhvatio — potvrđeno da
pun pytest suite (62 testa, uključujući sve plan_progress testove) i
scripts/verify.py (7/7) prolaze i dalje.

Posljedica: Bilo koji klijent generičkog plan-progress API-ja (GUI dugme,
skripta, budući integracijski kod) sada može ručno vratiti IMPLEMENTED ili
VERIFIED stavku u IN_PROGRESS sa proizvoljnim slobodnim `reason` tekstom, bez
ikakve veze sa AgentReport verdictom, bez linka na report koji to opravdava.
Ovo tiho oslabljuje state-machine garanciju da IMPLEMENTED/VERIFIED → IN_PROGRESS
dolazi ISKLJUČIVO iz governed report-verdict toka — tačno ono što je audit
sloj (AgentReportBindingLink, resolved plan item) trebao osigurati kao
kontrolisan mehanizam.

Preporuka (NIJE implementirano), dvije opcije, korisnik/Codex bira:

Opcija A (uža, preferirana): Ne širiti dijeljenu ALLOWED_TRANSITIONS globalno.
Dodati validate_transition() opcioni keyword-only parametar, npr.
`allow_verdict_reopen: bool = False`. IMPLEMENTED/VERIFIED → IN_PROGRESS ostaje
DOZVOLJENO u matrici samo kad je `allow_verdict_reopen=True`; taj flag postavlja
ISKLJUČIVO ReportService._reopen_plan_item(), nikad _do_transition()/HTTP
akcije. Minimalan diff, jedna dijeljena funkcija, jasno imenovan izuzetak vidljiv
na mjestu poziva.

Opcija B: _reopen_plan_item() ne ide kroz generički validate_transition()
uopšte — dobija sopstvenu, usko-obimnu mutaciju (status + timestamp + audit
PlanProgressEvent) koja replicira samo ono što je javnom API-ju POTREBNO, bez
diranja dijeljene ALLOWED_TRANSITIONS matrice. Više koda dupliciranog, ali
nulti rizik da se generička matrica nehotice proširi za sve pozivaoce.

Bilo koja opcija zahtijeva i novi regression test koji EKSPLICITNO potvrđuje da
POST /plan-items/{id}/start i dalje vraća 409 na IMPLEMENTED/VERIFIED stavci —
danas takav test ne postoji, pa bi regresija ponovo prošla neopaženo.
```

---

# TEST FINDINGS

```text
F3 — MEDIUM
Nema regresionog testa za F1 (Task.plan_item_id drift nakon linkovanja)

Dokaz: grep nad tests/integration/test_agent_report_v2.py ne pronalazi test
koji mijenja Task.plan_item_id nakon linkovanja i provjerava koja se stavka
reopenuje. Scenario je dokazan isključivo ad-hoc probom u ovom review-u, ne
postojećim regresionim testom.

Posljedica: Ako se F1 popravi (ili ako ostane nepopravljen a preduslovi kasnije
postanu dostižni), nema automatske zaštite koja bi uhvatila regresiju.

Preporuka: dodati test analogan
test_linked_report_reopens_original_plan_item_not_current_session_pointer, ali
sa TaskService.update_task(plan_item_id=...) između linkovanja i verdicta.
```

```text
F4 — vidi F2 (isti nalaz, testna dimenzija)
Nema regresionog testa koji brani da generički /plan-items/{id}/start ostane
zabranjen na IMPLEMENTED/VERIFIED stavci nakon proširenja matrice.

Dokaz: vidi F2. tests/integration/test_plan_progress_api.py::test_invalid_transition_returns_409
testira nepovezan slučaj (NOT_STARTED→ACCEPTED skip), ne ovaj.

Preporuka: dodati test koji direktno poziva POST /plan-items/{id}/start (ili
/verify, ako se doda ekvivalentna akcija za VERIFIED) na IMPLEMENTED/VERIFIED
stavci i očekuje 409, NEZAVISNO od toga koja opcija (A/B) iz F2 bude izabrana
za popravku.
```

Ostali novi testovi (linkovanje, cross-session odbijanje, CASCADE/RESTRICT,
legacy fallback, multi-binding) su svi provjereni kao genuini i prolaze — bez
nalaza.

---

# MIGRATION FINDINGS

```text
F5 — MEDIUM
Nema DB CHECK constraint za work_status (i report_type) vrijednosti

Dokaz: alembic/versions/a17e4c8f9b21_agent_report_v2_bindings.py dodaje
`report_type`/`work_status` kao obične nullable String kolone bez
CheckConstraint. Prethodna migracija
(9b2d1f7a4c63_session_task_bindings.py) je za analogan slučaj
(SessionTaskBinding.binding_source) koristila
`CheckConstraint("binding_source IN ('USER', 'LEGACY_DIRECT_FK')", ...)` —
ustanovljen obrazac u ovoj šemi koji ova migracija ne prati bez objašnjenja.

Trenutni rizik: NIZAK, ne EKSPLOATABILAN danas. Grep potvrđuje da je
ReportService jedini write put za work_status u src/, i on uvijek validira.
Backend je jedini normalni DB writer po arhitekturi, pa je ovo danas dovoljno.

Zašto ipak MEDIUM, ne ACCEPTABLE bez ograde: work_status je eksplicitno
namijenjen da postane MAŠINSKI ČITLJIV autoritet za budući Workflow Ledger.
Bez DB-level garancije, bilo koji budući direktni SQL fixup, backfill skripta,
ili migracija koja zaobiđe ReportService (a takve su uobičajene u razvoju —
npr. ručna korekcija lošeg reda tokom debugginga) može upisati proizvoljnu
vrijednost bez ikakvog signala da je nešto pogrešno, i Ledger bi to tiho
progutao kao "validno" jer DB šema to ne sprečava.

Preporuka: dodati CheckConstraint (npr.
"work_status IN ('completed','partial','blocked') OR work_status IS NULL")
u budućoj migraciji PRIJE nego work_status stvarno postane ulaz za Ledger
logiku (ne nužno prije ovog commita) — jeftina izmjena, nullable kolona, bez
rizika po postojeće podatke.
```

Ostatak migracije (FK pravila, unique constraint, upgrade/downgrade
simetrija, odsustvo backfill-a) je ispravan — bez dodatnih nalaza.

---

# KNOWN/INTENTIONAL LIMITATIONS

```text
A — Nema produkcionog pozivaoca za link_report_to_binding()

Ocjena: OČEKIVANO ograničenje Phase 1, ne neželjena posljedica.

Dokaz: grep potvrđuje da se link_report_to_binding() poziva samo iz
tests/integration/test_agent_report_v2.py. SessionCompletionService.complete_session()
i dalje zove ReportService.create_draft() bez report_type/work_status i bez
poziva link_report_to_binding() poslije — potvrđeno čitanjem completion.py:189.
Ovo je eksplicitno navedeno kao izvan scope-a u izvještaju (HTTP endpoint,
SessionCompletionService semantika).

Efekat u praksi: Za SVAKI stvarni report koji danas nastaje (isključivo preko
SessionCompletionService), _reopen_plan_item() uvijek ide legacy fallback
putanjom (nula linkova). Za sesiju koja je promijenila task/plan_item makar
jednom, fallback zahtijeva TAČNO JEDAN relevantan istorijski binding — pošto
ih ima više, reopen se NE dešava, samo warning log.

Poređenje sa stanjem prije ove faze: PRIJE — verdict bi UVIJEK reopenovao
štagod AgentSession.plan_item_id trenutno pokazivao (pogrešno za multi-binding
sesije, ali barem "nešto se dešava"). SADA — verdict na takvoj sesiji ne radi
reopen UOPŠTE (sigurno, ali zahtijeva ručnu intervenciju korisnika).

Zaključak: Ovo je namjeran, ispravno dokumentovan trade-off (fail-safe umjesto
fail-wrong), ne bug. Ne zahtijeva kod izmjenu sada. Vrijedno je da korisnik
eksplicitno potvrdi da razumije da automatski reopen za multi-binding sesije
ostaje NEFUNKCIONALAN (ne "djelimično funkcionalan") dok se ingestion faza ne
ožiči — ovo nije naglašeno dovoljno jasno u izvještaju.
```

---

# REPORT QUALITY

```text
F6 — LOW (report-quality, ne code blocker)
Fabrikovan created_at timestamp u agent_reports/2026-08-11_agent-report-v2-phase-1.md

Dokaz: front matter navodi `created_at: 2026-08-11T00:00:00+02:00` — tačno
ponoć. Stvaran mtime fajla na disku: 2026-08-11 12:42:56+02:00 (provjereno
`stat`/`ls --time-style=full-iso`). Isti obrazac (tačna ponoć) postoji i u
ranijem `agent_reports/2026-08-11_agent-report-v2-readonly-analysis.md` —
nije izolovan slučaj nego ponovljen obrazac.

Posljedica: Ne utiče na funkcionalnost koda. Utiče na pouzdanost
agent_report metapodataka kao izvora istine za budući Ledger — ironično,
tačno onaj tip "izmišljenog vremena" koji CLAUDE.md/AGENTS.md princip
eksplicitno zabranjuje, u izvještaju koji uvodi work_status polje čija je
svrha da bude mašinski pouzdano vrijeme/status.

Preporuka: koristiti stvaran timestamp trenutka pisanja reporta (ili UTC
"sada") umjesto placeholder ponoći, za ovaj i buduće izvještaje.
```

---

# Verdict

```text
FIXES REQUIRED
```

Findinzi koje treba riješiti prije commita:

1. **F1 (HIGH)** — `_reopen_plan_item()` čita živi `Task.plan_item_id` umjesto
   istorijskog snapshot-a. Popraviti dodavanjem `resolved_plan_item_id`
   snapshot polja na `AgentReportBindingLink`, popunjenog u
   `link_report_to_binding()` u trenutku linkovanja, ne u trenutku verdicta.
2. **F2 (HIGH)** — globalno proširenje `ALLOWED_TRANSITIONS` otvara
   `IMPLEMENTED/VERIFIED → IN_PROGRESS` generičkom `/plan-items/{id}/start`
   HTTP putu, nezavisno od report-verdict konteksta — dokazano probom (HTTP
   200 na IMPLEMENTED stavci, bez ikakve veze sa reportom). Popraviti kroz
   Opciju A (`allow_verdict_reopen` flag na `validate_transition()`, samo
   `_reopen_plan_item()` ga postavlja) ili Opciju B (odvojena, uže-obimna
   mutacija van dijeljene matrice) — izbor prepušten Codexu/korisniku.
3. Uz oba — dodati regresione testove (F3, F4) koji bi svaku od ove dvije
   regresije uhvatili da se ponovo pojave.

Findinzi koji NE blokiraju commit, ali trebaju follow-up prije nego
`work_status`/reopen tok postanu operativni oslonac Workflow Ledgera:

- F5 (MEDIUM) — dodati DB `CHECK` constraint za `work_status`/`report_type` u
  budućoj migraciji.
- F6 (LOW) — ispraviti naviku fabrikovanja `created_at` ponoći u
  `agent_reports/*.md` front matteru.

Known Limitation A je prihvaćena kao namjerna i ispravno dizajnirana (fail-safe
umjesto fail-wrong) — ne zahtijeva izmjenu, samo eksplicitnu korisničku svijest
da automatski reopen za multi-binding sesije ostaje neaktivan do buduće
ingestion faze.

```bash
git status --short
```
