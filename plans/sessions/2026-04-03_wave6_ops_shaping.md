# Wave 6 Fleet Operations — Shaping Report

**Date:** 2026-04-03
**Lane:** analyst-b
**Task Packet:** `7bac78a9a37e`
**Status:** COMPLETE

## Summary

Shaped four fleet operations improvements for Wave 6 dispatch. Three issues
received dispatch-ready implementation briefs posted as issue comments. One
item (runtime relocation) received a deferral recommendation with cost analysis.

## Items Shaped

### 1. #2251 — Orchestrator Delegation Defaults

**Problem:** The orchestrator does analysis work that should be delegated to
analyst lanes — reading source files, drafting root cause analysis, writing
experiment designs.

**Root cause:** The orchestrator prompt says "don't implement" but doesn't
prevent *analysis*. All investigation guidance is advisory, not structural.

**Shaped output:** [Issue comment](https://github.com/Questuart/Bid-Euchre/issues/2251#issuecomment-4185233138)

**Implementation brief:**
- 1 file: `.claude/agents/steward-orchestrator.md`
- 3 changes: delegation-first rule, analysis anti-patterns section, stronger routing language
- Single PR, docs-only CI path, <15 min author work

**Branch:** `ops/orchestrator-delegation-defaults`

---

### 2. #2257 — Analyst Issue-Comment Output Default

**Problem:** Analyst lanes default to committing markdown files and opening PRs
for research findings. This creates CI noise, merge conflicts, auto-merge races,
and git history clutter.

**Root cause:** The analyst reuses the author-lane start-task workflow. No
alternative delivery path exists for research-only tasks.

**Shaped output:** [Issue comment](https://github.com/Questuart/Bid-Euchre/issues/2257#issuecomment-4185235493)

**Implementation brief:**
- 3 files: the analyst agent config, the start-task skill, and the delegate-task skill
- Adds delivery mode section (issue-comment vs PR), analyst-specific start-task
  path, and `delivery_mode`/`parent_issue` fields to task packets
- Single PR, docs-only CI path

**Branch:** `ops/analyst-issue-comment-default`

---

### 3. #2252 — Analyst Web Research Defaults

**Problem:** Analyst lanes only investigate the local codebase. WebSearch is
available but never prompted for.

**Root cause:** Zero mentions of WebSearch in the analyst prompt or any skill.
All investigation guidance points inward (repo state, plans, checkpoints).

**Shaped output:** [Issue comment](https://github.com/Questuart/Bid-Euchre/issues/2252#issuecomment-4185237379)

**Implementation brief:**
- 1 file: the analyst agent config
- Adds Research Protocol section with default web research steps, skip
  conditions, and search strategy guidance
- Updates Core Responsibilities to reference WebSearch explicitly
- Single PR, docs-only CI path, <15 min author work
- Follow-up `/research` skill (Option B) deferred to separate issue if warranted

**Branch:** `ops/analyst-web-research-defaults`

---

### 4. .claude/runtime Relocation to .ops_runtime

**Problem:** `.claude/runtime/` mixes ephemeral operational state (task queue,
events, sessions) with configuration (settings, skills, rules, agents, hooks)
inside the `.claude/` directory.

**Blast radius analysis:**

| Category | Files | Occurrences |
|----------|-------|-------------|
| Python (`src/`, `scripts/`) | 30 | 95 |
| Shell scripts (`.claude/hooks/`, etc.) | 11 | 20 |
| Markdown (docs, plans, skills) | 30+ | 91 |
| JSON (`.claude/settings.json`) | 1 | 4 |
| `.gitignore` | 1 | 11 |
| **Total** | **73+** | **221+** |

**Key constants (would need updating):**
- `src/bid_euchre/ops/status.py` — `DEFAULT_RUNTIME_DIR`
- `src/bid_euchre/ops/control_plane.py` — `DEFAULT_RUNTIME_DIR`
- `src/bid_euchre/ops/alert_push.py` — `DEFAULT_RUNTIME_DIR`
- `src/bid_euchre/ops/task_queue.py` — `DEFAULT_TASK_QUEUE_DIR`
- `src/bid_euchre/ops/message_bus.py` — `DEFAULT_BUS_DIR`
- `src/bid_euchre/ops/events.py` — `DEFAULT_EVENTS_DIR`
- `src/bid_euchre/ops/watchdogs.py` — 5 inline defaults

**Cost analysis (per measurement integrity standards):**

1. **Fix-now cost:**
   - 2-3 PRs of mechanical refactoring
   - Update ~10 Python constants + ~11 shell scripts + gitignore + settings.json
   - All 16+ persistent worktrees need coordinated update (symlink or path change)
   - Estimated: 2-4 hours of author time + coordination overhead

2. **Fix-later cost:**
   - Same base cost as fix-now
   - Plus: any new code written between now and then adds more references
   - Compounding rate: ~2-3 new references per week (estimated from recent PRs)
   - No crosswalk/recalibration needed (path change, not behavioral)

3. **Never-fix cost:**
   - Ongoing minor confusion about `.claude/` directory purpose
   - `.gitignore` complexity persists (11 fine-grained exception lines)
   - Permission model entanglement (`.claude/runtime/**` auto-accept covers both config and state)
   - Functional impact: **minimal** — the system works correctly today

**Recommendation: DEFER** — The blast radius (73+ files, 221+ occurrences) is
disproportionate to the functional benefit. The system works correctly with the
current path. The Python code already uses a `DEFAULT_*_DIR` constant pattern
with override parameters, so the actual behavioral risk is low. If pursued later,
the approach should be:

1. Introduce a central `OPS_RUNTIME_ROOT` env var / constant in a new
   paths module under `src/bid_euchre/ops/`
2. Update Python constants to reference it (mechanical, ~10 files)
3. Update shell scripts and hooks (~11 files)
4. Update `.gitignore` and `.claude/settings.json`
5. Do NOT update historical docs/plans — they reference paths at time of writing
6. Coordinate across all active worktrees (biggest risk)

File as a backlog issue with `enhancement` + `fix:process` labels if the user
wants to track it for a future low-activity window.

## Dispatch Recommendations

All three issue-shaped items can be dispatched in parallel to separate author
lanes — they have disjoint file scopes:

| Issue | Branch | File Scope | Overlap Risk |
|-------|--------|-----------|--------------|
| #2251 | `ops/orchestrator-delegation-defaults` | `.claude/agents/steward-orchestrator.md` | None |
| #2252 | `ops/analyst-web-research-defaults` | `.claude/agents/steward-analyst.md` | **Low** — #2257 also touches this file |
| #2257 | `ops/analyst-issue-comment-default` | `.claude/agents/steward-analyst.md`, `.claude/skills/start-task/SKILL.md`, `.claude/skills/delegate-task/SKILL.md` | **Low** — #2252 also touches analyst agent config |

**Safe parallelism:** #2251 is fully independent. #2252 and #2257 both modify
the analyst agent config but touch different sections (Research Protocol vs
Delivery Modes). They can run in parallel if authors add to different sections,
but a sequential dispatch (merge #2252 first, then #2257) avoids rebase risk.

**Recommended dispatch order:**
1. #2251 (independent, single file) + #2252 (independent section of analyst prompt)
2. #2257 (after #2252 merges, to avoid rebase on the analyst agent config)

## Outcome

- [x] #2251 shaped — implementation brief posted as issue comment
- [x] #2257 shaped — implementation brief posted as issue comment
- [x] #2252 shaped — implementation brief posted as issue comment
- [x] Runtime relocation — cost analysis complete, DEFER recommended
- [x] Consolidated session plan written
