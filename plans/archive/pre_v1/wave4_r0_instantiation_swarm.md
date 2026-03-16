# Wave 4: R0 Instantiation — 2-Agent Swarm Plan

## Context

PR #421 (report generator rewrite) merged. The full Arc D reporting infrastructure is
complete: chart modules (#417), three notebook templates (#418-#420), and the 11-section
report generator (#421). This plan instantiates the infrastructure for R0.

### Scope Correction

My earlier "Wave 5 cleanup" framing was incorrect:
- **PR-I1** is a Wave 1 foundational PR (already merged as #389)
- **Makefile `recursive=True`** is already correct — no fix needed
- The old `01_model_rung_template.py` is still used by phase0 notebooks — don't deprecate yet

The real remaining work is **two independent PRs** that can run in parallel.

## Data Inventory (confirmed on disk)

| Resource | Path | Status |
|----------|------|--------|
| R0 rung bundle | `data/artifacts/arc_d/r0/rung_bundle_r0.json` | EXISTS |
| OLSa model | `data/artifacts/arc_d/r0/hybrid_r0.json` | EXISTS |
| OLSa_Full model | `data/artifacts/arc_d/r0/hybrid_r0_full.json` | EXISTS |
| OLSa eval (seed 42) | `data/artifacts/arc_d/r0/eval_r0.json` | EXISTS |
| Promotion decision | `data/artifacts/arc_d/r0/promotion_decision_r0.json` | EXISTS |
| Comparator battery | `data/artifacts/arc_d/r0/comparator_battery_r0.json` | EXISTS |
| Eval run logs (OLSa) | `data/runs/arc_d_eval_r0_42_20260221_180253/` | EXISTS |
| Eval run logs (Full) | `data/runs/arc_d_eval_r0_full_42_20260221_175607/` | EXISTS |
| Existing R0 report | `docs/04_reports/arc_d_v1/r0/model_arc_r0_20260222.md` | EXISTS (39 lines, minimal) |

## Agent 1: PR-V1 — R0 Notebook Instantiation + Full Report

**Branch:** `feat/arc-d-v1-r0-instantiation`
**Worktree:** `../Bid-Euchre-v1`

### Step 1: Instantiate 3 R0 Notebooks

Copy each template to `notebooks/arc_d/` with R0-specific parameters filled in.
Per-rung notebooks are standalone copies (from MEMORY.md: "Per-rung notebooks are
standalone copies of the template, NOT auto-composed").

#### 1a. `notebooks/arc_d/10_feature_health_r0.py`

Copy from `notebooks/_templates/arc_d/10_feature_health.py`. Change parameters:

```python
EVAL_LOG_PATH = "data/runs/arc_d_eval_r0_42_20260221_180253"
MODE = "QUICK"
RUNG_ID = "r0"
CHART_OUTPUT_DIR = ""
```

**Note:** EVAL_LOG_PATH points to a directory — the notebook's auto-resolution logic
(Finding 2 fix from #421) will find the JSONL inside `logs/`.

#### 1b. `notebooks/arc_d/20_outcome_health_r0.py`

Copy from `notebooks/_templates/arc_d/20_outcome_health.py`. Same parameter changes.

#### 1c. `notebooks/arc_d/30_feature_outcome_eval_r0.py`

Copy from `notebooks/_templates/arc_d/30_feature_outcome_eval.py`. Change parameters:

```python
EVAL_LOG_PATH = "data/runs/arc_d_eval_r0_42_20260221_180253"
ARTIFACT_DIR = "data/artifacts/arc_d/r0"
MODE = "QUICK"
RUNG_ID = "r0"
CHART_OUTPUT_DIR = ""
```

#### 1d. Jupytext Sync

For each `.py` file, generate paired `.ipynb`:
```bash
uv run jupytext --to ipynb --output <ipynb> <py>
uv run nbstripout <ipynb>
```

### Step 2: Generate Full R0 Rung Report

Replace the 39-line minimal report with the full 11-section version.

**Script approach** — write a small script `scripts/internal/generate_r0_report.py`:

```python
from pathlib import Path
from bid_euchre.reporting.arc_d_report import generate_arc_d_rung_report
from bid_euchre.datasets.eval_dataset import build_eval_dataset

bundle = Path("data/artifacts/arc_d/r0/rung_bundle_r0.json")
decision = Path("data/artifacts/arc_d/r0/promotion_decision_r0.json")
eval_log = "data/runs/arc_d_eval_r0_42_20260221_180253/logs/arc_d_eval_r0_42_20260221_180253_hybrid_olsa_r0.jsonl"

eval_df = build_eval_dataset(eval_log)

report = generate_arc_d_rung_report(
    bundle,
    decision_path=decision,
    eval_df=eval_df,
    matchup_run_dir="data/runs/arc_d_eval_r0_42_20260221_180253",
)

output = Path("docs/04_reports/arc_d_v1/r0/model_arc_r0_20260224.md")
output.write_text(report)
print(f"Wrote {len(report)} chars to {output}")
```

**Alternative:** Just run the generator inline and commit the output. The script approach
is better for reproducibility (per project rules: "Include exact repro command with seed
in PR description").

**Important:** The old report `model_arc_r0_20260222.md` should be kept as-is (or removed
if the new report supersedes it). Recommendation: remove the old file since the new one
is strictly superior.

### Step 3: Regenerate Dashboard

```bash
uv run python scripts/internal/generate_arc_dashboard.py --snapshot
```

This is idempotent and reads all rung bundles to produce
`docs/04_reports/arc_d_v1/model_arc_d_dashboard.md`.

### Step 4: Verify

```bash
make check  # All 5 stages pass
# Verify notebooks are synced and outputs stripped
# Verify no data/ files are staged
```

### Files Created/Modified

| File | Action |
|------|--------|
| `notebooks/arc_d/10_feature_health_r0.py` | CREATE (copy template + params) |
| `notebooks/arc_d/10_feature_health_r0.ipynb` | CREATE (jupytext sync) |
| `notebooks/arc_d/20_outcome_health_r0.py` | CREATE (copy template + params) |
| `notebooks/arc_d/20_outcome_health_r0.ipynb` | CREATE (jupytext sync) |
| `notebooks/arc_d/30_feature_outcome_eval_r0.py` | CREATE (copy template + params) |
| `notebooks/arc_d/30_feature_outcome_eval_r0.ipynb` | CREATE (jupytext sync) |
| `docs/04_reports/arc_d_v1/r0/model_arc_r0_20260224.md` | CREATE (full 11-section report) |
| `docs/04_reports/arc_d_v1/r0/model_arc_r0_20260222.md` | DELETE (superseded) |
| `scripts/internal/generate_r0_report.py` | CREATE (reproducibility script) |

---

## Agent 2: PR-C1 — Arc D Template Contract Tests

**Branch:** `feat/arc-d-template-contracts`
**Worktree:** `../Bid-Euchre-c1`

### Rationale

The 3 new Arc D notebook templates (10_, 20_, 30_) currently have zero structural
contract tests. The old `01_model_rung_template.py` has 11+ tests in
`test_notebook_template_contract.py`. The new templates need equivalent coverage to
prevent parameter drift and section omission.

### Step 1: Add Contract Tests

Add a new test class `TestArcDTemplateContract` to
`tests/unit/test_notebook_template_contract.py` with tests for each template.

#### Tests for All 3 Templates (shared assertions)

```python
class TestArcDTemplateContract:
    """Contract tests for Arc D evaluation notebook templates."""

    TEMPLATES = {
        "10_feature_health": {...required_params, required_sections, required_imports...},
        "20_outcome_health": {...},
        "30_feature_outcome_eval": {...},
    }
```

For each template, verify:

1. **Required parameters exist** as declarations:
   - All 3: `EVAL_LOG_PATH`, `MODE`, `RUNG_ID`, `CHART_OUTPUT_DIR`
   - 30 only: `ARTIFACT_DIR`

2. **Required imports present**:
   - 10: `build_eval_dataset`, `plot_feature_distribution` or `plot_feature_correlation`
   - 20: `build_eval_dataset`, `plot_auction_health` or `plot_bidder_performance`
   - 30: `build_eval_dataset`, `load_eval_metrics`

3. **Removed/old parameters absent**:
   - None should declare `SPLIT_TYPE`, `ACTIVE_SPLIT`, `MODEL_ARTIFACT_PATH`

4. **Key patterns present**:
   - All 3: `MODE` controls deal count (SMOKE/QUICK/FULL pattern)
   - 30: `_resolve_path` helper defined (CWD-independence)
   - 30: `IsADirectoryError` in except tuple (directory resolution guard)
   - All 3: Jupytext header present (`# ---` / `jupytext:`)

5. **Directory resolution present** (10, 20, 30):
   - `eval_log.is_dir()` check present (Finding 2 fix)

#### Tests for R0 Instances (if Agent 1's PR merges first)

If R0 notebooks exist, add tests verifying:
- Parameters filled with R0-specific values (`RUNG_ID = "r0"`)
- `EVAL_LOG_PATH` points to real run directory
- `ARTIFACT_DIR` points to real artifact directory (30 only)

**Note:** These tests should be guarded with `pytest.mark.skipif(not path.exists())`
since R0 instances won't exist until PR-V1 merges.

### Step 2: Verify

```bash
uv run python -m pytest tests/unit/test_notebook_template_contract.py -v
make check
```

### Files Modified

| File | Action |
|------|--------|
| `tests/unit/test_notebook_template_contract.py` | MODIFY (add ~80 lines) |

---

## Swarm Coordination

```
Agent 1 (PR-V1)                    Agent 2 (PR-C1)
─────────────────                  ─────────────────
worktree: Bid-Euchre-v1           worktree: Bid-Euchre-c1
branch: feat/arc-d-v1-r0-inst     branch: feat/arc-d-template-contracts

Creates 6 notebooks + report       Adds contract tests for templates
Touches: notebooks/arc_d/          Touches: tests/unit/
         docs/04_reports/arc_d_v1/r0/
         scripts/internal/

NO FILE OVERLAP ✓                  NO FILE OVERLAP ✓
```

**Merge order:** Either can merge first — no dependency between them.

**If Agent 1 merges first:** Agent 2 can optionally add R0-instance tests.
**If Agent 2 merges first:** Agent 1 proceeds unchanged.

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Eval data not available in worktree | Symlink `data/runs/` from main checkout |
| Report generation fails (missing eval_df columns) | Graceful degradation — report works without eval_df |
| Notebook sync issues | Strip outputs + sync before commit |
| docs-check fails on backtick paths | Use plain text for data paths in committed docs |

## Verification Checklist (Both Agents)

- [ ] `make check` passes (repo-lint, ruff, pytest, notebook-check, docs-check)
- [ ] No `data/runs/` or `data/artifacts/` files staged
- [ ] PR description uses `.github/pull_request_template.md`
- [ ] Worktree proof included in PR description
