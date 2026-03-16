# Arc D v2 — R3 Rung Plan (Phase B)

**Status:** PROPOSED
**Lineage:** arc_d_v2
**Rung:** r3 (moon/loner action space expansion)

## 1. Objective

Expand the action space to include moon and loner bid types alongside regular
bids. Test whether models learn when the fixed +/-20 (moon) or +/-40 (loner)
payoff is worth the risk vs a regular bid at a lower level.

R3 is fundamentally different from R0*-R2: it does not add state features --
it expands the **action space**. The 59 state features from R2 are unchanged.
Two new action features (`is_moon`, `is_loner`) join the existing `bid_n` and
`bid_n_sq`.

Phase A (engine expansion) is complete. This plan covers Phase B only:
standard rung execution (Steps 0-9).

## 2. Model Roster

Same as R0/R1/R2 -- see `plans/arc_d_v2/roster.json`.
Per LA-4, FULL mode uses the trimmed roster: gbt_av, selected_two_stage_av,
full_ols_av, modeloespecifico.

## 3. Context Bundle

R3 context: hand + partner + position + opponent (unchanged from R2).
- 39 hand features (frozen)
- 6 partner features (v2 suit-relative, from R1)
- 2 position features (LA-1: auction_position, is_dealer)
- 12 opponent features (6 left + 6 right, from R2)
- Total: 59 state features (unchanged from R2)

R3 action features (expanded):
- `bid_n` -- bid level (1-10)
- `bid_n_sq` -- bid level squared
- `is_moon` -- 1 if evaluating a moon bid, 0 otherwise
- `is_loner` -- 1 if evaluating a loner bid, 0 otherwise

Uses `--feature-set full` (same as R2).

## 4. Hypotheses

See `plans/arc_d_v2/r3/hypotheses.json`.

## 5. Execution

Managed by `scripts/internal/run_rung.py --rung r3`.
Per Amendment LA-3, R3 runs at QUICK scale first.

### 5.1 Dataset Generation

```bash
uv run python scripts/internal/generate_action_value_dataset.py \
  --seed 42 \
  --mode <SMOKE|QUICK|FULL> \
  --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json \
  --output-dir data/runs/arc_d_v2/r3/datasets/ \
  --include-moon-loner
```

The `--include-moon-loner` flag enables counterfactual evaluation of moon and
loner actions. The card exchange uses deterministic heuristic policies (see
lineage plan section 6.4.4).

### 5.2 Training

All models train on the same expanded action-value dataset. The action feature
vector now includes `is_moon` and `is_loner` indicators. Moon and loner
actions always have `bid_n=10` and `bid_n_sq=100`.

### 5.3 Evaluation Batteries

H2H and comparator batteries run as normal. Models may bid moon or loner
during simulation if their EV estimate exceeds regular bids. The existing
battery infrastructure handles any legal action selected by the bidder.

## 6. Implementation Notes

- Card exchange simulation during counterfactual dataset generation follows
  the fixed heuristic policies defined in lineage plan section 6.4.4.
- Loner trick play uses 3-player trick resolution (partner sits out).
- Scoring: moon make = +20, fail = -20; loner make = +40, fail = -40.
  Defending team always scores their tricks won.
- The anchor (hybrid_r0_full) does NOT bid moon/loner -- it predates the
  action space expansion. This means H2H comparisons vs anchor test whether
  the expanded action space helps or hurts overall bidding quality.

## 7. R3-Specific Analysis

Beyond the standard report suite, R3 analysis should examine:
1. **Moon/loner bid rates** -- how often each model chooses moon vs loner vs
   regular-10 (requires new behavior_summary columns or SHAP analysis)
2. **Moon/loner make rates** -- when models bid moon/loner, how often do they
   make it (from game logs)
3. **Decision comparison** -- how often does GBT choose moon where OLS chooses
   regular? (Step 3b SHAP + game log analysis)
4. **Dealer position effect** -- do models learn the dealer takeover risk?
   (`is_dealer` feature importance for moon/loner actions)

Note: Some R3-specific metrics (moon_rate, loner_rate, moon_make_rate) are
not yet in the canonical CSV table schema. These will need to be extracted
from game log JSONL data during Step 7 or via supplementary analysis.
Hypotheses H3, H4, and H8 are flagged as potentially requiring table schema
extensions. If the pipeline does not produce these columns by execution time,
they should be evaluated manually from game logs and recorded in the decision
report.

## Outcome

_To be filled after execution._
