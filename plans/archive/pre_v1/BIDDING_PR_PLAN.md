# Arc B: Post-Merge Execution Ledger

**Snapshot Date:** 2026-02-06
**Status:** All PRs MERGED. Phase 0 complete; Phase 1 in progress.

This document records implemented reality from merged code on `main`.
For the forward-looking development roadmap, see `BIDDING_DEVELOPMENT_PLAN.md`.

---

## Merged PRs

| PR | Title | Key Files | Status |
|----|-------|-----------|--------|
| #262 | `refactor(bidding):` Rename StrictRaiserBidder to StrictHellRaiser | `strategy/bidding.py`, `experiments/config.py` | MERGED |
| #263 | `fix(bidding):` Lock ModeloEspecifico HIGH/LOW formulas | `strategy/bidding.py` | MERGED |
| #264 | `feat(diagnostics):` Diagnostic tricks eval + feature-outcome join | `scripts/evaluate_diagnostic_tricks.py`, `datasets/join.py` | MERGED |
| #265 | `feat(bidding):` OLSa training pipeline + OLSaBidder runtime | `models/train_olsa.py`, `strategy/bidding.py` | MERGED |
| #266 | `feat(eval):` Auction comparator gate stack | `scripts/run_auction_comparator.py`, `reporting/evaluator.py` | MERGED |
| #267 | `docs:` Arc B docs (Phase 0 complete) | `docs/02_agent/`, `BIDDING_DEVELOPMENT_PLAN.md` | MERGED |
| #268 | `feat(notebooks):` Phase0 canonical notebooks + CANONICAL_MODE | `notebooks/phase0_bidless/*.py`, `canonical_runs.py` | MERGED |
| #269 | `feat(reporting):` Promote diagnostic charts to production | `reporting/charts.py`, `reporting/chart_runner.py` | MERGED |
| #270 | `fix(notebook):` Hard-fail CANONICAL_MODE=True in notebook 20 | `notebooks/phase0_bidless/20_*.py` | MERGED |
| #271 | `fix(reporting):` Chart runner strategy suite + signature fix | `reporting/chart_runner.py`, `reporting/charts.py` | MERGED |
| #272 | `fix(comparator):` Hard-fail on missing evaluation + class name | `scripts/run_auction_comparator.py` | MERGED |
| #273 | `fix(notebook):` Remove dead RUN_DIR from notebook 20 | `notebooks/phase0_bidless/20_*.py`, `README.md` | MERGED |
| #274 | `fix(config):` Add pythonpath to pytest.ini | `pytest.ini`, `reporting/__init__.py` | MERGED |

All paths above are relative to `src/bid_euchre/` unless prefixed with `scripts/`, `notebooks/`, or `docs/`.

---

## Reproducibility Index

### Diagnostic Tricks Evaluation

```bash
uv run python scripts/evaluate_diagnostic_tricks.py \
    --greedy-dir data/runs/canonical_bidless_dataset_greedy_42_20260204_221121 \
    --glutton-dir data/runs/canonical_bidless_dataset_glutton_42_20260204_222713 \
    --seed 42 \
    --output docs/02_agent/DIAGNOSTIC_TRICKS_EVALUATION.md
```

### OLSa Training

```bash
uv run python -m bid_euchre.models.train_olsa \
    --run-dir data/runs/canonical_bidless_dataset_glutton_42_20260204_222713 \
    --seed 42 \
    --output /tmp/olsa_artifacts/
```

Produces: `olsa_v1.json`, `training_metrics.json`, `training_summary.md`.

### Auction Comparator

```bash
uv run python scripts/run_auction_comparator.py \
    --config experiments/configs/auction_comparator.yaml \
    --seed 42 \
    --olsa-artifact /tmp/olsa_artifacts/olsa_v1.json
```

### Notebook Checks

```bash
make notebook-check              # Verify sync + outputs cleared
make notebook-run                # Execute (SMOKE, ~10s)
make notebook-run-full           # Execute (QUICK, ~2-5min)
```

Papermill injects `CANONICAL_MODE=False` and the chosen `MODE`.

### Reporting Chart Runner

```bash
uv run python -m bid_euchre.reporting.chart_runner \
    --run-dir data/runs/<run_id> \
    --output-dir /tmp/charts/ \
    --suite all \
    --dpi 150
```

Available suites: `feature_health`, `feature_outcome`, `distribution`, `strategy_matchup`, `all`.

### Full Gate

```bash
make check    # repo-lint + ruff + pytest + notebook-check
```

---

## Artifacts & Reports

### Canonical Run Data

Canonical run registry was removed in PR #305. Notebooks now generate data on-the-fly via `load_or_generate_*()`. Run data lives in `data/runs/` (gitignored).

| Key | Run ID | Contents |
|-----|--------|----------|
| `greedy_dataset` | `canonical_bidless_dataset_greedy_42_20260204_221121` | 300K hands, greedy play policy |
| `glutton_dataset` | `canonical_bidless_dataset_glutton_42_20260204_222713` | 300K hands, glutton play policy |
| `outcomes_zoom` | `canonical_bidless_outcomes_zoom_42_20260204_222712` | Focused outcome distributions |

Each run directory contains:

```
<run_id>/
  datasets/
    bidless.parquet          # Per-seat feature rows (hand_id, seat, 41 features)
    bidless_outcomes.parquet  # Per-hand outcomes (hand_id, tricks_team0, tricks_team1)
    bidless_meta.json
    bidless_outcomes_meta.json
  results/                   # Per-scenario result JSONs
  meta.json                  # Run metadata (seed, config, git SHA)
```

### OLSa Model Artifact

Output of `train_olsa`: `olsa_v1.json` (schema_version `"1"`, artifact_type `"olsa_v1"`).

Three per-contract models:
- **suit:** `bowers + trump_count + offsuit_aces`
- **high:** `offsuit_aces`
- **low:** `offsuit_tens_count`

### Evaluation Reports

| File | Source |
|------|--------|
| `docs/02_agent/DIAGNOSTIC_TRICKS_EVALUATION.md` | `evaluate_diagnostic_tricks.py` output |
| `docs/02_agent/GLUTTON_VS_GREEDY_EVALUATION.md` | Play policy gate evidence |
| `data/runs/play_policy_gate_aggregate_20260204_221656.json` | Gate aggregate (gitignored) |

### Auction Comparator Config

`experiments/configs/auction_comparator.yaml` defines 4 static bidders:

| Name | Class | Notes |
|------|-------|-------|
| fiveheadfred | `FixedBidder(n=5, contract="S")` | Always bids 5 spades |
| stricthellraiser | `StrictHellRaiser` | Always raises |
| rankthetank | `RanktheTank` | Heuristic rank-sum |
| modeloespecifico | `ModeloEspecifico` | Hand-coded per-contract weights |

OLSa is injected dynamically via `--olsa-artifact`.

---

## Known Gaps / Deferred

All items below are non-blocking and relate to documentation or API ergonomics only.

| Item | Notes | Severity |
|------|-------|----------|
| Chart generators not re-exported from `reporting/__init__.py` | Circular import prevents it; use `from bid_euchre.reporting.charts import ...` directly | P3 / by design |
| `reporting/__init__.py` has no `__all__` entry for charts | Comment documents the constraint (PR #274) | P3 / documented |
| OLSa artifact path is a CLI flag, not a config field | Comparator YAML references 4 static bidders; OLSa is dynamic | P3 / intentional |

---

## Key Files Reference

| Module | File | Purpose |
|--------|------|---------|
| Bidding policies | `src/bid_euchre/strategy/bidding.py` | OLSaBidder, StrictHellRaiser, ModeloEspecifico |
| OLSa training | `src/bid_euchre/models/train_olsa.py` | Per-contract sparse OLS pipeline |
| Feature-outcome join | `src/bid_euchre/datasets/join.py` | Seat-to-team mapping + parquet join |
| Evaluator | `src/bid_euchre/reporting/evaluator.py` | expected_points, bid_rate, CVaR |
| Production charts | `src/bid_euchre/reporting/charts.py` | 4 chart suites (PNG generators) |
| Chart CLI | `src/bid_euchre/reporting/chart_runner.py` | Batch chart generation |
| Comparator | `scripts/run_auction_comparator.py` | Orchestrate auction runs + gate checks |
| Diagnostic eval | `scripts/evaluate_diagnostic_tricks.py` | Full-feature Ridge analysis |
| Canonical registry | _(removed in PR #305)_ | Was run ID lookup; notebooks now generate on-the-fly |
| Policy registration | `src/bid_euchre/experiments/config.py` | Strategy/policy factory |
