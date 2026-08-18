---
flowos_report_version: 1
report_id: 41643e1d-d476-4916-aeb8-c2bc07bffe43
agent: claude
model: claude-sonnet-5
session_id: unknown
report_type: review
work_status: completed
tasks:
  - FLOW-1108
commits: []
created_at: 2026-08-18T15:09:13Z
---

# FLOW-1108 — Zaštita lokalnih FlowOS podataka
## Final Security Re-review nakon REV-1108-H1 + REV-1108-M1

Nezavisan finalni adversarial review. Nije implementirana, mijenjana niti commitovana nijedna izmjena koda. Baseline: `d059ffc8ed4c9e0367776ee1f50a24bf1850b95a` (main, GitHub). FLOW-1108 ostaje lokalni uncommitted diff.

---

## SCOPE REVIEWED

`git diff --stat` protiv baseline-a identičan je prethodnom focused re-review-u (2026-08-18-FLOW-1108-focused-security-rereview.md): `pyproject.toml`, `app_paths.py`, `logging.py`, `persistence/engine.py`, `persistence/schema_repair.py`, `runtime.py` (svi tracked, isti diff-stat brojevi kao prije), plus untracked `dir_security.py` i `tests/unit/test_dir_security.py`.

Eksplicitno provjereno `git diff` na `runtime.py` i `schema_repair.py` — **bajt-identičan** prethodnom review-u; M1 fix nije dirao wiring, samo `dir_security.py` interno. Nema unrelated production code change.

`docs/*.pptx`, `docs/.~lock...`, `docs/FlowOS_unapredjenja...md` ostaju van scope-a.

---

## REV-1108-H1: CLOSED

`/C` (continue-on-error) je potpuno uklonjen iz oba icacls poziva u `_apply_windows_acl()` (`dir_security.py:145-163`). Regex-based tekstualni parser (`_FAILED_PROCESSING_RE`) je u potpunosti obrisan iz koda — `_run_icacls()` sada provjerava isključivo `result.returncode != 0`.

## REV-1108-M1: CLOSED

Provjereno direktno u kodu — nema NIJEDNOG mjesta gdje `result.stdout`/`result.stderr` sadržaj utiče na fail/success odluku. Tekst se koristi isključivo u poruci izuzetka (dijagnostika), ne u kontrolnom toku.

`tests/unit/test_dir_security.py::TestLocaleIndependentFailClosed` eksplicitno dokazuje ovo sa NE-mock testovima:
- `returncode=0` + nepoznat njemački tekst ("Erfolgreich verarbeitet...") → uspjeh
- `returncode=5` + ćirilični srpski tekst ("Успјешно обрађено...", "Приступ је одбијен") → `DirectoryHardeningError`

`TestRuntimeWiring::test_descriptor_not_written_on_icacls_nonzero_failure` i `TestBackupDirectoryWiring::test_schema_backup_not_written_on_icacls_nonzero_failure` koriste identičan obrazac (ćirilični tekst, `returncode=5`) na nivou stvarnih pozivalaca (RuntimeManager, schema_repair) — ne samo `_run_icacls()` izolovano.

---

## LOCALE-INDEPENDENT FAILURE HANDLING: PASS

Kod ne sadrži nijedan regex, substring provjeru ili bilo kakvu zavisnost od `result.stdout`/`result.stderr` sadržaja za sigurnosnu odluku. Jedini signal je `subprocess.CompletedProcess.returncode`. Ovo je direktno pročitano u `_run_icacls()` (linije 89-100) — nema uslovne grane koja ispituje tekst.

---

## ROOT FAILURE PROBE: PASS

Stvaran (ne mock) icacls poziv, BEZ `/C`, protiv nepostojeće putanje, kroz STVARNU `_apply_windows_acl()` funkciju (ne izolovan `_run_icacls()`):

```
dir_security._apply_windows_acl(Path("C:/definitely/does/not/exist/xyz123final"))
→ DirectoryHardeningError: icacls hardening nije uspio za
  C:\definitely\does\not\exist\xyz123final (exit=3):
  C:\definitely\does\not\exist\xyz123final: The system cannot find the path specified.
```

Dodatno, izolovani probe direktnih icacls poziva (mirror stvarnih `dir_cmd`/`children_cmd` oblika, BEZ `/C`), svi protiv PRAVOG `icacls.exe` na ovoj Windows mašini:

| Slučaj | Komanda (bez `/C`) | returncode | Rezultat |
|---|---|---|---|
| A: nepostojeći single target | `icacls <nonexistent> /inheritance:r /grant:r ...` | **3** | non-zero, kako je očekivano |
| B: validan single target | `icacls <valid-dir> /inheritance:r /grant:r ...` | **0** | uspjeh |
| C: validan `/reset /T /L` (4 fajla, ugniježđeno) | `icacls <dir>\* /reset /T /L` | **0** | uspjeh, sva djeca obrađena |

**A, B, C potvrđeni direktno protiv pravog `icacls.exe`, ne mock-a.**

---

## RECURSIVE CHILD FAILURE PROBE: NOT AVAILABLE

Pokušano nezavisno (drugačija tehnika od implementacionog izvještaja): postavljanje deny ACE preko specijalnog "OWNER RIGHTS" SID-a (`S-1-3-4`, `WD,WO`) na jedan fajl unutar direktorijuma sa dva fajla (jedan "dobar", jedan "loš"), s namjerom da natjera `icacls <dir>\* /reset /T /L` (bez `/C`) da stvarno ne uspije na tom jednom djetetu dok je drugo dijete validno.

Rezultat: `icacls` je i dalje uspio (`returncode=0`, "Successfully processed 2 files; Failed processing 0 files") — deny ACE je efektivno bio prepisan/zaobiđen samim `/reset` pozivom. Windows-ov security model implicitno daje vlasniku WRITE_DAC bez obzira na deny ACE-ove (osim preko OWNER RIGHTS SID-a koji je ovdje pokušan, ali očigledno nije blokirao `/reset` operaciju u ovom kontekstu — moguće zbog naslijeđenih privilegija procesa ili specifičnog ponašanja `/reset` komande).

Konstruisanje genuine per-child ACL failure-a protiv sopstveno-posjedovanih objekata bez elevacije pokazalo se nemogućim u ovom review-u, konzistentno sa implementacionim izvještajem (`D-fail) recursive sa controlled child failure: NOT AVAILABLE`).

**Procjena rezidualne neizvjesnosti (§9 pravilo — ne izmišljati PASS):**

Rezidualna neizvjesnost NIJE materijalna za blokiranje acceptance-a, iz sljedećih razloga:

1. **Dokumentovana Windows semantika**: `icacls /?` eksplicitno opisuje `/C` kao "Continues on file errors (rather than stops on the file error)" — ovo implicira da je DEFAULT (bez `/C`) ponašanje da se OBRADA ZAUSTAVI na prvoj grešci fajla, sa exit kodom koji odražava neuspjeh cijelog poziva.
2. **Direktan dokaz iz scenarija A**: single-target neuspjeh (bez `/C`) pouzdano vraća non-zero (rc=3) — ovo je najjednostavniji slučaj istog "stop-on-error" mehanizma koji bi trebao važiti i za rekurzivni wildcard slučaj.
3. **Strukturalna odbrana u dubinu**: `children_cmd` (wildcard) se izvršava TEK NAKON što je `dir_cmd` (na `path` samom) već uspio. Pošto djeca standardno nasljeđuju dozvole od `path`-a u FlowOS-kreiranim instalacijama, okruženje dovoljno neprijateljsko da blokira ACL operaciju na POJEDINAČNOM djetetu a NE na `path`-u samom je usko, artificijelno stanje (npr. eksterna TOCTOU izmjena između koraka 1 i 2) — ne uobičajena misconfiguracija.
4. **Sopstveni adversarial pokušaj nije uspio**: namjeran, ciljan pokušaj (OWNER RIGHTS SID deny ACE) da se konstruiše baš ovaj scenario nije uspio čak ni protiv stvarnog `icacls`-a — što je negativan, ali informativan dokaz da je takav scenario teško dostižan na standardnom (ne-elevated) Windows nalogu.

Ovo NE ELIMINIŠE teorijsku mogućnost, ali je u skladu sa §9 pravilom zadatka ("Only block acceptance if that uncertainty represents a concrete BLOCKER/HIGH/MEDIUM risk") — ne tretiram ovo kao takav rizik.

---

## RUNTIME TOKEN FAIL-CLOSED: PASS

`RuntimeManager.write_descriptor()` — kod nepromijenjen od prethodnog review-a (bajt-identičan diff). `ensure_private_directory(self.DESCRIPTOR_DIR)` (linija 147) i dalje striktno prije upisa `.tmp`/finalnog descriptora (linije 159-161).

`test_descriptor_not_written_on_icacls_nonzero_failure` (Windows-only) sada testira sa `returncode=5` + ćiriličnim tekstom (ne engleskim "Failed processing") — dokazuje da fail-closed radi NEZAVISNO od jezika poruke. Ni `service.json` ni `.tmp` fajl ne postoje nakon `DirectoryHardeningError`-a.

## BACKUP FAIL-CLOSED: PASS

`create_schema_backup()` — kod nepromijenjen (bajt-identičan diff). `harden_existing_directory(backup_dir)` (linija 384) i dalje striktno prije `sqlite3.connect`/`src.backup(dst)`/WAL/SHM/metadata upisa.

`test_schema_backup_not_written_on_icacls_nonzero_failure` koristi isti ćirilični obrazac — nijedna kopija `flowos.db` ne postoji u `backups/` nakon detektovanog failure-a.

---

## ORIGINAL ACL PROPERTIES: PASS

Svjež, direktan probe protiv `_apply_windows_acl()` (post-M1 kod, ne test mock), na direktorijumu sa pre-postojećim fajlom:

```
RADOVAN\radovan:(OI)(CI)(F)
NT AUTHORITY\SYSTEM:(OI)(CI)(F)
BUILTIN\Administrators:(OI)(CI)(F)

Everyone present: False
BUILTIN\Users present: False
Authenticated Users present: False
existing file still writable: OK  (append test nakon hardening-a)
```

Trenutni korisnik, SYSTEM i Administrators zadržavaju full access; Everyone/Users/Authenticated Users odsutni; pre-postojeći fajl ostaje upisiv nakon hardening-a. Identično prethodno prihvaćenim osobinama.

## JUNCTION SAFETY: PASS

`TestJunctionSafety::test_real_junction_target_unaffected` (stvaran `mklink /J`, ne mock) — PASSED. `/L` flag nedirnut M1 izmjenom (samo `/C` je uklonjen iz oba poziva).

## ROOT CONTAINMENT: PASS

Svjež, direktan probe protiv `_assert_hardenable_path()` (post-M1 kod):

| Putanja | Rezultat |
|---|---|
| `C:\` | REJECTED |
| sibling FlowOS root-a (`FlowOS-evil`) | REJECTED |
| `..\..` traversal | REJECTED |
| `Path.home()` | REJECTED |
| repo root | REJECTED |
| worktree-like sibling naziv | REJECTED |

`_hardenable_roots()`/`_assert_hardenable_path()` tekstualno nepromijenjeni od prethodnog review-a — potvrđeno čitanjem punog fajla.

---

## REGRESIJA OD UKLANJANJA `/C` (§6)

- ACL principal-i: nepromijenjeni (iste SID konstante, isti `grant_specs`/`remove_specs`).
- Inheritance model: nepromijenjen (`(OI)(CI)` flagovi identični).
- `/reset /T /L` ponašanje na uspješnim stablima: nepromijenjeno — potvrđeno probom C (4 fajla, uspjeh).
- Root hardening idempotentnost: `TestRealWindowsAclProbe::test_real_hardening_is_idempotent` — PASSED.
- Postojeća instalacija (pre-populated direktorijum): `TestExistingDirectoryHardened` — svi PASSED, uključujući `test_existing_files_remain_openable_after_hardening`.
- Nema novog traversal/performance-značajnog koda dodano — jedina izmjena je uklanjanje jednog flag stringa iz dvije liste argumenata.

Nema regresije.

---

## TARGETED TESTS

```
python -m pytest tests/unit/test_dir_security.py -v --tb=short
```
**31 passed** (0 failed, 0 skipped).

## FLOW-1107 REGRESSION

```
python -m pytest tests/integration/test_service_runtime.py tests/gui/test_live_launch.py \
  tests/gui/test_api_client_auth.py tests/integration/test_composition_root.py \
  tests/integration/test_websocket_auth.py -v --tb=short
```
**55 passed** (0 failed, 0 skipped).

## scripts/verify.py

```
1. Ruff format check       [PASS]
2. Ruff lint                [PASS]
3. mypy                     [PASS]
4. Architecture boundaries  [PASS]
5. Unit tests (530 passed)  [PASS]
6. Migrations check         [PASS]
7. Alembic round-trip       [PASS]

Prošlo: 7/7 — VERIFIKACIJA PROŠLA
```

Nijedan test nije mijenjan niti `verify.py` dirana radi prolaska.

---

## FINAL SECURITY QUESTIONS

**A. Zavisi li sigurnosna ispravnost FLOW-1108 od engleskog icacls teksta?**
`NO` — regex/tekstualni parser potpuno uklonjen iz koda; potvrđeno čitanjem `_run_icacls()`.

**B. Zavisi li od BILO KOJEG lokalizovanog icacls teksta?**
`NO` — testovi eksplicitno dokazuju uspjeh/neuspjeh sa nepoznatim njemačkim i ćiriličnim srpskim tekstom, ishod zavisi isključivo od `returncode`.

**C. Da li root hardening fail-closed na stvarno neuspjelom target-u?**
`YES` — direktno dokazano (`_apply_windows_acl()` protiv nepostojeće putanje → `DirectoryHardeningError`, exit=3, pravi icacls).

**D. Da li recursive hardening fail-closed kad child operacija ne uspije?**
`NOT PROVEN` — genuine per-child failure nije bezbjedno reproducibilan (ni u ovom review-u ni u implementacionom). Rezidualna neizvjesnost procijenjena kao ne-materijalna (§9, obrazloženje iznad) na osnovu dokumentovane icacls semantike + scenario A dokaza + neuspješnog sopstvenog adversarial pokušaja.

**E. Može li runtime token biti zapisan nakon detektovanog ACL failure-a?**
`NO` — dokazano kodom (ordering nepromijenjen) i testom sa ćiriličnim tekstom + nonzero exit.

**F. Može li backup sadržaj biti zapisan nakon istog?**
`NO` — dokazano identično.

**G. Može li junction traversal promijeniti eksterni target?**
`NO` — stvaran `mklink /J` test i dalje prolazi, `/L` flag nedirnut.

**H. Može li root-containment slučajno hardenovati repo/worktree/home/system root?**
`NO` — svjež direktan probe protiv post-M1 koda potvrđuje odbijanje svih navedenih.

**I. Da li je uklanjanje `/C` uvelo novi BLOCKER/HIGH/MEDIUM finding?**
`NO` — jedina identifikovana rezidualna neizvjesnost (§D iznad) procijenjena je kao ne-materijalna, ne kao finding.

---

## NEW FINDINGS

**BLOCKER:** nema

**HIGH:** nema

**MEDIUM:** nema (REV-1108-M1 je zatvoren ovim fix-om)

**LOW:** nema novih

## RESIDUAL UNCERTAINTY

Recursive child-failure fail-closed ponašanje (bez `/C`) nije direktno reprodukovano protiv stvarnog icacls-a (ni od strane implementatora ni u ovom review-u, uprkos namjernom adversarial pokušaju). Procijenjeno kao ne-materijalno za acceptance na osnovu: dokumentovane Windows/icacls semantike `/C` flaga, direktnog dokaza scenario A (single-target stop-on-error), i strukturalne odbrane-u-dubinu (dir_cmd na `path` samom mora uspjeti prije nego što se children_cmd uopšte izvrši). Preporuka za budućnost (van scope-a acceptance-a): ako se ikad pojavi praktičan način bezbjedne reprodukcije (npr. u izolovanom test VM sa administrativnim pravima za manipulaciju SACL/owner-rights), dodati kao regresioni test.

---

## FINAL VERDICT

**FLOW-1108 — Zaštita lokalnih FlowOS podataka**
**= ACCEPT**

REV-1108-H1 i REV-1108-M1 su oba stvarno zatvorena — `/C` je potpuno uklonjen, fail-closed logika zavisi isključivo od `subprocess` `returncode`-a, i ovo je direktno dokazano kroz stvarne (ne-mock) probe protiv pravog `icacls.exe` na Windows mašini (nepostojeći target, validan target, validan rekurzivni reset). Runtime token i backup fail-closed lanci su nepromijenjeni od prethodnog prihvaćenog review-a i eksplicitno testirani sa non-English tekstom da se dokaže locale-independence. Originalne ACL zaštite (principal model, root containment, junction) potvrđene nepromijenjenim svježim probama. Nema regresije od uklanjanja `/C`. Svi ciljani i regresioni testovi prolaze, `verify.py` = 7/7.

Jedina rezidualna neizvjesnost (recursive child-failure edge case) je transparentno dokumentovana, procijenjena kao ne-materijalna na osnovu dokumentovane Windows semantike i strukturalne odbrane-u-dubinu, i ne predstavlja BLOCKER/HIGH/MEDIUM nalaz.

---

Do NOT commit. Do NOT push.

## Odstupanja od prompta

NONE
