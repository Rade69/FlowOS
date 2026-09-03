# Kako radim — opis radnog toka sa AI agentima

**Namjena:** ovaj dokument opisuje moj (Radovanov) stvaran radni tok kad
razvijam softver uz pomoć AI agenata — koje alate koristim, u kojoj ulozi,
i kako se sve to uklapa u jednu cjelinu. Pisano da mogu jasno objasniti
nekome ko pita "kako ti to radiš?", bez potrebe da pretražujem chat
istoriju da bih se sjetio detalja.

---

## 1. Filozofija u jednoj rečenici

> **Ništa se ne prihvata na riječ — svaka tvrdnja ("radi", "testovi
> prolaze", "gotovo je") mora imati dokaz koji neko drugi može nezavisno
> provjeriti, prije nego što uđe u glavnu granu koda.**

Ovo je namjerno sporije od "pusti agenta da radi i vjeruj mu". Cijena
greške u ozbiljnom softveru je stvarna; cijena dodatnog kruga provjere je
mala u poređenju s tim. Proces je izgrađen oko toga da agenti — koliko
god sposobni — griješe, preuveličavaju, ili propuste rub-slučaj, i da
sistem to mora uhvatiti PRIJE nego što čovjek (ja) treba da bude
posljednja linija odbrane za svaki detalj.

---

## 2. Akteri — ko radi šta

| Ko | Uloga |
|---|---|
| **Ja (Radovan)** | Jedini izvor konačnog odobrenja. Odlučujem obim, prioritet, dodjeljujem ko radi šta. Ništa se ne merguje u glavnu granu bez mog eksplicitnog "odobravam" — čak ni kad su oba reviewera dala zeleno svjetlo. |
| **Claude Code** | Radi kao koordinator: piše tačnu specifikaciju zadatka PRIJE nego što iko napiše kod, priprema konkretne instrukcije za druge agente, nezavisno provjerava njihov rad (čita stvaran kod, sam pokreće testove — ne vjeruje samo izvještaju), jedan je od dva nezavisna reviewera, radi spajanje (merge) u glavnu granu, i održava dokumentaciju stanja projekta. |
| **Codex** | Drugi nezavisni reviewer, poseban fokus na kvalitet testova i "adversarnu" provjeru — namjerno vraća stari, pogrešan kod da provjeri da li novi test to stvarno hvata. |
| **Pi i Crush** | Implementatori — pišu stvaran kod prema specifikaciji. Nikad ne commituju/pušuju sami bez mog zahtjeva. |

**Nepregovarano pravilo:** ko je implementirao nešto, ne smije biti i
(jedini) reviewer za to isto. Nezavisnost review-a je namjerna, ne
formalnost.

---

## 3. Alati — šta se stvarno koristi

### Osnovni razvojni alati
- **Git / GitHub** — verzionisanje. Svaki netrivijalan zadatak dobija
  svoju izolovanu granu i svoju kopiju radnog direktorija ("git
  worktree"), da dva agenta koja rade istovremeno fizički ne mogu
  slučajno prepisati isti fajl na disku.
- **Terminal (PowerShell/Bash)** — gdje se sve odvija: pokretanje
  testova, git komande, provjere.
- **VS Code** — okruženje u kojem sve ovo živi.

### Naši vlastiti alati (napravljeni tokom rada, ne kupljeni)
- **`coordination.py`** — "registar zauzeća" fajlova. Prije nego što
  agent počne raditi, "zauzme" tačnu listu fajlova koje planira mijenjati.
  Ako drugi agent pokuša da dirne isti fajl dok je zauzet, alat to
  blokira. Ovo je ono što nam dozvoljava da dva agenta rade PARALELNO bez
  straha od sudara.
- **`agent_sensors.py`** — noviji alat (izgrađen u ovoj sesiji, poslije
  nekoliko ponovljenih grešaka koje smo ručno hvatali). Automatski,
  deterministički skenira kod i traži poznate arhitektonske greške (npr.
  GUI koji direktno mijenja bazu umjesto da prođe kroz predviđeni sloj) —
  hvata ih PRIJE nego što čovjek ili reviewer to primijeti ručno.

### Verifikacioni alati (standardni, ali obavezni na svakom koraku)
- **pytest** — pokreće cijeli test suite.
- **ruff** — provjerava stil/kvalitet Python koda.
- **mypy** — provjerava tipove (hvata cijelu klasu grešaka prije nego što
  se kod uopšte pokrene).

### GitNexus — "graf znanja" o kodu
Alat koji indeksira cijeli repo u graf bazu i omogućava pitanja koja
obično grep/pretraga teksta ne može:

- "šta bi se pokvarilo ako promijenim ovu funkciju?" (analiza uticaja /
  "blast radius");
- "ko sve poziva ovu funkciju, i šta ona sama poziva?" (360-stepeni
  pregled jednog dijela koda);
- "koje API rute postoje i ko ih sve koristi?";
- sigurno preimenovanje kroz cijeli kod (nalazi SVE reference, ne samo
  tekstualne podudarnosti).

Koriste ga i drugi agenti (ne samo ja). Najkorisniji je kad se ulazi u
nepoznat ili velik dio koda i treba razumjeti posljedice prije izmjene.
U dijelovima rada gdje je zadatak već došao sa preciznom specifikacijom
(tačan fajl, tačna linija, tačan predložen kod) manje je potreban jer je
"analiza uticaja" već urađena ručno prilikom pisanja specifikacije.

### Skillovi — spakovane, ponovo-upotrebljive procedure
Kad zadatak odgovara poznatom, već uvježbanom obrascu, umjesto da se
proces izmišlja iznova, poziva se imenovan "skill" — gotov set
instrukcija za tu vrstu posla. Primjeri: pregled koda prije spajanja
grane (code review), reprodukcija i dijagnostika prijavljenog bug-a prije
nego što se uopšte pokuša popravka, dizajn i objava vizuelnog
dokumenta/izvještaja. Skill se poziva po imenu kad prepoznam da zadatak
spada u tu kategoriju — ovo sprečava da se ista vrsta posla svaki put
radi na malo drugačiji, nedosljedan način.

---

## 4. Pisani trag — zašto ništa ne živi samo u razgovoru

Svaki zadatak ostavlja trag u `agent_reports/` folderu, kao obični
tekstualni (markdown) fajlovi, trajno sačuvani u git istoriji:

1. **Specifikacija zadatka** (Task Contract) — napisana PRIJE ijedne
   linije koda. Sadrži tačan cilj, često i tačan predložen kod, listu
   fajlova koje SMIJE i koje NE SMIJE dirati, i kako će se prihvatiti
   kao gotovo.
2. **Izvještaj implementatora** — šta je stvarno urađeno, sa doslovnim
   (kopiranim, ne prepričanim) izlazom iz terminala kao dokazom.
3. **Izvještaj svakog reviewera** — u strogo istom formatu svaki put
   (jasan verdikt na vrhu: prolazi / prolazi uz napomenu / odbijeno),
   tako da se brzo skenira bez čitanja cijelog teksta.

Razlog: razgovor u chatu nestaje. Fajl u git istoriji ne nestaje, i svako
— uključujući mene za tri mjeseca — može otvoriti tačno taj fajl i
razumjeti šta se desilo i zašto, bez rekonstrukcije iz sjećanja.

---

## 5. Pun tok jednog zadatka, korak po korak

```text
1.  Prepozna se potreba (nalaz iz provjere, stavka iz plana, moj zahtjev)
2.  Claude piše specifikaciju zadatka — PRIJE koda
3.  Agent "zauzima" fajlove koje će mijenjati (coordination.py)
4.  Napravi se izolovana grana + kopija radnog direktorija
5.  Implementator (Pi ili Crush) piše kod — NE commituje sam
6.  Implementator piše izvještaj sa doslovnim dokazom (izlaz testova)
7.  Claude čita STVARAN kod (ne samo izvještaj), sam pokreće testove,
    tek onda commituje i pušuje granu
8.  Reviewer 1 (Codex) — nezavisan pregled, fokus na test kvalitet
        → ako nešto ne valja: tačna instrukcija nazad implementatoru,
          ponovi od koraka 5
        → ako valja: dalje
9.  Reviewer 2 (Claude) — nezavisan arhitektonski pregled
        (NE ponavlja ono što je Reviewer 1 već dokazao — fokus na ono
        što taj reviewer po svojoj ulozi ne bi nužno uhvatio)
10. JA dajem konačno odobrenje — nikad automatski, uvijek eksplicitno
11. Spajanje u glavnu granu
12. Ponovna, potpuna provjera NA glavnoj grani (ne samo na grani
    zadatka — hvata slučajeve gdje su dva ispravna zadatka zajedno
    ipak napravila problem)
13. Ažurira se dokumentacija stanja projekta, "zauzeće" fajlova se
    oslobađa
```

Ovaj tok se ponavlja za svaki, čak i mali zadatak — razlika je samo u
tome koliko je od ovih koraka OBAVEZNO za dati nivo rizika (sitna,
lako-povratna izmjena ide brže i lakše nego nešto što dira baznu šemu
ili bezbjednost).

---

## 6. Kako radimo paralelno bez sudaranja

Prije nego što se dva agenta puste da rade ISTOVREMENO, provjerava se:
da li bi njihove liste fajlova ("koje smiju dirati") uopšte preklapale.
Ako se ne preklapaju — mogu paralelno, svaki u svom izolovanom
direktorijumu. Ako bi se preklapale, ili se posao radi jedan-za-drugim,
ili se — ako ima smisla — sam DIZAJN zadatka mijenja tako da preklapanje
nestane (npr. svaki dio koda pravi svoju nezavisnu instancu nečega
umjesto da oba moraju dirati isti centralni "ožičavajući" fajl).

Ovo se ne pretpostavlja automatski — provjerava se svaki put prije
dodjele, jer je pogrešna pretpostavka o paralelizmu skuplja nego minut
provjere unaprijed.

---

## 7. Kako hvatamo greške — stvaran primjer, ne teorija

Test koji samo provjerava "da li je rezultat na kraju ispravan" nije
dovoljan kad je poenta zadatka da se promijeni PUT kojim se do rezultata
dolazi (npr. "GUI više ne smije direktno pisati u bazu, mora ići kroz
predviđeni međuloj"). Takav slab test bi i dalje prošao i sa STARIM,
pogrešnim kodom — što znači da ništa stvarno ne štiti.

Zato je uvedeno pravilo: kad se popravlja ovaj tip problema, implementator
mora DOKAZATI da njegov novi test pada na starom, pogrešnom kodu i
prolazi na novom, ispravnom. To se radi tako što se privremeno vrati
stari kod, pokrene se novi test, mora pasti; vrati se ispravan kod, isti
test mora proći. Oba rezultata se zapisuju kao dokaz, ne samo tvrde.

Ovo pravilo nije izmišljeno unaprijed — otkriveno je nakon što se
IDENTIČAN propust desio dva puta zaredom kod dva različita zadatka.
Poslije toga je postalo standardna praksa unaprijed, ne nešto što se
čeka da reviewer ponovo uhvati.

---

## 8. Kad nešto pođe po zlu — transparentnost, ne prikrivanje

Greške se dešavaju i agentima i meni. Primjer iz stvarnog rada: dok sam
provjeravao jednu izmjenu, greškom sam pokrenuo git komandu koja je
obrisala rad koji implementator još nije bio sačuvao u istoriju. Primijetio
sam odmah (nešto što je trebalo postojati — nije postojalo), odmah sam to
rekao naglas, i rekonstruisao tačno taj rad iz onoga što sam prethodno
pročitao — provjereno da je rezultat identičan onome što je izgubljeno,
prije nego što sam nastavio.

Pravilo: ako se nešto pokvari, prvo se to prizna i popravi, TEK onda se
nastavlja — nikad se ne prelazi preko toga tiho.

---

## 9. Sažetak za brzo objašnjenje

> Radim sa više AI agenata koji imaju jasno odvojene uloge (piše
> specifikaciju / piše kod / nezavisno provjerava kod dva puta), svaki
> zadatak ima pisani trag prije, tokom i poslije rada, ništa se ne
> spaja u glavni kod bez dva nezavisna "da" i mog konačnog "da", i
> svaka tvrdnja da "nešto radi" mora imati dokaz koji se može ponovo
> provjeriti — ne samo izjavu agenta da je gotovo.

---

## 10. Napomena o ovom dokumentu

Ovo NIJE generički predložak za druge projekte — za to postoji zaseban
fajl (`AGENTIC_WORKFLOW_BLUEPRINT.md`) koji je namjerno bez ijedne
Dentaland specifičnosti. Ovaj dokument je lični opis stvarnog toka, za
tvoje (Radovanovo) razumijevanje i objašnjavanje drugima, sa svim
konkretnim imenima alata koji se zaista koriste.
