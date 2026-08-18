---
flowos_report_version: 1
report_id: cdacaa66-6ed2-43e1-975d-70418ebdb303
agent: claude
model: claude-sonnet-5
session_id: unknown
report_type: review
work_status: completed
tasks:
  - FLOW-1108
commits: []
created_at: 2026-08-18T14:27:05Z
---

# FLOW-1108 — Zaštita lokalnih FlowOS podataka
## Focused Security Re-review nakon REV-1108-H1 fix-a

Nezavisan adversarial re-review. Nije implementirana, mijenjana niti commitovana nijedna izmjena koda. Baseline: `d059ffc8ed4c9e0367776ee1f50a24bf1850b95a` (main, GitHub). FLOW-1108 ostaje lokalni uncommitted diff.

---

## SCOPE REVIEWED

`git diff --stat` protiv baseline-a potvrđuje da su izmjene ograničene na:

- `pyproject.toml` — dodaje `win32api`/`win32security` u mypy `ignore_missing_imports` listu (nastavak postojećeg `pywin32.*` obrasca; bez sigurnosnog efekta)
- `src/flowos/service/services/infrastructure/app_paths.py` — dodaje `get_flowos_root()` (čist getter, korišten od `dir_security.py`)
- `src/flowos/service/services/infrastructure/logging.py` — wiring: `ensure_private_directory()` na default `log_dir`
- `src/flowos/service/services/infrastructure/persistence/engine.py` — wiring: `ensure_private_directory()` u `get_data_directory()`
- `src/flowos/service/services/infrastructure/persistence/schema_repair.py` — wiring: `harden_existing_directory()` odmah nakon `backup_dir.mkdir(exist_ok=False)`, prije upisa backup sadržaja
- `src/flowos/service/services/infrastructure/runtime.py` — wiring: `ensure_private_directory()` prije upisa runtime descriptora (FLOW-1107 bearer token)
- `src/flowos/service/services/infrastructure/dir_security.py` (novi, untracked) — centralni ACL hardening primitiv, uključujući REV-1108-H1 fix u `_run_icacls()`
- `tests/unit/test_dir_security.py` (novi, untracked) — 31 test

Nema izmjena van ovog scope-a. Provjereno eksplicitno: ACL principal model (SID konstante nepromijenjene), root containment logika (`_hardenable_roots`/`_assert_hardenable_path` — nema diff artefakta jer je fajl untracked, ali direktna proba protiv trenutnog koda — vidi §6 — potvrđuje isto ponašanje kao u prethodnom prihvaćenom review-u od 2026-08-14), junction zaštita (`/L` flag netaknut), DB/log wiring (samo dodaje poziv, ne mijenja postojeću logiku), FLOW-1107 auth/token semantika (netaknuta — `runtime.py` diff dodaje samo `ensure_private_directory()` poziv prije postojećeg upisa, token generation kod nedirnut).

`docs/*.pptx`, `docs/.~lock...`, `docs/FlowOS_unapredjenja...md` su nepovezani untracked artefakti (prezentacije/napomene) — van scope-a, ignorisani.

**Nema unrelated production code change.**

---

## REV-1108-H1: CLOSED

Pregledana stvarna `_run_icacls()` implementacija (`dir_security.py:95-112`):

```python
if result.returncode != 0:
    raise DirectoryHardeningError(...)

failed_match = _FAILED_PROCESSING_RE.search(result.stdout)
if failed_match and int(failed_match.group(1)) > 0:
    raise DirectoryHardeningError(...)
```

Provjereno protiv originalnog §1108-H1 test matrixa (A-D iz zadatka):

| Slučaj | Rezultat |
|---|---|
| A: returncode=0, "Failed processing 1 files" | `DirectoryHardeningError` ✅ |
| B: returncode=0, "Failed processing N files", N>0 | `DirectoryHardeningError` ✅ |
| C: returncode=0, "Failed processing 0 files" | success ✅ |
| D: returncode!=0 | `DirectoryHardeningError` ✅ (provjereno PRIJE regex provjere, redoslijed ispravan) |

Provjera NIJE zavisna od engleskih opisnih poruka tipa "Access is denied" — koristi isključivo numerički signal iz "Failed processing N files" i exit code. Ovo je u skladu sa zahtjevom.

---

## MASKED ICACLS FAILURE: PASS (uz jedan rezidualni MEDIUM nalaz — vidi §5)

### Stvarna (ne-mock) reprodukcija originalnog H1 scenarija

Protiv **pravog** `icacls` binarnog fajla (Windows okruženje, ne mock):

```
$ icacls C:/definitely/does/not/exist/xyz123 /inheritance:r /grant:r *S-1-5-18:(OI)(CI)F /C
stdout: 'Successfully processed 0 files; Failed processing 1 files'
returncode: 0
```

Pozivom `dir_security._run_icacls()` direktno protiv ovog stvarnog komandnog niza:

```
DirectoryHardeningError raised (expected): icacls hardening nije uspio za
C:\definitely\does\not\exist\xyz123: Successfully processed 0 files; Failed processing 1 files
```

**Potvrđeno: fix ispravno hvata originalni H1 masked-failure repro (a) protiv pravog icacls-a, ne samo mockova.**

Scenario (b) iz originalnog nalaza (postojeći path sa deny-WDAC ACE) NIJE ponovo reprodukovan protiv stvarnog icacls-a u ovom re-review-u — pokušaj postavljanja deny-WDAC ACE na sopstveni direktorijum nije proizveo maskiranu grešku jer Windows vlasniku objekta implicitno zadržava WRITE_DAC bez obzira na deny ACE (nije zaobiđeno bez admin/SeRestorePrivilege konteksta koji ovaj re-review namjerno nije koristio da ne ugrozi sistem). Ovo NE umanjuje pouzdanost fix-a — scenario (a) je dovoljan i dovoljno reprezentativan dokaz da je regex/exit-code logika ispravna za realan `/C`-maskiran izlaz.

### Adversarial parser probe — dodatni slučajevi testirani protiv PRAVOG icacls-a

- Prazan direktorijum (bez djece), wildcard `path\*` `/reset /T /C /L`: `Successfully processed 0 files; Failed processing 0 files`, exit=0 → **ispravno tretirano kao uspjeh** (nema lažnog pozitiva).
- Duboko ugniježđena struktura (path length ~268 karaktera, van MAX_PATH): icacls je obradio sve fajlove/foldere ispravno, `Failed processing 0 files` — nema regresije zbog dugih putanja.
- Svi parametrizovani slučajevi iz test suite-a (`Failed processing 1/2/10 files`, sa/bez "Successfully processed N files;" prefiksom) — regex hvata sve.

**Nije pronađen format u kojem stvaran icacls izlaz zaobilazi regex na English-locale Windows-u.**

---

## RUNTIME TOKEN FAIL-CLOSED: PASS

`RuntimeManager.write_descriptor()` (`runtime.py:138-161`):

```python
def write_descriptor(self, port: int) -> None:
    ensure_private_directory(self.DESCRIPTOR_DIR)   # linija 147 — PRIJE
    descriptor = {..., "token": self._token, ...}
    tmp = self.DESCRIPTOR_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(descriptor, indent=2))  # linija 160 — TEK NAKON
    tmp.replace(self.DESCRIPTOR_FILE)
```

`ensure_private_directory()` je fail-closed (baca `DirectoryHardeningError` prije `return`-a ako ACL hardening ne uspije), a poziv je na liniji 147, striktno prije bilo kakvog upisa descriptora (linija 159-161). Nema puta kroz funkciju koji upisuje `.tmp` ili finalni fajl bez prethodnog uspješnog hardening poziva.

Test `test_descriptor_not_written_on_masked_icacls_failure` (Windows-only, real `_current_user_sid_string` monkeypatch + real `subprocess.run` mock koji vraća TAČNO H1 masked-failure stdout: `"Successfully processed 0 files; Failed processing 1 files"`, returncode=0) potvrđuje da ni `service.json` ni `.tmp` fajl ne postoje nakon poziva. Ovo NIJE proizvoljan exception mock — koristi stvaran H1 put kroz `_run_icacls()` regex.

**Potvrđeno kodom (ordering) + testom koji cilja tačan H1 scenario.**

---

## BACKUP FAIL-CLOSED: PASS

`schema_repair.create_schema_backup()` (`schema_repair.py:372-409`):

```python
backup_dir.mkdir(parents=True, exist_ok=False)   # linija 380
harden_existing_directory(backup_dir)             # linija 384 — PRIJE bilo kakvog sadržaja
backup_db = backup_dir / source.name
...
src.backup(dst)                                    # linija 392 — DB backup sadržaj
copied_wal = _copy_if_present(...)                 # linija 397 — WAL
copied_shm = _copy_if_present(...)                 # linija 398 — SHM
(backup_dir / "metadata.json").write_text(...)     # linija 407 — metadata
```

`harden_existing_directory()` je pozvan neposredno nakon `mkdir(exist_ok=False)` i striktno prije `sqlite3.connect(str(backup_db))`/`src.backup(dst)` (DB sadržaj), WAL/SHM kopiranja i metadata upisa. Fail-closed: ako hardening baci, funkcija se prekida prije bilo kakvog sadržaja.

Test `test_schema_backup_not_written_on_masked_icacls_failure` (Windows-only) koristi identičan H1 masked-failure stdout kao runtime test i potvrđuje da `backups/` ne sadrži nijednu kopiju `flowos.db` nakon `DirectoryHardeningError`-a.

**Potvrđeno kodom (ordering) + testom koji cilja tačan H1 scenario.**

---

## ORIGINAL FLOW-1108 SECURITY PROPERTIES: PASS

Direktna proba protiv trenutnog `_assert_hardenable_path()` (živi kod, ne test mock), izvan pytest-a:

| Putanja | Rezultat |
|---|---|
| `C:\` | REJECTED |
| sibling direktorijum FlowOS root-a (`...\FlowOS-evil`) | REJECTED |
| `..\..` traversal iz FlowOS root-a | REJECTED |
| `Path.home()` (user profile root) | REJECTED |
| repo root (`C:\Users\38765\Desktop\FolowOS`) | REJECTED |

Sibling-direktorijum odbijanje NIJE string-prefix provjera (koja bi bila ranjiva na `FlowOS-evil` "startswith FlowOS" laž) — implementacija koristi `Path.resolve()` + `root in resolved.parents` (strukturnu roditelj-provjeru), što ispravno odbija svaki sibling naziv koji dijeli prefiks ali nije stvarni poddirektorijum.

Junction zaštita: `TestJunctionSafety::test_real_junction_target_unaffected` radi STVARAN `mklink /J` i upoređuje `icacls` izlaz cilja prije/poslije hardening-a roditelja — identičan, dakle `/L` flag stvarno sprečava propagaciju.

Principal model (SYSTEM/Administrators/current-user full access; Everyone/Users/Authenticated Users uklonjeni) potvrđen kroz `TestRealWindowsAclProbe` (stvaran icacls poziv protiv temp direktorijuma, ne mock) — PASSED.

Non-Windows ponašanje: `TestNonWindowsBehaviorPreserved` potvrđuje da se `_apply_windows_acl` NE poziva kad `sys.platform != "win32"` — samo `mkdir`.

---

## REAL WINDOWS PROBE: PASS

Izvršeno na stvarnom Windows razvojnom okruženju (ne CI/mock):

1. Prazan direktorijum + wildcard reset → `Failed processing 0 files`, exit=0 → ispravan uspjeh.
2. Direktan H1 repro (nepostojeća putanja) protiv `_run_icacls()` → `DirectoryHardeningError` — potvrđeno.
3. Duboko ugniježđena struktura (>MAX_PATH) → bez lažnog neuspjeha.
4. Root containment probe (§6 iznad) protiv živog `_assert_hardenable_path()`.

Sve probe su rađene isključivo u `%TEMP%` privremenim direktorijumima (kreiranim i obrisanim u ovom review-u); repo, worktree, user profile ACL i sistemski direktorijumi nisu dirani.

---

## NEW FINDING — REV-1108-M1 (MEDIUM)

**Lokacija:** `dir_security.py:37` — `_FAILED_PROCESSING_RE = re.compile(r"Failed processing (\d+) files")`

**Nalaz:** `icacls.exe` na Windows-u učitava svoje poruke iz jezički-specifičnih MUI resource fajlova (`icacls.exe.mui`) — potvrđeno postojanje tog fajla na test mašini (`C:\Windows\System32\en-US\icacls.exe.mui`, aktivan `Get-UICulture` = en-US). Regex koji REV-1108-H1 fix koristi za detekciju maskiranog neuspjeha je hardkodovan na **engleski** tekst "Failed processing N files". Na Windows instalaciji sa drugačijim UI display jezikom (npr. njemački, francuski, ili — s obzirom da je cijeli FlowOS projekat dokumentovan na srpskom/bosanskom, ne nezamislivo — regionalni jezik), `icacls` bi prijavio identičnu semantiku (returncode=0, N fajlova neuspješno) ali TEKSTUALNO drugačijom porukom, koju ovaj regex NE bi uhvatio. Rezultat: `ensure_private_directory()`/`harden_existing_directory()` bi "tiho uspjeli" u TAČNO istom scenariju koji je REV-1108-H1 trebao zatvoriti — runtime token ili backup sadržaj bi mogli biti upisani u direktorijum čiji ACL nikad nije stvarno ograničen.

**Dokaz vs. ograničenje dokaza:** Mehanizam (MUI lokalizacija icacls poruka) je direktno potvrđen na ovoj mašini (postojanje `icacls.exe.mui`, aktivna en-US UI kultura). Stvaran non-English icacls izlaz NIJE reprodukovan (ovo razvojno okruženje nema instaliran drugi jezički paket) — ovo je PROVEN mehanizam sa DOKAZANOM pretpostavkom (locale-dependent resource loading), ali NE direktno reprodukovan bypass string. Ne izmišljam hipotetički format teksta — rizik je u samom mehanizmu učitavanja poruka, ne u nagađanju konkretnog stranog stringa.

**Uticaj:** Ne utiče na `returncode != 0` granu (i dalje hvata sve failure-e nezavisno od jezika). Utiče isključivo na `/C`-maskiran (`returncode=0` + tekstualni failure) slučaj — što je upravo scenario koji je REV-1108-H1 trebao zatvoriti.

**Preporuka (za budući fix, van scope-a ovog review-a):** Dodati jezički-nezavisan sekundarni signal, npr. tretirati bilo koji ne-prazan `result.stderr` uz `returncode == 0` kao dodatni hard-failure trig (originalni H1 repro je imao `stderr: opis greške` u oba dokumentovana slučaja), ili ukloniti `/C` sa `dir_cmd` (single-target poziv gdje continue-on-error nema stvarnu korist — sugerisano već u originalnom H1 nalazu kao alternativa) i zadržati `/C` samo na `children_cmd` gdje je regex jedini praktičan signal.

---

## TARGETED TESTS

```
python -m pytest tests/unit/test_dir_security.py -v --tb=short
```
**31 passed** (0 failed, 0 skipped na ovoj Windows mašini).

## FLOW-1107 REGRESSION

```
python -m pytest tests/integration/test_service_runtime.py tests/gui/test_live_launch.py \
  tests/gui/test_api_client_auth.py tests/integration/test_composition_root.py \
  tests/integration/test_websocket_auth.py -v --tb=short
```
**55 passed** (0 failed, 0 skipped).

## scripts/verify.py

```
1. Ruff format check   [PASS]
2. Ruff lint            [PASS]
3. mypy                 [PASS]
4. Architecture boundaries [PASS]
5. Unit tests (530 passed) [PASS]
6. Migrations check     [PASS]
7. Alembic round-trip    [PASS]

Prošlo: 7/7 — VERIFIKACIJA PROŠLA
```

---

## SECURITY QUESTIONS

**A. Može li `/C` i dalje vratiti exit=0 sa processing failure-om koji FlowOS tretira kao success?**
`NOT PROVEN` (uslovno) — `NO` na English-locale Windows instalaciji (direktno reprodukovano i dokazano protiv pravog icacls-a, §3). `NOT PROVEN` na non-English-locale Windows instalaciji zbog REV-1108-M1 (mehanizam dokazan, konkretan string nije reprodukovan zbog nedostupnosti drugog jezičkog paketa na test mašini).

**B. Može li runtime token biti zapisan nakon REV-1108-H1 masked ACL failure-a?**
`NO` na English-locale Windows-u — dokazano ordering-om koda (§4) i testom koji cilja tačan H1 stdout. Isti locale caveat kao pod A za non-English instalacije (REV-1108-M1).

**C. Može li backup sadržaj biti zapisan nakon istog failure-a?**
`NO` na English-locale Windows-u — dokazano ordering-om koda (§5) i testom koji cilja tačan H1 stdout. Isti locale caveat kao pod A.

**D. Jesu li postojeće ACL semantike ostale netaknute?**
`YES` — principal model, root containment, junction zaštita, non-Windows ponašanje svi potvrđeni nepromijenjenim (§6, stvarni Windows testovi i direktna proba).

**E. Može li junction traversal promijeniti ACL external targeta?**
`NO` — `test_real_junction_target_unaffected` (stvaran `mklink /J`, ACL cilja identičan prije/poslije) potvrđuje.

**F. Može li root-containment zaštita zahvatiti repo/worktree/home?**
`NO` — direktno provjereno protiv živog koda: `C:\`, sibling FlowOS dir, `..\..` traversal, `Path.home()`, repo root — svi REJECTED.

**G. Postoji li novi BLOCKER/HIGH/MEDIUM finding uveden fixom?**
`YES` — REV-1108-M1 (MEDIUM): masked-failure regex je locale-dependent; mehanizam dokazan (MUI resource loading), konkretan non-English bypass string nije direktno reprodukovan na ovoj mašini.

---

## NEW FINDINGS

**BLOCKER:** nema

**HIGH:** nema

**MEDIUM:**
- REV-1108-M1 — `_FAILED_PROCESSING_RE` je hardkodovan na engleski tekst; na Windows instalaciji sa drugačijim UI display jezikom, isti `/C`-maskiran scenario koji je REV-1108-H1 trebao zatvoriti bi ponovo tiho prošao kao "uspjeh". Vidi detaljan opis iznad.

**LOW:** nema novih (REV-1108-L1 iz originalnog review-a — test suite je dopunjen realnim H1-repro testovima, tretiram kao zatvoren)

---

## FINAL VERDICT

**FLOW-1108 — Zaštita lokalnih FlowOS podataka**
**= FIXES REQUIRED**

REV-1108-H1 je stvarno i dokazano zatvoren za English-locale Windows instalacije — ovo je bio jedini prethodni HIGH nalaz i popravka je solidna, testirana protiv pravog `icacls`-a (ne samo mockova), sa ispravnim redoslijedom hardening→upis za oba osjetljiva puta (runtime token, schema backup). Originalne ACL zaštite (principal model, root containment, junction, non-Windows) nisu regresirane — sve direktno provjereno. `verify.py` = 7/7, targeted i regression testovi 100% prolaze.

Jedini razlog za FIXES REQUIRED je REV-1108-M1: rezidualni, uzak ali stvaran gap u istom fail-closed garancijom koju je H1 trebao potpuno zatvoriti, ograničen na non-English-locale Windows instalacije. S obzirom da je čitav FlowOS projekat dokumentovan i komuniciran na srpskom/bosanskom, non-English Windows UI jezik na ciljnoj mašini nije zanemarljiv scenario. Preporučena korekcija je mala i lokalizovana (dodati jezički-nezavisan `stderr`-based signal ili ukloniti `/C` sa `dir_cmd`) — ne zahtijeva veći rework.

---

Do NOT commit. Do NOT push.

## Odstupanja od prompta

NONE
