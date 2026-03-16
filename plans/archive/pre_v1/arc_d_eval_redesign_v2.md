# Arc D Rung Evaluation Redesign — v2 (Ready to Implement)

> Tightened from v1. Addresses 6 blockers found during code verification.
> See "Blocker Resolution" section at end for traceability.

## Context

Same as v1 — the R0 notebook crashes on gitignored paths and produces empty
charts. JSONL game logs contain all the data needed for rich analysis.

**Single branch:** `feat/arc-d-eval-redesign`

---

## PR Decomposition

Three PRs, revised dependency graph:

| PR | Concept | Depends on |
|----|---------|------------|
| **PR-A** | JSONL eval dataset parser | — |
| **PR-B** | Notebook template redesign | PR-A |
| **PR-C** | Report generator upgrade + docs cleanup | PR-A, **PR-B** |

PR-C now explicitly depends on PR-B because the report references
notebook-generated chart PNGs from CHART_OUTPUT_DIR.

---

## PR-A: JSONL Eval Dataset Parser

### Dataset Schema (Corrected)

Per-seat rows (4 rows per deal). **Features use `feat_` prefix** to match
the diagnostics API contract (`health_checks.py:148`, `charts.py:68`,
`stats.py:179`).

| Column | Type | Source |
|--------|------|--------|
| `deal_id` | int | `record["deal_id"]` |
| `seat` | int (0-3) | expansion (one row per seat) |
| `team` | int (0 or 1) | derived: `0 if seat in {0,2} else 1` |
| `contract_type` | str | `record["contract"]` |
| `trump` | str or None | `record["trump"]` |
| `tricks_won` | int | `t0 if seat in [0,2] else t1` |
| `winning_bid` | int or None | `record["winning_bid"]` |
| `bidder_seat` | int or None | `record["bidder_position"]` |
| `bidder_team` | int or None | derived from `bidder_position` |
| `dealer_seat` | int or None | `record["dealer_position"]` |
| `made_bid` | bool or None | `record["made_bid"]` |
| `redeal_flag` | bool or None | `record["redeal_flag"]` |
| `is_bidder` | bool | `seat == bidder_position` |
| `is_declaring_team` | bool | `team == bidder_team` |
| `feat_hand_value` | float | `features[seat]["hand_value"]` |
| `feat_trump_count` | float | `features[seat]["trump_count"]` |
| ... 37 other `feat_*` cols ... | float | `features[seat][name]` |

**Key change from v1:** All 39 hand features are prefixed with `feat_` in
the DataFrame columns, even though the JSONL `features` list stores them
with bare names. The parser adds the prefix during expansion:

```python
for feature_name, value in record["features"][seat].items():
    row[f"feat_{feature_name}"] = value
```

Plus per-deal auction summary columns (same value across all 4 seats):

| Column | Type | Source |
|--------|------|--------|
| `n_bids` | int | count of BID actions in `auction_transcript` |
| `n_passes` | int | count of PASS actions |
| `auction_rounds` | int | total entries in `auction_transcript` |

### Function Signature

```python
def build_eval_dataset(
    log_path: str | Path,
    *,
    skip_redeals: bool = True,
    max_deals: int | None = None,
) -> pd.DataFrame:
    """Parse JSONL game log into analysis-ready per-seat DataFrame.

    Features are stored with `feat_` prefix to match the diagnostics API
    contract (health_checks, charts, stats all filter on `feat_*` columns).

    Reuses patterns from:
    - evaluator._iter_hand_end_records(): JSONL iteration with try/except
    - notebook_data._load_outcomes_from_logs(): per-seat expansion
    - datasets/join.py: team assignment logic

    Args:
        log_path: Path to *.jsonl game log file.
        skip_redeals: If True, exclude all-pass redeal hands (default True).
        max_deals: If set, stop after this many deals (for SMOKE mode).

    Returns:
        DataFrame with per-seat rows. Features prefixed with `feat_`.

    Raises:
        FileNotFoundError: If log_path doesn't exist.
        ValueError: If no hand_end events found.
    """
```

### Aggregation Level Guidance (Blocker #3 Fix)

The docstring and module-level documentation will include clear guidance
about when to use per-seat rows vs aggregated rows:

```python
# Module docstring includes:
"""
IMPORTANT: Aggregation levels for analysis
-------------------------------------------
The DataFrame has 4 rows per deal (one per seat). This is correct for:
- Hand feature distributions (each seat has its own features)
- Seat balance checks (comparing across seats)
- Tricks won distribution (per-seat perspective)

For TEAM-LEVEL metrics, filter before aggregating:
- Bid accuracy (bid vs tricks): filter to `is_bidder == True` (1 row/deal)
- Make rate: filter to `is_declaring_team == True` then deduplicate by deal_id
- Team points: filter to one seat per team per deal (e.g., seat 0 for team 0)

For DEAL-LEVEL metrics:
- Contract selection: `df.drop_duplicates(subset="deal_id")`
"""
```

### Files

| File | Change |
|------|--------|
| `src/bid_euchre/datasets/eval_dataset.py` | **New.** `build_eval_dataset()` |
| `tests/unit/test_eval_dataset.py` | **New.** 13 tests |

### Tests (`tests/unit/test_eval_dataset.py`)

1. `test_basic_parsing` — Single valid record → 4 rows with correct columns
2. `test_feature_extraction_with_prefix` — All 39 features extracted with `feat_` prefix
3. `test_team_assignment` — Seats 0,2 → team 0; seats 1,3 → team 1
4. `test_tricks_won_by_team` — team 0 gets t0, team 1 gets t1
5. `test_bidder_flags` — `is_bidder` and `is_declaring_team` correct
6. `test_auction_summary` — `n_bids`, `n_passes`, `auction_rounds` from transcript
7. `test_skip_redeals` — Redeal records excluded when `skip_redeals=True`
8. `test_include_redeals` — Redeal records included when `skip_redeals=False`
9. `test_max_deals` — Only first N deals returned
10. `test_missing_file` — FileNotFoundError raised
11. `test_empty_log` — ValueError raised (no hand_end events)
12. `test_skip_non_hand_end_events` — run_start, run_end, trick_end records ignored
13. `test_malformed_json_lines_skipped` — Bad JSON lines tolerated (matches evaluator pattern)

### Test Fixture Design

Tests build synthetic JSONL records in-memory:

```python
def _make_hand_end_record(
    deal_id=0, contract="suit", trump="H", t0=6, t1=4,
    winning_bid=6, bidder_position=0, dealer_position=3,
    redeal_flag=False, made_bid=True, n_features=39,
    auction_transcript=None, seed=42,
) -> dict:
    """Build a synthetic hand_end JSONL record for testing."""
    features = []
    for seat in range(4):
        feat = {"hand_value": 10.0 + seat}
        # Fill remaining 38 features with deterministic values
        for i, name in enumerate(FEATURE_NAMES[1:]):  # skip hand_value
            feat[name] = float(seat * 100 + i)
        features.append(feat)
    ...
```

Where `FEATURE_NAMES` is imported from `hand_eval` or hardcoded as the
canonical 39-feature list.

### Verification

```bash
PYTHONPATH=src uv run python -m pytest tests/unit/test_eval_dataset.py -v
```

---

## PR-B: Notebook Template Redesign

### Parameter Changes

| Parameter | Keep/Add/Remove | Notes |
|-----------|-----------------|-------|
| `MODE` | Keep | SMOKE/QUICK/FULL |
| `SEED` | Keep | RNG seed |
| `EVAL_RUN_DIR` | **Add** | Path to eval run dir |
| `ARTIFACT_DIR` | Keep | Path to rung artifacts |
| `RUNG_ID` | Keep | Rung identifier |
| `CHART_OUTPUT_DIR` | Keep | For chart PNGs |
| `PROMOTION_DECISION_PATH` | Keep | Optional |
| `SPLIT_TYPE` | **Remove** | Not needed for eval |
| `ACTIVE_SPLIT` | **Remove** | Not needed for eval |
| `MODEL_ARTIFACT_PATH` | **Remove** | Derived from bundle |
| `SEMANTIC_GATE_OUTPUT_DIR` | **Remove** | Merged into CHART_OUTPUT_DIR |
| `RUN_DIR` | **Remove** | Replaced by EVAL_RUN_DIR |
| `SPLIT_MANIFEST_PATH` | **Remove** | Not needed for eval |

### New Section Structure

| Section | Content | Data Source | Faceting |
|---------|---------|-------------|----------|
| **§0 Setup** | Imports, config, data loading | JSONL log or synthetic | — |
| **§1 Deal Health** | Feature distributions, seat balance, strata completeness | Per-seat DataFrame | contract_type, seat |
| **§2 Auction Health** | Bid distribution, pass rate by seat, contract selection | Per-seat DataFrame (deduplicated) | contract_type |
| **§3 Gameplay Health** | Tricks won distribution, team balance, seat fairness | Per-seat DataFrame | contract_type, team |
| **§4 Auction Outcomes** | Bid accuracy, make rate, overbid/underbid | Bidder-only rows (`is_bidder==True`) | contract_type, bid level |
| **§5 Gameplay Outcomes** | Points distribution, net differential, tail risk | One row per deal-team (deduplicated) | contract_type |
| **§6 Model Specs** | Feature selection table, coefficient plots | Bundle JSON + model artifact | contract_type |
| **§7 Model Performance** | Predicted vs actual tricks, residuals, R²/MAE | Model predictions on eval data | contract_type |
| **§8 Dual-Arm Comparison** | OLSa vs OLSa_Full metrics side-by-side | Eval JSONs via `load_eval_metrics()` | — |
| **§9 Seed Sensitivity** | Multi-seed net_eppd stability, CV warning | Bundle eval paths | — |
| **§10 Promotion Summary** | Gate outcome, attribution gap, tier 1 checks | Promotion decision JSON | — |

### Aggregation Discipline (Blocker #3 Fix)

Sections that analyze team-level outcomes explicitly filter:

```python
# §4 Auction Outcomes: one row per deal (bidder's perspective)
bidder_df = df[df["is_bidder"] == True].copy()  # noqa: E712
assert bidder_df["deal_id"].nunique() == len(bidder_df), "Expected 1 bidder per deal"

# §5 Gameplay Outcomes: one row per deal-team
# For declaring team analysis:
declaring_df = df[df["is_declaring_team"] == True].copy()  # noqa: E712
declaring_df = declaring_df.drop_duplicates(subset=["deal_id", "team"])
```

### Data Loading Logic (§0)

```python
# Tier 1: Load from JSONL logs (primary)
df = pd.DataFrame()
_data_source = "none"

if EVAL_RUN_DIR and Path(EVAL_RUN_DIR).exists():
    log_files = sorted(Path(EVAL_RUN_DIR, "logs").glob("*.jsonl"))
    if log_files:
        from bid_euchre.datasets.eval_dataset import build_eval_dataset
        df = build_eval_dataset(
            log_files[0],
            max_deals=MODE_DEAL_COUNTS[MODE],
        )
        _data_source = "eval_logs"

# Tier 2: Generate synthetic demo data (SMOKE fallback for CI)
if df.empty:
    df = _build_demo_data(seed=SEED, n_deals=MODE_DEAL_COUNTS[MODE])
    _data_source = "synthetic"
```

The `_build_demo_data()` function generates deals using `generate_deal()` +
`get_hand_features()`, with `feat_` prefix added to features, plus mock
auction columns. This ensures deal health and feature distribution charts
always have data.

Auction-specific sections (§2, §4) guard on `_data_source == "eval_logs"`.

### §6 Model Specs — Loading Coefficients

Load model details from the rung bundle:

```python
if ARTIFACT_DIR and RUNG_ID:
    bundle_path = Path(ARTIFACT_DIR) / f"rung_bundle_{RUNG_ID}.json"
    if bundle_path.exists():
        bundle = json.load(open(bundle_path))
        # Load model artifact for coefficient analysis
        for arm_key in ("olsa", "olsa_full"):
            artifact_path = bundle.get(arm_key, {}).get("artifact_path")
            if artifact_path and Path(artifact_path).exists():
                artifact = json.load(open(artifact_path))
                # Extract per-contract model details
                for cf, model_data in artifact["payoff_model"].items():
                    if "offensive" in model_data:
                        # Off/def: use offensive arm
                        feature_names = model_data["offensive"]["feature_names"]
                        weights = model_data["offensive"]["weights"]
                        bias = model_data["offensive"]["bias"]
                    else:
                        feature_names = model_data["feature_names"]
                        weights = model_data["weights"]
                        bias = model_data["bias"]
```

### §7 Model Performance — Predictions (Corrected Schema)

**Corrected from v1:** Uses `weights` (list), `bias` (float), `feature_names`
(list) — matching the actual artifact schema in `train_hybrid_olsa.py:287-291`.

```python
# Load model and compute predictions
for contract_family, model_data in artifact["payoff_model"].items():
    if "offensive" in model_data:
        # Skip off/def for now — R0 doesn't use it
        continue
    feature_names = model_data["feature_names"]
    weights = np.array(model_data["weights"])
    bias = model_data["bias"]

    # Feature columns have feat_ prefix in our DataFrame
    feat_cols = [f"feat_{fn}" for fn in feature_names]
    subset = df[df["contract_type"] == contract_family]

    if not subset.empty and all(c in subset.columns for c in feat_cols):
        X = subset[feat_cols].values.astype(np.float64)
        y_pred = X @ weights + bias
        y_actual = subset["tricks_won"].values
        # Scatter: pred vs actual, residual histogram, R²/MAE with CIs
```

### Reusable Functions from Diagnostics Stack

These all work **because features use `feat_` prefix**:

| Function | Location | Used in Section |
|----------|----------|-----------------|
| `compute_health_scorecard()` | `diagnostics/health_checks.py` | §1 Deal Health |
| `display_scorecard()` | `diagnostics/health_checks.py` | §1 Deal Health |
| `compute_seat_balance()` | `diagnostics/stats.py` | §1, §3 |
| `compute_feature_stats()` | `diagnostics/stats.py` | §1 |
| `plot_hand_value_by_seat()` | `diagnostics/charts.py` | §1 |
| `plot_hand_value_by_contract()` | `diagnostics/charts.py` | §1 |
| `plot_feature_distributions()` | `diagnostics/charts.py` | §1 |
| `plot_outcome_distributions()` | `diagnostics/charts.py` | §3 |
| `plot_feature_outcome_correlation()` | `diagnostics/charts.py` | §3 |
| `plot_feature_vs_outcome_by_contract()` | `diagnostics/charts.py` | §7 |
| `load_eval_metrics()` | `reporting/evaluator.py` | §8, §9 |

**Note:** `_check_hands_differ()` will return WARN for eval data (no
`hand_cards` column in eval dataset — hands are not preserved in per-seat
expansion). This is acceptable and expected.

### R0 Notebook Instantiation

```python
# Parameters
MODE = "SMOKE"
SEED = 42
EVAL_RUN_DIR = "data/runs/arc_d_eval_r0_42_20260221_180253"
ARTIFACT_DIR = "data/artifacts/arc_d/r0"
RUNG_ID = "r0"
CHART_OUTPUT_DIR = ""
PROMOTION_DECISION_PATH = "data/artifacts/arc_d/r0/promotion_decision_r0.json"
```

**Graceful fallback:** When EVAL_RUN_DIR or ARTIFACT_DIR paths don't exist,
sections skip with clear messages. No FileNotFoundError crashes.

### Files

| File | Change |
|------|--------|
| `notebooks/_templates/01_model_rung_template.py` | **Rewrite.** New sections §0-§10 |
| `notebooks/_templates/01_model_rung_template.ipynb` | Jupytext sync |
| `notebooks/arc_d/02_r0_baseline.py` | **Update.** New params, new sections |
| `notebooks/arc_d/02_r0_baseline.ipynb` | Jupytext sync |
| `tests/unit/test_notebook_template_contract.py` | **Update.** New required sections/params |

### Contract Test Updates

```python
REQUIRED_PARAMETERS = [
    "MODE", "SEED", "EVAL_RUN_DIR", "ARTIFACT_DIR",
    "RUNG_ID", "CHART_OUTPUT_DIR", "PROMOTION_DECISION_PATH",
]

REQUIRED_SECTIONS = [
    "§0 Setup", "§1 Deal Health", "§2 Auction Health",
    "§3 Gameplay Health", "§4 Auction Outcomes", "§5 Gameplay Outcomes",
    "§6 Model Specs", "§7 Model Performance", "§8 Dual-Arm Comparison",
    "§9 Seed Sensitivity", "§10 Promotion Summary",
]
```

### Verification

```bash
make check
make notebook-check
```

---

## PR-C: Report Generator Upgrade + Docs Cleanup

**Depends on:** PR-A and PR-B (report embeds notebook-generated charts).

### Report Generator Upgrade

Extend `generate_arc_d_rung_report()` signature:

```python
def generate_arc_d_rung_report(
    bundle_path: str | Path,
    decision_path: str | Path | None = None,
    output_path: str | Path | None = None,
    *,
    eval_df: pd.DataFrame | None = None,
    chart_dir: str | Path | None = None,
) -> str:
```

When `eval_df` is provided, the report includes data-driven sections.
When `chart_dir` is provided, it embeds chart PNGs as markdown image links.
Both are optional — the existing signature still works for basic reports.

**New report sections (when eval_df provided):**

| Section | Content |
|---------|---------|
| Executive Summary | 3-bullet TL;DR of rung outcome |
| Data Provenance | Seed, N deals, model artifact SHA, eval run ID, timestamp |
| Reproducibility | Exact command to regenerate |
| Deal Health Summary | Seat balance results, strata completeness |
| Auction Analysis | Bid distribution table, pass rate, contract selection |
| Gameplay Analysis | Tricks distribution by contract_type, team balance |
| Model Specifications | Dual-arm feature table, coefficient summary |
| Model Performance | R², MAE with CIs by contract_type |
| Dual-Arm Comparison | (existing, enhanced with formatting) |
| Attribution Gap | (existing, enhanced) |
| Promotion Gate | Decision, tier 1 checks, gate results |

**Aggregation discipline:** Report computations follow the same rules as
the notebook (filter to `is_bidder` for bid accuracy, deduplicate for team
metrics).

### Docs Cleanup (Corrected — Blocker #5)

The existing `docs/04_reports/` convention is **historical snapshots** that
are committed. Moving arc_d reports to gitignored `data/reports/` would
break provenance expectations.

**Corrected approach:**
- **Keep** existing `docs/04_reports/model_arc_r0_20260222.md` as immutable
  historical snapshot (like phase0 reports).
- **Keep** `docs/04_reports/arc_d_v1/model_arc_d_dashboard.md` as the dashboard
  snapshot.
- **Add** `docs/04_reports/README.md` entries for the arc_d reports.
- **Future** generated reports go to `data/reports/arc_d/` (gitignored),
  and a manual snapshot step copies to `docs/04_reports/` when finalised.
- **Update** `scripts/internal/generate_arc_dashboard.py` to default output
  to `data/reports/arc_d/` (working copy, gitignored), with `--snapshot`
  flag to write to `docs/04_reports/`.

### Files

| File | Change |
|------|--------|
| `src/bid_euchre/reporting/arc_d_report.py` | **Major expansion.** New sections, DataFrame input |
| `scripts/internal/generate_arc_dashboard.py` | Add `--snapshot` flag |
| `docs/04_reports/README.md` | Add arc_d entries to index |
| `docs/02_agent/MODEL_ARC_RUNS.md` | Enhanced provenance fields |
| `tests/unit/test_arc_d_reporting.py` | Extend for new report sections |

### Verification

```bash
make check
```

---

## Blocker Resolution Traceability

### Blocker #1 (P0): `feat_` prefix mismatch

**Problem:** Diagnostics APIs expect `feat_*` columns; `get_hand_features()`
returns bare names; plan had unprefixed schema.

**Fix:** Parser adds `feat_` prefix during expansion:
`row[f"feat_{name}"] = value`. All 39 features stored as `feat_hand_value`,
`feat_trump_count`, etc. Diagnostics APIs (`compute_health_scorecard`,
`plot_hand_value_by_seat`, `compute_feature_stats`) work without changes.

**Verified against:** `health_checks.py:148`, `charts.py:68`, `stats.py:179`.

### Blocker #2 (P0): Model artifact schema mismatch

**Problem:** Plan said `coefficients` (dict) + `intercept`; actual schema
uses `weights` (list) + `bias` (float) + `feature_names` (list).

**Fix:** §7 Model Performance uses correct schema:
```python
weights = np.array(model_data["weights"])
bias = model_data["bias"]
feature_names = model_data["feature_names"]
feat_cols = [f"feat_{fn}" for fn in feature_names]
```

**Verified against:** `train_hybrid_olsa.py:287-291`.

### Blocker #3 (P1): Double-counting in per-seat expansion

**Problem:** 4 rows per deal means team-level metrics get counted 2x per
team if not deduplicated.

**Fix:** Module docstring + section-level guards enforce aggregation discipline:
- §4 (Auction Outcomes): filter to `is_bidder == True` (1 row/deal)
- §5 (Gameplay Outcomes): deduplicate by `(deal_id, team)`
- §1, §3 (Health): per-seat rows are correct (measuring seat-level balance)

**Verified against:** `notebook_data.py:660` (same per-seat expansion pattern).

### Blocker #4 (P1): PR dependency inconsistency

**Problem:** PR-C claimed to depend only on PR-A but needed PR-B chart
output for embedding.

**Fix:** Dependency graph corrected: PR-C depends on PR-A and PR-B.
Chart embedding is optional (`chart_dir` parameter), but full report quality
requires charts from the notebook.

### Blocker #5 (P1): Docs move breaks provenance

**Problem:** Moving committed reports to gitignored directory breaks the
`docs/04_reports/` convention of historical snapshots.

**Fix:** Keep existing files. Add README entries. Generated reports go to
`data/reports/arc_d/` (gitignored working copies). Manual snapshot step
copies to `docs/04_reports/` when finalized. Dashboard script gets
`--snapshot` flag.

**Verified against:** `docs/04_reports/README.md:3` ("Historical analysis
reports for completed research phases").

### Blocker #6 (P2): Missing malformed-JSONL test

**Problem:** Evaluator tolerates bad JSON lines (`evaluator.py:57-59`);
parser should test that behavior.

**Fix:** Added `test_malformed_json_lines_skipped` to test list. Parser
uses same try/except/continue pattern as `_iter_hand_end_records()`.

---

## What This Does NOT Change

Same as v1:
- No simulation re-running
- No gate logic changes
- No training pipeline changes
- No execution plan changes beyond report output paths
- Per-rung notebooks preserved

---

## End-to-End Verification

After all 3 PRs merge:

```bash
# 1. Full test suite
make check

# 2. CI notebook execution (synthetic data, no artifacts needed)
make notebook-run

# 3. R0 notebook with real data (requires local artifacts)
# Verify non-null charts in all sections
PYTHONPATH=src uv run jupyter execute \
  notebooks/arc_d/02_r0_baseline.ipynb

# 4. R0 report with eval DataFrame
PYTHONPATH=src uv run python -c "
from bid_euchre.reporting.arc_d_report import generate_arc_d_rung_report
from bid_euchre.datasets.eval_dataset import build_eval_dataset
df = build_eval_dataset('data/runs/arc_d_eval_r0_42_20260221_180253/logs/arc_d_eval_r0_42_20260221_180253_hybrid_olsa_r0.jsonl')
print(f'Eval dataset: {df.shape[0]} rows, {df.shape[1]} cols')
print(f'Feature cols: {len([c for c in df.columns if c.startswith(\"feat_\")])}')
generate_arc_d_rung_report(
    'data/artifacts/arc_d/r0/rung_bundle_r0.json',
    'data/artifacts/arc_d/r0/promotion_decision_r0.json',
    'data/reports/arc_d/model_arc_r0.md',
    eval_df=df)
"

# 5. Diagnostics compatibility check
PYTHONPATH=src uv run python -c "
from bid_euchre.datasets.eval_dataset import build_eval_dataset
from bid_euchre.diagnostics.health_checks import compute_health_scorecard, display_scorecard
df = build_eval_dataset('data/runs/arc_d_eval_r0_42_20260221_180253/logs/arc_d_eval_r0_42_20260221_180253_hybrid_olsa_r0.jsonl', max_deals=100)
sc = compute_health_scorecard(df)
print(display_scorecard(sc))
"
```
