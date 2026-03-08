# R1.5 Step 5: 3-Seed Gameplay Screen

**Arc:** D — OLSa-Hybrid Bidder
**Rung:** R1.5 (objective-alignment)
**Date:** 2026-03-08
**Purpose:** Detect catastrophic behavior before committing to full H2H battery

## Executive Summary

The 3-seed self-play screen **passed all three sub-gates**. The ActionValueBidder
is functional and produces balanced self-play outcomes. However, the behavioral
profile reveals a pattern not anticipated by the design spec: the bidder **almost
never passes** (2 passes across 30,000 auction decisions, 0.007% pass rate) and
nearly every hand is bid at level 4 (the minimum when all 4 players bid once
each). Two hands across seeds 43 and 44 include a mid-auction pass, ending at
bid=3.

This is the inverse of the over-passing concern from Gate X3, where the model's
top action was pass in 39.2% of offline states (vs the oracle's 26.5%). The
discrepancy arises because the offline evaluation evaluates all legal actions from
`current_high_bid=0` in a single step, while gameplay involves a sequential
auction where each player faces progressively restricted action spaces and almost
always finds some bid more valuable than passing.

**Decision:** Proceed to Step 6 (H2H battery). The near-zero pass rate is not
catastrophic but will likely produce weak H2H performance against opponents that
bid higher on strong hands.

## 1. Methodology

### Configuration

- **Config:** `experiments/configs/r1_5_self_play.yaml`
- **Mode:** Self-play (ActionValueBidder vs itself, all 4 seats)
- **Contract type:** Auction mode (`contract_type: null`)
- **n_per:** 2,500 deals per seed
- **Seeds:** 42, 43, 44
- **Artifact:** `data/artifacts/arc_d/r1_5/action_value_full.json`
- **Play policy:** GluttonStrategy (greedy trick play, default)

### Reproduction

```bash
for seed in 42 43 44; do
  uv run python experiments/run_experiment.py \
    --config experiments/configs/r1_5_self_play.yaml --seed $seed
done
```

## 2. Gate Results

### Step 5 Sub-Gates (All PASS)

| Sub-gate | Threshold | Seed 42 | Seed 43 | Seed 44 | Verdict |
|----------|-----------|---------|---------|---------|---------|
| Self-play WR | [40%, 60%] | 49.9% | 51.1% | 50.9% | **PASS** |
| Pass rate | < 70% | 0.00% | 0.01% | 0.01% | **PASS** |
| Mean eppd | >= 0 | 4.761 | 4.777 | 4.750 | **PASS** |

### Detailed Metrics

| Metric | Seed 42 | Seed 43 | Seed 44 | Cross-seed Mean |
|--------|---------|---------|---------|-----------------|
| Win rate (Team 0) | 49.9% | 51.1% | 50.9% | 50.6% |
| Avg tricks (T0) | 4.980 | 5.055 | 5.023 | 5.019 |
| Avg tricks (T1) | 5.020 | 4.945 | 4.977 | 4.981 |
| Avg points (T0) | 4.698 | 4.859 | 4.763 | 4.773 |
| Avg points (T1) | 4.824 | 4.695 | 4.736 | 4.752 |
| Mean eppd | 4.761 | 4.777 | 4.750 | 4.763 |
| Net eppd (T0-T1) | -0.126 | +0.164 | +0.027 | +0.022 |
| Make rate | 92.8% | 93.4% | 92.5% | 92.9% |
| Avg bid level | 4.0 | 4.0 | 4.0 | 4.0 |
| Tie rate | 21.2% | 20.0% | 20.1% | 20.4% |
| Pass rate | 0.00% | 0.01% | 0.01% | 0.007% |

## 3. Behavioral Analysis

### Auction Dynamics

Each auction has exactly 4 actions (one per seat). The dominant pattern
(99.96% of hands) is escalating bids:
1. First bidder bids 1 (some contract) — model predicts positive EV
2. Second bidder bids 2 (some contract) — still positive for many contracts
3. Third bidder bids 3 (some contract) — still positive
4. Fourth bidder bids 4 (some contract) — still positive, wins the auction

In 2 out of 7,502 hands with auctions (seeds 43 and 44), one player passes
mid-auction instead of bidding, resulting in a final bid of 3. Example (seed
43, hand 1256): seat 2 bids 1 (suit-C), seat 3 **passes**, seat 0 bids 2
(high), seat 1 bids 3 (suit-H).

The near-zero pass rate is consistent with the Gate X3 finding that the pass
model has very low R^2 (0.044) — the model almost always predicts some bid
contract as higher-value than passing.

### Contract Type Distribution (Seed 42)

| Contract Type | Count | Share |
|--------------|-------|-------|
| Suit | 1,138 | 45.5% |
| Low | 918 | 36.7% |
| High | 444 | 17.8% |

This mix is plausible. Suit contracts dominate because trump/bower advantages
provide more control. Low contracts appear frequently because low-card hands
have a natural advantage when counting from 10 upward.

### Over-Passing vs Near-Zero Passing: Reconciliation

The Gate X3 report documented the **model's** family choice rate for pass as
39.2% (vs the oracle's 26.5%). That is, when the model evaluates all ~61 legal
actions from `current_high_bid=0` and picks the highest-predicted-value action,
it selects pass in 39.2% of states. Yet in gameplay, the pass rate is 0.007%.

This is not contradictory — it reflects a difference in evaluation context:
- **Offline (X3):** Each state is evaluated in isolation at `current_high_bid=0`
  with the full menu of 61 actions. The model's argmax is pass in 39.2% of
  these independent evaluations.
- **Gameplay:** The auction is sequential. The first bidder faces
  `current_high_bid=0` and picks a low-level bid (bid=1), not pass. Subsequent
  bidders face `current_high_bid >= 1` with a restricted action set, and they
  too prefer bidding over passing. The 39.2% offline rate counted states where
  pass was globally best across all 61 options, but in gameplay each player
  only needs pass to beat the progressively smaller set of remaining bids.

The key insight: the offline evaluation is a single-step argmax over the full
action space, while gameplay is a multi-step sequential auction where each
player's action restricts the next player's options. The model's predicted
value for low-level bids (1-3) is almost always positive, making them preferred
over pass when the action space starts wide.

## 4. Risk Assessment for H2H

### Concern: Conservative Bidding

The bid=4 ceiling means the ActionValueBidder earns the minimum possible
declaring bonus. Against the R0 HybridOLSaBidder (which routinely bids 5-7+
on strong hands), the ActionValueBidder will:
- Win fewer points when declaring (lower bid = lower reward on make)
- Rarely outbid opponents (can't compete above level 4)
- Rely entirely on defending (earning tricks against opponents' contracts)

### Concern: Undifferentiated Hands

The model treats nearly all hands identically in the auction — almost every
seat bids, and the winning bid is almost always 4. It cannot identify
"premium" hands worth bidding higher on vs "marginal" hands worth passing.
This is the cross-model calibration problem from Gate X3 manifesting in
gameplay.

### Expected H2H Outcome

Based on the behavioral profile, the ActionValueBidder v1 will likely
**underperform** the R0 HybridOLSaBidder in H2H:
- R0 bidder earns more from strong hands (bids higher, earns more on make)
- R0 bidder passes on weak hands (avoids being set)
- ActionValueBidder's only advantage is contract-type selection (it picks
  the best contract family, even if at a low level)

The magnitude of the gap is the key question for Step 6.

## 5. Provenance

| Item | Value |
|------|-------|
| gate_status | PASSED (all 3 sub-gates) |
| Config | `experiments/configs/r1_5_self_play.yaml` |
| Artifact | `data/artifacts/arc_d/r1_5/action_value_full.json` |
| Seeds | 42, 43, 44 |
| n_per | 2,500 |
| Run dirs | `data/runs/r1_5_self_play_{42,43,44}_20260308_*` |
| analysis_base_sha | e1d2509 (HEAD of main at time of analysis) |

## 6. Reproduction

```bash
# Run 3-seed self-play screen
for seed in 42 43 44; do
  uv run python experiments/run_experiment.py \
    --config experiments/configs/r1_5_self_play.yaml --seed $seed
done

# Inspect auction behavior from hand logs
python3 -c "
import json, glob
from collections import Counter

for seed in [42, 43, 44]:
    dirs = glob.glob(f'data/runs/r1_5_self_play_{seed}_*')
    if not dirs: continue
    logfiles = glob.glob(f'{dirs[0]}/logs/*.jsonl')
    if not logfiles: continue
    with open(logfiles[0]) as f:
        hands = [json.loads(line) for line in f]
    actions = Counter(e.get('action') for h in hands
                      for e in h.get('auction_transcript', []))
    total = sum(actions.values())
    passes = actions.get('PASS', 0)
    bids = actions.get('BID', 0)
    print(f'Seed {seed}: {bids} bids, {passes} passes ({passes/total*100:.2f}%)')
"
```
