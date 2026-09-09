# Graft hooks/skill/statusline A/B benchmark — 2026-09-09

## Sažetak odluke

Testirana je puna repo-local Graft 0.16.0 instalacija za Claude Code — MCP, skill, hooks i statusline — protiv kontrolne varijante sa istim Graft MCP serverom, ali bez Graft skilla, hookova i statuslinea.

Na tri validna FlowOS zadatka obje varijante su dale funkcionalno tačne odgovore. Puna instalacija je ukupno obradila 995.648 tokena naspram 1.605.418 u kontroli, odnosno 38,0% manje, i koštala je 0,8568 USD naspram 1,1561 USD, odnosno 25,9% manje. Međutim, agregat skriva izrazitu zavisnost od tipa zadatka:

- na uskom locate zadatku puna instalacija je potrošila 44,0% više tokena;
- na širokom impact zadatku potrošila je 61,6% manje tokena;
- na pregledu jednog velikog fajla potrošila je 47,2% više tokena.

Zato rezultat ne opravdava automatsku punu instalaciju za svaku sesiju. Najbolji izmjereni kompromis je zadržati Graft MCP, a skill i prompt/session hooks uključivati ciljano za široke impact/trace zadatke. Statusline je jeftin, ali njegova prikazana statistika štednje u ovom testu nije bila pouzdana.

## Task contract

**Cilj:** izmjeriti ponašanje, kvalitet, stvarnu modelsku potrošnju tokena i operativni overhead pune Graft integracije u odnosu na Graft MCP bez hooks/skilla/statuslinea.

**Scope:** tri read-only Claude Code A/B zadatka na istom FlowOS commitu, lokalni test svih instaliranih hook tipova, statusline test, Graft telemetrijski status i cleanup benchmark instalacije.

**Out of scope:** izmjene FlowOS produkcijskog koda, pytest suite, GitNexus-vs-Graft ponavljanje, Graft `--deep`, trajna promjena globalne Claude/Codex konfiguracije i uklanjanje postojećeg GitNexusa.

**Acceptance kriteriji:** isti model i prompt po paru; isti commit; ista MCP dostupnost; fresh session; bez write/shell/web/subagent alata; stvarni Claude usage po runu; odvojeno evidentirani nevalidni pokušaji; dokumentovani hooks, statusline i telemetrija.

## Testno okruženje

- FlowOS commit: `8628dbe` (`fix(plan-import): skip blocking cycle check for informational dependencies`)
- Graft: `0.16.0`
- Claude Code: `2.1.236`
- Model: `claude-sonnet-5`, effort `medium`
- Kontrola: `H:\FlowOS-worktrees\graft-benchmark-8628dbe`
- Puna instalacija: `H:\FlowOS-worktrees\graft-full-hooks-benchmark-8628dbe`
- Oba worktreeja: detached na istom commitu
- Sesije: `--no-session-persistence`, `--setting-sources project`, eksplicitni `.mcp.json`, `--strict-mcp-config`
- Sigurnosna ograničenja: zabranjeni `Bash`, `Write`, `Edit`, `MultiEdit`, `WebSearch`, `WebFetch`, `Task` i `Agent`
- Permission režim validnih runova: `bypassPermissions`; pošto su mutirajući i mrežni alati izričito zabranjeni, ovo je korišteno samo da read-only Graft MCP ne bude odbijen zbog untrusted benchmark worktreeja

Korisnik je eksplicitno odobrio slanje ograničenih FlowOS isječaka Anthropic API-ju i uključivanje Graft telemetrije.

## Šta je sadržavala puna Graft instalacija

Pokrenuto je:

```text
graft init --yes --no-global
```

Repo-local instalacija je dodala ili promijenila:

- `.mcp.json` — Graft MCP server;
- `.claude/skills/graft/SKILL.md` — 9.101 bajt;
- `.claude/helpers/graft-hooks.cjs` — 2.765 bajtova;
- `.claude/helpers/graft-statusline.cjs` — 2.755 bajtova;
- `.claude/settings.json` — 1.870 bajtova;
- `AGENTS.md` — ograđeni Graft instrukcijski blok;
- `.windsurf/rules/graft.md` — 2.293 bajta;
- `opencode.json` — MCP unos;
- `.gitignore`, `.ignore` i lokalni `graft/` graph cache.

Claude postavke su uključivale:

- `SessionStart` hook;
- `UserPromptSubmit` hook;
- `PostToolUse` za edit alate;
- `PostToolUse` za Bash/Graft/Read/Grep/Glob statistiku;
- `Stop` hook;
- glavni i subagent statusline;
- dozvole i footer regex za Graft.

Kontrola je imala samo isti Graft MCP zapis. Nije imala Graft skill, hooks, statusline niti Graft instrukcijski blok.

## Metod mjerenja tokena

Autoritativna potrošnja je uzeta iz završnog Claude Code `stream-json` `usage` objekta.

U tabelama je `ukupni token volume`:

```text
input_tokens
+ cache_creation_input_tokens
+ cache_read_input_tokens
+ output_tokens
```

Ovo je količina tokena koju je servis prijavio kao obrađenu kroz run. Nije isto što i obračunska cijena: cache-read tokeni se tarifiraju drugačije. Zato su kategorije i stvarni `total_cost_usd` prikazani odvojeno.

Graftova poruka `saved ~Nk tokens` nije korištena kao autoritativna metrika. To je procjena hipotetičkih source readova, a ne mjera stvarne modelske potrošnje.

## Validni A/B rezultati

| Task | Varijanta | Input | Cache create | Cache read | Output | Ukupni volume | Cijena | Claude trajanje | Turns |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| T1 locate | MCP bez hooks/skilla | 14 | 21.580 | 223.562 | 1.648 | 246.804 | $0,2224 | 22,016 s | 7 |
| T1 locate | puna instalacija | 18 | 26.568 | 326.672 | 2.048 | 355.306 | $0,2882 | 30,486 s | 9 |
| T3 impact | MCP bez hooks/skilla | 52 | 40.652 | 1.202.038 | 6.851 | 1.249.593 | $0,7085 | 86,996 s | 28 |
| T3 impact | puna instalacija | 22 | 22.176 | 453.909 | 3.789 | 479.896 | $0,3261 | 62,067 s | 13 |
| T4 veliki fajl | MCP bez hooks/skilla | 6 | 28.533 | 78.526 | 1.956 | 109.021 | $0,2252 | 22,739 s | 3 |
| T4 veliki fajl | puna instalacija | 8 | 28.487 | 129.780 | 2.171 | 160.446 | $0,2424 | 31,843 s | 5 |

### Razlika pune instalacije

| Task | Tokeni | Cijena | Claude trajanje | Kvalitet |
|---|---:|---:|---:|---|
| T1 locate | +44,0% | +29,6% | +38,5% | praktično izjednačeno |
| T3 impact | **-61,6%** | **-54,0%** | **-28,7%** | praktično izjednačeno; puna varijanta je bila mnogo fokusiranija |
| T4 veliki fajl | +47,2% | +7,7% | +40,0% | praktično izjednačeno |
| **Ukupno** | **-38,0%** | **-25,9%** | **-5,6%** | bez potvrđenog gubitka tačnosti |

Ukupno:

| Metrika | MCP bez hooks/skilla | Puna instalacija | Razlika |
|---|---:|---:|---:|
| Token volume | 1.605.418 | 995.648 | -609.770 |
| Cijena | $1,1561 | $0,8568 | -$0,2993 |
| Claude trajanje | 131,751 s | 124,396 s | -7,355 s |

Tri zadatka su premali uzorak za univerzalni procenat. Posebno T3 dominira agregatom.

## Ponašanje alata po zadatku

### T1 — precizni locate

Kontrola:

- `Grep`: 4;
- `Read`: 2;
- Graft MCP: 0.

Puna instalacija:

- `ToolSearch`: 1;
- `graft_find_code`: 2;
- `graft_find_all`: 3;
- `Read`: 2.

Obje varijante su pronašle `PlanImportService.import_plan`, blocking-type guard i `test_informational_edge_preserved_when_blocking_first`. Puna instalacija je napravila više retrieval koraka i zatim ipak otvorila dva source regiona. To objašnjava veći token volume i vrijeme.

Oba finalna odgovora su imala istu malu tehničku nepreciznost: formulacija da `check_cycle` obilazi sve tipove postojećih grana nije tačna; aktuelni BFS filtrira postojeće blocking grane. Suština ordering testa ipak ostaje tačna: kada se predložena INFORMATIONAL grana pogrešno pošalje u `check_cycle`, ranije ubačena suprotna blocking grana dovoljna je za lažnu detekciju ciklusa.

### T3 — impact `WorkflowLedgerService.append_test_result`

Kontrola:

- `ToolSearch`: 1;
- Graft MCP: 2 poziva;
- `Grep`: 15;
- `Read`: 9;
- ukupno 28 modelskih turnova.

Puna instalacija:

- `ToolSearch`: 1;
- `graft_trace_calls`: 2;
- `graft_find_all`: 5;
- `graft_find_code`: 3;
- `Read`: 1;
- ukupno 13 modelskih turnova.

Obje varijante su pronašle:

- direktni production caller `SessionCompletionService.complete_session`;
- SAVEPOINT/exception boundary;
- composition-root `_make_complete_session/_complete` background closure;
- činjenicu da stvarni poziv `app.state.complete_session` nije potvrđen u pregledanom production toku;
- direktne ledger testove, completion unit testove i širi E2E tok;
- obaveznu `UNKNOWN` kvalifikaciju umjesto zaključka “zero callers = safe”.

Ovdje je Graft skill promijenio strategiju: puna sesija je ostala na graph/exhaustive retrievalu i otvorila samo jedan source region, dok je kontrola nakon dva Graft pokušaja prešla na opsežno ručno grep/read obilazak. To je najveća potvrđena korist pune instalacije.

### T4 — veliki `overview_skeleton.py`

Kontrola:

- `Grep`: 1;
- `Read`: 1.

Puna instalacija:

- `ToolSearch`: 1;
- `graft_file_api`: 1;
- `graft_find_code`: 1;
- `Read`: 1.

Obje varijante su pravilno izdvojile top-level helper funkcije, widget klase i minimalne `MainWindow`/`Sidebar` regije za build, zamjenu stranica i navigation routing. Puna instalacija je dodala retrieval prije istog jednog source read-a, pa je bila skuplja bez mjerljivog dobitka u tačnosti.

Puna varijanta je korisno upozorila da Graft vraća i staru kopiju iz `review_bundles/`; to potvrđuje postojeći noise problem i potrebu za pažljivim ignore pravilima koja neće sakriti stvarno relevantne artefakte.

## Hooks: lokalni funkcionalni test

Svi hook tipovi iz pune instalacije su zasebno pozvani sintetičkim Claude hook payloadom.

| Hook/površina | Rezultat | Izmjereno vrijeme |
|---|---|---:|
| `SessionStart` | PASS; ubacio Graft orijentaciju i repo mapu | 0,278 s interno |
| `UserPromptSubmit` | PASS; pokrenuo pointers-only retrieval | 0,865 s interno |
| `PostToolUse` edit | PASS; provjerio/sinhronizovao dirty graph | 4,452 s interno |
| `Statusline` sintetički | PASS; prikazao graph sync i context | 0,096 s interno |
| `Statusline` nad stvarnom T3 sesijom | PASS; `3094 nodes / 6627 edges`, `✓ synced`, `ctx 42%` | 0,369 s procesno vrijeme |

Tokom tri validne pune sesije hookovi su u modelsku sesiju vratili ukupno 10.108 znakova dodatnog contexta:

- T1: 3.286 znakova;
- T3: 3.536 znakova;
- T4: 3.286 znakova.

Broj opaženih hook odgovora po punoj sesiji:

- T1: SessionStart 1, UserPromptSubmit 1, PostToolUse 2, Stop 1;
- T3: SessionStart 1, UserPromptSubmit 1, PostToolUse 1, Stop 1;
- T4: SessionStart 1, UserPromptSubmit 1, PostToolUse 1, Stop 1.

Najveći lokalni latency rizik je edit hook od približno 4,45 s po edit događaju. To nije izmjereno u read-only A/B runovima jer su edit alati bili zabranjeni.

## Statusline nalaz

Statusline radi i render je jeftin u odnosu na modelsku sesiju. Međutim, za stvarnu T3 sesiju:

```json
{
  "graftReads": 0,
  "sourceReads": 1,
  "savedTokens": 0,
  "injectedPointers": [
    "tests/integration/test_workflow_ledger_phase3b.py:L349-L366"
  ]
}
```

Claude finalni odgovor iste sesije naveo je `graft saved ~135k tokens this turn, 7 calls`, dok je `graft stats --json` prikazao nula Graft readova i nula saved tokena. Statusline zato nije prikazao uštedu.

Zaključak: statusline je funkcionalan kao sync/context indikator, ali njegova saved-token metrika nije potvrđena kao pouzdana za MCP pozive u ovom setupu. Ne treba je koristiti za evaluaciju ili billing.

## Telemetrija

Telemetrija je ostavljena uključena na eksplicitni zahtjev korisnika:

```text
telemetry: on — anonymous, aggregate-only
endpoint: https://events.nanonets.com
queued: 95 events waiting for the next daily flush
```

`graft telemetry debug` je korišten za lokalni pregled; prema CLI poruci ta komanda ništa ne šalje. U redu je bilo 95 događaja, od čega 32 od početka završnog benchmark prozora. Za dva benchmark repo ID-a zabilježeno je:

- puna instalacija: 30 query događaja — ask 14, grep 10, callers 5, skeleton 1;
- kontrola: 2 query događaja — ask 1, skeleton 1.

Pregledani telemetrijski payload sadrži agregatna polja kao što su Graft verzija, OS/arch, anonimizirani `repo_id`, command/surface i host. Ne sadrži Claude `input_tokens`, cache tokene, output tokene ni `total_cost_usd`.

Zato postoje dvije različite stvari:

1. Graft telemetrija — anonimni agregat korištenja alata;
2. Claude `stream-json` usage — autoritativni per-test tokeni i cijena korišteni u ovom izvještaju.

Telemetrijski red nije očišćen niti forsirano poslan. Ostavljen je uključen kako je korisnik tražio.

## Nevalidni i infrastrukturno kontaminirani pokušaji

Ovi runovi nisu uključeni u glavnu A/B tabelu:

1. Run bez `--verbose` — Claude CLI ga je odbio prije izvršenja.
2. Run u kojem `Task/Agent` nisu bili zabranjeni — puna varijanta je pokrenula subagenta, pa par nije bio uporediv.
3. Run u `dontAsk` režimu — full Graft MCP poziv je odbijen jer benchmark worktree nije trusted; agent je prešao na Read/Grep.
4. Prvi validno konfigurisan full T3 pokušaj — Anthropic je vratio ponovljene `529 overloaded`, zatim `500`; run je završio greškom poslije prijavljenih 271.355 tokena model usagea i $0,2474. Nije bodovan. Uspješni fresh retry je korišten u tabeli.

Neuspjeli T3 je važan troškovni nalaz: API retry/failure može potrošiti novac i tokene bez upotrebljivog rezultata. To nije Graft-vs-hooks performansna razlika, nego vanjska infrastrukturna varijansa.

## Dodatni nalazi

### Puna instalacija nije čista izolacija samo tri tražene komponente

`graft init` je uz Claude fajlove automatski dodao Windsurf i OpenCode wiring. Za FlowOS daily setup treba eksplicitno odlučiti koji hostovi su stvarno potrebni; automatski multi-host artefakti povećavaju repo diff i maintenance površinu.

### Skill može pomoći i odmoći

Skill je na T3 uspješno zadržao agenta na graph-first/exhaustive toku. Na T1 i T4 je proizveo dodatne MCP korake prije source read-a koji je agent ionako uradio. Fiksno pravilo “Graft-first za svaki zadatak” nije optimalno.

### Hook injection ima fiksni porez

SessionStart i UserPromptSubmit zajedno dodaju nekoliko hiljada znakova u svaki fresh run. Taj porez se bolje amortizuje na širokom impact zadatku nego na kratkom locate/file zadatku.

### `review_bundles/` ostaje izvor noisea

Graft je u rezultatima nalazio historijske kopije iz review bundleova. Agent ih je u finalnim odgovorima prepoznao, ali trajni setup treba razmotriti precizan ignore samo ako neće sakriti relevantne dokazne artefakte.

### Telemetrija nije token-meter

Čak i uključena telemetrija ne daje per-test stvarnu potrošnju modela. Za FlowOS observability treba parsirati native usage događaje svakog agent adaptera i čuvati jasno odvojene input/cache/output/cost metrike.

## Odluka po komponenti

| Komponenta | Preporuka | Dokaz |
|---|---|---|
| Graft CLI/MCP | **KEEP** | potreban za graph retrieval; raniji benchmark i ovaj impact test pokazuju vrijednost |
| Graft skill globalno/uvijek | **NE još** | +44–47% tokena na dva lokalna zadatka; korist koncentrisana na široki impact |
| Graft skill ciljano | **DA, eksperimentalno** | T3: -61,6% tokena, -54,0% cijene i manje ručnog source obilaska |
| SessionStart hook | **OPTIONAL** | koristan onboarding/mapa, ali fiksni context porez po sesiji |
| UserPromptSubmit hook | **OPTIONAL / ciljano** | može usmjeriti retrieval, ali dodaje latency/context i duplira samostalni MCP izbor |
| PostToolUse edit hook | **NE po defaultu** | lokalno približno 4,45 s po edit događaju; nije dokazana proporcionalna korist |
| Tool-savings hook | **NE kao izvor metrike** | `graft stats` nije evidentirao stvarne MCP saved tokene u T3 |
| Stop sync hook | **OPTIONAL** | koristan za svjež graph poslije edit sesije; read-only test ne dokazuje daily overhead |
| Statusline | **OPTIONAL** | render radi i jeftin je; sync/context koristan, saved-token dio nepouzdan |
| Graft telemetry | **ON po odluci korisnika** | agregatna i anonimna prema pregledanom payloadu; ne mjeri model token usage |

## Preporučeni sljedeći eksperiment

Prije trajnog uključivanja skilla/hookova napraviti veći ponovljeni test:

- najmanje 10 runova po kategoriji: locate, impact, large-file, debug i edit;
- randomizovati redoslijed full/control runova;
- odvojeno testirati `MCP only`, `MCP + skill`, `MCP + hooks` i `MCP + skill + hooks`;
- dodati edit workload da se izmjeri PostToolUse overhead;
- score odgovora raditi blind prema unaprijed definisanom goldu;
- per-run bilježiti native token kategorije, cijenu, tool pozive, hook context znakove i API retry događaje.

Ovaj 2×2 faktorski minimum je potreban da se razdvoji efekat skilla od efekta hookova; trenutni test poredi kompletan paket protiv MCP-only kontrole.

## Cleanup i završno stanje

- Puna instalacija je uklonjena sa `graft uninstall -y --no-global`; globalne postavke nisu dirane.
- Full benchmark worktree je poslije uninstall-a zadržao samo Graftovu praznu/nepraćenu `.ignore` datoteku.
- Baseline worktree je zadržao benchmark `.mcp.json` i `graft/` cache. Pokušaj dodatnog destruktivnog cleanup-a nije izvršen jer retention/approval pravila nisu dala novu potvrdu za brisanje.
- Worktreeji nisu obrisani; retention je očuvan.
- Globalni Graft CLI i uključena telemetrija ostaju.
- Nije mijenjan FlowOS source. Benchmark je prvobitno završen bez commita; korisnik je naknadno zatražio dokumentacijski commit i push.
- Globalni config hashovi ostali su identični:

| Fajl | SHA-256 |
|---|---|
| `C:\Users\38765\.codex\config.toml` | `2EBB7E609169B4F9966DCD53E9F4EFB0D30E7A9E47F88E06CB427A3F50636C90` |
| `C:\Users\38765\.codex\hooks.json` | `5B07B5525D04976C0DF624C5DE38C9DD85C516E07473C7BFEEDF604408AFCC33` |
| `C:\Users\38765\.claude\settings.json` | `18645F09685048182D976FD5A4F9AF9923492DCC6051D1E412EF27EE57A4A811` |

## Konačni zaključak

Puna Graft instalacija nije univerzalna optimizacija. Ona je u ovom uzorku bila odlična za široki impact task, ali je povećala potrošnju i vrijeme na dva jednostavnija zadatka. Najrazumniji FlowOS setup trenutno je:

```text
Graft MCP uvijek dostupan
+ kratko repo pravilo ZERO CALLERS = UNKNOWN
+ skill/hooks samo ciljano ili iza novog većeg eksperimenta
+ native agent usage kao jedini per-test token meter
```
