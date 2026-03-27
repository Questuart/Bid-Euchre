# Architecture

This document defines the repository structure, module boundaries, and canonical execution paths.

## Repo Layers and Boundaries

### `src/bid_euchre/`
**Library code only.** Contains importable modules for game simulation, strategies, and analysis.

**Hard rule**: Code in `src/` must NOT import from `experiments/` or `tests/`.

Submodules:
- `core/` — Game mechanics (cards, rules)
- `strategy/` — Strategy implementations
- `features/` — Hand evaluation
- `sim/` — Simulation engines
- `experiments/` — Configuration system (StrategyConfig, ExperimentConfig)
- `datasets/` — Dataset collectors (bidding, bidless)
- `models/` — Model training/inference
- `diagnostics/` — Visualization and analysis tools
- `validation/` — Schema validation
- `arc_d_v2/` — Arc D v2 lineage: typed schemas, paths, configuration (orchestration and reporting scripts import from here)
- `ops/` — Operator tooling (internal): status, worktrees, events, watchdogs, scheduler
- `reporting/`, `logging/`, `analysis/` — Supporting utilities
- `scoring.py` — Top-level scoring module (compute_points)

### `experiments/`
**Experiment configurations and canonical runner.**

Structure:
- **`run_experiment.py`** — **Blessed canonical runner** (use this for production workflows)
- `configs/` — YAML experiment configurations (reproducible inputs)
- `_deprecated/` — Legacy scripts (do not use or extend)
- `comparisons/`, `training/` — Exploratory research scripts (not canonical; for ad-hoc exploration)

**Note**: Only `run_experiment.py` is the blessed entrypoint. Other scripts in subfolders are for research exploration and must not define competing canonical paths.

**Disambiguation**: `experiments/` is a filesystem directory (YAML configs + runner). `bid_euchre.experiments` (under `src/bid_euchre/experiments/`) is the library config module. Do not `import experiments` as a Python package.

### `scripts/`
**Blessed tooling entrypoints.**

Canonical scripts:
- `check_docs_freshness.py` — Docs freshness gate (path refs + script list completeness)
- `check_infra_pr_metadata.py` — Infra PR metadata checker (advisory governance gate)
- `compare_rollup.py` — Drift detection (compares rollup against baseline fixture)
- `compare_runs.py` — Run comparison utility with bootstrap statistics
- `generate_dashboard.py` — Commit analytics dashboard (churn-corrected Bollinger Bands)
- `generate_report.py` — Per-run report generator
- `lint_repo.py` — Repository linter (enforces boundaries and data policy)
- `run_bidless_diagnostics.py` — Bidless feature dataset diagnostics
- `run_charts.py` — Production chart generation (extracted from `reporting.chart_runner`)
- `run_notebooks.py` — Notebook execution via papermill (CI tooling)
- `run_suite.py` — Suite runner (batches experiments with rollup generation)
- `run_tests.py` — Test runner utility
- `train_b0.py` — B0 hand value model training (extracted from `models.train_b0`)
- `train_bidder.py` — Bidder model training
- `train_hybrid_olsa.py` — Hybrid OLSa training pipeline (Arc D)
- `train_olsa.py` — OLSa model training (extracted from `models.train_olsa`)
- `update_r0_bundle.py` — Update R0 rung bundle with eval paths (Arc D)
- `validate_configs.py` — Config validation utility
- `validate_teacher_roster.py` — Teacher roster validation
- `write_r0_promotion.py` — Write R0 auto-promotion decision (Arc D)

Deprecation wrappers (forward to `scripts/internal/` with a warning):
- `evaluate_diagnostic_tricks.py`, `play_policy_gate.py`, `run_auction_comparator.py`

Shell scripts:
- `run_r0b.sh` — R0 baseline lock reproduction commands (Arc D Wave 3)

### `scripts/internal/`
**Research and internal tooling.** Not part of the canonical experiment workflow.
Arc D v2 lineage scripts (orchestrator, reporting) are canonical execution tools
that import typed schemas and paths from `bid_euchre.arc_d_v2`.

- `analyze_phase1a_matrix.py` — Phase 1A 2×2 model×label matrix H2H analysis (effect decomposition)
- `audit_analysis.py` — Review pipeline audit (follow-up rates, corrective PRs, per-PR trail)
- `blind_strategy_comparison.py` — Blind strategy comparison for Arc D evaluation (anonymize, rubric, unblind)
- `calibrate_arc_d_thresholds.py` — Arc D gate threshold calibration from H2H null signal
- `claude_fix_adapter.py` — Deterministic fix application from Codex findings (auto-fix + commit)
- `codex_plan_review_adapter.py` — Codex CLI plan review adapter (tier detection, plan-scoped invocation, Claude failsafe)
- `codex_review_adapter.py` — Codex CLI invocation and output parsing (review findings extraction)
- `confidence_scorer.py` — Deterministic confidence scoring for P2 review findings (heuristic filtering)
- `deterministic_prechecks.py` — Fast deterministic code checks (merge markers, RNG, imports)
- `evaluate_diagnostic_tricks.py` — Diagnostic Ridge evaluation
- `evaluate_gate_x3.py` — R1.5 Gate X3 offline ranking evaluation (action-value model vs oracle)
- `extract_comparator_cis.py` — Bootstrap CIs for comparator battery metrics
- `generate_action_value_dataset.py` — Counterfactual action-value dataset generator (R1.5)
- `generate_advance_check.py` — Arc D v2 advance check generator (hypothesis + sufficiency + canary evaluation)
- `generate_arc_dashboard.py` — Cross-rung Arc D progression dashboard
- `generate_auction_context_dataset.py` — Auction-context dataset generator (R1 partner features)
- `generate_batch_report.py` — Batch report + eligibility gate
- `generate_cross_rung_tables.py` — Cross-rung progression table from per-rung comparator CIs
- `generate_evidence_manifest.py` — Evidence manifest generator (JSON + markdown) for Arc D v2
- `generate_interpretability.py` — Interpretability pipeline (SHAP, selection paths, decision comparison)
- `generate_interpretability_charts.py` — Interpretability chart generation from CSV data
- `generate_r1_5_diagnostics.py` — R1.5-v2 calibration diagnostics (cross-rung analysis + bimodality tests)
- `generate_r4_charts.py` — One-off report chart regeneration utility
- `generate_rung_charts.py` — CSV-first rung chart generation for Arc D v2 reports
- `generate_rung_report.py` — Markdown rung report renderer from CSV tables and chart PNGs
- `generate_rung_tables.py` — Canonical CSV table generation for Arc D v2 rung reports
- `github_pr_state.py` — GitHub CLI wrappers for PR metadata and CI status
- `manage_artifacts.py` — Artifact lifecycle CLI (status, supersession, quarantine, prune)
- `manage_invite_codes.py` — Invite code admin CLI (generate, list, revoke) for browser game pilot access
- `plan_review_driver.py` — Plan review loop orchestrator (Codex -> fix -> re-review cycles with fallback alerting)
- `play_policy_gate.py` — Play policy stability gate
- `review_common.py` — Shared severity constants and predicates for the review pipeline
- `review_driver.py` — Autonomous review loop orchestrator (state machine)
- `review_lane_runner.py` — Shadow-mode review lane queue processor (claims requests, invokes steward-review, writes SHA-bound verdicts)
- `review_state.py` — Review loop state schema, persistence, and transitions
- `run_arc_d_gate.py` — Arc D promotion gate runner
- `run_arc_d_h2h_battery.py` — H2H all-vs-all battery runner (competitive validation)
- `run_auction_comparator.py` — Auction comparator orchestrator
- `run_lambda_sweep.py` — Simulation-based risk_lambda tuning sweep
- `run_normalizer_offline_screen.py` — Normalizer go/no-go offline screening pipeline
- `run_play_confound_audit.py` — E1 play-policy confound audit (ranking comparison)
- `run_rung.py` — Arc D v2 rung orchestrator (9-step runbook execution, multi-seed, QUICK/FULL pipeline)
- `run_threshold_sweep.py` — Grid search over pass_threshold values (R1 threshold tuning)
- `rung_state.py` — Rung orchestrator state management (RunState persistence, step/model tracking)
- `suit_decision_diagnostic.py` — R1.5.3 Step 0 decision-level suit diagnostic (error taxonomy, boundary analysis)
- `test_codex_plan_review_live.py` — Live smoke/quick/full test for Codex CLI plan review pipeline
- `test_review_infra.py` — Tiered (SMOKE/QUICK/FULL) end-to-end review infrastructure test harness
- `train_action_value.py` — Action-value OLS training pipeline (R1.5)
- `train_unified_model.py` — Unified cross-contract OLS training (Track F OneModel)
- `update_arc_registry.py` — Arc D registry updater (MODEL_ARC_RUNS.md)
- `validate_action_value_artifact.py` — Behavioral validation gate for action-value artifacts
- `validate_arc_d_rung_contract.py` — Arc D rung bundle validator

Shell scripts:
- `ci_poller.sh` — Background CI poller; monitors GitHub PR checks with optional auto-merge (launched by post-push hook)
- `clean_worktrees.sh` — Removes git worktrees and local branches whose upstream remote has been deleted (`[gone]`)
- `overnight_full_orchestrator.sh` — Sequential overnight orchestrator for FULL-mode Arc D v2 rung runs (all rungs x seeds)
- `set_review_status.sh` — Publishes GitHub commit statuses for the review gate (`reviewing-changes` context)

Deprecation wrappers at old paths (`scripts/*.py`) forward to `scripts/internal/` with a warning.

### `tests/`
**Test suite only.**

Structure:
- `unit/` — Fast, isolated tests
- `integration/` — Multi-component tests
- `performance/` — Benchmarks (marked as slow)
- `property/` — Property-based tests

### `data/`
**Generated outputs and fixtures.**

**Commit policy**:
- ✅ **Allowed**: `data/fixtures/` only (tiny, intentional test/doc fixtures)
- ❌ **Forbidden**: All generated outputs (`data/runs/`, legacy paths)

See `DATA_CONTRACT.md` for full details.

---

## Gold Path Commands

Run before opening a PR (either one):

```bash
make check-quiet    # Same validation, minimal output — preferred (logs to tmpfile)
make check          # Full validation (repo-lint + lint + tests)
```

Individual checks:

```bash
make repo-lint      # Repository linter only
make lint           # Ruff (format + lint) only
make test           # Pytest (fast suite) only
```

**Agents must use these commands. Do not invent one-off runners.**

---

## Canonical Execution Paths

### Run an experiment

Use the unified runner:

```bash
uv run python experiments/run_experiment.py --config experiments/configs/quick_test.yaml --seed 42
```

**Required**: `--seed` (unless you opt in to nondeterminism via `--allow-nondeterministic`)

### Generate a report

Use the blessed report entrypoint:

```bash
uv run python scripts/generate_report.py \
  --run-dir data/runs/<run_id>
```

**Options**: `--overwrite` to regenerate existing reports

---

## Run Output Contract

Every experiment run creates a standardized directory under `data/runs/<run_id>/` containing:

- `meta.json` — Run metadata (schema v2)
- `config_effective.yaml` — Resolved configuration snapshot
- `results/` — Machine-readable outputs (JSON, CSV)
- `logs/` — Structured logs (JSONL hand logs)
- `reports/` — Generated charts and dashboards
- `splits/` — Train/test/validation data (if generated)
- `artifacts/` — Model binaries and intermediates (if generated)

**Full details**: See `EXPERIMENTS.md` for complete run output structure and reproduction instructions.

---

## Canonical CLI Contract

### Primary commands (production workflows)

| Command | Purpose |
|---------|---------|
| `experiments/run_experiment.py` | Run experiments (seed required) |
| `scripts/generate_report.py` | Generate per-run reports |
| `scripts/run_suite.py` | Batch experiment runner |

### Supporting tooling

| Command | Purpose |
|---------|---------|
| `scripts/check_docs_freshness.py` | Docs freshness gate (path refs + script list) |
| `scripts/check_infra_pr_metadata.py` | Infra PR metadata checker (advisory governance gate) |
| `scripts/compare_runs.py` | Compare two runs with bootstrap statistics |
| `scripts/generate_dashboard.py` | Commit analytics dashboard (churn-corrected Bollinger Bands) |
| `scripts/compare_rollup.py` | Drift detection against baseline fixture |
| `scripts/lint_repo.py` | Repository linter |
| `scripts/run_charts.py` | Production chart generation |
| `scripts/run_notebooks.py` | Notebook execution via papermill (CI) |
| `scripts/run_tests.py` | Test runner utility |
| `scripts/validate_configs.py` | Config validation |
| `scripts/validate_teacher_roster.py` | Teacher roster validation |

### Internal tooling (`scripts/internal/`)

| Command | Purpose |
|---------|---------|
| `scripts/internal/analyze_phase1a_matrix.py` | Phase 1A 2×2 model×label matrix H2H analysis (effect decomposition) |
| `scripts/internal/audit_analysis.py` | Review pipeline audit (follow-up rates, corrective PRs) |
| `scripts/internal/blind_strategy_comparison.py` | Blind strategy comparison for Arc D evaluation (anonymize, rubric, unblind) |
| `scripts/internal/claude_fix_adapter.py` | Deterministic fix application from Codex findings (auto-fix + commit) |
| `scripts/internal/codex_plan_review_adapter.py` | Codex CLI plan review adapter (tier detection, plan-scoped invocation, Claude failsafe) |
| `scripts/internal/codex_review_adapter.py` | Codex CLI invocation and output parsing (review findings extraction) |
| `scripts/internal/confidence_scorer.py` | Deterministic confidence scoring for P2 review findings (heuristic filtering) |
| `scripts/internal/deterministic_prechecks.py` | Fast deterministic code checks (merge markers, RNG, imports) |
| `scripts/internal/evaluate_diagnostic_tricks.py` | Diagnostic Ridge evaluation |
| `scripts/internal/evaluate_gate_x3.py` | R1.5 Gate X3 offline ranking evaluation (action-value model vs oracle) |
| `scripts/internal/export_hosted_decisions.py` | CLI wrapper for exporting hosted-play decisions to JSONL (SP-4-01 schema) |
| `scripts/internal/extract_comparator_cis.py` | Bootstrap CIs for comparator battery metrics |
| `scripts/internal/generate_action_value_dataset.py` | Counterfactual action-value dataset generator (R1.5) |
| `scripts/internal/generate_advance_check.py` | Arc D v2 advance check generator (hypothesis + sufficiency + canary evaluation) |
| `scripts/internal/generate_arc_dashboard.py` | Cross-rung Arc D progression dashboard |
| `scripts/internal/generate_auction_context_dataset.py` | Auction-context dataset generator (R1 partner features) |
| `scripts/internal/generate_batch_report.py` | Batch report + eligibility gate |
| `scripts/internal/github_pr_state.py` | GitHub CLI wrappers for PR metadata and CI status |
| `scripts/internal/generate_r1_5_diagnostics.py` | R1.5-v2 calibration diagnostics (cross-rung analysis + bimodality tests) |
| `scripts/internal/generate_r4_charts.py` | One-off report chart regeneration utility |
| `scripts/internal/generate_cross_rung_tables.py` | Cross-rung progression table from per-rung comparator CIs |
| `scripts/internal/generate_rung_charts.py` | CSV-first rung chart generation for Arc D v2 reports |
| `scripts/internal/generate_rung_tables.py` | Canonical CSV table generation for Arc D v2 rung reports |
| `scripts/internal/generate_rung_report.py` | Markdown rung report renderer from CSV tables and chart PNGs |
| `scripts/internal/generate_evidence_manifest.py` | Evidence manifest generator (JSON + markdown) for Arc D v2 |
| `scripts/internal/generate_interpretability.py` | Interpretability pipeline (SHAP, selection paths, decision comparison) |
| `scripts/internal/generate_interpretability_charts.py` | Interpretability chart generation from CSV data |
| `scripts/internal/manage_artifacts.py` | Artifact lifecycle CLI (status, supersession, quarantine, prune) |
| `scripts/internal/manage_invite_codes.py` | Invite code admin CLI (generate, list, revoke) for browser game pilot access |
| `scripts/internal/play_policy_gate.py` | Play policy stability gate |
| `scripts/internal/plan_review_driver.py` | Plan review loop orchestrator (Codex -> fix -> re-review cycles with fallback alerting) |
| `scripts/internal/test_codex_plan_review_live.py` | Live smoke/quick/full test for Codex CLI plan review pipeline |
| `scripts/internal/test_review_infra.py` | Tiered (SMOKE/QUICK/FULL) end-to-end review infrastructure test harness |
| `scripts/internal/review_common.py` | Shared severity constants and predicates for the review pipeline |
| `scripts/internal/review_driver.py` | Autonomous review loop orchestrator (state machine) |
| `scripts/internal/review_lane_runner.py` | Shadow-mode review lane queue processor (claims requests, invokes steward-review, writes SHA-bound verdicts) |
| `scripts/internal/review_quality_audit.py` | Review-quality audit: scan loop artifacts, report missed blockers, noisy findings, deterministic-check candidates |
| `scripts/internal/review_state.py` | Review loop state schema, persistence, and transitions |
| `scripts/internal/rung_state.py` | Rung orchestrator state management (RunState persistence, step/model tracking) |
| `scripts/internal/run_rung.py` | Arc D v2 rung orchestrator (9-step runbook execution, multi-seed, QUICK/FULL pipeline) |
| `scripts/internal/calibrate_arc_d_thresholds.py` | Arc D gate threshold calibration from H2H null signal |
| `scripts/internal/run_arc_d_gate.py` | Arc D promotion gate runner |
| `scripts/internal/run_arc_d_h2h_battery.py` | H2H all-vs-all battery runner (competitive validation) |
| `scripts/internal/run_play_confound_audit.py` | E1 play-policy confound audit (ranking comparison) |
| `scripts/internal/run_auction_comparator.py` | Auction comparator orchestrator |
| `scripts/internal/run_lambda_sweep.py` | Simulation-based risk_lambda tuning sweep |
| `scripts/internal/run_normalizer_offline_screen.py` | Normalizer go/no-go offline screening pipeline |
| `scripts/internal/run_threshold_sweep.py` | Grid search over pass_threshold values (R1 threshold tuning) |
| `scripts/internal/suit_decision_diagnostic.py` | R1.5.3 Step 0 decision-level suit diagnostic (error taxonomy, boundary analysis) |
| `scripts/internal/train_action_value.py` | Action-value OLS training pipeline (R1.5) |
| `scripts/internal/train_unified_model.py` | Unified cross-contract OLS training (Track F OneModel) |
| `scripts/internal/update_arc_registry.py` | Arc D registry updater (MODEL_ARC_RUNS.md) |
| `scripts/internal/validate_action_value_artifact.py` | Behavioral validation gate for action-value artifacts |
| `scripts/internal/validate_arc_d_rung_contract.py` | Arc D rung bundle validator |
| `scripts/internal/verify_squash_merge.py` | Verify no files are dropped during stacked-PR squash merges |
| `scripts/internal/build_audit_index.py` | Build or rebuild the local SQLite FTS5 audit index over runtime artifacts |
| `scripts/internal/build_curated_memory.py` | Manage curated memory entries (add, remove, search, validate provenance) |
| `scripts/internal/compact_session_context.py` | Compact and archive session context with non-lossy artifact index |
| `scripts/internal/ci_poller.sh` | Background CI poller with optional auto-merge (launched by post-push hook) |
| `scripts/internal/clean_worktrees.sh` | Remove worktrees and branches whose upstream remote is deleted (`[gone]`) |
| `scripts/internal/ops.py` | Operator CLI for steward workspace health, worktree lifecycle, events, and monitoring |
| `scripts/internal/overnight_full_orchestrator.sh` | Sequential overnight orchestrator for FULL-mode Arc D v2 rung runs |
| `scripts/internal/set_review_status.sh` | Publish GitHub commit statuses for review gate contexts |

### Research tooling (canonical path)

| Command | Purpose |
|---------|---------|
| `scripts/run_bidless_diagnostics.py` | Bidless diagnostics |
| `scripts/train_b0.py` | B0 hand value model training |
| `scripts/train_bidder.py` | Bidder model training |
| `scripts/train_hybrid_olsa.py` | Hybrid OLSa training (Arc D) |
| `scripts/train_olsa.py` | OLSa model training |
| `scripts/update_r0_bundle.py` | Update R0 rung bundle with eval paths (Arc D) |
| `scripts/write_r0_promotion.py` | Write R0 auto-promotion decision (Arc D) |

---

## Module Dependency Contract

The following import edges are explicitly allowed between `reporting/` and `diagnostics/`:

| Edge | Status | Reason |
|------|--------|--------|
| `diagnostics/*.py` → `reporting.style` | Allowed | Shared styling constants |
| `reporting.charts` → `diagnostics.charts` | Allowed | Direct import for chart composition |
| `reporting.__init__` → `reporting.charts` | **Forbidden** | Would trigger circular import |
| `reporting.style` → `diagnostics.*` | **Forbidden** | Back-edge would create cycle |

These constraints are enforced by `tests/unit/test_import_contract.py`.

---

## Integration Policy

1. **Fresh branch from `origin/main`** per PR — never merge stale heads directly
2. **Cherry-pick or re-implement** intended commits only when rebasing across PRs
3. **One concept per PR** — mixed refactor + feature PRs are rejected
4. **Worktree-only workflow** — all code changes happen in dedicated worktrees, never on `main`

---

## Promotion Workflow

Promotion-track PRs (labeled `promotion`) must pass the promotion CI gate:
`make promotion-gate` (repo-lint + notebook smoke + gate assertion).

See `docs/02_agent/PROMOTION_WORKFLOW.md` for the full end-to-end workflow including
split manifests, artifact freeze, notebook gates, and reviewer checklist.

---

## Design Principles

1. **Single source of truth**: One canonical runner (`run_experiment.py`), one report generator (`generate_report.py`)
2. **Determinism by default**: Seed required unless explicitly opted out
3. **Output hygiene**: All outputs written inside run directories (`data/runs/<run_id>/`)
4. **Library separation**: `src/` is import-only; no CLI logic in library code
5. **Gated changes**: All PRs must pass `make check`
6. **Promotion gates**: Promotion-track PRs must additionally pass `make promotion-gate`
