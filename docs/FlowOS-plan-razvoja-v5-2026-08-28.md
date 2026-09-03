# FlowOS — plan razvoja v5
## Deterministički human control plane — ugovori, blueprint jezgro, ljudska radna površina i read-only agentska površina

**Datum:** 2026-08-28  
**Status:** ispravljeni kandidat za novi kanonski roadmap — usklađen sa revidiranim `FLOW-DOC-001` change specom, punim blueprintom i KAKO-RADIM-v2  
**Repo snapshot za provjere:** `b83f197ec12d1a57209d3858ef4fe0a878015b7f`  
**Izvedeno iz:** dostupnog v4.1 + v4.3 determinističkog plana + `FlowOS-change-spec-v4.3-to-v5.md` + stvarnog koda na fiksiranom SHA-u

---
# 0. Zašto postoji v5

v5 ne mijenja identitet FlowOS-a. On reorganizuje postojeći deterministički roadmap oko onoga što se može **mehanički dokazati i provoditi**, a tek zatim oko onoga što čovjek i eksterni agentski alati koriste kao radnu površinu.

Lanac izvođenja koji je stvarno dostupan za ovu reviziju je:

```text
v4.1 — dostupan
→ v4.3 deterministički — direktna osnova za v5
→ FLOW-DOC-001 change spec — revidirana verzija sa board-first Fazom C
→ AGENTIC_WORKFLOW_BLUEPRINT.md — generička workflow specifikacija
→ KAKO-RADIM-v2-prosireno.md — stvarni korisnikov operating model
→ v5
```

v4.3 navodi v4.2 kao svoju osnovu, ali `v4.2` nije pronađen među dostupnim dokumentima. Zato se v5 ne predstavlja kao provjerena direktna derivacija iz v4.2.

Za ovu ispravljenu verziju `AGENTIC_WORKFLOW_BLUEPRINT.md` je dostupan i pročitan u cijelosti. Zato §7.4 više nema parcijalno/pretpostavljeno mapiranje: svih 18 blueprint sekcija je eksplicitno preslikano na FLOW pokriće, metod ili namjerno nepokriven prostor.

Prošireni `KAKO-RADIM-v2` potvrđuje ključnu produktnu potrebu Faze C: FlowOS ne treba prvo praviti duboki ekran jednog Taska, nego ukloniti svakodnevno ručno **provjeravanje gdje je svaki paralelni Task sada**, bez pokušaja da FlowOS preuzme sam rad iz VS Code-a i terminala.

Glavni redoslijed je:

```text
FAZA A — Ugovori i blokatori
        ↓
FAZA B — Blueprint jezgro
        ↓
FAZA C — Čovjekova radna površina: tabla aktivnih Taskova
        ↓
FAZA D — Agentska read površina
        ↓
FAZA E — Uslovljeno proširenje
```

Time se uklanja ključna slabost v4.3: Task Contract, nezavisnost reviewer-a, risk gate, file claims, dependency-in-main i post-merge provjera dolaze prije velikog GUI širenja, a prvi GUI milestone rješava stvarni bottleneck korisnika umjesto unaprijed zamišljenog Task Detail ekrana.

Glavno pravilo ostaje:

> **AI radi. FlowOS pamti, povezuje i dokazuje. Čovjek odlučuje.**

---

# 1. North Star

> **FlowOS je lokalni, deterministički human control plane za agent-potpomognuti razvoj. Održava provjerljivu vezu između ljudske namjere, Taska, eksternih razvojnih sesija, Git/worktree stvarnosti, dokaza, reviewa i odluka tako da čovjek može pouzdano razumjeti gdje je projekat, šta je dokazano i šta treba odlučiti bez ručne rekonstrukcije iz chatova, terminala i report direktorijuma.**

FlowOS ne optimizuje za:

```text
što više agenata
što više modela
što više tokena
što više paralelnih sesija
što više automatskih AI odluka
```

nego za:

```text
što više razumljivog i provjerljivog engineering rada
po jedinici ljudske pažnje
```

---
# 2. Granica proizvoda

Arhitektura treba ostati ovakva:

```text
ČOVJEK
   │
   ├──────────────► Claude Code
   ├──────────────► Codex
   ├──────────────► Pi
   ├──────────────► Crush
   ├──────────────► Fusion Harness
   └──────────────► drugi alat
                         │
                         │ rade nad projektom
                         ▼
                 Git / files / worktrees
                         │
                         ▼
┌────────────────────────────────────────────────────┐
│                     FLOWOS                         │
│                                                    │
│  prati stanje                                      │
│  povezuje događaje                                 │
│  čuva canonical podatke                            │
│  razlikuje činjenice, signale i claimove           │
│  izvršava determinističke provjere                 │
│  prikazuje konflikte i nedostatke dokaza           │
│  održava Current State                             │
│  generiše deterministički Handoff                  │
│  prikazuje čovjeku gdje je potrebna odluka         │
│                                                    │
│               NEMA INTERNOG LLM-a                  │
│               NE POKREĆE AGENTE                    │
└────────────────────────┬───────────────────────────┘
                         │
                         ▼
                      ČOVJEK
```

FlowOS može integrisati podatke iz eksternih alata samo kao:

```text
READ
INGEST
CORRELATE
VERIFY
DISPLAY
```

Ne kao:

```text
START
PROMPT
SELECT
DELEGATE
RETRY
CONTROL
```

---
# 3. Šest trajnih arhitektonskih odluka v5

## D1 — FlowOS nikada ne spawn-uje agentski alat

FlowOS Session je **logički zapis rada**, ne parent process agentskog alata.

Dozvoljeni smjer:

```text
FlowOS registruje Task / Session / worktree kontekst
        ↓
korisnik sam otvara Claude Code / Codex / Pi / Crush / drugi alat
        ↓
eksterni alat radi nad projektom
        ↓
FlowOS posmatra i povezuje provjerljive posljedice
```

Mogući pasivni mehanizmi:

```text
manual session register/begin/end
attach external session reference
import AgentReport/review metadata
worktree binding
Git/watcher korelacija
```

PID nije obavezan i nije authority.

`started_at` ne znači dokaz da je agent stvarno počeo da radi.

`ended_at` ne znači da je Task završen.

Postojeći adapter/launcher kod koji još nudi `can_launch`, `launch()` ili process-tree kontrolu agentskog alata je legacy semantika koju Faza A uklanja; ne predstavlja smjer proizvoda.

## D2 — FlowOS ne gradi paralelni GitNexus

FlowOS ne razvija vlastiti general-purpose dependency/call graph za proizvoljne projekte ako dokaz već može doći iz specijalizovanog eksternog alata.

Dva nivoa:

```text
BUILT-IN DETERMINISTIČKI SIGNALI
- Git changed paths
- worktree/base odnos
- explicit Task dependencies
- known test/file mapping gdje je jednostavno

OPTIONAL EXTERNAL DEPENDENCY EVIDENCE
- GitNexus
- drugi graph/index alat
```

Konceptualni read-only interfejs:

```text
DependencyEvidenceProvider
```

Provider vraća dokazive reference sa provenance-om. Nije authority i ne izvršava agente.

## D3 — Board-first GUI; generičke primitive i duboki Task Detail dolaze tek kad ih stvarna upotreba opravda

v4.3 je istovremeno stavio `FLOW-1200 — Task-centric GUI primitive` prije `FLOW-1204 — Task Detail GUI` i tvrdio da primitive treba izvući iz stvarnog use-casea. Revidirani change spec dodatno pokazuje da ni sam veliki Task Detail nije pravi prvi use-case.

Stvarni prvi use-case je **tabla svih aktivnih Taskova** iz Faze C:

```text
FLOW-1202  stvarna stranica Zadaci = tabla
        ↓
FLOW-1203  plitki board read-model, red po Tasku
        ↓
Milestone 1 dogfooding
        ↓
tek ako drugi stvarni ekran pokaže ponovljene UI obrasce
        ↓
FLOW-1200  ODGOĐENO — izvlačenje GUI primitiva
```

`FLOW-1204 — Task Detail GUI` se takođe premješta u Fazu E kao `ODGOĐENO`. Duboki ekran jednog Taska se ne gradi dok tabla i realno korištenje ne pokažu da klik na dokaz nije dovoljan.

Pravilo:

> **Ne graditi UI framework ni duboki detail ekran prije nego što drugi stvarni use-case dokaže šta se zaista ponavlja i šta korisniku zaista nedostaje.**

## D4 — Atribucija ima strukturni plafon i postojeća semantika se ne prepisuje retroaktivno

Ciljna taksonomija ostaje:

```text
DIRECT
ISOLATED
HEURISTIC
UNKNOWN
```

Postojeći kod trenutno koristi:

```text
WORKTREE
SOLE_ACTIVE
HINT
UNATTRIBUTED
USER
```

v5 uvodi kompatibilno mapiranje u `FLOW-1112 — Evidence Semantics Contract`, a punu novu correlation semantiku tek u `FLOW-1902 — Session ↔ Git correlation`.

Početno kompatibilno mapiranje:

```text
USER         → DIRECT
WORKTREE     → ISOLATED
SOLE_ACTIVE  → HEURISTIC
HINT         → HEURISTIC
UNATTRIBUTED → UNKNOWN
```

`DIRECT` iz eksplicitnog Task↔Session bindinga + izolovanog treeja može se proizvoditi u novom read-modelu bez prepisivanja istorijskih `AttributionResult.source` vrijednosti.

Pravila:

- `HEURISTIC` nikad nije canonical authority;
- `HEURISTIC` ne smije biti jedina osnova za hard block;
- `UNKNOWN` je validan rezultat;
- Bottleneck View se gradi iz canonical Task/Ledger stanja, ne iz ownership heuristike.

## D5 — Relativni sizing, ali velocity kalibracija dolazi čim postoji blueprint jezgro

Svaki roadmap task dobija:

```text
S
M
L
```

`XL` nije dozvoljen kao direktno implementabilan task; ono što ispadne XL mora se razbiti prije rada.

`FLOW-1505 — Velocity calibration` premješta se iz kraja starog P0 toka u Fazu B. Razlog: nakon Faze A+B treba što ranije početi skupljati 5–10 stvarnih uzoraka, prije nego što se procjenjuju kasniji GUI i conditional subsistemi.

## D6 — Pet semantičkih klasa ostaju canonical; MECHANICAL_EVIDENCE nije šesta klasa

Canonical klase su:

```text
SOURCE_FACT
DERIVED_FACT
HEURISTIC_SIGNAL
CLAIM
HUMAN_DECISION
```

`MECHANICAL_EVIDENCE` se u v5 ne uvodi kao šesta paralelna klasa. To je **kvalifikator SOURCE_FACT-a** kada je činjenica nastala iz determinističke/mehaničke provjere, npr.:

```text
pytest/verify artifact
+ command
+ exit code
+ hash/reference
→ SOURCE_FACT
  proof_kind = MECHANICAL
```

U `FLOW-1112` se ne uvodi nova globalna DB kolona samo radi taksonomije. Semantic class se deterministički izvodi iz source/provenance tipa u centralnom contract/classifier sloju; durable izvor ostaje postojeći canonical zapis. API/ViewState uvijek izlaže semantic class, ali projekcija ne stvara novi source of truth.

Ako dogfooding pokaže da source tip više nije dovoljan za jednoznačnu klasifikaciju, schema proširenje postaje zasebna buduća odluka — ne pretpostavlja se unaprijed.

U Fazi C ovo ima direktnu UX posljedicu:

```text
mehanička opažanja (watcher/Git/process, kada su eksplicitno veziva za Task) → SOURCE_FACT
workflow stanje nastalo iz agentskog report/evidence toka              → CLAIM
TASK_DECISION                                                           → HUMAN_DECISION
```

`Ko radi` na tabli je deklarisana dodjela iz Task Contracta/korisničkog workflowa, **ne runtime atribucija**. Mehanička aktivnost nikada se ne koristi da se izmisli ko radi ili da se izvede da je Task završio.

---

# 4. Neupitne arhitektonske granice

1. Primarna platforma ostaje Windows 10/11.
2. GUI ostaje PySide6 + Qt Widgets.
3. Backend ostaje odvojen Python/FastAPI proces.
4. Arhitektura ostaje `View → Controller → Services`.
5. SQLite ostaje lokalna baza dok stvarna potreba ne opravda PostgreSQL.
6. Git je autoritet za stanje koda, ali commit nije workflow acceptance.
7. Worktree je izolacija rada, ne Task.
8. Task, Session, Worktree, Report, Review, Finding i Decision ostaju različiti koncepti.
9. FlowOS ne radi automatski merge/push zaštićenog targeta.
10. AgentReport je evidence/claim container, ne canonical authority.
11. Model ili agent ne potvrđuje sam svoj rezultat kao konačan dokaz.
12. `IMPLEMENTED ≠ VERIFIED ≠ ACCEPTED`.
13. User decision ostaje canonical authority za acceptance/rejection.
14. Prompt nije security boundary.
15. FlowOS core radi bez cloud servisa i bez LLM-a.
16. FlowOS core ne poziva LLM API radi zaključivanja.
17. FlowOS ne pokreće agentske alate.
18. **FlowOS ne inicira komunikaciju sa agentom; agent povlači podatke kroz read-only površinu ili korisnik ručno prenosi artefakt.**
19. FlowOS ne bira model.
20. FlowOS ne dodjeljuje Task agentu.
21. FlowOS ne pokreće retry/correction petlju nad agentom.
22. FlowOS ne organizuje debate, opinion fan-out, swarm, fusion ili multi-agent collaboration.
23. FlowOS ne odlučuje semantički koji plan, model ili agent je bolji.
24. Ne uvoditi LLM gdje Git, SQL, state machine, parser, AST, eksterni deterministički evidence provider ili test mogu riješiti problem.
25. Ne uvoditi paralelne ručne `current.md`, `progress.md`, `decisions.md` kao izvore istine.
26. Generisani Current State/Handoff je projekcija canonical podataka, nikada input authority-ja.
27. Ne prikazivati procenat napretka bez objašnjivog pravila.
28. Ne izmišljati atribuciju, status ili completion kada nema dokaza.
29. Svaka nova složenost mora imati dokazanu potrebu i jasan konzument.
30. Eksterni deterministic evidence provider nije authority; provenance mora ostati vidljiv.

### 4.1 Slojevita arhitektura — obavezna za svaki novi subsystem

```text
View ne pristupa bazi, Gitu, filesystemu ni subprocessu.

Controller mapira DTO u ViewState i upravlja UI tokom.
Controller ne sadrži SQL, Git, subprocess ni poslovna pravila.

Services su jedino mjesto poslovne logike i pristupa persistenciji/
Git/filesystem/subprocess infrastrukturi.

CLI komanda nije prečica do domena.
CLI ide preko podržanog API/controller boundary-ja.

HTTP ruta ne sadrži ORM upit.
```

Tri posebno rizične nove površine:

```text
FLOW-1163 — File claim registry
CLI/API → Controller → ClaimService → persistence

FLOW-1167 — Post-merge integration gate
Controller/workflow entry → IntegrationGateService → Verification/Git/Ledger services

FLOW-1170 — Read-only agentska površina
MCP/read-only HTTP route → Controller → CanonicalReadService
```

Nijedna od njih ne dobija direktan ORM/Git poziv u ruti ili CLI-ju.

---
# 5. Dvije odvojene osi: proizvod i metod rada

## A. Product roadmap

Šta ugrađujemo u FlowOS.

## B. Engineering method

Kako čovjek, uz pomoć eksternih agentskih alata ako želi, radi svaki veći FlowOS Task.

Metod rada ne postaje automatski backend subsystem.

Preporučeni metod:

```text
Idea / problem
        ↓
Alignment / Grill
        ↓
Product destination
        ↓
Research / Probe — samo ako postoji stvarna nepoznanica
        ↓
Architecture
        ↓
Program Design
        ↓
Vertical Slice plan
        ↓
Locked Task Contract
        ↓
Implementation
        │
        ├─ contract i dalje važi
        │      → nastavi
        │
        └─ implementation pretpostavka je dokazivo pogrešna
               ↓
          Evidence-backed contract deviation
               │
               ├─ isti goal/scope/acceptance/risk
               │      → dokumentuj dokaz i nastavi
               │
               └─ mijenja scope/architecture/risk/acceptance
                      → STOP
                      → human decision
        ↓
Evidence / tests
        ↓
Independent review
        ↓
Finding → Fix → Re-review
        ↓
Human decision
        ↓
Commit / integration gate
```

FlowOS može evidentirati artefakte i status ovog procesa.

FlowOS ga ne izvršava umjesto čovjeka.

---
# 6. Program Design i Locked Contract

## 6.1 Program Design checkpoint

Za veći scope, gdje je opravdano:

```text
Koji fajlovi se mijenjaju?
Koji tipovi/signature nastaju?
Kako izgleda call/data flow?
Koji testovi će dokazati rezultat?
Koje odluke su najmanje sigurne?
Kako se posao razbija na vertikalne, provjerljive rezove?
```

## 6.2 Locked ne znači nepogrešiv

Authoritative boundary:

```text
goal
scope / out_of_scope
acceptance
risk / approval granice
```

Implementation assumptions:

```text
predloženi fajlovi
konkretan tehnički recept
očekivani call path
pomoćna struktura
```

Ako je implementation assumption dokazivo pogrešna, bounded alternativa je dozvoljena samo kada:

```text
[ ] goal ostaje isti
[ ] scope ostaje isti
[ ] acceptance ostaje isti
[ ] risk nije povećan
[ ] postoji reproduktivan dokaz da je pretpostavka pogrešna
[ ] odstupanje je zapisano u report/evidence
```

U suprotnom:

```text
STOP
→ human decision
```

---
# 7. Provođenje, reuse, prenosivost i blueprint pokriće

## 7.1 Tri sloja provođenja

FlowOS mora eksplicitno razlikovati ono što može blokirati od onoga što samo može zabilježiti.

### MEHANIČKI PROVODIVO — FlowOS može odbiti ili blokirati tranziciju

```text
file-claim registar
presjek allowed_paths
implementer ≠ reviewer
minimalan broj nezavisnih reviewera po risk tieru
post-merge integration gate kao obavezan korak
zavisni Task je dokazivo u main prije branchanja zavisnog Taska
claim oslobođen prije zatvaranja Taska
Task Contract postoji prije prvog implementacionog commita
```

Blokada mora biti objašnjiva pravilom i ulaznim činjenicama. Nema LLM procjene.

### SAMO BILJEŽIVO — FlowOS vidi evidence, ali ne ocjenjuje kvalitet

```text
dubina i kvalitet reviewa
kvalitet samog Task Contracta
da li adversarial test zaista dokazuje pravu stvar
da li je OUT_OF_SCOPE_FINDING semantički pravilno klasifikovan
da li je ljudska arhitektonska argumentacija uvjerljiva
```

FlowOS može prikazati da artefakt postoji, ko ga je dao i koje je klase. Ne pretvara kvalitet u automatski PASS/FAIL.

### OSTAJE U METODU / DOKUMENTU — FlowOS ne pokušava automatizovati

```text
fresh-reviewer eskalacija
redizajn kontrakta da se overlap ukloni
čišćenje ili skraćivanje state dokumenta kao urednička odluka
izbor boljeg modela/agenta za konkretan problem
```

## 7.2 Postojeći kod — proširi prije nego što izgradiš paralelni subsystem

| Postojeći element | Odluka u v5 | FLOW |
|---|---|---|
| `services/evidence.py` | **Proširiti** iz PlanItem-ključanog `EvidenceBundle` u Task-ključani **board row** read-model. Ne praviti drugi Evidence subsystem. | 1203 |
| `services/project_state.py` | **Proširiti** za Project State / Current State samo ako se E aktivira; ne graditi paralelnu projekciju. | 1602 |
| `services/project_timeline.py` | Odluka o reuse/zamjeni je **ODGOĐENA** zajedno sa zasebnim Workflow History ekranom. | 1302 — E |
| `services/sessions/timeline.py` | Zadržati session-lifecycle odgovornost; eventualni budući Task history ga ne smije duplirati. | 1302 — E |
| `services/conflicts/service.py` | Zadržati pet postojećih post-fact conflict tipova. Njegova GUI stranica nije dio Milestone 1; povezivanje se razmatra u E prije širenja conflict intelligencea. | 2100–2104 / E |
| `services/reports/ingestion.py` | Zadržati; formalizovati `<repo>/agent_reports/*.md` kao podržani write/ingest ugovor. | 1172 |
| `scripts/guard_architecture.py` | Proširiti u A, a kasnije registrovati kao prvi postojeći guard — ne izmišljati drugi mehanizam. | 1156, 2003 |
| `services/attribution/service.py` | Kompatibilno mapiranje trenutnih izvora u 1112; punu D4 correlation taksonomiju uvoditi u 1902. | 1112, 1902 |

## 7.3 Prenosivost je poprečno pravilo, ne kasni port

Primarna platforma:

```text
Windows 10/11
```

Podržani cilj iz izvornog koda:

```text
Linux
```

macOS:

```text
OTVORENO — uvoditi samo kada postoji stvaran korisnik/potreba
```

Trajna pravila:

```text
Ne dodavati novi Windows-only kod.
Svaka aplikacijska putanja ide kroz app_paths.
Svaki FlowOS-owned subprocess ide kroz jedan centralni wrapper.
Nijedan novi direktan os.environ/sys.platform/platform poziv u feature kodu;
platformske razlike pripadaju centralnim infrastructure helperima.
```

Fedora 44 napomena iz change speca:

```text
system python3 = 3.14
repo cilja Python 3.12/3.13
→ koristiti venv sa 3.12 ili 3.13

GDM = Wayland-only
→ Qt/PySide6 smoke test je prvi portability gate

filesystem = case-sensitive
→ FLOW-1110 od početka testira i case-sensitive i case-insensitive path semantiku
```

Postojeće stanje koje opravdava ovo pravilo:

- runtime već ima `fcntl.flock` non-Windows granu;
- `app_paths.py` još koristi `%LOCALAPPDATA%`/`AppData/Local` fallback;
- `dir_security.py` na non-Windows samo kreira direktorij bez `0700`/ownership provjere;
- scanner koristi Windows `tasklist`;
- View direktno koristi `explorer`;
- CLI još ima `.exe`/`tasklist` pretpostavke.

## 7.4 Preslikavanje svih blueprint sekcija

`AGENTIC_WORKFLOW_BLUEPRINT.md` je pročitan u cijelosti. Blueprint je generički metod za multi-agent projekat; v5 ga **adaptira**, ne kopira slijepo. Tamo gdje generički blueprint predlaže ručni state fajl ili coordination skriptu, FlowOS isti problem rješava canonical servisom/projekcijom kada je to dio proizvoda.

| Blueprint | Šta traži | FLOW / v5 pokriće | Sloj provođenja | Faza |
|---|---|---|---|---|
| §1 Uloge | Human owner, implementer, nezavisni reviewer-i | 1161; reviewer metadata 1150 | implementer ≠ reviewer mehanički; ostalo bilježivo/human | A/B |
| §2 Risk tier | LOW/MEDIUM/HIGH → različita review dubina | 1162; 1150 | mehanički minimalni broj reviewera | A/B |
| §3 Bootstrap | instructions, mapa/routing/state, reports, claims, CI | 1154, 1155, 1163, 2201. Ručni `CURRENT_STATE.md` se **ne uvodi kao FlowOS authority**; zamjenjuju ga projekcije gdje se aktiviraju. | mješovito | A/B/E |
| §4 Task Contract | contract prije koda | 1160 | mehanički za postojanje i granice; kvalitet bilježivo | B |
| §5 File claims | centralni claim/status/release/check | 1163, 1165 | mehanički | B |
| §6 Worktree izolacija | izolovan task tree + dependency stvarno u main | postojeći worktree subsystem + 1110 + 1166 | mehanički tamo gdje je dokazivo | A/B |
| §7 Pipeline po tasku | contract → claim → worktree → implementation/evidence → review → human → merge → post-merge | 1160–1167, 1305, 1401–1403; report ingestion 1172 | mješovito; FlowOS ne launchuje agenta niti radi merge | A–D |
| §8 Review verdict | strukturisan PASS/REJECT + blocking findings | 1150, 1161, 1162 | schema/nezavisnost/risk mehanički; kvalitet reviewa bilježivo | A/B |
| §9 TEST-ADVERSARIAL | novi test pada na starom, prolazi na novom | 1305 | izvršenje/evidence mehanički; semantički kvalitet dokaza bilježivo | A |
| §10 Paralelizacija | allowed_paths presjek; po potrebi redizajn | 1164 | presjek mehanički; redizajn ostaje metod/human | B |
| §11 Fresh reviewer | kontaminirani reviewer se zamjenjuje svježim | nema backend taska | ostaje u metodu/dokumentu | — |
| §12 Evidence/report precision | doslovni output, OOS finding, ne duplirati review | 1150, 1172, 1303; strukturisani Findings 1701 ako E bude aktivirana | pretežno bilježivo; schema/ingestion mehanički | A/C/D/E |
| §13 Human approval | merge nikad bez eksplicitnog čovjeka | 1401–1402 + postojeći TASK_DECISION authority | HUMAN_DECISION; FlowOS ne mergeuje | C |
| §14 Post-merge gate | verify na glavnoj grani poslije mergea | 1167 | mehanički obavezan gate/evidence | B |
| §15 State document | kratkotrajan state, periodično čišćenje | **nema direktan product task**. FlowOS ne uvodi ručni `CURRENT_STATE.md` authority; Handoff/Project State su canonical projekcije u D/E. | metod/dokument | D/E |
| §16 Anti-patterns | zabrane retro contracta, self-reviewa, stale claim-a, zelenog CI kao authority-ja itd. | distribuirano kroz 1160–1167, 1305 i docs sync 1155 | mješovito | A/B |
| §17 Sensors | opcioni deterministic architecture sensor + historical replay | 1156 za postojeći guard; 2001–2005 samo ako E bude aktivirana | mehanički tek nakon replay validacije; praksa je i dalje nedokazana/emerging | A/E |
| §18 Adaptacija | jezgro 4,6,7,8,13,14 ne preskakati; sensors kasnije | sama struktura A→B→C→D→E; gore navedeni FLOW taskovi | roadmap/metod | cijeli v5 |

Eksplicitno nepokriveno kao samostalan FlowOS subsystem:

```text
§11 fresh reviewer eskalacija — ostaje procesna disciplina
§15 ručni state-document lifecycle — FlowOS ga ne usvaja kao source of truth
§18 adaptacija blueprinta — dokumentaciona/roadmap obaveza, ne runtime feature
```

To nisu rupe koje treba popuniti novim taskovima. One su namjerno izvan mehaničkog authority-ja FlowOS-a.

---

# 8. FAZA A — Ugovori i blokatori

## Cilj

Prije širenja workflowa i GUI-ja ukloniti kontradikcije u postojećem kodu, zaključati request/evidence/review ugovore, ojačati slojevite granice i uspostaviti minimalnu cross-platform/subprocess sigurnost.

`FLOW-1109 — Redakcija tajni iz logova i artefakata` **nije aktivan task u v5**. Na fiksiranom SHA-u potvrđeno je da je njegov kod ušao kroz commit `c9c92d88d98f3920fd6a716bff9b0fc8239b650c`; ostaje istorijski evidence, ne roadmap blocker.

---

## FLOW-1110 — Siguran worktree identitet i cleanup `[L]`

### Polazni dokaz

Na fiksiranom SHA-u postoje dva unsafe string-prefix obrasca:

```python
str(wt_path_resolved).startswith(str(flowos_root))
```

i:

```python
wt.path == path or wt.path.startswith(path)
```

Kasniji cleanup containment već koristi `Path.is_relative_to()`, pa v5 ne tvrdi da su sva tri mjesta ista greška.

### Obavezno

- centralni path identity/containment helper;
- jasno razdvojiti **identity** od **containment**;
- case-insensitive semantika za Windows;
- case-sensitive semantika za Linux;
- canonical/resolved path;
- junction/symlink/reparse rizik gdje je relevantno;
- `project_id` provjera prije destruktivne akcije;
- cleanup samo tačnog managed worktree-a;
- dirty i retention zaštita ostaju;
- nikakav “najbliži prefix” fallback.

### Acceptance

```text
[ ] FLOW-1 ≠ FLOW-10
[ ] case-variant identitet se ponaša po ciljnom OS pravilu
[ ] Linux case-sensitive test postoji
[ ] root containment ne koristi string prefix
[ ] pogrešan project_id fail-closed
[ ] pogrešan path ne cleanup-uje drugi worktree
[ ] tačan worktree cleanup radi
[ ] dirty zaštita ostaje
```

---

## FLOW-1105 — Usklađivanje GUI/backend Plan Import formata `[M]`

### Polazni dokaz

GUI trenutno šalje:

```python
{"markdown": content}
```

backend čita:

```python
body.get("markdown_text", "")
```

dok `PlanImportRequest(markdown_text: str)` postoji, ali endpoint ga ne koristi. Postojeći GUI test zaključava pogrešan `{"markdown": ...}` contract jer testira lažni `_post`, ne stvarni endpoint.

### Obavezno

```text
View
→ Plan Controller
→ GuiApiClient.import_plan(...)
→ HTTP PlanImportRequest
→ PlanImport service/parser
```

- endpoint prima `PlanImportRequest`, ne `body: dict`;
- `GuiApiClient` dobija javnu `import_plan(project_id, markdown_text)`;
- `_on_import_plan` se izbacuje iz composition-root poslovne logike kroz FLOW-1157;
- file selection/read pripada kontrolisanom GUI controller/service toku;
- nema poziva privatnog `_post` iz composition root-a;
- stari test se mijenja zato što trenutno dokazuje pogrešan contract;
- dodati contract/E2E test koji prolazi preko stvarnog request shape-a.

### Adversarial dokaz

```text
OLD GUI payload + real endpoint → FAIL
NEW canonical payload + real endpoint → PASS
```

---

## FLOW-1106 — Stvarni uvoz dogfooding plana `[S]`

- FlowOS projekat stvarno registrovan/izabran;
- plan importovan kroz LIVE tok iz FLOW-1105;
- faze/items/criteria/dependencies potvrđeni;
- parser nejasnoće prikazane čovjeku;
- nema retroaktivnog fabrikovanja Ledger događaja.

---

## FLOW-1111 — Passive Session Contract `[S]`

### Polazni dokaz

`flowos session start` na sadašnjem kodu samo radi `POST /sessions`; ne pokreće agentski proces.

Istovremeno legacy adapter sloj još sadrži:

```text
AdapterCapabilities.can_launch = True
AgentProcessLauncher.launch()
kill_process_tree()
get_command()
get_environment()
```

a CLI registruje `pid=os.getpid()`, što je PID CLI procesa.

### Cilj

Kod i dokumentacija moraju opisivati stvarni pasivni model.

### Obavezno

- ukloniti `can_launch` kao default/produktni capability;
- ukloniti ili jasno demontirati production semantiku `AgentProcessLauncher`;
- ukloniti agentski `kill_process_tree` iz FlowOS core contracta;
- `session start/register` ne upisuje CLI PID kao da je agent PID;
- prazni legacy paketi `execution`, `jobs`, `approvals`, `usage`, `git`, `infrastructure/process`, `infrastructure/filesystem` se brišu ako nemaju stvarnog konzumenta; ako neki ima stvarnu init-contract ulogu, to se dokazuje prije zadržavanja;
- `infrastructure/process/__init__.py` više ne tvrdi da ga koristi Managed Execution;
- eksplicitno odlučiti:
  - `get_command()` — ukloniti ili ostaviti samo kao inertnu adapter metadata pomoć bez launch authority-ja;
  - `get_environment()` — ukloniti iz agent-launch ugovora; subprocess env za FlowOS-owned komande rješava FLOW-1151.

### Acceptance

```text
flowos session start/register
→ samo logical session record
→ nema child agent procesa
→ nema lažnog agent PID-a
```

---

## FLOW-1112 — Evidence Semantics Contract `[M]`

Canonical klase:

```text
SOURCE_FACT
DERIVED_FACT
HEURISTIC_SIGNAL
CLAIM
HUMAN_DECISION
```

### Zaključane odluke v5

1. `MECHANICAL_EVIDENCE` nije šesta klasa; to je `SOURCE_FACT` sa `proof_kind=MECHANICAL`.
2. U ovoj fazi se ne uvodi univerzalna DB kolona samo za semantic class.
3. Semantic class se deterministički izvodi iz source/provenance tipa centralnim classifier/contract slojem.
4. API/ViewState mora uvijek izložiti semantic class i provenance.
5. Postojeća atribucija se kompatibilno mapira:
   - `USER → DIRECT`
   - `WORKTREE → ISOLATED`
   - `SOLE_ACTIVE/HINT → HEURISTIC`
   - `UNATTRIBUTED → UNKNOWN`
6. Istorijske vrijednosti se ne prepisuju retroaktivno.

### Architecture path

```text
Source services / persistence
→ EvidenceSemanticsService / shared DTO
→ Controller
→ View
```

---

## FLOW-1150 — Report front-matter v2 i strukturisan reviewer verdict `[M]`

Trenutni parser ima strogu allowlistu i odbija nepoznat ključ. v2 mora podržati:

```text
risk
implementer
reviewers
```

i strukturisani reviewer verdict:

```text
verdict
scope
acceptance
architecture
security
blocking_findings
```

`user_verdict` ostaje ljudski workflow authority i ne smije biti preimenovan u reviewer verdict.

### Architecture path

```text
Report ingestion/controller
→ Report parsing/service
→ report persistence
```

---

## FLOW-1151 — Filtriran environment za FlowOS-owned subprocess `[S]`

Trenutni `VerificationService` poziva `subprocess.run(...)` bez `env=`.

Uvesti jedan centralni subprocess environment policy:

- minimalna allowlista;
- platform helperi centralizovani;
- secret vrijednosti se ne loguju;
- verification/build komande dobijaju samo potreban env;
- ne odnosi se na eksterni agent proces jer FlowOS njime ne upravlja.

---

## FLOW-1152 — Timeout završava cijelo FlowOS-owned process stablo `[M]`

`subprocess.run(timeout=...)` nije dovoljna semantika za tvrdnju “timeout je završio cijelo stablo”.

Obavezno:

- centralni process wrapper;
- Windows: stvarni process-tree/Job Object ili ekvivalentna dokaziva semantika;
- Linux: process group/session kill;
- graceful → hard cutoff gdje je praktično;
- exit/timeout rezultat tačno persistovan;
- nema tvrdnje da ovo kontroliše eksterni agent.

---

## FLOW-1153 — Linux iz izvornog koda `[M]`

Obavezno:

- `app_paths`: XDG-compatible grana;
- `dir_security`: `chmod 0o700`, provjera ownera i fail-closed za sensitive direktorije;
- `agent_scanner`: platform-neutral proces listing (npr. psutil) umjesto `tasklist`;
- OS folder-open ide kroz Service/infrastructure helper, ne View;
- CLI launcher/paths bez `.exe` pretpostavke u shared kodu;
- Fedora 44 smoke setup sa Python 3.12/3.13 venv;
- PySide6 Wayland smoke test.

---

## FLOW-1154 — CI matrica Windows + Linux `[S]`

Minimalno:

```text
windows-latest
ubuntu-latest
```

pokreću relevantni standardni verify tok.

CI ne postaje workflow authority; on je dodatni mechanical evidence source.

---

## FLOW-1155 — Sinhronizacija CLAUDE.md, AGENTS.md i README sa v5 `[S]`

Ukloniti tvrdnje koje pripadaju ukinutoj arhitekturi:

```text
wrapper kao kičma koja launchuje/posjeduje agent lifecycle
obavezan adapter launch redoslijed kao roadmap authority
Managed Execution / Durable Agent Engine kao obećani core put
service → subprocess/JobObject → agent kao ciljna arhitektura
can_launch kao core capability
```

Dokumenti moraju razlikovati:

```text
Session registration
≠ agent launch
```

---

## FLOW-1305 — Adversarial Regression Proof `[M]` — premješten iz stare Faze 13

Regression Proof je procesni/verification gate, ne GUI task.

Obavezno za:

```text
svaki bugfix
svaku promjenu execution patha
svaku promjenu architecture patha
```

Opciono je samo za čistu novu funkcionalnost gdje nema prethodnog ponašanja koje treba oboriti.

Obavezna TEST-ADVERSARIAL procedura iz blueprint §9:

```text
1. napiši test/sensor koji tvrdi da dokazuje novi put
2. reprodukuj PRE-CHANGE / stari pogrešni put u izolovanom, read-only-safe replay okruženju
3. pokreni upravo taj test
4. test mora FAIL-ovati iz pravog razloga
5. vrati/primijeni novi ispravni put
6. isti test mora PASS
7. dokumentuj oba rezultata kao evidence
```

Historical replay ne smije mutirati aktivni implementation worktree; koristi se `git show`/`ls-tree`/`cat-file` ili privremeni/detached worktree.

`FLOW-1157` obavezno potpada pod ovo pravilo jer mijenja arhitektonski put `View/composition → private API/OS` u podržani `View → Controller → Service` tok.

---

## FLOW-1157 — Composition root ponovo postaje wiring root `[M]`

**Ovaj task ide prije FLOW-1156.**

Izvući tačno četiri handlera koji nose poslovnu/OS/API policy logiku:

```text
_on_import_plan
_track_agent
_on_prepare_ready
_on_shutdown_requested
```

Dodatno:

- `overview_skeleton.py` folder-open više ne koristi `subprocess.Popen` iz View-a;
- `GuiApiClient` dobija javne metode umjesto poziva privatnog `_post`;
- ne dirati preostalih 14 handlera samo radi “čistoće”; oni se mijenjaju kada ih Faza C stvarno dotakne.

### Regression Proof

FLOW-1157 se ne može prihvatiti bez FLOW-1305 dokaza:

```text
stari kod + novi architecture test/sensor → FAIL na poznata kršenja
ispravljeni kod + isti test/sensor → PASS
```


---

## FLOW-1156 — Proširenje architecture guarda `[M]`

**Tek nakon FLOW-1157.**

Postojeći guard je import-based i ne vidi poznata kršenja.

Nova pravila moraju pokriti:

- `flowos.gui.composition_root` kao boundary source;
- `flowos.cli`;
- View → service direktne importe;
- View OS/subprocess pozive;
- private API client pozive (`._post`, `._get`, ...) iz composition/View/controller boundary-ja;
- ista semantika u `tests/architecture/test_boundaries.py`.

### Replay acceptance

Guard se prije prihvatanja replayuje protiv poznatog starog stanja.

Mora dokazivo uhvatiti najmanje:

```text
_on_import_plan private _post/boundary bypass
_track_agent private _post/boundary bypass
overview_skeleton View → subprocess/explorer
```

Guard koji “prođe” jer su prekršaji allowlistovani nije prihvaćen.

---

## Gate A

```text
[ ] FLOW-1110 accepted sa Windows + Linux path semantikom
[ ] Plan Import radi end-to-end kroz public GuiApiClient contract
[ ] dogfood plan aktivan
[ ] agent-launch semantika uklonjena iz koda i dokumentacije
[ ] evidence taxonomy zaključana; MECHANICAL_EVIDENCE riješen
[ ] front-matter v2 + structured reviewer verdict prihvaćeni
[ ] verify subprocess ima filtered env
[ ] timeout završava FlowOS-owned process tree
[ ] Linux source smoke + Windows smoke postoje
[ ] CI zelen na Windows i Linux
[ ] FLOW-1305 pravilo je primijenjeno na svaki bugfix/execution-path change u Fazi A
[ ] FLOW-1157 završen prije FLOW-1156
[ ] guard replay hvata sva tri poznata stara prekršaja i prolazi na ispravljenom kodu
[ ] composition_root je wiring root, ne ad-hoc business controller
[ ] CLAUDE.md / AGENTS.md / README ne propisuju ukinuti agent-launch smjer
```

---

# 9. FAZA B — Blueprint jezgro

## Cilj

FlowOS još uvijek **ne izvršava agenta**, ali sada mehanički provodi mali skup ugovora koji čine workflow pouzdanim prije prvog implementacionog commita i prije integracije.

---

## FLOW-1160 — Task Contract v1 `[M]`

Persistovan model:

```text
goal
risk
scope
out_of_scope
allowed_paths
forbidden_paths
acceptance
implementer
reviewers
verification_commands
```

Minimalni contract mora postojati prije prvog implementacionog commita.

### Architecture path / guard

```text
HTTP/GUI/CLI Controller
→ TaskContractService
→ persistence
```

Guard: FLOW-1156 mora spriječiti route/CLI/View direktni ORM pristup.

---

## FLOW-1161 — Uloge kao prvorazredni pojam `[M]`

`agent_type`/harness/tool nije role.

Uvesti odvojeno:

```text
IMPLEMENTER
REVIEWER
VERIFIER gdje je potreban
HUMAN_AUTHORITY
```

Mehanički provjeriti:

```text
implementer ≠ reviewer
```

Ne vezivati uloge za Claude/Codex/Crush/Pi.

### Architecture path / guard

```text
Task/Report Controller
→ RoleAssignmentService
→ TaskContract/Report persistence
```

FLOW-1156 pokriva boundary; service unit test pokriva role invariant.

---

## FLOW-1162 — Risk tier kao review gate `[S]`

Risk:

```text
LOW
MEDIUM
HIGH
```

Minimalna početna politika mora biti eksplicitna i konfigurabilna samo kroz kod/config, ne LLM:

```text
LOW    → najmanje 1 nezavisni reviewer kada review workflow zahtijeva review
MEDIUM → najmanje 1 nezavisni reviewer
HIGH   → najmanje 2 nezavisna reviewera
```

Ako postojeći projektni policy želi stroži prag, stroži policy pobjeđuje.

`ACCEPTED` se ne može zabilježiti kada ugovoreni risk gate nije ispunjen.

### Architecture path / guard

`WorkflowDecisionService → ReviewGateService`; nema logike u View/route.

---

## FLOW-1163 — File-claim registar `[M]`

Minimalne operacije:

```text
claim
status
release
check
```

Canonical registry je u FlowOS bazi, dostupan iz svakog worktreeja kroz servis.

Claim key:

```text
project_id + normalized repo-relative path
```

Ne koristiti apsolutnu worktree putanju kao logički identitet istog projektnog fajla.

Claim nije ownership istina o tome ko je stvarno pisao fajl; to je **workflow rezervacija**.

### Architecture path / guard

```text
CLI/read API
→ Controller
→ FileClaimService
→ persistence
```

CLI ne smije importovati `FileClaimService` direktno.

---

## FLOW-1164 — Presjek allowed_paths prije paralelne dodjele `[S]`

Deterministički:

```text
Task A.allowed_paths ∩ Task B.allowed_paths
```

Ako postoji preklapanje aktivnih writer Taskova:

```text
→ BLOCK / zahtijevaj promjenu ugovora ili serijalizaciju
```

Ovo ne pokušava semantički dokazati sve dependency konflikte; to dolazi kasnije samo po potrebi.

Architecture: `TaskContractService → CoordinationPolicyService`; guard iz 1156.

---

## FLOW-1165 — Stale claim detection `[S]`

Claim se označava stale kada je dokazivo, npr.:

```text
Task terminalno/integrisano stanje
+ claim još ACTIVE
```

Ne oslobađati destruktivno claim bez audit traila.

Architecture: `FileClaimService`; no direct route ORM.

---

## FLOW-1166 — Zavisni Task mora biti stvarno u main `[S]`

Prije branchanja/aktiviranja zavisnog Taska:

```text
dependency Task accepted/integrated metadata
+
Git dokaz da je odgovarajući commit ancestry/relevant change stvarno u main
```

Nije dovoljno:

```text
grana postoji
report kaže merged
```

Architecture:

```text
TaskDependencyPolicyService
→ Git read service
→ Task state service
```

Controller samo vraća rezultat.

---

## FLOW-1167 — Post-merge integration gate `[M]`

Poslije svakog mergea u glavnu granu:

```text
checkout/current main state je činjenica
→ standardni integration verification na main
→ persistovan mechanical evidence
→ Ledger/workflow event za post-merge gate rezultat
```

Commit/merge nije acceptance, a pre-merge verify nije dokaz da integrisani `main` radi.

FlowOS ne radi merge. Bilježi da je merge nastao i provodi obaveznu provjeru kada korisnik/workflow prijavi integraciju.

### Architecture path / guard

```text
Integration Controller/API
→ PostMergeGateService
→ GitStateReader + VerificationService + LedgerService
```

Nema standalone skripte koja zaobilazi service layer.

---

## FLOW-1505 — Velocity calibration `[S]` — premješten iz stare Faze 15

Nakon prvih najmanje 5 stvarnih Taskova kroz A+B bilježiti:

```text
size S/M/L
calendar elapsed
human attention gdje je poznat
review time
broj korekcija
rework
```

Nema analytics platforme i nema target KPI-ja.

### Architecture path / guard

Može početi kao strukturisana evidencija kroz postojeći service/report sloj. Ne uvoditi novi metrics backend dok drugi stvarni konzument ne postoji.

---

## Gate B

```text
[ ] Task Contract postoji kao model, ne samo Markdown konvencija
[ ] prije implementacionog commita postoji Task Contract
[ ] implementer i reviewer su odvojene uloge
[ ] HIGH risk ne može do ACCEPTED bez 2 nezavisna reviewera
[ ] claim nad aktivno claimovanim fajlom drugog Taska se odbija
[ ] allowed_paths overlap blokira nekonzistentnu paralelnu dodjelu
[ ] stale claim je vidljiv
[ ] dependent Task ne ide dalje dok dependency nije dokazivo u main
[ ] post-merge gate proizvodi mechanical evidence na main
[ ] claim mora biti releaseovan prije zatvaranja Taska
[ ] velocity uzorak postoji za najmanje 5 stvarnih Taskova
```

---
# 10. FAZA C — Čovjekova radna površina

## Cilj

**Milestone 1:** korisnik na jednom LIVE ekranu vidi **sve aktivne Taskove** i za svaki može odmah razlikovati:

```text
šta je eksplicitno dodijeljeno
šta je FlowOS mehanički opazio
koje workflow stanje je prijavljeno/dokazano
koji Task je utihnuo
koji Task čeka njegovu odluku
```

Ova faza je namjerno manja od v4.3. Ne gradi duboki Task Detail, zaseban Workflow History ekran ni reorganizaciju cijele navigacije prije nego što stvarna tabla dokaže potrebu.

## C.0 — Šta je stvarni problem

v4.3 je polazio od dubokog `FLOW-1204 — Task Detail GUI`: korisnik izabere jedan Task, pa na tom ekranu rekonstruiše njegovu priču.

Stvarna potreba iz `KAKO-RADIM-v2` je drugačija. Korisnik je već sam dodijelio ko radi koji Task. Njegov svakodnevni trošak je što mora obilaziti VS Code prozore, terminale, worktree-je i report fajlove da bi odgovorio:

```text
gdje je svaki paralelni Task sada?
da li se nešto i dalje dešava?
da li je agent utihnuo?
da li je stigao dokaz/review?
da li nešto čeka mene?
```

Zato je centralni objekat Faze C **tabla svih aktivnih Taskova**, ne Task Detail.

Milestone 1 uklanja **provjeravanje**. Ne premješta sam razvojni rad iz VS Code-a i terminala u FlowOS.

## C.1 — Oblik table

Jedan ekran, jedan red po Tasku, pet osnovnih kolona:

```text
Task        Ko radi   Gdje je        Zadnji signal     Čeka
FLOW-1157   Codex     IMPLEMENTED    commit, 6 min     review
FLOW-1105   Pi        —              fajl, 2 min       —
FLOW-1110   Crush     —              tišina 3h         ?
FLOW-1112   Claude    VERIFIED       review, 20 min    tebe
```

Semantika kolona je stroga:

### `Task`

Human-readable naslov + FLOW ID kao sekundarni identitet.

### `Ko radi`

Dolazi iz eksplicitne dodjele u Task Contractu / korisničkom workflowu.

To je **deklarisana dodjela**, ne dokaz runtime vlasništva. FlowOS ne koristi process scan ili watcher da bi izmislio ko radi.

### `Gdje je`

Prikazuje samo workflow stanje koje postoji kao canonical/report-driven evidence.

Ako nema workflow evidencea:

```text
—
```

Ne pretvarati nedavni file activity u lažno `u radu`, `implemented` ili `verified`.

### `Zadnji signal`

Najnoviji mehanički signal koji je dokazivo veziv za Task:

```text
watcher file event
Git commit/state change
explicitly bound session/process liveness
AgentReport ingestion timestamp
```

Ako se proces ne može eksplicitno vezati za Task, ostaje unattributed i **ne ulazi u Task red kao dokaz aktivnosti tog Taska**.

### `Čeka`

Deterministički razlog koji traži sljedeću akciju:

```text
review
verification
tebe
?
—
```

U Milestone 1 obavezni su najmanje:

```text
tebe  → FLOW-1181
?     → FLOW-1180 tišina / nedostatak signala
```

Klik na red ili konkretan evidence signal otvara **stvarni dokaz**: report, diff/Git referencu ili verify output. Ne otvara obavezno veliki ekran sa devet sekcija.

## C.2 — Mehanički signal i workflow stanje su različite stvari

Ovo je D6 primijenjen direktno na UI.

### MEHANIČKI SIGNAL

Ne traži saradnju agenta i nastaje iz determinističkog opažanja:

```text
watcher: izmjena fajla u eksplicitno vezanom worktree/task kontekstu
Git polling: commit/state promjena na vezanoj grani/worktreeju
agent_scanner/process signal: samo kada postoji eksplicitna Task/Session veza
```

Semantička klasa:

```text
SOURCE_FACT
```

### WORKFLOW STANJE

Nastaje kada postoji odgovarajući report/evidence tok:

```text
IMPLEMENTATION_COMPLETED
TEST_RESULT
REVIEW_COMPLETED
TASK_DECISION
```

Za prikaz table:

```text
agentski report/evidence o radu → CLAIM
TASK_DECISION                   → HUMAN_DECISION
```

FlowOS ne smije iz mehaničke aktivnosti izvesti workflow completion.

Kanonski primjer rupe:

```text
agent je radio i ostavio commit/file signal
ali nije ostavio report/odgovarajući workflow evidence

Gdje je:        —
Zadnji signal:  commit, 6 min
```

To je namjeran, informativan mismatch — ne greška koju treba prekriti riječju `u radu`.

## C.3 — Aktivni taskovi Faze C

### FLOW-1201 — Minimalni izbor i registracija projekta `[S]`

Bez promjene osnovnog sadržaja:

- aktivni projekat vidljiv;
- izbor postojećeg projekta;
- `Dodaj projekat`;
- bez automatskog `git init`;
- tabla i povezani podaci prate aktivni projekat.

### FLOW-1202 — `Zadaci` na stvarni backend = tabla `[M]`

Postojeća stranica `Zadaci` nije dodatna lista pored table. **Ona postaje tabla.**

Polazni dokaz iz repo audita: `TasksPage()` je instanciran inline, referenca se ne čuva i nema stvarni backend wiring.

Obavezno:

```text
View → Controller → GuiApiClient → /tasks/read-model → Services
```

- čuvati stvarnu TasksPage referencu;
- učitati aktivne Taskove za izabrani projekat;
- renderovati pet kolona iz C.1;
- nema direktnog View/API/ORM bypassa;
- ne dodavati poseban “dashboard task board” ekran pored `Zadaci`.

### FLOW-1203 — Task Board read-model kroz proširenje EvidenceService-a `[M]`

**Ne graditi drugi Evidence/Current-State subsystem.**

Postojeći `EvidenceService` se proširuje iz PlanItem-ključanog bundlea tako da može proizvesti plitki red table po Tasku.

Minimalni `TaskBoardRow` konceptualni output:

```text
task_id
title
explicit implementer assignment
workflow_state nullable
latest_mechanical_signal nullable
latest_mechanical_signal_at nullable
waiting_reason nullable
silence_state
relevant evidence references
semantic_class/provenance za prikazane signale
```

Izvori se sastavljaju iz postojećih/canonical podataka:

```text
Task
TaskContract iz 1160
SessionTaskBinding / explicit worktree binding gdje postoji
AgentReport ingestion
Workflow Ledger + TASK_DECISION
Git/worktree activity
Verification evidence
```

Ne treba puni duboki Current State jednog Taska u ovoj fazi.

### FLOW-1301 — Ujedinjen workflow read-model za tablu `[M]`

Canonical workflow činjenice trenutno dolaze iz dva writer-a:

```text
WorkflowLedgerService:
IMPLEMENTATION_COMPLETED
TEST_RESULT
REVIEW_COMPLETED

WorkflowDecisionService:
TASK_DECISION
```

FLOW-1301 daje jedan read-model koji FLOW-1203 može pitati za latest relevant workflow state po Tasku.

Ne pravi novi writer niti novi history authority.

### FLOW-1303 — Otvaranje stvarnih dokaza sa table `[M]`

Klik na red/signal omogućava otvaranje relevantnog izvora:

```text
implementation/report → stvarni AgentReport/source
commit/diff            → Git evidence/reference
test/verify             → verification artifact/output
review                  → structured reviewer verdict/report
decision                → TASK_DECISION metadata
```

Nedostajući dokaz ostaje `MISSING`/prazan. Ne generiše se AI objašnjenje kao zamjena.

### FLOW-1180 — Detekcija tišine `[M]`

Najkorisniji novi signal table.

Task je kandidat za `TIŠINA` kada duže od konfigurisanog praga nema **nijedan novi dokazivo vezan signal**:

```text
file activity
Git commit/state signal
AgentReport/workflow evidence
```

Pravila:

- potpuno deterministički;
- bez ownership heuristike;
- signal koji nije pouzdano vezan za Task ne resetuje njegovu tišinu;
- prag je konfigurabilan;
- početna numerička vrijednost praga je **OTVORENO — potrebna odluka korisnika kroz dogfooding**, ne izmišljati je u planu;
- tišina ne znači `FAILED`, `ABANDONED` ni `DONE`;
- tabla prikazuje činjenicu `nema novog signala X vremena`.

Sloj:

```text
Services izračunavaju → Controller mapira → View prikazuje
```

### FLOW-1181 — `Čeka na mene` `[S]`

Čist query nad canonical workflow stanjem.

Minimalno pravilo Milestone 1:

```text
Task ima relevantnu verifikaciju
+ ima relevantan nezavisni review
+ nema TASK_DECISION za aktuelni rezultat
→ Čeka = tebe
```

Ne koristi AI ranking i ne nagađa prioritet među više Taskova.

Sloj:

```text
Workflow/Task Service query → Controller → board ViewState
```

### FLOW-1401 — TASK_DECISION kontrole sa table `[M]`

Korisnik iz reda koji `čeka tebe` može otvoriti evidence i donijeti:

```text
Prihvati rezultat
Vrati u doradu
Odbaci rezultat
```

FlowOS prije odluke prikazuje šta je dokazano, šta je claim i šta nedostaje.

### FLOW-1402 — Backend-confirmed consequence `[S]`

```text
submit TASK_DECISION
→ backend transaction
→ reload canonical board state
→ render
```

GUI ne nagađa posljedicu odluke.

### FLOW-1403 — Kompletan dogfooding tok kroz LIVE FlowOS `[M]`

Najmanje jedan stvarni Task prolazi:

```text
Task Contract
→ implementation/report evidence
→ test/verification
→ independent review
→ board prikazuje "čeka tebe"
→ TASK_DECISION sa table
→ canonical reload
→ integration/post-merge evidence prema pravilima B
```

## C.4 — Odgođeno iz v4.3 faza 12–15

Ovi FLOW brojevi se **ne brišu i ne mijenjaju značenje**. Premještaju se u Fazu E sa oznakom `ODGOĐENO` jer nisu potrebni za stvarni Milestone 1:

```text
FLOW-1200  GUI primitivi — izvlače se kada postoji drugi stvarni ekran, ne prije
FLOW-1204  Task Detail kako je dizajniran — tabla pokriva sadašnji problem
FLOW-1302  Workflow History kao zaseban ekran — nije potreban za board-first milestone
FLOW-1304  Workflow History ≠ Technical Activity — bez 1302 nema zasebnog ekrana koji treba razdvajati
FLOW-1404  SessionTaskBinding historical proof — nije potreban za prvi board milestone
FLOW-1501  Zabilježiti UX probleme — formalni UX task čeka prvo stvarno korištenje table
FLOW-1502  Čišćenje navigacije — tabla ne zahtijeva reorganizaciju svih 10 postojećih stranica
FLOW-1503  MOCK/live nejasnoće — širi cleanup nije uslov za board milestone
FLOW-1504  Zamrznuti dogfood baseline — radi se tek kada se pokaže da baseline vrijedi zamrznuti
```

Aktivni C skup tako se smanjuje na **10 taskova**.

## C.5 — Gate C = Milestone 1

```text
[ ] jedan ekran pokazuje sve aktivne Taskove, red po Tasku
[ ] `Ko radi` je eksplicitna dodjela, ne heuristička atribucija
[ ] mehanički signal i workflow stanje su vizuelno razdvojeni
[ ] Task koji je utihnuo je vidljiv bez obilaska terminala/worktreeja
[ ] Task koji čeka korisnikovu odluku je vidljiv bez traženja
[ ] odluka se donosi sa tog ekrana i canonical stanje se ponovo učita
[ ] Task sa mehaničkom aktivnošću ali bez workflow reporta prikazuje rupu u `Gdje je`, ne lažno `u radu`
[ ] neatribuisan process/file signal ne pripisuje se Tasku
[ ] klik sa table otvara stvarni evidence
[ ] cijeli tok je prošao nad najmanje jednim stvarnim dogfooding Taskom
```

### Šta Milestone 1 namjerno ne rješava

```text
rad i dalje živi u VS Code-u i terminalu
FlowOS ne pokreće agente
FlowOS ne uređuje kod
FlowOS ne zamjenjuje terminal
FlowOS ne gradi duboki Task Detail prije dokazane potrebe
```

Vrijednost Milestonea 1 je da nestaje **ručno provjeravanje stanja svakog paralelnog Taska**, ne da nestaje sam razvojni rad.

---

# 11. FAZA D — Agentska read površina

## Cilj

**Milestone 2:** eksterni agent/harness može pročitati isto canonical FlowOS stanje koje vidi čovjek, bez toga da FlowOS inicira, promptuje ili upravlja agentom.

Trajna granica:

> **FlowOS ne inicira. Agent povlači.**

Kontekst se ne “sažima” LLM-om da stane u token budget. FlowOS smije samo deterministički:

```text
filtrirati po query/task/project scope-u
sortirati
deduplicirati po canonical ključu
ograničiti broj redova po eksplicitnom pravilu
odsjeći tekst po deklarisanom limitu
vratiti reference umjesto velikog body-ja
```

---

## FLOW-1170 — Read-only pristup canonical stanju za agente `[L]`

Površina može biti:

```text
FlowOS MCP
ili
read-only lokalni API
```

Odabir transporta je implementation odluka, ne product authority.

Minimalni query use-caseovi:

```text
get_task_contract
get_task_current_state
get_task_evidence
get_task_workflow_history
get_claims
get_open_decisions
get_handoff
```

Nema write/launch/prompt alata u prvoj agentskoj površini.

### Architecture path / guard

```text
Agent client
→ MCP/read-only HTTP Controller
→ CanonicalReadService
→ postojeći Evidence/Task/Workflow/Claim services
```

Ruta nema ORM upit. FLOW-1156 se proširuje ako novi transport nije pokriven postojećim boundary pravilom.

---

## FLOW-1171 — Svaki agentski odgovor nosi semantic class i provenance `[M]`

Primjer:

```json
{
  "value": "...",
  "semantic_class": "SOURCE_FACT",
  "proof_kind": "MECHANICAL",
  "source_type": "verification_artifact",
  "source_id": "...",
  "observed_at": "..."
}
```

`CLAIM` i `HEURISTIC_SIGNAL` moraju ostati označeni i u machine-readable odgovoru.

### Architecture path / guard

`CanonicalReadService → EvidenceSemanticsService → DTO`; bez klasifikacije u ruti.

---

## FLOW-1172 — Formalizovati AgentReport ingestion kao podržani write ugovor `[S]`

Postojeći `reports/ingestion.py` već prati `<repo>/agent_reports/*.md`.

v5 ga zadržava kao podržani direction:

```text
external agent/human writes structured report file
→ FlowOS observes/ingests
→ validates front matter
→ stores source identity/hash
```

Ne dodavati FlowOS→agent write/control kanal.

### Architecture path / guard

`Watcher/HTTP import Controller → AgentReportIngestionService → report persistence`.

---

## FLOW-1905 — Stale evidence detection `[L]` — premješten iz stare Faze 19

Ako se dokazivo promijeni relevantni:

```text
base commit
file/content hash
Task Contract
worktree/branch relation
```

FlowOS označava prethodni evidence kao:

```text
POTENTIALLY_STALE
```

Ne tvrdi automatski da je dokaz pogrešan.

Ovo je preduslov agentske površine: stale `VERIFIED` bez oznake je opasniji od nedostatka evidencea.

### Architecture path / guard

`EvidenceService/ProjectStateService → StalenessService → read DTO`; nema ad-hoc staleness logike u MCP/HTTP ruti.

---

## FLOW-1604 — Handoff State `[M]`

Deterministički paket:

```text
Goal
Current state
Relevant files/references
Constraints
Definition of done
Checks to run
Canonical decisions
Open blockers/findings
Worktree/base commit
```

Ako je body velik, vraćaju se reference; nema LLM summarizationa.

### Architecture path / guard

`HandoffProjectionService` koristi Task Current State/Evidence/Contract services. Ne čita DB direktno iz renderer-a.

---

## FLOW-1605 — Handoff rendereri `[S]`

```text
Markdown
JSON/API
Clipboard
GUI preview
```

Svi rendereri čitaju isti `HandoffState` DTO.

Nijedan renderer ne postaje source of truth.

### Architecture path / guard

`HandoffProjectionService → pure renderer → Controller/View/API`.

---

## Gate D — Milestone 2

```text
[ ] read-only agent surface postoji
[ ] FlowOS ni u jednom agentskom toolu ne inicira/promptuje/launchuje agenta
[ ] ruta/controller nema ORM/Git/subprocess poslovnu logiku
[ ] svaki odgovor nosi semantic class + provenance
[ ] stale evidence je označen prije izlaganja agentu
[ ] AgentReport ingestion je formalizovan i idempotentan
[ ] isti HandoffState se renderuje u najmanje dva formata
[ ] fresh eksterni agent/session može nastaviti realan Task bez starog chata
[ ] nije korišten LLM context summarization
```

---
# 12. FAZA E — Uslovljeno proširenje

## Pravilo ulaska

Faza E **nije obećani linearni roadmap**.

Svaka grupa se aktivira samo ako:

```text
dogfooding pokazuje konkretan problem
postojeći workaround je mjerljivo preskup/rizičan
postojeći servis se prvo reuse/proširi
postoji jasan korisnik rezultata
```

---

## E0 — ODGOĐENO iz Faze C

Ova grupa nije linearni nastavak Milestonea 1. Svaki task se ponovo procjenjuje tek nakon stvarnog korištenja table.

### FLOW-1200 — Task-centric GUI primitive `[M]` — ODGOĐENO

Razlog: primitive se izvlače tek kada drugi stvarni ekran pokaže ponovljeni obrazac. Ne graditi framework unaprijed.

### FLOW-1204 — Task Detail GUI `[L]` — ODGOĐENO

Razlog: board-first Milestone 1 rješava trenutni problem. Duboki detail se vraća samo ako klik na evidence i plitki board nisu dovoljni.

### FLOW-1302 — Workflow History GUI `[M]` — ODGOĐENO

Razlog: zaseban history ekran nije potreban za prvu tablu. Kada se vrati, mora riješiti odnos prema postojećim `project_timeline.py` i `sessions/timeline.py`, ne duplirati ih.

### FLOW-1304 — Workflow History ≠ Technical Activity `[S]` — ODGOĐENO

Razlog: nema zasebnog Workflow History ekrana koji treba razdvajati dok je 1302 odgođen.

### FLOW-1404 — SessionTaskBinding historical proof `[M]` — ODGOĐENO

Razlog: koristan za dublju istorijsku atribuciju, ali nije uslov za board Milestone 1.

### FLOW-1501 — Zabilježiti stvarne UX probleme `[S]` — ODGOĐENO

Razlog: formalni UX capture ima smisla poslije dovoljno stvarnih board sesija, ne prije table.

### FLOW-1502 — Pojednostaviti navigaciju `[M]` — ODGOĐENO

Razlog: tabla ne zahtijeva odmah reorganizaciju svih 10 postojećih stranica. Sudbina Agenti/Konflikti/Izvještaji/Projekti/Postavke odlučuje se iz realnog dogfoodinga.

### FLOW-1503 — Ukloniti MOCK/live nejasnoće `[M]` — ODGOĐENO

Razlog: širi GUI cleanup nije preduslov za dokaz board vrijednosti.

### FLOW-1504 — Zamrznuti prvi dogfood baseline `[S]` — ODGOĐENO

Razlog: baseline se zamrzava tek kada board pokaže stabilnu vrijednost i korisnik odluči šta zaista treba zadržati.

---

## E1 — Current State / Attention

### FLOW-1601 — Strukturisani Current State `[M]`

Tri projekcije iz istog canonical skupa, ne tri baze:

```text
Project State
Human Attention State
Handoff State (već D)
```

### FLOW-1602 — Project State kao proširenje postojećeg ProjectStateService-a `[S]`

Ne graditi paralelni service.

Dodati gdje nedostaje:

```text
current goal
active Task/PlanItem
latest decision
relevant sessions
Git/worktree state
verified evidence
open blockers
last safe checkpoint
```

### FLOW-1603 — Human Attention State `[M]`

Deterministički prioriteti:

1. blocking/risky decision;
2. failed/missing verification;
3. material open finding;
4. implementation bez verificationa;
5. verification bez user decisiona;
6. state mismatch;
7. informativna aktivnost.

Ako Task ispunjava više uslova:

```text
uzeti najviši prioritet kao primary reason
+
zadržati sve ostale matched reasons
```

Ne gubiti sekundarne razloge i ne koristiti AI ranking.

### FLOW-1606 — Fresh-session dogfood `[M]`

Korisnik ručno otvara eksterni alat/session i predaje/povuče Handoff iz Faze D. FlowOS ne inicira novu sesiju.

---

## E2 — Structured Findings

### FLOW-1701 — Finding model `[M]`

```text
id
task_id
review/report reference nullable
source_type
category
severity
title
description
evidence reference
status
created_at
```

`category` je **kontrolisan enum**, ne free-text, jer kasniji repeated-finding guard zavisi od stabilne kategorije.

Source:

```text
human review
external agent report
verification result
deterministic guard
contract assumption invalidated
```

### FLOW-1702 — FINDING_DECIDED `[S]`

```text
FIX_REQUIRED
ACCEPTED_RISK
REJECTED_FINDING
DEFERRED
```

Čovjek odlučuje.

### FLOW-1703 — FIX_COMPLETED `[S]`

Evidentira fix claim/evidence. Ne znači verified i ne pokreće implementera.

### FLOW-1704 — VERIFICATION_COMPLETED `[M]`

```text
CLOSED
OPEN
PARTIAL
```

`FIXED ≠ VERIFIED`.

### FLOW-1705 — Findings GUI `[L]`

Reuse Task Detail primitive-a. Nema novog detail frameworka.

### FLOW-1706 — USER_VALIDATION kandidat `[S]`

Samo za business/UX ponašanje gdje je stvarno potrebna ljudska validacija.

---

## E3 — Task Contract v2 / design artifacts

### FLOW-1801 — Task Contract v2 proširenje `[M]`

Ovo **nije prvi Task Contract**; v1 je FLOW-1160.

Dodatno po potrebi:

```text
working hypothesis
unknowns
dependencies
contract assumptions
approval boundary
```

### FLOW-1802 — Risk/size-based planning depth `[S]`

Planira metod, ne pokreće agente.

### FLOW-1803 — Program Design artifact `[M]`

```text
files
types/signatures
call/data flow
test plan
least-confident decisions
implementation assumptions
```

### FLOW-1804 — Decision Inbox `[M]`

Prikazuje:

```text
question/decision
impact
alternatives
evidence
source
```

FlowOS ne odlučuje.

### FLOW-1805 — Vertical Slice Plan `[M]`

Predstavlja vertikalne checkpointove; ne izvršava ih.

---

## E4 — Deterministička observability/correlation

### FLOW-1901 — External Session metadata `[M]`

```text
session reference
tool/harness label
project
recorded start/end
task binding
worktree
external session id nullable
status known/unknown
```

### FLOW-1902 — Session ↔ Git correlation `[L]`

Ciljna taksonomija:

```text
DIRECT
ISOLATED
HEURISTIC
UNKNOWN
```

Do ovog taska u storage/history i dalje mogu postojati stare vrijednosti:

```text
WORKTREE
SOLE_ACTIVE
HINT
UNATTRIBUTED
USER
```

FLOW-1112 definiše kompatibilno mapiranje; FLOW-1902 uvodi punu correlation projekciju bez retroaktivnog fabrikovanja istorije.

### FLOW-1903 — Evidence ingestion `[M]`

Indeksirati postojeće izvore sa source/time/task/session/hash/reference/semantic class.

### FLOW-1904 — Information semantics enforcement `[M]`

Backend/API/UI moraju očuvati pet canonical klasa.

---

## E5 — Deterministički sensors / guards

### FLOW-2001 — Guard Registry `[M]`

```text
guard_id
name
scope
source
severity
command/parser
enabled
version
description
```

### FLOW-2002 — Deterministički izvori `[M]`

Git, Ruff, mypy, pytest, uski AST rule, path policy, architecture tests, DependencyEvidenceProvider.

### FLOW-2003 — Architecture guardovi `[M]`

Postojeći `scripts/guard_architecture.py` je **prvi registrovani guard**, ne graditi novi paralelni mehanizam.

FLOW-1156 prvo proširuje coverage.

### FLOW-2004 — Repeated Finding → Guard Candidate `[M]`

Ista kontrolisana finding kategorija na najmanje 2 nezavisna Taska:

```text
→ GUARD_CANDIDATE
```

Nema automatskog guard stvaranja.

### FLOW-2005 — Guard provenance `[S]`

Promjena/suppress guard-a ima Task, diff, razlog/evidence i human decision gdje je potreban.

### Obavezni replay gate za cijelu grupu

Prije CI enforcementa guard se replayuje protiv poznate istorije:

```text
mora naći tačno očekivanu klasu poznatih prekršaja
ne smije "proći" samo na novom kodu
false positives se mjere/čitaju
```

Blueprint §17 je u change specu označen kao **nedokazana praksa**; dogfooding mora dokazati vrijednost prije širenja sensor platforme.

---

## E6 — Cross-worktree conflict intelligence

### FLOW-2100 — Dependency Evidence Strategy `[S]`

Postojeći `conflicts/service.py` se zadržava i već detektuje pet post-fact tipova:

```text
WRITE_WRITE
LATE_OVERLAP
BRANCH_CHANGE
STALE_SESSION
NO_COMMIT
```

Prije novih dependency tipova:

- priznati da postojeća GUI stranica `Konflikti` nije wired u Milestone 1;
- prvo odlučiti treba li je povezati kao zaseban ekran ili contextual evidence iz table/Taska;
- povezati/izložiti postojeće konflikte u korisnom Task kontekstu;
- dokumentovati stvarno iskustvo sa GitNexusom;
- definisati minimalni `DependencyEvidenceProvider` rezultat:

```text
provider
provider_version/index_revision
subject_path/symbol
referenced_path/symbol
relationship_type
source_reference
observed_at
```

Bez ovog minimalnog evidence contracta FLOW-2103 se odgađa.

### FLOW-2101 — WRITE_OVERLAP `[M]`

Built-in presjek stvarno changed/allowed paths.

### FLOW-2102 — STALE_BASE `[M]`

Prikazati stale base; bez auto rebase.

### FLOW-2103 — DEPENDENCY_REFERENCE `[L]`

Prioritet:

```text
explicit Task dependency
→ existing GitNexus/evidence provider
→ uski built-in deterministic reference
```

Ne graditi general-purpose graph.

### FLOW-2104 — ASSUMPTION_INVALIDATED `[M]`

Samo strukturisan/dokaziv signal. Ne semantic-AI engine.

---

## E7 — Readiness / bottleneck

### FLOW-2201 — Project Readiness `[M]`

Gotovo isto pitanje kao blueprint bootstrap checklist iz §3:

```text
verify command?
build?
tests?
Git state?
active worktree?
project instructions?
migration state?
unresolved findings?
clean baseline?
```

### FLOW-2202 — Bottleneck View `[M]`

Canonical queue state:

```text
čeka review
čeka human decision
čeka fix
čeka verification
```

### FLOW-2203 — Human Attention Projection `[M]`

Povezuje blockers/gaps/findings/decisions/state mismatch bez AI prioritizationa.

---

## E8 — Human comprehension

### FLOW-2301 — Review budget `[S]`

Veliki diff + širok scope + slab evidence → signal za manji checkpoint. Ne auto rejection.

### FLOW-2302 — Comprehension checkpoint `[S]`

Šablonska pitanja za visok rizik; bez LLM generisanja.

### FLOW-2303 — Deterministički Evidence Summary `[M]`

Samo strukturisane činjenice i statusi.

---

## E9 — Scale samo po dokazanoj potrebi

Mogući sadržaj stare Faze 24:

```text
PostgreSQL
multi-machine/team read-model
central artifact store
VS Code extension
shared project state
organization integrations
```

I dalje nisu FlowOS core:

```text
remote agent workers
agent scheduler
agent sandbox orchestrator
model provider router
LLM inference service
```

---

## Gate E

Pošto E nije linearna faza, gate se provjerava **po grupi**:

```text
[ ] konkretan dogfooding problem je dokumentovan
[ ] postojeći servis/reuse odluka je provjerena
[ ] nema novog source of truth bez potrebe
[ ] nema LLM/orchestration creepa
[ ] task ima S/M/L size
[ ] svaki L task je prije implementacije provjeren da nije XL
[ ] mehanički guard ima replay proof ako postaje enforcement
[ ] korisnik je eksplicitno odabrao da se baš ta grupa aktivira
```

---

# 13. Preslikavanje v4.3 → v5

Postojeći FLOW brojevi se ne renumerišu.

| FLOW / ljudski naziv | v4.3 lokacija | v5 lokacija |
|---|---|---|
| FLOW-1109 — Redakcija tajni iz logova i artefakata | stara Faza A | ZAVRŠENO — uklonjeno iz aktivnog v5 roadmapa |
| FLOW-1110 — Siguran worktree identitet i cleanup | stara Faza A | A |
| FLOW-1105 — Usklađivanje GUI/backend Plan Import formata | stara Faza A | A |
| FLOW-1106 — Stvarni uvoz dogfooding plana | stara Faza A | A |
| FLOW-1111 — Passive Session Contract | stara Faza A | A |
| FLOW-1112 — Evidence Semantics Contract | stara Faza A | A |
| FLOW-1200 — Task-centric GUI primitives | Faza 12 | E — ODGOĐENO |
| FLOW-1201 — Minimalni izbor i registracija projekta | Faza 12 | C |
| FLOW-1202 — Zadaci na stvarni backend | Faza 12 | C — postaje tabla |
| FLOW-1203 — Task Current State read-model | Faza 12 | C — sveden na board row read-model |
| FLOW-1204 — Task Detail GUI | Faza 12 | E — ODGOĐENO |
| FLOW-1301 — Workflow history read-model | Faza 13 | C — latest workflow state za board |
| FLOW-1302 — Workflow History GUI | Faza 13 | E — ODGOĐENO |
| FLOW-1303 — Otvaranje stvarnih dokaza | Faza 13 | C |
| FLOW-1304 — Workflow History ≠ Technical Activity | Faza 13 | E — ODGOĐENO |
| FLOW-1305 — Regression Proof baseline | Faza 13 | A |
| FLOW-1401 — TASK_DECISION kontrole | Faza 14 | C |
| FLOW-1402 — Backend-confirmed consequence | Faza 14 | C |
| FLOW-1403 — Kompletan dogfooding tok | Faza 14 | C |
| FLOW-1404 — SessionTaskBinding historical proof | Faza 14 | E — ODGOĐENO |
| FLOW-1501 — Zabilježiti UX probleme | Faza 15 | E — ODGOĐENO |
| FLOW-1502 — Pojednostaviti navigaciju | Faza 15 | E — ODGOĐENO |
| FLOW-1503 — Ukloniti MOCK/live nejasnoće | Faza 15 | E — ODGOĐENO |
| FLOW-1504 — Zamrznuti dogfood baseline | Faza 15 | E — ODGOĐENO |
| FLOW-1505 — Velocity calibration | Faza 15 | B |
| FLOW-1601 — Strukturisani Current State | Faza 16 | E |
| FLOW-1602 — Project State | Faza 16 | E |
| FLOW-1603 — Human Attention State | Faza 16 | E |
| FLOW-1604 — Handoff State | Faza 16 | D |
| FLOW-1605 — Handoff rendereri | Faza 16 | D |
| FLOW-1606 — Fresh-session dogfood | Faza 16 | E |
| FLOW-1701 — Finding model | Faza 17 | E |
| FLOW-1702 — FINDING_DECIDED | Faza 17 | E |
| FLOW-1703 — FIX_COMPLETED | Faza 17 | E |
| FLOW-1704 — VERIFICATION_COMPLETED | Faza 17 | E |
| FLOW-1705 — Findings GUI | Faza 17 | E |
| FLOW-1706 — USER_VALIDATION kandidat | Faza 17 | E |
| FLOW-1801 — Task Contract v2 | Faza 18 | E — proširenje v1 |
| FLOW-1802 — Risk/size-based planning depth | Faza 18 | E |
| FLOW-1803 — Program Design artifact | Faza 18 | E |
| FLOW-1804 — Decision Inbox | Faza 18 | E |
| FLOW-1805 — Vertical Slice Plan | Faza 18 | E |
| FLOW-1901 — External Session metadata | Faza 19 | E |
| FLOW-1902 — Session ↔ Git correlation | Faza 19 | E |
| FLOW-1903 — Evidence ingestion | Faza 19 | E |
| FLOW-1904 — Information semantics enforcement | Faza 19 | E |
| FLOW-1905 — Stale evidence detection | Faza 19 | D |
| FLOW-2001 — Guard Registry | Faza 20 | E |
| FLOW-2002 — Deterministički izvori | Faza 20 | E |
| FLOW-2003 — Architecture guardovi | Faza 20 | E |
| FLOW-2004 — Repeated Finding → Guard Candidate | Faza 20 | E |
| FLOW-2005 — Guard provenance | Faza 20 | E |
| FLOW-2100 — Dependency Evidence Strategy | Faza 21 | E |
| FLOW-2101 — WRITE_OVERLAP | Faza 21 | E |
| FLOW-2102 — STALE_BASE | Faza 21 | E |
| FLOW-2103 — DEPENDENCY_REFERENCE | Faza 21 | E |
| FLOW-2104 — ASSUMPTION_INVALIDATED | Faza 21 | E |
| FLOW-2201 — Project Readiness | Faza 22 | E |
| FLOW-2202 — Bottleneck View | Faza 22 | E |
| FLOW-2203 — Human Attention Projection | Faza 22 | E |
| FLOW-2301 — Review budget | Faza 23 | E |
| FLOW-2302 — Comprehension checkpoint | Faza 23 | E |
| FLOW-2303 — Deterministički Evidence Summary | Faza 23 | E |

Novi FLOW brojevi uvedeni change specom koriste rezervisani opseg 1150–1199:

```text
Faza A: 1150–1157
Faza B: 1160–1167
Faza D: 1170–1172
Faza C: 1180–1181
```

Nijedan stari FLOW broj nije ponovo upotrijebljen za drugi sadržaj.

---

# 22. GUI north star

GUI se organizuje prema ljudskim pitanjima.

## Pregled

```text
Šta se promijenilo?
Šta traži pažnju?
Šta je aktivno?
Gdje sam stao?
```

## Zadaci

Glavna radna površina.

## Plan

Mapa pravca i zavisnosti.

## Aktivnost

Technical activity / dijagnostika.

## Task Detail

Centralna jedinica razumijevanja i odluke.

### GUI arhitektonsko pravilo

Prije dodavanja novog Task-centric ekrana prvo provjeriti može li koristiti primitive iz FLOW-1200.

Ako ne može, dokumentovati zašto prije pravljenja novog paralelnog widget obrasca.

---
# 23. „Gdje si stao“

Project Resume nije source of truth.

To je Current State projekcija.

Za projekat:

```text
current goal
last relevant Task
latest evidence
Git/reconciliation
open blockers
next required workflow phase
```

Za Task:

```text
current implementation state
latest verification
latest review
latest decision
next required action
```

`next required action` dolazi iz state machine-a ili eksplicitnog workflow pravila.

Ne iz LLM zaključka.

---
# 24. Context pravila

## Stable context

```text
AGENTS.md
ADRs
architecture docs
project conventions
verification commands
external-system metadata bez secreta
```

## Current context

FlowOS projection.

## History

```text
Git
Ledger
Events
Reports
```

## Conversation

Privremeni kontekst eksternog alata.

FlowOS ne pokušava da conversation history pretvori u vlastiti LLM memory.

---
# 25. `docs/external/` i durable project knowledge

Vrijedna praksa:

```text
docs/adr/
docs/external/
```

`docs/external/` može opisati:

- env var nazive;
- deployment lokaciju;
- payment provider;
- test account oznake;
- support kanal;
- vanjske API contracte.

Nikada secret vrijednosti.

FlowOS može deterministički uključiti reference u Handoff projekciju.

---
# 26. Sigurnosno stanje i numerisane obaveze

Ova sekcija više se ne zove „non-regression contract“ za stavke koje još nisu implementirane. Razdvaja ono što je potvrđeno u postojećem kodu od onoga što v5 tek zahtijeva.

## 26.1 Potvrđeno stanje — path safety problem postoji

Nikad:

```text
string prefix = containment ili identity
```

Na fiksiranom SHA-u ostaju unsafe prefix provjere u worktree servisu. Rješava ih `FLOW-1110 — Siguran worktree identitet i cleanup`.

## 26.2 Obaveza — process lifecycle `[FLOW-1152]`

Odnosi se samo na FlowOS-owned subprocess:

- exit code se čuva tačno;
- timeout mora dokazivo završiti cijelo FlowOS-owned stablo;
- FlowOS ne tvrdi da kontroliše eksterni agent;
- nema agent cancel/retry lifecycle-a.

## 26.3 Obaveza — filtered environment `[FLOW-1151]`

Za FlowOS-owned subprocess:

- filtered env;
- secret vrijednosti se ne loguju;
- kritične varijable imaju jasna pravila;
- jedan centralni wrapper je boundary.

## 26.4 Potvrđeno pravilo — Watcher/Git

- callback greške se ne smiju nevidljivo izgubiti;
- stop je idempotentan;
- untracked files se vide;
- Git parser je stabilan;
- watcher event nije workflow completion.

## 26.5 Potvrđeno pravilo — Historical replay je read-only prema aktivnom implementation treeju

Dozvoljeno:

```text
git show
git ls-tree
git cat-file
```

Za izvršni test starog stanja:

```text
privremeni/detached worktree
ili izolovana scratch lokacija
```

Zabranjeno nad aktivnim implementation worktreejem:

```text
git checkout
git reset
git restore
```

radi historical replay-a.

Regression gate:

```text
dirty implementation worktree
+ historical replay
→ implementation diff ostaje byte-identičan
```

---
# 27. Standardni acceptance gate za budući Task

Svaki netrivijalni Task treba imati najmanje:

```text
1. cilj
2. scope / out-of-scope
3. DoD / acceptance
4. Git baseline
5. exact changed-files pregled
6. targeted tests
7. relevant regression
8. scripts/verify.py gdje je primjenjivo
9. Implementer/AgentReport ako se koristi
10. independent review za HIGH/rizičan rad
11. human TASK_DECISION gdje workflow to zahtijeva
12. commit scope provjeru
13. remote SHA provjeru prije tvrdnje "pushed"
14. historical replay ne smije mutirati aktivni worktree
15. evidence za bounded contract deviation ako postoji
```

Agentov report nikada nije sam po sebi acceptance.

---
# 28. Commit / integration gate

Prije commita:

```text
git status
exact diff
unrelated files excluded
fresh tests
review stanje
open material findings = none
```

Poslije commita/pusha:

```text
verify SHA
verify remote target gdje je relevantno
clean/expected working tree
```

---
# 29. Sizing pravila i mapa v5

## Pravila

```text
S = jedan mali, dobro omeđen vertical change
M = nekoliko povezanih promjena, ali jedan jasan subsystem/use-case
L = veći ekran/read-model ili više slojeva koji moraju zajedno proraditi
XL = NIJE implementabilan roadmap task; razbiti prije rada
```

## Faza A

| Task | Size |
|---|---:|
| FLOW-1110 — Siguran worktree identitet i cleanup | L |
| FLOW-1105 — Usklađivanje GUI/backend Plan Import formata | M |
| FLOW-1106 — Stvarni uvoz dogfooding plana | S |
| FLOW-1111 — Passive Session Contract | S |
| FLOW-1112 — Evidence Semantics Contract | M |
| FLOW-1150 — Report front-matter v2 / reviewer verdict | M |
| FLOW-1151 — Filtriran subprocess environment | S |
| FLOW-1152 — Process-tree timeout | M |
| FLOW-1153 — Linux source support | M |
| FLOW-1154 — CI Windows + Linux | S |
| FLOW-1155 — Dokumentaciona sinhronizacija | S |
| FLOW-1305 — Adversarial Regression Proof | M |
| FLOW-1157 — Composition-root cleanup | M |
| FLOW-1156 — Architecture guard extension | M |

## Faza B

| Task | Size |
|---|---:|
| FLOW-1160 — Task Contract v1 | M |
| FLOW-1161 — Uloge | M |
| FLOW-1162 — Risk reviewer gate | S |
| FLOW-1163 — File claims | M |
| FLOW-1164 — allowed_paths overlap | S |
| FLOW-1165 — stale claim | S |
| FLOW-1166 — dependency in main | S |
| FLOW-1167 — post-merge gate | M |
| FLOW-1505 — Velocity calibration | S |

## Faza C — 10 aktivnih taskova

| Task | Size |
|---|---:|
| FLOW-1201 — Project selection | S |
| FLOW-1202 — Zadaci = board | M |
| FLOW-1203 — Task Board read-model | M |
| FLOW-1301 — Workflow state read-model | M |
| FLOW-1303 — Evidence opening | M |
| FLOW-1180 — Detekcija tišine | M |
| FLOW-1181 — Čeka na mene | S |
| FLOW-1401 — TASK_DECISION kontrole | M |
| FLOW-1402 — Backend-confirmed consequence | S |
| FLOW-1403 — Dogfooding E2E | M |

## Faza D

| Task | Size |
|---|---:|
| FLOW-1170 | L |
| FLOW-1171 | M |
| FLOW-1172 | S |
| FLOW-1905 | L |
| FLOW-1604 | M |
| FLOW-1605 | S |

## Faza E — uključuje i odgođene C taskove

Odgođeni taskovi zadržavaju svoj postojeći size:

```text
1200 M
1204 L
1302 M
1304 S
1404 M
1501 S
1502 M
1503 M
1504 S
```

Ostali conditional taskovi ostaju S/M/L kako je opisano u §12. Nijedan nema XL status; svaki koji u designu ispadne XL mora biti razbijen prije implementacije.

---

# 30. Metrike koje imaju smisla

Prvo kvalitativni dogfooding.

Kasnije:

```text
time-to-resume
time-to-find-evidence
time-to-review
cycle time do accepted commita
review yield
rework
conflict detection before integration
IMPLEMENTED → VERIFIED conversion
VERIFIED → ACCEPTED conversion
human coordination time
stale/missing evidence count
conflicts caught before integration
```

Ne koristiti kao north star:

```text
lines of code
number of agents
number of sessions
token utilization
number of model calls
number of commits
```

---
# 31. Prioriteti v5 — A do E

## FAZA A — Ugovori i blokatori

Obavezna prije novog workflow/GUI širenja.

```text
1110
1105
1106
1111
1112
1150
1151
1152
1153
1154
1155
1305
1157
1156
```

`1305` je pravilo prije/za execution-path promjene; zato mora biti aktivno prije acceptancea `1157`. Redoslijed `1157 → 1156` ostaje obavezan.

## FAZA B — Blueprint jezgro

```text
1160–1167
1505
```

## FAZA C — Čovjekova radna površina: board-first Milestone 1

```text
1201
1202
1203
1301
1303
1180
1181
1401
1402
1403
```

Tačno **10 aktivnih taskova**. Sve ostalo iz starih faza 12–15 je odgođeno u E.

## FAZA D — Agentska read površina

```text
1170–1172
1905
1604–1605
```

## FAZA E — Uslovljeno proširenje

Prvo sadrži odgođene taskove iz stare C:

```text
1200
1204
1302
1304
1404
1501–1504
```

Zatim sve ostale conditional grupe iz §12. Nema obećanog redoslijeda; aktivira se samo grupa koja prođe svoj gate.

---

# 32. Šta se eksplicitno NE gradi

Ovo nije samo „ne sada“.

Ovo nije FlowOS core misija:

```text
interni LLM
LLM API pozivi radi zaključivanja
AI orchestration engine
agent launcher
agent process manager
agent scheduler
agent retry/correction loop
autonomous task decomposition
automatic model router
model recommendation engine
opinion/debate/fusion engine
multi-agent collaboration executor
automatic prompt dispatch
worker/checker orchestrator
durable agent job engine
remote agent workers
agent sandbox orchestration
AI priority score
AI completion percentage
LLM-generated Current State kao authority
LLM sažimanje konteksta radi token budžeta
LLM-generated evidence
auto merge/push
vlastiti general-purpose GitNexus replacement
```

---
# 33. Test matrica

## Passive Session Contract

- registracija Sessiona ne spawn-uje agent process;
- nema hidden child launch-a;
- session close nije completion;
- external session ID može nedostajati;
- worktree binding je opcioni dokaz, ne izmišljeni ownership.

## Evidence semantics

- claim nije mechanical evidence;
- derived fact navodi source facts;
- heuristic signal je vizuelno/semantički odvojen;
- human decision ostaje canonical authority;
- unknown ostaje unknown.

## Current State

- stariji report vs novija canonical odluka;
- missing evidence;
- unassigned report;
- multiple sessions;
- historical binding;
- stale Git snapshot;
- no history.

## Task Detail

- Task sa/bez PlanItem;
- implementation bez testova;
- test bez reviewa;
- accepted ali nije verified;
- evidence missing;
- claim + mechanical evidence prikazani različito.

## GUI primitives

- Empty/Unknown/MissingEvidence stanja konzistentna;
- Timeline koristi isti primitive u History i Findings gdje je prikladno;
- DecisionPanel nije dupliran po ekranima;
- novi ekran ne zahtijeva copy/paste cijelog detail layouta.

## Handoff

- fresh eksterni session;
- drugi alat/model;
- current decision supersedes old;
- missing reference;
- worktree changed;
- blocker postoji;
- FlowOS ne šalje handoff automatski.

## Attribution

- explicit binding + isolated worktree → DIRECT;
- isolated worktree bez potpunog bindinga → ISOLATED;
- shared-tree temporal signal → HEURISTIC;
- insufficient evidence → UNKNOWN;
- HEURISTIC ne proizvodi hard block.

## Historical replay

- dirty implementation worktree ostaje byte-identičan;
- read-only Git ili temp worktree;
- nema checkout/reset/restore nad aktivnim implementation treejem.

## Cross-worktree conflicts

- write overlap;
- stale base;
- dependency reference preko provider evidence-a;
- zero path overlap + dokaziva dependency referenca;
- unrelated modul ne daje false positive;
- HEURISTIC ownership ne podiže hard conflict severity.

## Dependency provider

- GitNexus rezultat ima provenance;
- unavailable provider ne ruši core FlowOS;
- provider output nije canonical authority;
- nema dupliranja generičkog graph engine-a bez dokazane potrebe.

## Guards

- deterministic guard nalazi poznat prekršaj;
- false positive nije predstavljen kao dokazani failure;
- guard promjena ima provenance;
- repeated finding samo stvara candidate;
- FlowOS ne pokušava automatski fix.

---
# 34. Predloženi razvojni ritam

Za svaki Task:

```text
1. jedan Task
2. jedan odgovorni implementer
3. evidence
4. independent reviewer kada je opravdano
5. jedan finding/fix scope po korekciji
6. user decision
7. exact commit
8. remote verification
9. tek onda sljedeća akcija
```

Implementer može biti čovjek ili eksterni agentski alat koji čovjek koristi.

FlowOS ga ne bira i ne pokreće.

Za svaki `L` Task prije rada:

```text
provjeri da nije zapravo XL
provjeri GUI reuse
provjeri da ne uvodi novi source of truth
provjeri da ne uvodi skriveni LLM/agent orchestration
```

---
# 35. Kada ćemo znati da je FlowOS stvarno uspio

## Milestone 1

> **Jedan stvarni development Task može od početne namjere do ljudske odluke biti razumljiv i dokaziv kroz LIVE FlowOS bez ručne rekonstrukcije iz chatova, terminala i report direktorijuma.**

## Milestone 2

> **FlowOS deterministički generiše dovoljan Handoff da korisnik ručno otvori novu eksternu sesiju i nastavi rad bez prethodnog chata.**

## Milestone 3

> **FlowOS jasno razlikuje SOURCE_FACT, DERIVED_FACT, HEURISTIC_SIGNAL, CLAIM i HUMAN_DECISION.**

## Milestone 4

> **FlowOS prije integracije hvata relevantan worktree/dependency konflikt bez izgradnje vlastitog general-purpose dependency engine-a.**

## Milestone 5

> **Ponovljeni materijalni finding može, uz ljudsku odluku, postati deterministički guard.**

## Milestone 6

> **Dogfooding daje stvaran velocity uzorak iz kojeg je moguće realnije procijeniti veličinu narednih faza.**

Ni jedan milestone ne zahtijeva interni LLM niti pokretanje agenta iz FlowOS-a.

---
# 36. Konačna razvojna mapa

```text
SADA
│
▼
FAZA A — UGOVORI I BLOKATORI
│
├─ FLOW-1110  Safe worktree identity
├─ FLOW-1105  PlanImport canonical contract
├─ FLOW-1106  Real dogfood import
├─ FLOW-1111  Passive Session Contract
├─ FLOW-1112  Evidence Semantics
├─ FLOW-1150  Report/reviewer contract v2
├─ FLOW-1151  Filtered subprocess env
├─ FLOW-1152  Process-tree timeout
├─ FLOW-1153  Linux source support
├─ FLOW-1154  Windows + Linux CI
├─ FLOW-1155  Docs sync
├─ FLOW-1305  Adversarial Regression Proof rule
├─ FLOW-1157  Composition-root cleanup
└─ FLOW-1156  Architecture guard extension + replay
        │
        ▼
FAZA B — BLUEPRINT JEZGRO
│
├─ FLOW-1160  Task Contract v1
├─ FLOW-1161  Roles
├─ FLOW-1162  Risk/reviewer gate
├─ FLOW-1163  File claims
├─ FLOW-1164  allowed_paths overlap
├─ FLOW-1165  Stale claim
├─ FLOW-1166  Dependency really in main
├─ FLOW-1167  Post-merge integration gate
└─ FLOW-1505  Velocity calibration
        │
        ▼
FAZA C — ČOVJEKOVA RADNA POVRŠINA / TASK BOARD
│
├─ FLOW-1201  Project selection
├─ FLOW-1202  Zadaci = jedna tabla svih aktivnih Taskova
├─ FLOW-1203  Board row read-model preko EvidenceService-a
├─ FLOW-1301  Latest canonical workflow state
├─ FLOW-1303  Otvaranje stvarnog evidencea
├─ FLOW-1180  Tišina / nema signala
├─ FLOW-1181  Čeka na mene
├─ FLOW-1401  Human TASK_DECISION sa table
├─ FLOW-1402  Canonical reload poslije odluke
└─ FLOW-1403  Real dogfooding E2E
        │
        ▼
MILESTONE 1
"Ne moram obilaziti terminale da vidim gdje je svaki Task."
        │
        ▼
FAZA D — AGENTSKA READ POVRŠINA
│
├─ FLOW-1170  Read-only canonical access
├─ FLOW-1171  Semantics + provenance
├─ FLOW-1172  Formalized report ingestion
├─ FLOW-1905  Stale evidence
└─ FLOW-1604/1605  Handoff State + renderers
        │
        ▼
MILESTONE 2
"Fresh agent može povući isto canonical stanje koje vidi čovjek."
        │
        ▼
FAZA E — SAMO AKO DOKAZANO TREBA
│
├─ ODGOĐENO: 1200 / 1204 / 1302 / 1304 / 1404 / 1501–1504
├─ Current State / Attention
├─ Structured Findings
├─ Task Contract v2 / Program Design
├─ Observability/correlation
├─ Guards/sensors
├─ Conflict intelligence
├─ Readiness/bottleneck
├─ Human comprehension
└─ Scale
```

Ne postoji grana:

```text
Agent launcher
Managed agent execution
Model routing
Durable agent jobs
Worker/checker orchestrator
LLM-in-FlowOS
```

---

# 37. Trajni filter za svaku novu ideju

## Q1 — Da li funkcija zahtijeva da FlowOS pokrene, promptuje, rasporedi, izabere, retry-a ili kontroliše LLM/agent?

Ako **DA**:

> **nije FlowOS core funkcija.**

## Q2 — Može li FlowOS funkciju pouzdano ostvariti iz Git-a, filesystema, SQL-a, parsera, AST-a za usko pravilo, state machine-a, strukturisanog artefakta, eksternog determinističkog evidence provider-a ili testa?

Ako **DA**:

> **dobar je kandidat za FlowOS.**

## Q3 — Koja je semantička klasa rezultata?

```text
SOURCE_FACT?
DERIVED_FACT?
HEURISTIC_SIGNAL?
CLAIM?
HUMAN_DECISION?
```

Ako se ne može jasno klasifikovati, funkcija nije spremna za canonical workflow.

## Q4 — Da li novi subsystem duplira specijalizovani alat koji već postoji?

Ako **DA**:

> prvo pokušati read-only integration/evidence provider, pa tek onda graditi vlastiti mehanizam.

## Q5 — Da li novi GUI ekran ponavlja postojeći Task-centric obrazac?

Ako **DA**:

> prvo pokušati reuse FLOW-1200 primitive-a.

---
# 38. Konačna preporuka

FlowOS treba ostati mali u svojoj vrsti odgovornosti, čak i ako postane funkcionalno bogat.

Njegova vrijednost nije:

```text
da zamijeni Claude Code
da zamijeni Codex
da napravi vlastiti agent harness
da bira najbolji model
da vodi agente kroz taskove
da pravi svoj GitNexus
```

Njegova vrijednost je:

```text
da zna koji Task postoji
da zna koji plan i odluka važe
da zna gdje je stvarni Git/worktree state
da zna šta se promijenilo
da zna koji evidence postoji
da razlikuje činjenicu, izvedeni dokaz, heuristiku i claim
da pokaže stale ili nedostajući evidence
da poveže review i finding sa konkretnim Taskom
da pokaže konflikt bez izmišljanja ownershipa
da generiše portable Handoff iz canonical state-a
da čovjeku omogući odluku sa manjim mentalnim teretom
```

Osnovni princip ostaje:

> **AI radi. FlowOS pamti, povezuje i dokazuje. Čovjek odlučuje.**

A v4.3 dodaje još dvije praktične zaštite:

> **FlowOS radije priznaje UNKNOWN nego da izmisli atribuciju.**

> **FlowOS radije koristi provjerljiv dokaz specijalizovanog alata nego da gradi drugi paralelni sistem bez potrebe.**
