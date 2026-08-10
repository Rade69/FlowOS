# ADR-005 — Agent Provider i način interakcije su nezavisni koncepti

## Odluka

FlowOS ne vezuje identitet AI agenta za korisnički interfejs ili način na koji je agent pokrenut.

Agent i način interakcije predstavljaju dvije nezavisne dimenzije sistema.

## AgentProvider

`AgentProvider` identifikuje agentski runtime sa kojim FlowOS radi.

Početno relevantni provideri su:

- `CLAUDE`
- `CODEX`
- `PI`
- `CRUSH`

Arhitektura mora omogućiti naknadno dodavanje drugih agenata bez promjene osnovnog `AgentRun`, `ExecutionWorkspace`, verification ili evidence modela.

## SessionMode

AgentRun može raditi u jednom od tri osnovna režima.

### EXTERNAL_INTERACTIVE

Agent je pokrenuo korisnik izvan FlowOS-a i korisnik vodi sesiju interaktivno.

Primjeri:

- Claude Code VSCode ekstenzija;
- Codex VSCode ekstenzija;
- Pi u terminalu;
- Crush u terminalu.

FlowOS u ovom režimu prvenstveno posmatra, evidentira i povezuje activity sa projektom, workspaceom i taskom.

FlowOS ne mora posjedovati PID niti lifecycle takvog procesa.

### FLOWOS_INTERACTIVE

FlowOS priprema execution kontekst i pokreće ili otvara odgovarajuće radno okruženje, ali korisnik neposredno vodi razgovor sa agentom.

Primjer:

`FlowOS → dedicated worktree → terminal/IDE → Pi/Claude/Codex → korisnik`

FlowOS posjeduje workspace lifecycle, ali korisnik ostaje operator agentske sesije.

### FLOWOS_MANAGED

FlowOS pokreće i kontroliše agentski execution bez potrebe za stalnim korisničkim prisustvom.

FlowOS u ovom režimu može upravljati:

- pokretanjem;
- prompt/task predajom;
- streamingom događaja;
- timeoutom;
- prekidom;
- retry/resume pravilima;
- completion detekcijom;
- verification workflowom.

Ovo je osnovni režim za budući AFK execution.

## InteractionSurface

Površina preko koje korisnik vidi ili vodi agent može biti evidentirana nezavisno od SessionMode-a.

Primjeri:

- `VSCODE`
- `TERMINAL`
- `CLI`
- `RPC`
- budući drugi klijenti.

InteractionSurface nije zaseban domain workflow i ne određuje semantiku ImplementationTask-a.

## Provider capabilities

Ne moraju svi AgentProvider-i podržavati iste mogućnosti.

Provider adapter treba eksplicitno deklarisati capabilities, na primjer:

- `OBSERVABLE`
- `PROGRAMMATIC_START`
- `STREAM_EVENTS`
- `STRUCTURED_EVENTS`
- `INTERACTIVE`
- `RESUME_CONTEXT`
- `FORK_CONTEXT`
- `PROGRAMMATIC_STOP`
- `STRUCTURED_RESULT`

FlowOS workflow smije koristiti samo capabilities koje konkretni provider stvarno podržava.

## Jedinstveni AgentRun model

Bez obzira da li agent radi u VSCode-u, terminalu, CLI-u ili RPC režimu, FlowOS koristi zajednički `AgentRun` domain koncept.

Primjer:

`AgentRun(provider=CLAUDE, mode=EXTERNAL_INTERACTIVE, surface=VSCODE)`

i

`AgentRun(provider=PI, mode=FLOWOS_MANAGED, surface=RPC)`

predstavljaju isti osnovni tip radne jedinice sa različitim provider capabilities i načinom kontrole.

## Personal-first pravilo

FlowOS ne zahtijeva od korisnika da napusti postojeći način rada kako bi mogao koristiti sistem.

Postojeći interaktivni workflowi u VSCode-u i terminalu moraju ostati prvoklasno podržani.

FlowOS-managed execution je dodatna mogućnost, a ne obavezna zamjena za postojeće alate.

## Integraciona strategija

Integracija pojedinačnih agenata razvija se postepeno.

Prvo se koristi najmanje invazivan pouzdan mehanizam za observation i identifikaciju sesije.

Dublja programatska kontrola dodaje se samo kada agent nudi dovoljno stabilan interfejs i kada donosi konkretnu vrijednost FlowOS-u.

FlowOS ne smije zavisiti od nedokumentovanih internih protokola pojedinačne IDE ekstenzije kao osnovnog mehanizma rada.