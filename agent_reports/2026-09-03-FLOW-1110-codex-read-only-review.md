# FLOW-1110 — Codex nezavisni read-only review

## Status izvještaja

Ovo je istorijski review originalne implementacije
`5c44b507098866abd0c3ecadd80ccd1760d1072f` na tadašnjem branch HEAD-u
`3dd7cd27c93c52f66280bb586bfbaf19a5ec5c20`.

Nakon završetka ovog reviewa branch je napredovao i dobio fix commit
`44bcd91`. Ovaj dokument nije review tog fixa i ne smije se koristiti kao
verdikt za trenutni branch HEAD.

## Datum

2026-09-03

## Agent / uloga

Codex — nezavisni reviewer; review-only, bez implementacije fixa.

## Review target

- Branch: `task/FLOW-1110-safe-worktree-identity`
- Reviewed branch HEAD: `3dd7cd27c93c52f66280bb586bfbaf19a5ec5c20`
- Reviewed implementation: `5c44b507098866abd0c3ecadd80ccd1760d1072f`
- Baseline: `66320730f8383c2ea7c247cec2c0b9310b0f79a4`

## Verdict

**BLOCK**

## Potvrđeno

- Branch HEAD i implementation parent odgovarali su očekivanim SHA vrijednostima.
- Implementation commit mijenjao je samo četiri deklarisana fajla.
- Exact canonical poređenje zatvorilo je `FLOW-1`/`FLOW-10` prefix collision.
- `Path.is_relative_to()` pravilno je razlikovao `worktrees/FLOW-1` od
  `worktrees-old/FLOW-1`; managed root sam po sebi namjerno nije worktree.
- Trailing i mixed separator, `..` i Windows case varijante canonicalizovane
  su kako je očekivano.
- Unknown, main i unmanaged worktree nisu prolazili cleanup ni sa `force=True`.
- Project A service nije nalazio Project B worktree u svom `git worktree list`;
  produkcijski probe je bio fail-closed i Project B worktree je preživio.
- Session i conflict guardovi ostali su bezuslovni. Dirty i retention mogli su
  se zaobići samo postojećim namjernim `force=True` ponašanjem.
- Nije pronađen `is_main` consumer kojem je potrebna razlika između stvarnog
  main worktreeja i unmanaged linked worktreeja.

## Findings

### FLOW-1110-CX-01

- **Severity:** BLOCKER
- **Location:** `src/flowos/service/services/worktrees/service.py:392-415` i
  `src/flowos/service/services/worktrees/service.py:240-249`
- **Claim:** Cleanup je validirao canonical identitet jednog worktreeja, ali je
  zatim Git-u slao originalni caller path. Originalni path mogao je imati
  drugačiju filesystem/Git interpretaciju i uzrokovati wrong-target remove.
- **Evidence:** U izolovanom temp repou registrovana su dva worktreeja: vanjski
  `A/worktrees/RELATIVE` i ugniježđeni `A/repo/worktrees/RELATIVE`. Uz process
  CWD `A`, poziv `cleanup("worktrees/RELATIVE", force=True)` canonicalizovan je
  prema process CWD-u i validirao vanjski worktree. `_git()` je istu relativnu
  putanju izvršio sa CWD `A/repo`, pa je Git uklonio ugniježđeni worktree.
  Poslije poziva vanjski je postojao i ostao registrovan, dok je ugniježđeni
  bio uklonjen i deregistrovan.
- **Evidence:** Nezavisni junction TOCTOU probe dao je isti sigurnosni ishod.
  Alias je pri validaciji pokazivao na `TOCTOU-1`; neposredno prije Git poziva
  retargetovan je na `TOCTOU-2`. Cleanup je uspješno uklonio `TOCTOU-2`, dok je
  validirani `TOCTOU-1` ostao.
- **Expected:** Worktree potvrđen identity provjerom mora biti jedini worktree
  koji destructive poziv može ukloniti.
- **Actual:** Validirani worktree ostao je, a drugi registrovani worktree bio je
  uklonjen.
- **Recommended action:** Destructive poziv vezati za tačno registrovani
  `WorktreeInfo.path` dobijen matchom i dodati regression testove za
  relative-CWD mismatch i alias/TOCTOU, pa ponoviti nezavisni review.

## Path identity

- `_canonical_key()` je koristio process CWD za relativne ulaze, dok je
  `_git()` koristio repository CWD. Ta dva namespacea nisu nužno ista.
- Postojeće apsolutne putanje, trailing separator, mixed separator i Windows
  case radili su pravilno.
- Nepostojeća putanja koristila je lexical canonicalization.
  `GHOST\\..\\FLOW-10` canonicalizovan je kao `FLOW-10`, a Git je prihvatio tu
  reprezentaciju.
- POSIX `normcase` ostaje case-sensitive, što odgovara standardnoj Python
  semantici.
- `_is_within(child, parent)` daje `True` samo za stvarnog potomka;
  `child == parent` daje `False`, što odgovara managed-worktree semantici.

## Project binding

- Produkcijski tok koristio je
  `Worktree.project_id -> Project.repo_path -> WorktreeService(project.repo_path)`.
- DB Worktree projekta A sa apsolutnom putanjom worktreeja projekta B nije
  prošao exact match u Git listi projekta A.
- Project B worktree nije uklonjen.
- Relativan ili alias DB path ostao je opasan zbog findinga FLOW-1110-CX-01.

## Force semantics

- `force=True` više nije zaobilazio negativan `can_cleanup`.
- Unknown, main, unmanaged i conflict zaštite ostale su hard guardovi.
- Force je i dalje namjerno zaobilazio dirty i retention policy u Manageru i
  dodavao Git `--force`.

## Original caller path risk

- Wrong-target remove je reproduciran.
- Relativni path se različito razrješavao između process CWD-a i Git repository
  CWD-a.
- Junction retarget između identity provjere i Git poziva reproducirao je
  TOCTOU wrong-target remove.
- Trenutno ponašanje imalo je dokazanu sigurnosnu posljedicu; registered matched
  path mora biti autoritet za destructive poziv.

## `is_main` semantika

- `is_main` je efektivno značio „nije FlowOS-managed“.
- Consumere su činili cleanup guard, retention status i API prikaz/listanje.
- Nije pronađen consumer kojem je bila potrebna bukvalna razlika main naspram
  unmanaged linked worktreeja.
- Nije pronađena regresija iz ove semantičke promjene.

## Test quality

- `test_prefix_collision_no_match` direktno je hvatao originalni
  `FLOW-1`/`FLOW-10` bug.
- `test_wrong_prefix_never_removes_other_tree` spyjem je potvrđivao da remove
  nije pozvan za prefix mismatch.
- `test_managed_root_sibling_not_included` direktno je hvatao
  `worktrees`/`worktrees-old` problem.
- Windows case test imao je stvarnu vrijednost i izvršen je na Windowsu.
- `test_manager_cleanup_uses_project_repo_path` dokazivao je samo constructor
  binding i prosljeđivanje putanje. `FakeService.cleanup()` uvijek je
  uspijevao, pa test nije dokazivao project isolation.
- Nijedan od 12 testova nije pokrivao neslaganje process/Git CWD-a, original
  caller path poslije matcha ili junction TOCTOU.

## Test execution

```text
python -m pytest tests/unit/test_worktree_identity.py -q
12 passed in 1.58s

python -m pytest tests/integration/test_worktree_isolation.py tests/integration/test_worktree_verify_redaction.py -q
4 passed, 1 warning in 14.04s
```

## Full verify

```text
python scripts/verify.py
560 passed, 1 warning in 151.84s (0:02:31)
Prošlo: 8/8
[PASS] VERIFIKACIJA PROŠLA
```

Passing suite nije pokrivao dokazani wrong-target scenario.

## GitNexus / blast radius

Direktni cleanup tok rekonstruisan je kao:

```text
HTTP cleanup_worktree
-> WorktreeManager.cleanup_worktree
-> WorktreeService.cleanup
-> can_cleanup
-> _find_worktree
-> list_worktrees
-> _dict_to_info
```

Pogođeni scope bio je ograničen na worktree servis, Manager, HTTP cleanup tok i
relevantne testove. GitNexus indeks bio je vezan za baseline checkout, pa
post-change mapiranje task-worktree diffa nije korišteno kao dokaz.

## Repo mutation tokom reviewa

Tracked task worktree ostao je čist. Privremeni OS-temp Git repo i probe
skripta bili su uklonjeni; završna provjera je dala
`probe_script_exists=False` i `leftover_count=0`.

## Preporuka u trenutku reviewa

**RETURN TO IMPLEMENTER**

Potrebna je nova nezavisna provjera fix commita `44bcd91`; ovaj istorijski
verdikt se ne prenosi automatski na izmijenjenu implementaciju.
