# Promotion Workflow

Step-by-step workflow for promoting experiment runs to canonical status.

## Prerequisites

- Active batch pointer set in `experiments/promotion/ACTIVE_BATCH.yaml`
- Suite config defined in `experiments/suites/canonical_promotion.yaml`

## Steps

### 1. Set Active Batch

Edit `experiments/promotion/ACTIVE_BATCH.yaml`:
```yaml
batch_id: "promotion_YYYYMMDD"
suite_path: experiments/suites/canonical_promotion.yaml
created_at: "YYYY-MM-DDTHH:MM:SSZ"
```

### 2. Run Suite

```bash
uv run python scripts/run_suite.py \
  --suite experiments/suites/canonical_promotion.yaml \
  --seed 42 --batch-purpose promotion
```

### 3. Generate Per-Run Reports

For each member run discovered from rollup.json:
```bash
PYTHONPATH=src uv run python scripts/generate_report.py \
  --run-dir <run_dir> --fail-on-sanity-failures
```

### 4. Run Notebook Gate

```bash
PYTHONPATH=src uv run python scripts/run_notebooks.py \
  --mode quick --gate-output-dir <run_dir>/reports/notebook_review/
```

### 5. Generate Batch Report

```bash
PYTHONPATH=src uv run python scripts/generate_report.py \
  --batch-dir <rollup_dir>
```

### 6. Review

- Review `BATCH_REPORT.md` and `batch_gate.json`
- Check eligibility: eligible=true means all gates passed

### 7. Promote or Reject

If promoted:
1. Update `notebooks/phase0_bidless/canonical_runs.py` with new run IDs
2. Update `docs/02_agent/CANONICAL_BIDLESS_RUNS.md` with new run details
3. Clear `experiments/promotion/ACTIVE_BATCH.yaml` (set batch_id back to null)

If rejected:
1. Document reason in PR or issue
2. Clear `experiments/promotion/ACTIVE_BATCH.yaml`
