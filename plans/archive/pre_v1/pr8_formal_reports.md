# PR-8 Execution Plan: Formal Reports

**Date:** 2026-02-25
**Branch:** `feat/r0-nb-8-formal-reports`
**Depends:** PR-0 through PR-7 (all merged)
**GitHub PR target:** `main`

---

## Objective

Create three formal report documents for R0 promotion closeout, completing Phase 2 of the R0 Notebook execution plan. These reports capture the R0 evaluation results as permanent, human-reviewed documentation — distinct from the auto-generated `model_arc_r0_20260224.md`.

---

## Deliverables

### D1: R0 Promotion Report
**File:** `docs/04_reports/arc_d_v1/r0/r0_promotion_report.md` — **NEW**

A narrative promotion decision document. Covers:

1. **Executive Summary** — PROMOTED decision, key metrics, one-paragraph rationale
2. **Gate Results** — Tier 1 health checks table (4 checks, all PASS from `promotion_decision_r0.json`)
3. **Evaluation Metrics** — Per-arm metrics from `eval_r0.json` / `eval_r0_full.json`:
   - `net_eppd`, `eppd`, `bid_rate`, `make_rate`, `cvar_5`, `downside_variance`
   - Multi-seed stability table (seeds 42, 43, 44) with per-seed values
4. **Attribution Gap Analysis** — Gap = −0.1437 (constrained outperforms); narrative explaining why this is expected at R0 (3/1/1 features highly targeted, full arm still exploring)
5. **Comparator Context** — Reference to comparator rankings doc (D3), highlight `modeloespecifico` baseline gap
6. **Known Limitations** — Single eval seed for promotion, linear-only models, low/high sample sizes
7. **Decision** — PROMOTED with conditions (R1 must address attribution gap)
8. **Provenance** — Bundle path, artifact SHAs, git SHA, generation timestamp

**Data sources:**
- `data/artifacts/arc_d/r0/promotion_decision_r0.json` (gate checks, per-arm metrics)
- `data/artifacts/arc_d/r0/eval_r0.json`, `eval_r0_s43.json`, `eval_r0_s44.json` (OLSa multi-seed)
- `data/artifacts/arc_d/r0/eval_r0_full.json`, `eval_r0_full_s43.json`, `eval_r0_full_s44.json` (OLSa_Full multi-seed)
- `data/artifacts/arc_d/r0/rung_bundle_r0.json` (provenance)

### D2: OLSa R0 Model Spec
**File:** `docs/01_core/schemas/olsa_r0_model_spec.md` — **NEW**

Concrete instantiation of `hybrid_olsa_v1` schema for R0 frozen artifacts. Contains the actual model parameters — NOT a schema description (that's `hybrid_olsa_v1.md`), but the specific R0 values.

1. **Artifact Identity** — paths, SHA256 hashes, frozen timestamps
2. **OLSa (constrained) Parameters**
   - Per-contract feature lists, weights, biases (from `hybrid_r0.json`)
   - Per-contract residual variance
   - Feature selection constraint: 3/1/1 (suit/high/low)
3. **OLSa_Full (promotional) Parameters**
   - Per-contract feature lists, weights, biases (from `hybrid_r0_full.json`)
   - Per-contract residual variance
   - Feature selection log reference
4. **Training Provenance**
   - Source run: `canonical_bidless_dataset_glutton_42_20260221_175752`
   - Split type: `three_way`
   - Training seed: 42
   - Per-contract train/val/test sizes (from `training_report_r0.json`)
   - Per-contract R² on train/val/test splits
5. **Split Manifests** — references to 3 split files (suit, high, low)
6. **Risk Parameters** — `risk_lambda`, `context_features`
7. **Schema Conformance** — note that both artifacts conform to `hybrid_olsa_v1` schema

**Data sources:**
- `data/artifacts/arc_d/r0/hybrid_r0.json` (constrained arm)
- `data/artifacts/arc_d/r0/hybrid_r0_full.json` (full arm)
- `data/artifacts/arc_d/r0/training_report_r0.json` (train/val/test metrics)
- `data/artifacts/arc_d/r0/feature_selection_log_r0_full.json` (selection trace)
- `data/artifacts/arc_d/r0/split_manifest_r0_{suit,high,low}.json` (splits)

### D3: Comparator Rankings
**File:** `docs/04_reports/arc_d_v1/r0/comparator_rankings.md` — **NEW**

Ranked table of all comparator bidders with bootstrap 95% CIs.

1. **Rankings Table** — All 5 comparators + `hybrid_olsa` R0 arm, sorted by `net_eppd` descending:
   - Columns: Bidder, net_eppd [95% CI], eppd [95% CI], bid_rate, make_rate, cvar_5 [95% CI], net_cvar_5 [95% CI]
   - CIs computed from per-deal data in JSONL logs
2. **Statistical Significance** — Pairwise significance tests (bootstrap p-values) for `net_eppd` differences between adjacent-ranked bidders
3. **Behavioral Profiles** — Brief per-bidder characterization:
   - `modeloespecifico`: always-bid oracle (bid_rate=1.0, make_rate=0.90)
   - `hybrid_olsa` R0: selective bidder (bid_rate=0.83, make_rate=0.83)
   - `rankthetank`: always-bid rank heuristic
   - `fiveheadfred`: always-bid fixed-5
   - `stricthellraiser`: always-bid aggressive (make_rate=0.38)
4. **Key Takeaways** — Gap to `modeloespecifico` ceiling, R0's position in field
5. **Methodology** — n_per=10,000, seed=42, bootstrap n=10,000

**Data sources:**
- `data/artifacts/arc_d/r0/comparator_battery_r0.json` (point estimates)
- `data/runs/auction_comparator_{fiveheadfred,hybrid_olsa,modeloespecifico,rankthetank,stricthellraiser}_42_*/logs/*.jsonl` (per-deal data for bootstrap)

---

## Implementation Steps

### Step 1: Create worktree and branch

```bash
git worktree add ../Bid-Euchre-formal-reports -b feat/r0-nb-8-formal-reports
cd ../Bid-Euchre-formal-reports
ln -s /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/runs data/runs
uv sync --all-extras && uv pip install pre-commit
```

### Step 2: Write extraction script for comparator bootstrap CIs

**File:** `scripts/internal/extract_comparator_cis.py` — **NEW**

This is a one-time internal script (not production code) that:
1. Reads JSONL logs from each comparator's `data/runs/auction_comparator_*` directory
2. Parses per-deal `bidder_team_points` and `net_bidder_team_points` arrays using `build_eval_dataset()` or direct JSONL parsing
3. Computes bootstrap 95% CIs using the existing `bootstrap_ci()` from `src/bid_euchre/analysis/stats.py` for:
   - `net_eppd` (primary)
   - `eppd`
   - `cvar_5`
   - `net_cvar_5`
4. Computes pairwise bootstrap p-values for `net_eppd` between adjacent-ranked bidders
5. Outputs a JSON file with all CIs and p-values to `data/artifacts/arc_d/r0/comparator_cis_r0.json`

**Key functions to reuse:**
- `bootstrap_ci(data, statistic=np.mean, n_bootstrap=10000, seed=42)` from `analysis/stats.py`
- For CVaR: custom statistic `lambda x: np.mean(np.sort(x)[:max(1, int(len(x)*0.05))])`
- For pairwise p-values: bootstrap permutation test (resample difference, fraction < 0)

**Why a script?** The CI computation is data-heavy (5 × 10K deals × 10K bootstrap) and should not live in a report doc. The script outputs clean JSON that D3 consumes.

### Step 3: Run extraction script

```bash
cd ../Bid-Euchre-formal-reports
PYTHONPATH=src uv run python scripts/internal/extract_comparator_cis.py \
  --artifacts-dir data/artifacts/arc_d/r0 \
  --runs-dir data/runs \
  --seed 42 \
  --n-bootstrap 10000 \
  --output data/artifacts/arc_d/r0/comparator_cis_r0.json
```

Verify output JSON has all 5 bidders + hybrid_olsa with CIs.

**Note:** `comparator_cis_r0.json` is a gitignored artifact (lives under `data/artifacts/`). It is consumed locally to write the report but not committed.

### Step 4: Write multi-seed extraction for promotion report

Read the 6 eval files (3 per arm × 2 arms) and extract the key metrics per seed. This can be done inline in the report-writing process — no separate script needed. The eval JSONs already contain:
- `net_expected_points_per_deal`, `expected_points_per_deal`, `bid_rate`, `make_rate`, `cvar_5`, `downside_variance`

Pattern:
```python
import json
from pathlib import Path

seeds = [42, 43, 44]
for arm, suffix in [("olsa", ""), ("olsa_full", "_full")]:
    for seed in seeds:
        seed_suffix = "" if seed == 42 else f"_s{seed}"
        path = f"data/artifacts/arc_d/r0/eval_r0{suffix}{seed_suffix}.json"
        data = json.loads(Path(path).read_text())
        # Extract metrics from data["strategies"][0]
```

### Step 5: Write D1 — R0 Promotion Report

Create `docs/04_reports/arc_d_v1/r0/r0_promotion_report.md` with the structure from D1 above.

**Implementation notes:**
- Write manually (not auto-generated) — this is a curated decision document
- Reference specific numbers from the eval JSONs read in Step 4
- Multi-seed table format:

| Metric | Seed 42 | Seed 43 | Seed 44 | Mean ± Std |
|--------|---------|---------|---------|------------|
| net_eppd | 1.6274 | ... | ... | ... |

- Attribution gap narrative: explain negative gap is benign at R0 (constrained arm's 3/1/1 features are hand-picked strong predictors; full arm forward-selects from 39 and may include weaker features)
- Gate checks: replicate the 4-row tier_1_checks table from `promotion_decision_r0.json`

### Step 6: Write D2 — OLSa R0 Model Spec

Create `docs/01_core/schemas/olsa_r0_model_spec.md` with the structure from D2 above.

**Implementation notes:**
- Read actual weights/biases from `hybrid_r0.json` and `hybrid_r0_full.json`
- Format weights in tables with 4 decimal places (matching existing report style)
- Include SHA256 hashes verbatim from `rung_bundle_r0.json`
- Training metrics table from `training_report_r0.json`:

| Contract | Split | R² | MAE | n |
|----------|-------|----|-----|---|
| suit | train | 0.2109 | 1.2321 | 640,000 |
| suit | val | 0.2184 | 1.2318 | 80,000 |
| suit | test | 0.2153 | 1.2351 | 80,000 |

### Step 7: Write D3 — Comparator Rankings

Create `docs/04_reports/arc_d_v1/r0/comparator_rankings.md` using the CI data from Step 3.

**Implementation notes:**
- Rankings table sorted by `net_eppd` descending (modeloespecifico > hybrid_olsa > rankthetank > fiveheadfred > stricthellraiser)
- CI format: `1.63 [1.55, 1.71]`
- Pairwise significance: `***` (p<0.001), `**` (p<0.01), `*` (p<0.05), `ns` (p≥0.05)
- Bidder profiles: 1-2 sentences each explaining bidding strategy

### Step 8: Validation

```bash
cd ../Bid-Euchre-formal-reports
make docs-check          # Verify doc freshness
make check-quiet         # Full validation suite
```

Specific verifications:
1. All 3 new files exist under their target directories
2. No backtick-quoted paths that reference non-existent files (docs-check gotcha)
3. `make notebook-run-arc-d` still passes (notebooks unchanged)

### Step 9: Commit and open PR

```bash
PATH=".venv/bin:$PATH" git add \
  docs/04_reports/arc_d_v1/r0/r0_promotion_report.md \
  docs/01_core/schemas/olsa_r0_model_spec.md \
  docs/04_reports/arc_d_v1/r0/comparator_rankings.md \
  scripts/internal/extract_comparator_cis.py

PATH=".venv/bin:$PATH" git commit -m "docs: add R0 formal reports (promotion, model spec, comparators)"
git push -u origin feat/r0-nb-8-formal-reports
gh pr create --base main ...
```

---

## File Ownership Matrix

| File | Action | Contention Risk |
|------|--------|-----------------|
| `docs/04_reports/arc_d_v1/r0/r0_promotion_report.md` | NEW | None |
| `docs/01_core/schemas/olsa_r0_model_spec.md` | NEW | None |
| `docs/04_reports/arc_d_v1/r0/comparator_rankings.md` | NEW | None |
| `scripts/internal/extract_comparator_cis.py` | NEW | None |

**All files are NEW** — zero contention risk, no merge conflicts possible.

---

## Acceptance Criteria (from execution plan)

- [x] Reports reference specific metric values from R0 eval (not placeholders)
- [x] Model spec matches frozen artifact contents (SHA256-verifiable)
- [x] Comparator rankings include all bidders with CIs
- [x] `make docs-check` passes
- [x] No H2H Matchup Report (deferred per C50)

## Phase 2 Exit Gate

After this PR merges, Phase 2 is complete:

```bash
make check-quiet
make notebook-run-arc-d NOTEBOOK="notebooks/arc_d/r0/*.ipynb"
```

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| JSONL logs missing for a comparator | Low (verified: all 5 exist) | Script errors loud on missing data |
| docs-check fails on backtick paths | Medium | Use plain text for artifact paths in reports, not backticks |
| Multi-seed metrics inconsistent | Low | Table shows all 3; narrative addresses variance |
| Attribution gap narrative too speculative | Medium | Stick to facts: gap magnitude, direction, R0 context |

---

## Estimated Scope

- **New files:** 4 (3 docs + 1 internal script)
- **Modified files:** 0
- **Tests:** None required (docs-only PR; script is internal/one-time)
- **Risk level:** Low (all new files, no code changes)
