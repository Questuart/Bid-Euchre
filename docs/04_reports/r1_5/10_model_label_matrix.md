# Phase 1A: 2×2 Model×Label Matrix — H2H Evaluation

**Date:** 2026-03-12
**Arc:** D — OLSa-Hybrid Bidder
**Rung:** R1.5.3 (model-architecture exploration)
**Predecessor:** `09_multi_rollout_diagnostic.md` (H14 CONFIRMED), `08_gbt_prototype_evaluation.md` (GBT QUICK)
**Plan:** `plans/sessions/2026-03-12_r1-5-3-forward-plan-v2.md`, Phase 1A

## 1. Goal

Decompose the independent contributions of **model capacity** (OLS vs GBT) and
**label quality** (single-rollout N=1 vs multi-rollout N=20) to gameplay
performance. The 2×2 factorial design answers the critical question: does
multi-rollout OLS match or beat single-rollout GBT?

## 2. Hypothesis

| ID | Hypothesis | Status |
|----|-----------|--------|
| H12 | Bimodal make/set target causes suit regression via between-mode OLS prediction | **SUPPORTED** — OLS suit delta stays negative regardless of label quality |
| H14 | Imperfect-info label averaging improves OLS suit fit | CONFIRMED (Phase 0) — but R² improvement doesn't translate to gameplay |
| H15 | Model capacity matters more than label quality for gameplay | **NEW → CONFIRMED** |

## 3. Design

### 3.1 Experimental Matrix

| Cell | Model | Labels | Training Dataset |
|------|-------|--------|-----------------|
| A | OLS | N=1 (single-rollout) | `action_value_quick_42` (existing) |
| B | OLS | N=20 (multi-rollout) | `av_quick_n20_42` (new) |
| C | GBT | N=1 (single-rollout) | `action_value_quick_42` (existing) |
| D | GBT | N=20 (multi-rollout) | `av_quick_n20_42` (new) |
| — | Hybrid R0 | — (handcrafted) | `hybrid_r0_full.json` (incumbent) |

### 3.2 H2H Battery

- 5-bidder roster: Cells A–D + Hybrid R0
- 25 matchups: 5 self-play + 20 cross-matchups (both seat rotations)
- 2,500 deals per matchup, seed=42, paired deals
- Play strategy: GluttonStrategy (all seats)

## 4. Results

### 4.1 Model Fit (R²)

| Cell | Suit | High | Low | Pass |
|------|------|------|-----|------|
| A (OLS, N=1) | 0.565 | 0.533 | 0.514 | 0.046 |
| B (OLS, N=20) | **0.706** | **0.678** | **0.688** | **0.095** |
| C (GBT, N=1) | 0.594 | 0.550 | 0.538 | 0.030 |
| D (GBT, N=20) | **0.745** | **0.707** | **0.727** | **0.091** |

Label effect on R² is dramatic: +0.14 for OLS suit, +0.15 for GBT suit.
Model effect on R² is modest: +0.03 (N=1), +0.04 (N=20).

### 4.2 Self-Play Sanity

| Bidder | net_eppd | CI | avg_bid | make% |
|--------|----------|-------|---------|-------|
| Cell A (OLS, N=1) | +0.003 | [-0.174, +0.182] | 4.00 | 94.6% |
| Cell B (OLS, N=20) | +0.024 | [-0.158, +0.206] | 3.98 | 94.8% |
| Cell C (GBT, N=1) | +0.029 | [-0.212, +0.269] | 5.44 | 87.1% |
| Cell D (GBT, N=20) | -0.027 | [-0.253, +0.195] | 5.39 | 90.6% |
| Hybrid R0 | +0.019 | [-0.149, +0.192] | 3.77 | 96.6% |

All self-play net_eppd CIs include zero — PASS. GBT variants bid higher (5.4
vs 4.0) and have lower make rates but still healthy (87–91%).

### 4.3 vs Hybrid R0 (Incumbent)

| Cell | Pooled Delta | CI | Suit | High | Low |
|------|-------------|-------|------|------|-----|
| A (OLS, N=1) | +0.165 | [+0.045, +0.286] | **-0.139** | +0.440 | +0.517 |
| B (OLS, N=20) | +0.139 | [+0.019, +0.263] | **-0.264** | +0.579 | +0.481 |
| C (GBT, N=1) | **+1.067** | [+0.925, +1.208] | **+1.112** | +1.462 | +0.719 |
| D (GBT, N=20) | **+1.111** | [+0.977, +1.251] | **+0.945** | +1.530 | +1.411 |

**Key finding:** Both OLS variants have negative suit deltas vs R0 (the suit
regression persists). Both GBT variants have strongly positive suit deltas.

### 4.4 Key Cross-Comparisons

| Comparison | Pooled | CI | Suit | High | Low |
|-----------|--------|-------|------|------|-----|
| B vs A (label effect, OLS) | -0.015 | [-0.141, +0.113] | -0.069 | +0.153 | -0.036 |
| C vs A (model effect, N=1) | +1.112 | [+0.962, +1.266] | +1.203 | +1.159 | +0.934 |
| D vs C (label effect, GBT) | +0.148 | [-0.015, +0.316] | -0.030 | +0.357 | +0.490 |
| **B vs C (labels > model?)** | **-1.206** | [-1.353, -1.060] | -1.517 | -1.096 | -0.704 |
| D vs B (GBT+N20 vs OLS+N20) | +1.378 | [+1.241, +1.515] | +1.436 | +1.367 | +1.247 |
| D vs A (full interaction) | +1.257 | [+1.114, +1.399] | +1.171 | +1.515 | +1.337 |

### 4.5 2×2 Effect Decomposition

| Effect | Value | Interpretation |
|--------|-------|---------------|
| Cell A (OLS, N=1) | +0.165 | Baseline |
| Cell B (OLS, N=20) | +0.139 | |
| Cell C (GBT, N=1) | +1.067 | |
| Cell D (GBT, N=20) | +1.111 | |
| **Label effect (OLS)**: B−A | **-0.026** | Multi-rollout labels do NOT help OLS gameplay |
| **Label effect (GBT)**: D−C | **+0.044** | Marginal benefit for GBT (CI spans zero) |
| **Model effect (N=1)**: C−A | **+0.902** | GBT massively outperforms OLS on same labels |
| **Model effect (N=20)**: D−B | **+0.972** | GBT advantage even larger with better labels |
| Interaction | +0.069 | Small positive interaction (GBT exploits better labels slightly more) |

### 4.6 Behavioral Profiles

| Cell | avg_bid | make_rate |
|------|---------|-----------|
| A (OLS, N=1) | 3.82 | 95.3% |
| B (OLS, N=20) | 3.82 | 95.2% |
| C (GBT, N=1) | 4.98 | 92.7% |
| D (GBT, N=20) | 4.86 | 93.9% |
| Hybrid R0 | 3.77 | 96.6% |

OLS variants bid identically to R0 (avg_bid ~3.8–4.0) — they can't distinguish
enough to bid aggressively. GBT variants bid ~5.0 with 87–94% make rates.

## 5. Interpretation

### 5.1 The R²–Gameplay Paradox

Multi-rollout labels improve R² by +0.14 (OLS suit) but produce **zero gameplay
benefit** for OLS (B vs A: -0.015, CI spans zero). Meanwhile, GBT on the same
N=1 noisy labels outperforms by +0.902.

**Explanation:** OLS's linear decision boundary cannot exploit the smoother
labels. Even with denoised targets, OLS still predicts intermediate values at
the make/set boundary where the optimal decision requires a nonlinear threshold.
GBT finds this threshold directly from the data, regardless of label noise.

### 5.2 H15 CONFIRMED: Model Capacity > Label Quality

The critical B vs C comparison is decisive: multi-rollout OLS (B) loses to
single-rollout GBT (C) by **-1.206** net_eppd. The model effect (C−A = +0.902)
dwarfs the label effect (B−A = -0.026) by a factor of **~35×**.

This answers the question posed in the forward plan: **labels are NOT more
important than model capacity.** The suit regression is fundamentally a
model-capacity problem, not a label-quality problem.

### 5.3 Suit Regression Analysis

OLS suit delta vs R0 is *worse* with multi-rollout labels (-0.264 vs -0.139).
This makes sense: smoother labels center OLS predictions even more tightly
around the mean, reducing the variance that occasionally pushes OLS predictions
past the implicit make/set threshold. GBT resolves suit completely (C: +1.112,
D: +0.945).

### 5.4 Winner Identification

**Cell D (GBT, N=20)** is the best candidate:
- Highest pooled delta vs R0: +1.111 [+0.977, +1.251]
- Suit regression resolved: +0.945
- All contract types positive
- Best make rate among GBT variants: 93.9%
- Slightly lower avg_bid than Cell C (4.86 vs 5.44) with higher make rate

However, Cell C (GBT, N=1) is nearly as good (+1.067) and doesn't require
the expensive N=20 dataset generation. The label effect on GBT (D−C = +0.044)
is not statistically significant at QUICK scale.

## 6. Gate Checks

| Gate | Criterion | Result | Status |
|------|-----------|--------|--------|
| G1 | Best candidate pooled CI_low > 0 | +0.977 > 0 | **PASS** |
| G2 | Best candidate suit delta > -0.092 | +0.945 > -0.092 | **PASS** |
| G3 | At least one candidate suit > 0 | C: +1.112, D: +0.945 | **PASS** |

All three gates PASS.

## 7. Recommendations

1. **Advance Cell D (GBT, N=20) to Phase 2 (FULL validation)** as the primary
   candidate, with Cell C (GBT, N=1) as the fallback if N=20 generation cost
   at FULL scale is prohibitive.

2. **Label quality is a secondary lever.** For FULL-scale validation, N=1
   labels are likely sufficient given the marginal GBT improvement from
   multi-rollout (+0.044, not significant). This avoids the 20× generation
   cost at FULL scale (50,000 deals × 20 would require ~1M simulations per
   action).

3. **OLS is not viable for the action-value bidder.** Multi-rollout labels
   cannot rescue OLS from the suit regression. H12 is supported: the bimodal
   make/set target requires nonlinear modeling.

4. **Update H12 status to SUPPORTED** — OLS suit regression persists regardless
   of label quality, confirming it's a model-capacity issue.

## 8. Provenance

| Item | Value |
|------|-------|
| Seed | 42 |
| N deals (dataset) | 2,500 per dataset |
| N deals (H2H) | 2,500 per matchup |
| N=20 dataset | `data/runs/av_quick_n20_42/datasets/action_value.parquet` |
| N=1 dataset | `data/runs/action_value_quick_42/datasets/action_value.parquet` |
| Cell A artifact | `data/runs/phase1a_cell_a_ols_n1/action_value_full.json` |
| Cell B artifact | `data/runs/phase1a_cell_b_ols_n20/action_value_full.json` |
| Cell C artifact | `data/runs/phase1a_cell_c_gbt_n1/action_value_gbt.json` |
| Cell D artifact | `data/runs/phase1a_cell_d_gbt_n20/action_value_gbt.json` |
| H2H run ID | `phase1a_model_label_matrix_h2h_42_20260312_144219` |
| Continuation artifact | `data/artifacts/arc_d/r0/hybrid_r0_full.json` |
| git_sha | (see run metadata) |

### Reproduction Commands

```bash
# Generate N=20 dataset (~100 min)
uv run python scripts/internal/generate_action_value_dataset.py \
  --seed 42 --n-deals 2500 --n-opponent-samples 20 \
  --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json \
  --output-dir data/runs/av_quick_n20_42

# Train 4 models
for cell_dir model dataset in \
  "phase1a_cell_a_ols_n1 ols action_value_quick_42" \
  "phase1a_cell_b_ols_n20 ols av_quick_n20_42" \
  "phase1a_cell_c_gbt_n1 gbt action_value_quick_42" \
  "phase1a_cell_d_gbt_n20 gbt av_quick_n20_42"; do
  uv run python scripts/internal/train_action_value.py \
    --seed 42 --model-class $model --skip-validation \
    --dataset data/runs/$dataset/datasets/action_value.parquet \
    --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json \
    --output-dir data/runs/$cell_dir
done

# Run H2H battery (~6 min)
uv run python experiments/run_experiment.py \
  --config data/runs/phase1a_h2h/h2h_config.yaml --seed 42

# Analyze results
uv run python scripts/internal/analyze_phase1a_matrix.py \
  --run-dir data/runs/phase1a_model_label_matrix_h2h_42_20260312_144219 \
  --seed 42
```
