# FlowOS — Design brief za Milestone 1 (Faza C)

**Svrha:** vizuelna referenca za dva ekrana koja Milestone 1 stvarno
sadrži. Ovo nije specifikacija cijele aplikacije — devet ekrana sa
prošlog mokapa miješa postojeće, sadašnje i namjerno odgođeno. Ovaj
dokument crta samo ono što je sadašnje.

---

## 0. Obim

```text
U OBIMU:      Pregled (dopunjen)
              Zadaci (nova tabla)

NE CRTATI:    Task Detail dubinski panel
              Aktivnost kao zasebna stranica
              bilo kakva odluka o Konfliktima/Izvještajima/Postavkama
```

Sve ostalo (Plan, Sesije, Agenti, Radna stabla, Projekti) već postoji i
radi u aplikaciji — ne redizajnirati, ne crtati ponovo. Ako se ChatGPT
pita treba li nešto dodati van ova dva ekrana, odgovor je ne.

---

## 1. Zadaci — glavni ekran

Jedan red po Tasku. Pet kolona, tim redom:

```text
Task        Ko radi     Gdje je         Zadnji signal    Čeka
```

- **Task** — FLOW broj, kratak naziv ispod ili pored.
- **Ko radi** — dodijeljen agent (iz Task Contracta, ne pretpostavka).
- **Gdje je** — workflow stanje: `IMPLEMENTED`, `VERIFIED`, `REVIEWED`,
  ili prazno ako nema nijednog izvještaja.
- **Zadnji signal** — vremenska oznaka + izvor (fajl, commit, izvještaj).
- **Čeka** — šta blokira napredak: `review`, `tebe`, `—`.

### 1.1 Signal razdvajanje — obavezno pravilo

Dvije vrste podataka koje kolone „Gdje je" i „Zadnji signal" nose moraju
biti **vizuelno različite**, ne isti stil badge-a:

```text
MEHANIČKI SIGNAL (Zadnji signal)     WORKFLOW STANJE (Gdje je)
— fajl, commit, proces živ            — postoji samo ako je pisan izvještaj
— neutralna boja, tiha tipografija    — obojen badge, jasna riječ
— nikad ne tvrdi "gotovo"             — jedino ovo tvrdi status
```

**Kritično:** ako task ima svježu fajl/commit aktivnost ali nema
izvještaja, kolona „Gdje je" mora izgledati **prazno/upitno** — vizuelna
rupa, ne isti izgled kao „u radu". Ne izmišljati status iz aktivnosti.

### 1.2 Filter tabovi iznad table

```text
Svi | Aktivni | Čekaju mene | Bez signala | Završeni
```

„Čekaju mene" i „Bez signala" nisu kozmetički filteri — to su direktni
prikazi dvije nove provjere (detekcija tišine, decision bez odgovora).
Kad se filtrira na njih, tabela treba dodatno istaći **koliko dugo**
traje to stanje (npr. "3h bez signala"), ne samo da li je uslov ispunjen.

### 1.3 Klik na red

Otvara panel sa dokazom: link na izvještaj, diff, verify output, i
kontrole odluke (prihvati / vrati na doradu) ako task čeka na korisnika.

**Granica panela — ne prekoračiti:**

```text
SMIJE:  naziv taska, ko/risk, tri-četiri linije dokaza, dugmad odluke
NE SMIJE: postajati višesekcijski detaljni ekran sa istorijom,
          metrikama, granama, tehničkim detaljima worktreeja
```

Ako panel počne rasti van ovoga, to je znak da se vraća u Task Detail
koji je namjerno odgođen — stati na „dokaz + odluka".

---

## 2. Pregled — dopuna

Postojeći ekran, dodati brojčane indikatore izvedene iz iste table:

```text
[ Aktivnih zadataka ]  [ Čekaju mene ]  [ Bez signala ]  [ Aktivne sesije ]
```

„Čekaju mene" i „Bez signala" moraju biti vizuelno upozoravajući kad je
broj > 0 (npr. boja koja odudara od ostalih), jer je to tačno ono što
korisnik treba da primijeti prvo. Ispod: kratka lista „traži pažnju" —
najviše tri do pet taskova sortiranih po tome koliko dugo čekaju, ne po
FLOW broju.

---

## 3. Stil

Ne propisujem boje ni font — to je slobodno. Jedino tvrdo pravilo je iz
1.1: mehanički signal i workflow stanje moraju biti vizuelno
razdvojivi na prvi pogled, bez čitanja teksta.

---

## 4. Podsjetnik

Ovo je referenca za **ideju**, ne za implementaciju. Konačan izgled u
kodu zavisi od FLOW-1202/1203 taskova kad se otvore. Ne prenositi ovaj
brief kao gotovu specifikaciju dizajna dok ti taskovi ne budu aktivni.
