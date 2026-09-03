# Agentski radni tok — Blueprint za postavljanje novog projekta

**Status:** generički, portabilan template — izveden iz stvarne prakse na
Dentaland projektu (REF-00..14, DENT-IMPROVE-001..010 paketi), ali NE
sadrži nikakve Dentaland-specifične reference (domena, stack, šema baze).
Namijenjen kopiranju u korijen bilo kojeg novog projekta koji koristi
više agenata (Claude/Codex/Pi/Crush ili slično) za razvoj.

**Kako se koristi:** ovo NIJE dokumentacija koja se čita jednom — ovo je
referenca koju agent čita PRIJE početka rada na bilo kom tasku, i na koju
se vraća kad nije siguran kako da postupi. Sekcija 18 na kraju objašnjava
tačno kako se ovaj fajl adaptira za konkretan novi projekat.

Svaka praksa niže je ovdje zato što je **dokazano** riješila stvaran
problem koji se desio, ne zato što "zvuči dobro". Gdje je relevantno,
naznačeno je koji je problem praksa riješila — to je razlog da se praksa
ne izbaci "radi jednostavnosti" bez razumijevanja šta se time gubi.

---

## 1. Uloge i odgovornosti

| Uloga | Odgovornost |
|---|---|
| **Human owner** | Jedini izvor odobrenja za merge. Dodjeljuje implementere/reviewere po tasku. Odlučuje o obimu/prioritetu. Odobrenje se NIKAD ne pretpostavlja — čak i nakon što je jednom odobrio sličnu akciju, svaki merge traži svoj eksplicitan "odobravam". |
| **Koordinator** (obično najsposobniji/najduže-kontekstualni agent u sesiji) | Piše Task Contracts prije koda, priprema konkretne (ne generičke) promptove za implementere, radi nezavisnu verifikaciju, često je i jedan od reviewera, merguje, pokreće post-merge gate, održava state dokumente. |
| **Implementer** | Piše kod strogo unutar `allowed_paths` iz Task Contracta. NE commituje/pušuje sam bez eksplicitnog zahtjeva. Odstupanja od kontrakta prijavljuje kao `OUT_OF_SCOPE_FINDING`, ne popravlja ih tiho niti širi scope. |
| **Reviewer 1, Reviewer 2, ...** | Nezavisni od implementera ZA TAJ TASK — nikad ista sesija/agent koja je i implementirala. Različiti reviewer-i mogu imati različit fokus (npr. test-kvalitet/adversarno vs arhitektura) — to je namjerno, ne duplirati isti posao. |

**Nepregovarano pravilo:** Implementer nikad nije isti agent/sesija kao
Reviewer za taj isti task. Ako se to desi (npr. reviewer je usput
implementirao fix), taj reviewer je "kontaminiran" za taj task — vidi
sekciju 11 (Eskalacija).

---

## 2. Risk tier definicije

| Tier | Kriterijum | Proces |
|---|---|---|
| `LOW` | Nema promjene ponašanja vidljive korisniku, izolovan fajl/modul, lako reverzibilno | Implementer → 1 reviewer → merge |
| `MEDIUM` | Vidljiva promjena ponašanja, ili dira dijeljenu klasu/modul koji koristi više potrošača | Implementer → targeted+adversarni testovi → 1 reviewer → human approval → merge |
| `HIGH` | Šema/migracije, sigurnosne invarijante (auth, tokeni, PII), nepovratne operacije | Implementer → Reviewer 1 → Reviewer 2 (nezavisno) → human approval → merge → post-merge gate |

Za posebno osjetljive pakete (npr. veliki arhitektonski refactor koji
dotiče čitav sloj aplikacije), vrijedi PRIVREMENO podići standardni
MEDIUM proces na dual-review (2 nezavisna reviewera) za CIJELI paket, uz
eksplicitnu odluku human ownera — ovo je bilo namjerno skuplje od
standarda i opravdano se pokazalo vrijednim za taj paket, ali se NE
primjenjuje automatski na sve buduće MEDIUM taskove.

---

## 3. Bootstrap checklist — šta postaviti PRIJE prvog taska

```text
[ ] CLAUDE.md / AGENTS.md (ili ekvivalent za korišćene alate) — kratka
    trajna pravila, thin router ka ostalim dokumentima, ne duplira sadržaj
[ ] .agent/PROJECT_MAP.md — gdje se šta nalazi u repou
[ ] .agent/TASK_ROUTING.md — koji dokument čitati za koji tip taska
[ ] .agent/CURRENT_STATE.md — kratkotrajno stanje (prazno na početku,
    eksplicitno označeno da se periodično čisti, vidi sekciju 15)
[ ] docs/ — dugotrajni planovi, arhitektonske odluke, procesni dokumenti
[ ] agent_reports/ — folder za Task Contracts, implementer i reviewer
    izvještaje (jedan folder, flat, imenovanje po konvenciji iz sekcije 4)
[ ] scripts/coordination.py (ili ekvivalent) — file-claim registar,
    vidi sekciju 5
[ ] Definisan risk-tier proces (sekcija 2) u procesnom dokumentu
[ ] CI: test suite + linter + type checker, sve zeleno prije prvog taska
```

Redoslijed je bitan: dokumentacioni sloj (routing/map/state) PRIJE prvog
taska, ne naknadno — svrha mu je da smanji lutanje po repou kad je task
brief kratak, što ne radi ako ne postoji od početka.

---

## 4. Task Contract — obavezan šablon

**Piše se PRIJE koda, ne retroaktivno.** Ovo je jedina nepregovarana
stavka cijelog sistema — svaka druga praksa ovdje postoji da bi ovu
podržala.

```yaml
---
task_id: <PROJ-NNN>
risk: LOW|MEDIUM|HIGH
implementer: <ime ili TBD>
reviewers: [<ime>, ...]
status: "OPEN — task contract napisan prije koda"
created_at: <datum>
---
```

Tijelo kontrakta mora sadržati:

1. **Kontekst** — zašto ovaj task postoji (referenca na nalaz, plan,
   prethodni task), ne samo šta treba uraditi.
2. **Cilj** — konkretan, provjerljiv opis krajnjeg stanja.
3. **Traženo rješenje** — kad god je moguće, DATI TAČAN KOD/OBLIK, ne
   samo prozni opis. Implementer ne treba da nagađa dizajn-odluke koje su
   već donesene (npr. tačno ime nove metode, tačan potpis, tačan obrazac
   konstrukcije). Ovo drastično smanjuje broj REJECT rundi zbog
   nesporazuma o obliku rješenja.
4. **Acceptance** — checklist, svaka stavka provjerljiva komandom ili
   direktnim čitanjem koda (ne subjektivna ocjena).
5. **Allowed paths / Forbidden paths** — eksplicitna lista. Ovo je
   granica za coordination claim (sekcija 5) I za scope disciplinu.
6. **Review** — ko, kojim redoslijedom, i šta se traži od svakog
   reviewera specifično (ne "provjeri sve", nego "ti provjeri X, drugi
   reviewer Y" ako ima specijalizacije).
7. **Koordinacija** — worktree putanja, ime grane, zavisnosti od drugih
   taskova (i eksplicitna potvrda da je zavisnost STVARNO mergovana u
   main, ne samo da postoji kao grana — vidi sekciju 6).

Imenovanje fajlova (dokazano radi, ne mijenjati bez razloga):

```text
agent_reports/<TASK-ID>-task-contract.md
agent_reports/<YYYY-MM-DD>-<TASK-ID>-<implementer-opis>.md      (implementer report)
agent_reports/<YYYY-MM-DD>-<TASK-ID>-review-<reviewer-ime>.md   (reviewer report)
```

---

## 5. Coordination / file-claim registar

**Problem koji rješava:** dva agenta u različitim worktree-ovima
nezavisno mijenjaju isti fajl → merge konflikt ili tih međusobni prepis.

**Minimalan potreban alat** (CLI, ne mora biti složeniji):

```bash
coordination.py claim   --task <ID> --agent <ime> --paths a.py,b.py
coordination.py status
coordination.py release --task <ID>
coordination.py check   --path <fajl>
```

Bitne osobine:

- Registar mora biti **dijeljen preko svih worktree-ova** (jedan
  centralni fajl/baza, ne po-worktree stanje), inače ne radi svoju
  funkciju.
- Putanje se normalizuju **relativno na korijen trenutnog worktree-a**,
  ne apsolutno — ista logička putanja mora biti uporediva bez obzira iz
  kojeg se worktree-a poziva.
- Idealno: hook koji BLOKIRA pokušaj izmjene fajla koji je zauzet drugim
  taskom (potvrđeno radi za jedan alat u praksi; ako se koristi više
  različitih agentskih alata, ne pretpostaviti da svaki ima isti hook
  mehanizam dok se ne provjeri — označiti kao `UNVERIFIED` dok se ne
  testira, ne kao aktivno).

**Poznat, ponavljan problem:** implementer završi task i zaboravi
osloboditi claim nakon merge-a → sljedeća izmjena istog fajla (npr.
ažuriranje statusa u Task Contractu poslije merge-a) biva blokirana.
**Rješenje koje se ponovilo kao pouzdano:** `coordination.py status` da
se potvrdi da je claim zaista zastario (task već mergovan), pa
`coordination.py release --task <ID>` prije nastavka. Ovo TREBA biti
eksplicitan korak u post-merge checklisti implementera (sekcija 13), ne
prepušteno da se otkrije slučajno.

---

## 6. Git worktree izolacija

- Svaki netrivijalan task dobija svoj worktree i svoju granu.
- **Prije branch-anja, PROVJERITI da je zavisni task STVARNO mergovan u
  main** (`git log --oneline -1 main` upoređeno sa očekivanim commit-om
  zavisnosti) — ne samo da postoji kao grana. Granje sa zastarjelog
  main-a je uzrokovalo stvaran izgubljen rad u praksi; implementer je
  morao merge-ovati svježi main i svjesno ažurirati svoj rad da odražava
  novo kanonsko stanje.
- Imenovanje: `<repo>-worktrees/<TASK-ID>-<kratak-opis>`, grana
  `task/<TASK-ID>-<kratak-opis>`.
- Stari worktree-ovi se NE brišu automatski nakon merge-a osim ako
  eksplicitno zatraženo — mogu sadržati koristan istorijski kontekst, i
  brisanje je nepotrebno destruktivna default akcija.

---

## 7. Pipeline po tasku (puni tok)

```text
Nalaz/potreba
   → Task Contract napisan PRIJE koda (sekcija 4)
   → coordination.py claim (sekcija 5)
   → git worktree, grana sa VERIFIKOVANOG main HEAD-a (sekcija 6)
   → implementacija
       — implementer NE commituje/pušuje sam
       — odstupanja od kontrakta → OUT_OF_SCOPE_FINDING (sekcija 12)
       — implementer report sa DOSLOVNIM verifikacionim outputom
   → koordinator čita STVARAN diff (ne samo izvještaj), nezavisno
     verifikuje, commit + push grane
   → Reviewer 1
       → REJECT → konkretan fix prompt nazad implementeru → ponovi ovaj korak
       → PASS → dalje
   → Reviewer 2 (ako risk tier traži) — NE duplira već završenu
     verifikaciju Reviewer-a 1 (sekcija 9), fokus na ono što je taj
     reviewer specifično zadužen da provjeri
   → Human approval — eksplicitan, nikad pretpostavljen (sekcija 13)
   → Merge (--no-ff preporučeno, jasna commit poruka)
   → Post-merge integration gate (sekcija 14)
   → Task Contract status → DONE + merge hash + review summary
   → State dokument ažuriran, commit + push (poseban commit)
   → coordination claim release (provjeriti da je stvarno oslobođen)
```

---

## 8. Review — strukturiran verdict format

Svaki review izvještaj počinje mašinski-čitljivim blokom:

```yaml
verdict: PASS|PASS_WITH_NOTES|REJECT
scope: PASS|REJECT
acceptance: PASS|REJECT
architecture: PASS|REJECT
security: PASS|REJECT
blocking_findings:
  - <kratak kod nalaza>: <jednoredni opis>
```

Zatim narativne sekcije, dosljedan redoslijed (lakše za brzo skeniranje
kroz veliki broj izvještaja):

```text
CILJ                      — šta se tačno provjerava, u jednoj rečenici
URAĐENO                   — šta je reviewer stvarno provjerio, sa
                             referencama na tačne linije/fajlove
[BLOCKING FINDING]        — samo ako ih ima, sa dokazom (ne pretpostavkom)
STANDARDNA VERIFIKACIJA   — doslovan output test/lint/type-check komandi
NE DIRATI                 — eksplicitna lista šta implementer NE smije
                             raditi u fix rundi (sprečava da fix runda
                             sama proširi scope)
SLJEDEĆE                  — jasna instrukcija ko radi šta poslije ovog
                             izvještaja
```

Ovaj format je namjerno rigidan — svrha nije kreativnost nego da svaki
budući čitalac (agent ili čovjek) zna tačno gdje da nađe verdict bez
čitanja cijelog teksta.

---

## 9. Test-kvalitet i adversarna provjera (imenovana praksa)

**Problem koji rješava:** implementacija je ispravna, ali test koji je
"dokazuje" zapravo provjerava samo krajnji rezultat (npr. da li je
podatak sačuvan), ne PUT kroz koji se do rezultata došlo (npr. da li je
prošao kroz namjeravanu arhitektonsku granicu). Takav test daje lažan
PASS i na starom, pogrešnom putu — što znači da ne štiti od regresije.

**Ovo se desilo ponovljeno, identičnim obrascem, prije nego što je
implementer naučio da to izbjegne unaprijed.** Vrijedno je formalizovati
kao obavezan korak kad god task mijenja PUT kojim se dolazi do istog
krajnjeg rezultata (npr. "View poziva Service direktno" → "View poziva
Service kroz Controller").

**Obavezna procedura (TEST-ADVERSARIAL):**

```text
1. Napiši test koji tvrdi da dokazuje novi put.
2. PRIVREMENO vrati stari (pogrešan) put u produkcijskom kodu.
3. Pokreni upravo taj test.
4. Test MORA pasti. Ako prolazi, test ne dokazuje ništa — mora se
   prepraviti (npr. spy/monkeypatch na novu granicu + stara metoda
   postavljena da baci grešku ako je pozvana direktno).
5. Vrati ispravan kod.
6. Isti test MORA proći.
7. Dokumentuj oba rezultata (fail-na-starom, pass-na-novom) u izvještaju
   kao dokaz, ne samo tvrdnju.
```

**Preporuka:** ako je Task Contract poznat unaprijed kao ovaj tip
promjene (View→Controller, ili slično), navesti ovu proceduru direktno u
kontraktu kao dio Acceptance-a — implementer koji je uradi PROAKTIVNO
(prije nego što reviewer to zatraži) uštedi cijelu REJECT rundu. Ovo je
dokazano radilo: identičan tip taska koji je preskočio ovaj korak je
dobio REJECT i morao ponoviti rundu; sljedeći isti-tip task koji ga je
uradio unaprijed prošao je review na prvi pokušaj.

---

## 10. Paralelizacija — protokol provjere

**Ne pretpostaviti** da dva taska mogu ići paralelno — provjeriti prije
dodjele:

```text
1. Uzeti allowed_paths oba kandidatska Task Contracta.
2. Provjeriti da je presjek PRAZAN (nijedan fajl se ne pojavljuje u oba).
3. Ako je presjek prazan → mogu paralelno, dodijeliti različitim agentima.
4. Ako presjek NIJE prazan → razmotriti REDIZAJN jednog od kontrakata da
   se preklapanje izbjegne (npr. svaki potrošač konstruiše svoju
   nezavisnu instancu dijeljene klase umjesto da se ta klasa ožičava
   kroz centralni fajl koji oba taska moraju dirati) — samo ako je
   redizajn jeftin i ne žrtvuje ništa bitno. Inače, sekvencijalno.
```

Ovo je dokazano vrijedno: nekoliko puta je originalni dizajn taska
slučajno pravio nepotrebno preklapanje (npr. oba taska trebaju ožičiti
novu komponentu kroz isti centralni "glavni" fajl), a jednostavna izmjena
dizajna (svaki potrošač pravi svoju privatnu instancu umjesto dijeljene)
je eliminisala preklapanje i omogućila stvaran paralelan rad bez ikakvog
gubitka funkcionalnosti.

---

## 11. Eskalacija — "fresh reviewer" obrazac

**Kad se desi:** reviewer je (namjerno ili slučajno) postao i
implementer za dio problema u istom tasku — npr. naredba da reviewer sam
završi fix koji implementer nije uspio nakon više pokušaja.

**Šta NE raditi:** preskočiti review za taj dio jer je "reviewer to već
pregledao dok je pravio fix" — to nije nezavisan review, to je
samo-provjera.

**Šta uraditi:** dovesti STVARNO nezavisnog reviewera (drugi agent koji
NIJE vidio prethodno rezonovanje/pokušaje) da uradi taj review od nule,
eksplicitno instruisan da ne čita prethodnu istoriju prije sopstvene
provjere. Ovo je jedini način da se zadrži garancija nezavisnog reviewa
kad kontaminacija postane neizbježna.

---

## 12. Evidence i izvještaji — pravila preciznosti

- **Izvještaji se pišu sa istom preciznošću kao kod.** "Testovi prolaze"
  nije prihvatljivo — potreban je doslovan output (`X passed, Y
  warnings`). Precizna tvrdnja koja se kasnije pokaže netačnom (npr.
  "byte-identično" kad je zapravo identično tek nakon normalizacije) se
  eksplicitno ispravlja, ne ostavlja da stoji.
- **`OUT_OF_SCOPE_FINDING` format** za bilo koje odstupanje od kontrakta:

  ```yaml
  finding: OUT_OF_SCOPE_FINDING
  description: <šta i zašto>
  location: <fajl:linija>
  risk: LOW|MEDIUM|HIGH
  proposed_task: <novi task ID ili "none" ako je popravka unutar allowed_paths>
  ```

  Ako je odstupanje NUŽNA korekcija da bi kontraktova instrukcija uopšte
  radila (npr. kontrakt je tražio nešto što bi pokvarilo postojeći test),
  implementer smije to ispraviti UNUTAR allowed_paths, ALI mora
  dokumentovati kao finding — koordinator/reviewer to nezavisno
  provjerava prije nego što se prihvati (ne uzima se implementerovoj
  tvrdnji na riječ, čak i kad je implementer u pravu).
- **Ne dupliraj tuđu već završenu verifikaciju.** Ako je Reviewer 1 već
  adversarno dokazao nešto (npr. da fix radi), Reviewer 2 ne treba
  ponavljati identičnu proceduru — treba provjeriti ono što Reviewer 1
  po svojoj specijalizaciji NE bi nužno uhvatio. Ponavljanje već
  završenog posla je čist trošak bez dodatne sigurnosti.

---

## 13. Human approval — gate koji se nikad ne pretpostavlja

- Bez obzira koliko je reviewera dalo PASS, merge se ne dešava dok human
  owner eksplicitno ne odobri.
- Jedno prošlo odobrenje ne znači odobrenje za sve buduće slične akcije —
  svaki merge traži svoj eksplicitan signal.
- Nakon odobrenja, koordinator radi: merge → post-merge gate → state
  update → claim release — sve u istom koraku, ne razbacano kroz sesiju,
  da se ne izgubi nijedan dio checkliste.

---

## 14. Post-merge integration gate

**Zašto ne dovoljno samo "grana je bila zelena":** merge sam po sebi
može unijeti interakcijski problem koji nijedna grana pojedinačno nije
imala (dva taska nezavisno ispravna, zajedno ne).

Obavezno nakon SVAKOG merge-a u glavnu granu:

```bash
<test suite> -q
<linter> <relevantan scope>
<type checker> <relevantan scope>
```

Sve mora biti čisto NA GLAVNOJ GRANI nakon merge-a, ne samo na
feature grani prije merge-a.

---

## 15. Održavanje state dokumenta — kratkotrajan, ne istorijski arhiv

`.agent/CURRENT_STATE.md` (ili ekvivalent) mora eksplicitno navesti u
svom vrhu da sadrži SAMO kratkotrajne informacije koje mogu zastarjeti za
par sedmica — ne trajna pravila (ta idu u procesni dokument) i ne
kompletnu istoriju (ta živi u git log-u i pojedinačnim task izvještajima).

**Periodično čistiti:** kad dokument naraste sa starim, više-neoperativno
relevantnim detaljima (završeni paketi, riješeni bugovi iz prošlosti),
ukloniti ih i zamijeniti kompaktnom tabelom/referencom na git commit
hash. Cilj je da svaki novi agent koji otvori ovaj fajl dobije TRENUTNO
stanje za par sekundi čitanja, ne arheologiju projekta.

---

## 16. Anti-patterns — šta izbjegavati

- **Praviti Task Contract retroaktivno** (poslije koda) — gubi se cijela
  svrha, implementer je već donio dizajn-odluke bez provjere.
- **Vjerovati izvještaju implementera bez čitanja stvarnog diff-a** —
  izvještaj opisuje NAMJERU, ne nužno stvarno stanje.
- **Preskočiti review jer "je task mali"** — mali task može i dalje
  nositi arhitektonski rizik; risk tier (sekcija 2), ne veličina diff-a,
  određuje koliko reviewa treba.
- **Dozvoliti implementeru da commituje/pušuje bez zahtjeva** — gubi se
  checkpoint gdje koordinator vidi tačno stanje prije nego što uđe u
  istoriju.
- **Ostaviti coordination claim zauzet nakon merge-a** — blokira
  sljedeću legitimnu izmjenu; provjeriti i osloboditi kao rutinski
  zadnji korak, ne kao vatrogasnu intervenciju kad se prvi put desi
  problem.
- **Širiti scope u istom tasku kad se nešto usput otkrije** — prijaviti
  kao finding, otvoriti novi task, ne pokušavati "dok smo već tu".
- **Tretirati zeleni CI kao dokaz arhitektonske ispravnosti** — CI
  potvrđuje da postojeći testovi prolaze; ne potvrđuje da su ti testovi
  uopšte testirali pravu stvar (vidi sekciju 9).
- **Dozvoliti da state dokument postane istorijski arhiv** — vidi
  sekciju 15.

---

## 17. Opciono/emerging: deterministički arhitektonski senzori

**Status: NIJE dokazana praksa u trenutku pisanja ovog blueprinta — pilot
u toku.** Uključeno ovdje kao nacrt jer adresira realan, ponovljen
problem (sekcija 9 — arhitektonski bypass koji prolazi kroz zeleni CI),
ali NE tretirati kao obavezan dio blueprinta dok se ne dokaže mjerljivo.

Ideja: AST-bazirani statički senzor koji hvata poznatu klasu
arhitektonskog prekršaja (npr. "sloj A direktno poziva sloj C, mimoilazi
sloj B") DETERMINISTIČKI, prije reviewera — praćen kratkim kontekstualnim
"habit guide" tekstom koji agentu objašnjava ŠTA signal znači i kako
ispravno reagovati (ne samo "greška", nego "evo zašto i evo kako").

**Obavezan uslov prije nego što se ovakav senzor doda u CI:** replay
validacija protiv poznate istorije — senzor mora dokazano pronaći tačno
poznate prošle prekršaje (ni manje ni više, provjeriti false positive na
čistom kodu) prije nego što mu se vjeruje da blokira nove taskove.
Senzor koji ne prođe ovu provjeru se NE stavlja u CI.

Ako se ovaj sloj usvoji, prati mu iste discipline kao i review (sekcija
16): ne dozvoliti "gaming" senzora (preimenovanje da senzor ne vidi,
allowlist bez opravdanja, slabljenje testa) — svaki takav pokušaj je
ozbiljniji problem od samog prekršaja koji je senzor trebao uhvatiti.

---

## 18. Kako adaptirati ovaj blueprint za novi projekat

1. Kopirati ovaj fajl u korijen novog repoa.
2. Popuniti sekciju 1 (uloge) sa stvarnim imenima/alatima koji će se
   koristiti na tom projektu.
3. Potvrditi ili prilagoditi risk-tier definicije (sekcija 2) stvarnom
   prirodom projekta (šta je "HIGH" ovdje zavisi od domene — finansije,
   zdravstvo i interni alat imaju različite pragove).
4. Napraviti bootstrap fajlove iz sekcije 3.
5. Implementirati (ili preuzeti postojeći) coordination CLI po specifikaciji
   iz sekcije 5.
6. NE preskakati sekcije 4, 6, 7, 8, 13, 14 — ovo je jezgro sistema, sve
   ostalo je pojačanje jezgra.
7. Sekcija 17 (senzori) je opciona i tek nakon što je jezgro dokazano
   stabilno na tom projektu.
8. Nakon prvih nekoliko taskova, ažurirati OVAJ fajl ako se pokaže da
   neka praksa ne odgovara — ali svaku izmjenu opravdati konkretnim
   iskustvom (kao što je svaka postojeća stavka ovdje opravdana), ne
   ukidati disciplinu "radi brzine" bez zamjene koja rješava isti
   problem na drugi način.
