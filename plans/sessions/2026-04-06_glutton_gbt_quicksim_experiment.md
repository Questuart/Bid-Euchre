# Glutton + GBT Quick-Sim Ablation — Experiment Design

**Lane:** analyst-d
**Branch:** `analyst/glutton-gbt-quicksim-experiment`
**Date:** 2026-04-06
**Status:** DESIGN — NO experiment runs, NO strategy code changes
**Delivery mode:** PR (plans + YAML configs are durable artifacts)

---

## 1. Executive Summary

### What this is
A pre-deployment ablation that isolates the individual contribution of four
proposed Glutton + GBT enhancements before any of them land in the hosted
browser game. Two are already merged but flag-gated; two are not yet built.
All four have been implicated by evidence (unit audit, live game logs, issue
triage) and all four are candidates for the next Bud Bot refresh. We do not
know which of them actually helps until we paired-test them on common deals.

### What it is not
This document is **design only**. It does not run experiments. It does not
implement the Claim 1 fix. It does not implement the GBT filter wrapper. It
specifies everything needed for the orchestrator to dispatch an
implementation packet (Claim 1 fix + `FilteredGBTBidder` wrapper) and then
run the two quick-sim configs below.

### Four enhancements under test

| ID | Name | Source | State |
|----|------|--------|-------|
| **Cash-A** | `cash_winners_on_lead` flag on Glutton | PR #2534 (merged) | Flag OFF by default in v0.8.0 |
| **Claim 1** | `_draw_trump_lead` sure-winner-first fallback | [cash_a_deep_audit.md §2.4](./2026-04-06_cash_a_deep_audit.md) | Not implemented |
| **GBT Enh A** | "Don't overbid as last bidder" filter | Issue #2149 (live game) | Not implemented |
| **GBT Enh B** | "Don't nudge partner's bid +1 in same suit" filter | Design proposal (this doc §8) | Not implemented |

### Headline recommendation
Run the two quick-sim configs on the same seed (42), the same n (5000 paired
deals per cell), and the same canonical scenario set (6 pre-declared for the
play-side contrast, 1 auction scenario for the bidder contrast). Total
compute budget ~5 minutes wall. Adoption gate is statistical significance
at 95% CI on paired bootstrap deltas, not visual inspection.

### Why a split matrix, not a single 5-cell run
The task packet specifies a 5-cell unified matrix. A unified matrix is not
physically realisable in a single experiment run because the four enhancements
live on two orthogonal axes:
- **Cash-A + Claim 1** are pure PLAY edits on `GluttonStrategy.play_card` /
  `_draw_trump_lead`. The cleanest contrast surface for them is bidless
  `mode: self_play` with `pair_deals: true` and pre-declared trump.
- **GBT Enhancements A + B** are pure BIDDING edits that wrap
  `GBTActionValueBidder.choose_bid`. They are completely inert in a bidless
  run because the bidder is never invoked.

Forcing both axes into one config either (a) inactivates the GBT filters or
(b) introduces bid-contract variance that muddies the Cash-A contrast. We
therefore split into two sub-matrices — **P** (play, 3 cells) and **B**
(bidding, 3 cells) — for 6 total cells on 2 configs. The mapping from task
matrix to sub-matrix is explicit in §2.

---

## 2. Experiment Matrix

### 2.1 Task matrix (as requested)

| Cell | Glutton `cash_winners_on_lead` | Claim 1 fix | GBT Enh A | GBT Enh B |
|------|:---:|:---:|:---:|:---:|
| **Baseline** | OFF | N/A | OFF | OFF |
| **C1** | ON | NOT APPLIED | OFF | OFF |
| **C2** | ON | APPLIED | OFF | OFF |
| **C3** | ON | APPLIED | ON | OFF |
| **C4** | ON | APPLIED | ON | ON |

### 2.2 Sub-matrix split

| Task cell | Sub-matrix cell | Config | Measured via |
|-----------|------|--------|--------------|
| Baseline | **P0** (`p0_baseline_flag_off`) | `glutton_gbt_ablation_play.yaml` | bidless, 6 pre-declared scenarios |
| C1 | **P1** (`p1_cash_a_buggy`) | `glutton_gbt_ablation_play.yaml` | bidless, 6 pre-declared scenarios |
| C2 | **P2** (`p2_cash_a_fixed`) | `glutton_gbt_ablation_play.yaml` | bidless, 6 pre-declared scenarios |
| C3 | **B1** (`b1_gbt_enh_a`) | `glutton_gbt_ablation_auction.yaml` | auction, `contract_type: null` |
| C4 | **B2** (`b2_gbt_enh_ab`) | `glutton_gbt_ablation_auction.yaml` | auction, `contract_type: null` |

The auction sub-matrix also contains **B0** (`b0_gbt_vanilla`), a raw GBT
baseline that is implicit in the task matrix (it is the "C2 with GBT turned
on but no filters" state). B0 is the ground for the B1/B2 deltas.

### 2.3 Contrasts we actually report on

| Contrast | Isolates | Primary metric | Expected direction |
|----------|----------|----------------|---------------------|
| **P1 − P0** | Cash-A flag flip on the buggy code (PR #2534 as-merged) | paired Δ `t0` (team 0 tricks / deal) | neutral-to-negative on some scenarios, positive on others — this is the contested measurement |
| **P2 − P1** | Claim 1 fix contribution (given Cash-A on) | paired Δ `t0` | non-negative; any loss is a red flag |
| **P2 − P0** | Combined Cash-A + Claim 1 effect vs current production | paired Δ `t0` | positive if we adopt Cash-A |
| **B1 − B0** | GBT Enhancement A contribution | paired Δ `net_points_t0` | positive if Enh A reduces overbid losses |
| **B2 − B1** | GBT Enhancement B additional contribution | paired Δ `net_points_t0` | non-negative; near-zero is acceptable |
| **B2 − B0** | Combined GBT filter effect | paired Δ `net_points_t0` | positive |

### 2.4 Compute budget

| Sub-matrix | Cells | Scenarios | n per cell per scenario | Hands | Est wall |
|------------|-------|-----------|-------------------------|-------|----------|
| P (play) | 3 | 6 | 5000 | 90,000 | ~20 s (bidless throughput ~5000/sec) |
| B (bidding) | 3 | 1 | 5000 | 15,000 | ~2.5 min (GBT auction throughput ~100/sec, arc_d_v2 r3 benchmarks) |
| **Total** | — | — | — | **105,000** | **~3 min** |

Well under the 60 min compute budget in the task packet. Budget headroom is
intentional — the orchestrator can double n to 10,000 if the first pass
lands close to the MDE without blowing the wall budget.

---

## 3. YAML Configs

### 3.1 `experiments/configs/glutton_gbt_ablation_play.yaml`
**Sub-matrix P.** 3 `GluttonIsolatedStrategy` cells, 6 pre-declared
scenarios, bidless `mode: self_play`, `pair_deals: true`, n=5000. Emits one
JSONL per cell under `data/runs/<run_id>/logs/<run_id>_<cell-name>.jsonl`.

Key parameters:
- `n_per: 5000` / `seed: 42` / `log_level: hand`
- Cells: `p0_baseline_flag_off`, `p1_cash_a_buggy`, `p2_cash_a_fixed`
- Scenarios: `suit_C`, `suit_D`, `suit_H`, `suit_S`, `high`, `low`
- Research-only runtime switch `draw_trump_lead_legacy` on
  `GluttonIsolatedStrategy` — `True` on P1, `False` on P0/P2

### 3.2 `experiments/configs/glutton_gbt_ablation_auction.yaml`
**Sub-matrix B.** 3 bidder cells, 1 auction scenario (`contract_type: null`),
single shared `GluttonStrategy` play strategy pinned to the Cash-A-fixed
state (`cash_winners_on_lead: true` after the Claim 1 fix lands), n=5000.
Emits one JSONL per cell.

Key parameters:
- `n_per: 5000` / `seed: 42` / `log_level: hand`
- Bidder cells: `b0_gbt_vanilla` (raw `GBTActionValueBidder`),
  `b1_gbt_enh_a` (`FilteredGBTBidder` with Enh A on),
  `b2_gbt_enh_ab` (`FilteredGBTBidder` with Enh A + Enh B on)
- Play strategy: `cash_a_fixed` (`GluttonStrategy` with Cash-A flag on)

Both configs ship in this PR with extensive header comments explaining
prerequisites, compute budget, and run command.

---

## 4. Runnable CLI Commands

### 4.1 Pre-flight: verify prerequisites are in place
Before running either config, the orchestrator should dispatch an
implementation packet that lands the following in a single PR (or two
sequential PRs — play fix and bidder wrapper can parallelise):

1. Claim 1 fix on `GluttonStrategy._draw_trump_lead` and
   `GluttonIsolatedStrategy._draw_trump_lead` per
   [cash_a_deep_audit.md §2.4](./2026-04-06_cash_a_deep_audit.md).
2. `GLUTTON_STRATEGY_VERSION = "0.8.1"` bump in
   `src/bid_euchre/strategy/greedy.py`.
3. Research-only `draw_trump_lead_legacy: bool = False` parameter on
   `GluttonIsolatedStrategy.__init__` ONLY. Explicitly documented as
   research-only, with a follow-up cleanup PR tracked to remove it after
   this ablation signs off. This flag must NOT be added to production
   `GluttonStrategy`.
4. `FilteredGBTBidder` class in `src/bid_euchre/strategy/bidding.py` per
   §7 and §8 of this report. Registered in
   `src/bid_euchre/experiments/config.py::BIDDER_CLASSES` and
   `REQUIRED_PARAMS`.
5. The GBT artifact at
   `data/artifacts/arc_d_v2/r3/training_artifact_gbt_av.json`. Local
   checkouts may ship the artifact at
   `web/models/training_artifact_gbt_av.json` instead — copy or symlink
   it into `data/artifacts/arc_d_v2/r3/` before running the auction
   config, or edit the three `artifact_path` params to point at the
   local path. (The canonical production path is what `web/config.py`
   resolves via `GBT_ARTIFACT`.)
6. Unit tests for the Claim 1 fix and for the
   `FilteredGBTBidder` filter predicates.
7. `make check-gated` green.

### 4.2 Play sub-matrix run (P0, P1, P2)
```bash
uv run python experiments/run_experiment.py \
  --config experiments/configs/glutton_gbt_ablation_play.yaml \
  --seed 42
```

Expected output directory:
```
data/runs/<run_id>/
  config.json
  metadata.json
  logs/
    <run_id>_p0_baseline_flag_off.jsonl
    <run_id>_p1_cash_a_buggy.jsonl
    <run_id>_p2_cash_a_fixed.jsonl
```

### 4.3 Auction sub-matrix run (B0, B1, B2)
```bash
uv run python experiments/run_experiment.py \
  --config experiments/configs/glutton_gbt_ablation_auction.yaml \
  --seed 42
```

Expected output directory:
```
data/runs/<run_id>/
  config.json
  metadata.json
  logs/
    <run_id>_b0_gbt_vanilla.jsonl
    <run_id>_b1_gbt_enh_a.jsonl
    <run_id>_b2_gbt_enh_ab.jsonl
```

### 4.4 Dry-run both configs (no compute cost)
Before either real run, validate YAML parse + strategy registration:
```bash
uv run python experiments/run_experiment.py --seed 42 --dry-run \
  --config experiments/configs/glutton_gbt_ablation_play.yaml
uv run python experiments/run_experiment.py --seed 42 --dry-run \
  --config experiments/configs/glutton_gbt_ablation_auction.yaml
```

---

## 5. Analysis Commands

### 5.1 Play sub-matrix — paired tricks deltas
The play contrasts are computed directly by
`src/bid_euchre/analysis/paired.py::compute_paired_deltas`, which keys on
`(deal_id, seed)` and computes `delta = comp_t0 - base_t0` per matched pair.
Bootstrap CI is computed by `src/bid_euchre/analysis/stats.py::bootstrap_ci`.

Inline analysis via `uv run python`:
```bash
PLAY_RUN=data/runs/<play_run_id>

uv run python - <<'PY'
from bid_euchre.analysis.paired import load_paired_data, compute_paired_deltas
from bid_euchre.analysis.stats import bootstrap_ci
import numpy as np

run_dir = "data/runs/<play_run_id>"  # replace with real id
strategies = ["p0_baseline_flag_off", "p1_cash_a_buggy", "p2_cash_a_fixed"]
data = load_paired_data(run_dir, strategies)

contrasts = [
    ("p0_baseline_flag_off", "p1_cash_a_buggy",  "P1 - P0 (Cash-A flag flip, buggy draw)"),
    ("p1_cash_a_buggy",      "p2_cash_a_fixed",  "P2 - P1 (Claim 1 fix on top of Cash-A)"),
    ("p0_baseline_flag_off", "p2_cash_a_fixed",  "P2 - P0 (combined)"),
]

for base, comp, label in contrasts:
    for scen in ["suit_C", "suit_D", "suit_H", "suit_S", "high", "low", None]:
        pd = compute_paired_deltas(data, base, comp, scenario=scen)
        if pd["n_matched"] == 0:
            continue
        deltas = np.array(pd["deltas"])
        mean, lo, hi = bootstrap_ci(deltas, statistic=np.mean,
                                     n_bootstrap=10000, seed=42)
        tag = scen or "ALL"
        sig = "*" if lo > 0 or hi < 0 else " "
        print(f"{label:55s} {tag:8s} n={pd['n_matched']:5d} "
              f"Δt0={mean:+.4f} [{lo:+.4f}, {hi:+.4f}] {sig}")
PY
```

### 5.2 Auction sub-matrix — paired net_points deltas
`compute_paired_deltas` only reports `t0` deltas, which is not enough for the
bidder contrast — bid accuracy shows up in **net points**, not raw tricks
(overbidding still wins tricks but loses set penalties). The auction analysis
must pull the `scores` field from the hand_end records directly. A small
ad-hoc script fits inside the design envelope:

```bash
AUCTION_RUN=data/runs/<auction_run_id>

uv run python - <<'PY'
import json, os, glob
import numpy as np
from bid_euchre.analysis.stats import bootstrap_ci

run_dir = "data/runs/<auction_run_id>"  # replace with real id
strategies = ["b0_gbt_vanilla", "b1_gbt_enh_a", "b2_gbt_enh_ab"]

def load_cell(strategy):
    recs = {}
    for path in glob.glob(os.path.join(run_dir, "logs", f"*{strategy}.jsonl")):
        with open(path) as f:
            for line in f:
                r = json.loads(line)
                if r.get("event") != "hand_end" or r.get("redeal_flag"):
                    continue
                key = (r["deal_id"], r.get("seed"))
                scores = r["scores"]  # [s0, s1, s2, s3]
                # Team 0 = seats 0, 2; Team 1 = seats 1, 3
                net0 = (scores[0] + scores[2]) - (scores[1] + scores[3])
                recs[key] = net0
    return recs

cells = {s: load_cell(s) for s in strategies}

contrasts = [
    ("b0_gbt_vanilla", "b1_gbt_enh_a", "B1 - B0 (Enh A only)"),
    ("b1_gbt_enh_a",   "b2_gbt_enh_ab", "B2 - B1 (Enh B additional)"),
    ("b0_gbt_vanilla", "b2_gbt_enh_ab", "B2 - B0 (combined Enh A+B)"),
]

for base, comp, label in contrasts:
    common = sorted(set(cells[base]) & set(cells[comp]))
    deltas = np.array([cells[comp][k] - cells[base][k] for k in common])
    mean, lo, hi = bootstrap_ci(deltas, statistic=np.mean,
                                 n_bootstrap=10000, seed=42)
    sig = "*" if lo > 0 or hi < 0 else " "
    print(f"{label:35s} n={len(deltas):5d} "
          f"Δnet0={mean:+.4f} [{lo:+.4f}, {hi:+.4f}] {sig}")
PY
```

### 5.3 Diagnostic: overbid / set rates on the auction cells
Useful as a secondary measure to confirm Enhancement A is doing the thing it
claims to do — reducing the overbid rate — and not just randomly shifting
net points.

```bash
uv run python - <<'PY'
import json, os, glob

run_dir = "data/runs/<auction_run_id>"  # replace with real id
for strategy in ["b0_gbt_vanilla", "b1_gbt_enh_a", "b2_gbt_enh_ab"]:
    n, n_set, n_last_bidder_bid = 0, 0, 0
    for path in glob.glob(os.path.join(run_dir, "logs", f"*{strategy}.jsonl")):
        with open(path) as f:
            for line in f:
                r = json.loads(line)
                if r.get("event") != "hand_end" or r.get("redeal_flag"):
                    continue
                n += 1
                if not r.get("made_bid", True):
                    n_set += 1
                # "Last bidder bid" heuristic: dealer seat appears in the
                # transcript with action=BID
                for entry in (r.get("auction_transcript") or []):
                    if entry.get("seat") == r.get("dealer_position") \
                            and entry.get("action") == "BID":
                        n_last_bidder_bid += 1
                        break
    print(f"{strategy:20s} n={n:5d} set_rate={n_set/n:.3f} "
          f"dealer_bid_rate={n_last_bidder_bid/n:.3f}")
PY
```

---

## 6. Acceptance Criteria

### 6.1 Quantitative gates

A change is **adopted** only if both of the following hold:

**Gate A — Positive paired bootstrap delta (required):**
- For the play sub-matrix (P2 − P0): 95% CI lower bound on mean Δt0 > 0 on
  the pooled sample across all 6 scenarios (n ≥ 29,000 after match filter).
- For the auction sub-matrix (B2 − B0): 95% CI lower bound on mean
  Δnet_points_t0 > 0 (n ≥ 4,800 after redeal filter).

**Gate B — No per-scenario regression beyond MDE (required):**
- For each of the 6 play scenarios, the 95% CI for P2 − P0 must not show a
  lower bound worse than −1 × MDE (i.e., we tolerate near-zero but not a
  clear scenario-local loss).
- For the auction sub-matrix, no per-trump breakdown required (auction
  scenario is a single contract_type=null cell).

### 6.2 MDE at n=5000

The minimum detectable effect is the 95% half-width of the paired bootstrap
delta CI divided by the square root of the sample size. We compute it
defensively from observed paired standard deviations, not from theoretical
assumptions:

| Sub-matrix | Metric | Paired SD (assumed, from prior runs) | SE at n=5000 | MDE (2×SE, 95% CI half-width) |
|------------|--------|--------------------------------------|--------------|-------------------------------|
| P (play) | Δt0 per deal | ~0.5 tricks | ~0.0071 | **~0.014 tricks/deal** |
| B (auction) | Δnet_points per deal | ~4 points | ~0.0566 | **~0.113 pts/deal** |

The P-side paired SD estimate is taken from the auction_play_strategy_sensitivity
runs on the same canonical scenario layout. The B-side paired SD is
conservatively padded relative to arc_d_v2 r3 bootstrap artifacts for
auction deltas on net_points.

**If the observed SD is materially larger than these estimates, the
orchestrator should double n to 10,000 before declaring a non-result — the
wall budget easily accommodates it.**

### 6.3 Qualitative gates

- **Sample size documented:** All reported deltas must cite the actual
  matched-pair n, not just the nominal 5000. `load_paired_data` drops
  all-pass redeal records, and on the auction side this is typically 3-6%
  of deals.
- **Per-scenario breakdown required for play sub-matrix:** A pooled-only
  result without per-scenario breakdown would mask the known interaction
  between Cash-A and specific trump suits documented in the cash_a_deep_audit
  report. The adoption decision must see the scenario breakdown.
- **Auction diagnostic required:** The overbid / set-rate diagnostic in §5.3
  must be reported alongside the net_points deltas. A positive net_points
  delta without a corresponding drop in set rate would be suspicious and
  trigger further investigation before adoption.

### 6.4 Reporting location

Results write to `plans/sessions/2026-04-06_glutton_gbt_quicksim_results.md`
(not this file — this file is design-only). The results report cites the run
ids, the actual matched-pair n, the bootstrap deltas with CIs, and the
go/no-go recommendation per enhancement. It is the artifact the orchestrator
uses to decide whether to ship Cash-A, Claim 1, Enh A, and Enh B.

---

## 7. GBT Enhancement A — "Don't Overbid as Last Bidder"

### 7.1 Motivation
Live game evidence from issue #2149: Bud Bot, sitting as the dealer and
therefore as the last bidder, had the action folded to it at a table state
where its team already had no obligation to bid. It bid **5 Spades**, took
4 tricks, got set, and lost a close game 36-35. The GBT model's action-value
estimate for "bid 5S" exceeded its pass value by a small margin, and without
a guard rail the model will take the raw argmax even when passing clearly
secures the win condition for the hand.

The live anecdote has not been reproduced in a controlled environment yet.
The purpose of this enhancement — and this ablation — is to measure whether
a simple last-seat filter materially reduces the overbid failure mode
without hurting the bidder's EV in normal auctions.

### 7.2 Precise spec

Hook location: `src/bid_euchre/strategy/bidding.py`, inside
`FilteredGBTBidder.choose_bid`, after the inner `GBTActionValueBidder`
returns a raw action.

Pseudocode:
```python
def choose_bid(self, obs: BiddingObservation) -> BidAction:
    raw = self._inner.choose_bid(obs)
    if raw.is_pass():
        return raw
    if obs.seat != obs.dealer_seat:
        # Not the last bidder -> filter inactive
        return raw
    if self._flag_a and _would_overbid_last(obs, raw):
        return BidAction.pass_bid()
    if self._flag_b and _would_nudge_partner(obs, raw):
        return BidAction.pass_bid()
    return raw
```

`_would_overbid_last(obs, raw)` — the Enhancement A predicate. The dealer
is strictly the last bidder in LOD order
(`player_idx = (dealer_index + offset) % 4` for offset 1..4, so offset=4
is the dealer — verified in `src/bid_euchre/sim/simulation.py` around
line 232). When the predicate runs, three things are true simultaneously:

1. We are the dealer (offset=4 in the LOD rotation).
2. The raw action is a bid, not a pass.
3. No bid from our team has been recorded in the auction yet (this is the
   "we are the last chance to bid" condition).

The predicate:

```python
def _would_overbid_last(obs: BiddingObservation, raw: BidAction) -> bool:
    # Must be a real overcall of something already on the table — not a
    # first bid in an all-pass auction. An all-pass auction is a redeal,
    # not an overbid scenario.
    if obs.current_high_bid <= 0:
        return False

    # Count team bids. Team 0 = seats 0, 2. Team 1 = seats 1, 3.
    # Partner seat is (obs.seat + 2) % 4.
    partner_seat = (obs.seat + 2) % 4
    team_has_bid = False
    for entry in obs.auction_transcript:
        if entry.get("action") != "BID":
            continue
        if entry.get("seat") in (obs.seat, partner_seat):
            team_has_bid = True
            break

    # If our team has already declared, we are not in the "last bidder
    # overbid" state — partner has committed and we should follow the
    # model's recommendation.
    if team_has_bid:
        return False

    # Opponent holds the contract at obs.current_high_bid. The raw bid
    # overcalls that (by construction — raw is a bid and enumerate_legal_actions
    # only returns bids that overcall current_high_bid for non-dealers,
    # and dealer-takeover logic aside, any regular bid from the dealer is
    # a legal overcall). The Enhancement A rule: the dealer should only
    # overcall the opponent's bid if the model's EV improvement is large
    # enough to justify taking the contract. We approximate "large enough"
    # by asking: would the raw bid force us to bid at least
    # `current_high_bid + 1` tricks? If yes, the filter fires.
    #
    # In plain terms: whenever the dealer is the last-chance bidder, their
    # team has passed so far, and the raw GBT choice is any overcall at
    # all of the opponent's bid, suppress it to a pass. This is the
    # strongest form of the Enh A filter. The weaker form — only suppress
    # when the raw bid is exactly current_high_bid + 1 — is called out
    # as a tunable in §7.3.
    return True
```

### 7.3 Tunables deliberately not wired
The filter above is the **strong form**: it suppresses any dealer overcall
when the team has not bid. Two weaker forms exist and are explicitly **not**
wired into this ablation to keep the cell count low:

1. **Weak form A.w1** — only suppress when `raw.n == obs.current_high_bid + 1`
   (i.e., the minimum overcall). Preserves aggressive dealer takeovers.
2. **Weak form A.w2** — only suppress when `raw.contract != highest_opp_contract`
   (i.e., dealer is switching suits, which is often suicidal at the end
   of an auction).

If the strong form lands positive in this ablation, the follow-up
investigation should compare strong vs. weak forms on a separate mini-run
before rolling to production. If the strong form lands negative or
near-zero, the weak forms are unlikely to rescue it and should not be
pursued.

### 7.4 What we expect
**Prediction:** The dealer overcall rate on the raw GBT model is somewhere
in the 5–15% range on the canonical auction scenario (estimated from the
dealer_bid_rate diagnostic on arc_d_v2 r3 comparator runs). The set rate
on those overcalls is materially higher than the set rate on partner-led
contracts. Enhancement A should reduce the set rate by enough to move
net_points by at least the MDE of 0.113 pts/deal.

**Concrete quantitative prediction registered in advance for accountability:**
- B1 − B0 mean Δnet_points_t0 ∈ [+0.05, +0.30] with 95% CI lower bound > 0.
- Set rate on `b1_gbt_enh_a` ≤ set rate on `b0_gbt_vanilla` by ≥ 0.5
  percentage points.

If these predictions do not hold, the write-up must say so explicitly and
the enhancement does not ship.

---

## 8. GBT Enhancement B — "Don't Nudge Partner's Bid +1 in Same Suit"

### 8.1 Motivation
When partner has already bid `n` in trump suit `T`, the dealer's incremental
value from bidding `n+1` in the same suit `T` is very small on average —
partner has already committed the team to the trump choice, and the extra
trick on the contract mostly just increases the set penalty magnitude
without increasing the make probability by much. In practice, "bumping
partner's bid by +1 in the same suit" is a failure mode of aggressive
point-estimate models that don't see the covariance between their own EV
and partner's declaring advantage.

Unlike Enhancement A, this pattern does not have a crisp live-game anecdote
attached. It is a hypothesis generated from the design of the GBT action-value
head: the model scores actions independently on individual seat EVs and
does not penalise the "burn partner's declaring advantage" mode. This
ablation is the test of the hypothesis.

### 8.2 Precise spec

Hook location: same as §7.2 — inside `FilteredGBTBidder.choose_bid`, after
Enhancement A has had a chance to fire.

Predicate:
```python
def _would_nudge_partner(obs: BiddingObservation, raw: BidAction) -> bool:
    # Only meaningful if raw is a regular (non-moon/loner) bid in a suit
    # contract. HIGH/LOW bumps are a separate pattern and are out of scope.
    if raw.bid_type != "regular":
        return False
    if raw.contract not in {"C", "D", "H", "S"}:
        return False

    # Find the most recent BID action from partner in the transcript.
    partner_seat = (obs.seat + 2) % 4
    partner_bid = None
    for entry in obs.auction_transcript:
        if entry.get("action") != "BID":
            continue
        if entry.get("seat") != partner_seat:
            continue
        partner_bid = entry  # last write wins — transcripts are time-ordered

    if partner_bid is None:
        return False
    if partner_bid.get("contract_type") != "suit":
        return False
    if partner_bid.get("trump") != raw.contract:
        return False

    # Same-suit bump: we are bidding raw.n in suit raw.contract and partner
    # already bid partner_bid["tricks_bid"] in the same suit. The filter
    # fires only on the minimum nudge (exactly +1 over partner).
    if raw.n != partner_bid.get("tricks_bid", -99) + 1:
        return False

    # Final guard: only fire when we are still the last bidder (dealer).
    # This is already checked by the outer choose_bid, but duplicate it
    # here for readability.
    return obs.seat == obs.dealer_seat
```

### 8.3 Why the filter is narrower than Enh A
Enhancement B is a targeted surgical suppression — it fires only on the
exact "partner bid n in X, dealer bid n+1 in X" pattern, not on any dealer
overcall. This is intentional: a dealer jump from `n+1` to `n+2` or higher
is a genuine strength signal that the model is allowed to express. The
failure mode we are targeting is the lazy +1 nudge, not aggressive declaring.

### 8.4 Expected direction
Neutral to slightly positive. This is the "insurance policy" cell — we
include it to see whether locking down the nudge pattern buys us anything
on top of Enhancement A. If B2 − B1 lands materially below zero, we ship
Enhancement A without B. If B2 − B1 lands at or above the MDE, we ship
both.

**Concrete quantitative prediction:**
- B2 − B1 mean Δnet_points_t0 ∈ [−0.02, +0.10] with 95% CI overlapping zero
  is acceptable; a CI lower bound materially below zero is a rejection.

---

## 9. Risk Register

### 9.1 Methodology risks

| Risk | Severity | Description | Mitigation |
|------|----------|-------------|------------|
| Sample size too small for bidder effect | **HIGH** | Paired SD on net_points is variable and can exceed the 4.0 estimate on rare-event auctions. At n=5000 the MDE may be larger than the effect. | Pre-compute observed paired SD on the first 1000 deals; if SE is >0.08, double n to 10,000 before reporting. |
| Redeal-drop imbalance | MEDIUM | `load_paired_data` drops all-pass redeals. If the different bidder cells drop at different rates, the paired match set shrinks and introduces selection bias. | Report raw n and matched n per cell in the results report. If match rate differs by >2%, investigate before reporting deltas. |
| P2 − P1 confounded by Cash-A vs Claim 1 interaction | LOW | The Claim 1 fix is measured conditional on Cash-A being ON. If Cash-A and Claim 1 interact in a subtle way, the P2 − P1 delta underestimates Claim 1's standalone value. | Document explicitly that P2 − P1 is "Claim 1 given Cash-A on". If adoption decision hinges on Claim 1 standalone, add a P3 cell (Cash-A OFF + Claim 1) in a follow-up mini-run. |
| Notebook-boundary violation on reporting | MEDIUM | `.claude/rules/deferred/45_notebook_boundary.md` forbids decision-critical claims that live only in notebook output. | The results report must embed the actual numbers inline and cite the exact JSONL run paths, not link to a notebook. The inline Python scripts in §5 produce stdout numbers that go directly into the report. |
| GBT artifact unavailable | MEDIUM | The canonical path `data/artifacts/arc_d_v2/r3/training_artifact_gbt_av.json` may not exist in a fresh checkout. | §4.1 documents the fallback path and the copy step. Implementation packet must verify the artifact is present before running the auction config. |

### 9.2 Implementation hazards

| Hazard | Severity | Description | Mitigation |
|--------|----------|-------------|------------|
| `draw_trump_lead_legacy` flag contamination | **HIGH** | If the research-only flag accidentally lands on `GluttonStrategy` (production), it could ship to the browser game and regress live play. | Explicit scope constraint in §4.1 point 3: flag only on `GluttonIsolatedStrategy`. Test: `grep -n draw_trump_lead_legacy src/bid_euchre/strategy/greedy.py` must return hits only inside `class GluttonIsolatedStrategy` scope. Follow-up cleanup PR removes the flag after adoption. |
| `FilteredGBTBidder` registration drift | MEDIUM | A new bidder class requires two registry edits (`BIDDER_CLASSES` and `REQUIRED_PARAMS`) plus an import in `src/bid_euchre/experiments/config.py`. Missing any one of them causes dry-run to fail with a confusing error. | Implementation packet must run `--dry-run` on both configs as an acceptance step before marking the prerequisite PR ready for review. |
| Transcript key drift | LOW | Enhancement B parses `entry.get("trump")` and `entry.get("contract_type")` from the transcript dict. If the schema changes (the hand_end schema has versioned through v8 already), the predicate silently no-ops. | Enhancement B predicate gets a unit test that constructs a synthetic `BiddingObservation` with a known transcript and asserts the filter fires / does not fire as expected. |
| Version bump without test rewrite | LOW | `GLUTTON_STRATEGY_VERSION = "0.8.1"` and `test_lead_highest_trump_when_drawing` must be rewritten per cash_a_deep_audit §2.5. | Implementation packet includes the test rewrite; reviewer checks the test file lands in the same PR as the fix. |
| Cross-lane conflict on `bidding.py` | MEDIUM | Other author lanes may be touching `src/bid_euchre/strategy/bidding.py` concurrently. | Scope-lock the bidder PR to just the new class + registry edits; do not touch existing bidder classes in the same PR. |

### 9.3 Adoption risks

| Risk | Severity | Description | Mitigation |
|------|----------|-------------|------------|
| Rubber-stamp adoption of Cash-A | MEDIUM | PR #2534 already shipped with the flag OFF by default. Pressure to flip it exists regardless of this ablation. | Gate flag flip explicitly on the P2 − P0 result: positive CI lower bound required. Document that the flag stays OFF if gate fails. |
| Single-seat measurement | LOW | All scenarios use `leader=0` by default. Seat effects could mask per-scenario deltas. | The canonical 6-scenario layout already balances across 4 suit trumps + 2 no-trump contracts. Seat rotation is a separate concern and out of scope for this ablation. |
| Overfitting to self-play | MEDIUM | Self-play measures Glutton-vs-Glutton, not Glutton-vs-human. The hosted game serves Glutton/Bud Bot against humans, and the play-side deltas may not generalise. | Tag the adoption decision as "self-play evidence only". Follow-up work: head-to-head mini-run against a distinct play strategy (e.g., `GreedyStrategy`) to verify the Cash-A and Claim 1 deltas survive outside self-play. |

---

## 10. Out of Scope (Explicit)

This ablation deliberately does NOT cover the following. Do not expand
scope without reopening this design.

1. **Implementing the Claim 1 fix.** This is an implementation packet
   dispatched separately. This design document specifies the acceptance
   criteria for that packet.
2. **Implementing `FilteredGBTBidder`.** Same as above — separate
   implementation packet. §7 and §8 specify the class.
3. **Running the experiments.** The design terminates at the runnable CLI
   command. Execution is a separate orchestrator step.
4. **Head-to-head measurement.** All cells are paired `self_play`. Measuring
   any of these enhancements against a different play strategy (e.g.,
   `GreedyStrategy`, `StrictHellRaiser`) is a follow-up investigation if
   the self-play gates pass.
5. **Seat rotation.** Leader is fixed per the canonical scenario layout.
   Seat-balanced measurement is a separate investigation.
6. **Bud Bot versioning / release engineering.** If Cash-A + Claim 1 + Enh A
   ship, the browser game needs a Bud Bot version bump and a rollout plan.
   That is outside this document.
7. **Production rollout of the research-only `draw_trump_lead_legacy` flag.**
   This flag exists only to support this ablation. A follow-up PR removes
   it after sign-off.
8. **Tuning the weak forms of Enhancement A (A.w1, A.w2).** Only the strong
   form is measured. If it passes, follow-up measurement compares against
   weak forms.
9. **Moon and loner bidding behaviour.** Neither `FilteredGBTBidder` filter
   fires on `bid_type in {"moon", "loner"}`. Moon/loner failure modes are a
   separate investigation.
10. **Card-play heuristics beyond `_draw_trump_lead`.** The Cash-A deep audit
    identified four claims; only Claim 1 is in scope here. Claims 2–4 are
    follow-up work tracked in that report.

---

## Cross-References

- [Cash-A deep audit (analyst-c)](./2026-04-06_cash_a_deep_audit.md) — source of Claim 1 bug and fix spec
- [AI play strategy investigation (analyst-a)](./2026-04-06_ai_play_strategy_investigation.md) — canonical 6-scenario layout
- [Glutton strategy revamp experiment design](./2026-03-27_glutton-strategy-revamp-experiment-design.md) — scenario layout precedent
- [Strategy versioning plan](./2026-04-06_strategy_versioning_plan.md) — `GLUTTON_STRATEGY_VERSION` MVP and the `load_paired_data` list-vs-array gotcha (§2.3)
- `src/bid_euchre/strategy/greedy.py` — `GluttonStrategy`, `GluttonIsolatedStrategy`, `_draw_trump_lead`, `cash_winners_on_lead` flag
- `src/bid_euchre/strategy/bidding.py` — `GBTActionValueBidder` (line 2347), `BiddingObservation` (line 227), `BidAction` (line 31), `BiddingPolicy` ABC (line 249)
- `src/bid_euchre/sim/simulation.py` — auction transcript schema (around line 214), dealer-last LOD ordering (around line 232)
- `src/bid_euchre/analysis/paired.py` — `load_paired_data`, `compute_paired_deltas`
- `src/bid_euchre/analysis/stats.py` — `bootstrap_ci`
- `experiments/run_experiment.py` — canonical runner, `mode: self_play` + `pair_deals: true`
- Issue #2149 — "AI overbids when it doesn't need to" (live game evidence for Enh A)
- PR #2534 — Cash-A flag + Claim 1 draw-trump-lead fix (merged, flag OFF by default)

## Outcome
_To be filled after implementation packets + runs complete. Results report
will be at `plans/sessions/2026-04-06_glutton_gbt_quicksim_results.md`._
