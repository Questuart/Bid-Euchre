# Repo Review + Cleanup + Docs + Roadmap Prompt (ZIP-based)

Last Updated: January 12, 2026 (post PR #97 — bidding infrastructure foundation complete)

## ROLE

You are an engineering lead reviewing a Python card-game simulator repo (Bid Euchre / double-deck euchre). The repo is entirely created by AI agents. Your job is to:

1. Review the entire repo and the development to date (use PRs + commits as ground truth)
2. Propose and stage a repo cleanup plan (reduce clutter, consolidate structure, quarantine/deprecate safely)
3. Create and/or complete missing docs (some docs may be thin/empty/outdated)
4. Chart a roadmap from here (sequenced PRs, low risk, agent-friendly)

You MUST bias toward agent execution correctness and low-leak processes:
- Hard gates
- Determinism by default
- Reproducible experiments
- Clear "gold path" commands
- Strict boundaries (no imports across forbidden layers)
- No committed generated artifacts

---

## INPUTS

- You will be given a ZIP of the repo (treat ZIP contents as authoritative).
- Use PR history + commit history below as "archaeology hints," but do not invent details not present in the ZIP.
- If anything is unclear, explicitly say what you could not confirm and how to verify it.

---

## GROUND TRUTH: PR HISTORY (MERGED)

97 PRs total (January 5–12, 2026)

### Latest PRs (#88–97): Bidding Infrastructure Foundation

**MAJOR MILESTONE**: 10 PRs in 3 days establishing bidding model development foundation

| PR | Title | Theme |
|----|-------|-------|
| #97 | fix: wire bidding dataset emission flag (v1) | Bugfix |
| #96 | feat: add heuristic baseline bidding policies (v1) | Feature |
| #95 | test: add bidding dataset schema guard (v1) | Testing |
| #94 | docs: add GitHub auth sandbox workflow guidance | Docs |
| #93 | feat: emit bidding dataset (v1) | Feature |
| #92 | test: lock auction bidding rules (v1) | Testing |
| #91 | docs: enforce worktrees in PR templates | Docs |
| #90 | feat: add bidding policy interface (v1) | Feature |
| #89 | docs: define bidding contract (v1) | Docs |
| #88 | docs: define bidding dataset contract (v1) | Docs |

### PRs #82–87: Drift Polish + Documentation + Testing

| PR | Title | Theme |
|----|-------|-------|
| #86 | test: cover suite aggregation + rollup comparator behavior | Testing |
| #85 | docs: improve baseline_matchups readability | Docs |
| #84 | docs: operationalize root README (gold path) | Docs |
| #83 | test: add drift tooling regression tests | Testing |
| #82 | docs: add repo review + cleanup + docs + roadmap prompt | Docs |

### PRs #76–81: Drift Pipeline Polish + Cleanup

| PR | Title | Theme |
|----|-------|-------|
| #81 | ci: polish drift workflow with actionable issue output | CI |
| #79 | feat: improve comparator output ergonomics | Feature |
| #78 | docs: fix DRIFT.md fixture schema example | Docs |
| #77 | docs: fix experiments/README.md config and suite lists | Docs |
| #76 | docs: delete empty placeholder docs | Cleanup |

### PRs #64–75: Drift Infrastructure + Fixture Stabilization

| PR | Title | Theme |
|----|-------|-------|
| #75 | ci: baseline_full drift workflow runs comparator (tricks-only) and ignores auction_smoke | CI |
| #74 | docs: align METRICS.md with emitted keys and drift v1 (tricks-only) | Docs |
| #73 | chore: populate baseline_full fixture and stabilize rollup JSON determinism (tricks-only drift) | Quality |
| #72 | docs: make worktrees default for parallel PR agents | Docs |
| #71 | ci: add scheduled baseline_full drift signal | CI |
| #70 | docs: tidy CODEBASE_CONSISTENCY tracking | Docs |
| #69 | docs: clarify experiments _deprecated guidance | Docs |
| #68 | docs: tighten archive guardrails | Docs |
| #67 | docs: make PR templates parallel-safe via git worktrees | Docs |
| #66 | ci: add scheduled baseline_full drift-signal workflow | CI |
| #65 | feat: emit win-rate metrics in results JSON and suite rollups | Feature |
| #64 | feat: add rollup drift comparator script + baseline_full fixture v0 | Feature |

### PRs #56–63: Baseline Full Suite + Metrics Contract

| PR | Title | Theme |
|----|-------|-------|
| #63 | docs: bulletproof PR prompt templates for gh auth + TLS + SSH remote | Docs |
| #62 | docs: bulletproof PR templates for gh TLS + SSH | Docs |
| #61 | feat: surface rollup metric parse failures in summary table | Feature |
| #60 | docs: define metrics contract v1 (win/points/tricks) | Docs |
| #59 | feat: add per-config metrics table to suite rollup | Feature |
| #58 | docs: add ARCHIVED banner to docs/archive/ | Docs |
| #57 | docs: fix training README false --config claim | Docs |
| #56 | feat: add baseline_full suite (matchup matrix) | Feature |

### PRs #46–55: Docs Cleanup + Hardening

| PR | Title | Theme |
|----|-------|-------|
| #55 | docs: resolve PR #49 revert impact and restore correct experiments docs | Docs |
| #54 | docs: consolidate and harden PR prompt templates (parallel-safe + auth gate) | Docs |
| #53 | docs: remove stale blockers from CODEBASE_CONSISTENCY | Docs |
| #52 | chore: quarantine non-runnable experiment configs | Cleanup |
| #51 | docs: remove 0-byte agent-doc footguns | Cleanup |
| #50 | docs: harden PR prompt templates for parallel agents | Docs |
| #49 | Revert "docs: fix experiments README stale refs" | Revert |
| #48 | docs: fix experiments README stale refs | Docs |
| #47 | docs: fix docs README legacy script ref | Docs |
| #46 | chore: quarantine stale experiments registry | Cleanup |

### PRs #39–45: Fixes, Linting, Docs Cleanup

| PR | Title | Theme |
|----|-------|-------|
| #45 | ci: fix ruff exclude to lint canonical runner and scripts | CI |
| #44 | docs: remove dead reporting commands from active docs | Docs |
| #43 | docs: align docs with current workflows (remove dead paths) | Docs |
| #42 | chore: lint runner and scripts (ruff coverage) | Quality |
| #41 | chore: remove .DS_Store from git tracking | Hygiene |
| #40 | fix: auction determinism under deal_seed + repeatability test | Bugfix |
| #39 | docs: clarify config precedence and effective-config snapshot | Docs |

### PRs #30–38: Scoring, Guards, and Hardening

| PR | Title | Theme |
|----|-------|-------|
| #38 | feat: runner validation hardening (fail fast) | Quality |
| #37 | test: add results JSON shape guard (baseline_tiny) | Testing |
| #36 | test: add scoring invariants guard (baseline_tiny) | Testing |
| #35 | docs: fix SCORING.md and DATA_CONTRACT.md ambiguity | Docs |
| #34 | docs: add scoring contract documentation | Docs |
| #33 | fix: auction smoke test verifies auction mode without requiring bids | Bugfix |
| #32 | feat: support auction scenarios (contract_type: null) in run_experiment | Feature |
| #31 | chore: remove .DS_Store and block via repo-lint | Hygiene |
| #30 | chore: fix report command footgun | Bugfix |

### Infrastructure Blitz (#19–29): CI, Determinism, Baseline

| PR | Title | Theme |
|----|-------|-------|
| #29 | feat: add points scoring aggregates to simulation results | Feature |
| #28 | chore: fix report generator command in run_experiment output | Bugfix |
| #27 | test: add baseline_tiny invariants fixture and CI guard | Testing |
| #26 | feat: add suite runner for baseline_tiny + rollup index | Feature |
| #25 | docs: define baseline + add baseline_tiny suite | Docs |
| #24 | test: add deterministic repeatability check | Testing |
| #23 | ci: block new scripts in experiments comparisons and training folders | CI |
| #22 | chore: delete quarantined experiment scripts | Cleanup |
| #21 | chore: quarantine legacy experiment scripts | Cleanup |
| #19 | chore: pre-commit hygiene sweep (whitespace/EOF/YAML) | Hygiene |

### Foundation (#1–18): Core Infrastructure

| PR | Title | Theme |
|----|-------|-------|
| #18 | feat: add per-run report generator entrypoint | Feature |
| #17 | feat: standardize run output layout and snapshot config | Feature |
| #16 | feat: require seed by default for deterministic runs | Determinism |
| #15 | ci: enforce data fixtures allowlist and size limits | CI |
| #14 | chore: remove tracked data artifacts | Cleanup |
| #13 | docs: define data layout and commit policy | Docs |
| #12 | docs: add meta.json schema v2 documentation | Docs |
| #11 | chore: add Makefile gold path and use in CI | Build |
| #10 | ci: add repo linter (artifacts, boundaries, deprecated) | CI |
| #9 | test: fix model test and xfail flaky perf test | Testing |
| #8 | ci: re-enable ruff linting with import sorting (I) | CI |
| #7 | feat: strengthen run meta.json contract (schema v2) | Feature |
| #4 | test: add engine invariants integration test | Testing |
| #3 | test: add golden seed smoke test | Testing |
| #2 | chore: add PR template (repro-first) | Process |
| #1 | ci: add Tier 1 pytest workflow | CI |

Closed (not merged): #6, #5 (conflicts; functionality in other PRs)

---

## RECENTLY FIXED (January 8–12, 2026)

The following issues were identified in earlier reviews and have been resolved:

| Issue | Fixed In | Verification |
|-------|----------|--------------|
| Auction determinism bug | PR #40 | Code now uses `random.Random(deal_seed + deal_id)` for deterministic dealer selection |
| .DS_Store tracked in git | PR #41 | `git ls-files \| rg -i ds_store` returns nothing |
| Ruff excludes runner/scripts | PR #42, #45 | `extend-exclude` now only excludes `["data/", "experiments/_deprecated/"]` |
| docs/README.md deprecated script refs | PR #43, #44, #47 | Removed `generate_all_reports.py`, `generate_dashboard.py`, `run_baseline_greedy.py` refs |
| experiments/README.md stale folder refs | PR #48, #55 | No longer references `analysis/`, `dashboards/`, `data_generation/`, `plotting/` |
| experiments/REGISTRY.yaml outdated | PR #46 | Moved to `_deprecated/`; replaced with `REGISTRY.md` pointing to configs/ |
| Empty docs (AI_PLAYBOOK.md, WORKPLAN.md) | PR #51 | Deleted 0-byte files |
| CODEBASE_CONSISTENCY.md stale blockers | PR #53, #70 | Removed stale "scoring system" blockers |
| Win-rate metrics missing | PR #65 | Added `win_rate_team0`, `win_rate_team1`, `tie_rate` to results JSON |
| Rollup drift comparator | PR #64, #73 | `scripts/compare_rollup.py` + `data/fixtures/baseline_full_expected.json` |
| CI drift detection workflow | PR #66, #71, #75 | `.github/workflows/baseline_full_drift.yml` runs daily |
| Empty placeholder docs (01_core/) | PR #76 | Deleted ROADMAP.md, SCHEMA_VERSIONING.md, STYLEGUIDE.md, TESTING_STRATEGY.md |
| Empty placeholder docs (root) | PR #76 | Deleted CHANGELOG.md, CONTRIBUTING.md |
| experiments/README.md outdated config list | PR #77 | Now lists all 10 active configs accurately |
| DRIFT.md schema vs fixture mismatch | PR #78 | Schema example now matches `data/fixtures/baseline_full_expected.json` |
| Comparator output not actionable | PR #79 | Improved formatting, shows expected/actual/delta, deterministic ordering |
| Drift workflow issue not readable | PR #81 | GitHub issues now include run metadata table, artifact links, comparison output |
| Repo review prompt needed | PR #82 | Added this document to guide future repo reviews |
| Drift comparator lacked tests | PR #83 | Added regression tests for comparator behavior (skip logic, tolerance) |
| Root README lacked gold path | PR #84 | Added clear "getting started" and "gold path" commands |
| baseline_matchups readability | PR #85 | Improved YAML structure and comments |
| Suite aggregation edge cases | PR #86 | Tests cover rollup generation and comparator edge cases |
| **Bidding contract undefined** | **PR #88, #89** | **Documented bidding rules, observation contract, and dataset schema (v1)** |
| **No bidding policy interface** | **PR #90** | **Added BidAction, BiddingObservation, BiddingPolicy abstractions** |
| **Auction rules not locked** | **PR #92** | **Unit tests lock single round, strict raising, redeal on all pass** |
| **No bidding dataset emission** | **PR #93, #97** | **Dataset emission flag wired, outputs to data/runs/<run_id>/datasets/bidding.jsonl** |
| **No bidding schema guards** | **PR #95** | **Added fixture + schema validation tests for bidding dataset** |
| **No baseline bidding policies** | **PR #96** | **Added 3 heuristic baseline bidders (FixedBidder, HeuristicSuitBidder, HighLowHeuristicBidder)** |

---

## KNOWN ISSUES (still present as of January 12, 2026)

### BIDDING MODEL PHASE 1 INCOMPLETE (post PR #97 / BID-PR-04)

**Status**: Foundation established (PRs #88–#97 / BID-PR-00 through BID-PR-04), but Phase 1 dataset correctness items remain:

| Issue | Priority | Description | Next Step |
|-------|----------|-------------|-----------|
| **Parquet emission not implemented** | HIGH | Docs say Parquet is primary format, but only JSONL emitted | BID-PR-05 |
| **Attempted vs effective bids not tracked** | HIGH | Dataset doesn't distinguish attempted bid from effective action (illegal raises recorded as pass) | BID-PR-06 |
| **Dataset identity depends on run_id timestamps** | MEDIUM | run_id timestamps embedded in rows break byte-identical determinism checks | BID-PR-07 (move to metadata) |

### LEGACY ISSUES (informational only)

**Issue:** Fixture only covers baseline_matchups.yaml
- **Description:** `data/fixtures/baseline_full_expected.json` only has metrics for `baseline_matchups.yaml`; `auction_smoke.yaml` is explicitly skipped for drift comparison (by design)
- **Verification:** `cat data/fixtures/baseline_full_expected.json`
- **Status:** By design (auction_smoke is smoke-only, no metrics to compare)

---

## IMPLICATIONS OF CURRENT STATE

### CI & Quality Gates

- CI runs fast pytest on PRs (Tier 1)
- Ruff lint/import sorting enforced (E/F/I) in CI + pre-commit
- Ruff now covers `experiments/run_experiment.py` and `scripts/*.py`
- Repo-linter enforced: prevents sprawl, boundary violations, artifact commits
- **Drift detection**: Scheduled daily workflow runs `baseline_full` suite and compares against fixture
- "Honest green CI": flaky perf test xfailed (not silently ignored)

### Gold Path Commands (via Makefile)

```bash
make repo-lint    # Repo linter (diff vs origin/main)
make lint         # Ruff check
make test         # Pytest fast suite
make check        # All of the above
```

### Data Policy & Enforcement

- Only `data/fixtures/**` is commit-allowed (size-capped)
- Generated outputs must not be committed
- All outputs go to `data/runs/<run_id>/`
- .DS_Store blocked by repo-lint and not tracked

### Determinism

- Runner requires seed by default; nondeterminism is opt-in (`--allow-nondeterministic`)
- Common deals: strategies see same hands when seeded
- Auction mode dealer selection is deterministic when `deal_seed` provided

### Run Output Contract

Runs live under `data/runs/<run_id>/` with stable skeleton:
- `meta.json` (schema v2)
- `config_effective.yaml`
- `results/`, `logs/`, `reports/`, `splits/`, `artifacts/`

### Scoring & Points

- Results JSON includes: `avg_points_team0/team1`, `distribution_points_*`, bidding_points
- Scoring contract documented in `docs/01_core/SCORING.md`
- CI guards freeze scoring invariants in `baseline_tiny`

### Baseline Infrastructure

- `baseline_tiny` suite defined (~760 hands, seconds to run)
- `baseline_full` suite defined (16 matchups x 6 scenarios = 96 configs, n_per=500, ~5 min)
- Suite runner: `scripts/run_suite.py`
- Invariants fixture + CI guard for regression detection
- Results JSON shape guard for structural stability
- Auction repeatability test added

### Drift Detection (Stable as of PR #81)

- **Comparator script:** `scripts/compare_rollup.py`
- **Fixture:** `data/fixtures/baseline_full_expected.json` (tricks-only, v0 schema)
- **CI workflow:** `.github/workflows/baseline_full_drift.yml` (daily at 17:00 UTC, creates GitHub Issue on drift)
- **Metric gated:** `avg_tricks` only (auction_smoke skipped for drift)
- **Tolerance:** 0 (exact match required for deterministic suite)
- **Issue output:** Run metadata table, artifact links, comparator output in collapsible details, next steps guidance

### Auction Support

- `contract_type: null` enables auction mode in experiments
- Smoke test validates auction path
- Determinism verified via `test_auction_repeatability.py`
- **Note:** auction_smoke excluded from drift detection (smoke-only, no metrics)

### Bidding Infrastructure (NEW as of PRs #88–#97)

**Ground Truth (v1):**
- **Bidding protocol**: Single round, left of dealer, simultaneous action, strictly increasing bids, redeal on all pass
- **Contracts**: Suit (C/D/H/S), HIGH, LOW; n ∈ [0..10] where 0 = pass
- **Observation contract (v1)**: hand + current_high_bid + seat + dealer_seat (but seat/dealer NOT used in v1 training inputs)
- **Legality**: n > current_high_bid else effective action is PASS

**Implementation:**
- **Policy interface**: `BiddingPolicy` abstract base class with `choose_bid(obs: BiddingObservation) -> BidAction`
- **Baseline policies**: AlwaysPassBidder, StrictRaiserBidder, FixedBidder, HeuristicSuitBidder, HighLowHeuristicBidder
- **Dataset emission**: `--emit-bidding-dataset` flag, outputs to `data/runs/<run_id>/datasets/bidding.jsonl`
- **Schema guards**: `data/fixtures/bidding_dataset_tiny.jsonl` + CI tests in `tests/unit/test_bidding_dataset_schema.py`

**Dataset Contract (v1):**
- **Row granularity**: 4 rows per hand (one per seat decision)
- **Inputs**: hand_cards, hand_features (40+ features), current_high_bid
- **Labels**: bid_n, bid_contract, bid_trump_suit
- **Metadata**: run_id, hand_id, seat, dealer_seat, hand_feature_schema_version
- **Determinism**: Fully deterministic when seeded

**What's NOT done yet (Phase 1 remaining):**
- Parquet emission (docs say Parquet primary, but only JSONL implemented)
- Attempted vs effective bid tracking (illegal raises logged)
- Stable dataset identity (run_id timestamps break byte-identical hashes)
- Test that v1 training inputs exclude seat/dealer

---

## COMMIT HISTORY HIGHLIGHTS

### Milestones (chronological)

| Date | Milestone |
|------|-----------|
| Dec 10, 2025 | Initial simulation + strategies + greedy |
| Dec 15, 2025 | Refactor to `src/bid_euchre` package layout |
| Dec 15–16, 2025 | Unified experiment runner + standardized outputs + reporting |
| Dec 16, 2025 | Head-to-head evaluation system + deprecations |
| Jan 3, 2026 | Regression modeling + bidding engine + training data pipeline (200k records) |
| Jan 4, 2026 | Major reorganization (67+ files) + docs overhaul |
| Jan 5–6, 2026 | Infrastructure blitz: CI + lints + determinism + output contracts (PRs #1–29) |
| Jan 7–8, 2026 | Scoring contracts + guards + auction support + hardening (PRs #30–38) |
| Jan 8–10, 2026 | Auction determinism fix + .DS_Store removal + Ruff coverage + docs cleanup (PRs #39–55) |
| Jan 10–11, 2026 | baseline_full suite + drift comparator + CI drift workflow (PRs #56–75) |
| Jan 11, 2026 | Drift pipeline polish + cleanup + actionable issue output (PRs #76–81) |
| Jan 11, 2026 | Drift testing + docs polish (PRs #82–87) |
| **Jan 11–12, 2026** | **Bidding infrastructure foundation: contracts, policies, dataset emission, schema guards, heuristic baselines (PRs #88–#97)** |

---

## KEY THEMES SUMMARY (what to validate)

### Infrastructure & Quality

- CI workflow correctness and speed
- Ruff + pre-commit consistency (now covers runner/scripts)
- Makefile gold path parity with CI
- Repo-linter rule coverage
- **Drift workflow correctness**

### Reproducibility & Determinism

- Seed requirement and propagation to all RNG sources
- Auction determinism (fixed)
- meta.json v2 integrity
- config_effective.yaml usefulness for reproduction
- Stable run outputs (no writes outside run dirs)
- **Rollup JSON determinism**

### Scoring & Points

- Scoring contract completeness (`docs/01_core/SCORING.md`)
- Points aggregates in results JSON
- bidding_points conditional fields logic
- Scoring invariants guard stability

### Baseline & Regression Detection

- `baseline_tiny` suite coverage (3 configs, ~760 hands)
- `baseline_full` suite coverage (16 matchups + auction_smoke)
- Invariants fixture accuracy
- Results JSON shape guard effectiveness
- Suite runner + rollup correctness
- Auction repeatability test
- **Drift comparator accuracy**

### Testing

- 12 unit test files, 17+ integration test files (including auction repeatability), 1 performance test file
- Golden seed smoke tests
- Engine invariants
- Scoring + shape guards
- Runner validation tests
- **NEW**: Bidding dataset schema guards + heuristic bidder tests

### Bidding Infrastructure (NEW as of PRs #88–#97)

- Bidding protocol documented and locked in tests (single round, strict raising)
- Policy interface defined: BidAction, BiddingObservation, BiddingPolicy
- 5 baseline bidders implemented (2 simple + 3 heuristic)
- Dataset emission working (JSONL; Parquet next)
- Schema guards in place
- **Gap**: Phase 1 not complete (Parquet, attempted/effective, determinism polish, training input tests)

### Documentation Health

- ✅ Empty docs deleted (PR #76)
- ✅ experiments/README.md config list accurate (PR #77)
- ✅ DRIFT.md schema matches actual fixture (PR #78)
- ✅ Bidding contract + dataset schema documented (PRs #88, #89)

---

## CURRENT STRUCTURE

```
bid-euchre/
├── src/bid_euchre/          # Core library (the only importable package)
│   ├── core/                # Cards, deck, rules, trick logic
│   ├── sim/                 # Simulation engine (auction determinism fixed)
│   ├── strategy/            # AI strategies (greedy, random, etc.)
│   │   ├── bidding.py       # NEW: Bidding policy interface + 5 baseline bidders
│   │   ├── baselines.py     # Play strategies
│   │   └── ...
│   ├── datasets/            # NEW: Dataset emission
│   │   └── bidding.py       # Bidding dataset collection and emission (JSONL)
│   ├── features/            # Hand evaluation (40+ features)
│   ├── scoring.py           # Points calculation
│   ├── analysis/            # Statistical analysis
│   ├── reporting/           # Metrics, visualization
│   ├── logging/             # Structured game logging
│   └── experiments/         # Config system
├── experiments/             # Experiment configs + runner
│   ├── run_experiment.py    # THE canonical runner (linted)
│   ├── configs/             # YAML experiment definitions (10 active)
│   ├── suites/              # Suite definitions (baseline_tiny, baseline_full)
│   ├── _deprecated/         # Quarantined legacy scripts + configs
│   ├── comparisons/         # (blocked by repo-lint)
│   ├── training/            # (blocked by repo-lint)
│   ├── README.md            # Directory guide
│   └── REGISTRY.md          # Points to configs/ as authoritative
├── scripts/                 # Tooling (linted)
│   ├── lint_repo.py
│   ├── run_suite.py
│   ├── generate_report.py
│   ├── compare_rollup.py    # NEW: Drift comparator
│   ├── run_tests.py
│   └── validate_tests.py
├── tests/                   # Unit, integration, performance tests
├── docs/                    # Documentation
│   ├── 01_core/             # Architecture, contracts, specs
│   │   ├── ARCHITECTURE.md  # System design, boundaries
│   │   ├── BASELINE.md      # Baseline suite documentation
│   │   ├── BIDDING.md       # NEW: Bidding contract (v1)
│   │   ├── BIDDING_DATASET.md  # NEW: Bidding dataset schema (v1)
│   │   ├── DRIFT.md         # Drift detection contract
│   │   ├── METRICS.md       # Metrics contract v1
│   │   ├── SCORING.md       # Points calculation
│   │   └── (others...)      # All accurate
│   ├── 02_agent/            # AI agent guidelines
│   │   ├── AGENTS.md        # Agent operating rules
│   │   └── PR_PROMPT_TEMPLATES.md  # Parallel-safe + auth gate
│   ├── 03_TODO/             # Task tracking
│   ├── archive/             # Deprecated docs (has ARCHIVED banner)
│   ├── DEVELOPMENT.md       # Build/test commands
│   └── README.md            # Docs overview
├── data/
│   ├── fixtures/            # Committed test fixtures (size-capped)
│   │   ├── baseline_full_expected.json  # Drift fixture
│   │   └── bidding_dataset_tiny.jsonl   # NEW: Bidding dataset schema fixture
│   └── runs/                # Generated outputs (gitignored)
│       └── <run_id>/
│           └── datasets/
│               └── bidding.jsonl  # NEW: Emitted bidding dataset
├── Makefile                 # Gold path commands
├── pyproject.toml           # Ruff config (now lints runner/scripts)
└── .github/
    ├── workflows/
    │   ├── ci.yml           # Fast CI on PRs
    │   ├── baseline_full_drift.yml  # NEW: Daily drift detection
    │   └── nightly_baseline_full.yml
    └── PULL_REQUEST_TEMPLATE.md
```

---

## PRIORITIES (ranked) — Updated post PR #97

**Context**: Repo has pivoted from "drift detection polish" (complete) to **bidding model development** (foundation established, Phase 1 in progress).

### 1. Bidding Model Development (PRIMARY FOCUS)

**Goal**: Build imitation learning → value model pipeline for bidding strategy optimization

**Phase 0: Core Plumbing (DONE — GH PRs #91–#97)**
- ✅ **BID-PR-00**: Worktrees enforced (GH #91)
- ✅ **BID-PR-01**: Auction rules locked (GH #92)
- ✅ **BID-PR-02**: GH auth sandbox guidance (GH #94)
- ✅ **BID-PR-03**: Dataset schema guard (GH #95)
- ✅ **BID-PR-04**: Dataset emission wired (GH #97)

**Phase 1: Dataset Correctness + Determinism (must complete before training)**
- ☐ **BID-PR-05**: Convert to Parquet (docs say Parquet primary, but only JSONL implemented)
- ☐ **BID-PR-06**: Add attempted vs effective bid fields (illegal raises logged)
- ☐ **BID-PR-07**: Stable dataset identity via Parquet metadata (ignore run_id timestamps)

**Phase 2: Imitation Training v1 (after Phase 1)**
- ☐ **BID-PR-08**: Define artifact schema (JSON-only, string contracts)
- ☐ **BID-PR-09**: Training pipeline for three models (StrictRaiser, HeuristicSuit, HighLowHeuristic)
- ☐ **BID-PR-10**: ModelBidder loads artifact, produces deterministic bids
- ☐ **BID-PR-11**: Prediction determinism + artifact compatibility guards

**Phase 3: Online Evaluation (after Phase 2)**
- ☐ **BID-PR-12**: Config-driven bidder selection
- ☐ **BID-PR-13**: Online evaluator (expected points, make-rate, CVaR-5%, downside variance)
- ☐ **BID-PR-14**: bid_eval_tiny suite (fast end-to-end)
- ☐ **BID-PR-15**: Scheduled bid_eval_full workflow (report-only first)

**Phase 4: Future Expansion (long-term, deferred)**
- ☐ **BID-PR-16**: Seat/dealer/position awareness (observation v2)
- ☐ **BID-PR-17**: Partner bid awareness (observation v3)
- ☐ **BID-PR-18**: Value model bidder (argmax over contracts, Q-learning)

### 2. Agent Execution Correctness / Low Leak (ONGOING)

- Agents must use gold-path commands ✅
- Prevent new one-off runners/entrypoints ✅
- Deterministic experiments by default ✅
- Reproducibility is non-negotiable ✅
- Strict layer boundaries and import hygiene ✅
- No committed generated outputs, ever ✅
- Drift detection for regression protection ✅
- **NEW**: Bidding model training must be prediction-deterministic (byte-identical artifacts not required)

### 3. Infrastructure Maintenance (LOW PRIORITY, stable)

- Drift detection is production-ready (PRs #76–#86)
- No new infrastructure work needed unless issues arise
- Focus remains on bidding model development

---

## CONSTRAINTS

- Prefer "quarantine + deprecate + delete later" over risky sweeping changes.
- Do not invent repo details—if something is missing/unclear, say so and propose how to verify.
- Bias toward deterministic, reproducible, and CI-validated changes.
- Keep future PRs small and incremental.

---

## TASKS

### A) Audit the Repo

1. Map the current structure:
   - Boundaries: `src/`, `experiments/`, `scripts/`, `tests/`, `docs/`, `data/`
   - Entrypoints and runners (identify "one true" runner; find competing scripts)
   - Experiment configs and output layout (confirm run output contract)
   - Reporting entrypoint and its I/O contract
   - Drift detection pipeline and its contract
   - Bidding + training pipelines and where they live

2. Summarize "what exists" vs "what should exist":
   - What is core and stable
   - What is legacy/deprecated
   - What violates intended boundaries (if anything)

3. Verify known issues status:
   - Empty docs: Are they still 0 bytes?
   - experiments/README.md: Is config list accurate?
   - DRIFT.md: Does schema match fixture?

4. Identify additional leak points (beyond known issues):
   - Nondeterminism (seed enforcement, per-deal seed derivation, RNG sources)
   - Duplicate runners / multiple ways to do the same thing
   - Code placed in wrong layer
   - Generated artifacts written outside run dirs
   - Configs drifting / unclear config precedence

5. Identify "thin ice" areas:
   - Areas likely to break determinism or correctness
   - Brittle tests or xfails hiding problems
   - Drift comparator edge cases

Deliverable: 10–20 bullet repo summary + known issues status + any new leak points with mitigations.

---

### B) Repo Cleanup Plan (staged, PR-sized, low-risk)

1. Classify files/folders: Keep (core) / Move (wrong location) / Quarantine (deprecated but referenced) / Delete (dead)
2. Propose target structure: Define what belongs in each folder; what is forbidden; single "gold paths" for: run experiment, generate report, run suite, compare drift
3. Enforcement proposals: Additional repo-linter rules if needed
4. Risk/reward for each step
5. Cleanup PR sequence (5–10 PRs): goal, scope, acceptance criteria, gates

Deliverable: Ranked actions + PR plan + "do not touch yet" list.

---

### C) Docs Plan + Drafts

1. Docs map: path → purpose → status → priority

| Path | Status | Priority | Notes |
|------|--------|----------|-------|
| docs/01_core/ARCHITECTURE.md | Good | — | Accurate |
| docs/01_core/BASELINE.md | Good | — | Accurate |
| docs/01_core/DRIFT.md | Good | — | Accurate (fixed PR #78) |
| docs/01_core/EXPERIMENTS.md | Good | — | Accurate |
| docs/01_core/METRICS.md | Good | — | Accurate |
| docs/01_core/REPRODUCIBILITY.md | Good | — | Accurate |
| docs/01_core/SCORING.md | Good | — | Matches code |
| docs/02_agent/AGENTS.md | Good | — | Strong operational doc |
| docs/02_agent/PR_PROMPT_TEMPLATES.md | Good | — | Parallel-safe + auth gate |
| docs/DEVELOPMENT.md | Good | — | Matches Makefile/CI |
| experiments/README.md | Good | — | Accurate (fixed PR #77) |
| docs/archive/** | Stale | — | Has ARCHIVED banner |

**Deleted (PR #76):** docs/01_core/ROADMAP.md, SCHEMA_VERSIONING.md, STYLEGUIDE.md, TESTING_STRATEGY.md, docs/CHANGELOG.md, docs/CONTRIBUTING.md

2. Draft highest leverage docs aligned to current gates

Deliverable: 2–4 fully verified/updated docs + status assessment for others.

---

### D) Roadmap from Here (sequenced PRs)

**Status:** PR #97 (GH #97 / BID-PR-04) is complete. Bidding infrastructure foundation established. Now completing Phase 1 (dataset correctness + determinism) before moving to training.

**Roadmap IDs:** Using **BID-PR-XX** as stable roadmap identifiers, mapped to GitHub PR numbers where known.

---

#### **PHASE 0: Core Plumbing** (DONE — GH PRs #91–#97)

**BID-PR-00 — Docs: worktrees enforced in agent workflow** (DONE — GH #91)
- **Files:** `.github/pull_request_template.md`, `docs/02_agent/PR_PROMPT_TEMPLATES.md`
- **Summary:** Hard-gates worktrees + proof outputs so parallel PRs stop corrupting each other
- **Captured answers:** Worktrees mandatory; agents must prove worktree before edits

**BID-PR-01 — Tests: lock auction bidding rules v1** (DONE — GH #92)
- **Files:** `tests/unit/test_auction_bidding_rules.py`
- **Summary:** Freezes: single-round auction, strict-increasing, redeal-on-all-pass, winner leads
- **Captured answers:** Single round; all-pass redeal; strict increasing; action = (n, contract) with n=0 pass; contract set {S, H, D, C, HIGH, LOW}

**BID-PR-02 — Docs: GH auth sandbox guidance** (DONE — GH #94)
- **Files:** `docs/02_agent/PR_PROMPT_TEMPLATES.md`
- **Summary:** Makes `gh` reliable in sandbox via GH_TOKEN + full-permissions mode

**BID-PR-03 — Tests: bidding dataset schema guard v1** (DONE — GH #95)
- **Files:** `tests/unit/test_bidding_dataset_schema.py`, `data/fixtures/bidding_dataset_tiny.jsonl`
- **Summary:** CI guardrail so dataset schema doesn't drift silently

**BID-PR-04 — Fix/Feature: wire `--emit-bidding-dataset` end-to-end** (DONE — GH #97)
- **Files:** `experiments/run_experiment.py`, `src/bid_euchre/datasets/bidding.py`, `src/bid_euchre/sim/simulation.py`, `tests/unit/test_bidding_dataset_schema.py`
- **Summary:** Flag now emits `<RUN_DIR>/datasets/bidding.jsonl`, gated to auction mode, deterministic modulo run_id timestamp
- **Captured answers:** v1 emits per-seat decision rows; v1 observation = own hand + current_high_bid only (no history); no behavior change when flag off or non-auction
- **Follow-up:** Dataset determinism "stable excluding run_id timestamp" — addressed in BID-PR-07

---

#### **PHASE 1: Dataset Correctness + Parquet + Determinism Polish** (must complete before training)

**BID-PR-05 — Feat: switch dataset to Parquet (canonical) with minimal churn**
- **Files:** `src/bid_euchre/datasets/bidding.py`, `experiments/run_experiment.py`, `pyproject.toml` (add pyarrow dependency), docs + tests/fixtures
- **Depends on:** BID-PR-04 (complete)
- **Goal:** Make Parquet the canonical emitted dataset format
- **Scope:**
  - Add minimal dependency (pyarrow)
  - Emit to `data/runs/<run_id>/datasets/bidding.parquet`
  - Add `--bidding-dataset-format parquet|jsonl` flag (default: parquet)
  - Keep JSONL as escape hatch for debugging/transition
  - Keep emission gated to auction mode + `--emit-bidding-dataset` flag
- **Acceptance:** Parquet emitted by default, schema matches docs, `make check` passes
- **Priority:** HIGH (docs already say Parquet is primary, but only JSONL implemented)
- **Captured answers:** Dataset format = **Parquet**; output under run dir; JSONL optional for debug

**BID-PR-06 — Feat/Test: attempted vs effective bid fields + schema bump**
- **Files:** `src/bid_euchre/datasets/bidding.py`, `src/bid_euchre/sim/simulation.py`, `tests/unit/test_bidding_dataset_schema.py`, `data/fixtures/bidding_dataset_tiny.*`
- **Depends on:** BID-PR-05
- **Goal:** Add explicit columns to distinguish attempted bids from effective actions (for calibration analysis)
- **Scope:**
  - Add columns: `attempted_bid_n`, `attempted_bid_contract`, `attempted_bid_trump_suit`
  - Add columns: `effective_bid_n`, `effective_bid_contract`, `effective_bid_trump_suit`
  - Add column: `is_legal_raise` (bool)
  - Update fixture (Parquet + JSONL if kept) and schema tests
  - When policy proposes illegal raise (n ≤ current_high_bid), record attempted bid AND effective action (PASS)
- **Acceptance:** Illegal proposals recorded with both attempted and effective fields, tests pass
- **Priority:** HIGH (needed for calibration analysis and debugging bidding behavior)
- **Captured answers:** **Record attempted bid**; legality rule: n=0 or n≤current_high_bid ⇒ effective PASS

**BID-PR-07 — Feat: make dataset deterministic without "normalize run_id" hacks**
- **Files:** `src/bid_euchre/datasets/bidding.py`, `tests/unit/test_bidding_dataset_schema.py`
- **Depends on:** BID-PR-05 (can parallelize with BID-PR-06 but sequential safer)
- **Goal:** Achieve byte-identical determinism across runs by removing timestamped run_id from row data
- **Scope:**
  - **Approach:** Move run_id to Parquet metadata instead of row-level data
  - Add test verifying byte-identical datasets (same seed, different run_id timestamps)
  - Document determinism guarantee in schema docs
- **Acceptance:** sha256(dataset.parquet) matches across identical seeded runs
- **Priority:** MEDIUM (determinism already verified modulo run_id; this enables easier diffing)
- **Captured answers:** Training must be **prediction-deterministic**; use **Option 2** (Parquet metadata)

**Parallelism for Phase 1:**
- **Sequential (recommended):** BID-PR-05 → BID-PR-06 → BID-PR-07
  - Reason: All three touch dataset emitter; sequential avoids merge conflicts
- **Alternative (if needed):** BID-PR-05 → (BID-PR-06 + BID-PR-07 parallel)
  - Conflict risk: Both BID-PR-06 and BID-PR-07 modify emitter, but BID-PR-07 is metadata-only change (lower risk)

---

#### **PHASE 2: Imitation Training v1** (get models bidding end-to-end)

**BID-PR-08 — Feat: define model artifact v1 (JSON-only, string-based contracts)**
- **Files:** `src/bid_euchre/models/bidding_artifact.py` (new), `docs/01_core/BIDDING_MODEL.md` (new)
- **Depends on:** BID-PR-06 (final v1 dataset fields)
- **Goal:** Define small, deterministic JSON artifact schema for bidding models
- **Scope:**
  - **Artifact format:** JSON only (no pickle/binaries)
  - **Contract encoding:** Keep as strings ("C", "D", "H", "S", "HIGH", "LOW") — no enum needed
  - **Fields:** schema_version, feature_schema_version, model_type (e.g., "logistic_regression"), teacher_policy_name, model_params
  - Document artifact schema and versioning
- **Acceptance:** Artifact schema documented, JSON-serializable, matches dataset contract
- **Priority:** HIGH (required before training)
- **Captured answers:** **JSON only**; contracts as **strings** (n, contract) format; no enum/int mapping needed

**BID-PR-09 — Feat: training pipeline v1 (imitation learning) for three teacher models**
- **Files:** `src/bid_euchre/models/train_bidder.py` (new, library-first), minimal wrapper in `scripts/train_bidder.py` if needed
- **Depends on:** BID-PR-08
- **Goal:** Train **three** imitation models from different teacher policies
- **Scope:**
  - **Model A:** Imitates `StrictRaiserBidder` (deterministic baseline)
  - **Model B-Suit:** Imitates `HeuristicSuitBidder` (hand-strength-based suit contracts)
  - **Model B-HighLow:** Imitates `HighLowHeuristicBidder` (card-composition-based HIGH/LOW)
  - All models use same dataset contract, produce JSON artifacts per BID-PR-08
  - Prediction-deterministic training (same data/config → same predictions)
  - Keep it simple: logistic regression or simple classifier (best choice for deterministic + serializable)
- **Acceptance:** Three models trained, three JSON artifacts emitted, training deterministic
- **Priority:** HIGH (core training pipeline)
- **Captured answers:** v1 label strategy = **teacher imitation**; train **three models** separately; libraries: best choice for determinism

**BID-PR-10 — Feat: ModelBidder loads artifact and produces deterministic bids**
- **Files:** `src/bid_euchre/strategy/bidding.py` or `src/bid_euchre/strategy/model_bidder.py` (new)
- **Depends on:** BID-PR-08
- **Goal:** Deterministic inference wrapper that loads JSON artifacts and produces bids
- **Scope:**
  - Load JSON artifact
  - Predict action deterministically (same observation → same output)
  - Apply legality rules: if predicted n ≤ current_high_bid, effective action is PASS (but record attempted)
  - Optionally emit attempted/effective fields for logging
  - Integrate with experiment runner via config-driven selection
- **Acceptance:** Inference deterministic, integrates with experiment runner, illegal bids handled correctly
- **Priority:** HIGH (required for evaluation)
- **Captured answers:** Inference must be **deterministic**; illegal bids treated as PASS but attempted recorded

**BID-PR-11 — Tests: inference determinism + schema compatibility guards**
- **Files:** `tests/unit/test_bidder_model_inference.py` (new), fixture artifacts (small JSON files)
- **Depends on:** BID-PR-09 + BID-PR-10
- **Goal:** Lock determinism and prevent "model loads but behaves differently" regressions
- **Scope:**
  - Given fixed fixture dataset + artifact: predictions identical across runs
  - Feature schema version must match between artifact and dataset
  - Contract mapping stability (strings stay strings)
  - Test all three models (A, B-Suit, B-HighLow)
- **Acceptance:** Tests pass, determinism verified for all three models
- **Priority:** HIGH (prevents regressions)
- **Captured answers:** **Prediction-deterministic** is required

**Parallelism for Phase 2:**
- **Sequential (required):** BID-PR-08 → BID-PR-09 → BID-PR-10 → BID-PR-11
  - Reason: Each depends on previous; no parallelization possible

---

#### **PHASE 3: Online Evaluation as Truth + Suites + CI Signal**

**BID-PR-12 — Feat: config-driven bidder selection (no new runners)**
- **Files:** `experiments/run_experiment.py`, `experiments/configs/*.yaml`, config schema docs
- **Depends on:** BID-PR-10 (ModelBidder inference ready)
- **Goal:** Choose bidding policy/model via experiment config (canonical runner only)
- **Scope:**
  - Add config key for bidder selection (e.g., `bidding_policy: model_a` or `bidding_policy: heuristic_suit`)
  - Support model artifact paths (e.g., `bidding_model_artifact: data/artifacts/model_a.json`)
  - Preserve "no-policy default = non-auction random contract" **forever** (backward compat guarantee)
  - No new runners — only canonical `experiments/run_experiment.py`
- **Acceptance:** Config-driven selection works, backward compat maintained, model artifacts loadable
- **Priority:** HIGH (required for evaluation)
- **Captured answers:** **No-policy default** stays non-auction/random forever; canonical runner only

**BID-PR-13 — Feat: online bidder evaluator CLI (truth metric) + per-hand risk metrics**
- **Files:** `scripts/eval_bidder.py` (new), `src/bid_euchre/eval/bidding.py` (new, library helper)
- **Depends on:** BID-PR-12
- **Goal:** Run full simulations with bidder policies and report comprehensive metrics
- **Scope:**
  - **Primary metric:** `expected_points` (mean of bidder_team_points across all hands)
  - **Secondary metric:** `make_rate` (fraction of contracts made by bidder's team)
  - **Risk metrics (per-hand basis on `bidder_team_points`):**
    - `cvar_5pct`: Conditional Value at Risk at 5th percentile (mean of worst 5% outcomes)
    - `downside_variance`: Variance of negative per-hand points only
  - **Debug metrics:** `team0_points`, `team1_points` (for sanity checking)
  - Output: JSON report with all metrics, rollup structure compatible with drift detection
  - CLI: `scripts/eval_bidder.py --config <path> --bidder <policy_name> --n_hands <N>`
- **Acceptance:** Evaluator runs, all metrics calculated and reported, deterministic given seed
- **Priority:** HIGH (core evaluation infrastructure)
- **Captured answers:** **EV > make-rate > win-rate**; risk important; risk metrics basis = **per-hand bidder_team_points**; CVaR-5% + downside variance

**BID-PR-14 — Code+Test: bid_eval_tiny suite (fast end-to-end)**
- **Files:** `experiments/suites/bid_eval_tiny.yaml`, rollup wiring/tests
- **Depends on:** BID-PR-13
- **Goal:** One command produces a deterministic bidder evaluation rollup with new metrics
- **Scope:**
  - Small suite (< 1 minute, ~100 hands per bidder config)
  - Compare 2-3 bidders (e.g., StrictRaiser vs Model A vs HeuristicSuit)
  - Rollup emits: expected_points, make_rate, cvar_5pct, downside_variance, team0/team1 debug
  - Reproducible results (seeded)
  - Suite runner: `scripts/run_suite.py experiments/suites/bid_eval_tiny.yaml`
- **Acceptance:** Suite runs, rollup JSON emitted with all metrics, deterministic
- **Priority:** HIGH (fast validation before CI)
- **Captured answers:** Fast validation suite for bidder comparison

**BID-PR-15 — CI: scheduled bid_eval_full workflow (report-only first)**
- **Files:** `.github/workflows/bid_eval_full.yml`
- **Depends on:** BID-PR-14
- **Goal:** Nightly/weekly evaluation producing trend artifacts and reports
- **Scope:**
  - Report-only (no PR gating yet — gating decision after stability period)
  - Larger suite (5-10 minutes, ~1000 hands per bidder config)
  - Compare all available bidders (heuristics + trained models)
  - Create GitHub issue or comment with results table (expected_points, make_rate, cvar_5pct, downside_variance)
  - Store artifacts for trend analysis
- **Acceptance:** Workflow runs on schedule, report generated, no false positives
- **Priority:** MEDIUM (can defer until models trained)
- **Captured answers:** Start **report-only**; gating decision comes after stability

**Parallelism for Phase 3:**
- **Sequential (required):** BID-PR-12 → BID-PR-13 → BID-PR-14 → BID-PR-15
  - Reason: Each depends on previous; BID-PR-15 can be developed in parallel with BID-PR-14 once BID-PR-13 is stable

---

#### **PHASE 4: Future Expansion** (long-term, explicitly postponed until Phase 3 stable)

**BID-PR-16 — Feat: seat/dealer/position awareness (observation v2)**
- **Files:** `src/bid_euchre/datasets/bidding.py`, observation contract docs, training pipeline
- **Depends on:** BID-PR-15 (Phase 3 stable) + explicit decision to add positional awareness
- **Goal:** Expand observation contract to include positional information
- **Scope:**
  - **v2 observation:** hand + current_high_bid + seat + dealer_seat (used in training, not just metadata)
  - **Why deferred:** v1 explicitly excludes positional awareness to keep models simple and prevent overfitting to position-specific patterns before we understand baseline performance
  - Update dataset schema version (v2)
  - Retrain models with v2 observations
  - Compare v1 vs v2 performance
- **Acceptance:** v2 models trained, performance compared to v1, documented decision on whether to adopt
- **Priority:** FUTURE (explicit v1 → v2 upgrade decision point)
- **Captured answers:** **v1 explicitly no seat/dealer/position**; add later as v2

**BID-PR-17 — Feat: partner bid awareness (observation v3)**
- **Files:** `src/bid_euchre/datasets/bidding.py`, observation contract docs, training pipeline
- **Depends on:** BID-PR-16 (v2 stable)
- **Goal:** Add bidding history within the round (partner bid awareness)
- **Scope:**
  - **v3 observation:** v2 + partner's bid (n, contract) if available (still no opponent bids, no hand leakage)
  - **Why deferred:** Single-round auction means limited partner signal; focus on hand-strength first
  - Update dataset schema version (v3)
  - Retrain models with v3 observations
  - Compare v2 vs v3 performance
- **Acceptance:** v3 models trained, performance gains documented
- **Priority:** FUTURE (after v2 evaluation)
- **Captured answers:** Bidding history (partner only first) added as v3

**BID-PR-18 — Feat: value model (argmax over contracts) — postpone until v2+**
- **Files:** `src/bid_euchre/datasets/bidding.py` (outcome labels), `src/bid_euchre/models/...`, `src/bid_euchre/strategy/...`
- **Depends on:** BID-PR-15 (Phase 3 evaluation stable) + sufficient training data
- **Goal:** Predict EV(points) for each (n, contract) action and select argmax
- **Scope:**
  - Extend dataset with outcome labels: `points_delta`, `made_bid`, `risk_signal` (per-hand)
  - Train value model: Q(observation, action) → expected_points
  - Inference: enumerate all legal (n, contract) pairs, predict value for each, select argmax
  - Compare imitation (Phase 2) vs value model (Phase 4) performance
- **Acceptance:** Value model trained, argmax selection works, outperforms imitation baseline
- **Priority:** FUTURE (explicitly deferred until imitation + evaluation pipeline stable)
- **Captured answers:** "Regress over all combos" approach; postpone until v2+

**Versioning Summary:**
- **v1 (current):** hand + current_high_bid only (no seat/dealer/position/history)
- **v2 (future):** v1 + seat + dealer_seat (positional awareness)
- **v3 (future):** v2 + partner bid history (limited history)
- **v4+ (future):** Potentially full bidding history, opponent modeling, etc. (TBD)

---

#### **Next Immediate Steps** (recommended execution order)

**Phase 1 (start now):**
1. **BID-PR-05** (Parquet emission) — must go first
2. **BID-PR-06** (attempted vs effective fields) — immediately after BID-PR-05
3. **BID-PR-07** (stable dataset identity) — after BID-PR-06 (or parallel with conflict risk)

**Phase 2 (after Phase 1 complete):**
4. **BID-PR-08** (artifact spec) → **BID-PR-09** (training) → **BID-PR-10** (inference) → **BID-PR-11** (tests)
   - Sequential only

**Phase 3 (after Phase 2 complete):**
5. **BID-PR-12** (config-driven) → **BID-PR-13** (evaluator) → **BID-PR-14** (tiny suite) → **BID-PR-15** (CI)
   - Sequential, but BID-PR-15 can parallelize with BID-PR-14 once BID-PR-13 stable

**Phase 4 (long-term):**
6. Defer until Phase 3 demonstrates stable evaluation pipeline

---

## ROADMAP DECISIONS CAPTURED

All roadmap design decisions have been resolved and incorporated into BID-PR-00 through BID-PR-18 above:

1. **Teacher policies (BID-PR-09):** Train **three models** — Model A (StrictRaiser), Model B-Suit (HeuristicSuitBidder), Model B-HighLow (HighLowHeuristicBidder)
2. **Contract encoding (BID-PR-08):** Use **strings** (no enum) — (n, contract) format matches current BidAction
3. **Risk metrics (BID-PR-13):** **CVaR-5% + downside variance** on per-hand `bidder_team_points`, plus expected_points (primary) and make_rate (secondary)
4. **Dataset determinism (BID-PR-07):** Move run_id to **Parquet metadata** (not row data)
5. **Observation versioning:** v1 (current) excludes seat/dealer; v2 (future) adds position; v3 (future) adds partner history; v4+ (TBD)
6. **Sequencing:** Strict phase gating (Phase 1 → Phase 2 → Phase 3 → Phase 4) with sequential execution within phases to minimize merge conflicts

---

## OUTPUT FORMAT (required)

1. Repo Summary (10–20 bullets)
2. Known Issues Status (verify each from KNOWN ISSUES section)
3. Additional Leak Points + Mitigations (if any found beyond known issues)
4. Cleanup Plan
   - Ranked actions
   - PR sequence with acceptance criteria
   - "Do not touch yet" list
5. Docs Map (path → status → priority)
6. Docs Assessment (2–4 docs verified/updated; status of others)
7. Roadmap
   - Next 5 PRs detailed (with acceptance criteria)
   - Medium/long-term milestones

---

## VERIFICATION COMMANDS

Run these to verify current state:

```bash
# Verify bidding infrastructure exists
ls docs/01_core/BIDDING.md docs/01_core/BIDDING_DATASET.md
ls src/bid_euchre/datasets/bidding.py
ls src/bid_euchre/strategy/bidding.py
ls data/fixtures/bidding_dataset_tiny.jsonl
ls tests/unit/test_bidding_dataset_schema.py

# Verify bidding dataset emission flag
python experiments/run_experiment.py --help | grep -A2 bidding

# Verify baseline bidders exist (PR #96)
grep "class.*Bidder" src/bid_euchre/strategy/bidding.py

# Verify dataset schema guard tests exist
pytest tests/unit/test_bidding_dataset_schema.py -v

# Verify drift infrastructure still intact
ls .github/workflows/baseline_full_drift.yml
python scripts/compare_rollup.py --help

# Run make check to validate everything
make check
```

---

## NOTE

- Do not claim something exists unless you can point to it in the ZIP.
- When unsure, say what you looked for and how to verify.
- Bias toward minimal changes that strengthen correctness, determinism, and agent execution reliability.
- Verify known issues before proposing fixes — some may have been resolved since last review.
