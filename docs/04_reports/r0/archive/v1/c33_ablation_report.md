# C33 Ablation: Gaussian EV Wrapper Effect

> **⚠ SUPERSEDED** — This is the v1 version, archived for reference.
> The current version is at [`../05_c33_ablation_report.md`](../05_c33_ablation_report.md).
> See [README.md](README.md) for the v1→v2 delta summary.

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

**Bid rate definition:** `bid_rate = hands_with_bids / deals_total`
(evaluator.py:326). In H2H matchups, this is the *competitive* bid rate --
the fraction of deals where a bidder wins the contested auction. It is NOT
the intrinsic bid rate, which measures how often the bidder would bid in
uncontested self-play.

For context:

| Context | Bidder | Bid Rate | Source |
|---------|--------|----------|--------|
| Comparator self-play (uncontested, vs Glutton) | hybrid_olsa | 19.7% | [comparator_rankings.md](comparator_rankings.md) v4 |
| C33 H2H (contested auction, vs olsa) | hybrid_olsa | 16.2% | This report |
| C33 H2H (contested auction, vs hybrid_olsa) | olsa | 83.8% | This report |

The 3.5pp gap between intrinsic (19.7%) and competitive (16.2%) bid rates
reflects auction interaction: olsa outbids hybrid_olsa in some deals where
both would bid, because olsa has no EV threshold and bids more aggressively.
The much larger gap between hybrid_olsa (16.2%) and olsa (83.8%) reflects
the core architectural difference: the EV wrapper causes hybrid_olsa to pass
on hands where olsa's floor-based rule would bid.

## 3. Architecture Comparison

### 3.1 Bid/Pass Decision Mechanism

Both bidders share identical OLS regression coefficients from `hybrid_r0.json`.
The OLS model predicts mu (expected tricks_won) for each of the six candidate
contracts (4 suits + HIGH + LOW). Both use `floor(mu)` to determine bid amount.
The only difference is the decision layer that determines whether to bid or
pass.

**OLSa (floor-based threshold).** OLSa bids whenever `floor(mu) >= 1` and
the bid exceeds the current high bid (bidding.py:751). It places every hand
where the OLS model predicts at least 1 trick for some contract. No
consideration of prediction uncertainty or expected value. This results in
~100% bid rate in self-play (comparator), as most hands predict at least 1
trick for some contract.

**HybridOLSa (Gaussian EV wrapper).** HybridOLSa models the full distribution
of tricks via the residual variance sigma from training. For each candidate bid
(bidding.py:910-952):

- Applies a continuity correction: `threshold = bid_n - 0.5`
- Computes z-score: `z = (threshold - mu) / sigma` (capped at +/-6.0)
- Computes `P(make) = 1 - Phi(z)` via the normal CDF
- Computes conditional expectations via truncated normal:
  `E[tricks|make] = mu + sigma * phi(z) / P(make)` and
  `E[tricks|set] = mu - sigma * phi(z) / P(set)`
- Computes net-differential payoffs:
  `make_ev = 2 * E[tricks|make] - 10` and
  `set_ev = E[tricks|set] - bid_n - 10`
- Computes `EV = P(make) * make_ev + P(set) * set_ev`
- Bids only if `EV > 0` (plus risk penalty, which is zero at R0)

The wrapper enables "selective restraint" -- declining bids that OLSa would
take when P(make) is low and the expected payoff is negative.

| Property | OLSa | HybridOLSa |
|----------|------|------------|
| Decision rule | `floor(mu) >= 1` | `EV > 0` |
| Uses sigma? | No | Yes (per-contract residual variance) |
| Accounts for uncertainty? | No | Yes (Gaussian model) |
| Bid rate (comparator, uncontested) | ~100% | 19.7% |
| Parameters beyond OLS | None | residual_variance, risk_lambda |

### 3.2 Risk Quantification (Analytical CVaR)

The Gaussian model also enables Monte Carlo CVaR-5% computation from the left
tail of the trick distribution (draws from `Normal(mu, sigma)`, takes mean of
bottom 5%). This provides per-hand downside risk before
play, penalizing high-variance hands even when EV is positive. At R0,
`risk_lambda = 0.0`, so the risk penalty does not affect bid decisions. CVaR
becomes active when `risk_lambda > 0` (planned for R3+).

Both the EV wrapper and CVaR computation inherit the Gaussian assumption over
a discrete, bounded [0, 10] support. The global sigma per contract family (no
heteroscedasticity modeling) likely underestimates tail risk near boundaries.
The continuity correction (`threshold = bid_n - 0.5`) partially mitigates the
discrete-continuous mismatch.

## 4. Results

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

#### Distributional Detail

The pooled delta masks the per-deal variance. Distributional statistics
for the cross-matchups (net_eppd_delta per deal):

| Matchup | net_eppd_delta | 95% CI | std | IQR | P5 | P95 |
|---------|----------------|--------|-----|-----|-----|------|
| hybrid_olsa vs olsa | +0.147 | [+0.014, +0.276] | 6.67 | 8.0 | -10.0 | +10.0 |
| olsa vs hybrid_olsa | -0.266 | [-0.399, -0.135] | 6.74 | 8.0 | -10.0 | +10.0 |

Note: The large per-deal variance (std ~6.7) reflects the high stochasticity
of individual deals. The wrapper effect (+0.21) is small relative to single-deal
noise but emerges reliably over 10,000 paired deals.

#### Team Breakout

Per-team metrics for each cross-matchup, showing that the wrapper's
advantage manifests through higher make rate, not raw trick volume:

| Matchup | Team | net_eppd | bid_rate | make_rate |
|---------|------|----------|----------|-----------|
| hybrid_olsa vs olsa | team0 (hybrid_olsa) | -3.18 | 16.2% | 89.4% |
| hybrid_olsa vs olsa | team1 (olsa) | -3.33 | 83.8% | 76.4% |
| olsa vs hybrid_olsa | team0 (olsa) | -3.40 | 83.5% | 76.1% |
| olsa vs hybrid_olsa | team1 (hybrid_olsa) | -3.13 | 16.5% | 89.8% |

In both seat arrangements, hybrid_olsa achieves a higher (less negative)
net_eppd despite bidding far less often. The higher make rate (89.4-89.8%
vs 76.1-76.4%) drives the advantage.

#### Per-Contract-Type Wrapper Effect

The pooled +0.21 net_eppd may hide contract-type variation. The wrapper's
selectivity differs by contract family because residual sigma differs
(from `hybrid_r0.json`):

| Contract Type | Residual Variance | Sigma | Restraint Implications |
|---------------|-------------------|-------|------------------------|
| suit | 2.339 | 1.530 | Lowest sigma → tightest P(make) estimates → most precise restraint. Dominant contract (98.3% of R0 bids), so most restraint zone hands are suit bids. |
| high | 2.877 | 1.696 | 11% wider sigma → more hands pushed below EV=0 threshold. Fewer observations in R0 data. |
| low | 2.898 | 1.702 | Widest sigma → broadest restraint zone. Fewest observations. |

Higher sigma widens the Gaussian uncertainty band around mu, pushing more
hands below the EV=0 threshold and into the restraint zone. Tier A
restraint rates and Tier B per-contract net_eppd breakdowns are in
notebook `57_c33_ablation_deep_dive` sections S4 and S6.

### Behavioral Profile

| Metric | hybrid_olsa (as A) | olsa (as A) |
|--------|-------------------|-------------|
| Bid rate | 16.2% | 83.8% |
| Make rate | 89.4% | 76.4% |

These are *competitive* bid rates from H2H (see section 2 for context on
bid rate semantics). See
[h2h_battery_analysis.md](h2h_battery_analysis.md) section 2 for the
full behavioral asymmetry analysis, and notebook `50_r0_matchups` for
pairwise heatmaps.

## 5. Decision Divergence Evidence

Evidence from notebook `57_c33_ablation_deep_dive` (R0-only analysis). The
replay engine reconstructs both bidders' decisions on the same hands using
the model artifact, then validates predictions against actual outcomes.

### 5.1 Aggregate EV Distributions

The EV distribution for OLSa-eligible hands (Tier A: all 4 seats,
`current_high_bid=0`) shows a substantial negative-EV tail that HybridOLSa
truncates. See notebook S3, Chart 3a for overlaid histograms faceted by
contract_type.

The key observation is that many hands where `floor(mu) >= 1` (OLSa would bid)
have EV <= 0 when the full Gaussian model is applied. These are hands where the
prediction uncertainty is high relative to the bid threshold, making the
expected payoff negative despite a nominally viable mu.

Chart 3b (mu vs P(make) scatterplot) shows the geometric decision boundary:
OLSa-only-bid hands (red) cluster in a region of moderate mu but low P(make),
exactly where the wrapper's restraint is most valuable.

### 5.2 Decision Divergence Counts

Across the replayed hands, the divergence categories (Tier A) are:

| Category | Description |
|----------|-------------|
| **Both bid** | OLSa and Hybrid both select this hand |
| **Both pass** | Neither bidder considers the hand viable |
| **OLSa-only bid** (restraint zone) | OLSa would bid, Hybrid passes (EV <= 0) |
| **Hybrid-only bid** | Hybrid bids but OLSa passes (expect ~0) |

By construction, `hybrid_bids <= olsa_bids` (the wrapper only removes
candidates, never adds them). The restraint zone represents hands where the
Gaussian model identifies negative expected value despite the floor-based
rule considering them viable.

See notebook S4 for exact counts and faceted breakdowns by contract_type.

### 5.3 P(make) Calibration

The Gaussian P(make) estimates are tested against actual make rates using
Tier B data (auction winner only). Hands are binned by predicted P(make),
and actual make rate is computed per bin with Wilson binomial confidence
intervals.

The calibration analysis uses ALL Tier B rows (no contract-match filter)
to avoid selection bias. Optional stratification by whether the replay's
best contract matches the actually-played contract reveals how auction
dynamics affect calibration quality.

See notebook S3.5 for calibration plots faceted by contract_type.

### 5.4 Per-Bid-Level Restraint

The per-bid-level breakdown (Tier A) reveals whether the wrapper mostly
filters marginal low bids (low-risk restraint) or prevents catastrophic
high bids (high-value restraint). The restraint rate generally increases
with bid level, since higher bids require higher P(make) to achieve
positive EV.

See notebook S4, per-bid-level table.

### 5.5 Worked Example

A single hand from the restraint zone illustrates the mechanism. The worked
example shows a hand where:

1. OLSa would bid (floor(mu) >= 1, exceeds high bid)
2. HybridOLSa passes (EV <= 0 after Gaussian analysis)
3. The actual outcome is a set (validating the wrapper's restraint)

The step-by-step EV computation in notebook S5 traces through mu prediction,
sigma lookup, z-score, P(make), truncated normal expectations, and the
net-differential payoff to show exactly why EV is negative.

### 5.6 Interpretation

The evidence confirms that the wrapper's value is **selective restraint**:
HybridOLSa identifies and avoids hands where the OLS prediction is
nominally above the bid threshold but the distributional model indicates
negative expected value. These are hands where OLSa bids and gets set more
often than it makes -- the wrapper prevents these losses.

The restraint zone has:
- Negative mean EV (by definition -- these are the hands Hybrid declines)
- Higher set rate than the both-bid zone (Tier B validation)
- Lower mean tricks won than both-bid hands (Tier B validation)

This provides direct empirical support for the +0.21 net_eppd advantage
reported in section 4.

## 6. Interpretation

The Gaussian CDF wrapper adds statistically significant value, but the
mechanism is **selective restraint** rather than superior prediction:

1. **hybrid_olsa declines ~84% of bids** where its P(make) estimate is below
   the EV threshold. When it does bid, it makes 89.4% of contracts vs olsa's
   76.4%.

2. **The wrapper avoids -EV contracts** rather than finding +EV ones the floor
   misses. Both bidders use the same trick predictions (section 3); the
   difference is entirely in the bid/pass decision boundary.

3. **The effect is modest** (+0.21 net_eppd). For context, the gap between
   hybrid_olsa and modeloespecifico is +1.132 net_eppd in single-seat comparator
   ([comparator_rankings.md](comparator_rankings.md) v4). The wrapper effect is
   about one-fifth of the gap to the domain-expert ceiling.

4. **Asymmetric deltas** (+0.147 vs -0.266) are expected in H2H with
   seat-swapping. When hybrid_olsa is bidder A, it yields the auction to olsa
   in most deals, so its advantage is compressed. When olsa is bidder A against
   hybrid_olsa as B, the effect is amplified.

5. **Competitive vs intrinsic bid rates:** The 16.2% competitive bid rate
   understates hybrid_olsa's intrinsic propensity (19.7% in uncontested
   self-play). The gap reflects auction interaction -- olsa's aggressive
   bidding captures deals that hybrid_olsa would also bid on. See section 2
   for the full bid rate disambiguation.

Section 5 provides direct empirical evidence for the restraint mechanism,
including EV distribution analysis, P(make) calibration, per-bid-level
breakdown, and a worked example confirming the wrapper's value.

## 7. Impact & Decisions

- **Architecture validated:** The Gaussian EV wrapper is worth maintaining
  through R1+. Removing it would sacrifice +0.21 net_eppd with no offsetting
  benefit.

- **Gate threshold context:** The delta_floor for R1 promotion is 0.180
  (see [r0_promotion_report.md](r0_promotion_report.md)). The wrapper effect
  (+0.21) would *barely* clear this bar, meaning an R1 challenger needs to
  show improvement comparable to the entire wrapper contribution to promote.

- **No action required:** This ablation confirms existing design, not a change
  proposal.

## 8. Arc Context

```
R0 training (#396)
  |
  +---> C33 ablation (this report)
  |       validates wrapper architecture
  |
  +---> Comparator battery v4 (comparator_rankings.md)
  |       ranks all 7 bidders (single-seat, GluttonStrategy)
  |
  +---> H2H battery (h2h_battery_analysis.md)
  |       competitive ordering + threshold calibration
  |
  +---> R1 training cycle (PR-R1a, next)
```

## 9. Provenance

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

## 10. Reproduction

```bash
# C33 ablation (4 matchups, 10k paired deals each)
uv run python experiments/run_experiment.py --seed 42 \
  --config experiments/configs/arc_d_r0_c33_ablation.yaml

# Parse results into JSON artifact.
# The C33 ablation uses a 2-bidder roster (hybrid_olsa, olsa), not the
# default 7-bidder roster. Create a roster file matching DEFAULT_ROSTER
# format for these two bidders:
cat > /tmp/c33_roster.json <<'ROSTER'
[
  {"name": "hybrid_olsa", "class_name": "HybridOLSaBidder",
   "params": {"artifact_path": "data/artifacts/arc_d/r0/hybrid_r0.json"}},
  {"name": "olsa", "class_name": "OLSaBidder",
   "params": {"artifact_path": "data/artifacts/arc_d/r0/hybrid_r0.json"}}
]
ROSTER
PYTHONPATH=src uv run python scripts/internal/run_arc_d_h2h_battery.py \
  --mode QUICK --seed 42 --n-per 10000 \
  --roster /tmp/c33_roster.json \
  --parse-run data/runs/arc_d_r0_c33_ablation_42_20260225_170036 \
  --output data/artifacts/arc_d/r0/c33_ablation_results.json
```
