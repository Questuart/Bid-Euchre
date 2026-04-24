# Agent-Readability Scorecard

**Floor (per ADR 001):** ≥7/10
**Current score:** 7/10 (last run 2026-04-24 04:59 UTC)
**Phase 0 baseline:** <recorded at Phase 0 Readiness>
**Phase 1 end score:** <recorded at Phase 1 end; must ≥ Phase 0 baseline>

## Items

| # | Item | Status | Detail |
|---|---|---|---|
| 1 | CLAUDE.md ≤ 200 lines | FAIL | 273 lines; limit 200 |
| 2 | Single canonical entry point | PASS | H1 count=1; Project-Overview marker=yes |
| 3 | Governing plan findable in ≤2 hops | PASS | 2 reference(s): CLAUDE.md:plans/browser_game/governing_plan.md (+1 more) |
| 4 | Skills discoverable | PASS | 41 skills; 0 orphans |
| 5 | Lane registry authoritative | PASS | pools covered: platform, browser, analyst, flex, control |
| 6 | MEMORY.md indexes rather than recaps | FAIL | FAIL: MEMORY.md not found |
| 7 | ADR index current | PASS | 1 ADR file(s) on disk; 10 ID(s) indexed in README |
| 8 | KB INDEX current | PASS | kb_index.py --check exit 0 (INDEX up to date) |
| 9 | No orphan references in plans | PASS | lint check load-bearing-ownership exit 0 (no BLOCK findings) |
| 10 | Rule files grep-discoverable | FAIL | 12 orphan rule file(s): .claude/rules/10_workflow.md, .claude/rules/20_determinism.md, .claude/rules/deferred/30_data_contract.md (+9 more) |

## Run log

- 2026-04-24: 7/10 — scorecard runner v0 — lane-automated — post-Phase-0-scaffold — floor 7/10
