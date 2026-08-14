# FlowOS — sigurnosni hardening plan bez gubitka performansi

## Status dokumenta

- Datum: 2026-08-14
- Vrsta: read-only nezavisna verifikacija `docs/FlowOS-sigurnosni-uvidi-i-preporuke.md` + konkretan predlog implementacije
- Metod: direktno čitanje trenutnog koda (ne oslanjanje na prethodni dokument "na riječ"), gdje je bilo praktično i probe protiv stvarnog ponašanja
- Van scope-a: izmjena koda (ovo je predlog, ne implementacija), penetracioni test, audit zavisnosti

Ovaj dokument ne ponavlja `docs/FlowOS-sigurnosni-uvidi-i-preporuke.md` — dopunjava ga sa: (1) stvarnom verifikacijom onih tačaka koje prethodni pregled nije citirao sa tačnim kodom, i (2) eksplicitnom performance analizom za svaku preporuku, jer je to bio direktan zahtjev.

---

## 1. Šta je nezavisno provjereno u ovoj sesiji

Prethodni dokument je citirao dokaz za neke tačke, a za druge samo tvrdio zaključak. Ovdje su te druge tačke provjerene direktno u kodu, sa tačnim linijama.

### 1.1. Agent environment — potvrđeno, gore nego što je opisano

`src/flowos/service/services/infrastructure/agent_adapters/claude_code.py:128-152`:

```python
def get_environment(self, request: AgentRequest) -> dict[str, str]:
    """Filtrirani environment — bez tajni.
    Zadržava: PATH, HOME, USER, SYSTEMROOT, TEMP, TMP.
    Uklanja: API ključeve, tokene, secrets.
    """
    safe_keys = {"PATH", "HOME", "USER", "USERNAME", "SYSTEMROOT", "TEMP", "TMP", "LANG", "TERM"}
    env = {}
    for key, value in os.environ.items():
        if key in safe_keys or key.startswith("CLAUDE_") or key.startswith("ANTHROPIC_"):
            env[key] = value
    for key, value in request.env.items():
        if key not in self.BLOCKED_OVERRIDES:  # {"PATH", "SYSTEMROOT", "COMSPEC"}
            env[key] = value
    return env
```

Docstring tvrdi "Uklanja: API ključeve, tokene, secrets." Kod radi suprotno —
eksplicitno VRAĆA svaku varijablu koja počinje sa `CLAUDE_` ili `ANTHROPIC_`,
što uključuje `ANTHROPIC_API_KEY` ako je postavljena u environment-u procesa
koji pokreće FlowOS servis. `request.env` prihvata bilo koji ključ osim tri
(`PATH`, `SYSTEMROOT`, `COMSPEC`) — može prepisati `HOME`, `USER`, ili ubaciti
proizvoljnu novu varijablu.

### 1.2. Job Object — potvrđeno, potpuno odsutan

`src/flowos/service/services/infrastructure/agent_adapters/claude_code.py:155-234`.
Sekcijski komentar kaže "Process launcher (koristi Job Object na Windows-u)".
Stvaran kod: `subprocess.Popen(..., creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)`
i `kill_process_tree()` koji radi samo:

```python
handle = kernel32.OpenProcess(1, False, pid)
kernel32.TerminateProcess(handle, 1)
```

Nigdje u fajlu ne postoji `CreateJobObject`, `AssignProcessToJobObject` ni
`TerminateJobObject`. `CREATE_NEW_PROCESS_GROUP` samo omogućava slanje
CTRL_BREAK_EVENT grupi — ne garantuje da se cijelo potomačko stablo gasi.
`capabilities()` ipak vraća `can_cancel=True` bezuslovno. Ako `claude` CLI
sam pokrene podproces, taj podproces preživljava "cancel".

### 1.3. Worktree identitet — potvrđeno, konkretan collision bug

`src/flowos/service/services/worktrees/service.py:389-395`:

```python
def _find_worktree(self, path: str) -> WorktreeInfo | None:
    worktrees = self.list_worktrees()
    for wt in worktrees:
        if wt.path == path or wt.path.startswith(path):
            return wt
    return None
```

Ovo se poziva iz `can_cleanup()` i `get_retention_status()`. Petlja vraća PRVI
worktree koji ili tačno odgovara ili ima traženi `path` kao STRING prefiks.
Ako `list_worktrees()` vrati `.../worktrees/flow-100-extra` prije
`.../worktrees/flow-100`, a pozivalac traži tačno `flow-100`, funkcija vraća
pogrešan (`flow-100-extra`) worktree — jer `"...flow-100-extra".startswith(
"...flow-100")` je `True`. Ovo direktno hrani `can_cleanup`/cleanup odluke.

### 1.4. Path validacija projekta — potvrđeno, minimalna

`src/flowos/shared/contracts/projects.py:24-30`:

```python
@field_validator("repo_path")
def repo_path_valid(cls, v: str) -> str:
    p = Path(v.strip())
    if not p.is_absolute():
        raise ValueError(f"repo_path mora biti apsolutna putanja: {v}")
    return str(p)
```

Jedina provjera je `is_absolute()`. `C:\`, `C:\Windows`, `C:\Users\<ja>` su svi
apsolutni i svi prolaze. Nema provjere postojanja, nema provjere da je Git
repo, nema `resolve()`/kanonizacije, nema odbijanja filesystem root-a ili
sistemskih direktorijuma.

### 1.5. Redakcija tajni — potvrđeno, ne postoji nigdje

```
grep -rln "redact\|Redact" src/flowos/   →  0 rezultata
```

Nijedan fajl u cijelom stablu ne sadrži bilo kakav redaction mehanizam.
`services/verification/service.py` čuva `stdout_summary`/`stderr_summary`
direktno (skraćeno na zadnjih 2000 karaktera, ali NE redigovano).

### 1.6. Verification execution granica — potvrđeno

`src/flowos/service/services/verification/service.py:134-176`: `run_verify()`
prima opcioni `verify_path`; ako je dat, koristi se direktno kao
`[sys.executable, str(verify_file)]` bez provjere da je unutar repoa, bez
symlink/junction provjere, bez allowlist-a registrovanih projekata.

### 1.7. Skriveni network fetch u "read-only" preflight-u — potvrđeno

`src/flowos/service/services/worktrees/service.py:267-272`: `get_diff_to_base()`
— koji se zove iz `prepare_integration()` (zvuči kao read-only priprema) —
radi `self._git(["fetch", "origin", base_branch])` bez korisničke potvrde, i
bez `check-ref-format` provjere `base_branch` bilo gdje u fajlu.

### 1.8. extra_args bez validacije — potvrđeno

`claude_code.py:108-126`, `get_command()`: `cmd.extend(request.extra_args)` —
lista se direktno nastavlja na CLI komandu bez ikakve allowlist/blocklist
provjere pojedinačnih flagova.

**Zaključak verifikacije**: svih 8 provjerenih tačaka iz prethodnog dokumenta
su potvrđene tačnim kodom, ne samo prihvaćene "na riječ". Nijedna nije bila
preuveličana — nekoliko (naročito environment i Job Object) je gore u kodu
nego što bi se zaključilo iz same docstring dokumentacije.

---

## 2. Organizujući princip: sigurnost na granicama, ne u hot path-u

Ovo je odgovor na "maksimalno sigurno bez gubitka performansi" — jedna ideja
koja se provlači kroz sve preporuke ispod:

> **Validacija, kanonizacija i autentikacija se rade JEDNOM, na granici gdje
> podatak/zahtjev ulazi u sistem — nikad ponovljeno u petlji koja se izvršava
> po fajlu, po watcher eventu, po WebSocket poruci ili po Git pollu.**

FlowOS već ima ovaj princip ugrađen na više mjesta (Git polling na ~30s,
watcher debounce 500ms, `PRESERVED_TABLES` provjera samo pri schema repair-u,
ne pri svakom upitu) — hardening treba nastaviti isti obrazac, ne uvesti nov.

Konkretno grananje granica u FlowOS-u:

| Granica | Učestalost | Gdje validacija pripada |
|---|---|---|
| Registracija projekta | rijetko, korisnička akcija | Ovdje: puna path kanonizacija, Git root provjera |
| Agent launch | povremeno, po sesiji | Ovdje: environment allowlist, Job Object setup |
| HTTP/WebSocket handshake | po konekciji | Ovdje: auth token provjera |
| Watcher filesystem event | često, sekunde | NE OVDJE: koristi već kanonizovan project root iz baze |
| Git poll | ~30s | NE OVDJE: koristi već validiran repo path |
| Log/artifact upis | po eventu, ali mali payload | Ovdje: redakcija, ali na već-skraćenom (2000 char) baferu |

Svaka preporuka ispod je eksplicitno mapirana na ovu tabelu.

---

## 3. Konkretne preporuke sa performance analizom

### 3.1. Per-instance bearer token (P0)

**Minimalna izmjena**: pri startup-u generisati `secrets.token_urlsafe(32)`,
upisati u `service.json` pored `pid`/`port` (isti fajl, isti write). FastAPI
dependency provjerava `Authorization: Bearer <token>` na svakoj ruti osim
`/health`. WebSocket provjerava token prije `accept()`.

**Performance trošak**: **zanemarljiv**. Provjera je jedan dict lookup +
`hmac.compare_digest()` (constant-time), mikrosekunde po zahtjevu — manje
vremena nego što JSON serijalizacija odgovora već troši. WebSocket provjera se
dešava JEDNOM po konekciji (handshake), ne po poruci — nema ponavljanog
troška u toku dugotrajne WebSocket sesije.

**Granica**: HTTP/WebSocket handshake (po konekciji, ne po eventu).

### 3.2. Windows ACL na runtime/data/logs/backups (P0)

**Minimalna izmjena**: pri PRVOM kreiranju `%LOCALAPPDATA%\FlowOS\` stabla,
jednokratno postaviti ACL (npr. preko `icacls` subprocess poziva ili
`win32security`) da ograniči na trenutnog korisnika.

**Performance trošak**: **nula u runtime-u**. Ovo je one-time operacija pri
`mkdir`, ne pri svakom file I/O. Windows ACL provjere za sve naredne
read/write operacije obavlja sam OS kernel (isti trošak kao i danas — NTFS
uvijek provjerava ACL, FlowOS trenutno samo ne postavlja restriktivniji od
default nasljeđenog).

**Granica**: kreiranje data direktorijuma (jednom po instalaciji/prvom pokretanju).

### 3.3. Centralna redakcija tajni (P0)

**Minimalna izmjena**: jedan `SecretRedactionFilter` sa malim brojem
precompiled regex-a (bearer token oblik, `sk-...`/`ANTHROPIC_API_KEY=...`
oblik, generic `KEY=`/`TOKEN=` heuristika) — primijeniti SAMO na tačci pisanja
(log handler emit, `stdout_summary`/`stderr_summary` prije čuvanja), ne na
svaki intermediate string kroz kod.

**Performance trošak**: **mali i ograničen po dizajnu**. `stdout_summary`/
`stderr_summary` su već isječeni na zadnjih 2000 karaktera PRIJE nego što bi
redakcija trebalo da se primijeni (postojeći kod to već radi) — regex scan
nad 2KB stringa je sub-milisekundni, i dešava se PO VERIFIKACIJI/SESIJI
(rijetko, ne po HTTP zahtjevu). Log redakcija se dešava po log liniji, ali
log linije su kratke i broj po sekundi je nizak (ovo nije high-throughput
event stream). **Izbjeći**: ne uvoditi punu OWASP-style biblioteku sa
stotinama pattern-a — 5-10 ciljanih regex-a pokriva realan rizik uz
minimalan trošak.

**Granica**: upis na disk / WebSocket emit (izlazna tačka, ne svaka
međukoraka).

### 3.4. Environment allowlist umjesto blocklist-a (P0)

**Minimalna izmjena**: ukloniti `startswith("CLAUDE_")`/`startswith(
"ANTHROPIC_")` passthrough. Ako je API ključ stvarno potreban za launch,
dobaviti ga eksplicitno iz Windows Credential Managera SAMO za taj launch i
ubaciti ga pod tačno poznatim imenom (ne kopirati cijeli `ANTHROPIC_*`
namespace).

**Performance trošak**: **nula, poboljšanje ako išta**. `get_environment()`
se poziva jednom po agent launch-u (rijedak event, ljudska vremenska skala —
sekunde do minuti između launcheva). Iteracija kroz `os.environ` je već
jeftina (par desetina varijabli); allowlist umjesto blocklist-a ne mijenja
red veličine.

**Granica**: agent launch (povremeno, po sesiji).

### 3.5. Stvaran Windows Job Object (P1, prije Managed Executiona)

**Minimalna izmjena**: `CreateJobObject()` + `SetInformationJobObject()` sa
`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` + `AssignProcessToJobObject()` odmah
nakon `Popen()`. `kill_process_tree()` postaje `TerminateJobObject()`.

**Performance trošak**: **zanemarljiv**. Ovo je 3 dodatna Win32 API poziva PRI
LAUNCH-U procesa (koji već radi `CreateProcess` interno kroz `subprocess.
Popen`) — mikrosekunde do niski milisekundi, jednokratno po sesiji. Nema
trajnog "polling" troška — Job Object je pasivna OS struktura, kernel je
održava bez FlowOS koda koji je aktivno provjerava.

**Granica**: agent launch (povremeno).

### 3.6. Tipizirane agent opcije umjesto sirovih `extra_args` (P1)

**Minimalna izmjena**: `AgentRequest.extra_args: list[str]` → eksplicitan,
tipiziran skup opcija po adapteru (npr. `AgentLaunchOptions` dataclass);
adapter prevodi u CLI flagove. Standardni profil odbija permission-bypass
flagove; rizičan profil zahtijeva eksplicitan approval flag.

**Performance trošak**: **nula**. Zamjena liste stringova tipiziranim
poljima ne mijenja red veličine — i dalje par desetina polja provjerenih
jednom po launch-u.

**Granica**: agent launch.

### 3.7. Zaključana verification execution granica (P1)

**Minimalna izmjena**: `verify_path` mora biti `None` (default `<repo>/
scripts/verify.py`) ili unaprijed odobren; provjera `verify_file.resolve().
is_relative_to(Path(repo_path).resolve())` prije izvršenja; zapisati Git
commit SHA i SHA-256 skripte u verification artefakt.

**Performance trošak**: **zanemarljiv**. `Path.resolve()` + `is_relative_to()`
je mikrosekundna operacija; SHA-256 nad jednom malom Python skriptom
(tipično par KB) je sub-milisekundna. Ovo se dešava JEDNOM po verify pokretanju
(sami testovi/lint/mypy traju sekunde do minute — path provjera je zanemarljiv
dio tog vremena).

**Granica**: pokretanje verifikacije (rijetko, po zahtjevu za verifikacijom,
ne po fajlu koji se provjerava).

### 3.8. Centralna path kanonizacija za repo/worktree registraciju (P1)

**Minimalna izmjena**: jedna `canonicalize_and_validate_repo_path()` funkcija
u infrastructure sloju — `Path(v).resolve(strict=True)`, provjera da `.git`
postoji (direktno ili kao worktree gitdir fajl), odbijanje filesystem root-a i
poznatih sistemskih putanja, detekcija junction/reparse point-a.

**Performance trošak**: **nula u hot path-u, po dizajnu**. Ovo se poziva
ISKLJUČIVO pri registraciji projekta (`POST /projects`) — rijedak, korisnički
inicirani event. **Ključno**: watcher i Git poller NE smiju pozivati ovu
funkciju po eventu — treba da koriste VEĆ kanonizovanu, u bazi sačuvanu
`repo_path` vrijednost. Ovo je tačno primjena principa iz Sekcije 2 — ako se
canonicalization greškom ubaci u watcher callback (koji se poziva na svaki
filesystem event, potencijalno desetine puta u sekundi na debounce granici),
to BI mjerljivo usporilo watcher throughput. Mora ostati na granici
registracije.

**Granica**: registracija projekta (rijetko). NE watcher/Git poll petlja.

### 3.9. Tačan worktree identitet (P1)

**Minimalna izmjena**: `wt.path == path` (nakon kanonizacije oba stringa),
ukloniti `.startswith()` granu potpuno. Potvrditi da je target u trenutnom
`git worktree list --porcelain` i unutar FlowOS-managed worktree root-a prije
cleanup-a.

**Performance trošak**: **poboljšanje, ne trošak**. Tačna string jednakost
(`==`) je jeftinija operacija od `.startswith()` (obje su O(n) po dužini
stringa u najgorem slučaju, ali `==` prekida ranije na prvom neslaganju
karaktera u prosjeku). Ako se `_find_worktree` pozove često, moglo bi se čak
zamijeniti dict-om (`{path: WorktreeInfo}`) za O(1) lookup umjesto trenutne
O(n) linearne petlje — ali to je opciona dodatna optimizacija, ne
prerekvizit za sigurnosnu ispravku.

**Granica**: worktree cleanup/status upit (po korisničkoj akciji, ne po
watcher eventu).

### 3.10. Git ref validacija i uklanjanje skrivenog fetch-a (P1)

**Minimalna izmjena**: `git check-ref-format --branch <ref>` provjera PRIJE
upotrebe u bilo kojoj Git komandi; `prepare_integration()`/`get_diff_to_base()`
podrazumijevano koriste samo lokalne refove; "Osvježi sa origin-a" postaje
zaseban, eksplicitno korisnički pokrenut poziv.

**Performance trošak**: **poboljšanje za default slučaj**. Uklanjanje
implicitnog `git fetch origin` iz "prepare integration" toka čini TAJ tok
BRŽIM za uobičajen slučaj (fetch je mrežna operacija, može trajati sekunde;
lokalni diff je milisekunde). `check-ref-format` je jedan brz subprocess poziv
(par milisekundi), pozvan JEDNOM po branch kreiranju/integraciji, ne u petlji.

**Granica**: branch/integracija akcija (po korisničkoj akciji).

### 3.11. Tipizirani API payloadovi + resource limiti (P2)

**Minimalna izmjena**: Pydantic model po mutirajućem endpoint-u (dio već
postoji — `ProjectCreate` itd. — proširiti pokrivenost), max string/list
dužina, HTTP body-size limit, WebSocket message size/client count limit.

**Performance trošak**: **zanemarljiv, FastAPI/Pydantic to već radi**.
Pydantic validacija se dešava jednom po zahtjevu, već je dio postojećeg puta
(FastAPI je uvijek validirao kroz Pydantic za rute koje imaju modele) — dodavanje
max-length constraint-a na postojeće stringove ne dodaje novi validacioni
prolaz, samo pooštrava granice unutar već postojećeg.

**Granica**: HTTP request parsing (po zahtjevu, ali to je već postojeći trošak).

---

## 4. Šta NAMJERNO ne raditi (performance/scope zamke)

Da bi "maksimalno sigurno" ostalo iskreno bez "gubitka performansi", ovo
treba izbjeći:

1. **Ne stavljati path/secret validaciju u watcher callback ili Git poll
   petlju.** Watcher radi na debounce od 500ms i može primiti desetine
   eventa u kratkom vremenu; svaka validacija koja bi se tu ponavljala
   (umjesto da se odradi jednom pri registraciji) direktno degradira
   throughput. Ovo je najvažnija performance zamka u cijelom planu.
2. **Ne uvoditi punu enterprise secret-scanning biblioteku.** Mali, ciljani
   skup regex-a nad već-skraćenim baferima pokriva realan rizik uz
   predvidljiv, nizak trošak. Veliki pattern setovi (stotine regex-a,
   entropy-based detekcija) imaju mjerljiv CPU trošak koji nije opravdan za
   lokalni, single-user alat.
3. **Ne uvoditi distribuirano zaključavanje ili session store za auth
   token.** Jedan token po instanci, čuvan u runtime descriptoru (isti fajl
   koji se već piše), provjeren in-memory — nema potrebe za Redis-om,
   SQLite auth tabelom niti mrežnim pozivom po zahtjevu.
4. **Ne raditi Job Object setup po child procesu unutar agent sesije** (npr.
   ako `claude` CLI sam pokrene puno kratkotrajnih podprocesa) — Job Object
   se veže JEDNOM na root proces sesije; djeca automatski nasljeđuju
   članstvo u Job-u bez dodatnog FlowOS koda po djetetu.
5. **Ne raditi sinhronu SHA-256 nad velikim fajlovima u hot path-u.**
   Verification script hash (3.7) je nad malim skriptama (KB, ne MB) — ako
   se isti princip ikad primijeni na artefakte, treba ostati asinhron/
   pozadinski za velike fajlove, ne blokirati request-response ciklus.
6. **Ne kanonizovati putanju na svakom Git poll-u (~30s ciklus).** Repo
   path se kanonizuje JEDNOM pri registraciji i čuva u bazi; poller čita tu
   već-validiranu vrijednost.

---

## 5. Predložen redoslijed (mapiran na postojeći P0/P1/P2)

Redoslijed iz `docs/FlowOS-sigurnosni-uvidi-i-preporuke.md` (Paketi A-D)
ostaje ispravan i ovaj dokument ga ne mijenja. Dopuna: pošto je FLOW-1103
(LIVE launch) upravo prihvaćen, a Faza 12+ (Task Detail, dogfooding) je
sljedeća na redu prema `docs/FlowOS-plan-faze-11-15-dogfooding-v2.md`,
predlažem da se **Sigurnosni paket A (auth + ACL + redakcija)** uvede kao
FLOW-11xx stavka PRIJE Faze 12 početka, ne kao posebna, nezavisna
inicijativa — isti obrazac numeracije/gate-a koji je već dokazano dobro
funkcionisao za FLOW-1101 do FLOW-1104 u ovoj sesiji. Svaka stavka treba
task contract, impact analizu i independent review prije prihvatanja — isti
proces korišten za sve prethodne FLOW stavke u ovoj sesiji.

Paketi B i C (putanje/worktree/Git, Job Object/Managed Execution) ostaju
gejtovani iza svojih odgovarajućih faza, kako originalni dokument već
predlaže — ne treba ih ubrzavati ispred stvarne potrebe.

## 6. Ograničenja ovog dokumenta

Nezavisno provjereno (direktno čitanje koda, tačne linije citirane): stavke
1, 2 (djelimično — file-read potvrda, ne cross-user test), 3, 4, 5, 6, 7, 8,
9, 10 iz originalnog dokumenta. NE verifikovano u ovoj sesiji: tipizirani
API payload pokrivenost svih endpointa (#11), AgentReport ingestion
symlink-race specifika (#12), supply-chain/signing stanje (#13), backup
manifest sadržaj u detalje (#14). Ovo nije formalna sigurnosna revizija niti
penetracioni test — ostaje read-only pregled koda plus predlog, isto
ograničenje koje ima i originalni dokument.
