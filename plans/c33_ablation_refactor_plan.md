# C33 Ablation Report Refactor — Implementation Plan

> **Status:** Ready for implementation
> **Scope:** R0 only. Changes do not persist to other rungs.
> **Source:** `plans/c33_ablation_review_notes.md`

---

## Open Questions — Resolved

### Q1: Decision trace data availability

**Answer: NOT logged. Replay required.**

The JSONL schema v7 `auction_transcript` field captures only `{seat, action,
tricks_bid, contract_type, trump}` per seat — no model internals. The
`HybridOLSaBidder.choose_bid()` computes mu, sigma, P(make), EV in-memory and
discards them. No hooks or callbacks capture bidder internals during simulation.

**Implication:** Notebook D3 must replay hands through the model artifact.
The `hands` field (v3+) in JSONL logs provides raw hand contents per seat,
which can be used to reconstruct Card objects and recompute features for all
contracts. The replay approach is:

1. Parse raw JSONL logs (not `build_eval_dataset`, which only extracts features
   for the played contract)
2. Extract `hands` field → 4 hand contents per deal
3. For each hand × all 6 contracts: compute features via `get_hand_features()`
4. Run both decision layers (Gaussian EV vs floor-based) on the same features
5. Record per-hand diagnostics: mu, sigma, P(make), EV, bid/pass decision

### Q2: EV formula

**Confirmed from `HybridOLSaBidder._compute_ev()` (bidding.py:900–942):**

```
threshold = bid_n - 0.5                      # continuity correction
z = (threshold - mu) / sigma                 # z-score (capped at ±6.0)
P(make)   = 1 - Φ(z)
P(set)    = 1 - P(make)

E[tricks | make] = mu + sigma · φ(z) / P(make)     # truncated normal
E[tricks | set]  = mu - sigma · φ(z) / P(set)

make_ev = 2 · E[tricks|make] - 10
set_ev  = E[tricks|set] - bid_n - 10

EV = P(make) · make_ev + P(set) · set_ev
```

**Payoff model is net-differential:**
- Make (tricks ≥ bid_n): net = 2·tricks - 10
- Set (tricks < bid_n): net = tricks - bid_n - 10

**Utility:** `utility = EV - risk_penalty`. Risk penalty uses Monte Carlo CVaR
with `risk_lambda` from artifact. For R0, `risk_lambda` is likely 0.0 (verify
from `hybrid_r0.json`), making `utility = EV`. Bidder passes if `utility ≤ 0`.

**OLSa decision layer (for comparison):** Simply bids if `floor(mu) ≥ 3` and
exceeds current high bid. No sigma, no P(make), no EV check.

### Q3: Bid rate provenance

**Three distinct bid rates from three different contexts:**

| Rate | Bidder Arm | Context | Source |
|------|-----------|---------|--------|
| **62.5%** | hybrid_olsa (constrained, 3 features, Gaussian CDF) | Comparator self-play (uncontested, vs Glutton) | `comparator_rankings.md` v2 (10k deals, seed=42) |
| **82.8%** | OLSa_Full (full, 39 features, floor-based) | R0 promotion eval (uncontested, vs Glutton) | `r0_promotion_report.md` (seed=42) |
| **16.2%** | hybrid_olsa (constrained, 3 features, Gaussian CDF) | C33 ablation H2H (contested auction, vs olsa) | `c33_ablation_report.md` (10k deals, seed=42) |

**Key distinction:** 62.5% and 82.8% are from *different model arms*, not the
same model in different contexts. The 16.2% competitive rate reflects auction
interaction: hybrid_olsa yields 84% of auctions to olsa because olsa always
outbids it when both would bid (olsa has no EV threshold).

---

## PR Strategy

### PR 1: Report Structural Refactor + Architecture Section

**Branch:** `c33-ablation-report-refactor`
**Scope:** Pure writing — no data dependencies, no notebooks.

**Files modified:**
- `docs/04_reports/r0/c33_ablation_report.md`

**Changes:**
1. **New §3: Architecture Comparison** (D1-a) — two subsections
2. **Expand §2 Methodology** — add bid_rate formula, competitive vs intrinsic distinction
3. **Renumber sections** — current §3→§4, §4→§6 Interpretation, §5→§7, §6→§8, §7→§9, §8→§10
4. **Add placeholder §5** — "Decision Divergence Evidence" with note: "Evidence from
   notebook `55_c33_ablation_deep_dive` (PR 2)"
5. **Update Behavioral Profile table** — add bid rate context footnotes
6. **Update §6 Interpretation** — revise to reference §3 and §5

**Acceptance criteria:**
- [ ] Report is self-contained: reader understands the architecture being ablated
- [ ] Bid rate is explained: competitive vs intrinsic, with formula and sources
- [ ] Section numbering is consistent
- [ ] Cross-references to other R0 reports are valid
- [ ] `make check-quiet` passes (docs-check validates backtick-quoted paths)

### PR 2: Notebooks + Report Data Expansion + Evidence Section

**Branch:** `c33-ablation-notebooks`
**Base:** main (after PR 1 merged)

**Files modified:**
- `notebooks/arc_d/r0/55_c33_ablation_deep_dive.py` (NEW)
- `notebooks/arc_d/r0/50_r0_matchups.py` (violin plot addition)
- `docs/04_reports/r0/c33_ablation_report.md` (data sections + evidence)

**Changes:**
1. **D3:** New notebook with 7 sections (detailed spec below, includes S3.5 calibration)
2. **D2:** Violin plot of net_eppd_delta in 50_r0_matchups.py (~15 lines)
3. **D1-b completion:** Distributional detail (std, IQR, P5/P95), team0/team1 breakout,
   per-contract-type wrapper effect table
4. **D1-c:** Fill in §5 Decision Divergence Evidence with notebook findings (6 subsections:
   EV distributions, divergence counts, calibration, per-bid-level, worked example, interpretation)
5. **Update §6 Interpretation** — connect evidence from §5 to claims

**Acceptance criteria:**
- [ ] Notebook runs in SMOKE mode without real data (synthetic fallback)
- [ ] All charts faceted by contract_type
- [ ] All matchup tables show team0 and team1 separately
- [ ] `make check-quiet` passes
- [ ] `make notebook-check` passes (Jupytext sync, outputs cleared)
- [ ] No data artifacts committed
- [ ] Decision divergence counts are consistent with report claims

---

## Deliverable D1-a: New §3 Architecture Comparison

### Section Outline

```
## 3. Architecture Comparison

### 3.1 Bid/Pass Decision Mechanism

[Para 1: Shared foundation]
Both bidders share identical OLS regression coefficients from `hybrid_r0.json`.
The OLS model predicts mu (expected tricks_won) for each contract. Both use
floor(mu) to determine bid amount. The only difference is the decision layer
that determines whether to bid or pass.

[Para 2: OLSa (floor-based threshold)]
OLSa bids whenever floor(mu) >= 3 — it places every hand that the OLS model
considers viable. No consideration of prediction uncertainty or expected value.
This results in ~100% bid rate in self-play (comparator), as most hands predict
at least 3 tricks for some contract.

[Para 3: HybridOLSa (Gaussian EV wrapper)]
HybridOLSa models the full distribution of tricks via the residual variance
sigma from training. For each candidate bid:
- Computes P(make) = P(tricks >= bid_n - 0.5) via normal CDF
- Computes EV using truncated normal expectations:
  EV = P(make) * (2·E[tricks|make] - 10) + P(set) * (E[tricks|set] - bid_n - 10)
- Bids only if EV > 0

[Para 4: Key differences table]

| Property | OLSa | HybridOLSa |
|----------|------|------------|
| Decision rule | floor(mu) >= 3 | EV > 0 |
| Uses sigma? | No | Yes (per-contract residual variance) |
| Accounts for uncertainty? | No | Yes (Gaussian model) |
| Bid rate (comparator, uncontested) | ~100% | ~62.5% |
| Parameters beyond OLS | None | residual_variance, risk_lambda |

### 3.2 Risk Quantification (Analytical CVaR)

[Para 1: Mechanism]
The Gaussian model also enables analytical CVaR-5% computation from the left
tail of the trick distribution. This provides per-hand downside risk before
play, penalizing high-variance hands even when EV is positive.

[Para 2: Drawbacks]
Both the EV wrapper and CVaR computation inherit the Gaussian assumption over
a discrete, bounded [0,10] support. The global sigma per contract (no
heteroscedasticity) likely underestimates tail risk near boundaries. The
continuity correction (threshold = bid_n - 0.5) partially mitigates the
discrete-continuous mismatch.
```

---

## Deliverable D1-b: Results Expansion

### Bid Rate Clarification (PR 1)

Add to §2 Methodology or §4 Behavioral Profile:

```
**Bid rate definition:** `bid_rate = hands_with_bids / deals_total`
(evaluator.py:326). In H2H matchups, this is the *competitive* bid rate —
the fraction of deals where a bidder wins the contested auction. It is NOT
the intrinsic bid rate, which measures how often the bidder would bid in
uncontested self-play.

For context:
- hybrid_olsa intrinsic bid rate: 62.5% (comparator_rankings.md v2, 10k deals)
- hybrid_olsa competitive bid rate vs olsa: 16.2% (this report)
- The 46pp gap reflects auction interaction: olsa outbids hybrid_olsa in most
  deals because olsa has no EV threshold and bids more aggressively.
```

### Per-Contract-Type Wrapper Effect (PR 2)

The pooled +0.21 net_eppd hides contract-type variation. Since sigma differs
by contract family (suit vs high vs low in the artifact), the wrapper's
selectivity differs too. Add a faceted wrapper effect table:

| Contract Type | net_eppd_delta | 95% CI | Restraint Rate | Significant? |
|---------------|----------------|--------|----------------|--------------|
| suit          | ...            | ...    | ...            | ...          |
| high          | ...            | ...    | ...            | ...          |
| low           | ...            | ...    | ...            | ...          |

"Restraint rate" = fraction of OLSa-would-bid hands where Hybrid passes,
per contract_type. This shows whether the wrapper is more valuable for some
contract types than others.

(Values computed from C33 ablation run data + D3 replay by the coding agent.)

### Distributional Detail (PR 2)

Add to cross-matchup results table:

| Matchup | net_eppd_delta | 95% CI | std | IQR | P5 | P95 |
|---------|----------------|--------|-----|-----|-----|------|

(Values computed from C33 ablation run data by the coding agent.)

### Team0/Team1 Breakout (PR 2)

Replace collapsed matchup rows with:

| Matchup | Team | net_eppd | bid_rate | make_rate |
|---------|------|----------|----------|-----------|

Show team0 and team1 separately for each matchup. In C33 ablation, team0 is
bidder A's team (seats 0,2) and team1 is bidder B's team (seats 1,3).

---

## Deliverable D1-c: New §5 Decision Divergence Evidence

### Section Outline (PR 2, after D3 produces data)

```
## 5. Decision Divergence Evidence

Evidence from notebook `55_c33_ablation_deep_dive` (R0-only analysis).

### 5.1 Aggregate EV Distributions

[Reference D3 S3 histograms. Summarize: the EV distribution for OLSa-eligible
hands shows a substantial negative-EV tail that HybridOLSa truncates. ~X% of
hands where OLSa would bid have EV ≤ 0.]

### 5.2 Decision Divergence Counts

[Reference D3 S4 table. Summarize: across N cross-matchup deals, M (X%) show
divergence where OLSa bids but Hybrid passes (the "restraint zone"). These
hands have mean EV of Y and mean tricks_won of Z when actually played.]

### 5.3 P(make) Calibration

[Reference D3 S3.5 calibration plot. Summarize: the Gaussian P(make) estimates
are [well-calibrated / directionally correct but over/under-confident]. Key
observation: [whether calibration quality affects the wrapper's effectiveness].]

### 5.4 Per-Bid-Level Restraint

[Reference D3 S4 per-bid-level table. Summarize: the restraint zone
concentrates at bid level [X], where the wrapper filters out [Y]% of OLSa
candidates. Higher bid levels show [higher/lower] restraint rates because
[reason].]

### 5.5 Worked Example

[Reference D3 S5. One illustrative hand from the restraint zone showing the
step-by-step EV calculation and actual outcome.]

### 5.6 Interpretation

The evidence confirms that the wrapper's value is selective restraint:
HybridOLSa identifies and avoids hands where the OLS prediction is nominally
above the bid threshold but the distributional model indicates negative
expected value. These are hands where olsa bids and gets set more often than
it makes — the wrapper prevents these losses.
```

---

## Deliverable D2: Violin Plot in 50_r0_matchups.py

### Location

Insert after §2 Tricks Distribution (after line ~350 in `50_r0_matchups.py`).

### Specification

```python
# %% [markdown]
# # §2.5 Net EPPD Delta Distribution
#
# Violin plots of per-deal net_eppd_delta by matchup, faceted by contract_type.
# Self-play violins (centered on zero) serve as visual null reference.

# %%
if not df_all.empty and "contract_type" in df_all.columns:
    # Compute per-deal net_eppd_delta for each matchup
    # net_eppd_delta = team0_net - team1_net per deal
    # ... (implementation detail)

    ctypes = sorted(df_all["contract_type"].unique())
    matchup_ids = sorted(df_all["matchup_id"].unique())

    fig, axes = plt.subplots(1, len(ctypes), figsize=(6 * len(ctypes), 5), sharey=True)
    # ... violin plot per contract_type with matchups on y-axis
    # Color: green for cross-matchups, gray for self-play
    # Add vertical line at x=0 (null reference)
```

**Chart spec:**
- One panel per contract_type
- Y-axis: matchup labels
- X-axis: net_eppd_delta per deal
- Violin width proportional to deal count
- Gray fill for self-play, colored fill for cross-matchups
- Vertical line at x=0

---

## Deliverable D3: Notebook 55_c33_ablation_deep_dive.py

### File

`notebooks/arc_d/r0/55_c33_ablation_deep_dive.py` (Jupytext percent format)

### Parameters Cell

```python
# %% tags=["parameters"]
MODE = "SMOKE"          # SMOKE | QUICK | FULL
SEED = 42               # RNG seed
C33_RUN_DIR = ""        # Path to C33 ablation run (empty = synthetic fallback)
ARTIFACT_PATH = "data/artifacts/arc_d/r0/hybrid_r0.json"
```

### Section S1: Setup & Data Loading

**Imports:**
```python
import json, math, os, warnings
from pathlib import Path
import matplotlib, matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import norm
from bid_euchre.features.hand_eval import get_hand_features
from bid_euchre.core.cards import Card
```

**Data loading:**
1. Find repo root (standard pattern from 30_feature_outcome_eval.py)
2. Load model artifact JSON (hybrid_r0.json)
3. Extract per-contract: weights, bias, feature_names, residual_variance
4. Assert `risk_lambda == 0.0` (R0 uses zero; see risk-lambda guard in S2)
5. Load JSONL logs from C33_RUN_DIR cross-matchup files
6. Parse hand_end records: extract `hands`, `winning_bid`, `bidder_position`,
   `contract`, `trump`, `t0`, `t1`, `made_bid`, `deal_id`
7. Synthetic fallback for CI/SMOKE: generate random hands and simulate decisions

**Fail-fast gates:**
```python
assert len(artifact["payoff_model"]) == 3, "Expected suit/high/low models"
assert all(cf in artifact["residual_variance"] for cf in artifact["payoff_model"])
# If real data loaded:
assert n_deals >= 100, f"Insufficient deals: {n_deals}"
```

### Section S2: Decision Replay Engine

The replay uses a two-tier architecture to separate structural decision
comparison (Tier A) from outcome validation (Tier B).

**Core replay function:**

```python
def replay_bidding_decision(
    hand_cards: list[Card],
    artifact: dict,
    current_high_bid: int = 0,
) -> dict:
    """Replay a hand through both decision layers.

    Returns dict with keys:
      olsa_bid_n, olsa_contract, olsa_bids (bool),
      hybrid_bid_n, hybrid_contract, hybrid_bids (bool),
      best_mu, best_sigma, best_p_make, best_ev, best_utility,
      all_contracts: list of per-contract dicts
    """
```

**Required helper functions (must mirror `bidding.py` exactly):**

These helpers extract logic from `HybridOLSaBidder` into standalone functions
for replay. Each must be verified against the production code path:

```python
def _detect_offdef(artifact: dict) -> bool:
    """Detect nested off/def vs flat artifact format. Mirrors bidding.py:803-807."""
    return any(
        "offensive" in model_data
        for model_data in artifact["payoff_model"].values()
    )

def _get_model(artifact: dict, contract_family: str) -> dict:
    """Get the offensive model dict. Mirrors bidding.py:874-878."""
    if _detect_offdef(artifact):
        return artifact["payoff_model"][contract_family]["offensive"]
    else:
        return artifact["payoff_model"][contract_family]

def predict_mu(artifact: dict, contract_family: str, features: dict) -> float:
    """Predict tricks via OLS. Mirrors bidding.py:863-880.

    Args:
        features: Feature dict from get_hand_features() (NOT a numpy array).
                  Converted to vector in model["feature_names"] order,
                  matching production code at bidding.py:879.
    """
    model = _get_model(artifact, contract_family)
    x = np.array([features[f] for f in model["feature_names"]], dtype=np.float64)
    return float(x @ np.array(model["weights"]) + model["bias"])

def get_sigma(artifact: dict, contract_family: str) -> float:
    """Get residual std dev. Mirrors bidding.py:882-898.

    Handles both flat (float) and nested (off/def dict) residual_variance.
    """
    rv = artifact["residual_variance"][contract_family]
    if isinstance(rv, dict) and "offensive" in rv:
        var = float(rv["offensive"])
    else:
        var = float(rv)
    return math.sqrt(max(0.0, var))

def compute_p_make(mu: float, sigma: float, bid_n: int) -> float:
    """P(make) via Gaussian CDF. Mirrors bidding.py:905+919.

    Handles sigma == 0 (deterministic) to match _compute_ev()'s guard.
    """
    if sigma == 0.0:
        # Deterministic: matches _compute_ev()'s mu >= bid_n check (line 907)
        return 1.0 if mu >= bid_n else 0.0
    threshold = bid_n - 0.5  # continuity correction
    z = (threshold - mu) / sigma
    z = max(-6.0, min(6.0, z))
    return float(1.0 - norm.cdf(z))

def compute_ev(mu: float, sigma: float, bid_n: int) -> float:
    """Expected value via truncated normal. Mirrors bidding.py:900-942."""
    # Must replicate _compute_ev() exactly, including the sigma == 0 guard:
    #   if sigma == 0: deterministic payoff (line 905-910)
    #   else: truncated normal with net-differential payoff:
    #     make_payoff = 2·tricks - 10
    #     set_payoff  = tricks - bid_n - 10
    # See bidding.py:900-942 for the full truncated normal formula.
    ...  # Implementation must match production code line-for-line
```

**Verification:** After implementing these helpers, add a unit-level sanity
check comparing their output to `HybridOLSaBidder._compute_ev()` on a known
hand to ensure no formula drift.

**Implementation steps:**
1. For each contract family (suit×4, high, low):
   a. Compute features: `get_hand_features(hand_cards, contract_type, trump)`
   b. Compute mu: `x @ weights + bias` (using offensive sub-model via `predict_mu`)
   c. Compute bid_n: `math.floor(mu)`
   d. If bid_n < 3 or bid_n > 10: skip
   e. For OLSa: record as candidate if `bid_n > current_high_bid`
   f. For Hybrid: compute sigma from residual_variance, then:
      - threshold = bid_n - 0.5
      - z = (threshold - mu) / sigma (capped at ±6.0)
      - p_make = 1 - norm.cdf(z)
      - EV via truncated normal formula (exact formula from bidding.py:900–942)
      - utility = EV - risk_penalty (risk_penalty = 0 if risk_lambda = 0)
      - Record as candidate if `bid_n > current_high_bid` AND `utility > 0`

2. OLSa picks best candidate by (predicted_tricks, bid_n, contract) descending
3. Hybrid picks best candidate by utility descending
4. Return comprehensive diagnostic dict

**Card parsing:**

The `hands` field in JSONL logs stores cards as `[suit, rank]` pairs
(per game_logger.py:240):
```python
from bid_euchre.core.cards import Card
# Format: [["S","A"], ["C","K"], ["H","T"], ...]
hand = [Card(suit=c[0], rank=c[1]) for c in raw_hand]
```

**Cross-matchup identification:**

Use the dual-field pattern (matching `run_arc_d_h2h_battery.py:487`).
Do NOT use ordinal position or filename order:
```python
def get_matchup_id(record: dict) -> str:
    """Extract matchup ID using dual-field fallback."""
    return record.get("matchup_id") or record.get("strategy_id", "")

def is_cross_matchup(record: dict) -> bool:
    """Identify cross-matchups by participant names, not position."""
    mid = get_matchup_id(record)
    return "_vs_" in mid and "self_play" not in mid
```

**Risk-lambda guard:**

The Hybrid decision logic is `utility = EV - risk_penalty`. Using `actual_ev`
alone for outcome interpretation is only valid when `risk_lambda == 0.0`
(risk_penalty vanishes). Add a fail-fast guard immediately after loading the
artifact, before any replay loop runs:

```python
risk_lambda = artifact.get("risk_lambda", 0.0)
assert risk_lambda == 0.0, (
    f"risk_lambda={risk_lambda} != 0.0; Tier-B actual_ev must be replaced "
    f"with actual_utility = actual_ev - risk_penalty. See bidding.py:944-978."
)
# TODO: If risk_lambda != 0 in future rungs, compute actual_risk_penalty via
# _compute_risk_penalty(actual_mu, actual_sigma, actual_bid) and store
# actual_utility = actual_ev - actual_risk_penalty in df_outcome.
```

**Tier A: Intrinsic replay loop (all seats, predicted metrics only):**

```python
tier_a_rows = []
for record in cross_matchup_records:
    mid = get_matchup_id(record)
    for seat in range(4):
        hand_cards = parse_hand(record["hands"][seat])
        result = replay_bidding_decision(hand_cards, artifact)
        result["deal_id"] = record["deal_id"]
        result["seat"] = seat
        result["matchup_id"] = mid
        # NO outcome columns — Tier A is prediction-only
        tier_a_rows.append(result)

df_intrinsic = pd.DataFrame(tier_a_rows)
```

**Tier B: Outcome-validated replay loop (auction winner only):**

```python
tier_b_rows = []
for record in cross_matchup_records:
    winner_seat = record.get("bidder_position")
    if winner_seat is None:
        continue  # all-pass redeal, skip

    hand_cards = parse_hand(record["hands"][winner_seat])
    # Replay at current_high_bid=0 (intrinsic decision comparison)
    result = replay_bidding_decision(hand_cards, artifact)

    # Also compute P(make) and EV for the ACTUAL contract+bid played
    actual_cf = record["contract"]  # "suit", "high", or "low"
    actual_trump = record.get("trump")
    actual_bid = record["winning_bid"]
    if actual_cf in ("high", "low"):
        actual_features = get_hand_features(hand_cards, actual_cf, None)
    else:
        actual_features = get_hand_features(hand_cards, "suit", actual_trump)

    actual_mu = predict_mu(artifact, actual_cf, actual_features)
    actual_sigma = get_sigma(artifact, actual_cf)
    actual_p_make = compute_p_make(actual_mu, actual_sigma, actual_bid)
    actual_ev = compute_ev(actual_mu, actual_sigma, actual_bid)

    result["deal_id"] = record["deal_id"]
    result["winner_seat"] = winner_seat
    result["matchup_id"] = get_matchup_id(record)

    # Outcome columns — valid because this is the actual auction winner
    result["actual_contract"] = record["contract"]
    result["actual_trump"] = record.get("trump")
    result["actual_bid"] = actual_bid
    result["actual_made"] = record.get("made_bid")
    result["actual_p_make"] = actual_p_make
    result["actual_ev"] = actual_ev

    # Contract match flag for calibration stratification
    hybrid_contract = result.get("hybrid_contract")
    olsa_contract = result.get("olsa_contract")
    result["contract_match_hybrid"] = (hybrid_contract == record["contract"])
    result["contract_match_olsa"] = (olsa_contract == record["contract"])

    # Declaring team's tricks
    winner_team = 0 if winner_seat in (0, 2) else 1
    result["actual_tricks"] = record["t0"] if winner_team == 0 else record["t1"]

    # Net differential for the declaring team
    if result["actual_made"]:
        result["actual_net"] = 2 * result["actual_tricks"] - 10
    else:
        result["actual_net"] = result["actual_tricks"] - actual_bid - 10

    tier_b_rows.append(result)

df_outcome = pd.DataFrame(tier_b_rows)
```

**Fail-fast gates:**
```python
# Tier A: Hybrid should bid on a subset of OLSa's bids
hybrid_bids = df_intrinsic["hybrid_bids"].sum()
olsa_bids = df_intrinsic["olsa_bids"].sum()
assert hybrid_bids <= olsa_bids, (
    f"Hybrid bids more than OLSa: {hybrid_bids} vs {olsa_bids}"
)

# Tier B: every row should have a valid winner
assert df_outcome["winner_seat"].notna().all()
assert df_outcome["actual_made"].notna().all()
```

### Section S3: Aggregate EV Distribution

**Data source: Tier A (intrinsic, all seats).** These charts use `df_intrinsic`
(predicted EV/mu/P(make) only, no outcome data).

**Chart 3a: Overlaid EV histograms (faceted by contract_type)**

- Filter to hands where OLSa would bid (olsa_bids == True)
- X-axis: EV of bid decision (from Hybrid's computation)
- Two overlaid distributions:
  - Blue: hands where Hybrid also bids (EV > 0)
  - Red: hands where Hybrid passes (EV ≤ 0) — the "restraint zone"
- Vertical line at EV = 0
- One panel per contract_type
- Title includes count of restraint-zone hands
- Label: "Intrinsic analysis (current_high_bid=0, no auction interaction)"

**Chart 3b: Decision scatterplot (faceted by contract_type)**

- One panel per contract_type (1×3 or 2×2 layout)
- X-axis: mu (predicted tricks, same for both bidders)
- Y-axis: P(make) from Hybrid's computation
- Color by decision category:
  - Gray: both pass
  - Green: both bid
  - Red: OLSa-only bid (restraint zone)
  - Blue: Hybrid-only bid (rare/impossible with same mu, but include)
- Horizontal line at P(make) where EV ≈ 0 (the implicit threshold)
- Shows the geometric decision boundary
- Label: "Intrinsic analysis (current_high_bid=0, no auction interaction)"

**Assert gate:**
```python
# Restraint zone should be non-empty
restraint_count = ((df_intrinsic["olsa_bids"]) & (~df_intrinsic["hybrid_bids"])).sum()
assert restraint_count > 0, "No restraint zone hands found"
print(f"Restraint zone: {restraint_count} hands "
      f"({restraint_count / len(df_intrinsic) * 100:.1f}%)")
```

### Section S3.5: P(make) Calibration Check

**Purpose:** Test whether the Gaussian P(make) estimates are directionally
correct. The wrapper's value depends on P(make) being a reasonable ranking of
hand quality, even if not perfectly calibrated.

**Data source: Tier B (auction winner only).** Use ALL `df_outcome` rows —
do NOT filter by whether the intrinsic replay contract matches the actual
contract played. The `actual_p_make` column already stores P(make) for the
actual (contract, bid) that was played, which is the correct prediction to
calibrate against `actual_made`.

**Chart: Calibration plot (faceted by contract_type)**

- Use all rows from `df_outcome` (Tier B, auction winner only)
- Bin hands by predicted P(make) (`actual_p_make`): 10 bins (0–10%, ..., 90–100%)
- For each bin, compute actual make rate from `actual_made`
- Plot: predicted P(make) (bin midpoint) vs actual make rate
- Add diagonal (perfect calibration reference)
- Add error bars (Wilson binomial CI per bin)
- One panel per contract_type
- Label: "Outcome-validated (auction winner only)"

**Optional stratification:** As a diagnostic, stratify the calibration per
policy to reveal how contract selection affects calibration quality:

- **Hybrid-match stratum:** `contract_match_hybrid == True` (Hybrid's intrinsic
  best-contract matches the actual contract played)
- **Hybrid-mismatch stratum:** `contract_match_hybrid == False`
- **OLSa-match stratum:** `contract_match_olsa == True` (OLSa's intrinsic
  best-contract matches the actual contract played)
- **OLSa-mismatch stratum:** `contract_match_olsa == False`

Report per-policy strata alongside the pooled calibration. This reveals
whether calibration degrades when the auction forces a different contract than
what each policy would prefer. Do NOT exclude mismatch rows — that would
introduce selection bias by preferentially removing disagreement cases.

**Interpretation notes for the report:**
- If close to diagonal: Gaussian model is well-calibrated, and the P(make)
  threshold is principled.
- If above diagonal (under-confident): the model systematically underestimates
  P(make), meaning the wrapper is overly cautious. This is consistent with the
  low 16.2% competitive bid rate.
- If below diagonal (over-confident): the model overestimates P(make), but the
  wrapper still works because the EV threshold (not just P(make)) determines
  the decision.
- If poorly calibrated but wrapper still adds value: this means directional
  ranking matters more than absolute accuracy — a useful insight for R1.
- If match/mismatch strata diverge significantly: auction dynamics introduce
  contract selection effects that the intrinsic replay doesn't capture.

**Assert gate:**
```python
# Predicted and actual should be positively correlated (directional correctness)
bin_df = calibration_bins[calibration_bins["count"] >= 10]  # sufficient data
if len(bin_df) >= 3:
    corr = bin_df["predicted_p_make"].corr(bin_df["actual_make_rate"])
    assert corr > 0, f"P(make) calibration has negative correlation: {corr:.3f}"
    print(f"P(make) calibration correlation: {corr:.3f}")
```

### Section S4: Decision Divergence Table

**Table spec (columns from two tiers):**

| Category | Count (Tier A) | % | Mean EV | Mean mu | Mean P(make) | Mean tricks_won (Tier B) | Mean net_eppd (Tier B) |
|----------|----------------|---|---------|---------|--------------|--------------------------|------------------------|

- Counts, %, Mean EV, Mean mu, Mean P(make): from `df_intrinsic` (Tier A, all seats)
- Mean tricks_won, Mean net_eppd: from `df_outcome` (Tier B, auction winner only)

Categories:
- **Both bid**: OLSa bids AND Hybrid bids
- **Both pass**: OLSa passes AND Hybrid passes
- **OLSa-only bid** (restraint zone): OLSa bids, Hybrid passes
- **Hybrid-only bid**: Hybrid bids, OLSa passes (expect ~0)

Faceted by contract_type.

Note: "Outcome columns (tricks_won, net_eppd) are restricted to deals where
the auction winner's seat is in the given divergence category. Sample sizes for
outcome columns may differ from Tier A counts."

**Per-bid-level breakdown (additional table, Tier A only):**

| Bid Level | OLSa Bids | Hybrid Bids | Restraint Count | Restraint % | Mean EV (restraint) |
|-----------|-----------|-------------|-----------------|-------------|---------------------|
| 3         | ...       | ...         | ...             | ...         | ...                 |
| 4         | ...       | ...         | ...             | ...         | ...                 |
| 5         | ...       | ...         | ...             | ...         | ...                 |
| 6+        | ...       | ...         | ...             | ...         | ...                 |

This shows whether the wrapper mostly filters marginal 3-bids (low-risk
restraint) or prevents catastrophic high bids (high-value restraint).
Expect the restraint rate to increase with bid level, since higher bids
require higher P(make) to achieve positive EV.

**Computation notes:**
- "Mean tricks_won" from Tier B only (actual declaring team's tricks for
  the auction winner). NOT propagated to non-winning seats.
- "Mean net_eppd" from Tier B only: 2·tricks - 10 (made) or
  tricks - bid - 10 (set), using `actual_net` column.
- For "both pass" category, outcome columns show "N/A" (no auction winner).

**Assert gate:**
```python
# OLSa-only bid zone should have lower mean tricks_won than both-bid zone
# (Tier B only — filter df_outcome by divergence category of the winner seat)
restraint_tricks = df_div_b[df_div_b["category"] == "olsa_only_bid"]["actual_tricks"].mean()
both_bid_tricks = df_div_b[df_div_b["category"] == "both_bid"]["actual_tricks"].mean()
if not np.isnan(restraint_tricks) and not np.isnan(both_bid_tricks):
    assert restraint_tricks < both_bid_tricks, (
        f"Restraint zone has higher tricks ({restraint_tricks:.2f}) "
        f"than both-bid zone ({both_bid_tricks:.2f})"
    )
```

### Section S5: Worked Example Hand

**Selection criteria:**
- From `df_outcome` (Tier B, auction winner only)
- From "olsa_only_bid" category (Hybrid would pass, OLSa would bid)
- Choose a deal where `actual_made == False` (olsa-team winner got set)
- Prefer a suit contract (most common, easiest to explain)

The worked example shows a real auction winner's hand with a verifiable
outcome, not a counterfactual for a non-winning seat.

**Display format:**
```
Deal #XXXX, Seat Y
Contract: suit (trump=Z), Bid: N tricks

Hand: [list of cards]

Features:
  bowers: ...
  trump_count: ...
  offsuit_aces: ...

OLS Prediction:
  mu = X.XX tricks (floor → bid N)

Gaussian EV Computation:
  sigma = X.XX (residual std for suit contracts)
  threshold = N - 0.5 = X.X
  z = (threshold - mu) / sigma = X.XX
  P(make) = 1 - Φ(z) = X.X%
  E[tricks|make] = X.XX
  E[tricks|set]  = X.XX
  make_ev = 2·X.XX - 10 = X.XX
  set_ev  = X.XX - N - 10 = X.XX
  EV = P(make)·make_ev + P(set)·set_ev = X.XX

Decision:
  OLSa: BID (floor(mu) = N ≥ 3)    ← would bid
  Hybrid: PASS (EV = X.XX ≤ 0)     ← declines

Actual Outcome:
  olsa bid N, won X tricks → SET (X < N)
  Net differential: X - N - 10 = -XX
```

### Section S6: Summary

Print key findings for report cross-reference, split by tier:
```
=== C33 Ablation Deep Dive Summary ===

--- Tier A: Intrinsic Decision Comparison (all seats, current_high_bid=0) ---
Total hands replayed: NNNN (N deals × 4 seats)
Decision divergence:
  Both bid:        NNNN (XX.X%)
  Both pass:       NNNN (XX.X%)
  OLSa-only bid:  NNNN (XX.X%)  ← restraint zone
  Hybrid-only bid: NNNN (XX.X%)

Restraint zone (predicted metrics):
  Mean EV:      X.XX (negative, confirming wrapper avoids -EV bids)
  Mean P(make): XX.X%

--- Tier B: Outcome-Validated (auction winner only) ---
Total deals with winner: NNNN
Restraint zone with outcomes: NNNN deals

Restraint zone (actual outcomes):
  Mean tricks_won: X.XX
  Set rate:        XX.X% (vs XX.X% in both-bid zone)
  Mean net_eppd:   X.XX

P(make) calibration:
  Correlation:  X.XX (directional correctness)
  Assessment:   [well-calibrated / over-confident / under-confident]

Per-bid-level restraint (Tier A):
  Bid 3: XX.X% restraint rate (N hands)
  Bid 4: XX.X% restraint rate (N hands)
  Bid 5: XX.X% restraint rate (N hands)
  Bid 6+: XX.X% restraint rate (N hands)

Per-contract-type wrapper effect (Tier B):
  suit: +X.XX net_eppd (restraint rate XX.X%)
  high: +X.XX net_eppd (restraint rate XX.X%)
  low:  +X.XX net_eppd (restraint rate XX.X%)
```

---

## Execution Order

```
PR 1 (docs only, no dependencies):
  1. Create worktree: git worktree add ../Bid-Euchre-c33-report -b c33-ablation-report-refactor
  2. Edit c33_ablation_report.md:
     a. Insert §3 Architecture Comparison (D1-a)
     b. Add bid rate formula + competitive/intrinsic distinction to §2
     c. Renumber §3→§4 Results, insert placeholder §5, §4→§6 Interpretation, etc.
     d. Update cross-references
  3. Run make check-quiet
  4. Open PR

PR 2 (after PR 1 merged):
  1. Create worktree: git worktree add ../Bid-Euchre-c33-notebooks -b c33-ablation-notebooks
  2. Create notebooks/arc_d/r0/55_c33_ablation_deep_dive.py (D3)
  3. Add violin plot to notebooks/arc_d/r0/50_r0_matchups.py (D2)
  4. Expand c33_ablation_report.md:
     a. Add distributional detail to §4 Results (D1-b)
     b. Add team0/team1 breakout tables (D1-b)
     c. Fill in §5 Decision Divergence Evidence (D1-c)
     d. Update §6 Interpretation with evidence references
  5. Run make notebook-sync && make check-quiet
  6. Open PR
```

---

## Implementation Notes

### Card Parsing for Replay

The `hands` field stores cards as `[suit, rank]` pairs (per game_logger.py:240):

```python
from bid_euchre.core.cards import Card
# Format: [["S","A"], ["C","K"], ["H","T"], ...]
hand = [Card(suit=c[0], rank=c[1]) for c in raw_hand]
```

### Artifact Structure for Replay

The `hybrid_r0.json` artifact (type: `hybrid_olsa_v1`) may use either of two
formats. The replay helpers (`_detect_offdef`, `_get_model`, `get_sigma`)
handle both automatically, matching `bidding.py:803-853`:

**Nested off/def format:**
```json
{
  "artifact_type": "hybrid_olsa_v1",
  "payoff_model": {
    "suit": {"offensive": {"weights": [...], "bias": float, "feature_names": [...]}, "defensive": {...}},
    "high": {"offensive": {...}, "defensive": {...}},
    "low": {"offensive": {...}, "defensive": {...}}
  },
  "residual_variance": {
    "suit": {"offensive": float, "defensive": float},
    "high": {"offensive": float, "defensive": float},
    "low": {"offensive": float, "defensive": float}
  },
  "risk_lambda": float
}
```

**Flat format (original single-model):**
```json
{
  "artifact_type": "hybrid_olsa_v1",
  "payoff_model": {
    "suit": {"weights": [...], "bias": float, "feature_names": [...]},
    "high": {...},
    "low": {...}
  },
  "residual_variance": {"suit": float, "high": float, "low": float},
  "risk_lambda": float
}
```

For replay, use the **offensive** sub-model (declaring perspective) when nested,
or the flat model when not nested. The `_detect_offdef()` helper determines
which format is in use. The notebook must assert `risk_lambda == 0.0`
before using EV-only interpretations (see risk-lambda guard in S2). If a
future rung uses non-zero risk_lambda, the notebook will need to compute
`actual_utility = actual_ev - risk_penalty` for Tier B outcome validation.

### Synthetic Fallback

For CI/SMOKE mode (no real data), generate synthetic hands and demonstrate
the replay pipeline works. The synthetic data should show a clear restraint
zone (some hands with floor(mu) >= 3 but EV < 0) to verify chart generation.

Use the same synthetic data pattern as `30_feature_outcome_eval.py` (random
features with known distributions).

### Notebook Conventions

Follow the patterns from existing R0 notebooks:
- Jupytext percent format with metadata header (copy from 50_r0_matchups.py)
- `matplotlib.use("Agg")` for non-interactive backend
- MODE_DEAL_COUNTS dict for SMOKE/QUICK/FULL
- Fail-fast validation section after data loading
- Print run metadata summary
- All charts use `plt.tight_layout()` and `plt.show()`
- Gate assertions use `assert` with descriptive messages

### Cross-Matchup Identification

Use the dual-field pattern from `run_arc_d_h2h_battery.py:487`:
`record.get("matchup_id") or record.get("strategy_id", "")`. This handles
both older JSONL with `matchup_id` and current format with `strategy_id`.
Cross-matchups satisfy `"_vs_" in mid and "self_play" not in mid`.
Do NOT use ordinal position — the matchup order in the config is not
guaranteed stable across regeneration. Self-play matchups should be excluded
from the decision replay analysis.

---

## Validation Checklist (Pre-PR)

### PR 1
- [ ] `make check-quiet` passes
- [ ] No backtick-quoted paths to nonexistent files (docs-check)
- [ ] Section numbers sequential and consistent
- [ ] Cross-references to other R0 reports valid
- [ ] Bid rate formula matches `evaluator.py:326`
- [ ] Architecture description matches `bidding.py` code exactly
- [ ] EV formula matches `_compute_ev()` implementation

### PR 2
- [ ] `make check-quiet` passes
- [ ] `make notebook-check` passes (Jupytext sync, outputs cleared)
- [ ] No data artifacts committed
- [ ] Notebook runs in SMOKE mode (synthetic fallback)
- [ ] All charts faceted by contract_type
- [ ] All matchup tables show team0 and team1 separately
- [ ] Violin plot uses correct net_eppd_delta computation
- [ ] Decision divergence counts are plausible:
  - Restraint zone is non-empty
  - Restraint zone has negative mean EV
  - Hybrid bids ⊆ OLSa bids (approximately)
- [ ] P(make) calibration has positive correlation (directional correctness)
- [ ] Per-bid-level table shows restraint rate by bid amount
- [ ] Per-contract-type wrapper effect table included in report
- [ ] Worked example shows a SET outcome in the restraint zone
- [ ] Report §5 findings are consistent with notebook outputs
- [ ] Worktree proof in PR description
- [ ] Tier A charts labeled "Intrinsic analysis (current_high_bid=0)"
- [ ] Tier B charts labeled "Outcome-validated (auction winner only)"
- [ ] Outcome columns (tricks_won, net_eppd) never attached to non-winning seats
- [ ] P(make) calibration uses ALL Tier B rows (no contract-match filter)
- [ ] Calibration stratified by contract match/mismatch as diagnostic
- [ ] Cross-matchups identified by dual-field pattern, not ordinal position
- [ ] risk_lambda == 0.0 asserted before EV-only interpretation
- [ ] `get_matchup_id()` uses `record.get("matchup_id") or record.get("strategy_id")`
- [ ] `compute_p_make()` and `compute_ev()` guard `sigma == 0.0` before division
