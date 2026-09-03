---
task_id: FLOW-1110
title: Siguran identitet worktree putanja
phase: GATE-A
risk: MEDIUM
risk_note: destructive worktree safety; elevated review rigor
coordinator: ChatGPT
implementer: Crush
reviewers:
  - ChatGPT
  - Codex
status: IMPLEMENTING
created_at: 2026-09-02
dependencies:
  - FLOW-1100
allowed_paths:
  - src/flowos/service/services/worktrees/service.py
  - src/flowos/service/services/worktrees/manager.py
  - tests/unit/test_worktree_identity.py
  - agent_reports/FLOW-1110-task-contract.md
  - agent_reports/2026-09-02-FLOW-1110-crush.md
forbidden_paths:
  - src/flowos/service/controllers/**
  - src/flowos/gui/**
  - alembic/**
  - migrations/**
  - pyproject.toml
  - README.md
  - CLAUDE.md
  - AGENTS.md
gitnexus_required: true
adversarial_required: true
baseline_sha: 66320730f8383c2ea7c247cec2c0b9310b0f79a4
branch: task/FLOW-1110-safe-worktree-identity
worktree: ../FlowOS-worktrees/FLOW-1110-safe-worktree-identity
---

# OBJECTIVE

Napraviti deterministički, canonical path identity za managed worktree odluke
tako da textual prefix nikada nije identitet.

# NON-GOALS

- redesign WorktreeManagera
- DB migration
- HTTP contract promjena
- GUI
- Session redesign
- retention redesign
- branch naming redesign
- novi worktree framework
- general-purpose filesystem abstraction

# PRE-CHANGE FACTS (potvrđeno na baseline-u)

- `WorktreeService._find_worktree()` koristi `wt.path == path or wt.path.startswith(path)` —
  textual prefix identitet. `FLOW-1` pogrešno identifikuje `FLOW-10`.
- `WorktreeService.list_flowos_worktrees()` koristi `startswith` nad normalizovanim
  slash stringovima. Sibling `.../worktrees-old/FLOW-1` je pogrešno uključen u
  managed root `.../worktrees`.
- `WorktreeService._dict_to_info()` koristi `startswith` za `is_main` detekciju — isti
  textual prefix bug.
- `WorktreeManager.cleanup_worktree()` koristi `wt.worktree_path` kao `repo_path` za
  `WorktreeService`, umesto canonical `Project.repo_path`.
- `WorktreeService.cleanup()` ima `if not can and not force:` — `force=True` može
  zaobići negativan `can_cleanup` rezultat (uključujući hard identity guard).

# ACCEPTANCE KRITERIJI

- exact canonical path match (bez prefix collision)
- managed root membership = structural containment
- project identity kroz `Worktree.project_id -> Project.repo_path`
- `force=True` ne zaobilazi hard identity/scope zaštite
- fail-closed za unknown/unmanaged/main
- dirty/retention policy ostaje nepromenjena
- nema regresije postojećeg lifecycle testa
