# ADR-004 — Git ownership, worktree izolacija i integracija

## Odluka

FlowOS je vlasnik Git execution infrastrukture za FlowOS-managed rad.

AI agent koristi execution workspace koji mu FlowOS dodijeli, ali ne upravlja lifecycleom brancha, worktreea niti integracije.

## Dedicated worktree

Svaki FlowOS-managed AFK `ImplementationTask` mora koristiti:

- dedicated Git branch;
- dedicated Git worktree.

Direktan AFK rad nad glavnim korisničkim working treejem nije dozvoljen.

## Git ownership

FlowOS je odgovoran za:

- kreiranje brancha;
- izbor base brancha;
- evidentiranje base commita;
- kreiranje worktreea;
- praćenje Git stanja;
- procjenu mergeabilityja;
- integration workflow;
- cleanup worktreea i privremenih branchova.

Agent ne kreira niti bira execution branch kao dio svog implementacionog rada.

## Base commit

Pri kreiranju ExecutionWorkspace-a FlowOS trajno evidentira `base_commit`.

Base commit predstavlja fiksnu početnu tačku execution runa i koristi se za:

- računanje kompletnog diff-a;
- changed-file evidence;
- code review;
- conflict detection;
- integraciju.

Promjena target brancha tokom rada agenta ne mijenja base commit aktivnog workspacea.

## Agent commits

Agent smije praviti commitove unutar dodijeljenog brancha.

Agentov commit predstavlja rezultat implementacionog rada, ali ne predstavlja automatsko prihvatanje niti integraciju.

FlowOS ne tretira postojanje commita kao dokaz semantičke ispravnosti.

## Dirty workspace

Ako AgentRun završi sa necommitovanim promjenama, ExecutionWorkspace prelazi u `DIRTY` ili ekvivalentno eksplicitno stanje.

FlowOS mora sačuvati najmanje:

- modified files;
- staged changes;
- unstaged changes;
- untracked files.

Dirty workspace se ne briše niti integriše dok stanje nije razriješeno.

FlowOS u početnoj implementaciji ne pravi automatski završni commit u ime agenta.

## Writer ownership

Jedan ExecutionWorkspace može imati najviše jedan aktivni writer AgentRun.

Istovremeni Claude/Codex ili drugi writer agenti ne smiju mijenjati isti worktree.

Paralelizacija coding rada ostvaruje se kroz različite ExecutionWorkspace instance.

Read-only ili review procesi mogu koristiti workspace prema posebnom policyju.

## Integration authority

AI agent ne smije samostalno:

- mergeovati svoj branch u target branch;
- pushovati direktno u zaštićeni target branch;
- rebaseovati aktivni workspace na noviji target branch bez FlowOS-controlled workflowa;
- mijenjati branch izvan dodijeljenog execution prostora.

Integracijom upravlja FlowOS kroz poseban integration workflow nakon potrebnih verification, review i human gate koraka.

## Acceptance i integration

Prihvatanje rezultata i Git integracija predstavljaju dva različita stanja.

`ACCEPTED` znači da je korisnik prihvatio rezultat ImplementationTask-a.

Poseban integration status prati Git stanje, na primjer:

- `NOT_INTEGRATED`
- `INTEGRATING`
- `INTEGRATED`
- `CONFLICTED`

Task može biti prihvaćen, a da integracija još nije završena.

## Target branch changes

Ako se target branch promijeni nakon kreiranja ExecutionWorkspace-a, aktivni workspace se ne rebazira niti automatski osvježava tokom rada agenta.

Promjena target brancha procjenjuje se tek u pre-integration fazi.

Konflikt ili nekompatibilnost vodi u eksplicitni integration/conflict workflow.

## Cleanup

ExecutionWorkspace može biti automatski očišćen tek kada su ispunjeni svi uslovi:

- nema aktivnih procesa;
- nema necommitovanih promjena;
- nema neriješenih konflikata;
- potrebni evidence artefakti su trajno sačuvani;
- rezultat je integrisan ili eksplicitno odbačen;
- workspace više nije potreban za recovery.

## Attribution

Za FlowOS-managed dedicated worktree rad atribucija promjena smatra se determinističkom.

Heuristička atribucija ostaje potrebna za external ili shared-working-tree sesije koje FlowOS samo prati.

Time se razlikuju:

`MANAGED_WORKTREE → deterministic attribution`

i

`EXTERNAL_SHARED_TREE → heuristic attribution`.