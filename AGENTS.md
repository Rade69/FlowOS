# AGENTS.md — FlowOS

Ovaj fajl važi za sve agente koji rade u ovom repozitoriju, uključujući Codex, Claude Code, pi i druge CLI/API agente. Za jezik, detaljnu proceduru rada, agent_reports format, Git pravila i memorijski model vidi [CLAUDE.md](./CLAUDE.md). Ne duplirati detalje iz tog fajla bez potrebe.

## Naziv i cilj projekta

FlowOS je lokalni lični operativni sistem za:

- praćenje i koordinaciju paralelnih agentskih sesija;
- detekciju konflikata u dijeljenim Git working treejima;
- pouzdanu atribuciju rada kroz Git i worktree izolaciju;
- upravljanje projektima, zadacima, odlukama i izvještajima;
- kasniju nadogradnju modulima za Managed Execution, observability, durable izvršavanje i verifier tokove.

Glavni arhitektonski i fazni plan je [FlowOS-novi-detaljan-plan-PySide6.md](./FlowOS-novi-detaljan-plan-PySide6.md). Originalni plan [FlowOS-kompletan-plan.md](./FlowOS-kompletan-plan.md) ostaje kao referenca za backend arhitekturu. Pročitati relevantne dijelove oba plana prije implementacije.

## Arhitektonska pravila — obavezna

- **PySide6 + Qt Widgets je GUI sloj.** Electron, React, Node.js, npm, pnpm, yarn i QML su zabranjeni — nisu dio aplikacije ni build procesa.
- Python 3.12 + FastAPI backend (`flowos-service.exe`) je stalni lokalni servis i vlasnik domena, persistencea, `watchdog` watchera, Git/worktree koordinacije, agentskih adaptera i budućih izvršnih modula. Sluša samo na 127.0.0.1. Mora nastaviti pratiti sesije kada je GUI zatvoren.
- GUI proces (`flowos-gui.exe`) je PySide6 Qt Widgets aplikacija. Arhitektura GUI-ja je View → Controller → Services — View ne sme direktno pozivati Services, Controller ne sme pristupati bazi/Git-u/subprocess-u. **Ne dodavati poslovnu, agentsku, storage, watcher, Git ili AI logiku u GUI proces.**
- Sistem počinje kao modularni monolit. Ne uvoditi mikroservise, broker, PostgreSQL, distribuirane workere ili kontejnere prije faze i dokazane potrebe iz plana.
- `FlowOS Core` ne smije zavisiti od konkretnog agentskog adaptera.
- Konkretne CLI/API razlike pripadaju isključivo adapterima i capability ugovorima.
- Wrapper je primarni način registracije sesija; ručni `EXTERNAL_TRACKED` režim ostaje podržan fallback. Redoslijed adaptera je Claude Code → pi → Codex → `GenericCliAdapter`.
- Posmatrani filesystem/Git događaji su primarni izvor aktivnosti. Ownership/path glob može biti hint, ne izmišljena činjenica.
- Git je autoritet za kod. FlowOS zapis nije zamjena za status, diff, commit i rezultate verifikacije.
- Pouzdana atribucija paralelne implementacije zahtijeva poseban worktree. Jedan writable worktree smije imati najviše jednu writer sesiju.
- Managed Execution, Observability, Durable Job Engine i verifier tok ostaju zasebni, opcionalni moduli koji se dodaju samo redoslijedom i pod gateovima iz plana.

## Ne raditi

- Ne izlagati modelu proizvoljni shell execution alat.
- Ne tretirati prompt kao sigurnosnu granicu.
- Ne dodavati cloud telemetriju niti slati projektne podatke van računara bez eksplicitne korisničke odluke.
- Ne čuvati tajne u bazi, logovima, artefaktima ili repozitoriju.
- Ne tvrditi da `EXTERNAL_TRACKED` sesija podržava process control, tačan heartbeat ili recovery koje FlowOS stvarno nema.
- Ne prikazivati heurističku atribuciju kao sigurnu činjenicu.
- Ne uvoditi automatski merge; integracija je korisnička akcija.
- Ne uvoditi model voting kao dokaz kvaliteta.
- Ne snimati privatno rezonovanje modela niti svaki token.
- Ne graditi narednu fazu dok acceptance kriterij i vertikalni eksperiment prethodne faze nisu dokazani.
- Ne brisati napuštene worktreeje, artefakte ili djelimičan rad prije retention perioda i korisničkog pregleda.
- Ne commitovati API ključeve, `.env*` fajlove s tajnama, lokalne baze, logove, build output, virtualna okruženja ili korisničke artefakte.

## Namjerno odgođeno — ne uvoditi prije uslova iz plana

- Ne uvoditi `WorkerLease`, poseban heartbeat ni fencing generation na jednom računaru. Lokalni tok koristi PID, Windows Job Object i startup recovery; lease/fencing pripadaju tek fazi 10 s udaljenim workerima.
- Ne uvoditi Checkpoint tabelu. Lokalni checkpoint je commit SHA + `handoff.md`, zapisan kao `CHECKPOINT` event.
- Ne graditi ownership manifeste kao izvor istine, hash-check čitanje→upis, `ControlRequest` model, kanonski approval hash ili opštu risk matricu bez uslova povratka iz §21 plana.
- Ne obećavati cooperative pause/resume procesa dok konkretan adapter to stvarno ne podržava. Faza 8 pause znači da se ne pokreće sljedeći korak.
- Ne uvoditi AgentSpan kao opšti durable backend za eksterne CLI procese. Može se kasnije evaluirati samo za pi/SDK tok ako se pojavi stvarna potreba.
- Ne uvoditi OpenTelemetry izvoz dok ne postoji konkretan vanjski konzument.

## Prije rada i prije svake izmjene

- Pokrenuti `git status --short --branch` i pregledati posljednje commitove.
- Pretpostaviti da isti filesystem mogu dijeliti Claude Code, Codex, pi i korisnik. Sve postojeće izmjene pripadaju njima dok se ne dokaže suprotno.
- Ne vraćati, prepisivati, premještati ili uključivati tuđe necommitovane izmjene u vlastiti commit.
- Pregledati modul koji se mijenja, njegove pozivaoce, ulaze/izlaze, testove i relevantne ugovore.
- Ako je GitNexus indeksiran za ovaj repo, obavezno pokrenuti upstream impact analizu prije izmjene funkcije, klase ili metode i prijaviti direct callers, procese i nivo rizika korisniku.
- Ako GitNexus nije dostupan ili repo još nije indeksiran, ručno pronaći reference i eksplicitno prijaviti blast radius prije izmjene simbola.
- Ako je rizik HIGH ili CRITICAL, upozoriti korisnika prije editovanja.
- Za rename/refactor koristiti graph-aware rename kada je dostupan; ne raditi slijepi globalni find-and-replace.
- U dijeljenom treeju ponovo pročitati svaki fajl neposredno prije izmjene, naročito aktivne collision fajlove. Ne oslanjati se na keširani sadržaj.
- Provjeriti relevantnu fazu u [FlowOS-kompletan-plan.md](./FlowOS-kompletan-plan.md) i stvarno stanje koda prije tvrdnje da je nešto završeno.

## Pravila implementacije

- Raditi fazu po fazu i u malim vertikalnim cjelinama.
- Svaka promjena mora imati jasan task contract: cilj, scope, out-of-scope, acceptance kriterije, rizike i plan verifikacije.
- Preferirati deterministički kod nad modelskim pozivom.
- Nivo 1 jeftini model koristiti samo za klasifikaciju, ekstrakciju i sažetke; jaki agent i durable workflow koristiti samo kada složenost to opravdava.
- SQLite + WAL + Alembic ostaju zadani storage do uslova faze 10.
- Wrapper mora ostati brz i ne smije blokirati korisnikov rad kada backend privremeno nije dostupan.
- Watcher upozorenja moraju biti zasnovana na stvarnim signalima, imati kontrolisan šum i jasno prikazivati confidence atribucije.
- Capability ugovor adaptera počinje samo sa `can_launch`, `can_stream_events`, `can_report_usage`, `can_cancel` i `can_use_worktree`; nove capabilityje dodavati tek kada ih ciljani alat stvarno podržava.
- Checkpoint u lokalnom durable toku je commit + `handoff.md`, ne obećanje nastavka internog rezonovanja.
- Verifier radi read-only i svaki nalaz mora sadržati dokaz ili reprodukciju. Najviše dvije review runde po jobu.
- Vanjske ili nepovratne akcije koriste approval, idempotency i side-effect barrier; nejasan ishod ide u `BLOCKED`, ne u slijepi retry.
- Kod fajl koji se kreira ili značajno mijenja mora na vrhu imati kratak komentar/docstring koji objašnjava svrhu i mjesto u sistemu.

## Prije commita

- Ponovo provjeriti `git status` i puni relevantni diff.
- Pokrenuti relevantne unit, integracijske i end-to-end testove, lint, typecheck i build.
- Kada postoji `scripts/verify.py`, koristiti ga kao standardnu završnu ulaznu tačku.
- Za durability/recovery tvrdnje pokrenuti fault-injection testove propisane planom.
- Ako je GitNexus dostupan, pokrenuti `gitnexus_detect_changes()` prije commita i provjeriti pogođene simbole i execution flowove.
- Napisati `agent_reports/` izvještaj prema [CLAUDE.md](./CLAUDE.md).
- Ažurirati implementacijski tracker u istom commitu kao kod kada tracker bude uveden. Arhitektonski plan i stvarno stanje koda ne smiju divergirati.
- Ne praviti commit bez eksplicitnog korisničkog zahtjeva.
- Nikada ne preskakati Git hookove.

## Predaja rada

Korisniku sažeti:

- koje module i fajlove je agent izmijenio;
- kakvo se ponašanje promijenilo;
- blast radius i otvorene rizike;
- koje su provjere pokrenute i njihov rezultat;
- šta nije dirano;
- da li je potrebna korisnička odluka ili integracija worktreeja.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **FlowOS** (12027 symbols, 17981 relationships, 203 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/FlowOS/context` | Codebase overview, check index freshness |
| `gitnexus://repo/FlowOS/clusters` | All functional areas |
| `gitnexus://repo/FlowOS/processes` | All execution flows |
| `gitnexus://repo/FlowOS/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
