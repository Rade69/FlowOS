# FlowOS — tehnički feasibility izvještaj za praćenje Claude, Codex, Pi i Crush agenata

**Datum provjere:** 2026-08-10  
**Status:** Feasibility spike / tehnička provjera prije dalje arhitekture  
**Cilj:** Utvrditi da li FlowOS može dovoljno pouzdano pratiti postojeći radni tok u kojem se Claude i Codex uglavnom koriste kroz VSCode, a Pi i Crush kroz terminal/CLI, bez zahtjeva da FlowOS sam pokreće ili kontroliše agente.

---

## 1. Izvršni zaključak

### Konačna ocjena: **GO — osnovna ideja FlowOS-a je tehnički ostvariva**

Najvažniji zaključak ovog istraživanja je da **nije potrebno screen-scrapeovati terminal niti uvoditi interni LLM da bi FlowOS pratio agentski rad**.

Tri od četiri alata imaju dovoljno strukturiranih integracionih tačaka da FlowOS može dobiti pouzdane događaje:

- **Claude Code:** vrlo jaka i eksplicitno podržana hook telemetrija, uključujući VSCode ekstenziju.
- **Pi:** vrlo jaka extension/event telemetrija u normalnom interaktivnom terminalskom radu; dodatno ima JSON/RPC režime za eventualni budući managed execution.
- **Codex:** jaka hook i app-server infrastruktura; za tačno ponašanje hookova u korisnikovoj konkretnoj VSCode ekstenziji treba uraditi mali lokalni PoC prije nego što se integracija proglasi potpuno potvrđenom.
- **Crush:** u standardnom terminalskom režimu trenutno ima samo `PreToolUse` hook i zato je praćenje djelimično; ali eksperimentalni client/server režim već ima bogat REST/SSE API sa sessionima, message/tool događajima, modelom, greškama i autoritativnim `RunComplete` događajem.

Najvažnija arhitektonska posljedica:

> **FlowOS ne smije zavisiti od toga da svi agenti nude isti nivo telemetrije.**

FlowOS treba imati dva sloja:

1. **Univerzalni project-observation sloj** koji radi za svaki projekat:
   - Git stanje i commitovi;
   - filesystem promjene;
   - `agent_reports`;
   - korisničke odluke;
   - učitani plan i taskovi.

2. **Agent-specifični observation adapteri** koji dodaju bogatiju telemetriju kada je agent podržava:
   - Claude hooks;
   - Codex hooks;
   - Pi extension events;
   - Crush hooks ili, kasnije, client/server SSE.

Ako agent-specifični adapter privremeno ne radi, FlowOS i dalje funkcioniše — samo je detaljnost praćenja manja.

---

## 2. Pitanje koje je trebalo dokazati prije dalje arhitekture

Provjerena je sljedeća matrica:

| Sposobnost | Claude | Codex | Pi | Crush |
|---|---|---|---|---|
| Session detect | ? | ? | ? | ? |
| Project / cwd | ? | ? | ? | ? |
| Activity events | ? | ? | ? | ? |
| Errors / rate limit | ? | ? | ? | ? |
| Report linkage | ? | ? | ? | ? |
| Pouzdanost | ? | ? | ? | ? |

Istraživanje je namjerno urađeno prema **trenutnom stvarnom workflowu korisnika**, a ne prema hipotetičkom FlowOS-managed CLI sistemu:

- Claude → VSCode ekstenzija
- Codex → VSCode ekstenzija
- Pi → terminal/CLI
- Crush → terminal/CLI

---

## 3. Legenda ocjena

- **✅ DIREKTNO** — postoji dokumentovan, strukturiran signal koji FlowOS može koristiti bez semantičkog nagađanja.
- **🟡 DJELIMIČNO** — dio informacije postoji, ali nije potpun ili zahtijeva rezervni mehanizam / lokalnu provjeru.
- **⚪ FALLBACK** — FlowOS može dobiti informaciju preko univerzalnog Git/filesystem/report sloja, ali ne direktno od agenta.
- **❌ NEMA** — trenutno nije pronađen pouzdan tehnički signal.

Pouzdanost:

- **VRLO VISOKA** — dokumentovan javni integracioni mehanizam koji odgovara našem use-caseu.
- **VISOKA** — strukturirana integracija postoji uz mali broj ograničenja.
- **SREDNJE VISOKA** — tehnički je dobro podržano, ali postoji jedna važna neprovjerena pretpostavka.
- **SREDNJA** — dovoljno za korištenje uz fallback sloj.
- **NISKA** — nije preporučljivo graditi ključni FlowOS workflow na toj integraciji.

---

# 4. Konačna matrica — sadašnji korisnikov workflow

| Sposobnost | Claude / VSCode | Codex / VSCode | Pi / Terminal | Crush / Terminal |
|---|---|---|---|---|
| **Session detect** | ✅ DIREKTNO | 🟡 Vrlo vjerovatno direktno; lokalni PoC | ✅ DIREKTNO | 🟡 Prvi tool call daje session ID |
| **Project / cwd** | ✅ DIREKTNO | ✅ DIREKTNO kroz hook payload | ✅ DIREKTNO | ✅ DIREKTNO kroz hook |
| **Activity events** | ✅ VRLO BOGATO | ✅ BOGATO za hook-obuhvaćene aktivnosti | ✅ VRLO BOGATO | 🟡 Samo `PreToolUse` u normalnom režimu |
| **Errors / rate limit** | ✅ Strukturirani `StopFailure` | 🟡 Hook-only slabiji; app-server vrlo bogat | ✅ HTTP status + retry/tool error events | 🟡 Default: log/fallback; client-server mnogo bolji |
| **Aktivni model** | ✅ `SessionStart.model` | ✅ hook model / app-server | ✅ `model_select` | 🟡 Hook ga ne daje; client-server ga daje |
| **Report linkage** | ✅ session_id + cwd | ✅ session_id + cwd | ✅ session ID/file + cwd | ✅ session_id + cwd nakon prvog hooka |
| **Turn/run completion signal** | ✅ `Stop` / `StopFailure` | ✅ `Stop`; app-server `turn/completed` | ✅ `agent_end` / `turn_end` | 🟡 Default nema; client-server `RunComplete` |
| **Pouzdanost za FlowOS v1** | **VRLO VISOKA** | **SREDNJE VISOKA** | **VRLO VISOKA** | **SREDNJA** |
| **GO/NO-GO** | **GO** | **GO uz PoC** | **GO** | **GO kao parcijalni adapter** |

---

# 5. Claude Code — detaljna provjera

## 5.1. Najvažniji nalaz

Claude Code je trenutno **najčistiji kandidat za FlowOS observer integraciju**.

Anthropic eksplicitno navodi da VSCode ekstenzija i CLI dijele Claude Code konfiguraciju u:

```text
~/.claude/settings.json
```

i da se ta zajednička konfiguracija koristi za:

- dozvoljene komande;
- environment varijable;
- hooks;
- MCP servere.

To je presudno za FlowOS zato što korisnik **ne mora prestati koristiti Claude u VSCode-u**.

FlowOS može dodati user-level Claude hook konfiguraciju, a Claude se i dalje koristi u postojećem VSCode panelu.

---

## 5.2. Session detect — ✅ DIREKTNO

Claude ima:

- `SessionStart`
- `SessionEnd`

`SessionStart` se aktivira za:

- novu sesiju (`startup`);
- resume;
- clear;
- compact.

Payload sadrži najmanje:

```text
session_id
transcript_path
cwd
source
model
```

FlowOS time može deterministički evidentirati:

```text
CLAUDE_SESSION_STARTED
session_id = ...
project_root = resolved from cwd
model = ...
source = startup/resume/...
```

Nema potrebe za PID heuristikom niti čitanjem VSCode UI-a.

### Važna napomena

`SessionStart` poslije `compact` ne treba tretirati kao novu FlowOS sesiju. Isti `session_id` treba prepoznati kao nastavak postojećeg agentskog konteksta.

---

## 5.3. Project / cwd — ✅ DIREKTNO

Common Claude hook payload sadrži:

```text
cwd
session_id
```

Dodatno postoji poseban `CwdChanged` hook sa:

```text
old_cwd
new_cwd
```

To znači da FlowOS može:

1. primiti hook;
2. normalizovati `cwd`;
3. pronaći najbliži registrovani FlowOS project root;
4. povezati sesiju sa projektom;
5. pratiti promjenu direktorijuma tokom rada.

To je mnogo pouzdanije od pokušaja zaključivanja projekta na osnovu imena VSCode prozora.

---

## 5.4. Activity events — ✅ VRLO BOGATO

Claude nudi lifecycle događaje na tri nivoa.

### Session nivo

- `SessionStart`
- `SessionEnd`
- `CwdChanged`
- `FileChanged`
- `ConfigChange`
- `InstructionsLoaded`

### Turn nivo

- `UserPromptSubmit`
- `Stop`
- `StopFailure`

### Tool nivo

- `PreToolUse`
- `PermissionRequest`
- `PermissionDenied`
- `PostToolUse`
- `PostToolUseFailure`
- `PostToolBatch`

Dodatno:

- `SubagentStart`
- `SubagentStop`
- `TaskCreated`
- `TaskCompleted`
- worktree događaji

Za FlowOS v1 nije potrebno slati svaki mogući event. Dovoljna početna podskupina je:

```text
SessionStart
UserPromptSubmit        [opciono zbog privatnosti]
PreToolUse
PostToolUse
PostToolUseFailure
Stop
StopFailure
CwdChanged
SessionEnd
```

### Šta FlowOS time može prikazati

Primjer:

```text
07:11 Claude session started
07:12 Bash started: pytest tests/test_x.py
07:13 Bash completed
07:15 Edit/Write activity
07:17 Claude turn stopped
```

FlowOS ne mora tumačiti sadržaj; bilježi strukturirane događaje.

---

## 5.5. Errors / availability — ✅ DIREKTNO I STRUKTURIRANO

Claude je ovdje posebno dobar.

`StopFailure` se aktivira kada turn završi zbog API greške i dokumentovano razlikuje:

```text
rate_limit
authentication_failed
oauth_org_not_allowed
billing_error
invalid_request
server_error
max_output_tokens
unknown
```

Payload može sadržati i:

```text
error_details
last_assistant_message
```

To znači da FlowOS može prikazati:

```text
Claude
RATE LIMITED
detektovano: 07:42
izvor: StopFailure
```

bez ikakvog LLM-a i bez parsiranja slobodnog teksta sa ekrana.

### Važna UX posljedica

FlowOS ne treba tvrditi da je Claude „dostupan zauvijek“.

Treba čuvati:

```text
last_known_availability_state
last_observed_at
source
```

Npr.:

```text
RATE_LIMITED — posljednji signal 07:42
```

Naredni uspješan turn može osvježiti stanje.

---

## 5.6. Model detect — ✅

`SessionStart` sadrži `model`.

Zato FlowOS može, kada je podatak dostupan, prikazati:

```text
Claude / claude-sonnet-...
```

Naziv modela ostaje pomoćna informacija, ne preduslov workflowa.

---

## 5.7. Report linkage — ✅

Ako standardizovani `agent_report` sadrži:

```yaml
agent: claude
session_id: <claude session id>
tasks:
  - FLOW-017
```

FlowOS može potpuno deterministički povezati:

```text
Claude hook events
      ↓ session_id
AgentSession
      ↓ session_id
agent_report
      ↓ task IDs
Plan / tasks
```

Ako report nema session ID, fallback je:

- cwd/project;
- vrijeme nastanka;
- aktivni task;
- korisnička potvrda.

Za nove reportove treba koristiti session ID gdje god ga agent adapter može dati.

---

## 5.8. Preporučeni Claude adapter

### FlowOS v1

Mali user-level hook:

```text
Claude VSCode
    ↓
Claude hook
    ↓ HTTP POST ili lokalna command skripta
FlowOS localhost collector
```

Preporuka je da FlowOS podrži:

```text
ClaudeObservationAdapter
```

koji normalizuje Claude evente u FlowOS Event Ledger.

### Zašto HTTP hook ima smisla

Claude hooks mogu slati JSON HTTP endpointu, pa FlowOS može imati npr.:

```text
POST http://127.0.0.1:<port>/observation/claude
```

Za lokalnu zaštitu može se koristiti:

- loopback-only bind;
- nasumični lokalni token;
- secret header iz environmenta;
- odbacivanje zahtjeva koji ne dolaze lokalno.

---

## 5.9. Claude zaključak

| Stavka | Ocjena |
|---|---|
| Session detect | ✅ |
| CWD/project | ✅ |
| Tool activity | ✅ |
| Tool errors | ✅ |
| API/rate-limit errors | ✅ |
| Model | ✅ |
| Report linkage | ✅ |
| Promjena korisnikovog workflowa | Minimalna |
| Ukupna pouzdanost | **VRLO VISOKA** |

### Verdict

**CLAUDE: GO**

---

# 6. Pi — detaljna provjera

## 6.1. Najvažniji nalaz

Pi je možda čak **najfleksibilniji agent za FlowOS integraciju**, jer normalni terminalski Pi podržava ekstenzije koje se automatski učitavaju, a te ekstenzije imaju vrlo bogat lifecycle/event API.

Za FlowOS nije potrebno da Pi bude pokrenut preko FlowOS-a.

Mala FlowOS Pi ekstenzija može stajati u:

```text
~/.pi/agent/extensions/
```

i normalno se učitavati kada korisnik pokrene Pi kao i danas.

---

## 6.2. Session detect — ✅ DIREKTNO

Pi extension API ima:

```text
session_start
session_shutdown
```

`session_start` razlikuje razloge:

```text
startup
reload
new
resume
fork
```

SessionManager eksplicitno nudi:

```text
getSessionId()
getSessionFile()
getCwd()
isPersisted()
```

To FlowOS-u daje pouzdan identitet sesije.

### Persistirani session format

Pi session fajlovi su JSONL i session header sadrži:

```text
type = session
id
timestamp
cwd
```

Dakle čak i ako je live event propušten, postoji mogućnost kasnije reconciliation provjere nad session metapodacima.

To ne znači da FlowOS treba čitati cijeli transcript kao primarni protokol. Za live rad bolja je extension telemetrija.

---

## 6.3. Project / cwd — ✅ DIREKTNO

Pi ima direktan `getCwd()` i session header čuva cwd.

Extension događaji takođe rade u kontekstu aktivne sesije.

FlowOS može mapirati:

```text
Pi cwd
↓
registrovani FlowOS project root
```

---

## 6.4. Activity events — ✅ VRLO BOGATO

Pi nudi lifecycle događaje kao:

```text
agent_start
agent_end

turn_start
turn_end

message_start
message_update
message_end

tool_execution_start
tool_execution_update
tool_execution_end
```

Tool end sadrži i:

```text
isError
```

Pi extension sistem dodatno nudi `tool_call` / `tool_result` interception i druge evente.

To znači da FlowOS može dobiti skoro real-time timeline:

```text
Pi turn started
Bash tool started
Bash streaming output
Bash completed
Edit tool started
Edit completed
Turn completed
Agent run settled
```

bez parsiranja terminalskog rendera.

---

## 6.5. Provider errors i rate limit — ✅ DIREKTNO

Pi ima posebno koristan događaj:

```text
after_provider_response
```

koji dobija:

```text
status
headers
```

Dokumentacija direktno daje primjer:

```text
status == 429
```

za rate limit.

Dakle FlowOS Pi adapter može evidentirati:

```text
PI_PROVIDER_RESPONSE
status = 429
retry_after = ...
```

ako provider/transport exposeuje header.

Pi takođe ima:

```text
auto_retry_start
auto_retry_end
```

kao strukturirane događaje.

Tool greške su dostupne preko `tool_execution_end.isError`.

---

## 6.6. Model detect — ✅ DIREKTNO

Pi ima `model_select` event koji daje:

```text
event.model
event.previousModel
event.source
```

Model sadrži provider/model identitet.

To je idealno za FlowOS scenarij gdje korisnik u Pi-ju promijeni:

```text
Kimi → Gemini → DeepSeek
```

FlowOS ne treba zaključiti da je „Pi nedostupan“ ako je samo jedan model/provider dosegao limit.

Može evidentirati:

```text
Pi / Kimi → RATE_LIMITED
```

a nakon promjene:

```text
Pi / Gemini → aktivan model
```

---

## 6.7. Report linkage — ✅

Najbolji ključ je:

```text
Pi session_id
```

uz:

```text
cwd
```

i standardizovani report header:

```yaml
agent: pi
session_id: ...
tasks:
  - FLOW-017
```

Pi session ID je trajni UUID, pa je veza vrlo čista.

---

## 6.8. Budući managed execution — postoji bez nove arhitekture

Pi dodatno podržava:

```text
--mode json
--mode rpc
```

RPC/JSON režim emituje strukturirane evente preko JSONL.

To znači da, ako FlowOS jednog dana bude sam pokretao Pi AFK, možemo koristiti službeni programatski interfejs umjesto terminal scraping-a.

Ali za v1 to nije potrebno.

---

## 6.9. Preporučeni Pi adapter

```text
Pi TUI
  ↓
FlowOS Pi extension
  ↓
localhost FlowOS collector
```

Extension sluša samo potrebne evente i šalje normalizovane podatke.

Predloženi minimum:

```text
session_start
session_shutdown
agent_start
agent_end
turn_start
turn_end
tool_execution_start
tool_execution_end
after_provider_response
model_select
```

`message_update` ne treba slati po defaultu jer bi proizvodio mnogo događaja i nepotrebno čuvao sadržaj razgovora.

---

## 6.10. Pi zaključak

| Stavka | Ocjena |
|---|---|
| Session detect | ✅ |
| CWD/project | ✅ |
| Tool activity | ✅ |
| Tool error | ✅ |
| Provider/rate-limit | ✅ |
| Model | ✅ |
| Report linkage | ✅ |
| Promjena workflowa | Minimalna: instalira se FlowOS extension |
| Ukupna pouzdanost | **VRLO VISOKA** |

### Verdict

**PI: GO**

---

# 7. Codex — detaljna provjera

## 7.1. Najvažniji nalaz

Codex ima **dvije različite integracione površine** relevantne za FlowOS:

1. **Hooks** — najbolji kandidat za pasivno praćenje korisnikovog postojećeg rada.
2. **`codex app-server`** — vrlo bogat programatski protokol koji napaja rich klijente, uključujući VSCode ekstenziju.

Važno je da ih ne pomiješamo.

To što VSCode ekstenzija koristi app-server **ne znači automatski da FlowOS smije ili može bezbjedno da se zakači na baš onu app-server instancu koju je pokrenula VSCode ekstenzija**.

Za v1 treba preferirati hooks.

---

## 7.2. Hook sistem — potvrđeno u aktuelnom OpenAI Codex sourceu

Aktuelni Codex source ima hook schema za:

```text
PreToolUse
PermissionRequest
PostToolUse
PreCompact
PostCompact
SessionStart
UserPromptSubmit
SubagentStart
SubagentStop
Stop
SessionEnd
```

Relevantni hook inputi sadrže:

```text
session_id
cwd
model
transcript_path
```

Turn-scoped hookovi sadrže i:

```text
turn_id
```

Tool hookovi sadrže:

```text
tool_name
tool_input
tool_use_id
```

`PostToolUse` sadrži i:

```text
tool_response
```

Ovo je dovoljno za jak observer adapter.

---

## 7.3. Session detect — 🟡 / ✅ NAKON LOKALNOG PoC-a

Source potvrđuje:

```text
SessionStart
SessionEnd
session_id
cwd
model
source = startup/resume/clear/compact
```

Dakle Codex engine ima sve što nam treba.

### Zašto ipak nije odmah označeno „vrlo visoka“ kao Claude

Kod Claudea Anthropic eksplicitno dokumentuje da VSCode ekstenzija i CLI dijele hook settings.

Kod Codexa je potvrđeno:

- app-server napaja VSCode ekstenziju;
- hook sistem je dio aktuelnog Codex core-a;
- hook lifecycle i schema postoje.

Ali prije nego što zaključamo FlowOS implementaciju treba na korisnikovom računaru provjeriti:

> Da li trenutna instalirana Codex VSCode ekstenzija zaista izvršava user hook konfiguraciju za `SessionStart`, `PostToolUse`, `Stop` i `SessionEnd` u grafičkom VSCode workflowu koji korisnik koristi.

To je mali test od nekoliko minuta i ne zahtijeva promjenu arhitekture.

---

## 7.4. Project / cwd — ✅

Hook schema direktno sadrži:

```text
cwd
session_id
model
```

Ako hook u VSCode-u radi, project mapping je čist.

App-server dodatno podržava thread operacije sa `cwd` i thread list filtriranje prema `cwd`.

---

## 7.5. Activity events — ✅ BOGATO, ali ne nužno potpuno

Hook nivo može pratiti:

```text
UserPromptSubmit
PreToolUse
PostToolUse
Stop
SubagentStart
SubagentStop
...
```

`PostToolUse` daje:

```text
tool_response
```

To je dovoljno da FlowOS vidi mnogo lokalne agentske aktivnosti.

### Ograničenje

Hook sistem ne treba tretirati kao garantovanu kopiju svakog internog događaja Codexa.

FlowOS treba da čuva samo ono što je adapter stvarno primio.

Ako neka hosted ili specijalna aktivnost nije predstavljena hookom, FlowOS ne smije izmišljati događaj.

---

## 7.6. App-server — vrlo bogata telemetrija

`codex app-server` je JSON-RPC interfejs koji OpenAI koristi za rich klijente.

Osnovni domain:

```text
Thread
  ↓
Turn
  ↓
Item
```

Dostupni događaji uključuju:

```text
thread/started
turn/started
item/started
item/completed
turn/completed
```

Postoje item tipovi za:

- command execution;
- file changes;
- MCP tool calls;
- agent messages;
- plan;
- druge aktivnosti.

`turn/diff/updated` daje agregirani diff trenutnog turna.

`commandExecution` sadrži:

```text
command
cwd
status
exitCode
durationMs
```

`fileChange` sadrži putanje i diffove.

Za FlowOS-managed Codex u budućnosti ovo je izuzetno moćan interfejs.

---

## 7.7. Errors / rate limits — dva nivoa

### A. Pasivni hook-only režim

**🟡 DJELIMIČNO**

Aktuelni Codex hook schema nema Claude-ekvivalentni `StopFailure` događaj sa jasnim:

```text
UsageLimitExceeded
RateLimit
BillingError
```

Tool error možemo vidjeti kroz tool response, ali provider-level API greška nije jednako čisto riješena samo hookovima.

### B. App-server režim

**✅ VRLO BOGATO**

App-server `turn/completed` može završiti sa:

```text
completed
interrupted
failed
```

a fail sadrži strukturirani error objekt.

App-server dodatno ima:

```text
account/rateLimits/read
account/rateLimits/updated
```

koji mogu vratiti:

- used percent;
- window duration;
- reset timestamp;
- rate limit reached type;
- mjesečni/effective credit limit kada postoji;
- spend-control status;
- reset credits kada ih backend daje.

Dakle informacija postoji.

### Ali važna granica

Ne treba za FlowOS v1 pretpostaviti:

> „Pošto VSCode koristi app-server, FlowOS će se jednostavno priključiti VSCode app-serveru.“

Tačan discovery/ownership/attach model VSCode-ove instance nije dokumentovan kao javni FlowOS use-case.

Zato:

- v1 = hooks + universal fallback;
- app-server = buduća managed/advanced integracija ili zaseban provjeren spike.

---

## 7.8. Model detect — ✅

Codex hook input sadrži `model`.

App-server thread/turn konfiguracija takođe poznaje model.

---

## 7.9. Report linkage — ✅

Ako hook radi u VSCode-u:

```text
session_id + cwd
```

su dovoljni za:

```text
Codex activity
→ FlowOS AgentSession
→ agent_report
→ tasks
```

Report header:

```yaml
agent: codex
session_id: ...
tasks:
  - FLOW-017
```

---

## 7.10. Codex lokalni PoC — OBAVEZAN prije produkcione integracije

Na korisnikovom računaru treba napraviti bezopasan hook koji samo appenduje JSON u lokalni fajl ili šalje localhost POST.

Provjeriti u **grafičkom Codex VSCode panelu**:

1. otvoriti novu sesiju;
2. poslati prompt;
3. natjerati Codex da pročita ili izmijeni bezopasan fajl;
4. izvršiti bezopasnu shell komandu;
5. završiti turn;
6. zatvoriti sesiju;
7. provjeriti dobijene evente.

Minimalni očekivani event set:

```text
SessionStart
UserPromptSubmit
PreToolUse
PostToolUse
Stop
SessionEnd
```

Ako ovo radi, Codex v1 adapter dobija ocjenu **VISOKA**.

Ako ne radi u trenutnoj VSCode verziji, fallback je:

```text
Git + filesystem + agent_reports + user decision
```

dok ne izaberemo drugu integraciju.

---

## 7.11. Codex zaključak

| Stavka | Ocjena |
|---|---|
| Session detect | 🟡 → ✅ poslije lokalnog VSCode PoC-a |
| CWD/project | ✅ |
| Tool activity | ✅ |
| Tool errors | ✅ za hook-obuhvaćene alate |
| Provider/rate-limit u passive hook režimu | 🟡 |
| Provider/rate-limit kroz app-server | ✅ |
| Model | ✅ |
| Report linkage | ✅ |
| Ukupna pouzdanost | **SREDNJE VISOKA** dok ne uradimo PoC |

### Verdict

**CODEX: GO UZ OBAVEZNI MALI LOKALNI PoC**

---

# 8. Crush — detaljna provjera

Crush zahtijeva najveću pažnju jer ima **dva veoma različita nivoa integracije**.

---

# 8A. Crush u današnjem normalnom terminalskom režimu

## 8A.1. Hooks — trenutno samo PreToolUse

Aktuelna Crush dokumentacija eksplicitno kaže da je podržan samo:

```text
PreToolUse
```

Hook dobija JSON:

```text
event
session_id
cwd
tool_name
tool_input
```

i environment varijable:

```text
CRUSH_SESSION_ID
CRUSH_CWD
CRUSH_PROJECT_DIR
CRUSH_TOOL_NAME
...
```

To je pouzdan i vrlo koristan signal, ali nije kompletan lifecycle.

---

## 8A.2. Session detect — 🟡 DJELIMIČNO

FlowOS može detektovati da postoji aktivna Crush sesija čim Crush prvi put pokuša tool call.

Tada dobija:

```text
session_id
cwd
project_dir
```

Ali `PreToolUse` nije pravi `SessionStart`.

Ako korisnik otvori Crush i deset minuta samo razgovara bez tool poziva, hook ne mora ništa poslati FlowOS-u.

Zato je pravilna semantika:

```text
CRUSH_SESSION_SEEN
```

a ne nužno:

```text
CRUSH_SESSION_STARTED
```

---

## 8A.3. Project / cwd — ✅ DIREKTNO

Kada hook okine, imamo direktno:

```text
cwd
CRUSH_PROJECT_DIR
```

Project mapping je vrlo pouzdan.

---

## 8A.4. Activity events — 🟡 DJELIMIČNO

Možemo vidjeti da je agent **namjeravao** pokrenuti:

- bash;
- edit;
- write;
- multiedit;
- druge tools.

Ali default hook nema:

```text
PostToolUse
ToolResult
TurnEnd
SessionEnd
```

Dakle FlowOS ne može iz samog hooka tvrditi da je predloženi tool call stvarno uspješno završen.

To se mora dopuniti:

- Git watcherom;
- filesystem watcherom;
- eventualno logom;
- agent reportom.

---

## 8A.5. Errors / rate limit — 🟡

Normalni hook nije provider-response hook.

Crush vodi projekatski log:

```text
.crush/logs/crush.log
```

i ima:

```text
crush logs --follow
```

Log se može koristiti kao **fallback diagnostika**, ali ga ne treba proglasiti stabilnim javnim machine-readable protokolom.

Ako se patterni loga promijene u novoj verziji, parser bi se mogao polomiti.

Zato FlowOS Core ne smije zavisiti od Crush log parsiranja za pravilno funkcionisanje.

---

## 8A.6. Model detect — 🟡

Default `PreToolUse` payload ne daje aktivni model.

Crush kao proizvod zna izabrani model, ali u normalnom hook režimu FlowOS ga ne treba pokušavati pogoditi.

GUI može prikazati:

```text
Crush — model UNKNOWN
```

dok ne postoji pouzdan signal.

---

## 8A.7. Report linkage — ✅

Nakon prvog hooka imamo:

```text
session_id
cwd
project_dir
```

Ako Crush report dobije:

```yaml
agent: crush
session_id: ...
tasks:
  - FLOW-017
```

link je deterministički.

---

## 8A.8. Default Crush verdict

| Stavka | Ocjena |
|---|---|
| Session detect | 🟡 |
| CWD/project | ✅ |
| Tool intent/activity | 🟡 |
| Tool result | ❌ direktno kroz default hook |
| Provider error | 🟡 fallback log |
| Model | 🟡 / UNKNOWN |
| Report linkage | ✅ |
| Pouzdanost | **SREDNJA** |

### Verdict

**CRUSH DEFAULT: GO KAO PARCIJALNI ADAPTER**

To nije razlog da FlowOS odustanemo od Crusha.

FlowOS za Crush samo mora iskreno pokazivati manje detalja.

---

# 8B. Crush client/server režim — mnogo bogatiji, ali eksperimentalan

## 8B.1. Status zrelosti

Crush release dokumentacija i dalje client/server arhitekturu označava kao:

```text
experimental
```

i uključuje se sa:

```text
CRUSH_CLIENT_SERVER=1
```

Zato ovaj režim **ne smije biti obavezan uslov FlowOS v1**.

---

## 8B.2. Workspace identitet

U client/server režimu workspaces su vezani za resolved:

```text
--cwd
```

Dva klijenta sa istim cwd mogu se spojiti na isti underlying workspace.

Workspace API izlaže:

```text
workspace ID
path
configuration
environment
```

---

## 8B.3. Session state

Session model izlaže:

```text
ID
ParentSessionID
Title
MessageCount
PromptTokens
CompletionTokens
Cost
Todos
CreatedAt
UpdatedAt
IsBusy
AttachedClients
```

Posebno korisno za FlowOS:

```text
IsBusy
AttachedClients
```

`IsBusy` znači da je agent turn trenutno u toku za session.

---

## 8B.4. Agent/model info

`AgentInfo` sadrži:

```text
IsBusy
IsReady
Model
ModelCfg
```

Dakle u client/server režimu aktivni model nije problem.

---

## 8B.5. SSE event stream

Crush server emituje strukturirane događaje preko SSE.

Potvrđene vrste uključuju:

- message događaje;
- session događaje;
- file/history događaje;
- permission events;
- AgentEvent;
- `RunComplete`;
- LSP/MCP događaje;
- config događaje.

Message struktura može sadržati:

- model;
- provider;
- text;
- reasoning;
- tool call;
- tool result;
- shell command;
- exit code;
- error oznaku.

Ovo je skoro idealan FlowOS observer feed.

---

## 8B.6. RunComplete — posebno važan signal

U provjerenom Crush v0.74.1 sourceu `RunComplete` je eksplicitno opisan kao **autoritativni završetak jednog top-level agent turna**.

Sadrži:

```text
SessionID
RunID
MessageID
Text
Error
Cancelled
```

To omogućava:

```text
RUN_STARTED/SEEN
...
RUN_COMPLETE
```

bez nagađanja.

Važno: ovo je završetak **run/turna**, ne dokaz da je FlowOS task završen. To ostaje u skladu sa ADR-005.

---

## 8B.7. Errors

`RunComplete.Error` i AgentEvent strukture omogućavaju detekciju da je agentski run završio greškom.

To je mnogo pouzdanije od log parsiranja.

Ipak, u istraženom javnom protokolu nije potvrđen jednako standardizovan provider error enum kao Claude `StopFailure`.

FlowOS zato može sigurno reći:

```text
Crush run error
```

i sačuvati poruku, ali klasifikaciju:

```text
RATE_LIMITED
BILLING
AUTH
```

treba napraviti samo ako je izvor eksplicitno strukturira ili ako kasnije dodamo provjeren parser za konkretan provider.

---

## 8B.8. Crush client/server zaključak

Tehnička observability sposobnost:

**VISOKA**

Produktna/stability zrelost:

**EKSPERIMENTALNA**

### Verdict

> **Vrlo obećavajuće za budući FlowOS Crush adapter, ali ne koristiti kao obaveznu v1 zavisnost dok Charm sam ne stabilizuje client/server arhitekturu ili dok je ne testiramo dovoljno na korisnikovom računaru.**

---

# 9. Univerzalni fallback sloj — ključ da FlowOS ne zavisi od agenata

Čak i kada nema nijednog provider hooka, FlowOS može pratiti mnogo činjenica.

## 9.1. Git

FlowOS može vidjeti:

```text
branch
HEAD
new commits
changed files
staged files
unstaged files
untracked files
diff
```

Git ne zna uvijek pouzdano **ko** je izvršio izmjenu u shared treeju, ali zna šta se promijenilo.

---

## 9.2. Filesystem

Watcher može evidentirati:

```text
file created
file modified
file deleted
agent report created
```

Opet: događaj je činjenica, autor može biti `UNKNOWN` ako nema agent session korelacije.

---

## 9.3. agent_reports

Ovo je posebno jak fallback.

Ako svaki novi report ima:

```yaml
---
flowos_report: 1
agent: pi
session_id: ...
role: implementation
tasks:
  FLOW-017: in_progress
  FLOW-018: agent_work_completed
---
```

onda FlowOS dobija pouzdan handoff čak i ako live observer nije uhvatio svaki događaj.

---

## 9.4. Korisnička odluka

Ako FlowOS ne zna kojoj sesiji pripada rad:

```text
Nova Pi/Crush/Codex aktivnost
Task: UNKNOWN
```

korisnik može jednim klikom povezati sesiju sa taskom.

To je bolje od semantičkog AI nagađanja.

---

# 10. Predloženi tehnički model — AgentObservationAdapter

Istraživanje podržava zajednički adapter interfejs.

Ne treba praviti četiri odvojena FlowOS sistema.

Konceptualno:

```text
AgentObservationAdapter
    ├── ClaudeObservationAdapter
    ├── CodexObservationAdapter
    ├── PiObservationAdapter
    └── CrushObservationAdapter
```

Adapter ne mora podržati sve mogućnosti.

Svaki adapter deklarira capabilities.

Primjer:

```text
SESSION_LIFECYCLE
SESSION_ID
CWD
MODEL
TURN_LIFECYCLE
TOOL_PRE
TOOL_POST
TOOL_ERROR
PROVIDER_ERROR
RATE_LIMIT
SUBAGENT_EVENTS
```

### Primjer capability matrice

| Capability | Claude | Codex hooks | Pi | Crush default | Crush client/server |
|---|---:|---:|---:|---:|---:|
| SESSION_ID | ✅ | ✅ | ✅ | ✅ | ✅ |
| SESSION_START | ✅ | ✅* | ✅ | ❌ | ✅ |
| SESSION_END | ✅ | ✅* | ✅ | ❌ | 🟡 workspace/session semantics |
| CWD | ✅ | ✅ | ✅ | ✅ | ✅ |
| MODEL | ✅ | ✅ | ✅ | ❌ | ✅ |
| TOOL_PRE | ✅ | ✅ | ✅ | ✅ | ✅ |
| TOOL_POST | ✅ | ✅ | ✅ | ❌ | ✅ |
| TOOL_ERROR | ✅ | ✅ | ✅ | ❌ | ✅ |
| TURN_COMPLETE | ✅ Stop | ✅ Stop / app-server | ✅ | ❌ | ✅ RunComplete |
| PROVIDER_ERROR | ✅ | 🟡 hooks / ✅ app-server | ✅ | ❌/log | ✅ generic run error |
| RATE_LIMIT | ✅ | 🟡 hooks / ✅ app-server | ✅ | ❌/log | 🟡 |
| Pouzdan live events | ✅ | ✅* | ✅ | 🟡 | ✅ |

`*` = potvrditi na tačnoj instaliranoj Codex VSCode verziji.

---

# 11. Normalizovani FlowOS event — preporuka

Agent adapteri ne smiju gurati provider-specific strukture direktno kroz cijeli FlowOS.

Minimalni normalizovani envelope:

```text
AgentObservationEvent
    event_id
    provider
    session_id
    project_id
    cwd
    event_type
    observed_at
    source
    model        [optional]
    turn_id      [optional]
    tool_name    [optional]
    raw_payload  [optional/retention policy]
```

Primjeri `event_type`:

```text
SESSION_STARTED
SESSION_SEEN
SESSION_RESUMED
SESSION_ENDED

TURN_STARTED
TURN_COMPLETED
TURN_FAILED

TOOL_STARTED
TOOL_COMPLETED
TOOL_FAILED

CWD_CHANGED
MODEL_CHANGED

PROVIDER_ERROR
RATE_LIMITED

REPORT_CREATED
```

### Važno

Ako adapter nema dokaz za određeni event, ne izmišlja ga.

Npr. Crush default:

```text
PreToolUse
```

može proizvesti:

```text
SESSION_SEEN
TOOL_STARTED / TOOL_PROPOSED
```

ali ne:

```text
TOOL_COMPLETED
SESSION_ENDED
```

dok nema drugi dokaz.

---

# 12. Report linkage — definitivno tehnički rješivo bez AI-a

Za nove reportove preporuka:

```yaml
---
flowos_report_version: 1
agent: pi
session_id: 6c...
role: implementation
project_id: ...
tasks:
  FLOW-017: in_progress
  FLOW-018: agent_work_completed
created_at: 2026-08-10T07:00:00+02:00
---
```

FlowOS zatim koristi:

```text
session_id
+
project_id/cwd
+
task IDs
```

Nema potrebe da LLM semantički čita report kako bi ga povezao sa sesijom.

Markdown body ostaje slobodan i ljudski čitljiv.

---

# 13. Privatnost i količina podataka

Pošto neki adapteri mogu emitovati veoma detaljne poruke i tool payloadove, FlowOS ne treba po defaultu čuvati sve.

Preporučeni v1 princip:

### Čuvati

```text
session lifecycle
agent/provider/model
cwd/project
tool name
tool status
file paths kada su relevantne
command status / exit code gdje je dostupan
Git state
timestamps
structured error category
agent report
```

### Ne čuvati automatski kompletno

```text
svaki thinking delta
svaki streaming token
cijeli transcript
svaki prompt sadržaj
svaki tool output bez potrebe
tajne/env vrijednosti
```

Razlog:

- manje baze;
- manje privatnosnog rizika;
- manje coupling-a sa provider formatima;
- FlowOS-u za osnovni cilj nije potrebno da bude transcript recorder.

---

# 14. Šta FlowOS NE SMIJE koristiti kao osnovni mehanizam

## 14.1. Screen scraping VSCode-a

Ne.

Krhko, zavisno od UI verzije i nepotrebno.

## 14.2. Terminal screen scraping

Ne kao osnovni mehanizam.

Pi ima extension/RPC API; Crush ima hook i client/server API.

## 14.3. Parsiranje skrivenog chain-of-thoughta

Ne.

FlowOS prati dostupne događaje i vidljive/strukturirane rezultate.

## 14.4. Transcript parsing kao glavni live API

Ne.

Transcript može biti pomoćni recovery/evidence izvor samo ako je format dokumentovan i stabilan.

Posebno za Codex ne treba graditi core oko internog transcript formata.

## 14.5. LLM klasifikovanje svakog eventa

Ne.

Provider adapter normalizuje poznati tehnički event deterministički.

---

# 15. Obavezni lokalni Proof-of-Concept testovi

Internet/source istraživanje dokazuje da integracione tačke postoje.

Prije implementiranja pune FlowOS funkcije treba uraditi **četiri mala lokalna smoke testa** nad verzijama koje korisnik stvarno koristi.

Ovo nije nova faza projekta od sedmica — cilj je dobiti empirijski dokaz.

---

## 15.1. Claude VSCode PoC

Napraviti bezopasan user-level hook koji evente appenduje u npr.:

```text
.flowos_probe/claude-events.jsonl
```

ili šalje na localhost.

Testirati:

1. otvoriti Claude VSCode sesiju;
2. poslati prompt;
3. natjerati Claude da pročita fajl;
4. natjerati ga da pokrene bezopasnu shell komandu;
5. završiti turn;
6. resume postojeću sesiju;
7. zatvoriti sesiju.

Očekujemo:

```text
SessionStart
PreToolUse
PostToolUse
Stop
SessionEnd
```

Dodatno StopFailure kada se prirodno pojavi API error/rate limit — ne treba namjerno trošiti kvotu radi testa.

### Pass kriterijum

`session_id` i `cwd` moraju biti stabilni i svi događaji moraju stići bez uticaja na normalan VSCode rad.

---

## 15.2. Codex VSCode PoC — najvažniji neprovjeren detalj

Napraviti minimalni hook logger.

U grafičkom Codex VSCode panelu testirati:

```text
SessionStart
UserPromptSubmit
PreToolUse
PostToolUse
Stop
SessionEnd
```

Provjeriti:

```text
session_id
turn_id
cwd
model
tool_name
tool_response
```

### Pass kriterijum

Ako user hooks rade u VSCode ekstenziji kao što Codex core schema sugeriše, Codex adapter prelazi sa:

```text
SREDNJE VISOKA
```

na:

```text
VISOKA
```

### Ako padne

Ne blokira FlowOS.

Privremeni Codex observer:

```text
Git + filesystem + agent_reports + user assignment
```

dok se zasebno ne ispita app-server ili drugi javni integracioni put.

---

## 15.3. Pi terminal PoC

Instalirati malu FlowOS Pi ekstenziju.

Testirati:

```text
session_start
agent_start
turn_start
tool_execution_start
tool_execution_end
turn_end
agent_end
model_select
session_shutdown
```

Provjeriti:

```text
ctx.sessionManager.getSessionId()
getSessionFile()
getCwd()
```

Kada se prirodno pojavi provider limit:

```text
after_provider_response.status == 429
```

### Pass kriterijum

Extension ne smije remetiti TUI niti usporavati normalan rad.

---

## 15.4. Crush normal mode PoC

Dodati globalni ili project `PreToolUse` FlowOS hook.

Provjeriti:

```text
session_id
cwd
CRUSH_PROJECT_DIR
tool_name
tool_input
```

### Pass kriterijum

FlowOS pouzdano dobija `SESSION_SEEN` i tool-intent događaje.

---

## 15.5. Crush client/server — odvojen eksperimentalni PoC

Samo ako želimo dublju Crush integraciju.

Uključiti:

```text
CRUSH_CLIENT_SERVER=1
```

Provjeriti:

- workspace discovery;
- session list;
- SSE stream;
- IsBusy;
- AttachedClients;
- message events;
- RunComplete;
- AgentInfo model;
- reconnect ponašanje;
- Windows named pipe transport.

### Bitna napomena

Ovaj režim ne treba biti uslov za FlowOS v1.

---

# 16. Verzije i kompatibilnost

Adapter mora evidentirati verziju alata kada je možemo dobiti.

Razlog:

```text
Claude hooks danas ≠ nužno hooks za dvije godine
Codex hook schema se razvija
Pi extension API se razvija
Crush client/server je eksperimentalan
```

FlowOS adapter treba imati:

```text
provider
provider_version
adapter_version
capabilities_detected
```

Umjesto pretpostavke:

```text
if provider == CRUSH:
    svi eventovi postoje
```

bolje:

```text
CrushAdapter.capabilities()
```

---

# 17. Posebna napomena o Crush v0.74.1 i current main

U istraživanju je direktno provjeren source tag:

```text
v0.74.1
```

i na njemu već postoje:

- `RunComplete`;
- session/agent proto strukture;
- SSE event wrapping;
- client/server infrastruktura.

Istovremeno, zvanični release tekst i dalje client/server opisuje kao **experimental**.

Aktuelni `main` dodatno napreduje i ne treba automatski pretpostaviti da je svaki detalj `main` brancha dostupan u korisnikovoj instaliranoj binarnoj verziji.

Zato FlowOS Crush adapter mora prvo pročitati/znati verziju i aktivirati samo provjerene capabilities.

---

# 18. GO / NO-GO po agentu

## Claude

**GO**

Nema identifikovanog fundamentalnog tehničkog problema.

Najbolji v1 mehanizam:

```text
Claude hooks → FlowOS localhost collector
```

---

## Pi

**GO**

Nema identifikovanog fundamentalnog tehničkog problema.

Najbolji v1 mehanizam:

```text
Pi extension → FlowOS localhost collector
```

---

## Codex

**GO UZ LOKALNI PoC**

Codex core ima odgovarajući hook model i app-server ima izuzetno bogatu telemetriju.

Jedina stvar koju ne treba pretpostaviti bez testa je ponašanje user hookova u tačnoj grafičkoj VSCode verziji koju korisnik trenutno koristi.

---

## Crush

**GO KAO DEGRADIRANI/PARCIJALNI ADAPTER U V1**

Default terminal:

```text
PreToolUse + Git + reports
```

je dovoljno da Crush bude vidljiv u FlowOS-u, ali ne jednako detaljno kao Claude/Pi.

Dublja integracija postoji kroz client/server REST/SSE, ali zbog eksperimentalnog statusa nije preporučljivo da FlowOS Core zavisi od nje.

---

# 19. Preporučeni redoslijed implementacije nakon PoC-a

Ovo nije konačni razvojni plan, nego tehnički najmanje rizičan redoslijed.

## 1. Universal Project Observer

Prvo napraviti ono što radi za sve:

```text
Git
filesystem
agent_reports
user decisions
```

## 2. ClaudeObservationAdapter

Najbolje dokumentovan i najmanje rizičan.

## 3. PiObservationAdapter

Vrlo bogat extension API i prirodan za postojeći terminal workflow.

## 4. CodexObservationAdapter

Tek nakon lokalnog VSCode smoke testa.

## 5. CrushObservationAdapter v1

`PreToolUse` + universal fallback.

## 6. Crush rich adapter

Tek kada client/server bude dovoljno stabilan ili nakon uspješnog lokalnog PoC-a.

---

# 20. Najvažnija arhitektonska posljedica

Istraživanje pokazuje da FlowOS ne treba imati model:

```text
svi agenti moraju davati sve događaje
```

nego:

```text
FlowOS Core
    │
    ├── Universal Project Observer
    │
    └── AgentObservationAdapter*
             │
             ├── različite capabilities
             └── različit nivo pouzdanosti
```

GUI uvijek mora moći razlikovati:

```text
KNOWN
UNKNOWN
NOT_SUPPORTED
LAST_KNOWN
```

Ako FlowOS nije dobio signal, ne smije izmišljati stanje.

---

# 21. Odgovor na početno pitanje

Početna sumnja je bila:

> Da li je planiranje FlowOS-a besmisleno ako nemamo tehnički način da pratimo agente koje korisnik stvarno koristi?

Nakon ovog spike-a odgovor je:

> **Nije besmisleno. Tehnička osnova postoji.**

Ali postoji važna korekcija:

> **FlowOS ne treba graditi kao da su svi agenti jednako integrabilni.**

Praktično:

```text
Claude  → bogat observer
Pi      → bogat observer
Codex   → bogat observer nakon malog VSCode dokaza
Crush   → parcijalni observer danas; bogat observer moguć u eksperimentalnom client/server režimu
```

Uz univerzalni Git/filesystem/report sloj, niti jedan pojedinačni agent nije single point of failure za FlowOS.

---

# 22. Konačna preporuka

**Nastaviti razvoj FlowOS-a.**

Ali prije novih velikih tehničkih ADR-ova uraditi četiri lokalna probe testa opisana u ovom dokumentu.

Prvi stvarni tehnički cilj nakon toga treba biti:

> **standardizovan `AgentObservationAdapter` + univerzalni project observer, bez manager LLM-a i bez zahtjeva da FlowOS preuzme kontrolu nad postojećim VSCode/terminal workflowom.**

To je najmanji sistem koji dokazuje osnovnu vrijednost FlowOS-a.

---

# 23. Primarni izvori

## Claude Code — Anthropic

- VSCode integration:  
  https://code.claude.com/docs/en/ide-integrations
- Hooks reference:  
  https://code.claude.com/docs/en/hooks
- Hooks guide:  
  https://code.claude.com/docs/en/hooks-guide

Ključna potvrda: VSCode ekstenzija i CLI dijele `~/.claude/settings.json`, uključujući hooks; hook payload daje `session_id` i `cwd`; `StopFailure` strukturira rate-limit/auth/billing/server greške.

---

## Codex — OpenAI

- Official repository:  
  https://github.com/openai/codex
- App Server protocol:  
  https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md
- Hook schema source:  
  https://github.com/openai/codex/blob/main/codex-rs/hooks/src/schema.rs
- Hook runtime/config source:  
  https://github.com/openai/codex/tree/main/codex-rs/hooks

Ključna potvrda: session/tool/stop hook schema ima `session_id`, `turn_id`, `cwd`, `model`; app-server daje thread/turn/item lifecycle, diff/command/file događaje i account rate-limit API.

---

## Pi — earendil-works/pi

- Extensions:  
  https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md
- Session format:  
  https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/session-format.md
- JSON event mode:  
  https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/json.md
- RPC mode:  
  https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/rpc.md
- SDK:  
  https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/sdk.md

Ključna potvrda: extensions vide lifecycle/tool/model/provider-response događaje; SessionManager daje session ID/cwd/file; provider response event daje HTTP status uključujući 429.

---

## Crush — Charmbracelet

- Official repository:  
  https://github.com/charmbracelet/crush
- Hook/config guide:  
  https://github.com/charmbracelet/crush/blob/main/internal/skills/builtin/crush-config/SKILL.md
- Releases:  
  https://github.com/charmbracelet/crush/releases
- Client/server proto, provjeren i na v0.74.1:  
  https://github.com/charmbracelet/crush/blob/v0.74.1/internal/proto/proto.go
- SSE event wrapping, provjeren i na v0.74.1:  
  https://github.com/charmbracelet/crush/blob/v0.74.1/internal/server/events.go

Ključna potvrda: default hooks trenutno nude samo `PreToolUse`; experimental client/server nudi workspace/session/model/SSE/RunComplete telemetriju.

---

## 24. Status nakon feasibility spike-a

```text
FLOWOS AGENT OBSERVABILITY FEASIBILITY

Claude   ██████████  GO
Pi       ██████████  GO
Codex    ████████░░  GO + local VSCode PoC
Crush    ██████░░░░  GO partial
                  ↳ richer client/server path exists but is experimental

OVERALL  █████████░  GO
```

**Nema pronađenog fundamentalnog tehničkog razloga zbog kojeg bi osnovnu FlowOS ideju trebalo odbaciti.**

Najveći preostali rizik nije „da li se može“, nego **koliko bogatu telemetriju možemo stabilno dobiti iz svake konkretne instalirane verzije bez povećavanja kompleksnosti i bez narušavanja postojećeg korisničkog workflowa.**
