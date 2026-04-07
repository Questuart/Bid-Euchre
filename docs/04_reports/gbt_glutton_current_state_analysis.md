# Current-State Analysis: GBT Bidding & Glutton Play in Browser Game vs Research Framework

> **Date:** 2026-04-06
> **Author:** analyst-c
> **Task:** `73327187832f` — Current-state analysis: GBT vs Glutton
> **Issues Cross-Referenced:** #2504, #2506, #2502, #2149, #2290, #2300, #2389, #2391

## Executive Summary

The browser game deploys two AI models — **Bud Bot** (GBT bidder + Glutton play)
and **OLSa Easy** (OLS action-value bidder + Glutton play). Both share the
identical `GluttonStrategy` play engine but differ in bidding. The research
framework offers a richer roster of bidders (OLSa, HybridOLSa, ActionValueBidder,
TwoStageActionValueBidder, FilteredGBTBidder) and a feature-isolated Glutton
twin (`GluttonIsolatedStrategy`) for A/B experimentation. This report maps the
exact configuration of each deployment surface, catalogs known behavioral gaps
from live play, and recommends prioritized follow-on research.

---

## 1. Bidding: Browser Game vs Research Framework

### 1.1 Browser Game Bidder Deployment

The browser game roster is configured in `web/ai_manager.py` and loaded at
startup via `web/config.py`:

| Model | UI Name | Bidder Class | Artifact Schema | Artifact Default Path |
|-------|---------|--------------|----------------|-----------------------|
| `bud_bot` | "Bud Bot" | `GBTActionValueBidder` | `action_value_gbt_v1` | `data/artifacts/arc_d_v2/r3/training_artifact_gbt_av.json` |
| `olsa` | "OLSa (Easy)" | `ActionValueBidder` | `action_value_olsa_v1` | `data/artifacts/arc_d_v2/r3/training_artifact_full_ols_av.json` |

**Key observations:**
- Both use **Arc D v2 R3** artifacts — the final lineage output.
- **Neither** uses `FilteredGBTBidder`. The browser game runs the **raw,
  unfiltered** GBT model. The post-inference filters (Enhancement A:
  suppress dealer overcalls; Enhancement B: suppress partner nudges) exist
  in the codebase (`src/bid_euchre/strategy/bidding.py:2623`) but are
  **not wired into production**.
- Both bidders are instantiated with `skip_behavioral_check=True` — the
  self-play validation that normally fires during experiment runs is
  bypassed for startup speed.
- The default model is `bud_bot` (`web/config.py:71`).

### 1.2 Research Framework Bidder Roster

The experiment config system (`src/bid_euchre/experiments/config.py`) registers
a much richer bidder set:

| Class | Schema | Purpose |
|-------|--------|---------|
| `OLSaBidder` | `olsa_v1` / `hybrid_olsa_v1` | Original tricks-won predictor. Floors predicted tricks to get bid amount. No net-differential scoring. |
| `HybridOLSaBidder` | `hybrid_olsa_v1` | Gaussian EV with net-differential scoring. Analytically computes E[net_points] using residual variance. Supports `risk_lambda`, `bid_bonus`, `bid_level_search`, offensive/defensive sub-models. |
| `ActionValueBidder` | `action_value_olsa_v1` | Per-contract OLS models predicting E[net_points] directly. Supports context features, partner features, positional features, interaction features, moon/loner actions. **This is what the browser calls "OLSa."** |
| `GBTActionValueBidder` | `action_value_gbt_v1` | Same architecture as `ActionValueBidder` but uses sklearn GBT regressors instead of OLS dot-product. Loads `.joblib` model files. **This is what the browser calls "Bud Bot."** |
| `TwoStageActionValueBidder` | `two_stage_action_value_v1` | Two-stage decomposition: P(make) logistic + conditional payoff OLS for suits; standard OLS for high/low. |
| `FilteredGBTBidder` | Wraps `GBTActionValueBidder` | Post-inference filter wrapper. `flag_a`: suppress dealer overcalls when team hasn't bid. `flag_b`: suppress same-suit +1 nudge of partner as dealer. |

### 1.3 Critical Differences: Browser vs Research

| Dimension | Browser Game | Research |
|-----------|-------------|----------|
| **Bidder for "Bud Bot"** | `GBTActionValueBidder` (raw) | Can use `FilteredGBTBidder` with Enhancement A/B filters |
| **Bidder for "OLSa"** | `ActionValueBidder` (net-points OLS) | Can also use `OLSaBidder` (tricks-won OLS) or `HybridOLSaBidder` (Gaussian EV) |
| **Overbid mitigation** | **None** — raw GBT output passes through unfiltered | `FilteredGBTBidder.flag_a` suppresses dealer overcalls where team has no standing bid |
| **Partner nudge mitigation** | **None** | `FilteredGBTBidder.flag_b` suppresses +1 same-suit partner bids |
| **Behavioral validation** | Skipped (`skip_behavioral_check=True`) | Run by default on experiment instantiation |
| **Contract types** | Full game (suit/high/low/moon/loner) | Configurable per experiment — can force specific contract types |
| **Artifact versioning** | Fixed at deploy time via env var | Experiment configs can point to any artifact |

### 1.4 The FilteredGBTBidder Gap

The `FilteredGBTBidder` was designed in `plans/sessions/2026-04-06_glutton_gbt_quicksim_experiment.md`
and implemented in PR #2559+. Its experiment configs (`glutton_gbt_ablation_auction.yaml`)
test Enhancement A (don't overbid as last bidder) and Enhancement B (don't nudge
partner's suit) against the raw GBT baseline.

**The browser game still uses the raw GBT.** This means the overbid behavior
documented in #2149 (Ace bids 5S as last bidder, takes 4, gets set) is **still
present in production**. The `FilteredGBTBidder` with `flag_a=True` would
directly address this — it's a one-line change in `web/ai_manager.py`:

```python
# Current (raw GBT):
bidding_policy=GBTActionValueBidder(artifact_path=path, ...)
# Fix (filtered GBT):
bidding_policy=FilteredGBTBidder(artifact_path=path, flag_a=True)
```

However, this should be blocked on the experiment ablation results confirming
that Enhancement A produces a statistically significant improvement.

---

## 2. Card Play: GluttonStrategy in Browser vs Research

### 2.1 Browser Game Play Strategy Deployment

Both AI models use the same play engine:

```python
# web/ai_manager.py:141 (OLSa) and :177 (Bud Bot)
play_strategy=GluttonStrategy()
```

All constructor defaults apply:
- `cash_winners_on_lead=False` (default)
- `debug=False`

The engine deep-copies the strategy per match (`web/routes.py:122`) so
concurrent games don't share mutable card-tracking state.

**Strategy version:** `GLUTTON_STRATEGY_VERSION = "0.8.1"` (greedy.py:28).

### 2.2 Research Framework Play Strategy

The experiment config system supports multiple play strategy configurations:

| Class | Key Feature Flags | Purpose |
|-------|------------------|---------|
| `GluttonStrategy` | `cash_winners_on_lead` (bool, default False) | Production play strategy. All features always on. |
| `GluttonIsolatedStrategy` | 10 independent feature flags (all default False) | A/B testing: toggle `smart_leads`, `smart_discards`, `third_seat_aggression`, `partner_awareness`, `sure_winner_cover`, `partner_check`, `trump_gating`, `probabilistic_trump_in`, `lead_bower`, `cash_winners_on_lead` |
| `GreedyStrategy` | None | Baseline: 1-trick lookahead, no partner awareness |

### 2.3 The `cash_winners_on_lead` Gap

The `cash_winners_on_lead` flag was added in v0.8.0 (PR #2534, Cash-A) and
controls three new behaviors:

1. **Fix 0.5:** Cash established sure winners first on lead (suit contracts).
   Picks sure winner from shortest effective suit.
2. **Fix 0.75 (1b):** Draw opponent trump before cashing side winners.
   Only fires when `_opponents_might_hold_trump()` returns True.
3. **Fix 2:** Draw trump from the top (highest sure-winner trump, not lowest).
   Uses `_draw_trump_lead()` with sure-winner-first fallback.
4. **High/Low fallback:** Cash sure winners before longest-suit heuristic.

**The browser game has `cash_winners_on_lead=False`.** This means none of
the Cash-A improvements are active in production. The flag was deliberately
defaulted to False per the plan:

> "Merging Cash-A must not change production behavior. The operator will
> flip this to True after a manual proving run."
> — `src/bid_euchre/strategy/greedy.py:137-141`

The experiment configs `glutton_gbt_ablation_play.yaml` and
`cash_a_h2h_auction.yaml` / `cash_a_h2h_per_contract.yaml` are designed to
prove this flag before the production flip.

### 2.4 GluttonStrategy Feature Inventory

Features that are **always on** in `GluttonStrategy` (cannot be toggled):

| Feature | Description | First Introduced |
|---------|-------------|-----------------|
| Partner awareness | Don't overkill partner's winning card; discard cheap instead | Original |
| Sure-winner cover | In 3rd seat, cover vulnerable partner with cheapest sure winner | Original |
| 3rd-seat aggression | Take tricks in 3rd seat when threat count <= 1 (with trump gating) | Original |
| Trump-in protection | In 3rd seat, trump to protect partner from void 4th seat with trump | Original |
| Card tracking | Double-deck aware seen_counts, void inference via observe_play() | Original |
| Smart leads | Non-trump aces from shortest suit, draw trump >= 4, longest suit | Original |
| Smart discards | Cheapest non-trump by value (post-#2300 fix, no void creation) | #2300 fix |
| Lead bower | Right bower when holding both bowers + 5+ trump | PR #2167 |

Features behind `cash_winners_on_lead` flag (**off in production**):

| Feature | Description | Addresses |
|---------|-------------|-----------|
| Sure-winner lead priority | Cash sure winners before any other lead heuristic | #2502, #2504, #2506 |
| Draw-trump-first | Lead trump when opponents might still hold trump | #2506 Defect F |
| Draw trump from top | `_draw_trump_lead`: highest sure-winner trump, not lowest | #2506 Defect B |
| High/Low sure-winner fallback | Cash sure winners in High/Low before longest-suit lead | #2502, #2504 |

---

## 3. Known Behavioral Gaps — Issue Cross-Reference

### 3.1 Issue Map

| Issue | Title | Root Cause | Status | Addressed By |
|-------|-------|-----------|--------|-------------|
| **#2149** | AI overbids as last bidder | Raw GBT has no position-aware bid suppression | **Open** | `FilteredGBTBidder.flag_a` (not yet deployed to browser) |
| **#2502** | AI misplays Low contracts — conserves 10s | `_choose_lead()` has no sure-winner priority (Defect A). Card valuation (`rank_strength`) is actually correct for Low. | **Open** | `cash_winners_on_lead=True` (not yet deployed) |
| **#2504** | AI holds ace until last trick in High | Same Defect A — no sure-winner lead priority | **Open** | `cash_winners_on_lead=True` (not yet deployed) |
| **#2506** | AI doesn't continue established suit | Defect A (no sure-winner priority) + Defect B (leads lowest trump) + Defect F (stops drawing trump mid-game) | **Open** | `cash_winners_on_lead=True` (not yet deployed) |
| **#2290** | Glutton wastes Aces, conserves 10s | Combined Defect A + stale discard heuristic (pre-#2300 fix). The #2300 fix addressed the discard side; sure-winner lead is still missing. | **Open (reopened)** | Partially addressed by #2300 (discard fix). Fully by `cash_winners_on_lead`. |
| **#2300** | Glutton suit preservation bias | `_choose_discard()` void-creation logic dumped Aces from non-void suits | **Open** (research) | Discard side fixed in code (cheapest non-trump by value). Lead side: `cash_winners_on_lead`. Research: validate simplification vs context-aware void. |
| **#2389** | Glutton bid-context awareness | Play strategy has no concept of declaring vs defending | **Open** (deferred research) | ~200 LOC / 3 PR effort. Not a go-live blocker. |
| **#2391** | Validate glutton discard/lead simplification | Go-live discard simplification needs simulation proof | **Open** (research) | Experiment design exists but not yet run |

### 3.2 Root Cause Taxonomy

All play-side issues trace to **three structural deficits** in `GluttonStrategy`:

```
                    ┌─────────────────────────────────────┐
                    │   Deficiency 1: No Sure-Winner      │
                    │   Lead Priority (Defect A)          │
                    │   #2502, #2504, #2506, #2290        │
                    │   Fix: cash_winners_on_lead=True    │
                    └─────────────────────────────────────┘
                    ┌─────────────────────────────────────┐
                    │   Deficiency 2: Wrong Trump Drawing │
                    │   (Defects B, F)                    │
                    │   #2506                             │
                    │   Fix: cash_winners_on_lead=True    │
                    │   + _draw_trump_lead (v0.8.1)      │
                    └─────────────────────────────────────┘
                    ┌─────────────────────────────────────┐
                    │   Deficiency 3: No Bid Context      │
                    │   (Declaring vs Defending)          │
                    │   #2389                             │
                    │   Fix: ~200 LOC, 3 PRs, deferred   │
                    └─────────────────────────────────────┘
```

The bidding issue (#2149) is structurally independent — it's a property of
`GBTActionValueBidder`, not `GluttonStrategy`.

### 3.3 What Has Already Been Fixed

| Fix | PR | Description | In Production? |
|-----|----|-------------|---------------|
| Discard simplification | (part of #2300 investigation) | `_choose_discard()` now dumps cheapest non-trump by value, removing broken void-creation logic | **Yes** — in GluttonStrategy code |
| Cash-A code merged | PR #2534 | Added `cash_winners_on_lead` flag, sure-winner lead priority, draw-trump-first, draw trump from top | **Code merged, flag OFF** |
| Claim 1 fix | PR #2559 | `_draw_trump_lead` sure-winner-first fallback (prevents burning LB when 2nd RB is out) | **Code merged, behind flag** |
| Strategy versioning | PR #2529 | Added `GLUTTON_STRATEGY_VERSION` and `play_strategy_version` column for cohort tracking | **Yes** |
| FilteredGBTBidder | PR #2559+ | `flag_a` / `flag_b` wrapper for GBT post-inference filters | **Code merged, not used in browser** |

---

## 4. Architecture: How Bidding and Play Interact

### 4.1 The Segregation Model

Bidding and play are **completely segregated** in both the browser game and
the research framework:

```
Browser Game Flow:
  MatchEngine(bidding_policy, play_strategy)
     │
     ├── Auction phase: bidding_policy.choose_bid(obs)
     │     └── Returns BidAction (amount, contract_type, trump_suit)
     │         No information flows back to play_strategy
     │
     └── Trick play phase: play_strategy.choose_card(hand, plays, ...)
           └── Knows contract_type, trump_suit (set by auction result)
               Does NOT know: who bid, what was bid, bid history,
               declaring vs defending role
```

This segregation means:
1. The play strategy cannot adapt its aggression based on whether the team
   is declaring (need N tricks) or defending (maximize trick capture).
2. The bidding model cannot learn from play outcomes within a hand.
3. Improving one does not automatically improve the other.

### 4.2 Information Flow in the Browser Engine

```
MatchEngine
  ├── start_match(seed, ai_model)
  │     └── Calls _deal_new_hand() → _advance_ai()
  │
  ├── _advance_ai()
  │     ├── Auction: bidding_policy.choose_bid(BiddingObservation)
  │     │     obs includes: hand, current_high_bid, seat, dealer_seat,
  │     │                   bid_history, current_high_suit, current_high_type
  │     │
  │     └── Trick play: play_strategy.choose_card(hand, plays_so_far,
  │           contract_type, trump_suit, player_index)
  │           + on_hand_start() lifecycle hook (resets per-hand state)
  │           + observe_play() lifecycle hook (card tracking, void inference)
  │
  └── _notify_strategy_hand_start() / _notify_strategy_play()
        └── Polymorphic dispatch to Strategy subclass hooks
```

### 4.3 Shared Strategy Instance Model

In the browser game, `AIManager` creates one `GluttonStrategy()` instance
per model at startup. Each match gets a `copy.deepcopy()` of that instance
(`web/routes.py:122`). This is critical because `GluttonStrategy` has
mutable per-hand state (`_seen_counts`, `_void_suits_by_seat`, contract
context). Without deep-copy, concurrent matches would corrupt each other's
card tracking.

In the research framework, the experiment runner creates one strategy
instance per cell/matchup/scenario. There's no deep-copy concern because
experiments run serially within a process.

---

## 5. Prioritized Follow-On Research

### Priority 1 (High Impact, Low Risk): Deploy Cash-A

**What:** Flip `cash_winners_on_lead=True` in `web/ai_manager.py` for both
Bud Bot and OLSa.

**Why:** This is the single change that addresses #2502, #2504, #2506, and
#2290 simultaneously. The code is already merged (PR #2534 + #2559). The
only gate is the experiment proving run.

**Experiment needed:**
- Run `experiments/configs/cash_a_h2h_auction.yaml` (EXP 2) to measure
  aggregate impact under realistic auction conditions.
- Run `experiments/configs/cash_a_h2h_per_contract.yaml` (EXP 1) to
  confirm suit-contract signal dominates.
- Run `experiments/configs/glutton_gbt_ablation_play.yaml` to isolate
  Cash-A flag flip vs Claim 1 fix contribution.

**Acceptance criteria:** Statistically significant improvement (p < 0.05)
in net_points for Cash-A ON vs OFF across 5,000+ paired deals.

**Risk:** Low. The flag is battle-tested via code review and the Claim 1
fix prevents the left-bower-burn regression.

**Estimated effort:** 1 PR (flag flip in `web/ai_manager.py`), gated on
experiment results.

### Priority 2 (High Impact, Low Risk): Deploy FilteredGBTBidder

**What:** Replace `GBTActionValueBidder` with `FilteredGBTBidder(flag_a=True)`
in `web/ai_manager.py` for Bud Bot.

**Why:** Directly addresses #2149 (AI overbids as last bidder). The filter
suppresses dealer overcalls when the team hasn't bid and there's a standing
opponent contract.

**Experiment needed:**
- Run `experiments/configs/glutton_gbt_ablation_auction.yaml` to measure
  Enhancement A's contribution against raw GBT baseline.
- Consider EXP 2 (auction H2H) with `FilteredGBTBidder` to measure
  aggregate competitive impact.

**Acceptance criteria:** Statistically significant reduction in set rate
for dealer-seat bids in the Enhancement A cell vs raw GBT, across 5,000+
paired deals with auction mode.

**Risk:** Low. The filter only fires on the dealer seat and only when the
team has no standing bid. It's a conservative post-inference guard.

**Decision point:** Whether to also enable `flag_b` (partner nudge
suppression). The experiment config includes a B2 cell (both flags) for
comparison.

**Estimated effort:** 1 PR (bidder swap in `web/ai_manager.py`), gated on
experiment results.

### Priority 3 (Medium Impact, Medium Effort): Discard Simplification Validation

**What:** Run the three-approach experiment from #2391:
1. Current (production): cheapest non-trump by value (post-#2300 fix)
2. Smart void: void-creation gated on trump holdings
3. Context-aware: void-creation only when declaring with trump

**Why:** The go-live discard simplification (#2300 fix) removed void creation
entirely. A context-aware version (void only when holding trump to ruff)
could recover 0.1-0.3 tricks/deal without the Ace-dumping regression.

**Experiment needed:** 2,000+ deals per approach × 6 scenarios, paired
bootstrap comparison.

**Estimated effort:** 2 PRs (implement context-aware discard variant in
`GluttonIsolatedStrategy`, run experiment).

### Priority 4 (Medium Impact, High Effort): Bid-Context Awareness

**What:** Give `GluttonStrategy` awareness of declaring vs defending role.
When declaring, play more aggressively to meet contract. When defending,
maximize trick capture to set the opponents.

**Why:** #2389 identifies this as a real gap. The play strategy currently
treats every hand identically regardless of bidding role.

**Implementation sketch** (from #2389 analysis):
- Pass `bidder_seat` and `bid_amount` to `on_hand_start()`
- Add role-aware aggression thresholds
- Declaring: lead trump more aggressively, cash winners faster
- Defending: trump-in more freely, don't waste cards on hopeless tricks

**Estimated effort:** ~200 LOC, 3 PRs. Needs simulation validation.

**Risk:** Medium. This touches the `Strategy` base class interface. Must
land in both `GluttonStrategy` and `GluttonIsolatedStrategy`.

### Priority 5 (High Impact, Very High Effort): Strategy Unification

**What:** Explore unifying bidding and play so the play strategy can
leverage the bidding model's hand evaluation.

**Why:** Currently the GBT bidder knows hand strength and partnership
context, but this information dies after the auction. A unified model
could make play decisions informed by why the contract was chosen.

**Estimated effort:** Research initiative. Multiple PRs across the
`Strategy` base class, `MatchEngine`, and experiment infrastructure.

**Risk:** High. Architectural change that crosses multiple modules.

---

## 6. Experiment Infrastructure Status

### 6.1 Configs Ready to Run

| Config | Purpose | Status |
|--------|---------|--------|
| `glutton_gbt_ablation_play.yaml` | Cash-A flag flip + Claim 1 fix isolation | Ready (prereqs met: v0.8.1 code merged) |
| `glutton_gbt_ablation_auction.yaml` | FilteredGBTBidder Enhancement A/B isolation | Ready (FilteredGBTBidder implemented) |
| `cash_a_h2h_auction.yaml` | Cash-A aggregate impact under auction | Ready |
| `cash_a_h2h_per_contract.yaml` | Cash-A per-contract-type impact | Ready |

### 6.2 Configs Needed

| Config | Purpose | Blocks |
|--------|---------|--------|
| Discard 3-approach comparison | #2391 validation | Priority 3 |
| Bid-context A/B | #2389 validation | Priority 4 |
| FilteredGBT browser H2H | Production FilteredGBTBidder validation | Priority 2 |

---

## 7. Deployment Checklist

When experiment results are available, the production deployment sequence is:

1. **Cash-A flag flip** (Priority 1):
   ```python
   # web/ai_manager.py — both _try_load_olsa and _try_load_bud_bot
   play_strategy=GluttonStrategy(cash_winners_on_lead=True)
   ```
   - 1 line change per model (2 total)
   - Bumps visible strategy version to 0.8.1 (already set in code)
   - Gated on experiment proving

2. **FilteredGBTBidder deployment** (Priority 2):
   ```python
   # web/ai_manager.py — _try_load_bud_bot only
   from bid_euchre.strategy.bidding import FilteredGBTBidder
   bidding_policy=FilteredGBTBidder(artifact_path=path, flag_a=True)
   ```
   - 1 import + 1 line change
   - OLSa stays on `ActionValueBidder` (no filter needed — OLSa is
     already more conservative)
   - Gated on experiment proving

3. **Strategy version tracking** — already operational. Each match records
   `play_strategy_version` in the database (`web/db.py:89`), enabling
   per-version cohort analysis after deployment.

---

## 8. Risks and Scope Traps

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Cash-A flag flip changes Glutton behavior for ALL AI opponents simultaneously | Both Bud Bot and OLSa are affected | This is by design — both share GluttonStrategy. The improvement benefits all. |
| FilteredGBTBidder may suppress valid bids | Could make Bud Bot too conservative | Enhancement A only fires when team has no standing bid and dealer overcalls into an opponent contract. Narrow scope. Monitor post-deploy set rates. |
| Experiment infrastructure dependency | Can't deploy without proving runs | Experiment configs are ready to run. ~5 min total compute for all four configs. |
| `GluttonIsolatedStrategy` divergence | Research twin must track production changes | Both classes are in the same file (`greedy.py`) and share version constant. The `draw_trump_lead_legacy` research flag is documented for cleanup. |
| Concurrent match deep-copy correctness | `GluttonStrategy(cash_winners_on_lead=True)` has same mutable state as False | Deep-copy in `web/routes.py:122` handles this. No architectural change needed. |

---

## 9. Summary Table: What's Built vs What's Deployed

| Component | Code Status | Browser Deployed? | Experiment Proven? |
|-----------|------------|-------------------|-------------------|
| `GluttonStrategy` base (v0.8.1) | Merged | Yes | Baseline proven via prior arc_d_v2 lineage |
| `cash_winners_on_lead` (Cash-A) | Merged, flag OFF | **No** | Configs ready, not yet run |
| `_draw_trump_lead` fix (Claim 1) | Merged, behind Cash-A flag | **No** | Configs ready, not yet run |
| `FilteredGBTBidder` | Merged | **No** | Configs ready, not yet run |
| Enhancement A (suppress dealer overcalls) | Merged in FilteredGBTBidder | **No** | Configs ready, not yet run |
| Enhancement B (suppress partner nudges) | Merged in FilteredGBTBidder | **No** | Configs ready, not yet run |
| Bid-context awareness | Not implemented | **No** | Not designed yet |
| Strategy unification | Not implemented | **No** | Research initiative |

---

## Outcome

Analysis complete. This document is the deliverable for task packet
`73327187832f`. The recommended next step is to run the four ready
experiment configs (Priorities 1-2) and use the results to gate the
Cash-A flag flip and FilteredGBTBidder deployment.
