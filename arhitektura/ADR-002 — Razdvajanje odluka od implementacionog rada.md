# ADR-002 — Razdvajanje odluka od implementacionog rada

## Odluka

FlowOS razlikuje dvije osnovne vrste radnih jedinica:

1. `DecisionItem`
2. `ImplementationTask`

One mogu dijeliti zajednički koncept `WorkItem`, ali imaju različitu semantiku, životni ciklus i kriterijume završetka.

## DecisionItem

`DecisionItem` predstavlja pitanje, neizvjesnost ili preduslov koji mora biti razriješen prije nego što se može pouzdano definisati implementacija.

Njegov rezultat nije production kod nego eksplicitna odluka, utvrđena činjenica ili završen preduslov.

Podržani tipovi su:

- `DISCUSSION`
- `RESEARCH`
- `PROTOTYPE`
- `MANUAL_TASK`

Predloženi statusi:

- `UNRESOLVED`
- `READY`
- `IN_PROGRESS`
- `BLOCKED`
- `RESOLVED`
- `DISCARDED`

`RESOLVED` znači da pitanje više nije otvoreno i da postoji zabilježena odluka ili činjenica zajedno sa relevantnim dokazima.

DecisionItem može imati zavisnosti od drugih DecisionItem-a.

Skup trenutno neriješenih i neblokiranih DecisionItem-a predstavlja decision frontier.

## ImplementationTask

`ImplementationTask` predstavlja već dovoljno definisan posao koji agent ili čovjek može izvršiti.

ImplementationTask sadrži:

- cilj rada;
- acceptance kriterijume;
- zavisnosti;
- risk level;
- execution policy;
- vezu sa relevantnim specifikacijama i odlukama.

Implementacioni task može biti povezan sa agentom, branchom, worktreejem, ExecutionWorkspaceom, VerificationRun-om, ReviewRun-om i EvidenceBundle-om.

## Veza

ImplementationTask može sadržati reference `derived_from` prema DecisionItem zapisima iz kojih je nastao.

Time FlowOS čuva trag:

`pitanje → odluka → specifikacija → implementacioni task → kod → verifikacija → prihvatanje`.

## Postojeći Plan model

Postojeći `Plan` / `PlanItem` sistem neće biti zamijenjen bez dodatne analize.

Po trenutnoj procjeni, `PlanItem` je semantički bliži `ImplementationTask` nego `DecisionItem`, pa će se postojeći planski model prvenstveno evoluirati prema implementacionom grafu.

Decision sistem će se modelirati kao zaseban domain, vjerovatno kroz:

- `DecisionMap`
- `DecisionItem`
- `DecisionDependency`
- `DecisionResolution`

## Pravilo korištenja

Decision Map nije obavezna faza svakog zadatka.

Ako su cilj, ponašanje i acceptance kriterijumi već dovoljno jasni, rad može direktno postati ImplementationTask.

DecisionItem se koristi samo kada postoji stvarna neizvjesnost koja blokira kvalitetnu implementaciju.

## Prototype pravilo

Prototype nije razvojna faza.

Prototype je alat za razrješavanje DecisionItem-a kada je određenu odluku jeftinije i pouzdanije provjeriti konkretnim artefaktom nego dodatnom tekstualnom raspravom.

Prototype je throwaway artefakt i ne smatra se production implementacijom.