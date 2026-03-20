# Repo Review — 2026-03-20

**Reviewer:** Claude Code (Opus 4.6)
**Branch:** main @ f6b142ad
**Protocol:** v3.7 (Drift-Resilient, Discovery-Driven)
**Previous reviews:** R17 (2026-03-17, 89/100), R18 (2026-03-18, 91/100)

---

## 1. Executive Summary

### Health Score

| Component | Score | Trend | Notes |
|-----------|-------|-------|-------|
| CI / Tests | 98/100 | = | 5045 tests passing, 44 skipped, 21 repo-lint rules |
| Code Quality | 96/100 | = | Zero actionable TODOs in prod, zero empty tests, clean imports |
| Documentation | 85/100 | ↑ | Phantom `agent_ops/` module, 10 undocumented scripts (down from 25) |
| Rigor | 94/100 | ↑ | 95% of plotting notebooks have stat tests, 76% configs production-grade |
| Architecture | 96/100 | = | Clean boundaries, promotion workflow functional, all modules importable |
| **Overall** | **93/100** | **↑ (+2)** | **Improvement from R18 (91/100); documentation drift remains primary gap** |

### Key Achievements Since R18

- Undocumented internal scripts reduced from 25 to 10 (60% improvement)
- Stale import paths in review prompt resolved (R18-4)
- All `.mean()` without CI anti-patterns resolved (R18-7)
- 124 new commits, 224 new merged PRs since R18
- 22 new test files added (177 → 199)
- Zero actionable TODOs in production source code

### Top 5 Issues

| Rank | ID | Severity | Issue | Location |
|------|-----|----------|-------|----------|
| 1 | R20-1 | HIGH | Phantom `agent_ops/` module in CLAUDE.md source layout | `CLAUDE.md` module table |
| 2 | R20-2 | HIGH | 10 undocumented internal scripts in ARCHITECTURE.md | `docs/01_core/ARCHITECTURE.md` |
| 3 | R20-3 | MEDIUM | Milestones table 224 PRs behind (worsened from R18-3) | `docs/02_agent/REPO_REVIEW_PROMPT.md` |
| 4 | R20-4 | MEDIUM | `57_c33_ablation_deep_dive` notebook has 14 plots, zero stat tests | `notebooks/arc_d/r0/57_c33_ablation_deep_dive.py` |
| 5 | R20-5 | MEDIUM | Review prompt staleness: 4 items including missing ops/ coverage | `docs/02_agent/REPO_REVIEW_PROMPT.md` |

---

## 2. Verification Evidence

| Verification | Command | Result | Status |
|--------------|---------|--------|--------|
| CI gates | `make check` | PASSED (5045 tests, 44 skipped, 73 warnings) | pass |
| Repo-linter | `make repo-lint` | 21 rules, all passed | pass |
| Ruff lint | `make lint` | Clean (no output) | pass |
| Pytest | `make test` | 5045 passed, 44 skipped, 5 deselected (328.35s) | pass |
| Notebook check | `make notebook-check` | All synced, outputs cleared | pass |
| Docs check | `make docs-check` | Passed | pass |
| Module imports | 14 directories + scoring.py | All import successfully | pass |
| Import hygiene | `grep -r "from experiments\|from tests" src/` | Zero matches | pass |
| Artifact leakage (git) | `git ls-files data/runs/` | 0 tracked files | pass |
| Frozen folders | `_deprecated/` | No recent modifications | pass |
| Promotion workflow | `make promotion-gate` target + imports | All functional | pass |
| Dry-run experiment | `--dry-run --force` | Configuration valid | pass |
| Config validation | `scripts/validate_configs.py` | 42 configs validated | pass |

---

## 3. Issue Registry

| ID | Severity | Location | Issue | Evidence | Recommendation |
|----|----------|----------|-------|----------|----------------|
| R20-1 | HIGH | `CLAUDE.md` module table | Phantom `agent_ops/` module listed — directory does not exist on disk | `ls -d src/bid_euchre/agent_ops/` → exit code 1 | Remove `agent_ops/` row from module table; the governed plan lives at `plans/agent_ops/` |
| R20-2 | HIGH | `docs/01_core/ARCHITECTURE.md` | 10 internal scripts undocumented (down from 25 at R18) | Scripts exist on disk but not in ARCHITECTURE.md internal scripts table | Add documentation for: `_repo_utils`, `build_audit_index`, `build_curated_memory`, `ci_shadow_trial_report`, `compact_session_context`, `evaluate_gate_x3`, `generate_r1_5_diagnostics`, `generate_r4_charts`, `ops`, `run_arc_d_h2h_battery` |
| R20-3 | MEDIUM | `docs/02_agent/REPO_REVIEW_PROMPT.md` milestones | Last documented era ends at PR #864; repo is at PR #1088 (224 PR gap) | Milestones table inspection | Add era(s) covering #865-#1088 (themes: Lineage Closeout, Ops Hardening, Agent Ops Planning) |
| R20-4 | MEDIUM | `notebooks/arc_d/r0/57_c33_ablation_deep_dive.py` | 14 plot calls with zero statistical tests (f_oneway, ttest, bootstrap) | `grep` for stat test patterns returns no matches | Add stat tests if used for decision-making; or annotate as exploratory-only (carryover from R18-6) |
| R20-5 | MEDIUM | `docs/02_agent/REPO_REVIEW_PROMPT.md` | 4 staleness items: missing `ops/` import check, missing `ops/` in structure tree, stale `data/models` path, milestones gap | Prompt audit agent verified each item | Apply targeted edits (Phase 6 candidate) |
| R20-6 | MEDIUM | `docs/01_core/schemas/hybrid_olsa_v1.md:93` | References `docs/04_reports/arc_d_v2/r1/r0_to_r1_progression.md` which does not exist | File annotated "[not yet generated]" | Generate the progression report or update the reference |
| R20-7 | LOW | `CLAUDE.md` | Test file count not updated (R18 referenced 177, actual is 199-201) | `find tests/ -name "test_*.py" \| wc -l` | Update if any count is documented; currently no hardcoded count in CLAUDE.md |
| R20-8 | LOW | `src/bid_euchre/strategy/bidding.py:1824` | `dealer_seat=0` default parameter | Documented as appropriate — function requires a default | No action (documented in R18-12) |
| R20-9 | LOW | `src/bid_euchre/strategy/bidding.py:2058,2107` | `trump="H"` in suit family sanity checks | Documented as appropriate in R18-11 | No action |
| R20-10 | LOW | 3 codex validation report stale refs | Historical reports reference deleted test fixtures | All annotated "[deleted]" in the reports | No action (frozen historical artifacts) |
| R20-11 | LOW | `docs/03_TODO/CODEBASE_CONSISTENCY.md` | 8 "Later" items remain open | All are intentionally deferred | Review periodically; no immediate action |
| R20-12 | LOW | `notebooks/sandbox/blog_reports/generate_matchup_charts.py` | Chart-only utility notebook with no stat tests | Sandbox/utility notebook, not used for inference | No action |
| R20-13 | LOW | `docs/01_core/ARCHITECTURE.md` `data/` section | Does not mention `data/artifacts/` or `data/reports/` subdirectories | Directory exists on disk | Add to data directory documentation |

---

## 4. Cleanup Plan

### PR Sequence (Recommended)

| Order | PR Scope | Issues Addressed | Effort |
|-------|----------|-----------------|--------|
| 1 | Remove phantom `agent_ops/` from CLAUDE.md | R20-1 | Trivial (1 line edit) |
| 2 | Update review prompt (Phase 6 fixes) | R20-3, R20-5 | Small (4 targeted edits) |
| 3 | Document undocumented internal scripts | R20-2 | Small (10 entries) |
| 4 | Add stat tests to ablation notebook (if decision-critical) | R20-4 | Medium |

PRs 1-3 are documentation-only. PR 4 is conditional on whether the notebook is used for decisions.

---

## 5. Rigor Assessment

### Sample Size Compliance

| Tier | Config Count | n_per Range | Status |
|------|-------------|-------------|--------|
| Smoke/test | 10 | 10-1,000 | Appropriate (clearly labeled) |
| Inference | 12 | 2,000-10,000 | Pass (meets ≥2,000 threshold) |
| Production | 20 | 50,000-100,000 | Pass (meets ≥50,000 threshold) |

### Statistical Test Coverage

| Metric | Value | Status |
|--------|-------|--------|
| Notebooks with plots | 20 | — |
| Notebooks with stat tests | 19/20 (95%) | pass |
| Notebooks with CIs | 15/21 (71%) | pass |
| Confidence interval refs across codebase | 161 occurrences | pass |
| Visual-only "looks balanced" anti-patterns | 0 | pass |
| Fail-fast assert gates | 6 locations | info |

### Anti-Pattern Scan

| Anti-Pattern | Count | Status |
|--------------|-------|--------|
| Hardcoded `seat=0` (undocumented) | 0 | pass |
| Hardcoded `trump='H'` (undocumented) | 0 | pass |
| `.mean()` without CI (in analysis) | 0 | pass (resolved since R18) |
| "Looks balanced/good" claims | 0 | pass |
| Unseeded experiments (active docs) | 0 | pass |

---

## 6. R18 Issue Tracking

| R18 ID | Issue | R20 Status | Notes |
|--------|-------|------------|-------|
| R18-1 | 25 undocumented internal scripts | **Improved** → R20-2 | Reduced to 10 (60% improvement) |
| R18-2 | Orphan `utils/` directory | **Resolved** | Confirmed deleted |
| R18-3 | Milestones table 84 PRs behind | **Worsened** → R20-3 | Now 224 PRs behind |
| R18-4 | 2 stale import paths in review prompt | **Resolved** | Imports now correct |
| R18-5 | 3 stale path refs in active docs | **Unchanged** → R20-10 | Historical reports, all annotated |
| R18-6 | 1 notebook without stat tests | **Unchanged** → R20-4 | `57_c33_ablation_deep_dive` |
| R18-7 | `.mean()` without CIs in templates | **Resolved** | All notebooks with extensive `.mean()` now have CI context |
| R18-11 | 2 hardcoded `trump='H'` | **Unchanged** → R20-9 | Documented as appropriate |
| R18-12 | 3 hardcoded `seat=0` defaults | **Unchanged** → R20-8 | Documented as appropriate |

**Resolution rate:** 4/9 R18 issues resolved, 1 improved, 1 worsened, 3 unchanged (documented as appropriate).

---

## 7. Prompt Audit Summary

The Prompt Audit agent found **4 stale items** in `docs/02_agent/REPO_REVIEW_PROMPT.md` v3.7:

| # | Category | Issue | Fix |
|---|----------|-------|-----|
| 1 | Missing module coverage | `ops/` module has no import health check in §1.3 | Add `uv run python -c "import bid_euchre.ops"` |
| 2 | Structure drift | `ops/` directory omitted from CURRENT STRUCTURE tree | Add `ops/` to the tree |
| 3 | Stale command | §2.3 references `data/models` which doesn't exist; should be `data/artifacts` | Update path |
| 4 | Milestones gap | Last era ends at PR #864; latest merged is #1088 | Add new era row(s) |

All items are straightforward edits. Recommend Phase 6 prompt maintenance PR.

---

## Appendix: Structure Snapshot

| Component | R17 | R18 | R20 | Delta (R18→R20) |
|-----------|-----|-----|-----|-----------------|
| Source modules | 13 | 14 | 14 | — |
| Experiment configs | 42 | 42 | 42 | — |
| Experiment suites | 4 | 4 | 4 | — |
| Scripts (top-level) | 22 | 23 | 23 | — |
| Scripts (internal) | 47 | 56 | 56 | — |
| Test files | 161 | 177 | 199-201 | +22-24 |
| Docs (total) | 179 | 203 | 205 | +2 |
| Active notebooks | 23 | 23 | 22-23 | — |
| Total commits | 723 | 884 | 1,008 | +124 |
| Latest merged PR | #780 | #864 | #1086-1088 | +222-224 |
| Repo-linter rules | 19 | 21 | 21 | — |
| Health score | 89 | 91 | 93 | +2 |
