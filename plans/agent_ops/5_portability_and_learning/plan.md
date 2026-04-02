# Phase 5: Portability and Learning

**Phase:** 5 (`5_portability_and_learning`)
**Status:** POSTPONED INDEFINITELY (2026-04-01 operator decision — platform work postponed to focus on browser game product. Phase 4 was the final delivered platform phase.)
**Governing plan:** `plans/agent_ops/governing_plan.md`
**Depends on:** Phase 3 (COMPLETE), Phase 4 (COMPLETE 2026-04-01)
**Created:** 2026-04-01

---

## Scope

Phase 5 covers two platform steps:

| Step | Platform | Description | Scope Lock |
|------|----------|-------------|------------|
| Platform-10 | Portability Layer | Complete core-vs-adapter split; migrate callers to ServiceProvider; document remaining coupling | Groundwork shipped (PRs #1807, #1813, #1817, #1950, #1954) |
| Platform-11 | Skill Learning Loop | Outcome-informed dispatch advisor; task type taxonomy; skill suggestion pipeline | `plans/agent_ops/5_skill_learning/scope_lock.md` |

## Groundwork Already Shipped

Platform-10 groundwork was shipped during Phase 4 as part of SP-4-10:

- **PR #1807** — Core ops ABCs (`interfaces.py`: 4 ABCs)
- **PR #1813** — Extract core ops (`controller.py`, `monitor.py` wrappers)
- **PR #1817** — Repo adapter (`adapters/bid_euchre.py`)
- **PR #1950** — ServiceProvider wiring (`provider.py`)
- **PR #1954** — Core adapter contract tests (6 test files, 2256 LOC)

The boundary exists but is not yet used by callers. Phase 5 completes the
migration and adds the learning loop.

## Sub-Plans

| ID | Title | Platform | PRs | Est. Hours |
|----|-------|----------|-----|------------|
| SP-5-01 | Platform-10 Portability Completion | Platform-10 | 4 | 6h |
| SP-5-02 | Platform-11 Skill Learning Loop | Platform-11 | 5 | 9.5h |

## Execution Order

Platform-10 and Platform-11 are **partially parallelizable:**

```
SP-5-01 PR1 (lane topology) ─────┐
                                  ├──→ SP-5-01 PR3 (manifest) ──→ SP-5-01 PR4 (hooks)
SP-5-01 PR2 (ServiceProvider CLI) ┘

SP-5-02 PR1 (taxonomy) ──→ SP-5-02 PR2 (outcomes log) ──→ SP-5-02 PR3 (advisor) ──→ SP-5-02 PR4 (wiring)
                                                                                    ↘ SP-5-02 PR5 (suggestions)
```

- SP-5-01 PR1 and PR2 can run in parallel
- SP-5-02 PR1 can start immediately (no dependency on SP-5-01)
- SP-5-02 PR4 (worker_pool wiring) should land after SP-5-01 PR1 (lane
  topology extraction) to avoid conflicting changes in worker_pool.py

**Recommended lane assignment:**
- SP-5-01: 1 author lane (4 sequential PRs after initial parallel pair)
- SP-5-02: 1 author lane (5 sequential PRs)
- Cross-lane coordination needed only for SP-5-02 PR4 vs SP-5-01 PR1

## Done-When

### Platform-10
- New orchestration code depends on adapter contracts rather than
  Bid-Euchre-specific paths or docs
- The refactor scope for existing `src/bid_euchre/ops/` assumptions is
  documented and materially reduced

### Platform-11
- Repeated successful workflows can produce skill suggestions with provenance
- Promotion/refinement cannot bypass review, context-safety, and rollback gates

## Total Estimate

| Sub-Plan | PRs | Lane-Hours |
|----------|-----|------------|
| SP-5-01 | 4 | 6h |
| SP-5-02 | 5 | 9.5h |
| **Total** | **9** | **15.5h** |
