# R1.5.3 Step 0: Decision-Level Suit Diagnostic

**Date:** 2026-03-12
**Arc:** D — OLSa-Hybrid Bidder
**Parent:** R1.5.3 alternative approaches plan (`plans/sessions/2026-03-11_r1-5-3-alternative-approaches.md`)
**Decision tree:** `plans/r1_5_forward_decision_tree.md`
**Status:** COMPLETE
**Goal:** Decompose the -0.142 suit net_eppd deficit into decision failure modes to
determine which treatment track (A/B/C) to pursue.

## Background

R1.5.2 diagnostics identified H12 (OLS predicts the mean of a bimodal make/set
distribution) as the leading working hypothesis for the suit regression, but all
evidence is prediction-level. No decision-level proof exists that between-mode
predictions cause bad bids. This diagnostic closes that gap.

Key numbers:
- AV v1 pooled delta vs R0: +0.152 net_eppd, CI [+0.124, +0.180]
- Suit deficit: -0.142, CI [-0.180, -0.105]
- High gain: +0.430, Low gain: +0.495
- Suit bimodality: BIC delta = 4,081 (made 37% / set 63%, ~15 pts apart)

## Data Sources

1. **FULL H2H game logs** (50K deals, 9 matchups)
   - Path: `data/runs/arc_d_r0_h2h_battery_42_20260308_173038/logs/`
   - Key matchups for AV v1 vs R0 comparison:
     - `*_action_value_v1_vs_hybrid_olsa_r0.jsonl` — AV v1 team0, R0 team1
     - `*_hybrid_olsa_r0_vs_action_value_v1.jsonl` — R0 team0, AV v1 team1
   - Schema: `hand_end` events with `auction_transcript` (list of 4 bid dicts),
     `contract`, `trump`, `bidder_position`, `t0`, `t1`, `made_bid`, `features` (39 per seat)
   - Parser: `build_eval_dataset()` from `src/bid_euchre/datasets/eval_dataset.py`
     yields per-seat DataFrame with `contract_type`, `is_bidder`, `is_declaring_team`,
     `points_won`, `feat_*` columns

2. **Counterfactual dataset** (468,388 rows, 62 columns)
   - Path: `data/runs/action_value_quick_42_v2/datasets/action_value.parquet`
   - Key columns: `contract_family`, `focal_declared`, `net_points`, `tricks_won`,
     `bid_n`, `action_type`, `hand_id`, `deal_id`
   - 305,592 suit rows (65% of dataset)
   - Contains per-action counterfactual outcomes (multiple rows per hand_id)

3. **AV v1 model artifact** — for reconstructing OLS predictions on counterfactual data
   - Schema: `action_value_olsa_v1` with `models.suit.coefficients`, `models.suit.intercept`,
     `models.suit.feature_names` (54 features: 52 state + 2 action)
   - `predict_ols(model_dict, features)` at `src/bid_euchre/strategy/bidding.py:1509`

## Plan

### Step 1: Build Analysis Script

Create `scripts/internal/suit_decision_diagnostic.py` — a single script that
loads both data sources, runs all 4 analyses, and outputs a JSON artifact +
markdown report.

**Functions:**

```python
def load_h2h_suit_hands(log_dir: Path) -> pd.DataFrame:
    """Load AV v1 vs R0 H2H matchups, filter to suit contract hands.

    Uses build_eval_dataset() on the two relevant JSONL files
    (*_action_value_v1_vs_*_olsa_r0 and *_olsa_r0_vs_action_value_v1).
    Returns DataFrame with columns: deal_id, seat, team, contract_type,
    tricks_won, winning_bid, bidder_seat, is_bidder, is_declaring_team,
    points_won, feat_*, matchup (which file it came from).

    Filter: contract_type == 'suit', is_bidder == True
    """

def load_counterfactual_suit(parquet_path: Path) -> pd.DataFrame:
    """Load counterfactual dataset, filter to suit rows with focal_declared.

    Returns DataFrame with columns needed for make/set boundary analysis.
    Derive: made_contract = (tricks_won >= bid_n)
    """

def reconstruct_ols_predictions(
    cf_df: pd.DataFrame,
    artifact_path: Path,
) -> np.ndarray:
    """Reconstruct OLS suit predictions from model artifact and features.

    Uses predict_ols() with suit model coefficients on the feature columns
    in the counterfactual dataset. Feature column mapping:
    - 39 hand features → feat columns in parquet (match by name)
    - 3 partner features → partner_bid_level, partner_passed, partner_suit_match
    - 10 positional features → current_high_bid, is_high, is_low, trump_*, seat_rel_*
    - 2 action features → bid_n, bid_n^2
    """
```

### Step 2: Analysis 1 — Error Taxonomy

For every suit hand in H2H data where AV v1 is the bidder:
1. Extract AV v1's bid decision from `auction_transcript`
2. Determine outcome (made/set, net points)
3. Classify into error types:

| Error Type | Detection |
|------------|-----------|
| **Over-bid suit** | AV v1 bids suit, team is set (made_bid=False) |
| **Under-bid suit** | AV v1 passes, but counterfactual shows suit would have been profitable |
| **Wrong contract** | AV v1 bids suit, but high/low would have yielded more points |
| **Wrong bid level** | AV v1 bids suit-N, different N would have been better |
| **Correct** | AV v1's suit decision was optimal or near-optimal |

For each type: compute frequency, average cost (net_eppd contribution),
and cumulative fraction of the -0.142 deficit.

**Note:** "Under-bid suit" and "wrong contract" require counterfactual
outcomes from the parquet dataset. Cross-reference by `deal_id` where
possible, but the H2H and counterfactual datasets are from different
deal populations. For under-bid analysis, use the counterfactual dataset
directly (hands where AV v1 would pass but suit has positive EV).

### Step 3: Analysis 2 — Disagreement State Analysis

Using H2H logs where both AV v1 and R0 appear:
1. Parse `auction_transcript` to extract each bidder's suit-related actions
2. Identify hands where the two bidders disagree on suit (one bids suit,
   the other doesn't, or different suit levels)
3. For disagreement hands: who won the deal? Was the disagreement costly?
4. Characterize disagreement states: which hand features correlate with
   disagreement? (use `feat_*` columns from the JSONL)

### Step 4: Analysis 3 — Make/Set Boundary Behavior

Using the counterfactual dataset (suit, focal_declared):
1. Derive `made_contract = (tricks_won >= bid_n)`
2. Reconstruct OLS predictions using `reconstruct_ols_predictions()`
3. Compute empirical P(make) in bins of OLS prediction (e.g., 20 bins)
4. Plot: OLS prediction vs P(make) calibration curve
5. Identify where costly errors concentrate:
   - Boundary region: P(make) in [0.3, 0.7]
   - Clear make: P(make) > 0.7
   - Clear set: P(make) < 0.3
6. Compute fraction of suit deficit from each region

### Step 5: Analysis 4 — Bid-Level Headroom (H13)

Using the counterfactual dataset (suit, focal_declared):
1. For hands where AV v1 bids suit-4 (bid_n == 4):
   - What's the counterfactual net_points for suit-5, suit-6, etc.?
   - Group by hand_id, compare net_points across bid levels
2. Compute: how often would a higher bid improve net_points?
3. Compute: total headroom from optimal bid-level selection
4. Compare to the -0.142 deficit — is bid-level optimization a significant factor?

### Step 6: Generate Outputs

1. **JSON artifact:** `data/artifacts/r1_5_3/suit_error_taxonomy.json`
   ```json
   {
     "analysis_date": "2026-03-12",
     "seed": 42,
     "n_suit_hands_h2h": "...",
     "n_suit_rows_cf": "...",
     "error_taxonomy": {
       "over_bid": {"count": "...", "pct_of_deficit": "...", "avg_cost": "..."},
       "under_bid": {"count": "...", "pct_of_deficit": "...", "avg_cost": "..."},
       "wrong_contract": {"count": "...", "pct_of_deficit": "...", "avg_cost": "..."},
       "wrong_level": {"count": "...", "pct_of_deficit": "...", "avg_cost": "..."},
       "correct": {"count": "...", "pct_of_deficit": "...", "avg_cost": "..."}
     },
     "boundary_analysis": {
       "boundary_pct_of_deficit": "...",
       "clear_make_pct": "...",
       "clear_set_pct": "..."
     },
     "bid_level_headroom": {
       "total_headroom_net_eppd": "...",
       "pct_hands_improvable": "..."
     },
     "gate_decision": "Track A / Track B / other",
     "gate_rationale": "..."
   }
   ```

2. **Diagnostic report:** `docs/04_reports/arc_d_v1/r1_5/suit_decision_diagnostic.md`
   - Error taxonomy table with frequencies and costs
   - Calibration curve (committed as PNG or described numerically)
   - Bid-level headroom results
   - Gate decision and rationale

### Step 7: Write Tests

Add tests in `tests/unit/test_suit_decision_diagnostic.py`:
- Test `load_h2h_suit_hands()` with a fixture JSONL (a few hand records)
- Test `load_counterfactual_suit()` with a small parquet fixture
- Test error taxonomy classification on synthetic hand records
- Test `reconstruct_ols_predictions()` produces correct values for known inputs
- Test bid-level headroom calculation on synthetic data

## Gate Criteria

After Step 0 completes, the error taxonomy determines the next track:

| Finding | Track | Rationale |
|---------|-------|-----------|
| Boundary errors > 60% of deficit | **Track A** (two-stage) | Classification at the boundary is the right fix |
| Errors spread, non-linear patterns | **Track B** (GBT) | Nonlinear model may capture what OLS misses |
| Errors mostly wrong-contract type | **New direction** | Contract selection mechanism, not within-suit |
| Bid-level errors significant (>30% of deficit) | **Bid-level fix** | Lighter-weight fix than full model change |
| Noise dominates | **Repeated rollouts** | Need cleaner signal before any treatment |

## Files

- `scripts/internal/suit_decision_diagnostic.py` — Main analysis script (NEW)
- `tests/unit/test_suit_decision_diagnostic.py` — Unit tests (NEW)
- `data/artifacts/r1_5_3/suit_error_taxonomy.json` — Output artifact (generated, not committed)
- `docs/04_reports/arc_d_v1/r1_5/suit_decision_diagnostic.md` — Diagnostic report (NEW)

## Validation

```bash
# Run targeted tests
uv run python -m pytest tests/unit/test_suit_decision_diagnostic.py -v

# Run the diagnostic (after tests pass)
uv run python scripts/internal/suit_decision_diagnostic.py \
  --h2h-dir data/runs/arc_d_r0_h2h_battery_42_20260308_173038 \
  --cf-dataset data/runs/action_value_quick_42_v2/datasets/action_value.parquet \
  --seed 42 \
  --output-dir data/artifacts/r1_5_3

# Pre-PR validation
make check-quiet
```

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| H2H and CF datasets have different deal populations | Use each dataset for its strength: H2H for real gameplay outcomes, CF for counterfactual comparisons |
| Single-rollout noise in CF data | Report confidence intervals; flag if disagreement analysis is ambiguous; optional repeated-rollout subset |
| Error taxonomy categories overlap | Define precise, mutually exclusive criteria; document edge cases |
| OLS prediction reconstruction doesn't match runtime | Validate against a few known predictions from H2H logs |

## Outcome

- PR: #TBD
- Gate decision: **Track B (GBT) or further investigation** — errors spread across calibration range, boundary accounts for only 28.5% of absolute residual (< 60% threshold for Track A)
- Key findings:
  - AV v1 makes 96.5% of suit bids (very conservative), vs R0 at 98.0%
  - Error concentration: clear-set region 43.0%, boundary 28.5%, clear-make 28.5%
  - Wrong contract: 26.5% of suit hands would be better as high/low
  - Bid-level headroom (H13): only 2.3% improvable — level optimization irrelevant
  - Suit bid rate ratio AV v1/R0 = 0.98 — nearly identical bidding frequency
- Notes: Under-bid analysis (62.7% of pass hands have "profitable" suit) is dominated by single-rollout noise — not actionable without repeated rollouts
