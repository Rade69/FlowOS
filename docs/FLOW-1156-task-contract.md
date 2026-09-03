---
task_id: FLOW-1156
risk: MEDIUM
implementer: TBD
reviewers: [Claude]
status: "OPEN — task contract napisan prije koda"
created_at: 2026-08-28
depends_on: [FLOW-1157]
blocks: []
coupled_with: [FLOW-1158]
---

# FLOW-1156 — Proširenje architecture guarda na GUI stablo

## 1. Kontekst

Potvrđeno na `34cacdb` (poslije FLOW-1157 mergea):

```text
python scripts/guard_architecture.py   → FAIL, 9 prekršaja, svi u src/flowos/service/services/**
pytest tests/architecture/             → PASS, 7/7
grep _api._post/_nam/_apply_auth_header src/flowos/gui/composition_root.py  → 0 pogodaka
grep subprocess src/flowos/gui/views/                                       → 0 pogodaka
```

Guard trenutno provjerava pet import-based pravila (`scripts/guard_architecture.py:14–29`),
uparenih po prefiksu modula. `flowos.gui.composition_root` ne odgovara
nijednom boundary izvoru pravila — guard ga preskače u petlji. Guard vidi
samo importe, nikad pozive, pa privatna metoda pozvana kroz javni klijent
(`self._api._post(...)`) ostaje nevidljiva po konstrukciji.

**Guard trenutno nije povezan sa `scripts/verify.py`.** Verify korak 4 je
`pytest tests/architecture/`, ne poziva `guard_architecture.py` direktno.
`.github/` ne postoji — nema CI-a, sve provjere su ručne po `KAKO-RADIM.md`
toku. To znači da je guard danas potpuno savjetodavan.

FLOW-1157 je uklonio tri poznata prekršaja iz GUI stabla (`_on_import_plan`,
`_track_agent`, `_on_shutdown_requested` u `composition_root.py`, i
`subprocess.Popen(["explorer", ...])` u `overview_skeleton.py`). Guard to
ne bi uhvatio ni prije ni poslije, jer nema pravilo za taj dio stabla.

## 2. Cilj

Guard prijavljuje sva tri poznata GUI prekršaja kad se pokrene nad starim
kodom (`b83f197`), i nijedan kad se pokrene nad ispravljenim (`34cacdb`).
Ista pravila važe u `tests/architecture/test_boundaries.py`.

**Ovaj task NE uvodi guard kao blokirajući korak u `scripts/verify.py` niti
u bilo koji CI gate.** Razlog: `guard_architecture.py` danas ima devet
pre-postojećih backend prekršaja (`services/*` importuje
`controllers.websocket.events`), praćenih odvojeno kroz FLOW-1158. Ako
FLOW-1156 guard učini blokirajućim prije nego što FLOW-1158 završi, gate
postaje trajno crven iz razloga koji nema veze sa GUI radom — a trajno
crven signal se prestaje gledati (blueprint §17). Wiring u `verify.py` je
zaseban budući task, otvara se tek kad guard prijavljuje nula prekršaja
ukupno.

## 3. Traženo rješenje

### 3.1 Nova pravila u `scripts/guard_architecture.py`

Dodati boundary izvore i zabrane, bez brisanja postojećih pet pravila:

```text
flowos.gui.composition_root
    ✗ pozivi privatnih metoda API klijenta (._post, ._get, ._nam, ._apply_auth_header)
    ✗ subprocess, os.system

flowos.gui.views
    ✗ subprocess, os.system
    (postojeće pravilo — ne importovati flowos.gui.services — ostaje)

flowos.cli
    ✗ (definisati granicu — trenutno nema nijedno pravilo za ovaj paket)
```

Guard trenutno hvata samo importe. Pozivi privatnih metoda (`self._api._post`)
traže AST provjeru poziva atributa čije ime počinje sa `_`, ne samo importa
modula. Implementirati kao dodatnu provjeru pored postojeće import-based
logike — ne zamjenjivati je.

### 3.2 Ista pravila u `tests/architecture/test_boundaries.py`

Fajl trenutno ima dodatno pravilo koje guard nema
(`test_package_imports_are_clean` za `flowos.cli`, `:97`). Uskladiti oba
smjera: guard dobija granicu za `flowos.cli` koju test već ima; test dobija
GUI call-level provjere koje guard dobija u 3.1.

### 3.3 Replay validacija (obavezna, blueprint §17)

Prije prihvatanja, pokrenuti **oba** enforcement puta nad **oba** commita:

```text
                          b83f197 (prije 1157)   34cacdb (poslije 1157)
guard_architecture.py     mora prijaviti 3        smije prijaviti 0
                          GUI prekršaja           GUI prekršaja
pytest architecture/      isto                     isto
```

Devet backend prekršaja (`services/*` → `controllers.websocket.events`)
ostaju prisutna na oba commita — to je poznato stanje, ne regresija ovog
taska. Ne dirati ih, ne allowlistovati ih bez reference na FLOW-1158.

**Zabranjeno:** guard koji „prolazi" jer je GUI prekršaj tiho allowlistovan
umjesto stvarno detektovan. Gaming senzora je ozbiljniji nalaz od
prekršaja koji sakriva.

## 4. Acceptance

```text
[ ] guard_architecture.py nad b83f197 prijavljuje tačno 3 GUI prekršaja
    (_on_import_plan, _track_agent, subprocess u overview_skeleton) + 9
    poznatih backend prekršaja = 12 ukupno
[ ] guard_architecture.py nad 34cacdb prijavljuje tačno 9 prekršaja,
    svi backend, nula GUI
[ ] pytest tests/architecture/ -q → 7 postojećih + novi testovi, svi PASS,
    na oba commita sa istim obrascem (crveno/zeleno)
[ ] scripts/guard_architecture.py NE poziva se iz scripts/verify.py
    (provjeriti da ovaj task to nije tiho dodao)
[ ] nijedan allowlist unos bez FLOW-1158 reference u komentaru
[ ] ruff check . → clean
[ ] mypy src → clean
```

### 4.1 Adversarni dokaz

```text
1. Pokrenuti guard i pytest architecture nad b83f197 — zapisati doslovan izlaz
2. Pokrenuti guard i pytest architecture nad 34cacdb (prije ove izmjene) —
   zapisati doslovan izlaz — MORA biti isti kao gore, guard slijep na GUI
3. Primijeniti izmjenu
4. Ponovo pokrenuti nad 34cacdb + izmjena — GUI prekršaji nula, backend i
   dalje devet
5. Sva četiri izlaza idu u izvještaj doslovno
```

## 5. Allowed / Forbidden paths

**Allowed:**

```text
scripts/guard_architecture.py
tests/architecture/test_boundaries.py
tests/architecture/  (novi testovi po potrebi)
```

**Forbidden:**

```text
scripts/verify.py                — wiring je zaseban budući task
src/flowos/**                    — ovaj task ne mijenja produkcijski kod
src/flowos/service/services/**   — FLOW-1158, ne ovaj task
```

Ako se tokom rada pokaže da je nemoguće napraviti call-level provjeru bez
dodatnih zavisnosti (npr. AST biblioteka van standardne), prijaviti kao
`OUT_OF_SCOPE_FINDING`, ne dodavati zavisnost bez odobrenja.

## 6. Review

**Reviewer: Claude.**

Fokus:

```text
1. Replay dokaz — jesu li sva četiri izlaza iz 4.1 stvarno pokrenuta,
   ne pretpostavljena
2. Da li je guard i dalje slijep za bilo koji od tri GUI obrasca
3. Da li su devet backend prekršaja netaknuti (isti fajlovi, iste linije)
4. Da li scripts/verify.py ostaje nepromijenjen
5. Da li je bilo kakav allowlist unos task-vezan
```

Verdict blok:

```yaml
verdict: PASS|PASS_WITH_NOTES|REJECT
scope: PASS|REJECT
acceptance: PASS|REJECT
architecture: PASS|REJECT
security: PASS|REJECT
blocking_findings:
  - <kod>: <opis>
```

## 7. Koordinacija

```text
grana:      task/FLOW-1156-guard-gui-coverage
baseline:   34cacdb ili noviji main — navesti u izvještaju
zavisnosti: FLOW-1157 (mergovan)
coupled:    FLOW-1158 — ne uvoditi guard kao blokirajući gate dok oba
            taska nisu završena
```

## 8. Izvještaj implementera

```text
agent_reports/<YYYY-MM-DD>-FLOW-1156-<implementer>-guard-gui-coverage.md
```

Sadrži: baseline SHA, sva četiri izlaza iz 4.1 doslovno, potvrdu da su
backend prekršaji netaknuti, svaki `OUT_OF_SCOPE_FINDING`.
