# C33 Ablation: Gaussian EV Wrapper Effect

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0 (baseline)
**Date:** 2026-02-25
**Purpose:** Isolate the value of the Gaussian CDF decision layer vs floor-based threshold

---

## 1. Motivation

The hybrid_olsa bidder uses an analytical P(make) computation via normal CDF
(the "Gaussian EV wrapper") to decide whether to bid. The alternative is a
simpler floor-based threshold on the OLS predicted tricks. Both approaches use
identical regression coefficients from the same trained model
(`hybrid_r0.json`). This ablation isolates the wrapper's contribution.

The result informs two decisions: (1) whether the Gaussian wrapper architecture
is worth maintaining through future rungs, and (2) what magnitude of
improvement the wrapper provides as context for the R1 gate threshold
(delta_floor = 0.180).

## 2. Methodology

**Design:** 4 H2H matchups using paired deals with seat-swapping:

| Matchup | Bidder A | Bidder B | Purpose |
|---------|----------|----------|---------|
| 1 | hybrid_olsa | hybrid_olsa | Self-play sanity |
| 2 | olsa | olsa | Self-play sanity |
| 3 | hybrid_olsa | olsa | Cross-matchup |
| 4 | olsa | hybrid_olsa | Cross-matchup (seat-swapped) |

- **Deals:** 10,000 paired deals per matchup (40,000 total)
- **Seed:** 42
- **Statistical method:** Bootstrap 95% CIs (10,000 resamples)
- **Config:** `experiments/configs/arc_d_r0_c33_ablation.yaml`
- **Metric:** net_eppd_delta (bidder A net points minus bidder B net points,
  per deal)

**Bidder definitions:**

| Bidder | Artifact | Decision Layer | Features |
|--------|----------|----------------|----------|
| hybrid_olsa | hybrid_r0.json | Gaussian CDF P(make) | 3 constrained |
| olsa | hybrid_r0.json | Floor-based threshold | 3 constrained |

Both bidders share identical OLS regression coefficients. The only difference
is the bid/pass decision mechanism.

## 3. Results

### Self-Play Sanity

| Matchup | net_eppd_delta | 95% CI | Spans zero? |
|---------|----------------|--------|-------------|
| hybrid_olsa self-play | -0.019 | [-0.108, +0.070] | Yes |
| olsa self-play | -0.017 | [-0.156, +0.122] | Yes |

Both self-play cells produce deltas near zero with CIs spanning zero,
confirming the paired-deal design is unbiased.

### Cross-Matchup Results

| Matchup | net_eppd_delta | 95% CI | Significant? |
|---------|----------------|--------|--------------|
| hybrid_olsa vs olsa | **+0.147** | **[+0.014, +0.276]** | **Yes** |
| olsa vs hybrid_olsa | **-0.266** | **[-0.399, -0.135]** | **Yes** |

Both cross-matchup CIs exclude zero in the same direction: hybrid_olsa
outperforms olsa.

**Pooled wrapper effect:** +0.21 net_eppd (average of |0.147| and |0.266|).

### Behavioral Profile

| Metric | hybrid_olsa (as A) | olsa (as A) |
|--------|-------------------|-------------|
| Bid rate | 16.2% | 83.8% |
| Make rate | 89.4% | 76.4% |

See [h2h_battery_analysis.md](h2h_battery_analysis.md) section 2 for the
full behavioral asymmetry analysis, and notebook `50_r0_matchups` for
pairwise heatmaps.

## 4. Interpretation

The Gaussian CDF wrapper adds statistically significant value, but the
mechanism is **selective restraint** rather than superior prediction:

1. **hybrid_olsa declines ~84% of bids** where its P(make) estimate is below
   the EV threshold. When it does bid, it makes 89.4% of contracts vs olsa's
   76.4%.

2. **The wrapper avoids -EV contracts** rather than finding +EV ones the floor
   misses. Both bidders use the same trick predictions; the difference is
   entirely in the bid/pass decision boundary.

3. **The effect is modest** (+0.21 net_eppd). For context, the gap between
   hybrid_olsa and modeloespecifico is +0.62 net_eppd in self-play
   ([comparator_rankings.md](comparator_rankings.md)). The wrapper effect is
   about one-third of the gap to the domain-expert ceiling.

4. **Asymmetric deltas** (+0.147 vs -0.266) are expected in H2H with
   seat-swapping. When hybrid_olsa is bidder A, it yields the auction to olsa
   in most deals, so its advantage is compressed. When olsa is bidder A against
   hybrid_olsa as B, the effect is amplified.

## 5. Impact & Decisions

- **Architecture validated:** The Gaussian EV wrapper is worth maintaining
  through R1+. Removing it would sacrifice +0.21 net_eppd with no offsetting
  benefit.

- **Gate threshold context:** The delta_floor for R1 promotion is 0.180
  (see [r0_promotion_report.md](r0_promotion_report.md)). The wrapper effect
  (+0.21) would *barely* clear this bar, meaning an R1 challenger needs to
  show improvement comparable to the entire wrapper contribution to promote.

- **No action required:** This ablation confirms existing design, not a change
  proposal.

## 6. Arc Context

```
R0 training (#396)
  |
  +---> C33 ablation (this report)
  |       validates wrapper architecture
  |
  +---> Comparator battery v2 (comparator_rankings.md)
  |       ranks all 7 bidders in self-play
  |
  +---> H2H battery (h2h_battery_analysis.md)
  |       competitive ordering + threshold calibration
  |
  +---> R1 training cycle (PR-R1a, next)
```

## 7. Provenance

| Item | Value |
|------|-------|
| gate_status | PROMOTED (R0 overall; this ablation is informational) |
| Artifact | data/artifacts/arc_d/r0/c33_ablation_results.json |
| OLSa model | data/artifacts/arc_d/r0/hybrid_r0.json |
| Git SHA | e3a82e72466f852618b2a0b14a1be577c92c2b7a |
| Seed | 42 |
| n_deals | 40,000 (4 matchups x 10,000) |
| Schema | h2h_battery_v1 |
| Run ID | arc_d_r0_c33_ablation_42_20260225_170036 |

## 8. Reproduction

```bash
# C33 ablation (4 matchups, 10k paired deals each)
uv run python experiments/run_experiment.py --seed 42 \
  --config experiments/configs/arc_d_r0_c33_ablation.yaml

# Parse results into JSON artifact
PYTHONPATH=src uv run python scripts/internal/run_arc_d_h2h_battery.py \
  --parse-run data/runs/arc_d_r0_c33_ablation_42_20260225_170036 \
  --output data/artifacts/arc_d/r0/c33_ablation_results.json
```
