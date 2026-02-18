# Bid Euchre Repo Review — 2026-02-18

**Protocol version used:** 3.2 (Drift-Resilient, Discovery-Driven)
**Branch reviewed:** `main` @ `d74ec8f`
**Reviewed via:** 4 parallel agents (Discovery, Verification, Issues, Prompt Audit)

---

## 1. Executive Summary

### Health Scores

| Component | Score | Key Evidence |
|-----------|-------|-------------|
| Core / CI Infrastructure | 95/100 | `make check` passes; 17 lint rules; 1,288 tests |
| Test Suite | 90/100 | 1,288 pass, 0 empty stubs, no xfail regressions |
| Rigor Compliance | 88/100 | Prod configs n_per=50K, all 4 suits; CI/bootstrap in all active notebooks |
| Promotion Workflow | 92/100 | All 5 components (freeze/splits/eligibility/promotion/lint rules) pass |
| Documentation Accuracy | 80/100 | ARCHITECTURE.md matches reality; 2 stale refs in active docs |
| Logging / Data Contract | 65/100 | 3 required schema fields missing (`auction_transcript`, `redeal_flag`, `made_bid`) |
| Review Prompt | 82/100 | 2 missing §1.3 import-health checks; milestone table 11 PRs behind |
| **Overall** | **85/100** | Strong foundation; logging gap is the top blocker for Arc D |

### Key Achievements (recent)

- 13 source modules all import cleanly
- `make check` passes with 1,288 tests and 17 lint rules
- Arc C promotion workflow fully operational (freeze/splits/eligibility/5 lint rules)
- Phase 0 bidless report complete through r5 (PRs #340–#356)
- Docs freshness check added to CI (#349); no stale command contracts

### Top 5 Issues

| ID | Severity | Issue | Impact |
|----|----------|-------|--------|
| I001 | HIGH | 3 missing logging fields (`auction_transcript`, `redeal_flag`, `made_bid`) — schema at v5 | Blocks bidding data collection (Arc D); consumers at `notebook_data.py:634` and `paired.py:44` must be explicitly updated |
| I002 | HIGH | `docs/03_experiments/BIDLESS_DATASET_TINY.md:17` references deleted `scripts/collect_bidless_dataset.py` | Active doc causes hard failure for anyone following it |
| I004 | MEDIUM | 5+ schema/logging gaps tracked but not scheduled (CODEBASE_CONSISTENCY.md "Later" section) | Technical debt accumulating |
| I007 | MEDIUM | Old `PYTHONPATH=src python` invocation style in 3 active docs (`AI_BOUNDARIES.md:93`, `ARCHITECTURE.md:115`, `BIDLESS_DATASET_TINY.md:17`) | Style drift persists after partial fix |
| I006 | LOW | `STYLEGUIDE.md` and `TESTING_STRATEGY.md` absent with no target date | Nice-to-have; not blocking |

> ~~I003~~: **Stale finding** — ARCHITECTURE.md lines 50–51 already document `run_tests.py` and `train_b0.py`.

---

## 2. Verification Evidence

| Verification | Command | Result | Status |
|---|---|---|---|
| CI gates | `make check` | PASSED — 1,288 passed, 5 skipped, 4 deselected, 2 xfailed, 1 xpassed, 82 warnings | ✅ pass |
| Repo-linter rules | `grep -c "^def check_" scripts/lint_repo.py` | 17 rules | ✅ pass |
| Module imports | 13 `uv run python -c "from ..."` checks | All pass | ✅ pass |
| Config count | `ls experiments/configs/*.yaml \| wc -l` | 26 configs | ✅ pass |
| Import hygiene (src→experiments) | `grep -r "import experiments" src/` | Only relative intra-package import; lint rule passes | ✅ pass |
| Artifact leakage | `git ls-files data/` | Only `data/fixtures/` (13 files) | ✅ pass |
| Global random | `grep -r "random\." src/` | All use `random.Random()` instances, no global calls | ✅ pass |
| Deprecated folder | `git log --diff-filter=M -- experiments/_deprecated/` | No recent changes | ✅ pass |
| Canonical runner dry-run | `run_experiment.py --dry-run --seed 42 --config quick_test.yaml` | Exits 0, prints config summary | ✅ pass |
| Promotion-gate target | `make -n promotion-gate` | Target exists, multi-step gate | ✅ pass |
| Promotion lint rules | `grep "^def check_" scripts/lint_repo.py` | 5 promotion rules present | ✅ pass |
| Freeze/splits/eligibility imports | `uv run python -c "from bid_euchre.models.freeze import ..."` | All resolve | ✅ pass |
| Hardcoded trump='H' (production) | Configs scan | Only dev/smoke configs — not for inference | ⚠️ info |
| Fail-fast assert gates | Notebooks scan | 1 bare `assert`; rigor guards via `if MODE != "SMOKE"` | ⚠️ info |

---

## 3. Issue Registry

| ID | Severity | Location | Issue | Evidence | Recommendation |
|----|----------|----------|-------|----------|----------------|
| I001 | **HIGH** | `game_logger.py:31`, `diagnostics/notebook_data.py:634-635`, `analysis/paired.py:44` | 3 missing logging fields: `auction_transcript`, `redeal_flag`, `made_bid` — schema at v5, open since 2026-01-04. Consumers hard-read `t0`/`t1` and dispatch on `event == "hand_end"` directly. | Tracker: "Open"; required by `RULES.md §8.2`; no schema guard on new fields | Before implementing: (1) choose strategy — nullable fields on `hand_end` (→ v6, backward-compat) vs. new event types; (2) update consumers; (3) add schema version tests; (4) update `DATA_CONTRACT.md`. Arc D unblocking work. |
| I002 | **HIGH** | `docs/03_experiments/BIDLESS_DATASET_TINY.md:17` | Stale script ref: `scripts/collect_bidless_dataset.py` referenced but deleted | `ls scripts/collect_bidless_dataset.py` → not found | Update to `uv run python experiments/run_experiment.py --config <config> --seed <N>` |
| I004 | **MEDIUM** | `docs/03_TODO/CODEBASE_CONSISTENCY.md` "Later §" | 5+ schema/logging gaps with no scheduled PRs: dual outcome tracking, card instance IDs, strategy IDs, TEAM_RANDOMIZED protocol | All "Open", no target PR | Group into Arc D planning; I001 fields are first priority |
| I005 | **MEDIUM** | `docs/01_core/legacy/TRAINING_DATA_LEGACY.md` | References `experiments/configs/bidder_training_data.yaml` which no longer exists | Config not found on disk | Move to `docs/archive/` or add stale notice |
| I007 | **MEDIUM** | `AI_BOUNDARIES.md:93`, `ARCHITECTURE.md:115`, `BIDLESS_DATASET_TINY.md:17` | Old `PYTHONPATH=src python` invocation style in 3 active docs | CLAUDE.md §Python Defaults: "Use `uv run` as the default Python runner" | Fix all 3 in one PR |
| I006 | **LOW** | `docs/03_TODO/CODEBASE_CONSISTENCY.md` nice-to-haves | `STYLEGUIDE.md` and `TESTING_STRATEGY.md` absent with no target date | "still absent; add when there's bandwidth" | Long-term backlog |

> ~~I003 (ARCHITECTURE.md missing run_tests.py/train_b0.py)~~: **Stale finding** — lines 50–51 already document both scripts.

---

## 4. Cleanup Plan

**PR A (docs): Fix stale references + normalize invocation style** (trivial, ~10 min)
- `docs/03_experiments/BIDLESS_DATASET_TINY.md:17` — replace `PYTHONPATH=src python scripts/collect_bidless_dataset.py` with `uv run python experiments/run_experiment.py --config <config> --seed <N>` (closes I002 + I007)
- `docs/01_core/ARCHITECTURE.md:115` — replace `PYTHONPATH=src python` with `uv run python` (closes I007)
- `docs/02_agent/AI_BOUNDARIES.md:93` — replace `PYTHONPATH=src python` with `uv run python` (closes I007)
- `docs/01_core/legacy/TRAINING_DATA_LEGACY.md` — move to `docs/archive/` or add stale notice (closes I005)

**PR B-1 (schema): `redeal_flag` + `made_bid`** (medium, Arc D unblocking)

Acceptance criteria:
1. **Implementation**: Nullable fields on `hand_end` records → schema v6 (backward-compatible: read-side `.get()` guards)
2. **Consumer updates**:
   - `src/bid_euchre/logging/game_logger.py` — bump `SCHEMA_VERSION` to 6, add fields to `HandEndRecord` dataclass
   - `src/bid_euchre/diagnostics/notebook_data.py:634-635` — add `.get('redeal_flag')` and `.get('made_bid')` handling
   - `src/bid_euchre/analysis/paired.py:44` — assess whether `redeal_flag` needs filtering (incomplete hands should likely be excluded from comparisons)
   - `docs/01_core/DATA_CONTRACT.md` — schema version bump + field documentation
3. **Tests**: Assert v6 fields present in logged `hand_end` records

**PR B-2 (schema): `auction_transcript`** (larger, own sub-task)
- Define per-bid record structure before implementing
- May introduce a new `bid_end` event type rather than a field on `hand_end`
- Target schema v7

---

## 5. Rigor Assessment

| Metric | Value | Status |
|--------|-------|--------|
| Production config minimum n_per | 50,000 | ✅ meets 50K threshold |
| Dev/smoke config n_per | 10–1,000 (labeled) | ✅ acceptable for purpose |
| Notebooks with statistical tests | 3/3 active notebooks | ✅ `f_oneway`, `ttest_ind`, `chi2_contingency`, `ks_2samp` |
| Notebooks with confidence intervals | 3/3 active notebooks | ✅ bootstrap CIs present |
| Hardcoded trump='H' (prod configs) | 0 | ✅ all prod configs use C,D,H,S expansion |
| Visual-only validation language | 0 matches | ✅ no "looks balanced" claims |
| Fail-fast assert gates | 1 bare assert | ⚠️ notebooks use `if MODE != "SMOKE"` guards; acceptable style |
| Contract-type faceting | Applied throughout | ✅ suit vs high/low split enforced in Phase 0 report |

---

## 6. Documentation Roadmap

| Doc | Issue | Priority |
|-----|-------|----------|
| `docs/03_experiments/BIDLESS_DATASET_TINY.md` | Stale script ref (I002) | High — active operational doc |
| `docs/02_agent/AI_BOUNDARIES.md` | Old invocation style (I007) | Medium |
| `docs/01_core/ARCHITECTURE.md` | Old invocation style in §"Run an experiment" (I007) | Medium |
| `docs/01_core/legacy/TRAINING_DATA_LEGACY.md` | Stale config ref (I005) | Low — archive or delete |
| `docs/02_agent/REPO_REVIEW_PROMPT.md` | Prompt maintenance: add `logging/`, `utils/` §1.3 import checks; add `docs/03_experiments/` to tree; update milestone table through #356 | Low |

---

## 7. Development Roadmap

### Where We Are

The repo has completed:
- **Arc A**: Core game engine (cards, rules, simulation)
- **Arc B**: Bidding policies — 16 PRs (#262–#275), OLSa, StrictHellRaiser, etc.
- **Arc C**: Batch infrastructure + Promotion Workflow — 14+ PRs (#310–#332)
- **Phase 0 Report** (bidless analysis): r5 — 12 sections, 16+ charts, statistical rigor throughout
- **Doc Hardening**: docs-freshness CI gate, `/review` skill, `/summarize` skill
- **Feature Rename**: `high_offsuit` → `offsuit_non_ace_count`

**Repo health: 85/100.** Infrastructure, tests, CI gates, and promotion workflow are all solid. The main gap is the logging schema — a prerequisite for Arc D.

### The Main Blocker: Logging Schema Gaps

The `CODEBASE_CONSISTENCY.md` "Now §1-3" items have been open since 2026-01-04:
- `auction_transcript` — per-seat bid action log
- `redeal_flag` — all-pass redeal marker
- `made_bid` — bid made/set flag

These are **prerequisites for Arc D (bidding data collection)**. Without `auction_transcript`, collected datasets can't be used to train or evaluate bidding models. `redeal_flag` and `made_bid` are simpler nullable fields (PR B-1); `auction_transcript` needs design work (PR B-2).

### Recommended Next Steps

**Near-term (unblocking Arc D):**
1. **PR A** — trivial doc cleanup (I002 + I007 + I005)
2. **PR B-1** — `redeal_flag` + `made_bid` as nullable fields on `hand_end` → schema v6
3. **PR B-2** — `auction_transcript` design + implementation → schema v7

**Arc D (Bidding Data Collection + Model):**
4. Design bidding dataset collection pipeline (auction transcripts → bidding features)
5. Train first bidding model (B1 = logistic/Ridge on contract type)
6. Phase 1 Report (bidding model performance)

**Lower priority:**
7. `STYLEGUIDE.md` and `TESTING_STRATEGY.md` (I006)
8. TEAM_RANDOMIZED comparator protocol (I004 subset)
9. Prompt maintenance: REPO_REVIEW_PROMPT.md v3.2 → v3.3

---

## Phase 6: Prompt Maintenance Findings

**Protocol version:** 3.2 (Drift-Resilient, Discovery-Driven)
**Total stale items:** 5

| Category | Count | Details |
|----------|-------|---------|
| Missing §1.3 import-health checks | 2 | `logging/` and `utils/` are in the CURRENT STRUCTURE tree (lines 900, 904) but have no `uv run python -c "from bid_euchre.logging..."` check in §1.3 (line 121) |
| Stale file references | 1 | `FLOW_DIAGRAM.md` implied to be in `docs/01_core/` but lives at `docs/FLOW_DIAGRAM.md` |
| Structure drift | 2 | `docs/03_experiments/` undocumented; `notebooks/sandbox/` + `notebooks/_templates/` not in tree |
| Milestone table gap | 1 | 11 PRs (#346–#356) unrepresented in the historical era table |
| Misleading section title | 1 | "Bidding Teacher Loop" implies a `make` target that doesn't exist |

All 16 existing §1.3 import checks pass. These fixes are low-severity and optional.
