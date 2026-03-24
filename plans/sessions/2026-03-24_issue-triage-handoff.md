# Next Session Handoff — Issue Triage and Resolution

**Date:** 2026-03-24
**Status:** READY FOR NEXT SESSION
**Primary goal:** Triage all open issues, define test criteria for each, and resolve them

---

## Current State

### What just shipped (Session 2026-03-24c)
- 28 PRs merged across Browser Phase 4 + Platform-8b + convention sweep
- Browser Phase 4 (SP-4-01 export/replay): COMPLETE
- Platform-8b (SP-4-06 audit trail): library complete, runtime wiring pending
- Session plan: `plans/sessions/2026-03-24_overnight-autonomous-run.md`

### Open PRs
- #1576 (ops JSON modes) — in CI, should auto-merge
- #1579 (test fixture consolidation rebase) — in CI, should auto-merge

### Steward State
- All 12 worker lanes cleared and idle
- Ops and review crons killed, contexts cleared
- Orchestrator inbox acked
- No dispatched task packets

---

## Primary Goal: Issue Triage and Resolution

Triage all 15 open issues. For each one:
1. Read the issue
2. Define explicit pass/fail test criteria (per #1581 policy)
3. Classify: fix now / defer / close
4. If fixing: create task packet with test criteria in the description
5. Dispatch to appropriate lane

### New Policy (#1581)
Every task packet MUST include test criteria before dispatch. Not just
"run make check" but specific, verifiable conditions. The orchestrator
should refuse to dispatch without them.

---

## Open Issues — Pre-Triage

### Tier 1: Autonomous Operations Hardening (fix before next fleet run)

| # | Title | Scope | Test Criteria (draft) |
|---|-------|-------|----------------------|
| **#1571** | Messaging system re-evaluation | Architecture/design | Produce design doc with bilateral messaging spec |
| **#1569** | Orchestrator must poll inbox | Orchestrator check-in skill | Send test message → verify orchestrator reads it within 1 cycle |
| **#1568** | Merge-conflict stall detection | Orchestrator monitoring | Open PR with conflict → verify orchestrator detects within 2 cycles |
| **#1572** | Idle auto-shutoff after 90min | Orchestrator session mgmt | Simulate 90min idle → verify shutoff triggers |
| **#1570** | Bilateral messaging tests | Test infrastructure | Smoke test: send+receive across all lane types in <30s |
| **#1580** | /clear doesn't kill crons | Lane shutdown procedure | /park a lane → verify CronList returns empty |
| **#1581** | Test criteria policy | Process/docs | Verify CLAUDE.md, templates, and dispatch enforce criteria |

### Tier 2: Platform-8b Completion

| # | Title | Scope | Test Criteria (draft) |
|---|-------|-------|----------------------|
| **#1573** | Audit trail not runtime-wired | Orchestrator + audit_trail.py | Send Telegram msg → verify entry in remote_exchanges.jsonl |

### Tier 3: Convention Follow-ups

| # | Title | Scope | Test Criteria (draft) |
|---|-------|-------|----------------------|
| **#1578** | Follow-up for PR #1575 | scripts/internal/export_hosted_decisions.py | TBD — read issue |
| **#1577** | Export ordering assertion | tests/ | TBD — read issue |
| **#1574** | Browser checkpoint test count | plans/browser_game/ | Checkpoint says "all tests pass" not exact count |

### Tier 4: Infrastructure (defer unless idle capacity)

| # | Title | Scope | Notes |
|---|-------|-------|-------|
| #1521 | Telegram plugin unreliable | External plugin | Needs user smoke test |
| #1337 | Dashboard auto-refresh | ops/dashboard.py | Partially addressed by #1534 |
| #1289 | Transport consolidation | Assessment only | Defer |
| #1288 | Comment ingestion bridge | ops/ | Defer |

---

## Execution Model

### Phase 1: Triage Pass (orchestrator-only, no dispatch)
1. Read each issue
2. Define test criteria
3. Update issue with test criteria comment
4. Classify into tiers
5. Identify file-scope overlaps

### Phase 2: Tier 3 Quick Fixes (parallel dispatch)
Small convention fixes with clear test criteria. 3-4 lanes, parallel.
These are easy wins that reduce the issue count fast.

### Phase 3: Tier 1 Design Work
- #1571 messaging re-evaluation needs a design doc first, not code
- #1581 policy needs CLAUDE.md + template updates
- #1580 needs a /park skill or shutdown procedure

### Phase 4: Tier 1 Implementation
Once design is locked:
- #1569 inbox polling (orchestrator check-in skill update)
- #1568 merge-conflict detection (orchestrator monitoring update)
- #1572 idle auto-shutoff
- #1570 bilateral messaging tests

### Phase 5: Tier 2 (Platform-8b wiring)
Only after Tier 1 is solid:
- #1573 runtime wiring of audit trail
- Depends on Telegram being functional (#1521) for end-to-end proof

---

## Monitoring Improvements for This Session

Based on overnight findings, the orchestrator MUST:

1. **Poll inbox every check-in:** `uv run python scripts/internal/ops.py inbox --lane orchestrator`
2. **Check PR mergeable status:** `gh pr view N --json mergeable` for every open PR
3. **Track last_meaningful_change:** If nothing changes for 30 minutes, investigate (don't just keep polling)
4. **Check ops pane:** Include ops lane in every status capture
5. **Verify facts before stating them:** Don't guess token counts, PR counts, or completion status

---

## Hard Constraints

- Do not start Platform-9a until Platform-8b wiring (#1573) is proven
- Do not start Telegram proving until #1521 is resolved
- Every dispatched task MUST have test criteria (#1581)
- One writer per overlapping file set
- Defer #1288, #1289 unless all tiers 1-3 are complete

---

## What To Read At Session Start

1. This handoff
2. `plans/sessions/2026-03-24_overnight-autonomous-run.md` (for context on what shipped)
3. MEMORY.md (updated with session results)
4. Each open issue (15 total) — read before triaging
