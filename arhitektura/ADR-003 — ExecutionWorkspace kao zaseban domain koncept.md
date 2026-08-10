# ADR-003 — ExecutionWorkspace kao zaseban domain koncept

## Odluka

FlowOS razdvaja radno okruženje, pojedinačno izvršenje AI agenta i resumable agentski kontekst u tri različita koncepta:

- `ExecutionWorkspace`
- `AgentRun`
- `AgentContext`

Ovi koncepti se ne smiju objediniti pod jednim generičkim `AgentSession` modelom.

## ExecutionWorkspace

`ExecutionWorkspace` predstavlja fizičko i Git okruženje u kojem se izvršava `ImplementationTask`.

Workspace može sadržavati:

- repository;
- dedicated branch;
- Git worktree;
- base commit;
- current commit;
- execution environment provider;
- sandbox/container identitet kada postoji;
- lifecycle stanje;
- informacije potrebne za recovery i ponovno povezivanje nakon restarta FlowOS-a.

Workspace nije vezan isključivo za AI agenta.

U njemu se mogu izvršavati:

- AI agenti;
- testovi;
- lint;
- build;
- Git operacije;
- determinističke skripte;
- verification komande.

## AgentRun

`AgentRun` predstavlja jedno konkretno pokretanje jednog AI agenta unutar ExecutionWorkspace-a.

Svako novo pokretanje, retry ili nastavak rada predstavlja novi AgentRun.

AgentRun evidentira najmanje:

- agent/provider;
- model kada je poznat;
- ExecutionWorkspace;
- početak i kraj;
- process/PID podatke;
- exit status;
- completion status;
- log/evidence reference;
- razlog pokretanja.

## AgentContext

`AgentContext` predstavlja agentski conversational/session state koji provider podržava da se kasnije nastavi ili fork-uje.

Primjeri su Claude Code session ID ili Codex session ID.

AgentContext je odvojen od AgentRun-a jer jedan agentski kontekst može biti korišten kroz više uzastopnih AgentRun-ova.

## Odnosi

Tipičan odnos je:

`ImplementationTask → ExecutionWorkspace → AgentRun`

a AgentRun može proizvesti ili koristiti `AgentContext`.

Jedan ExecutionWorkspace može sadržavati više AgentRun-ova, VerificationRun-ova i ReviewRun-ova tokom životnog ciklusa jednog taska.

## Worktree pravilo

FlowOS-managed AFK coding izvršenje mora koristiti dedicated branch i dedicated Git worktree.

Direktan AFK rad nad korisnikovim glavnim working treejem nije dozvoljen.

## Execution environment

Sandbox nije dio identiteta AI agenta.

ExecutionWorkspace bira `ExecutionEnvironmentProvider`, na primjer:

- `HOST`
- `DOCKER`
- budući remote provider

AgentProvider se bira nezavisno:

- Claude Code
- Codex
- Pi
- drugi provider

Time se omogućavaju kombinacije kao:

`Claude + HOST`

`Claude + DOCKER`

`Codex + HOST`

`Codex + DOCKER`

bez promjene osnovnog execution modela.

## Persistencija

ExecutionWorkspace mora imati dovoljno trajnog stanja da FlowOS može rekonstruisati njegovo stanje nakon:

- zatvaranja GUI-a;
- restarta GUI-a;
- restarta FlowOS servisa;
- neočekivanog prekida procesa.

Zatvaranje GUI-a ne prekida automatski ExecutionWorkspace niti agentske procese.

## Cleanup

Workspace se ne briše automatski ako sadrži:

- uncommitted promjene;
- neriješen konflikt;
- aktivan proces;
- nepohranjene evidence artefakte;
- stanje potrebno za recovery.

Takav workspace mora ostati dostupan korisniku dok FlowOS ne utvrdi da je cleanup bezbjedan ili korisnik ne donese odluku.

## Početno ograničenje

U prvoj implementaciji jedan ImplementationTask može imati najviše jedan aktivni ExecutionWorkspace.

Podrška za više paralelnih alternativnih workspaceova za isti task nije dio početnog scopea.