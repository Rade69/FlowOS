# ADR-005 — Execution Environment Provider

## Odluka

FlowOS odvaja execution okruženje od AI agenta kroz zaseban `ExecutionEnvironmentProvider` koncept.

Execution environment određuje gdje i pod kojim operativnim uslovima se izvršavaju agenti i determinističke komande.

Agent provider određuje koji AI agent se koristi.

Ta dva koncepta moraju ostati nezavisna.

## Provider model

FlowOS podržava konceptualno najmanje sljedeće environment providere:

- `HOST`
- `DOCKER`
- budući `REMOTE`

Početna implementacija koristi `HOST`.

Docker support se dodaje nakon stabilizacije osnovnog Execution Engine lifecyclea.

## HOST provider

HOST znači da se proces izvršava direktno na korisnikovom operativnom sistemu.

HOST execution ne znači rad nad glavnim working treejem.

FlowOS-managed AFK rad i dalje mora koristiti dedicated branch i dedicated worktree definisane ADR-004 odlukom.

## Docker provider

Docker predstavlja dodatni sloj process i filesystem izolacije.

Docker nije obavezna zavisnost FlowOS-a niti osnova njegovog domain modela.

ExecutionWorkspace može birati Docker environment kada execution policy to zahtijeva ili korisnik to odabere.

## Provider odgovornost

ExecutionEnvironmentProvider je odgovoran za operativne primitive kao što su:

- priprema environmenta;
- izvršavanje komande;
- streaming stdout/stderr rezultata;
- interaktivno izvršavanje kada provider to podržava;
- prekid aktivnog procesa;
- identifikovanje realnog runtime stanja;
- cleanup environmenta.

Provider ne odlučuje koji agent treba pokrenuti niti kojim redoslijedom se izvršavaju implementacija, verifikacija i review.

Tim workflowom upravlja `ExecutionOrchestrator`.

## AgentProvider nezavisnost

`AgentProvider` i `ExecutionEnvironmentProvider` mogu se kombinovati nezavisno.

Primjeri:

- Claude Code + HOST
- Codex + HOST
- Claude Code + DOCKER
- Codex + DOCKER

Dodavanje novog environment providera ne smije zahtijevati izmjene Claude/Codex provider implementacije.

Dodavanje novog AI agenta ne smije zahtijevati izmjene HOST/Docker provider implementacije.

## Warm environment

ExecutionEnvironment po defaultu pripada životnom ciklusu ExecutionWorkspace-a, a ne pojedinačnom AgentRun-u.

Isti environment može sekvencijalno izvršavati:

- AgentRun;
- VerificationRun;
- novi AgentRun;
- ReviewRun;
- determinističke komande.

Time dependencies, build artefakti i runtime stanje mogu ostati dostupni kroz više execution koraka.

## Filesystem policy

Sandboxed provider po defaultu dobija pristup samo resursima potrebnim konkretnom ExecutionWorkspace-u.

Dedicated task worktree može biti dostupan za read/write.

Dodatni host resursi moraju biti eksplicitno dozvoljeni.

FlowOS po defaultu ne smije izlagati sandboxu:

- korisnički home direktorij;
- SSH credentials;
- ostale projekte;
- kompletan filesystem;
- Docker socket;
- credential store;
- druge osjetljive resurse.

## Secrets policy

Secrets se environmentu daju eksplicitno prema potrebama konkretnog taska.

FlowOS ne mountuje kompletne credential direktorije samo zato što je potreban pojedinačni credential.

Secret injection mora biti moguće evidentirati bez zapisivanja same secret vrijednosti u normalne logove.

## Network policy

Provider arhitektura mora omogućiti buduće execution policy režime kao što su:

- bez mreže;
- puna dozvoljena mreža;
- ograničena mreža.

Network policy ne mora biti kompletno implementiran u prvoj verziji HOST providera.

## Resource policy

Sandbox provider mora omogućiti buduće ograničenje resursa kao što su:

- CPU;
- RAM;
- execution timeout.

Scheduler će kasnije moći koristiti ove podatke pri odlučivanju koliko workspaceova može biti aktivno paralelno.

## Streaming

ExecutionEnvironmentProvider mora podržavati streaming execution outputa dovoljan za:

- live GUI prikaz;
- heartbeat/activity detection;
- idle timeout;
- audit log;
- procesnu dijagnostiku.

Batch rezultat tek nakon završetka procesa nije dovoljan za FlowOS-managed AgentRun.

## Recovery

Provider mora omogućiti FlowOS-u da nakon restarta servisa utvrdi stvarno runtime stanje.

Trajno stanje ExecutionWorkspace-a mora sadržavati provider tip i relevantni runtime identitet potreban za reconciliation.

FlowOS ne vjeruje slijepo stanju zapisanom u bazi nego ga nakon prekida poredi sa stvarnim stanjem procesa/environmenta.

## Redoslijed implementacije

Prva implementacija:

`HOST provider → stabilan Execution Engine → Docker provider`

Docker se ne uvodi istovremeno sa osnovnim AgentRun/process lifecycleom kako bi se izbjeglo miješanje problema orchestrationa sa problemima container infrastrukture.