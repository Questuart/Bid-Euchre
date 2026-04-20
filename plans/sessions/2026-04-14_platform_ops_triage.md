# Platform & Ops Triage — Stabilization for Steward Extraction

**Date:** 2026-04-14
**Status:** DRAFT — awaiting operator review
**Scope:** Triage all open issues, stabilize the repo, and complete Platform-10
portability to enable steward extraction into the Fund repo.
**Goal:** Get the steward orchestration platform into a state where its core
(non-Bid-Euchre-specific) components can be extracted and reused in another
project.

---

## 1. Current State

### Governing Plan Status
- **Phases 0–4:** COMPLETE (Bootstrap → Remote Channel)
- **Phase 5+:** POSTPONED INDEFINITELY (operator decision 2026-04-01)
- **Platform-10 groundwork:** 5 PRs shipped (ABCs, core extraction, adapter,
  ServiceProvider, contract tests — 2256 LOC). 4 PRs remain. Sub-plan SP-5-01 exists.
- **Platform-11 scope lock:** Exists. Sub-plan SP-5-02 drafted. No groundwork shipped.
- **Platform-12/13:** Scope locks only. No sub-plans.

### Extraction Target
- **Source:** `src/bid_euchre/ops/` steward orchestration platform
- **Destination:** Fund repo (local machine)
- **Blocker:** 196 Bid-Euchre-specific coupling occurrences across 34 ops files.
  Platform-10 (SP-5-01) is the extraction seam — it separates core orchestration
  from repo-specific adapter code.
- **Extraction readiness after Platform-10:** Core interfaces, ServiceProvider,
  and adapter pattern will be clean. Remaining coupling will be cataloged in a
  machine-readable manifest with an audit script to track progress.

### Open Issue Inventory (29 issues)

| Category | Count | Issues | Extraction Relevance |
|----------|-------|--------|---------------------|
| Ops/platform | 5 | #2238, #2249, #2403, #2404, #2415 | HIGH — affects extracted code |
| Messaging revamp | (new) | Not yet filed | HIGH — message bus is core infra |
| Strategy bugs | 2 | #2626, #2627 | None — Bid-Euchre-specific |
| Browser game fixes/follow-ups | 7 | #2615, #2619, #2620, #2628, #2632, #2644, #2645 | None |
| Strategy experiments | 8 | #2634–#2641 | None |
| Strategy research | 3 | #1917, #2389, #2390 | None |
| Browser game features | 3 | #2131, #2185, #2229 | None |
| Strategy investigation | 1 | #2537 | None |

---

## 2. Issue-by-Issue Triage

### A. Ops/Platform Issues (5 open)

#### #2238 — Review lane stalls on permission prompt [bug]
**Filed:** 2026-04-03 | **Domain:** ops
**Problem:** Review lane blocks on permission gates during autonomous operation.
Causes PRs stuck in pending review, merge guard blocks.
**Current relevance:** HIGH — this hits every fleet session. The review lane is
the most common stall source.
**Recommendation:** **FIX** — bounded single-lane task. Likely needs permission
pattern additions to `.claude/settings.json` and/or review driver hardening.
**Staleness check:** May be partially addressed by PR #1982 (review stall fix)
and PR #1989 (runtime permission auto-accept). Needs analyst verification.

#### #2415 — Orchestrator needs reliable lane status introspection [enhancement]
**Filed:** 2026-04-04 | **Domain:** ops
**Problem:** `tmux capture-pane` + grep is fragile. Different tail depths show
different things. No standardized activity indicator across lanes.
**Current relevance:** HIGH — the orchestrator's situational awareness depends
on this. Every fleet-check cycle reinvents parsing logic.
**Recommendation:** **FIX** — design a standardized lane status protocol
(structured status line, or status file convention). Analyst shaping needed.

#### #2403 — Create /session-end skill [enhancement]
**Filed:** 2026-04-04 | **Domain:** ops
**Problem:** Session shutdown is manual multi-step (park ops, park review, park
authors, clear, write handoff). Error-prone.
**Current relevance:** MEDIUM — painful but infrequent (once per session).
**Recommendation:** **FIX** — skill authoring task, bounded scope. Could batch
with messaging revamp since both touch lane lifecycle.

#### #2404 — Enhance /away-mode with autonomous work + Telegram status loop [enhancement]
**Filed:** 2026-04-04 | **Domain:** ops
**Problem:** Away-mode doesn't auto-start autonomous work, doesn't push periodic
status updates, doesn't support escalation-only filtering.
**Current relevance:** MEDIUM — Telegram basics work. This is polish.
**Recommendation:** **DEFER** unless messaging revamp unlocks it naturally.
Away-mode already detects presence and pushes alerts.

#### #2249 — Evaluate Claude Code auto-accept + audit recent CC features [enhancement]
**Filed:** 2026-04-03 | **Domain:** ops
**Problem:** No systematic audit of Claude Code features that could eliminate
permission stalls and improve fleet operation.
**Current relevance:** LOW-MEDIUM — useful research but no guaranteed code output.
Permission stalls are better addressed directly (#2238).
**Recommendation:** **CLOSE or DEFER** — the specific permission stall is better
addressed by #2238. The broader feature audit is evergreen research that
doesn't need an issue tracking it.

### B. Messaging Revamp (New — Not Yet Filed)

**Problem:** The message bus is pull-only in practice. Lanes discover messages
via cron polling (up to 8-minute latency). Hooks and nudges exist in theory but
aren't reliably wired. Specific gaps:
- Task dispatch → inbox message arrives, but lane discovers it on next cron cycle
- Completion callbacks have same polling latency
- Escalations don't feel urgent (same cadence as routine)
- `tmux send-keys` nudge is brittle — collides with active work

**Recommendation:** **FILE ISSUE + ANALYST SHAPE** — this needs a design pass.
Key questions:
1. Which events should trigger push (hook-based) vs. poll (cron-based)?
2. What's the right interrupt mechanism for lanes? (file watch? signal? tmux hook?)
3. How does this interact with Platform-10 portability (message bus is core infra)?

### C. Strategy Bugs (2 open)

#### #2626 — Dealer overbids partner [fix:bug]
**Recommendation:** **FIX** — bounded strategy logic fix. Dispatch to platform author.

#### #2627 — Loner LOW void exploitation [fix:bug]
**Recommendation:** **FIX** — strategy play logic bug. Dispatch to platform author.

### D. Browser Game Fixes/Follow-ups (7 open)

| Issue | Description | Recommendation |
|-------|-------------|----------------|
| #2620 | Illegal bid suggestions + phantom hints (relabeled fix:bug) | **FIX** — user-visible bugs |
| #2619 | Migration robustness + illegal counterfactual logging | **FIX** — batch with #2632 |
| #2632 | PostgreSQL duplicate-column migration handling | **FIX** — batch with #2619 |
| #2628 | Backfill counterfactuals on Render DB | **VERIFY & CLOSE** — script shipped, confirm execution |
| #2615 | Test flake in mobile helper | **FIX** — low priority, quick |
| #2644 | Shared strategy instance mutable state | **FIX** — correctness issue |
| #2645 | Inconsistent export contract for counterfactuals | **FIX** — data integrity |

### E. Strategy Experiments (8 open: #2634–#2641)

All filed 2026-04-09. These are experiment design issues for GBT and Glutton
improvements. None are bugs — they're enhancement research.

**Recommendation:** **KEEP OPEN, DO NOT PRIORITIZE** — these are the backlog
for after operational issues are resolved. They'll need analyst shaping
individually when picked up.

### F. Strategy Research (3 open)

| Issue | Recommendation |
|-------|----------------|
| #1917 — Glutton revamp experiment design | **KEEP** — oldest open issue (Mar 27). Valuable but large. |
| #2389 — Glutton bid-context awareness | **KEEP** — research question, not actionable yet |
| #2390 — Unify bidding + play strategies | **KEEP** — architectural research, long-term |

### G. Browser Game Features (3 open)

| Issue | Recommendation |
|-------|----------------|
| #2131 — Enable Codex to play browser game | **KEEP** — fun but not priority |
| #2185 — AI suggested plays/bids | **PARTIALLY DONE** — PR #2617 shipped suggestions. Verify scope. |
| #2229 — Sim vs browser parity experiment | **KEEP** — valuable validation work |

### H. Investigation (1 open)

| Issue | Recommendation |
|-------|----------------|
| #2537 — StratBot defense losing ~1.22/hand | **KEEP** — research. May inform #2634–#2641 experiments. |

---

## 3. Governing Plan Reactivation — Extraction-First

### Decision: Reactivate Platform-10, Skip Platform-11/12/13

Platform-10 is the extraction seam. It separates core orchestration interfaces
from Bid-Euchre-specific adapter code. Without it, extracting the steward into
Fund means copying 34 tightly coupled files and untangling them in the target
repo. With it, extraction is: copy core/ + write a new adapter.

**Reactivate:** Platform-10 (SP-5-01, 4 PRs, ~6h, sub-plan exists and is detailed)
**Skip:** Platform-11 (skill learning), Platform-12/13 (cross-model, extraction proof)
**Rationale for skipping 12/13:** Platform-13 was "second-project extraction proof" —
but we're about to DO the extraction into Fund. The proof IS the extraction. No need
for a synthetic validation step.

### What to Run Outside the Governing Plan

The 5 open ops issues and the messaging revamp are operational improvements that
should ship as standalone PRs. They improve the extracted product quality but don't
need checkpoint overhead.

---

## 4. Proposed Execution Wave

### Wave Name: "Stabilize & Extract"

**Duration:** 2-3 fleet sessions
**Lane allocation:** 2-3 platform author lanes + analyst
**Exit criteria:** Platform-10 complete, quick-win bugs fixed, coupling manifest
produced, extraction into Fund unblocked.

### Phase 1: Quick Wins + Analyst Shaping (parallel)

**Immediate dispatches** (no analyst needed — bounded single-issue fixes):

| Track | Issues | Lane | Est. PRs |
|-------|--------|------|----------|
| **A: Strategy bugs** | #2626 (dealer overbids), #2627 (void exploitation) | author-a | 2 |
| **B: Browser bug** | #2620 (illegal bid suggestions + phantom hints) | brws-author-a | 1 |
| **C: Convention batch** | #2619+#2632 (migration robustness, batch together) | brws-author-b | 1 |
| **D: Correctness** | #2644 (shared strategy mutable state) | author-b | 1 |

**Analyst dispatch** (in parallel with above):

Route to `steward-analyst`:
1. **SP-5-01 freshness check** — verify Platform-10 sub-plan against current
   codebase (2 weeks of drift since postponement). Check all file paths, imports,
   and coupling counts still match.
2. **Messaging bus audit** — catalog all push vs. pull paths, identify where
   cron polling masks latency, recommend which events should be hook-driven.
   File a GitHub issue with findings.
3. **Extraction surface audit** — beyond Platform-10's scope, what else needs
   attention for Fund extraction? (tmux layout scripts, hook registration,
   skill files, cron primitives, Telegram adapter)
4. **Staleness checks** — verify #2238 (review stalls), #2185 (AI suggestions),
   #2628 (backfill execution) current status

### Phase 2: Platform-10 Completion (critical path)

Reactivate SP-5-01 after analyst freshness check. PR1 and PR2 are parallelizable:

| PR | Scope | Lane | Parallel? |
|----|-------|------|-----------|
| SP-5-01 PR1 | Lane topology extraction — move KNOWN_AUTHOR_LANES from hardcoded constants into adapter | author-a | Yes (with PR2) |
| SP-5-01 PR2 | ServiceProvider CLI migration — wire monitor/task/dispatch/controller through provider | author-b | Yes (with PR1) |
| SP-5-01 PR3 | Coupling manifest + audit script — document all remaining coupling, add regression test | author-a | After PR1+PR2 |
| SP-5-01 PR4 | Hook migration + cleanup — migrate hook callers to adapter imports | author-b | After PR3 |

**Key deliverable:** PR3's coupling manifest becomes the extraction checklist
for Fund. Every remaining coupling point is documented with severity
(hard-block, soft-coupling, cosmetic).

### Phase 3: Messaging & Remaining Fixes

After Platform-10 lands:

| Track | Scope | Lane | Est. PRs |
|-------|-------|------|----------|
| **Messaging revamp** | Hook-driven push for dispatch/completion/escalation events | author-a | 2-3 |
| **#2415** | Reliable lane introspection (informed by analyst design) | author-b | 1 |
| **#2403** | /session-end skill | flex-a | 1 |
| **#2645** | Export contract consistency | brws-author-a | 1 |
| **#2615** | Test flake fix | any idle | 1 |

### Phase 4: Extraction

After Phases 1-3 ship:
1. Run `audit_portability.py` to confirm coupling count is at threshold
2. Copy `src/bid_euchre/ops/core/` into Fund repo
3. Write Fund-specific adapter (equivalent to `adapters/bid_euchre.py`)
4. Wire ServiceProvider into Fund's entry points
5. Validate with contract tests (port from Bid-Euchre's 2256 LOC test suite)

### Phase 5: Post-Extraction Cleanup

| Action | Scope |
|--------|-------|
| Close #2249, #2404 | Operational friction resolved by messaging revamp |
| Close #2238 | If review stalls are fixed |
| Reassess Platform-11 | Does Fund need skill learning? Probably not initially |
| File extraction learnings | Document what the manifest missed for future extractions |

---

## 5. Issues to Close Now

| Issue | Reason |
|-------|--------|
| #2628 | Backfill script shipped (PR #2630). Verify execution, then close. |
| #2185 | Likely resolved by PR #2617. Analyst to confirm scope. |
| #2249 | Subsume into #2238 fix. Broader CC audit is evergreen, not issue-worthy. |

---

## 6. Summary Action Table

| Action | Issues/Items | Next Step | Phase |
|--------|-------------|-----------|-------|
| **Dispatch now** | #2626, #2627, #2620, #2619+#2632, #2644 | Immediate dispatch to author lanes | 1 |
| **Analyst shape** | SP-5-01 freshness, messaging audit, extraction surface, staleness checks | Route to steward-analyst | 1 |
| **Reactivate** | Platform-10 (SP-5-01, 4 PRs) | After analyst freshness check | 2 |
| **Fix after Platform-10** | Messaging revamp, #2415, #2403, #2645, #2615 | Dispatch after Phase 2 | 3 |
| **Verify & close** | #2628 (backfill ran?), #2185 (PR #2617 scope) | Analyst staleness check | 1 |
| **Close** | #2249 (subsume into #2238) | Immediate | — |
| **Defer** | #2404 (away-mode polish) | Revisit post-extraction | 5 |
| **Keep (backlog)** | #2634–#2641, #1917, #2389, #2390, #2537, #2131, #2229 | Future waves | — |
| **Skip** | Platform-11, 12, 13, 14 | Fund extraction IS the proof | — |

## 7. Extraction Readiness Checklist

Before attempting Fund extraction, all of these must be true:

- [ ] Platform-10 SP-5-01 PR1–PR4 merged
- [ ] `audit_portability.py` runs clean (coupling count at or below threshold)
- [ ] Coupling manifest (`PORTABILITY_MANIFEST.md`) reviewed
- [ ] Message bus works through ServiceProvider (not direct imports)
- [ ] Contract tests pass with mock adapter (proving core is adapter-agnostic)
- [ ] Quick-win bugs fixed (no known correctness issues in extracted code)

## Outcome

_(To be filled after execution)_
