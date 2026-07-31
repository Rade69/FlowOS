# Bootstrap izvještaj — FlowOS

**Datum:** 2026-07-31
**Agent:** pi (Claude opus model)
**Scope:** Inicijalni bootstrap CLAUDE.md prema UNIVERSAL_CLAUDE.md šablonu

## Task contract

- **Cilj:** Spojiti UNIVERZALNE strukturne principe sa postojećim FlowOS-specifičnim CLAUDE.md
- **Scope:** Merge postojećeg CLAUDE.md sa novim elementima iz UNIVERSAL_CLAUDE.md
- **Out-of-scope:** Nema implementacije, nema prepravljanja arhitektonskih odluka
- **Acceptance kriterij:** Spojeni CLAUDE.md sadrži sve iz originala + strukturne elemente koji su nedostajali, bez dupliranja

## Impact analiza

N/A — projekat je u fazi 0, nema koda, nema pozivalaca. Impact je dokumentacijski.

## Šta je urađeno

Bootstrap procedura iz Sekcije 0 UNIVERSAL_CLAUDE.md izvršena je u potpunosti:

### Skeniranje projekta (8 koraka)

1. **Tech stack** — Nema manifest fajlova. Stack definisan u FlowOS-kompletan-plan.md §4: Python 3.12 + FastAPI, SQLite/WAL, Alembic, watchdog, Electron/React GUI, PowerShell/Python CLI, Windows Job Objects.
2. **Struktura projekta** — Samo 5 root fajlova: AGENTS.md, CLAUDE.md, FlowOS-kompletan-plan.md, FolowOS-MOKAP-nove-3.png, UNIVERSAL_CLAUDE.md. Nema direktorijuma, nema koda. Faza 0 (planiranje/validacija).
3. **Konvencije koda** — Nema koda, ne postoje konvencije.
4. **Testovi** — Ne postoje. Plan predviđa `scripts/verify.py` od faze 3.
5. **Git istorija** — Prazan repo, 0 commitova, 5 untracked fajlova.
6. **Agent-infrastruktura** — AGENTS.md (projektna pravila), CLAUDE.md (FlowOS-specifičan), UNIVERSAL_CLAUDE.md (bootstrap šablon), FlowOS-kompletan-plan.md (arhitektura i faze).
7. **Evergreen napomene** — Nema koda za pretragu. Nema `HACK`, `WARNING`, `workaround` komentara.
8. **Sigurnost** — Nema `.env` fajlova, tajni, kredencijala. Plan specificira Windows Credential Manager.

### Merge CLAUDE.md

Postojeći CLAUDE.md (originalni, ljudski kuriran) zadržan je **doslovno u cjelini**. Dodato je **16 strukturnih elemenata**:

| Novi element | Pozicija |
|---|---|
| Token budget i context disciplina | Poslije Jezika |
| Evergreen napomene (N/A za sad) | Poslije Token budgeta |
| Obavezno prije nego počneš kodirati | Prije Arhitekture |
| Facts vs Decisions šablon | Unutar prethodnog |
| Confirmation gate | Unutar prethodnog |
| Reprodukcija i provjera prije rada | Prije Arhitekture |
| PROBE format | Prije Arhitekture |
| Plan prije HIGH/CRITICAL izmjene | Korak 5 u Proceduri prije izmjene |
| Handoff visokog rizika | Korak 6 u Proceduri prije izmjene |
| Definition of Done po tipu promjene (tabela) | Unutar Verifikacije |
| Hijerarhija dokaza (7 nivoa) | Unutar Verifikacije |
| Podjela odgovornosti (tabela) | Poslije Verifikacije |
| Nezavisna provjera (checker) | Poslije Podjele odgovornosti |
| Format zadatka za agenta | Poslije Nezavisne provjere |
| Format outputa (STATUS: OK/PARCIJALNO/BLOKIRANO) | U Proceduri nakon zadatka |
| Provjera prije predaje (checklist 9 stavki) | U Proceduri nakon zadatka |
| Kad ovaj fajl podijeliti na više (Sekcija 3) | Na kraju |

## Šta nije dirano

- AGENTS.md — netaknut
- FlowOS-kompletan-plan.md — netaknut
- FolowOS-MOKAP-nove-3.png — netaknut
- Sve arhitektonske i produktne odluke u originalnom CLAUDE.md — zadržane doslovno
- Nije dodato ništa što bi kontradiktovalo postojećim pravilima

## Verifikacija

- Ručno poređenje starog i novog CLAUDE.md: svi originalni odjeljci prisutni, sve nove sekcije dodate bez dupliranja
- UNIVERSAL_CLAUDE.md obrisan (svrha: referenca za spajanje)
- agent_reports/ folder kreiran
- Bootstrap status linija dodata na vrh CLAUDE.md

## Pronađeni problemi

Nema — projekat je u fazi planiranja, čist.

## Odbačene opcije

- **Opcija:** Prepisati CLAUDE.md "ljepšim" tekstom → **Odbijeno** jer postojeći sadrži ljudski kurirano znanje koje je po pravilu tačnije od bilo čega što bi svježi sken koda mogao zaključiti (UNIVERSAL_CLAUDE.md pravilo)
- **Opcija:** Dodati i Sekciju 1 (Zašto ova pravila postoje) → **Odbijeno** jer postojeći CLAUDE.md već ima jaku motivaciju kroz "Šta je FlowOS" i principe iz plana

## Rizici i ograničenja

- Projekat nema kod — većina bootstrap koraka vratila je prazne rezultate. Očekivano za fazu 0.
- Evergreen napomene su N/A — popuniće se prirodno s prvim kodom
- Nema `.gitignore` — treba ga dodati prije prvog koda

## Potreban follow-up

- Dodati `.gitignore` prije prvog generisanog koda/biblioteka
- Popuniti Evergreen napomene čim se pojave prvi `HACK`/`WARNING`/`workaround` komentari
- Razmotriti `docs/context/history.md` podjelu kad Evergreen napomene pređu ~100-150 linija

## Potrebna korisnička potvrda

- Potvrđeno — merge izvršen, Git repo inicijalizovan