---
flowos_report_version: 1
report_id: fa5006e5-80e6-4eb5-9617-61c0b5ff0658
agent: claude
model: claude-sonnet-5
session_id: unknown
report_type: review
work_status: completed
tasks:
  - FLOW-1108
commits: []
created_at: 2026-08-14T17:27:39+02:00
---

# FLOW-1108 — Zaštita lokalnih FlowOS podataka — nezavisni adversarial security review

READ ONLY. Nije mijenjan kod, nisu mijenjani testovi, nije pravljen commit, nije pushovano.
Implementation report NIJE prihvaćen "na riječ" — svaka tvrdnja niže je nezavisno probana
protiv stvarnog koda i stvarnog Windows ACL ponašanja, sa svježe napisanim probe skriptama
(ne samo ponovnim pokretanjem postojećih testova).

## 1. Scope i baseline

```
git rev-parse HEAD → d059ffc8ed4c9e0367776ee1f50a24bf1850b95a
```

Poklapa se sa očekivanim baseline-om. `git diff --name-only` je TAČNO lista iz zadatka —
nema neočekivanih izmjena van navedenog scope-a. Pun diff pregledan liniju-po-liniju za
svih 6 izmijenjenih fajlova (`pyproject.toml`,`app_paths.py`, `logging.py`, `engine.py`,
`schema_repair.py`, `runtime.py`) plus novi `dir_security.py` i `test_dir_security.py`.

## 2. TAČNE Windows ACL komande

Iz `dir_security.py::_apply_windows_acl()` (izvor, ne komentar):

```python
dir_cmd = [
    "icacls", str(path),
    "/inheritance:r", "/grant:r",
    f"*{user_sid}:(OI)(CI)F", f"*{SYSTEM_SID}:(OI)(CI)F", f"*{ADMINISTRATORS_SID}:(OI)(CI)F",
    "/remove:g",
    f"*{EVERYONE_SID}", f"*{USERS_SID}", f"*{AUTHENTICATED_USERS_SID}",
    "/C",
]
children_cmd = [
    "icacls", str(path / "*"),
    "/reset", "/T", "/C", "/L",
]
subprocess.run(cmd, capture_output=True, text=True, timeout=30)  # shell nije naveden → False
```

Potvrđeno: `shell=False` (default, nikad eksplicitno True), path je JEDAN element liste
(dokazano probom sa razmacima u imenu direktorijuma), well-known SID-ovi
(`S-1-5-18`=SYSTEM, `S-1-5-32-544`=Administrators, `S-1-1-0`=Everyone, `S-1-5-32-545`=Users,
`S-1-5-11`=Authenticated Users — svi locale-nezavisni), trenutni korisnik preko
`win32security.GetTokenInformation(..., TokenUser)` (SID, ne lokalizovano ime).

## 3. ROOT DIRECTORY ACL — nezavisna proba

Svježe napisan probe (ne ponovna upotreba implementacionog test fajla) na
`%TEMP%\flow1108_review_*\root-probe`:

```
BEFORE: NT AUTHORITY\SYSTEM:(I)(OI)(CI)(F), BUILTIN\Administrators:(I)(OI)(CI)(F), OWNER RIGHTS:(I)(OI)(CI)(F)
AFTER:  BUILTIN\Administrators:(OI)(CI)(F), NT AUTHORITY\SYSTEM:(OI)(CI)(F), RADOVAN\radovan:(OI)(CI)(F)
```

CRUD test nakon hardeninga: `{'create': True, 'read': True, 'append': True,
'mkdir_child': True, 'delete': True}` — sve operacije trenutnog korisnika rade. Root ACL
je EKSPLICITAN (bez `(I)` inherited flaga), ne oslanja se na nasljeđivanje koje je upravo
uklonjeno.

## 4. EXISTING FILE ACL — nezavisna reprodukcija fiksovanog bug-a

Konstruisano PRIJE hardeninga: `existing.txt` + `nested/nested.txt` sa stvarnim sadržajem.
Nakon `ensure_private_directory(root)`:

```
existing.txt AFTER: BUILTIN\Administrators:(I)(OI)(CI)(F), SYSTEM:(I)(OI)(CI)(F), RADOVAN\radovan:(I)(OI)(CI)(F)
nested/       AFTER: isti principal-i, (I)(OI)(CI)(F)
nested.txt    AFTER: isti principal-i, (I)(OI)(CI)(F)
```

Rezultati (stvaran `open()`, ne samo `icacls` tekst):
`{'read_existing': True, 'append_existing': True, 'read_nested': True,
'append_nested': True, 'new_file_writable': True}`

Novi fajl kreiran NAKON hardeninga (`new-after-hardening.txt`) ispravno nasljeđuje ACL
(`(I)(F)` sa istim principal-ima). **Bug opisan u implementacionom izvještaju (F1108-CRIT)
je nezavisno potvrđen kao POPRAVLJEN** — svježa proba, drugi test scenario od onog u
implementacionom test fajlu, isti pozitivan ishod.

## 5/6. Odsustvo širokih principala

`grep` na "Everyone", "BUILTIN\\Users", "Authenticated Users" u `icacls` izlazu za root,
`existing.txt`, `nested.txt`, i novi fajl nakon hardeninga — **NEMA rezultata ni na jednom
mjestu**. Nema DENY ACE varijante, nema "special ACE" preživljavanja u bilo kojem
posmatranom slučaju.

## 7. `/reset /T /L` semantika — nezavisno potvrđeno

Dvokoračni mehanizam (§4 dir_security.py docstring) empirijski potvrđen:
1. `icacls <path> /inheritance:r /grant:r ...(OI)(CI)F... /remove:g ... /C` — hardenuje
   SAMO `path`, bez `/T`.
2. `icacls <path>\* /reset /T /C /L` — wildcard cilja SAMO djecu (NE `path` sam), resetuje
   ih da naslijede TEK postavljen ACL sa koraka 1.

Zašto DVA koraka umjesto jednog `/T` poziva sa `(OI)(CI)` flagovima direktno na sve objekte
— NEZAVISNO reprodukovano: jedan-koračni pristup (`/inheritance:r /grant:r
...(OI)(CI)F... /T` u JEDNOM pozivu) daje `icacls` exit=0 ALI **prazan, potpuno
nepristupačan ACL na svakom postojećem FAJLU** (dokazano na kontrolisanom temp
direktorijumu — `test.log` postaje `Permission denied` čak i vlasniku). Ovo je isti bug
koji je implementacioni tim otkrio i popravio protiv stvarnog korisničkog
`flowos-service.log` fajla tokom FLOW-1108 rada — nezavisno reprodukovano ovdje i
potvrđeno da POPRAVLJENA verzija (dva koraka) ne pravi tu grešku.

## 8. Junction/reparse point sigurnost

Konstruisan STVARAN junction (`mklink /J`) unutar simuliranog FlowOS root-a, pokazujući na
eksterni direktorijum sa PREPOZNATLJIVIM markerom (`Everyone:(OI)(CI)(R)` eksplicitno
dodat prije hardeninga, plus stvaran sadržaj fajla):

```
BEFORE external_target ACL: Everyone:(OI)(CI)(R), SYSTEM:(I)(OI)(CI)(F), Administrators:(I)(OI)(CI)(F), OWNER RIGHTS
AFTER hardening flowos-root (koji sadrži junction): IDENTIČAN ACL, IDENTIČAN sadržaj fajla
```

`/L` flag potvrđeno sprečava `/T` rekurziju da prati junction u njegov cilj — eksterna
lokacija OSTAJE potpuno netaknuta.

**REAL WINDOWS ACL PROBE (junction dio): PASS.**

## 9/10. Root escape / path normalizacija

Probano protiv `_assert_hardenable_path()` direktno:

| Ulaz | Rezultat |
|---|---|
| repo root (cwd) | REJECTED |
| `Path.home()` (user profile root) | REJECTED |
| `C:\` | REJECTED |
| sibling direktorijum FlowOS root-a | REJECTED |
| parent FlowOS root-a | REJECTED |
| `..`/`..` traversal iz FlowOS root-a | REJECTED |
| relativna putanja | REJECTED |
| FlowOS root sa DRUGAČIJIM CASE-om (lowercase) | ACCEPTED — ali `.resolve()` ga vraća na ISTU stvarnu, kanonski-cased putanju (NTFS je case-insensitive, case-preserving) — nije bypass, ista fizička lokacija |
| FlowOS root sam | ACCEPTED (namjeravano) |
| runtime/data/logs/data-backups djeca | ACCEPTED (namjeravano) |

Case-different test NIJE bezbjednosni propust — Windows filesystem API (`Path.resolve()`)
razrješava case varijante NA ISTI fizički objekat kad roditeljske komponente već postoje
na disku; nema alternativne, van-scope-a lokacije dostupne kroz case manipulaciju.

## 11. Runtime token ordering — potvrđeno čitanjem izvora

```python
def write_descriptor(self, port: int) -> None:
    ensure_private_directory(self.DESCRIPTOR_DIR)   # LINIJA 147 — PRVO
    descriptor = {..., "token": self._token, ...}   # LINIJA 148+ — token dict
    tmp = self.DESCRIPTOR_FILE.with_suffix(".tmp")
    tmp.write_text(...)                               # LINIJA 160 — tmp upis
    tmp.replace(self.DESCRIPTOR_FILE)                 # LINIJA 161 — atomic rename
```

Ako `ensure_private_directory` baci, izvršenje NIKAD ne stigne do `descriptor = {...}`
niti do `.tmp` upisa — ni privremeni ni finalni fajl ne nastaju. Potvrđeno i testom
(`test_descriptor_not_written_if_hardening_fails`, fresh run PASSED).

## 12. Database direktorijum

```
app.py::main() → _run_migrations() [db_path=None] → target_db_path = default_database_path()
              → default_database_path() = get_data_directory() / "flowos.db"  [HARDENOVANO]
              → create_sqlite_engine(target_db_path)  [db_path NIJE None → get_data_directory() se NE zove ponovo,
                                                          ali direktorijum je VEĆ hardenovan od gornjeg poziva]

composition_root.py::create_app() → engine = create_sqlite_engine()  [BEZ argumenata]
                                   → unutar create_sqlite_engine: db_path is None → get_data_directory()  [HARDENOVANO]
```

Nezavisno potvrđeno `grep`-om svih poziva `create_sqlite_engine`/`get_data_directory`/
`default_database_path` u `src/` — OBA produkcijska ulazna puta (`app.py::main()` i
`composition_root.py::create_app()`) završavaju kroz `get_data_directory()`, koji JE
hardenovan. Eksplicitno prosleđen custom `db_path` (test/CLI scenario) ostaje van scope-a,
kako je i namjeravano.

## 13. Log direktorijum

Potvrđeno čitanjem `logging.py` linija 34–75: `ensure_private_directory(log_dir)` (linija
46) izvršava se PRIJE `RotatingFileHandler(log_dir / "flowos-service.log", ...)` (linija
67). Custom `log_dir` (kad bi neko u budućnosti pozvao sa eksplicitnim parametrom) NAMJERNO
ne prolazi kroz ACL hardening — plain `mkdir()` (linija 48).

## 14. Backup direktorijum

Potvrđeno čitanjem `schema_repair.py` linija 372–414: `harden_existing_directory(backup_dir)`
(linija 384) izvršava se ODMAH nakon `backup_dir.mkdir(parents=True, exist_ok=False)`
(linija 380), PRIJE `backup_db = backup_dir / source.name` (linija 385) i PRIJE `try:` bloka
koji stvarno kopira SQLite sadržaj (`sqlite3.connect`/`src.backup(dst)`, linija 388-392). Ako
`harden_existing_directory` baci, DB sadržaj se NIKAD ne kopira u backup direktorijum.

## 15. Existing installation hardening — stvarna startup putanja

Trasirano (ne pretpostavljeno): `RuntimeManager.write_descriptor()` (poziva se JEDNOM po
service startup-u u `app.py::main()`), `get_data_directory()` (poziva se pri SVAKOM
`create_sqlite_engine()`), `setup_logging()` (poziva se JEDNOM u `_make_lifespan` startup-u).
Sve TRI stvarne startup putanje su bezuslovne — izvršavaju se pri SVAKOM pokretanju servisa,
NE samo "ako direktorijum ne postoji". `app_paths.py::ensure_directories()` (neiskorišćena
funkcija) NIJE dio ovog lanca — potvrđeno da implementacija NE zavisi od nje.

## 16. Performance / učestalost poziva

`grep` na pozive `ensure_private_directory`/`harden_existing_directory` u cijelom `src/` —
tačno 4 poziv-mjesta (`runtime.py`, `engine.py`, `logging.py`, `schema_repair.py`), sva
vezana za startup/init granicu (service start, engine creation, logging setup, DDL repair
backup) — NIJEDNO vezano za HTTP request handler, DB upit, watcher event, WebSocket event
handler. Fresh test `test_repeated_requests_do_not_reinvoke_hardening` (ponovljen u ovoj
reviziji) potvrđuje: TAČNO jedan poziv na `TestClient` lifespan startup, ZATIM 5×2 HTTP
zahtjeva BEZ ijednog dodatnog poziva.

**Klasifikacija: NEGLIGIBLE.**

## 17. Non-Windows kompatibilnost — nezavisna simulacija

Probano BLOKIRANJEM `win32api`/`win32security` importa na nivou `builtins.__import__` (
simulira okruženje bez `pywin32` instaliranog):

```
Module import OK without win32api/win32security available
ensure_private_directory on simulated non-Windows: OK, dir exists = True
Expected: _current_user_sid_string() fails without win32api: simulated: win32api not available
```

Potvrđeno: modul se učitava čisto BEZ `pywin32` prisutnog (import je unutar funkcije, ne na
vrhu modula), i `ensure_private_directory()` radi ispravno kad `sys.platform != "win32"`
(nikad ne pokušava pozvati Windows-specifičan kod). Samo DIREKTAN poziv
`_apply_windows_acl()`/`_current_user_sid_string()` MIMO platform provjere bi pao — ali
nijedan stvaran pozivalac to ne radi (oba javna ulaza gate-uju `sys.platform == "win32"`).

## 18. pyproject.toml / mypy izmjena

```diff
     "watchdog.*",
     "pywin32.*",
+    "win32api",
+    "win32security",
     "httpx.*",
```

Potvrđeno TAČNO ova dva reda, u POSTOJEĆOJ `ignore_missing_imports = true` override listi.
Razlog je legitiman: `"pywin32.*"` NE pokriva stvarna imena modula (pywin32 instalira
top-level module kao `win32api`/`win32security`, ne pod `pywin32.*` namespace-om) — ovo je
bio latentan, nikad ranije iskorišten gap u postojećem mypy config-u (pošto `runtime.py`
prije FLOW-1108 koristi `ctypes.windll`, ne pywin32 module). Nema opšteg slabljenja mypy
pravila — samo dva specifična imena modula dobijaju isti tretman koji je već postojao za
"pywin32.*" wildcard.

**Verdikt: ACCEPT.**

## 19. Fail-closed ponašanje — **KRITIČAN NALAZ**

Testirano nezavisno protiv REALNOG `icacls` (ne mock):

| Scenario | Ponašanje |
|---|---|
| SID lookup failure (`_current_user_sid_string` baca) | `DirectoryHardeningError` — ispravno |
| icacls binary nije pronađen (`FileNotFoundError` iz subprocess) | `DirectoryHardeningError` — ispravno |
| Read-only/deny-write PARENT direktorijum (mkdir sam padne) | `PermissionError` propagira nepresretnuta — ispravno |
| **icacls NEUSPJEH na ciljnom objektu SAMOM (nonexistent path ILI postojeći path sa deny-WDAC ACE)** | **NIJE PRESRETNUTO — `harden_existing_directory()`/`ensure_private_directory()` VRAĆA USPJEŠNO, BEZ EXCEPTION-a, dok se ACL nikad ne mijenja** |

**Dokaz (nezavisno reprodukovano dva puta, dva različita trigger-a):**

```
$ icacls C:/definitely/does/not/exist/xyz123 /inheritance:r /grant:r *S-1-5-18:(OI)(CI)F /C
exit: 0
stdout: 'Successfully processed 0 files; Failed processing 1 files'
stderr: 'C:/definitely/does/not/exist/xyz123: The system cannot find the path specified.'
```

```
$ icacls <existing-dir-sa-deny-WDAC-ace> /inheritance:r /grant:r *S-1-5-18:(OI)(CI)F /C
exit: 0
stdout: 'Successfully processed 0 files; Failed processing 1 files'
stderr: '<path>: Access is denied.'
```

**Uzrok:** `/C` (continue-on-error) flag, prisutan u OBA icacls poziva
(`dir_cmd` i `children_cmd`), čini da `icacls.exe` VRATI exit code 0 ČAK I KAD je
100% ciljanih objekata neuspješno obrađeno — greška se prijavljuje SAMO tekstualno
(`stdout`: "Failed processing N files", `stderr`: opis greške), NIKAD kroz exit code.
`dir_security.py::_run_icacls()` provjerava ISKLJUČIVO `result.returncode != 0` — ovaj
tekstualni signal se nikad ne parsira niti provjerava.

**Sigurnosni uticaj:** `ensure_private_directory()`/`harden_existing_directory()` MOGU
tiho "uspjeti" bez da su stvarno primijenili BILO KAKVU ACL izmjenu. Za
`RuntimeManager.write_descriptor()`, to bi značilo da se API bearer token upisuje u
`service.json` NAKON navodno-uspješnog poziva `ensure_private_directory()` koji u
stvarnosti NIJE promijenio ACL uopšte — direktorijum ostaje u KOM GOD stanju je bio prije
(potencijalno stara/šira dozvola), bez ijednog loga, upozorenja ili exception-a koji bi to
otkrio.

**Zašto NIJE trenutno trivijalno iskoristivo kroz postojeće pozive:** svi TRENUTNI
pozivaoci (`write_descriptor`, `get_data_directory`, `setup_logging`,
`create_schema_backup`) ciljaju direktorijum koji upravo SAMI kreiraju (`mkdir()`
neposredno prije ili unutar iste funkcije) ili već postoji i pripada trenutnom procesu —
takav direktorijum standardno NEMA već-postojeću deny-WDAC ACE niti nedostaje. Trigger
zahtijeva NEOBIČNO predstanje (GPO-nametnuta deny ACE, ranija ručna `icacls /deny`
intervencija, AV/EDR softver koji blokira ACL izmjene, ili race na nepostojećem path-u) —
van default/standardnog single-user desktop scenarija koji je primarni threat model.

**Minimalna korekcija (NIJE primijenjena — samo za review, kako je traženo):** u
`_run_icacls()`, uz postojeću `returncode != 0` provjeru, DODATI parsiranje `result.stdout`
za `Failed processing (\d+) files` regex i tretirati bilo koji broj > 0 kao hard failure,
NEZAVISNO od exit code-a. Alternativno: ukloniti `/C` iz `dir_cmd` (single-target poziv gdje
"continue on error" nema realnu korist — ili sve uspije ili ne), zadržati `/C` samo na
`children_cmd` (gdje ima legitimnu svrhu — jedan loš fajl ne treba blokirati hardening
ostatka stabla) ALI dodati tekstualno parsiranje i tamo.

**Klasifikacija: HIGH** (vidi §24 FINDINGS za punu klasifikaciju).

## 20. Real Windows ACL probe — sažetak

```
REAL WINDOWS ACL PROBE: PASS
```

Svježa proba (nova skripta, ne ponovna upotreba implementacionog test fajla) na
`%TEMP%\flow1108_review_*\`:
- BEFORE/AFTER ACL zabilježeni za root i postojeće/nove fajlove (§3, §4 iznad).
- CRUD (create/read/append/mkdir/delete) sve rade za trenutnog korisnika nakon hardeninga.
- ACL postojećeg fajla nakon hardeninga.
- ACL novog fajla kreiranog nakon hardeninga.
- Junction test (§8) — eksterna lokacija netaknuta.

## 21. FLOW-1107 regresija — fresh run

```
python -m pytest tests/gui/test_live_launch.py tests/gui/test_api_client_auth.py \
  tests/integration/test_composition_root.py tests/integration/test_service_runtime.py \
  tests/integration/test_websocket_auth.py -v --tb=short
→ 55 passed, 1 warning in 36.00s
```

## 22. ACL targeted testovi — fresh run i kvalitet

```
python -m pytest tests/unit/test_dir_security.py -v --tb=short
→ 24 passed, 1 warning in 2.02s
```

**Kvalitet testova — miješan, sa identifikovanom slijepom tačkom:**
- Testovi koji koriste `TestRealWindowsAclProbe` i
  `test_existing_files_remain_openable_after_hardening` testiraju STVARAN filesystem/ACL
  (ne mock) — vrijedan, nezavisno reproducibilan dokaz.
- `TestFailClosed::test_icacls_nonzero_exit_raises` testira SAMO da kod ispravno reaguje
  KAD je `subprocess.run` MOCKOVAN da vrati `returncode=3` — ovo NE testira stvaran icacls
  ponašanje sa `/C` flagom (koje, kako je dokazano u §19, vraća `returncode=0` čak i pri
  potpunom neuspjehu). **Ovo je TAČNO slijepa tačka koja je propustila §19 nalaz** — test
  suita bi trebalo da uključi test koji stvarno pokreće `icacls` protiv namjerno
  neuspješnog cilja (npr. deny-WDAC ACE ili nepostojeći path) i provjeri da SE PODIŽE
  `DirectoryHardeningError`, ne samo da kod ispravno reaguje na mock.

## 23. Full verify.py

```
Prošlo: 7/7
[PASS] 1. Ruff format check
[PASS] 2. Ruff lint
[PASS] 3. mypy
[PASS] 4. Architecture boundaries
[PASS] 5. Unit tests
[PASS] 6. Migrations check
[PASS] 7. Alembic round-trip
```

Korišten već-committovan 240s timeout, bez workaround-a.

## 24. FINDINGS

### A. FLOW-1108 acceptance findings

| ID | Severity | Fajl/funkcija | Dokaz | Impact | Minimalna korekcija |
|---|---|---|---|---|---|
| **REV-1108-H1** | **HIGH** | `dir_security.py::_run_icacls()` (i implicitno `_apply_windows_acl`) | `/C` flag na OBA icacls poziva čini `returncode` nepouzdanim signalom neuspjeha — dokazano exit=0 uz "Failed processing 1 files" na (a) nepostojećem path-u, (b) postojećem path-u sa deny-WDAC ACE (§19) | `ensure_private_directory`/`harden_existing_directory` mogu tiho "uspjeti" bez ijedne stvarne ACL izmjene — narušava eksplicitno traženu fail-closed garanciju za runtime token upis i sve ostale zaštićene direktorijume | Parsirati `stdout` za `Failed processing (\d+) files` i tretirati >0 kao hard failure nezavisno od exit code-a; ili ukloniti `/C` sa `dir_cmd` (single-target, nema koristi od continue-on-error) |
| REV-1108-L1 | LOW | `tests/unit/test_dir_security.py::TestFailClosed::test_icacls_nonzero_exit_raises` | Test mockuje `returncode=3` direktno — ne pokriva stvaran `/C`-maskiran scenario | Test suita ima slijepu tačku koja je propustila REV-1108-H1 | Dodati test koji stvarno pokreće icacls protiv namjerno neuspješnog cilja (deny-WDAC ili nepostojeći path) bez mockovanja subprocess-a |

Nema BLOCKER nalaza. Nema MEDIUM nalaza van gore navedenih. **Jedan HIGH nalaz postoji.**

### B. Future-task findings (već identifikovano u implementacionom izvještaju, nezavisno potvrđeno tačnim)

- F1108-L1/B1 (implementacioni izvještaj): dvije paralelne `%LOCALAPPDATA%/FlowOS`
  kalkulacije (`app_paths.py` vs `engine.py`/`logging.py`) — potvrđeno postojećim, van
  scope-a FLOW-1108, korektno dokumentovano.
- Mrtav kod: `app_paths.py::ensure_directories()` i neiskorišćeni getteri — potvrđeno
  tačnim, nema uticaja na stvarnu zaštitu (implementacija ne zavisi od te funkcije).

## 25. IMPORTANT REVIEW QUESTIONS

**A. Može li drugi standardni Windows korisnik čitati `runtime/service.json` nakon hardeninga?**

`NOT PROVEN` (nije doslovno testirano sa drugim OS nalogom — kreiranje drugog Windows
korisničkog naloga je administrativna/sistemska akcija van scope-a read-only reviewa).
**Zaključeno iz ACL semantike (visoka pouzdanost, ne direktan dokaz):** hardenovan ACL
sadrži ISKLJUČIVO trenutni-korisnik-SID + SYSTEM + Administrators, eksplicitno bez
Everyone/Users/Authenticated Users i bez nasljeđivanja — NTFS default-deny za svaki
principal koji nije eksplicitno naveden znači da standardni drugi korisnik (nije
Administrator) NE bi trebalo da ima pristup. Ograničenje: ovo pretpostavlja da hardening
STVARNO uspije (vidi REV-1108-H1 — u rijetkim uslovima može tiho ne uspjeti).

**B. Može li trenutni FlowOS korisnik i dalje čitati/pisati postojeće fajlove nakon hardeninga?**

`YES` — dokazano stvarnim `open()`/read/append na postojeće i ugniježđene fajlove (§4).

**C. Mogu li novi fajlovi naslijediti bezbjedan ACL?**

`YES` — dokazano (§4, fajl kreiran nakon hardeninga ima identičan restriktivan,
inherited ACL).

**D. Može li junction traversal promijeniti ACL van FlowOS-owned root-a?**

`NO` — dokazano (§8, eksterni cilj junction-a ostaje potpuno netaknut, `/L` flag radi).

**E. Mogu li proizvoljne repo/worktree putanje biti proslijeđene u produkcijski hardening?**

`NO` — dokazano (§9, repo root/user profile/C:\ /sibling/parent/traversal svi REJECTED);
NAPOMENA: ovo se odnosi na EKSPLICITNU validaciju u `dir_security.py`. Nezavisno od toga,
REV-1108-H1 znači da AKO bi validacija ikad bila zaobiđena ili proširena u budućnosti, sam
fail-closed mehanizam ne bi bio 100% pouzdan signal.

**F. Može li token stići na disk prije nego što runtime ACL uspije?**

`YES, u rijetkom edge-case-u zbog REV-1108-H1` — normalno `NO` (dokazano redoslijedom u
`write_descriptor()`, §11), ALI ako `ensure_private_directory()` tiho "uspije" bez stvarne
ACL izmjene (REV-1108-H1 trigger uslovi), token SE UPISUJE u direktorijum čiji ACL nikad
nije stvarno promijenjen — bez exception-a koji bi to spriječio. Ovo je upravo suština
HIGH nalaza.

**G. Može li DB/WAL/SHM biti kreiran van zaštićenog produkcijskog data dir-a?**

`ONLY EXPLICIT CUSTOM PATH` — potvrđeno (§12), oba produkcijska ulazna puta idu kroz
`get_data_directory()`.

**H. Može li schema-repair backup sadržaj biti upisan prije hardeninga backup direktorijuma?**

`NO` — dokazano redoslijedom u kodu (§14).

## 26. FINAL VERDICT

```
FLOW-1108 — Zaštita lokalnih FlowOS podataka

WINDOWS ACL MECHANISM:
FIXES REQUIRED (mehanizam je ispravan po NAMJERI i u normalnom slučaju radi tačno kako
                treba — vidi §3,4,5,6,7,8 sve ACCEPT-level dokazano; jedini razlog za
                FIXES REQUIRED je REV-1108-H1 fail-closed gap)

CURRENT USER SID:
ACCEPT

ROOT DIRECTORY ACL:
ACCEPT

EXISTING FILE ACL:
ACCEPT

NEW FILE INHERITANCE:
ACCEPT

BROAD PRINCIPAL REMOVAL:
ACCEPT

JUNCTION SAFETY:
ACCEPT

ROOT CONTAINMENT:
ACCEPT

RUNTIME TOKEN ORDERING:
ACCEPT (kod redoslijed je ispravan; FIXES REQUIRED bi bio konzistentniji sa REV-1108-H1,
        ali sam REDOSLIJED u write_descriptor() je tačan — vidi F odgovor gore za nijansu)

DATABASE DIRECTORY:
ACCEPT

LOG DIRECTORY:
ACCEPT

BACKUP DIRECTORY:
ACCEPT

EXISTING INSTALLATION HARDENING:
ACCEPT

FAIL-CLOSED:
FIXES REQUIRED  (REV-1108-H1 — /C flag maskira icacls neuspjeh, dokazano)

NON-WINDOWS COMPATIBILITY:
ACCEPT

PYPROJECT/MYPY CHANGE:
ACCEPT

FLOW-1107 REGRESSION:
55 passed, 1 warning in 36.00s

ACL TARGETED TESTS:
24 passed, 1 warning in 2.02s

REAL WINDOWS ACL PROBE:
PASS

scripts/verify.py:
7/7

PERFORMANCE IMPACT:
NEGLIGIBLE
```

Postoji jedan HIGH acceptance nalaz (REV-1108-H1).

```
FLOW-1108 — Zaštita lokalnih FlowOS podataka
= FIXES REQUIRED
```

Napomena za korisnika: ovo NIJE arhitektonsko odbacivanje implementacije — dizajn (dvokoračni
`icacls`, SID-bazirana identifikacija, root containment, non-Windows kompatibilnost, redoslijed
upisa) je nezavisno potvrđen ispravnim u SVAKOM testiranom normalnom i adversarial scenariju.
Jedini materijalni nalaz je uzak, ali stvaran gap u fail-closed error-handling-u (`/C` flag
maskira icacls neuspjeh), sa jasnom, malom, lokalizovanom korekcijom (parsiranje stdout teksta
uz postojeću exit-code provjeru). Preporučuje se brz fix-and-reverify prije finalnog ACCEPT-a,
ne redizajn.

Odstupanja od prompta: NONE
