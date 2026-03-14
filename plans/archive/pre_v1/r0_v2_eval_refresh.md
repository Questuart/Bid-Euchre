# R0 v2 Eval Refresh Plan

**Created:** 2026-03-04T04:19:28Z
**Session:** Active — use this plan for the current session
**Status:** IN PROGRESS (eval runs DONE, executing Steps 3-8)
**Branch:** `eval-v2-bid-level-search`
**Worktree:** `Bid-Euchre-eval-v2`

---

## 1. Problem Statement

The 3 self-play eval configs (`arc_d_eval_r0.yaml`, `arc_d_eval_r0_full.yaml`,
`arc_d_eval_r0_diagnostic.yaml`) were never updated to include `bid_level_search: true`
when that parameter was added in PR #493. As a result:

- All 7 eval runs (from 2026-02-21) used `bid_level_search=False` (v1 floor(mu) bidding)
- `HybridOLSaBidder.__init__` defaults to `bid_level_search=False` (bidding.py:986)
- Even re-running with the current code + old config would reproduce v1 behavior
- The v2 batteries (comparator v6, H2H v4, C33 ablation) all correctly set `bid_level_search: true`
- The eval runs are the ONLY v2 data source that was missed

### Decision Safety Assessment

**All v2 decisions are SAFE.** The 5 decision notebooks do NOT use the stale eval runs:

| Decision | Notebook(s) | Data Source | Uses Eval Runs? |
|----------|------------|-------------|-----------------|
| Lambda (RETAIN λ=0.0) | nb58, nb59 | Bidless dataset + lambda sweep script (post-PR#493) | NO |
| Threshold (RETAIN t=0) | nb56 | Bidless dataset + v2 bid_level_search_vectorized() | NO |
| Normalizer (NO_GO) | nb55, screen script | Bidless dataset + comparator v6 battery | NO |
| C33 ablation | nb57 | C33 run from 2026-03-02 (post-PR#493) | NO |
| OneModel (REJECT) | training script | Bidless dataset + comparator onemodel config | NO |

**Why bidless data is safe:** The bidless dataset records play outcomes (tricks_won by
GluttonStrategy) which are independent of bidding policy. Notebooks apply v2 bid_level_search
on top of those outcomes. The data doesn't change — only the applied decision logic does.

### What IS Affected

The eval runs feed **diagnostic notebooks** (nb10, 20, 25, 30, 40) which in turn feed
**3 reports** that cite eval-run-specific metrics:

| Report | What's Stale |
|--------|-------------|
| `01_r0_promotion_report.md` | Self-play eval metrics: bid_rate, make_rate, net_eppd, CVaR (3 seeds × 2 arms) |
| `02_model_arc_r0.md` | Feature stats, contract mix, outcome stats, auction analysis from nb10-40 |
| `23_phase0_to_r0_progression.md` | Eval run path + derived outcome statistics |

---

## 2. Execution Steps

### Step 1: Fix eval configs (DONE)

Add `bid_level_search: true` to all bidding policy entries in:
- [x] `experiments/configs/arc_d_eval_r0.yaml`
- [x] `experiments/configs/arc_d_eval_r0_full.yaml`
- [x] `experiments/configs/arc_d_eval_r0_diagnostic.yaml`

### Step 2: Regenerate eval runs (DONE)

6 runs completed (50k hands each):

| Config | Seed | Run ID | Status |
|--------|------|--------|--------|
| arc_d_eval_r0 | 42 | `arc_d_eval_r0_42_20260303_201729` | DONE |
| arc_d_eval_r0 | 43 | `arc_d_eval_r0_43_20260303_201730` | DONE |
| arc_d_eval_r0 | 44 | `arc_d_eval_r0_44_20260303_201731` | DONE |
| arc_d_eval_r0_full | 42 | `arc_d_eval_r0_full_42_20260303_201732` | DONE |
| arc_d_eval_r0_full | 43 | `arc_d_eval_r0_full_43_20260303_201734` | DONE |
| arc_d_eval_r0_full | 44 | `arc_d_eval_r0_full_44_20260303_201735` | DONE |

**Note:** Diagnostic config run is NOT needed — no notebook or report depends on it.
The config fix is for completeness; the run can be done post-freeze if ever needed.

### Step 3: Extract eval artifacts

After runs complete, re-extract the eval summary JSON artifacts that the rung bundle
references. These are committed to `data/artifacts/arc_d/r0/`:

| Artifact | Source Run |
|----------|-----------|
| `eval_r0.json` | arc_d_eval_r0 seed 42 |
| `eval_r0_s43.json` | arc_d_eval_r0 seed 43 |
| `eval_r0_s44.json` | arc_d_eval_r0 seed 44 |
| `eval_r0_full.json` | arc_d_eval_r0_full seed 42 |
| `eval_r0_full_s43.json` | arc_d_eval_r0_full seed 43 |
| `eval_r0_full_s44.json` | arc_d_eval_r0_full seed 44 |

**Pipeline (RESOLVED):** `generate_bidder_evaluation()` in `src/bid_euchre/reporting/evaluator.py`
writes `{run_dir}/reports/bidding_strategy/evaluation.json`. The committed artifacts in
`data/artifacts/arc_d/r0/` are identical copies of these per-run files. After runs complete:

```bash
# Copy eval artifacts from run dirs to artifacts dir
cp data/runs/<new_r0_42>/reports/bidding_strategy/evaluation.json \
   data/artifacts/arc_d/r0/eval_r0.json
# Repeat for s43, s44, full_42, full_s43, full_s44
```

Then update bundle pointers if paths change (they won't — same filenames, just new content).

### Step 4: Update notebook parameters

Update the EVAL_LOG_PATH / EVAL_RUN_DIR parameter in each notebook to point to the
new v2 run directory:

| Notebook | Parameter | Old Value | New Value |
|----------|-----------|-----------|-----------|
| `10_feature_health.py` | `EVAL_LOG_PATH` | `data/runs/arc_d_eval_r0_42_20260221_180253` | `data/runs/<new_constrained_42_run_id>` |
| `20_outcome_health.py` | `EVAL_LOG_PATH` | `data/runs/arc_d_eval_r0_42_20260221_180253` | Same |
| `25_auction_health.py` | `EVAL_LOG_PATH` | `data/runs/arc_d_eval_r0_42_20260221_180253` | Same |
| `30_feature_outcome_eval.py` | `EVAL_LOG_PATH` | `data/runs/arc_d_eval_r0_42_20260221_180253` | Same |
| `40_r0_baseline.py` | `EVAL_RUN_DIR` | `data/runs/arc_d_eval_r0_42_20260221_180253` | Same |

All 5 notebooks use the constrained arm seed 42 run.

### Step 5: Sync + re-run notebooks

**Critical:** Step 4 edits `.py` files but `papermill` executes `.ipynb` files.
Must sync before execution or notebooks will run with old parameters.

```bash
# 5a: Sync .py → .ipynb BEFORE execution
make notebook-sync

# 5b: Execute each notebook in SMOKE mode for quick validation
for nb in 10_feature_health 20_outcome_health 25_auction_health \
          30_feature_outcome_eval 40_r0_baseline; do
  uv run papermill notebooks/arc_d/r0/${nb}.ipynb /tmp/${nb}_out.ipynb \
    -p MODE SMOKE 2>&1 | tail -3
done
```

Reports cite specific numbers from notebook outputs. For report-quality numbers,
execute with QUICK or FULL mode using the actual eval run data (not synthetic fallback).

For report-quality numbers, execute with QUICK or FULL mode using the actual
eval run data (not synthetic fallback).

### Step 6: Update reports with new metrics

After notebook execution, extract updated metrics and revise 3 reports:

#### 6a. `01_r0_promotion_report.md`

Update self-play eval tables (§1 summary + §2 evaluation metrics):
- OLSa_Full metrics: net_eppd, eppd, bid_rate, make_rate, CVaR (3 seeds)
- OLSa metrics: same set (3 seeds)
- Multi-seed stability analysis
- Eval run paths in provenance section

#### 6b. `02_model_arc_r0.md`

Update diagnostic sections sourced from nb10-40:
- §Feature Health: seat balance, per-contract feature stats (from nb10)
- §Outcome Health: mean tricks, per-contract outcome stats, make rates (from nb20)
- §Auction Analysis: contract selection frequency, bid distribution, auction lengths (from nb25)
- §Feature-Outcome Eval: Gaussian diagnostics reference (from nb30)
- §Reproduction: eval run path in provenance

#### 6c. `23_phase0_to_r0_progression.md`

Update R0-derived content throughout the report (not just the R0 row):
- Eval run ID in R0 row
- Hand counts (will change with bid_level_search — more deals bid on)
- Outcome statistics (mean tricks, make rates, declaring/defending splits)
- Provenance table: R0 eval run path (line 242) and R0 sample count (line 246)
- Reproduction section: R0 `build_eval_dataset()` snippet (line 277) with new run/log paths
- V2 context note (line 201-207): update "pre-v2 self-play runs" claim — these ARE now
  v2 runs, so the note should say the eval data reflects v2 bid-level search policy

### Step 6d: Regenerate promotion decision artifact

`data/artifacts/arc_d/r0/promotion_decision_r0.json` embeds stale eval metrics
(bid_rate=0.632 for OLSa, 0.828 for OLSa_Full — both from v1 floor(mu) runs).
Regenerate after eval artifacts are updated:

```bash
PYTHONPATH=src uv run python scripts/write_r0_promotion.py \
  --bundle data/artifacts/arc_d/r0/rung_bundle_r0.json \
  --output data/artifacts/arc_d/r0/promotion_decision_r0.json
```

### Step 6e: Update stale run ID references in scripts/docs

These files reference the old run ID `arc_d_eval_r0_42_20260221_180253` in
docstrings, usage examples, or narrative conventions. Update to new run ID:

| File | Type | What to Update |
|------|------|---------------|
| `scripts/internal/generate_rung_charts.py:10` | Usage example | `--eval-dir` path |
| `docs/02_agent/REPORT_NARRATIVE_CONVENTIONS.md:218` | Example | `--eval-dir` path |
| `scripts/run_r0b.sh:14-20` | Header comments | 6 old eval run IDs + stale net_eppd values |
| `tests/unit/test_arc_d_reporting.py:977` | Test fixture name | Cosmetic — test creates its own tmp dir; update for consistency but not functional |

**Note:** `plans/MASTER_PLAN.md` also references old run IDs but is deferred to
post-freeze (archived governance doc). `docs/04_reports/r0/archive/v1/` files are
v1 archives — do NOT update.

### Step 6f: Regenerate registry + dashboard artifacts

`docs/02_agent/MODEL_ARC_RUNS.md` (line 11) and `docs/04_reports/model_arc_d_dashboard.md`
(line 5) embed stale v1 net_eppd values (OLSa=1.6274, OLSa_Full=1.4837). These are
generated by `scripts/internal/update_arc_registry.py` and `scripts/internal/generate_arc_dashboard.py`.

After Step 6d (promotion decision regeneration), run the canonical pipeline from
`scripts/run_r0b.sh` Steps 5-7:

```bash
# Update rung bundle eval pointers (Step 5 of run_r0b.sh)
ARTIFACT=data/artifacts/arc_d/r0
PYTHONPATH=src uv run python scripts/update_r0_bundle.py \
  --bundle "$ARTIFACT/rung_bundle_r0.json" \
  --arm olsa \
  --eval-seed42 "$ARTIFACT/eval_r0.json" \
  --eval-seed43 "$ARTIFACT/eval_r0_s43.json" \
  --eval-seed44 "$ARTIFACT/eval_r0_s44.json"

PYTHONPATH=src uv run python scripts/update_r0_bundle.py \
  --bundle "$ARTIFACT/rung_bundle_r0.json" \
  --arm olsa_full \
  --eval-seed42 "$ARTIFACT/eval_r0_full.json" \
  --eval-seed43 "$ARTIFACT/eval_r0_full_s43.json" \
  --eval-seed44 "$ARTIFACT/eval_r0_full_s44.json"

# Regenerate registry (Step 7 of run_r0b.sh)
PYTHONPATH=src uv run python scripts/internal/update_arc_registry.py \
  --bundle "$ARTIFACT/rung_bundle_r0.json" \
  --decision "$ARTIFACT/promotion_decision_r0.json"

# Regenerate dashboard
PYTHONPATH=src uv run python scripts/internal/generate_arc_dashboard.py \
  --artifacts-base data/artifacts/arc_d \
  --output docs/04_reports/model_arc_d_dashboard.md \
  --snapshot
```

### Step 6g: Update run_r0b.sh run IDs

`scripts/run_r0b.sh` (lines 14-20) embeds old v1 run IDs in its header comments.
Update to new v2 run IDs for provenance accuracy.

### Step 7: Validate

```bash
make check-quiet   # Full validation
```

Stale reference sweep — check ALL file types, not just reports:

```bash
# Check reports, notebooks, scripts, docs for old v1 eval run IDs
# Use run-ID pattern (not just timestamp prefix) to catch all variants
grep -rn -E "arc_d_eval_r0(_full)?_[0-9]+_20260221_" \
  docs/04_reports/r0/ \
  notebooks/arc_d/r0/ \
  scripts/ \
  experiments/configs/ \
  docs/02_agent/ \
  --include='*.md' --include='*.py' --include='*.yaml' --include='*.sh' \
  | grep -v 'archive/v1/' \
  | grep -v 'plans/archive/' \
  | grep -v '__pycache__'
# Should return ZERO matches (all should reference new 20260303 run IDs)
```

Additional checks:
- `notebook-check` passes (sync verification)
- All report numbers match new eval artifact values
- `MODEL_ARC_RUNS.md` net_eppd values match `promotion_decision_r0.json`
- Dashboard values match registry

### Step 8: Commit, push, PR, review, ship

Single PR with all changes:
- 3 config fixes (eval YAML files)
- 5 notebook parameter updates (nb10, 20, 25, 30, 40)
- 6 eval artifact updates (eval_r0*.json — committed JSON)
- 1 rung bundle update (rung_bundle_r0.json — eval pointers refreshed)
- 1 promotion decision artifact regeneration (promotion_decision_r0.json)
- 1 registry update (MODEL_ARC_RUNS.md — net_eppd values)
- 1 dashboard update (model_arc_d_dashboard.md — net_eppd values)
- 3 report revisions (01_promotion, 02_model_arc, 23_progression)
- 3 stale run ID updates (generate_rung_charts.py, REPORT_NARRATIVE_CONVENTIONS.md, run_r0b.sh)
- 1 test fixture name update (test_arc_d_reporting.py — cosmetic)
- 2 plans archived (hitl_review_qa, normalizer_screen_spec)
- 1 plan added (this plan)
- Jupytext sync for updated notebooks

---

## 3. What This Plan Does NOT Cover

- **Re-running decision notebooks (55-59):** Not needed — decisions are safe (§1)
- **Re-running batteries (comparator, H2H, C33):** Already v2-correct
- **Regenerating bidless dataset:** Not needed — play outcomes are policy-independent
- **Diagnostic eval run:** Config fixed but run not needed (no consumers)
- **Normalizer offline screen re-run:** Not needed — used comparator data, not eval runs

---

## 4. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| New eval numbers materially change promotion recommendation | Low | High | All v2 decisions used independent data; eval is diagnostic |
| bid_level_search changes contract mix dramatically | Medium | Medium | Expected — this IS the v2 policy change; document delta |
| Report numbers don't match across reports | Low | Medium | Cross-check promotion report vs model spec vs progression |
| Notebook sync missed before execution | Medium | High | Step 5 now mandates `make notebook-sync` before `papermill` |

---

## 5. Plan Archival

### Archive now (completed/consumed, no active references outside plans/):

| File | Reason |
|------|--------|
| `r0_v2_hitl_review_qa.md` | COMPLETE — PR #517 merged all 25 findings |
| `r0_v2_normalizer_screen_spec.md` | COMPLETE — PR #509 merged, report written |

### Keep active:

| File | Reason |
|------|--------|
| `r0_canonical_v2_plan.md` | Master v2 plan (still governing freeze) |
| `r0_canonical_v2_promotion_gate.md` | Gate checklist (pending HITL sign-off) |
| `r0_v2_lambda_tuning_protocol.md` | Track D protocol (completed, referenced by nb58/59) |
| `r0_v2_normalizer_protocol.md` | Track E protocol (completed, referenced by reports) |
| `r0_v2_threshold_protocol.md` | Track B protocol (referenced by nb56) |
| `r0_v2_pr_a_amendments.md` | Referenced by nb56 |
| `r0_v2_onemodel_protocol.md` | Track F protocol (referenced by report 14) |
| `r1_follow_ups.md` | Active follow-ups |
| `arc_d_execution_plan.md` | R1+ reference |
| `contract_selection_analysis.md` | Referenced by nb55 + report 10 |
| `r0_pass_threshold_protocol.md` | Referenced by nb56 + report 11 |
| `MASTER_PLAN.md` | Deferred to post-freeze (has active references) |
| **`r0_v2_eval_refresh.md`** | **THIS PLAN — active** |
