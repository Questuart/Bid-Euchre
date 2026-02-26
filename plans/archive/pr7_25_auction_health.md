# Plan: PR-7 — 25_auction_health Notebook + 40_ Extraction

Date: 2026-02-25
Status: Draft — awaiting approval
Branch: `feat/r0-nb-7-25-auction-health`
Issues: C49 (new notebook), C39 (seat distributions), C40 (suit breakout), C42 (make rate by bid), C43 (seat-faceted bid accuracy)
Depends: PR-4 (merged as #434)
Est. size: ~250 lines new, ~60 lines removed from 40_

## Objective

Create a dedicated auction health notebook (`25_auction_health.py`) that absorbs §2 (Auction Health) and §4 (Auction Outcomes) from `40_r0_baseline.py`, expands them with the five review-tracked issues, and leverages the existing library functions in `diagnostics/auction_charts.py`.

## Key Design Decisions

### 1. Reuse library chart functions

The existing `plot_auction_health()` and `plot_bidder_performance()` in `src/bid_euchre/diagnostics/auction_charts.py` provide production-quality charts covering:
- Contract selection, bid distribution histogram, auction length (`plot_auction_health`)
- Make rate by contract, make rate curve by bid value with CI, overbid/underbid histogram (`plot_bidder_performance`)

The current 40_ §2/§4 uses inline custom code that duplicates these library functions. The new notebook should call the library functions and supplement with issue-specific analyses (C39 seat distributions, C40 suit breakout, C43 seat-faceted accuracy).

### 2. Data loading: single eval log (not matchup concatenation)

Unlike `50_r0_matchups.py` which loads multiple matchup logs, this notebook follows the same single-log pattern as `10_`, `20_`, `30_` — one `EVAL_LOG_PATH`, one `build_eval_dataset()` call.

### 3. Synthetic fallback scope

Auction fields (`n_bids`, `n_passes`, `auction_rounds`) come from JSONL logs. The synthetic fallback should generate plausible auction metadata so sections don't silently skip in CI/SMOKE mode. Follow the pattern from `20_outcome_health.py` which generates synthetic auction fields.

## File Changes

| File | Action | Scope |
|------|--------|-------|
| `notebooks/arc_d/r0/25_auction_health.py` | **CREATE** | New 8-section notebook (~250 lines) |
| `notebooks/arc_d/r0/25_auction_health.ipynb` | **CREATE** | Jupytext-paired (auto-generated) |
| `notebooks/arc_d/r0/40_r0_baseline.py` | **EDIT** | Remove §2 + §4, replace with cross-ref notes |
| `notebooks/arc_d/r0/40_r0_baseline.ipynb` | **EDIT** | Jupytext sync |

## New Notebook Structure: `25_auction_health.py`

### S0: Configuration & Data Loading (~60 lines)

Standard boilerplate matching sibling notebooks:
- Jupytext header (copy from `20_outcome_health.py`)
- Parameters cell: `EVAL_LOG_PATH`, `MODE`, `RUNG_ID`, `CHART_OUTPUT_DIR`, `SEED`
- CWD resolution block (identical to siblings)
- Eval run discovery cell
- Imports:
  ```python
  import matplotlib.pyplot as plt
  import numpy as np
  import pandas as pd
  from bid_euchre.datasets.eval_dataset import build_eval_dataset
  from bid_euchre.diagnostics.auction_charts import (
      plot_auction_health,
      plot_bidder_performance,
  )
  ```
- Data loading: `build_eval_dataset()` with JSONL primary, synthetic fallback
- Synthetic fallback must include: `winning_bid`, `contract_type`, `trump`, `n_bids`, `n_passes`, `auction_rounds`, `is_bidder`, `made_bid`, `tricks_won`, `bidder_seat`, `dealer_position`, `seat`
- `_data_source` flag, `deal_df` (seat-0 filter for deal-level rows)
- Run metadata print block

### S1: Fail-Fast Validation (~20 lines)

Sanity gates:
- `assert len(df) > 0`
- `assert df["deal_id"].nunique() >= 10` (minimum meaningful sample)
- Row count == 4 * deal count (per-seat invariant)
- Required columns present: `contract_type`, `winning_bid`, `is_bidder`
- Auction columns present when `_data_source == "eval_logs"`: `n_bids`, `n_passes`, `auction_rounds`

### S2: Bid Distribution by Contract (~30 lines)

**Covers:** extracted 40_ §2 (bid distribution) + C40 (suit breakout)

1. Call `plot_auction_health(df)` — library provides contract selection, bid distribution histogram, auction length panels
2. **C40 suit breakout:** For suit contracts, show bid distribution faceted by trump suit:
   ```python
   suit_df = deal_df[deal_df["contract_type"] == "suit"]
   # Bar chart grid: one subplot per trump suit, bid value on x-axis
   ```
3. Print table: contract selection frequency with percentages

### S3: Bidder & Dealer Seat Distributions (~35 lines)

**Covers:** C39 (seat distributions)

1. Bidder seat distribution: bar chart of `bidder_seat` values (0-3), with chi-square test for uniformity
2. Dealer seat distribution: bar chart of `dealer_position`, chi-square test
3. Bid height by dealer seat: box plot or bar chart showing mean `winning_bid` grouped by `dealer_position`, with ANOVA test
4. Cross-tabulation: bidder_seat x contract_type heatmap (are certain seats more likely to bid certain contracts?)

**Statistical tests:**
- Chi-square goodness-of-fit for seat uniformity (expected: 25% each)
- ANOVA for bid height by dealer seat

### S4: Make Rate & Surplus (~30 lines)

**Covers:** extracted 40_ §4 (auction outcomes) + C42 (make rate by bid value)

1. Call `plot_bidder_performance(df)` — library provides make rate by contract, make rate curve by bid value with 95% CI, overbid/underbid histogram
2. **C42 extension:** Print table with per-contract-type make rates, mean surplus, overbid/underbid rates
3. Surplus distribution: faceted by contract_type (suit vs high vs low behave differently)

### S5: Seat-Faceted Bid Accuracy (~35 lines)

**Covers:** C43

1. Make rate by bidder seat: grouped bar chart (seat on x-axis, contract type as hue)
2. Mean surplus by bidder seat: similar grouped chart
3. Statistical test: ANOVA on make rate by seat (check for seat-dependent bid accuracy bias)
4. Table: per-seat, per-contract make rate matrix

### S6: Auction Length & Pass Rate (~25 lines)

Expanded from the inline pass rate computation in 40_ §2:

1. Auction rounds distribution histogram (from `plot_auction_health` panel 3, but also show per-contract)
2. Pass rate computation: `n_passes / (n_bids + n_passes)` per deal (avoids Jensen's inequality vs ratio-of-means)
3. Mean bids and passes per deal, faceted by contract type
4. Scatter: auction length vs winning bid (do higher bids correlate with longer auctions?)

### S7: Summary (~15 lines)

Markdown + print summary:
- Total deals analyzed, data source
- Key findings: most common contract type, mean make rate, any seat bias detected
- Cross-reference to related notebooks (10_ features, 20_ outcomes, 40_ baseline)

## Changes to `40_r0_baseline.py`

### Remove §2 (lines 313–369)

Replace the entire code cell with a markdown cell:
```
# %% [markdown]
# ## §2 Auction Health
#
# Auction health analysis has been extracted to a dedicated notebook.
# See `25_auction_health.py` for bid distributions, seat analysis,
# and auction length diagnostics.
```

### Remove §4 (lines 454–483)

Replace with:
```
# %% [markdown]
# ## §4 Auction Outcomes
#
# Bid accuracy, make rate analysis, and surplus distributions have been
# extracted to `25_auction_health.py` §S4–S5.
```

### Section renumbering

After extraction, 40_ retains:
- §0 Setup (unchanged)
- §1 Deal Health (unchanged)
- §2 Auction Health → **cross-ref note**
- §3 Gameplay Health (unchanged)
- §4 Auction Outcomes → **cross-ref note**
- §5+ all unchanged

No renumbering — keep existing §-numbers to avoid breaking cross-references in other docs/notebooks.

## Implementation Order

1. Create `25_auction_health.py` with full 8-section structure
2. Edit `40_r0_baseline.py` — replace §2 and §4 with cross-ref markdown cells
3. Jupytext sync both notebooks
4. Run `make lint` + `ruff format` on changed files
5. Commit
6. Run `make check-quiet` (Tier 2)
7. Push and create PR

## Validation

1. `make check-quiet` — full Tier 2 (lint + tests + notebook-check + docs-check)
2. `uv run python -m pytest tests/unit/test_notebook_template_contract.py -x -q` — prefix convention test
3. Manual: verify `25_auction_health.py` compiles cleanly (`python -c "import py_compile; py_compile.compile('notebooks/arc_d/r0/25_auction_health.py')"`)
4. Manual: verify 40_ still has all non-auction sections intact

## Trace Matrix

| Issue | Section | Description |
|-------|---------|-------------|
| C49 | all | New auction health notebook |
| C39 | S3 | Bidder/dealer seat distributions |
| C40 | S2 | Suit breakout in bid distribution |
| C42 | S4 | Make rate by bid value chart |
| C43 | S5 | Seat-faceted bid accuracy |
