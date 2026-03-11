# Experiment Ledger — R1 through R1.5-v2

**Companion to:** [post_r1_retro.md](post_r1_retro.md)
**Last updated:** 2026-03-10

## Legend

| Field | Description |
|-------|-------------|
| **ID** | Sequential experiment identifier |
| **Phase** | R0v2, R1, R1.5-v1, R1.5-v2 |
| **Question** | The research question the experiment addresses |
| **Intervention** | What was changed or measured |
| **Metric** | Primary outcome metric |
| **Result** | Quantitative finding |
| **Confidence** | Statistical confidence (CI, p-value, or analytical proof) |
| **Verdict** | Decisive or Suggestive |
| **PR(s)** | Source PR number(s) |
| **Hypothesis** | Which hypothesis from the ledger this informs |

## R0 Canonical v2 Finalization

| ID | Question | Intervention | Metric | Result | Confidence | Verdict | PR(s) | Hypothesis |
|----|----------|-------------|--------|--------|------------|---------|-------|------------|
| E01 | Does risk_lambda > 0 help in H2H? | Lambda sweep: self-play + H2H at λ ∈ {0.0, 0.5, 1.0, 2.0} | net_eppd | Self-play +0.884 at λ=0.5 reversed to -1.15 in H2H | CI excludes 0 | Decisive | #500, #504 | — |
| E02 | Does pass_threshold > 0 help? | Threshold sweep: t ∈ {0.0, 0.25, 0.50, 0.75, 1.0} | net_eppd | Monotonic decline with increasing threshold | Significant | Decisive | #493, #509 | — |
| E03 | Does feature normalizer improve bidding? | Normalizer offline screen (Track E) | net_eppd | Accuracy +4% but net_eppd -0.269 | Significant | Decisive | #507, #508 | — |

## R1 Training Cycle

| ID | Question | Intervention | Metric | Result | Confidence | Verdict | PR(s) | Hypothesis |
|----|----------|-------------|--------|--------|------------|---------|-------|------------|
| E04 | Do partner features improve trick prediction? | Added 3 partner features to R0 pipeline | suit R² | +0.40 (0.25 → 0.63) | — | Decisive | #529, #532 | H1 (supports), H8 (later refutes) |
| E05 | Does improved R² translate to better gameplay? | R1 vs R0 H2H battery (3-seed, QUICK) | net_eppd | -0.348 overall, -0.76 suit | CI [-0.99, -0.53] | Decisive | #537 | H1 (confirms mismatch), H2 (supports) |
| E06 | Is there a code bug causing R1 regression? | Investigation F: full bug audit of training/inference | Bug count | 0 bugs found | N/A | Decisive | #543 | — |
| E07 | Is R1 regression caused by weight instability? | Investigation C: zero-out ablation of partner features | R² stability | H7 weight instability confirmed but not root cause | — | Suggestive | #546 | — |
| E08 | Does H10 bid-level search degeneracy exist? | Analytical proof of EV monotonicity | Mathematical | EV non-increasing in bid_n for sigma > 0, proven | 101 parametric tests | Decisive | #552 | H2 (confirms) |
| E09 | Can bid_bonus fix the decision layer? | bid_bonus sweep: {0.0, 0.25, 0.50, 0.75, 1.0} | net_eppd | bonus=0.25: +0.407 overall, but suit -0.456 persists | Significant | Decisive | #554 | H2 (confirms bottleneck, not sole cause) |
| E10 | How do R1 variants rank in comparator? | 6-bidder dual-seat comparator, n=5,000 | net_eppd ranking | R0 variants rank 1-2, R1 variants 3-4 (statistically tied) | Bootstrap CIs | Suggestive | #558 | H1 (supports) |
| E11 | Is ModeloEspecifico R1 viable? | ME_r1 with hand-coded partner weights | net_eppd | -10.49 (catastrophic) | — | Decisive | #536 | H8 (informs — naive weights destructive) |

## R1.5 v1 Pipeline

| ID | Question | Intervention | Metric | Result | Confidence | Verdict | PR(s) | Hypothesis |
|----|----------|-------------|--------|--------|------------|---------|-------|------------|
| E12 | Can AV models predict net_points from hand features? | OLS per-contract training on counterfactual data | R² | suit=0.565, high=0.533, low=0.514, pass=0.046 | — | Decisive | #567 | — |
| E13 | Does AV v1 rank actions correctly offline? | Gate X3: top-1 accuracy vs oracle | top-1 accuracy | 26.6% (below 40% threshold), but 84.6% pairwise accuracy | — | Suggestive | #572 | — (gate mis-specified) |
| E14 | Is AV v1 behaviorally stable? | 3-seed gameplay screen | WR, pass rate, eppd | WR 49.9-51.1%, pass 0.007%, eppd 4.75+ | 3 seeds | Decisive | #576 | — |
| E15 | Does AV v1 beat R0 in QUICK H2H? | 3-bidder H2H, n=2,500 | net_eppd | +0.165 vs HO_full R0 | Rotation CIs exclude 0 | Decisive | #577 | H1 (supports fix) |
| E16 | Does AV v1 beat R0 at FULL scale? | 3-bidder H2H, n=50,000 | net_eppd | +0.152, CI [+0.124, +0.180] | Bootstrap CI | Decisive | #582 | H1 (confirms) |
| E17 | Is the improvement uniform across contracts? | Per-contract faceting of FULL H2H | per-contract net_eppd | Suit -0.142, High +0.430, Low +0.495 | CIs exclude 0 for all | Decisive | #582 | H5 (informs), H12 (supports) |
| E18 | What is the partner feature contribution? | R0_full vs R0 in FULL H2H | net_eppd | +0.028, CI [+0.002, +0.055] | Bootstrap CI | Suggestive | #582 | H3 (supports) |

## R1.5-v2 Diagnostics

| ID | Question | Intervention | Metric | Result | Confidence | Verdict | PR(s) | Hypothesis |
|----|----------|-------------|--------|--------|------------|---------|-------|------------|
| E19 | Do extra features (39→52) explain the improvement? | Cell A: R0 features on net_points target, same data | R² delta | < 0.005 for all contracts | — | Decisive | #590, #599 | H6 (refutes) |
| E20 | Does AV architecture work with tricks_won? | Cell B': AV architecture + tricks_won target + H2H | net_eppd, behavior | Bids 10 every hand, 1% make rate, -13.7 net_eppd vs AV v1 | — | Decisive | #590, #599 | H1 (confirms), H4 (confirms) |
| E21 | Does counterfactual data help R0 models? | Option A: R0 sparse OLS on counterfactual data | suit R² | 0.084 (vs 0.223 on bidless) | — | Decisive | #599 | H9 (refutes) |
| E22 | Does declare/defend split improve R²? | Separate OLS per regime, composite R² | R² delta | +0.01 (gate threshold >0.05). Defend R²≈0. | — | Decisive | #599 | H11 (weakens) |
| E23 | Are residuals bimodal? | GMM BIC comparison (1-component vs 2-component) | delta_BIC | Suit=4,081, High=1,469, Low=1,286 (all strong) | — | Decisive | #591, #595 | H12 (supports) |
| E24 | Are partner features essential for AV v1? | Zero-mask training + H2H (no-partner vs R0, vs AV v1) | net_eppd | No-partner vs R0: -0.492. AV v1 vs R0: +0.224. Pass R²: 0.046→0.005. | — | Decisive | #602 | H3 (confirms), H10 (refutes) |
| E25 | Do interaction terms fix suit? | 3 terms (bower×trump, trump², bowers²) + H2H | R² delta, net_eppd | R² delta < 0.001, H2H +0.002 (noise) | — | Decisive | #603 | H7 (refutes) |

## Provenance

| Item | Value |
|------|-------|
| gate_status | N/A — ledger artifact, not a gate |
| Total experiments | 25 |
| Decisive experiments | 18 |
| Suggestive experiments | 4 |
| Not classified | 3 (E01-E03 are R0v2 finalization, not hypothesis-testing) |
| analysis_base_sha | f74ff62 |
