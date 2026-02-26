# HITL Notebook Gates & Semantic Review Framework

**Author:** Claude (ML Systems Architect)
**Date:** 2026-02-18
**Status:** PLAN — no code changes proposed

---

## 1. Scope and Non-Goals

### In Scope

1. **Notebook Standard** — define required parameters, outputs, section structure, and data-split access rules for every model-rung notebook.
2. **Semantic Gate Schema v1** — machine-readable JSON artifact emitted by notebooks that encodes pass/fail status for fairness, health, and directional-sanity checks with explicit thresholds.
3. **Report Template Spec** — required sections, tables, and charts for the human-readable report generated alongside each model-rung loop.
4. **HITL Visibility Contract** — notebooks used for human review may access only the validation split; the test split is never loaded during tuning.
5. **Blind Test Publication** — the test split is evaluated exactly once per promotion attempt; results are published in the semantic gate artifact with no prior human visibility.
6. **Promotion Gate Integration** — wire semantic gates into the existing `compute_eligibility()` pipeline and CI `make promotion-gate`.
7. **Test & Validation Plan** — unit tests for schema validation, gate logic, and split-access enforcement.

### Non-Goals

- Implementing the actual Phase 1 bidding model or its training loop.
- Changing the existing Phase 0 notebooks (they predate this framework and remain as-is).
- Building a visual dashboard / web UI — all review happens via rendered notebooks + markdown reports.
- Multi-model ensemble or hyperparameter search orchestration.
- Changing the existing `SplitManifest`, `freeze_artifact`, or `notebook_validation.py` code (we extend, not replace).

---

## 2. Files and Contracts to Add

All paths relative to repo root.

### New Source Files

| Path | Purpose |
|------|---------|
| `src/bid_euchre/diagnostics/semantic_gate.py` | Semantic gate evaluation engine: compute health checks, emit `semantic_gate.json` |
| `src/bid_euchre/diagnostics/split_guard.py` | Runtime enforcement: `require_split("val")` / `require_split("train")` / panic on `"test"` during HITL |
| `src/bid_euchre/reporting/report_template.py` | Structured report builder: generates required-section markdown from semantic gate + notebook outputs |

### New Notebook Template

| Path | Purpose |
|------|---------|
| `notebooks/_templates/01_model_rung_template.py` | Jupytext-paired template for every model-rung HITL notebook |

### New Schema Docs

| Path | Purpose |
|------|---------|
| `docs/01_core/schemas/semantic_gate_v1.md` | Authoritative schema specification for `semantic_gate.json` |

### Modified Files

| Path | Change |
|------|--------|
| `src/bid_euchre/reporting/eligibility.py` | Add `check_semantic_gate()` rule to `compute_eligibility()` |
| `scripts/run_notebooks.py` | Accept `--semantic-gate-output-dir` flag; merge semantic gate into notebook gate artifact |
| `src/bid_euchre/diagnostics/notebook_validation.py` | Add `validate_semantic_gate()` function for post-execution semantic checks |
| `docs/02_agent/PROMOTION_WORKFLOW.md` | Add §Semantic Gate section, update reviewer checklist |
| `Makefile` | Add `SEMANTIC_GATE_DIR` optional variable to `promotion-gate` target |

### New Test Files

| Path | Covers |
|------|--------|
| `tests/unit/test_semantic_gate.py` | Gate evaluation logic, threshold enforcement, schema emission |
| `tests/unit/test_split_guard.py` | Split-access enforcement, test-split panic, mode-awareness |
| `tests/unit/test_report_template.py` | Report section generation, required-section completeness |

---

## 3. Notebook Standard

### 3.1 Required Papermill Parameters

Every model-rung notebook MUST define a `parameters`-tagged cell with these variables:

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `MODE` | str | `"FULL"` | Sample size control: `SMOKE`, `QUICK`, `FULL` |
| `SEED` | int | `42` | RNG seed for data generation and splitting |
| `SPLIT_TYPE` | str | `"three_way"` | Split policy; model-rung notebooks always use `three_way` |
| `SPLIT_MANIFEST_PATH` | str\|None | `None` | Path to pre-computed split manifest (if reusing existing split) |
| `ACTIVE_SPLIT` | str | `"val"` | Which split the notebook operates on: `"train"`, `"val"`, or `"test"` |
| `MODEL_ARTIFACT_PATH` | str\|None | `None` | Path to the frozen model artifact being evaluated |
| `SEMANTIC_GATE_OUTPUT_DIR` | str\|None | `None` | Where to write `semantic_gate.json` |
| `RUN_DIR` | str\|None | `None` | Path to source data run directory |

### 3.2 Required Notebook Sections

Every model-rung notebook MUST contain these sections in order:

| Section # | Title | Purpose |
|-----------|-------|---------|
| §0 | Configuration & Setup | Parameters cell, imports, mode dispatch |
| §1 | Data Loading & Split Verification | Load data, verify split manifest, confirm `ACTIVE_SPLIT` matches loaded partition |
| §2 | Fairness Health Checks | Seat balance, contract-type balance, trump/suit family fairness |
| §3 | Directional Sanity Checks | Model predictions correlate positively with actual outcomes; contract-type sign checks |
| §4 | Performance Metrics | R², MAE, per-contract breakdown with bootstrap CIs (QUICK/FULL only) |
| §5 | Feature Importance | Per-contract top-N features, coefficient stability across strategies |
| §6 | Semantic Gate Emission | Compute and write `semantic_gate.json` |
| §7 | Summary & Recommendation | Human-readable verdict with evidence citations |

### 3.3 Required Outputs

Every model-rung notebook MUST produce:

1. **`semantic_gate.json`** — machine-readable gate artifact (schema defined in §5 below)
2. **At least 1 fairness chart** — seat balance visualization (boxplot or similar)
3. **At least 1 directional sanity chart** — predicted vs actual scatter or residual plot
4. **Summary markdown cell** — text verdict referencing gate status

### 3.4 Data Access Rules

| Context | Allowed Splits | Enforcement |
|---------|---------------|-------------|
| Model training (outside notebook) | `train` only | `split_guard.require_split("train")` |
| HITL review notebook | `val` only | `split_guard.require_split("val")` + assert `ACTIVE_SPLIT == "val"` |
| Blind test publication | `test` only | `split_guard.require_split("test")` — runs exactly once per promotion attempt |
| SMOKE mode (CI) | `val` (subset) | Same rules, smaller N |

**Enforcement mechanism:** `split_guard.py` exports:

```python
def require_split(
    df: pd.DataFrame,
    manifest: SplitManifest,
    allowed_split: str,
    seed: int,
) -> pd.DataFrame:
    """Filter df to the requested split, raising ValueError if
    allowed_split == 'test' and context is HITL (detected via
    the ACTIVE_SPLIT environment or parameter).

    Returns the filtered DataFrame.
    """
```

The guard re-derives partition boundaries from the manifest's seed and verifies partition hashes match before returning data. If `allowed_split="test"` is requested while `ACTIVE_SPLIT="val"`, it raises `ValueError("Test split access blocked during HITL review")`.

### 3.5 Sample Size Requirements by Mode

| Mode | Min Hands (total, pre-split) | Purpose | Bootstrap CIs? |
|------|------------------------------|---------|-----------------|
| `SMOKE` | 100 | CI execution gate only | No |
| `QUICK` | 2,000 | Statistical validation | Yes (1,000 resamples) |
| `FULL` | 50,000 | Production report | Yes (10,000 resamples) |

**Val split effective N:** With a 3-way split (80/10/10), the validation split contains 10% of hands. For `FULL` mode: 5,000 val hands. For `QUICK` mode: 200 val hands. These are sufficient for health checks but not for fine-grained per-contract-type CIs (which require training data). The semantic gate accounts for this by relaxing per-contract thresholds in `QUICK` mode.

---

## 4. Semantic Gate Schema v1

### 4.1 Top-Level Schema

```json
{
  "schema_version": 1,
  "gate_status": "PASS | FAIL",
  "created_at_utc": "ISO8601Z",
  "model_artifact_path": "path/to/olsa_v1.json",
  "model_artifact_sha256": "hex",
  "split_manifest_sha256": "hex",
  "active_split": "val | test",
  "mode": "SMOKE | QUICK | FULL",
  "seed": 42,
  "total_hands": 5000,
  "total_checks": 12,
  "passed_checks": 12,
  "failed_checks": 0,
  "warned_checks": 0,
  "checks": [ ... ]
}
```

**Required top-level fields:** `schema_version`, `gate_status`, `created_at_utc`, `active_split`, `mode`, `seed`, `total_hands`, `total_checks`, `passed_checks`, `failed_checks`, `checks`.

**Gate status logic:**
- `"PASS"` if `failed_checks == 0`
- `"FAIL"` if `failed_checks > 0`

### 4.2 Check Entry Schema

Each entry in the `checks` array:

```json
{
  "check_id": "seat_balance",
  "category": "fairness | health | directional_sanity",
  "status": "PASS | FAIL | WARN | SKIP",
  "threshold": "description of pass criterion",
  "observed": "observed value(s)",
  "detail": "human-readable explanation",
  "contract_type": "suit | high | low | aggregate | null",
  "n_samples": 5000
}
```

**Status definitions:**
- `PASS` — check met threshold
- `FAIL` — check violated threshold (blocks promotion)
- `WARN` — non-blocking concern (logged but does not set `gate_status=FAIL`)
- `SKIP` — check not applicable (insufficient data or wrong mode)

### 4.3 Required Checks and Thresholds

#### 4.3.1 Fairness Checks (category: `fairness`)

| check_id | Description | Threshold | Fail Action | SMOKE Behavior |
|----------|-------------|-----------|-------------|----------------|
| `seat_balance` | Mean hand_value per seat within each contract_type. ANOVA F-test across 4 seats. | ANOVA p > 0.01 for each contract_type. If N < 200 per cell, SKIP instead of FAIL. | FAIL blocks promotion | SKIP (N too small) |
| `contract_type_balance` | Row counts per contract_type match expected ratios (4:1:1 for suit:high:low under standard 6-scenario config). | Chi-square goodness-of-fit p > 0.01. Expected ratio derived from scenario config, not hardcoded. | FAIL blocks promotion | SKIP (N too small) |
| `trump_suit_invariance` | Mean hand_value variance across 4 trump suits (suit contracts only). | Relative spread < 2.0% (i.e., `(max_var - min_var) / mean_var < 0.02`). Phase 0 observed < 0.6%. 2.0% provides headroom. | FAIL blocks promotion | SKIP |
| `team_balance_self_play` | Mean trick delta from 5.0 in self-play (if self-play data present). | `|mean_delta| < 0.25` per strategy × contract_type. Consistent with Phase 0 threshold. | FAIL blocks promotion | SKIP |

**Default chosen:** `trump_suit_invariance` threshold of 2.0% relative spread. Phase 0 observed 0.6%; 2.0% provides 3× headroom for noisier model-rung data while still catching genuine invariance violations.

**Default chosen:** `seat_balance` uses ANOVA p > 0.01 (not 0.05) to reduce false positives from the 3–4 independent tests (one per contract_type) without requiring formal multiple-comparison correction. This is a conservative choice — Bonferroni at family-wise alpha=0.05 with 4 tests gives per-test alpha=0.0125, rounding to 0.01.

#### 4.3.2 Health Checks (category: `health`)

| check_id | Description | Threshold | Fail Action | SMOKE Behavior |
|----------|-------------|-----------|-------------|----------------|
| `val_split_integrity` | Partition hash from loaded data matches split manifest. | Exact hash match. | FAIL blocks promotion | PASS/FAIL (always checked) |
| `feature_count` | Number of features in loaded data matches expected feature set. | Exact match against `len(evaluate_hand(...))` (currently 39). The expected count is read from `hand_eval.py` at runtime, not hardcoded. | FAIL blocks promotion | PASS/FAIL (always checked) |
| `no_nan_features` | Zero NaN values in feature columns. | `df[feature_cols].isna().sum().sum() == 0` | FAIL blocks promotion | PASS/FAIL (always checked) |
| `tricks_range` | All tricks_won values in [0, 10]. | `df["tricks_won"].between(0, 10).all()` | FAIL blocks promotion | PASS/FAIL (always checked) |
| `min_sample_size` | Val split meets minimum N for the declared mode. | SMOKE: N ≥ 10. QUICK: N ≥ 100. FULL: N ≥ 2,000. | FAIL blocks promotion | PASS/FAIL |

**Default chosen:** `min_sample_size` for FULL mode val split = 2,000 hands. With 50K total hands and 10% val fraction, expected val N = 5,000. Threshold of 2,000 provides margin for scenario imbalance while still blocking severely undersized splits.

#### 4.3.3 Directional Sanity Checks (category: `directional_sanity`)

These checks verify that the model's predictions have the expected relationship with actual outcomes. They are computed per-contract-type.

| check_id | Description | Threshold | Fail Action | SMOKE Behavior |
|----------|-------------|-----------|-------------|----------------|
| `prediction_correlation` | Pearson r between model predicted tricks and actual tricks_won, per contract_type. | r > 0.10 for each contract_type. Phase 0 diagnostic R² ~0.19–0.24 implies r ~0.44–0.49; threshold of 0.10 is deliberately loose to catch only directional failures. | FAIL blocks promotion | SKIP |
| `prediction_sign_suit` | For suit contracts: coefficient of `trump_count` (or equivalent primary feature) is positive. | Coefficient > 0. | FAIL blocks promotion | SKIP |
| `prediction_sign_high` | For HIGH contracts: coefficient of `offsuit_aces` is positive. | Coefficient > 0. | FAIL blocks promotion | SKIP |
| `prediction_sign_low` | For LOW contracts: coefficient of `offsuit_tens_count` is positive. | Coefficient > 0. | FAIL blocks promotion | SKIP |
| `r_squared_floor` | Per-contract R² on val split. | R² > 0.05 per contract_type. Phase 0 observed 0.19–0.24; 0.05 is a 4× relaxation catching only catastrophic regression. | FAIL blocks promotion | SKIP |
| `mae_ceiling` | Per-contract MAE on val split. | MAE < 2.5 tricks. Phase 0 observed 1.2–1.4; 2.5 catches only models that are essentially random (random baseline MAE ~2.5). | FAIL blocks promotion | SKIP |

**Default chosen:** `prediction_correlation` threshold of r > 0.10. A model that cannot achieve even r = 0.10 between predictions and actual outcomes has no useful predictive signal and should not be promoted.

**Default chosen:** `r_squared_floor` of 0.05 and `mae_ceiling` of 2.5. These are intentionally loose — they catch catastrophic failures (wrong sign, garbage predictions) without being so tight that they reject a model that is merely mediocre. Tighter thresholds should be applied at the model-specific level, not the framework level.

### 4.4 Schema Constants

```python
SEMANTIC_GATE_SCHEMA_VERSION = 1

SEMANTIC_GATE_REQUIRED_FIELDS = {
    "schema_version",
    "gate_status",
    "created_at_utc",
    "active_split",
    "mode",
    "seed",
    "total_hands",
    "total_checks",
    "passed_checks",
    "failed_checks",
    "checks",
}

SEMANTIC_CHECK_REQUIRED_FIELDS = {
    "check_id",
    "category",
    "status",
    "threshold",
    "observed",
    "detail",
}
```

---

## 5. Report Template Spec

### 5.1 Required Report Sections

Every model-rung report (generated as markdown from notebook outputs) MUST contain:

| Section # | Title | Content | Data Source |
|-----------|-------|---------|-------------|
| §1 | Executive Summary | 1-paragraph verdict + bullet list of gate results (PASS/FAIL counts) | `semantic_gate.json` |
| §2 | Model Identity | Model artifact path, SHA256, training config, split manifest reference, git SHA | Parameters + manifest |
| §3 | Data Summary | Split sizes (train/val/test hand counts), contract-type distribution, feature count | Loaded DataFrame + manifest |
| §4 | Fairness Assessment | Seat balance table, contract-type distribution table, trump invariance table. Each row includes check_id, observed value, threshold, and status. | `semantic_gate.json` checks where `category == "fairness"` |
| §5 | Health Assessment | Val split integrity, feature completeness, NaN check, tricks range, sample size. Same tabular format. | `semantic_gate.json` checks where `category == "health"` |
| §6 | Directional Sanity | Per-contract prediction correlation, sign checks, R², MAE. Same tabular format. | `semantic_gate.json` checks where `category == "directional_sanity"` |
| §7 | Performance Detail | Per-contract coefficient table (top 10), R² and MAE with bootstrap 95% CIs (QUICK/FULL only), comparison against Phase 0 baseline if available | Notebook computations |
| §8 | Semantic Gate Summary | Full gate artifact reproduced inline (JSON or formatted table) | `semantic_gate.json` |
| §9 | Reproduction Commands | Exact commands to regenerate data, run notebook, and verify gate | Static template + parameters |
| §10 | Known Limitations | Caveats specific to this model rung (sample size notes, feature limitations, etc.) | Human-authored |

### 5.2 Required Tables

Every report MUST include these tables (generated programmatically):

1. **Gate Summary Table** — one row per check, columns: `check_id`, `category`, `status`, `threshold`, `observed`, `contract_type`
2. **Per-Contract Performance Table** — columns: `contract_type`, `R²`, `R² 95% CI`, `MAE`, `MAE 95% CI`, `N` (val split)
3. **Split Manifest Summary** — columns: `split_type`, `train_hand_ids`, `val_hand_ids`, `test_hand_ids`, `source_run_id`, `split_seed`

### 5.3 Required Charts

At minimum:

1. **Seat balance grouped boxplot** — hand_value by seat, faceted by contract_type
2. **Predicted vs actual scatter** — per contract_type, color-coded
3. **Residual distribution** — per contract_type

### 5.4 Report Generation

`src/bid_euchre/reporting/report_template.py` provides:

```python
def generate_model_rung_report(
    semantic_gate: dict,
    split_manifest: SplitManifest,
    performance_metrics: dict,   # per-contract R², MAE, CIs
    model_identity: dict,        # artifact path, sha256, config, git_sha
    limitations: list[str],
    output_path: Path,
) -> Path:
    """Generate markdown report from structured inputs.
    Returns path to written report.
    """
```

The function assembles all 10 required sections. Sections §4–§6 are auto-generated from the semantic gate checks array. Section §7 comes from `performance_metrics`. Section §10 comes from the `limitations` list (may be empty; the section header is always present).

---

## 6. Promotion Gate Integration

### 6.1 New Eligibility Rule: `check_semantic_gate()`

Add to `src/bid_euchre/reporting/eligibility.py`:

```python
def check_semantic_gate(
    gate_path: Optional[str],
    batch_purpose: str,
) -> EligibilityResult:
    """Check semantic gate JSON.

    - batch_purpose='promotion' + missing gate -> FAIL
    - batch_purpose='promotion' + gate_status=FAIL -> FAIL
    - batch_purpose!='promotion' + missing gate -> PASS (optional)
    """
```

**Behavior mirrors existing `check_notebook_gate()` pattern** — promotion requires it, exploration makes it optional.

### 6.2 Updated `compute_eligibility()` Pipeline

The existing 6-rule pipeline becomes 7 rules:

1. `config_membership` (existing)
2. `canonical_summary_clean` (existing)
3. `notebook_gate` (existing — execution gate)
4. **`semantic_gate`** (NEW — semantic health gate)
5. `git_sha_consistency` (existing)
6. `artifacts_frozen` (existing)
7. `split_manifests` (existing)

### 6.3 CI Integration

**Makefile changes:**

```makefile
# Existing promotion-gate target, extended:
promotion-gate:
    # ... existing checks ...
    @if [ -n "$(SEMANTIC_GATE_DIR)" ]; then \
        echo "Checking semantic gate..."; \
        python -c "import json; g=json.load(open('$(SEMANTIC_GATE_DIR)/semantic_gate.json')); assert g['gate_status']=='PASS', f'Semantic gate FAIL: {g[\"failed_checks\"]} checks failed'"; \
    fi
```

**`SEMANTIC_GATE_DIR` is optional for now.** When Phase 1 model-rung PRs begin, it becomes required for promotion-labeled PRs (matching the `ARTIFACT_DIR`/`ROLLUP_JSON` pattern).

### 6.4 Lint Rule Addition

Add to repo linter:

**`semantic-gate-schema`** — `semantic_gate*.json` files under `data/` must conform to the v1 schema (required fields present, `gate_status` must be `PASS`, all check entries have required fields).

### 6.5 Blind Test Flow

The test split is evaluated exactly once per promotion attempt, in a separate non-HITL step:

1. **Training** — uses `train` split only.
2. **HITL review** — notebook runs with `ACTIVE_SPLIT="val"`. Human reviews results, iterates on model.
3. **Freeze** — once the human approves, `freeze_artifact()` is called. No further model changes.
4. **Blind test** — a separate script (or the same notebook with `ACTIVE_SPLIT="test"`) runs on the test split. This produces a second `semantic_gate.json` with `active_split: "test"`.
5. **Promotion** — both semantic gates (val and test) must have `gate_status: PASS`. The eligibility engine checks for the test-split gate specifically:

```python
# In check_semantic_gate():
if batch_purpose == "promotion":
    # Require test-split gate exists alongside val-split gate
    test_gate = gate_dir / "semantic_gate_test.json"
    val_gate = gate_dir / "semantic_gate_val.json"
    # Both must exist and both must PASS
```

**File naming convention:**
- `semantic_gate_val.json` — emitted during HITL review (val split)
- `semantic_gate_test.json` — emitted during blind test (test split)

For non-promotion (exploration) workflows, only `semantic_gate_val.json` is needed.

---

## 7. Test and Validation Plan

### 7.1 Unit Tests: `tests/unit/test_semantic_gate.py`

| Test | What it verifies |
|------|-----------------|
| `test_seat_balance_pass` | ANOVA p > 0.01 → status=PASS |
| `test_seat_balance_fail` | Injected seat bias → status=FAIL |
| `test_seat_balance_skip_small_n` | N < 200 per cell → status=SKIP |
| `test_contract_type_balance_pass` | Correct ratio → PASS |
| `test_contract_type_balance_fail` | Skewed ratio → FAIL |
| `test_trump_invariance_pass` | Spread < 2% → PASS |
| `test_trump_invariance_fail` | Spread > 2% → FAIL |
| `test_team_balance_pass` | Delta < 0.25 → PASS |
| `test_team_balance_fail` | Delta > 0.25 → FAIL |
| `test_val_split_integrity_pass` | Hash matches → PASS |
| `test_val_split_integrity_fail` | Hash mismatch → FAIL |
| `test_feature_count_pass` | Correct count → PASS |
| `test_feature_count_fail` | Wrong count → FAIL |
| `test_no_nan_pass` | Clean data → PASS |
| `test_no_nan_fail` | Injected NaN → FAIL |
| `test_tricks_range_pass` | All [0,10] → PASS |
| `test_tricks_range_fail` | Value 11 → FAIL |
| `test_min_sample_size_pass` | N above threshold → PASS |
| `test_min_sample_size_fail` | N below threshold → FAIL |
| `test_prediction_correlation_pass` | r > 0.10 → PASS |
| `test_prediction_correlation_fail` | r < 0.10 → FAIL |
| `test_prediction_sign_suit_pass` | Positive coeff → PASS |
| `test_prediction_sign_suit_fail` | Negative coeff → FAIL |
| `test_prediction_sign_high_pass` | Positive coeff → PASS |
| `test_prediction_sign_low_pass` | Positive coeff → PASS |
| `test_r_squared_floor_pass` | R² > 0.05 → PASS |
| `test_r_squared_floor_fail` | R² < 0.05 → FAIL |
| `test_mae_ceiling_pass` | MAE < 2.5 → PASS |
| `test_mae_ceiling_fail` | MAE > 2.5 → FAIL |
| `test_gate_status_all_pass` | 0 failures → gate_status=PASS |
| `test_gate_status_any_fail` | 1+ failures → gate_status=FAIL |
| `test_warn_does_not_fail_gate` | WARN-only → gate_status=PASS |
| `test_skip_does_not_fail_gate` | SKIP-only → gate_status=PASS |
| `test_schema_emission` | Output JSON has all required fields |
| `test_smoke_mode_skips_statistical` | SMOKE mode → all statistical checks SKIP |
| `test_full_mode_runs_all` | FULL mode → no SKIPs (except data-dependent) |

**Estimated: 35 tests.**

### 7.2 Unit Tests: `tests/unit/test_split_guard.py`

| Test | What it verifies |
|------|-----------------|
| `test_require_val_split_returns_val_data` | Correct DataFrame filtered |
| `test_require_train_split_returns_train_data` | Correct DataFrame filtered |
| `test_require_test_blocked_during_hitl` | `ACTIVE_SPLIT="val"` + request `"test"` → ValueError |
| `test_require_test_allowed_during_blind` | `ACTIVE_SPLIT="test"` + request `"test"` → returns data |
| `test_partition_hash_verified` | Hash mismatch → ValueError |
| `test_partition_hash_matches` | Correct hash → success |
| `test_unknown_split_name_raises` | `"foo"` → ValueError |
| `test_two_way_manifest_no_val` | two_way manifest + request `"val"` → ValueError |

**Estimated: 8 tests.**

### 7.3 Unit Tests: `tests/unit/test_report_template.py`

| Test | What it verifies |
|------|-----------------|
| `test_all_10_sections_present` | Output markdown has all 10 required section headers |
| `test_gate_summary_table_format` | Table has correct columns |
| `test_performance_table_format` | Per-contract table has correct columns |
| `test_split_manifest_table_format` | Manifest summary table correct |
| `test_empty_limitations_still_has_section` | §10 header present even with empty list |
| `test_reproduction_commands_include_seed` | §9 contains `--seed` |

**Estimated: 6 tests.**

### 7.4 Integration Tests

| Test | What it verifies | Marker |
|------|-----------------|--------|
| `test_semantic_gate_smoke_notebook` | End-to-end: generate data → run semantic gate in SMOKE mode → valid JSON emitted | `@pytest.mark.slow` |
| `test_blind_test_after_val` | Full workflow: val gate → freeze → test gate → both gates PASS | `@pytest.mark.slow` |

**Estimated: 2 integration tests.**

### 7.5 Eligibility Pipeline Tests

| Test | What it verifies |
|------|-----------------|
| `test_check_semantic_gate_pass` | Valid PASS gate → PASS |
| `test_check_semantic_gate_fail` | FAIL gate → FAIL |
| `test_check_semantic_gate_missing_promotion` | Missing + promotion → FAIL |
| `test_check_semantic_gate_missing_exploration` | Missing + exploration → PASS |
| `test_compute_eligibility_includes_semantic` | 7 rules in pipeline |

**Estimated: 5 tests.**

**Total new tests: ~56.**

---

## 8. Risks and Mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R1 | Val split too small for per-contract statistical tests in QUICK mode (200 val hands ÷ 3 contract types ≈ 67 per type) | High | Low (WARN, not FAIL) | Per-contract checks that require N ≥ 200 per cell emit SKIP in QUICK mode. Aggregate checks still run. Only FULL mode enforces per-contract statistical thresholds. |
| R2 | Semantic gate thresholds too loose — pass garbage models | Medium | Medium | Thresholds are intentionally loose at the framework level (catch catastrophic failures only). Model-specific tighter thresholds can be added as additional checks via a `custom_checks` list parameter without modifying the framework. |
| R3 | Semantic gate thresholds too tight — block valid models from minor statistical fluctuations | Low | High | Using p > 0.01 (not 0.05) for ANOVA, large headroom on R²/MAE thresholds, and SKIP behavior for small N. All thresholds derived from Phase 0 observations with ≥3× headroom. |
| R4 | Test split leakage — human views test results before freeze | Medium | Critical | `split_guard.py` provides runtime enforcement. The `ACTIVE_SPLIT` parameter is checked at data-load time. Notebooks physically cannot load test split when `ACTIVE_SPLIT="val"`. CI verifies notebook parameters. |
| R5 | Dual gate artifacts (val + test) confuse reviewers | Low | Low | Clear naming convention (`_val.json` / `_test.json`). Report template §8 renders both gates side-by-side when present. |
| R6 | Feature count changes between training and evaluation (hand_eval.py updated mid-cycle) | Low | Medium | Feature count check reads expected count from source at runtime (not hardcoded). Any feature count mismatch between model artifact and data → FAIL with clear error. |
| R7 | Existing Phase 0 notebooks don't comply with new standard | N/A | None | Non-goal: Phase 0 notebooks are grandfathered. The new standard applies only to Phase 1+ model-rung notebooks. |

---

## 9. Assumptions and Defaults

| # | Assumption/Default | Rationale | Label |
|---|-------------------|-----------|-------|
| A1 | Val fraction = 10% (three_way split: 80/10/10) | Consistent with existing `create_grouped_split()` defaults in `splits.py`. 10% val is standard for model selection. | Existing convention |
| A2 | ANOVA alpha = 0.01 for seat balance | Conservative: reduces false positives from 3–4 parallel tests without formal Bonferroni. See §4.3.1. | Default chosen |
| A3 | Trump invariance threshold = 2.0% relative spread | Phase 0 observed 0.6%. 2.0% provides 3× headroom. | Default chosen |
| A4 | Team balance threshold = |delta| < 0.25 tricks | Inherited from Phase 0 self-play fairness threshold (§3 of r5 report). | Existing convention |
| A5 | Prediction correlation floor = r > 0.10 | Phase 0 observed r ~ 0.44–0.49. Threshold catches only models with no directional signal. | Default chosen |
| A6 | R² floor = 0.05 per contract type | Phase 0 observed 0.19–0.24. Floor catches catastrophic regression only. | Default chosen |
| A7 | MAE ceiling = 2.5 tricks per contract type | Phase 0 observed 1.2–1.4. Ceiling of 2.5 is near-random baseline. | Default chosen |
| A8 | SMOKE mode min sample size = 10 hands | Enough to test pipeline execution; not enough for any statistical inference. | Default chosen |
| A9 | QUICK mode min sample size = 100 hands (val split) | With 2K total, 10% val = 200. Threshold of 100 provides margin. | Default chosen |
| A10 | FULL mode min sample size = 2,000 hands (val split) | With 50K total, 10% val = 5,000. Threshold of 2,000 is comfortably met. | Default chosen |
| A11 | Semantic gate schema version is independent of notebook gate schema version | They serve different purposes: notebook gate = "did it run?", semantic gate = "are the results healthy?". Versioned independently. | Architectural decision |
| A12 | `semantic_gate.json` lives alongside `notebook_gate.json` in the gate output directory | Consistent location for all gate artifacts. The eligibility engine looks in one directory. | Existing convention |
| A13 | Phase 0 notebooks are not retrofitted | They were written before this framework. Retrofitting would be high-effort, low-value since Phase 0 health checks are already comprehensive. | Non-goal boundary |
| A14 | Sign checks reference specific feature names (`trump_count`, `offsuit_aces`, `offsuit_tens_count`) | These are the dominant features per contract type established in Phase 0 §6c. If the feature set changes, sign checks must be updated. The check code reads feature names from a constant, not hardcoded inline. | Default chosen |
| A15 | One semantic gate per model-rung-per-split (not per notebook) | A model rung may involve multiple notebooks, but they share one semantic gate. The final notebook in the sequence emits the gate. | Architectural decision |
| A16 | Chi-square expected ratios for `contract_type_balance` derived from scenario config | Standard 6-scenario config produces 4:1:1 (4 suit scenarios, 1 high, 1 low). The check reads the ratio from the notebook's `CONTRACT_TYPES` and `TRUMPS_FOR_SUIT_CONTRACTS` parameters rather than hardcoding 4:1:1. | Existing convention |
| A17 | Bootstrap CIs use `np.random.RandomState(seed)` for reproducibility | Consistent with all existing RNG usage in the repo. | Existing convention |
| A18 | Blind test evaluation uses the same notebook code but different `ACTIVE_SPLIT` parameter | No separate "test evaluation" script — the same notebook runs twice (val, then test). This ensures identical evaluation logic. | Architectural decision |

---

## 10. PR Decomposition (Suggested)

If implemented, this plan decomposes into approximately 5 PRs:

| PR # | Title | Key Files | Dependencies |
|------|-------|-----------|-------------|
| PR-1 | `feat: split_guard runtime enforcement` | `split_guard.py`, `test_split_guard.py` | None |
| PR-2 | `feat: semantic gate schema v1 + evaluation engine` | `semantic_gate.py`, `test_semantic_gate.py`, `schemas/semantic_gate_v1.md` | PR-1 |
| PR-3 | `feat: model-rung notebook template` | `01_model_rung_template.py`, updated `00_notebook_template.py` | PR-2 |
| PR-4 | `feat: report template generator` | `report_template.py`, `test_report_template.py` | PR-2 |
| PR-5 | `feat: promotion gate integration (semantic gate)` | `eligibility.py` (modified), `run_notebooks.py` (modified), `PROMOTION_WORKFLOW.md` (modified), Makefile, lint rule, `test_eligibility.py` additions | PR-2 |

PRs 3 and 4 are independent of each other and can be developed in parallel after PR-2 merges.
