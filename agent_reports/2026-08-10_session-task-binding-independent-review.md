---
flowos_report_version: 1
agent: claude
model: claude-sonnet-5
session_id: unknown
report_type: review
tasks:
  - unassigned
commits: []
created_at: 2026-08-11T00:00:00+02:00
---

# SessionTaskBinding — faza 1 — nezavisni review

## Datum

2026-08-10 (review izvršen 2026-08-11)

## Agent / model / sesija

- Agent: claude (Claude Code)
- Model: claude-sonnet-5
- Sesija: unknown

## Scope

Nezavisan review implementacije `SessionTaskBinding` faza 1 (codex/gpt-5, izvještaj
`agent_reports/2026-08-10_session-task-binding-phase1.md`), baseline commit
`0206df00e345643cb7f3ee9a49077a4b48c71d8e`. Cilj: utvrditi postoji li konkretan
bug, data-integrity, transakcijski ili arhitektonski problem koji sprečava
prihvatanje/commit. Kod NIJE mijenjan, commit NIJE napravljen.

## Metod

- Pročitan `AGENTS.md`, `CLAUDE.md`, prethodni implementacijski `agent_report`.
- Pročitan kompletan kod: `bindings.py`, `service.py`, `completion.py`, HTTP
  `sessions.py`, ORM model (`models.py`), enum, Pydantic contracts, Alembic
  migracija, test fajl `tests/integration/test_session_task_bindings.py`.
- Pokrenuti postojeći testovi i `scripts/verify.py` (rezultati ispod).
- Za tri konkretne hipoteze (redoslijed operacija u `switch_binding`, ponašanje
  HTTP sloja pri neuspjelom switch-u, i FK `ON DELETE SET NULL` nad istorijskim
  bindingom) napravljene su izolovane probe skripte protiv stvarnog koda (ne
  protiv izmijenjenog koda) da bi se tvrdnje dokazale, a ne pretpostavile.
  Probe skripte su privremene, van repozitorija (scratchpad), nisu commitovane.

## Pokrenute provjere

```text
python -m pytest tests/integration/test_session_task_bindings.py -q
→ 14 passed, 1 warning
```

```text
python scripts/verify.py
→ 306 passed (unit/integration/contract korak)
→ Prošlo: 7/7
→ VERIFIKACIJA PROŠLA
```

Rezultati se poklapaju s tvrdnjama iz implementacijskog izvještaja.

## Nalazi

```text
ID: F1
Severity: HIGH
Fajl/simbol: src/flowos/service/services/sessions/bindings.py — SessionTaskBindingService.switch_binding()
Problem: Postojeći aktivni binding se zatvara (_close_binding, linija ~66-67) PRIJE
nego što se validira da novi target (Task/PlanItem) uopšte postoji i pripada
istom projektu (_validate_target_project, poziva se tek poslije). Ako validacija
padne, funkcija baca ValueError, ali ORM objekat starog bindinga je već mutiran
(ended_at postavljen) u SQLAlchemy Session identity mapi. Izvještaj tvrdi da se
sve "flushuje kao jedna transakcija" (implying atomičnost) — to nije tačno na
nivou same funkcije; atomičnost trenutno postoji samo kao SPOREDNI efekat toga
što jedini pozivalac (HTTP switch endpoint) radi rollback pri bilo kom
Exception-u u `get_session` dependency-ju.
Kako se reprodukuje: Pozvati switch_binding(session_id, task_id="nepostojeci-id")
na sesiji koja već ima aktivan binding, NE raditi db.rollback() poslije uhvaćenog
ValueError-a, zatim pozvati bilo koji naredni db.flush()/commit() u istoj
SQLAlchemy sesiji. Dokazano probe skriptom: rezultat je sesija sa NULA aktivnih
bindinga (stari zatvoren, novi nikad kreiran), dok AgentSession.task_id (legacy
pointer) i dalje pokazuje na STARI task — direktna kontradikcija između
"autoritativne istorije" (bez aktivnog bindinga) i legacy pointera (pokazuje na
task koji binding istorija tvrdi da više nije aktivan).
Zašto je bitno: Trenutno jedini pozivaoci su HTTP switch endpoint (koji ispravno
rollback-uje zahvaljujući `except Exception: session.rollback()` u
`get_session()`) i `create_session()` (gdje nema postojećeg aktivnog bindinga za
zatvaranje, pa se bug ne može okinuti). Kroz te dvije trenutno postojeće ulazne
tačke, DEMONSTROVANO (probe_http_switch_rollback.py) da se ispravno stanje
očuva. Bug je zato LATENTAN, ne trenutno eksploatabilan preko postojećeg API-ja
— ali funkcija sama po sebi NIJE atomична/sigurna, i bilo koji budući direktni
pozivalac servisnog sloja (CLI wrapper, background job, WebSocket handler) koji
ne prolazi kroz identičan rollback-on-exception request wrapper će proizvesti
sesiju bez ijednog aktivnog bindinga.
Dokaz: probe_switch_order.py (lokalno, van repoa) — nakon neuspjelog switch-a i
sledećeg flush-a bez rollback-a: `get_active_binding() posle flush: None`,
`Broj bindinga ukupno: 1`, taj jedan binding ima `ended_at` postavljen a
`task_id` je STARI task. probe_http_switch_rollback.py potvrđuje da HTTP put
ipak ostaje ispravan (1 aktivan binding, nepromijenjen) zahvaljujući rollback-u
na nivou `get_session` dependency-ja.
Preporučena korekcija: Zamijeniti redoslijed — prvo `_validate_target_project(...)`,
tek onda `_close_binding(active, now)` i kreiranje novog bindinga. Ovo je izmjena
od par linija bez promjene ugovora.
```

```text
ID: F2
Severity: HIGH
Fajl/simbol: alembic/versions/9b2d1f7a4c63_session_task_bindings.py — FK task_id/plan_item_id ON DELETE SET NULL
Problem: `session_task_bindings.task_id` i `.plan_item_id` imaju `ondelete="SET NULL"`
prema `tasks.id` odnosno `plan_items.id`. Kad se referencirani Task (ili PlanItem)
kasnije obriše, FK automatski postavlja `task_id = NULL` na SVIM istorijskim
binding zapisima koji su ga referencirali — uključujući ZATVORENE (već završene)
segmente, ne samo aktivni. Pošto je "TASK" vs "UNASSIGNED" kind izveden isključivo
iz `task_id != NULL` (vidi `_binding_to_response` u sessions.py i identična logika
u testovima), zatvoren istorijski TASK binding postaje bit-za-bit neraspoznatljiv
od UNASSIGNED bindinga — bez ikakvog traga (nema snapshot naslova, nema tombstone
kolone, nema eventa) da je binding ikad imao target.
Kako se reprodukuje: Kreirati sesiju sa task_id, završiti sesiju (end_session),
zatim obrisati taj Task preko postojećeg `DELETE /tasks/{task_id}` endpointa
(TaskService.delete_task — hard delete, `session.delete(task)`). Istorijski
binding koji je opisivao "sesija je radila na Task A" sada izgleda kao "sesija
nikad nije bila dodijeljena nijednom tasku".
Zašto je bitno: Izvještaj eksplicitno predstavlja `SessionTaskBinding` kao "novu
autoritativnu istoriju promjena task konteksta" i CLAUDE.md tretira istoriju kao
append-only, nepromjenjivu ("Append-only događaje ne prepisivati"). Ovo ponašanje
tiho prepisuje značenje već zabilježene istorije kao nusprodukt sasvim obične,
već postojeće operacije (brisanje taska) — bez upozorenja, bez loga, bez testa
koji bi ovo uhvatio. Nalaz je EKSPLICITNO tražen u naloga za review i NIJE
pomenut u "Rizici i ograničenja" sekciji implementacijskog izvještaja.
Napomena: Za `plan_item_id` isti FK rizik postoji u šemi, ali trenutno ne postoji
HTTP DELETE endpoint za PlanItem (provjereno gerp-om), pa je taj dio rizika danas
neeksploatabilan — ali je isto arhitektonski prisutan ako se takav endpoint doda
kasnije bez revizije ove migracije.
Dokaz: probe_delete_task_history.py — binding kind PRIJE brisanja: `TASK`
(task_id=<uuid>). POSLIJE `TaskService(db).delete_task(task_a_id)`: isti binding
red, `task_id=None`, izračunati kind = `UNASSIGNED`.
Preporučena korekcija (bez izmjene sada — samo predlog za odluku korisnika):
razmotriti `ON DELETE RESTRICT`/zabranu brisanja taska koji ima istorijski
binding, ili snapshot polje (npr. `task_title_snapshot`) koje preživljava
brisanje reference, ili poseban `binding_kind` koji se upisuje pri kreiranju i
ne zavisi naknadno od trenutnog stanja FK-a.
```

```text
ID: F3
Severity: MEDIUM
Fajl/simbol: src/flowos/service/controllers/http/sessions.py — switch_session_binding()
Problem: Endpoint hvata isključivo `ValueError` i mapira ga na 404/409. Kada dva
switch zahtjeva za istu sesiju istinski trkaju (obje pročitaju isti aktivni
binding prije nego ijedna komituje), partial unique index
(`uq_session_task_bindings_active`) ispravno odbija duplikat AKTIVNOG bindinga —
ali to čini bacanjem `sqlalchemy.exc.IntegrityError`, koji NIJE `ValueError` i
NIJE uhvaćen u endpointu. Taj exception probija do `get_session` dependency-ja
(koji ga generički hvata i radi rollback — podaci ostaju ispravni), ali dalje
propagira kroz FastAPI kao neuhvaćen 500 Internal Server Error umjesto
kontrolisanog 409 Conflict.
Kako se reprodukuje: Dva switch zahtjeva na istu sesiju čije čitanje aktivnog
bindinga vremenski preklapa (prije commita bilo kog od njih).
Zašto je bitno: Integritet PODATAKA je očuvan (partial unique index radi kako
treba, dokazano probom) — ovo NIJE data-integrity bug. Jeste API/error-handling
robusnost problem: gubitnik trke dobija sirovu 500 grešku bez jasne poruke da je
neko drugi upravo promijenio binding, umjesto smislenog "pokušaj ponovo" 409
odgovora.
Dokaz: probe_true_race.py — ručno interleave-ovana simulacija dvije transakcije
koje čitaju isti aktivni binding prije bilo kog commita. T1 komituje uspješno.
T2 (na osnovu "zastarjele" reference) baca `sqlite3.IntegrityError: UNIQUE
constraint failed: session_task_bindings.session_id` na commit. Konačno stanje
baze: 2 bindinga ukupno, tačno 1 aktivan (ispravno) — ali gubitnik trke dobija
neobrađen IntegrityError, ne ValueError.
Preporučena korekcija: dodati `except IntegrityError` u `switch_session_binding`
i mapirati na 409 Conflict (analogno ostalim 409 slučajevima).
```

```text
ID: F4
Severity: MEDIUM
Fajl/simbol: tests/integration/test_session_task_bindings.py
Problem: Test fajl dobro pokriva "sretne puteve" i navedene A–N scenarije iz
naloga (početni TASK/PLAN_ITEM/UNASSIGNED binding, TASK→TASK, TASK→UNASSIGNED,
UNASSIGNED→TASK, cross-project odbijanje za Task i PlanItem, najviše jedan
aktivan binding na DB nivou, session end zatvara binding, legacy pointer sync,
nekonzistentan task_id+plan_item_id par, hronologija, zabrana forge-ovanja
binding_source). Nedostaju testovi za scenarije koji bi upravo uhvatili F1–F3:
- exception/rollback usred switch-a (F1) — nema nijednog testa koji poziva
  switch_binding sa nevalidnim targetom NA SESIJI KOJA VEĆ IMA aktivan binding
  i provjerava da aktivni binding ostaje netaknut nakon neuspjeha (postojeći
  test_cross_project_task_is_rejected koristi sesiju BEZ prethodnog aktivnog
  bindinga, pa ne testira zatvaranje-pa-neuspjeh scenario);
- konkurentni/skoro-istovremeni switch (F3) — nema testa;
- delete Task/PlanItem nakon što postoji istorijski binding (F2) — nema testa;
  ovo je test koji bi direktno uhvatio F2 prije prihvatanja;
- switch sa `switched_at` starijim od `started_at` aktivnog bindinga — kod ima
  zaštitu (`_close_binding` baca ValueError ako je `ended_at < started_at`), ali
  nijedan test je ne vežba direktno kroz `switch_binding`;
- završetak legacy sesije bez ijednog bindinga (npr. sesija kreirana prije ove
  migracije) — kod izgleda bezbjedan po čitanju (`close_active_binding` vraća
  None ako nema aktivnog bindinga), ali nema regresionog testa koji to
  eksplicitno dokazuje za `end_session`/`complete_session`.
Zašto je bitno: Ovo su tačno scenariji koje je nalog za review eksplicitno
tražio, i upravo nedostatak testa za "delete Task nakon bindinga" je razlog zašto
F2 nije uhvaćen prije review-a.
Preporučena korekcija: dodati regresione testove za gornje scenarije, posebno za
F1 (validacija-pa-zatvaranje umjesto zatvaranje-pa-validacija) i F2 (delete Task
→ provjeriti da istorijski binding_kind ostaje TASK, ili da se brisanje odbija).
```

```text
ID: F5
Severity: LOW
Fajl/simbol: src/flowos/service/services/sessions/bindings.py — switch_binding() parametar switched_at
Problem: `switched_at` nije validiran protiv `AgentSession.started_at` (samo
protiv `started_at` postojećeg aktivnog bindinga, kad takav postoji). Teoretski
bi direktan servisni poziv (ne HTTP — HTTP ugovor `SessionTaskBindingSwitchRequest`
uopšte ne izlaže `switched_at` klijentu) mogao kreirati prvi binding sa
`started_at` prije nego što je sesija uopšte započela.
Kako se reprodukuje: Direktan Python poziv
`switch_binding(session_id, task_id=X, switched_at=<vrijeme prije session.started_at>)`
na sesiji bez ijednog postojećeg bindinga.
Zašto je bitno: Nije dostižno preko HTTP API-ja (parametar nije izložen u
Pydantic ugovoru). Samo teorijski rizik za buduće interne pozivaoce.
Preporučena korekcija: nije hitno; napomenuti kao mogući budući edge case.
```

## Provjera po sekcijama naloga

**switch_binding() atomičnost** — vidi F1. Switch NIJE zaista atomičan na nivou
same funkcije (redoslijed close-pa-validate); atomičnost danas postoji samo kao
posljedica ponašanja jedinog HTTP pozivaoca. Partial unique index + service-layer
provjera (`get_active_binding` baca ako nađe >1 aktivan) rade zajedno korektno za
sprečavanje DVA aktivna bindinga (dokazano F3 probom — DB constraint je uvijek
zaustavio duplikat). `switched_at` ne može proizvesti vremenski nelogičan segment
u ODNOSU na postojeći aktivni binding (zaštićeno), ali nije provjeren protiv
`AgentSession.started_at` (F5, low risk). Legacy pointer sync (`_sync_legacy_pointer`)
je pozvan dosledno u istom pozivu kad se novi binding kreira — nije pronađena
grana koja kreira binding a preskače sync. Konkurentni switch-evi: DB nivo
integritet je očuvan (F3), ali error-handling nije (F3, MEDIUM).

**create_session()** — sva četiri ulazna slučaja (samo task_id, samo
plan_item_id, nijedan, oba) provjerena čitanjem i testovima
(test_new_session_with_task_gets_initial_binding,
test_new_session_with_plan_item_gets_initial_binding,
test_new_session_without_task_gets_unassigned_binding,
test_inconsistent_legacy_task_and_plan_item_are_rejected) — sva četiri prolaze i
logika u kodu odgovara testovima. Cross-project validacija je urađena PRIJE
kreiranja AgentSession reda (linije 56-77), tako da nema realnog puta gdje bi
`create_session` ostavio AgentSession bez ispravnog početnog bindinga usljed
parcijalnog commita — sve validacije koje `switch_binding` interno ponavlja već
su prošle ranije u istoj funkciji sa istim vrijednostima, pa je taj poziv u praksi
uvijek uspješan. HTTP create-session ugovor (`SessionCreateRequest`) je
nepromijenjen — kompatibilnost očuvana.

**Završetak sesije** — `end_session()` i `SessionCompletionService.complete_session()`
oba zovu `close_active_binding()` sa istim `now`/`session.ended_at` vrijednostima
koje upisuju u `AgentSession.ended_at` (verifikovano u kodu i testom
test_session_end_closes_active_binding). `close_active_binding()` je idempotentan
(vraća `None` bez greške ako nema aktivnog bindinga), pa poziv iz oba toka (ili
poziv na sesiji bez bindinga — legacy slučaj) ne baca grešku i ne duplira
zatvaranje. Nema testa koji to eksplicitno dokazuje za legacy sesiju bez
bindinga (F4), ali čitanje koda pokazuje da je bezbjedno.

**Alembic migracija** — CHECK constraints (single-target, time-order,
binding_source whitelist), FK-ovi, indeksi i partial unique index odgovaraju
onome što je opisano u izvještaju i modelu. `upgrade`/`downgrade` su simetrični
(downgrade briše indekse pa tabelu, ispravnim redoslijedom). `python scripts/verify.py`
korak 6/7 (migrations check) i 7/7 (Alembic round-trip) su PROŠLI. Migracija ne
dira postojeće `agent_sessions` redove niti radi backfill — potvrđeno čitanjem.
Glavni nalaz iz ove sekcije je F2 (ON DELETE SET NULL).

**Autoritet podataka** — Nije pronađeno mjesto u kodu koje bi legacy
`AgentSession.task_id`/`plan_item_id` tretiralo kao IZVOR ISTORIJE (npr.
rekonstrukciju prošlih task-konteksta). `SessionCompletionService` čita
`session.task_id`/`session.plan_item_id` samo da odredi TRENUTNO stanje na kraju
sesije (za draft report i auto-tranziciju plan itema) — to je u skladu sa
namjenom "compatibility pointer = trenutno stanje", ne istorija. Nije nađena
kontradiktorna upotreba.

## Šta NIJE provjereno / ograničenja ovog review-a

- Stvarna višenitna/višeprocesna trka (thread-level race) nije reprodukovana —
  probe F3 ručno interleave-uje dvije SQLAlchemy sesije u istom procesu da
  simulira trku; ovo je validna simulacija istog efekta koji bi dvije stvarne
  paralelne HTTP konekcije proizvele, ali nije test sa stvarnim thread-ovima/
  procesima protiv pravog FastAPI servera.
- GitNexus MCP alati nisu korišteni u ovom review-u (fokus je bio direktno
  čitanje koda, testova i probe-based dokaz; GitNexus impact/detect_changes
  analiza je već dokumentovana u implementacijskom izvještaju i nije ponovo
  izvršena ovdje jer review ne mijenja kod).
- Nezavisna provjera performansi (npr. brzina switch-a pod opterećenjem) nije
  rađena — van scope-a review-a.

## Odbačene opcije

Nema — ovaj review nije predlagao alternativna rješenja van onoga što je
zapisano kao "Preporučena korekcija" u svakom nalazu.

## Konflikti / kontradiktorni izvori

Nema. Implementacijski izvještaj je unutar sebe konzistentan; nesklad je između
tvrdnji izvještaja ("flushuje kao jedna transakcija", "nova autoritativna
istorija") i stvarnog ponašanja koda dokazanog probama (F1, F2).

## Commitovi

Nema. Ovaj review nije napravio commit niti izmijenio bilo koji fajl osim ovog
izvještaja.

## Rizici i ograničenja

- F1 i F2 su HIGH ali trenutno NE korumpiraju podatke kroz JEDINE postojeće
  ulazne tačke (F1 je maskiran HTTP rollback-om; F2 JESTE trenutno dostižan i
  aktivno mijenja značenje istorije kad se task obriše).
- F3 je MEDIUM — integritet baze je očuvan, ali API vraća pogrešan status kod
  pod trkom.
- Nijedan nalaz ne krši eksplicitno navedene acceptance kriterije iz
  implementacijskog izvještaja doslovno (kriteriji ne pominju ponašanje pri
  brisanju Task/PlanItem niti ponašanje pri neuspjeloj validaciji usred switcha),
  ali krše duh "autoritativna istorija" i "atomičan switch" tvrdnji.

## Potreban follow-up

- Odluka korisnika: da li F1 i F2 popraviti prije prihvatanja faze 1, ili
  prihvatiti fazu 1 uz eksplicitno zabilježen rizik i follow-up zadatak.
- Ako se popravlja: F1 je izmjena redoslijeda dvije linije koda; F2 zahtijeva
  arhitektonsku odluku (RESTRICT vs. snapshot polje vs. prihvatanje rizika) — to
  je odluka za korisnika, ne nešto što agent treba sam odabrati.
- F3 i F4 mogu ići kao manji follow-up zadatak bez blokiranja.

## Potrebna korisnička potvrda

Korisnik treba odlučiti da li se F1/F2 popravljaju prije commita ove faze, ili
se faza prihvata sa zabilježenim rizikom i follow-up zadatkom. Ovaj review ne
donosi tu odluku.

## Status

REVIEW ZAVRŠEN — ČEKA SE KORISNIČKA ODLUKA

---

# Završni verdikt

```text
CHANGES REQUIRED
```

Top 5 razloga:

1. **F2 (HIGH, stvarno dostižan danas)** — `DELETE /tasks/{id}` (postojeći,
   nepovezan endpoint) preko `ON DELETE SET NULL` tiho pretvara zatvoren
   istorijski TASK binding u nešto bit-za-bit identično UNASSIGNED bindingu, bez
   ikakvog traga. Ovo direktno krši ideju "autoritativna istorija" na kojoj cijela
   faza počiva, dokazano probom, i nije bilo pomenuto u izvještaju kao poznat
   rizik.
2. **F1 (HIGH, arhitektonski defekt)** — `switch_binding()` zatvara stari
   binding PRIJE validacije novog targeta, pa funkcija nije zaista atomična kako
   izvještaj tvrdi; sigurna je danas samo zahvaljujući ponašanju jedinog HTTP
   pozivaoca, što je krhka garancija za budući kod, a ispravka je trivijalna
   (zamjena redoslijeda dvije operacije).
3. **F2 nema test koji bi ga uhvatio** — test suite ne testira brisanje
   Task/PlanItem nakon što istorijski binding postoji, iako je to jedan od
   scenarija koje je nalog za review eksplicitno tražio da se provjeri.
4. **F3 (MEDIUM)** — konkurentni switch-evi dovode do neuhvaćenog
   `IntegrityError` (500 umjesto 409) iako je sam podatkovni integritet očuvan
   partial unique indexom — pokazuje da error-handling sloj nije testiran pod
   trkom.
5. Oba HIGH nalaza imaju jeftine, uske popravke (par linija koda za F1;
   arhitektonska odluka + eventualno migraciona izmjena za F2) — ne zahtijevaju
   redizajn, pa CHANGES REQUIRED ne znači veliki rewrite, samo da se ne
   commituje "kao gotovo" bez ove dvije ispravke ili eksplicitne, informisane
   korisničke odluke da se rizik prihvata.

```bash
git status --short
```
