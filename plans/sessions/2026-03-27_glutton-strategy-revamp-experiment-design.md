# Glutton Strategy Revamp — Experiment Design

> **Issue:** #1917
> **Status:** Shaped — ready for dispatch
> **Author:** analyst-a
> **Date:** 2026-03-27

## Problem Statement

The GluttonStrategy (`src/bid_euchre/strategy/greedy.py`) plays too
conservatively. It was designed as a 1-trick-lookahead strategy with partner
awareness, trump conservation, and void-creation heuristics — but it has
**no bidding integration**. Its `decide_bid()` is the inherited default
(always pass). When paired with external bidders (OLSa, RanktheTank), the
play strategy doesn't adapt to the bid it's trying to make — a fundamental
mismatch.

### Where Conservatism Lives

Analysis of the GluttonStrategy source (lines 78-547 of `src/bid_euchre/strategy/greedy.py`) reveals
these specific conservatism patterns:

1. **Partner deference is unconditional** (L482-526): When partner is winning,
   Glutton always dumps the cheapest card. It never considers whether the
   trick is *high-value* (late-game trick vs early-game trick) or whether
   securing the trick with a moderate card protects against 4th-seat override.

2. **3rd-seat aggression gating is very conservative** (L451-478): The
   `threats <= 1` check with trump gating means Glutton rarely takes tricks
   in 3rd seat. The threshold was tuned for bidless self-play, not
   auction-mode play where the declaring team needs to hit a trick target.

3. **Lead selection is one-dimensional** (L219-289): Leads are purely
   heuristic (non-trump Aces → draw trump → longest suit). No awareness
   of how many tricks remain, how many the team needs, or whether
   aggressive vs defensive leads would serve the contract better.

4. **No bid-contract awareness whatsoever**: The play strategy receives
   `contract_type` and `trump_suit` but has zero visibility into the
   *bid amount*, the *declaring team*, or the *tricks needed to make*.
   This is the core architectural gap.

5. **Discard logic is purely void-oriented** (L291-327): Discards optimize
   for creating voids (shortest suit, cheapest card) — good for defensive
   play but not optimal when the team is declaring and needs trick-count
   over void creation.

## Recommended Approach: Bid-Aware Glutton (Not Teacher-Student)

### Why Not Teacher-Student From Hosted Play Data?

The task packet asked whether teacher-student from operator play data is
viable. **It is not viable now**, for three reasons:

1. **Data volume**: The hosted play export (`web/export.py`) captures
   decisions per-action from the SQLite database. But the browser game
   is newly deployed — there are at most dozens of human-played games,
   far below the ≥2,000 deals minimum for any statistical inference
   (per `.claude/rules/deferred/05_rigor.md`). Teacher-student needs 10,000+ labeled examples
   to train even a simple model.

2. **Label quality**: Human play decisions from a web game are noisy —
   casual players make suboptimal choices, attention varies, and there's
   no guarantee the human strategy is *better* than Glutton. Teacher-student
   requires a teacher that demonstrably outperforms the student.

3. **Existing infrastructure gap**: The models/ directory has training
   pipelines for *bidding* models (`src/bid_euchre/models/train_olsa.py`, `src/bid_euchre/models/train_bidder.py`)
   but no training pipeline for *play* models. Building one is a separate
   multi-PR initiative.

**Recommendation**: Teacher-student is a future initiative once sufficient
high-quality human play data accumulates. For now, the highest-ROI path is
**parameterized heuristic improvements** to Glutton that make it bid-aware.

### Proposed Intervention: GluttonV2 with Bid Context

Create a `GluttonV2Strategy` (or extend `GluttonIsolatedStrategy` with new
feature flags) that receives bid context and adjusts aggression accordingly.

#### New Information Channel

The key architectural change is passing bid context to the play strategy.
Currently `choose_card()` receives:
- `hand`, `plays_so_far`, `contract_type`, `trump_suit`, `player_index`

The strategy also gets `on_hand_start()` at the start of each hand. This is
where bid context should flow in. Extend the hook signature:

```python
def on_hand_start(
    self,
    starting_hand: List[Card],
    contract_type: str,
    trump_suit: Optional[str],
    player_index: int,
    # NEW: bid context
    bid_amount: Optional[int] = None,  # 1-10 or None (bidless)
    bidder_seat: Optional[int] = None,  # which seat won the auction
    bid_type: str = "regular",  # "regular" | "moon" | "loner"
) -> None:
```

This is backward-compatible (new params default to None/"regular").

#### Aggression Adjustments

With bid context, GluttonV2 computes `tricks_needed` and adjusts:

| Condition | Current Behavior | Proposed V2 Behavior |
|-----------|-----------------|---------------------|
| Declaring team, behind target | Same as defending | More aggressive leads, lower threat threshold for 3rd-seat |
| Declaring team, on target | Same as defending | Status quo (conservative to hold lead) |
| Defending team, opponent near target | Same as declaring | More aggressive trump-in, sacrifice plays |
| 3rd-seat aggression threshold | `threats <= 1` | `threats <= 2` when declaring and behind |
| Lead selection (declaring) | Longest suit | Draw trump more aggressively when holding length |
| Discard (declaring, behind) | Void-creation focus | Higher-value discards to partner if partner leads |

## Experiment Structure

### Phase 1: Baseline Measurement (No Code Changes)

**Goal**: Establish current Glutton performance in auction mode with rigorous
statistical baselines.

#### Experiment 1A: Bidless Trick Capture Rate

Measures raw play quality without bidding confounds.

```yaml
# experiments/configs/glutton_v2_baseline_bidless.yaml
experiment_name: glutton_v2_baseline_bidless
parameters:
  n_per: 50000
  seed: 42
  log_level: hand
  mode: head_to_head_matrix

strategies:
  - name: glutton
    class_name: GluttonStrategy
  - name: greedy
    class_name: GreedyStrategy

matchups:
  - team0: glutton
    team1: greedy
  - team0: greedy
    team1: glutton

scenarios:
  - name: suit_C
    contract_type: suit
    trump_suit: C
  - name: suit_D
    contract_type: suit
    trump_suit: D
  - name: suit_H
    contract_type: suit
    trump_suit: H
  - name: suit_S
    contract_type: suit
    trump_suit: S
  - name: high
    contract_type: high
  - name: low
    contract_type: low
```

**Metrics**: `avg_tricks_team0`, `win_rate_team0`, trick distribution.
**Sample size**: 50,000 deals × 6 scenarios × 2 directions = 600K matchups.
Per `.claude/rules/deferred/05_rigor.md`, 50K exceeds the 2K minimum for bias detection.

**Validation command**:
```bash
uv run python experiments/run_experiment.py \
  --config experiments/configs/glutton_v2_baseline_bidless.yaml \
  --seed 42
```

#### Experiment 1B: Auction Mode Baseline

Measures Glutton's interaction with bidders in auction mode.

```yaml
# experiments/configs/glutton_v2_baseline_auction.yaml
experiment_name: glutton_v2_baseline_auction
parameters:
  n_per: 10000
  seed: 42
  log_level: hand

bidding_policies:
  - name: rankthetank
    class_name: RanktheTank
  - name: olsa
    class_name: OLSaBidder
    params:
      artifact_path: data/artifacts/arc_d/r0/hybrid_r0.json

strategies:
  - name: glutton
    class_name: GluttonStrategy
  - name: greedy
    class_name: GreedyStrategy

scenarios:
  - contract_type: null  # Auction mode
```

**Metrics**: `net_eppd`, `avg_tricks`, `win_rate`, `made_rate` (% bids made),
`set_rate` (% bids set).
**Key question**: Does Glutton make bids at a higher rate than Greedy when
paired with the same bidder? (This reveals whether play quality translates
to contract fulfillment.)

### Phase 2: Implementation (Requires Code Changes)

**Goal**: Build and wire GluttonV2 with bid-context awareness.

#### PR 2A: Wire bid context to play strategy (infrastructure)

**Scope**: `src/bid_euchre/strategy/base.py`, `src/bid_euchre/sim/simulation.py`
- Extend `on_hand_start()` signature with optional `bid_amount`, `bidder_seat`, `bid_type`
- Wire the values from `play_single_hand()` into the strategy hook
- All existing strategies are unaffected (default params)

**Tests**: Existing test suite passes unchanged; new unit test confirms
bid context flows through to a mock strategy.

#### PR 2B: GluttonV2 strategy with bid-aware aggression

**Scope**: `src/bid_euchre/strategy/greedy.py`
- New `GluttonV2Strategy` class (or extend `GluttonIsolatedStrategy` flags)
- `tricks_needed` computation from bid context
- Aggression adjustments per the table above
- Feature flags for each adjustment (for isolation testing)

**Tests**: Unit tests for each feature flag in isolation.

#### PR 2C: Register GluttonV2 in experiment config system

**Scope**: `src/bid_euchre/strategy/__init__.py`, `src/bid_euchre/experiments/config.py`
- Register `GluttonV2Strategy` in `PLAY_STRATEGY_REGISTRY`
- Add experiment YAML configs

### Phase 3: Evaluation (Post-Implementation)

#### Experiment 3A: GluttonV2 Bidless Head-to-Head

Same config as 1A, but with `GluttonV2Strategy` vs `GluttonStrategy`
and `GreedyStrategy`. Triple-matchup matrix.

**Success criterion**: GluttonV2 ≥ Glutton in avg_tricks_team0 across
all scenarios (p < 0.05, paired bootstrap).

#### Experiment 3B: GluttonV2 Auction Mode (bid-play interaction)

Same bidders as 1B, comparing GluttonV2 vs Glutton as the play strategy.

**Success criteria**:
- `made_rate` improvement ≥ 2% (GluttonV2 makes bids more often)
- `net_eppd` improvement with 95% CI excluding zero
- No regression in `set_rate` for defending team

#### Experiment 3C: GluttonV2 Feature Isolation

Extend `experiments/configs/glutton_feature_isolation.yaml` pattern with new V2 feature flags
to measure individual contribution of each aggression adjustment.

**Success criterion**: Each enabled flag individually improves net_eppd
or is neutral (95% CI includes zero but doesn't strongly include negative).

### Sample Size Requirements

| Experiment | n_per | Scenarios | Total Deals | Justification |
|-----------|-------|-----------|-------------|---------------|
| 1A Bidless | 50,000 | 12 (6×2) | 600,000 | Production report standard |
| 1B Auction | 10,000 | 1 | 10,000 per bidder | Sufficient for net_eppd CIs |
| 3A Bidless H2H | 50,000 | 18 (6×3) | 900,000 | Triple-matchup matrix |
| 3B Auction | 10,000 | 1 | 10,000 per combo | Match 1B for comparison |
| 3C Isolation | 100,000 | 6 | 600,000 per flag | Feature isolation needs power |

**Estimated compute time**: ~5 min per 50K deals (from existing benchmark).
Total: ~2 hours for full battery.

## Validation Criteria

### Gate 1 (Phase 1 — Baseline)
- [ ] Bidless H2H reproduces with `--seed 42`
- [ ] Glutton beats Greedy by statistically significant margin (reconfirming prior work)
- [ ] Auction baseline captures `made_rate` and `set_rate` metrics

### Gate 2 (Phase 2 — Implementation)
- [ ] `make check` passes after each PR
- [ ] Bid context flows through to strategy (unit test)
- [ ] GluttonV2 with all flags disabled = identical to Glutton (equivalence test)
- [ ] Each feature flag can be toggled independently

### Gate 3 (Phase 3 — Evaluation)
- [ ] GluttonV2 ≥ Glutton in bidless avg_tricks (p < 0.05)
- [ ] GluttonV2 has higher `made_rate` in auction mode (p < 0.05)
- [ ] No `net_eppd` regression with 95% CI
- [ ] Feature isolation shows no individual flag causes regression

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Bid context wiring breaks existing strategies | HIGH — all experiments affected | Default params maintain backward compat; equivalence test in Gate 2 |
| Aggression thresholds wrong | MEDIUM — GluttonV2 performs worse | Feature isolation (3C) isolates regressions to specific flags |
| `made_rate` not captured in current sim output | MEDIUM — can't evaluate key metric | Check sim output for bid-related tracking (L770-773 suggests it exists) |
| Teacher-student scope creep | LOW — someone adds it to this PR | Explicit out-of-scope declaration in issue |
| Bidless improvements don't transfer to auction mode | MEDIUM | Phase 1 baseline captures both modes; Phase 3 evaluates both |

## PR Decomposition

| PR | Dependencies | Scope | Estimated Size |
|----|-------------|-------|----------------|
| 2A: Wire bid context | None | 2 files (base.py, simulation.py) + tests | Small (< 100 LoC) |
| 2B: GluttonV2 strategy | 2A | 1 file (greedy.py) + tests | Medium (~300 LoC) |
| 2C: Register + configs | 2B | 3 files (__init__.py, config.py, YAML configs) | Small (< 50 LoC) |

PRs 2A → 2B → 2C are sequential (each depends on prior).
Phase 1 baseline experiments can run **before** any code changes (parallel with review).
Phase 3 evaluation runs after 2C merges.

## Out of Scope

- Teacher-student model from human play data (future initiative)
- New training pipeline in `models/` for play strategy learning
- Modifications to any bidding policy (OLSa, RanktheTank, etc.)
- Changes to the simulation engine beyond bid-context wiring
- Moon/loner-specific play adjustments (separate experiment)

## Orchestrator Handoff

### Dispatch Recommendation

**Track**: 3 sequential PRs to an author lane (author-a or author-b).

**Task packets to create**:

1. **PR 2A: Wire bid context to play strategy**
   - `scope_declared`: `src/bid_euchre/strategy/base.py`, `src/bid_euchre/sim/simulation.py`, `tests/unit/test_strategy.py`
   - `validation`: `uv run python -m pytest tests/unit/test_strategy.py tests/integration/test_simulation_validation.py -x`
   - Estimated: 1-2 hours

2. **PR 2B: GluttonV2 strategy with bid-aware aggression**
   - `scope_declared`: `src/bid_euchre/strategy/greedy.py`, `tests/unit/test_glutton.py`
   - `validation`: `uv run python -m pytest tests/unit/test_glutton.py tests/unit/test_strategy_correctness.py -x`
   - Estimated: 3-4 hours

3. **PR 2C: Register GluttonV2 + experiment configs**
   - `scope_declared`: `src/bid_euchre/strategy/__init__.py`, `src/bid_euchre/experiments/config.py`, `experiments/configs/glutton_v2_*.yaml`
   - `validation`: `uv run python experiments/run_experiment.py --config experiments/configs/glutton_v2_baseline_bidless.yaml --seed 42 --dry-run`
   - Estimated: 1 hour

**Baseline experiments** (Phase 1) can be dispatched in parallel to any lane
with experiment-running capability. They require **no code changes**.

## Outcome

*(To be filled after implementation)*
