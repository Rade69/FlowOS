# Graft hooks/skill/statusline benchmark

## Datum

2026-09-09

## Agent / model / sesija

Codex, primarna sesija; benchmark child sesije: Claude Code 2.1.236, `claude-sonnet-5`, effort medium.

## Scope

Read-only A/B benchmark pune Graft repo-local Claude instalacije protiv Graft MCP kontrole bez Graft skilla, hookova i statuslinea. Uključeni su native Claude token usage, Graft telemetrijski status, lokalni hook/statusline test i cleanup.

## Task contract / acceptance kriteriji

- isti FlowOS commit i isti prompt po A/B paru;
- isti model, effort i Graft MCP pristup;
- bez mutirajućih, shell, web i subagent alata;
- fresh sessions i native usage po runu;
- odvojiti nevalidne/infrastrukturno kontaminirane runove;
- dokumentovati sve nalaze u `docs/` artefaktu;
- ne mijenjati FlowOS source niti globalne agent konfiguracije.

## GitNexus impact ili ručni blast radius

Nisu mijenjani simboli ni produkcijski ugovori. Blast radius je ograničen na dva nova dokumentacijska fajla u glavnom treeju i benchmark-only repo-local artefakte u odvojenim worktreejima. GitNexus impact nad simbolom nije primjenjiv.

## Reprodukcija prije izmjene

Nije bugfix. Benchmark je reprodukovan kroz tri validna A/B para i zasebne sintetičke hook/statusline pozive.

## Šta je urađeno

- napravljena puna Graft 0.16.0 repo-local instalacija sa MCP, skillom, svim Claude hookovima i statuslineom;
- napravljena MCP-only kontrola bez Graft hooks/skilla/statuslinea;
- izvršeni T1 locate, T3 impact i T4 large-file A/B testovi;
- zabilježeni input, cache-create, cache-read, output, cijena, trajanje, turns i tool pozivi;
- provjereni SessionStart, UserPromptSubmit, PostToolUse edit, Stop i statusline;
- potvrđena uključena Graft telemetrija i pregledan tačan queued payload bez slanja debug komandom;
- dokumentovani nevalidni runovi i Anthropic 529/500 run;
- full instalacija uklonjena Graftovim `--no-global` inverse-uninstall postupkom;
- provjereni hashovi globalnih Codex/Claude konfiguracija.

## Zašto je urađeno

Prethodni MCP benchmark nije mjerio dodatni prompt, latency i ponašajni uticaj pune Graft instalacije. Korisnik je tražio direktno poređenje i per-test token telemetriju.

## Kako je urađeno

Claude Code je pokretan sa `--verbose --output-format stream-json --include-hook-events --no-session-persistence`, uz isti model i read-only alatni scope. Token volume je računat kao suma četiri native usage kategorije; Graft self-reported savings nije tretiran kao stvarna potrošnja.

## Izmijenjeni fajlovi i ponašanje

- `docs/graft-hooks-skill-statusline-benchmark-2026-09-09.md` — puni rezultat, metod, metrike, nalazi i preporuka;
- `agent_reports/2026-09-09_graft-hooks-skill-statusline-benchmark.md` — ovaj handoff.

Nema promjene runtime ponašanja FlowOS-a.

## Šta nije dirano

- FlowOS produkcijski kod i testovi;
- postojeće korisničke izmjene u `AGENTS.md`, `CLAUDE.md`, planu i drugim untracked dokumentima;
- globalni Codex/Claude config;
- postojeći GitNexus setup;
- Graft globalni CLI i uključena telemetrija.

## Verifikacija i stvarni rezultat

- 3/3 validna A/B para završila exit codeom 0;
- obje varijante dale su funkcionalno tačne odgovore na sva tri zadatka;
- puna instalacija ukupno: 995.648 token volume, $0,8568, 124,396 s Claude trajanja;
- kontrola ukupno: 1.605.418 token volume, $1,1561, 131,751 s;
- full razlika: -38,0% tokena, -25,9% cijene, -5,6% trajanja;
- T1 i T4 su bili skuplji sa full instalacijom; T3 je bio znatno jeftiniji;
- telemetrija: ON, 95 queued događaja; pregledani payload nema native model token usage;
- full statusline renderovao je graph/sync/context, ali `graft stats` je pokazao `savedTokens: 0` uprkos self-reportu od približno 135k;
- globalni config SHA-256 vrijednosti identične su početnim vrijednostima;
- full worktree nakon uninstall-a: samo `?? .ignore`;
- baseline worktree: `?? .mcp.json`, `?? graft/`.

Pytest/lint/typecheck nisu pokretani jer produkcijski kod nije mijenjan. Izvršeni benchmark je relevantni performansni dokaz.

## Nezavisna provjera

Nije rađen zaseban nezavisni checker nad novim dokumentom; zadatak ne mijenja produkcijski kod. Tačnost ključnih odgovora poređena je sa gold nalazima iz prethodnog benchmark artefakta i stvarnim source putanjama koje su child sesije otvorile.

## Pronađeni problemi

- Graft full instalacija povećava tokene i vrijeme na kratkim lokalnim zadacima;
- edit hook je lokalno trajao približno 4,45 s;
- statusline/session stats nisu uhvatili MCP saved-token podatke;
- `review_bundles/` stvara retrieval noise;
- `graft init` dodaje i Windsurf/OpenCode wiring, ne samo Claude artefakte;
- jedan full T3 run je potrošio 271.355 tokena i $0,2474 prije Anthropic 529/500 završetka;
- uninstall je ostavio `.ignore`;
- baseline benchmark artefakti nisu uklonjeni bez dodatne cleanup potvrde.

## Odbačene opcije

- **Proglasiti full instalaciju univerzalnim pobjednikom:** odbačeno jer su T1 i T4 imali 44–47% veći token volume; ponovo otvoriti poslije većeg faktorskog testa.
- **Koristiti Graft saved-token tekst kao glavnu metriku:** odbačeno jer se ne slaže sa native usageom ni `graft stats`; ponovo otvoriti ako Graft dokumentuje i popravi MCP accounting.
- **Uključiti nevalidne runove u prosjek:** odbačeno zbog subagenta, permission deniala i API greške; koristiti samo kao operativne nalaze.
- **Forsirano obrisati benchmark worktree artefakte:** odbačeno zbog retention/approval pravila; ponovo otvoriti uz eksplicitnu korisničku potvrdu.

## Konflikti/kontradiktorni izvori

Claude finalni Graft self-report za T3 naveo je približno 135k saved tokena, dok je `graft stats --json` za istu session ID vrijednost vratio `graftReads: 0` i `savedTokens: 0`. Native Claude usage je tretiran kao autoritativan za stvarnu potrošnju.

## Commitovi

Korisnik je nakon završetka benchmarka zatražio commit i push. Ovaj report i glavni benchmark dokument ulaze u zaseban dokumentacijski commit; commit hash se evidentira u Git istoriji.

## Rizici i ograničenja

- samo tri task kategorije i jedan validni run po ćeliji;
- API cache stanje i vanjska Anthropic latencija nisu potpuno kontrolisani;
- full paket ne razdvaja individualni efekat skilla od hookova;
- token volume nije isto što i obračunski broj tokena;
- nema edit-workload A/B testa;
- correctness ocjena nije bila blind nezavisna evaluacija.

## Potreban follow-up

- 2×2 ili 2×4 ponovljeni eksperiment koji odvojeno testira skill i hooks;
- edit workload i hook latency distribucija;
- precizno ignore pravilo za `review_bundles/`;
- native adapter usage ingestion za FlowOS observability;
- eventualni cleanup zadržanih benchmark artefakata nakon korisničke potvrde.

## Potrebna korisnička potvrda

Potrebna je samo ako korisnik želi trajno uključiti neki Graft hook/skill ili ukloniti preostale benchmark artefakte/worktreeje.
