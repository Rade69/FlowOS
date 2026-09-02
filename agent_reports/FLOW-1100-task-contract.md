---
task_id: FLOW-1100
title: Uvođenje kanonskih razvojnih dokumenata
phase: BOOT-0
risk: LOW
coordinator: ChatGPT
implementer: Pi
reviewers:
  - ChatGPT
status: IMPLEMENTING
created_at: 2026-09-02
dependencies: []
allowed_paths:
  - docs/FlowOS-novi-objedinjeni-detaljan-plan-razvoja-v4.4-2026-09-02.md
  - docs/FlowOS-kanonski-plan-daljeg-razvoja-i-agentskog-rada-v1.0.md
  - agent_reports/FLOW-1100-task-contract.md
  - agent_reports/2026-09-02-FLOW-1100-pi.md
forbidden_paths:
  - README.md
  - CLAUDE.md
  - AGENTS.md
  - src/**
  - tests/**
  - scripts/**
gitnexus_required: false
adversarial_required: false
baseline_sha: 08f915c08c2fb3eb4eb2a978faca7d6b1d4781e5
branch: task/FLOW-1100-canonical-docs
worktree: ../FlowOS-worktrees/FLOW-1100-canonical-docs
---

OBJECTIVE:
Dodati već odobreni v4.4 roadmap i canonical execution plan u repo bez izmjene runtime/source koda.

OUT OF SCOPE:
- README/CLAUDE/AGENTS alignment
- source kod
- testovi
- FLOW-1110
- stari roadmap cleanup
- uklanjanje deprecated dokumenata

ACCEPTANCE:
1. oba canonical dokumenta postoje na tačnim target putanjama;
2. njihov sadržaj odgovara dostavljenim source dokumentima;
3. nema source/runtime izmjena;
4. exact diff sadrži samo četiri dozvoljena fajla;
5. task branch je pushovan;
6. main nije mijenjan.

GITNEXUS:
NOT_REQUIRED — docs-only task, bez shared symbol/runtime promjene.
