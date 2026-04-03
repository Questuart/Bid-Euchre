# Simulation vs Browser Game Parity Experiment Plan

**Issue:** [#2229](https://github.com/Questuart/Bid-Euchre/issues/2229)
**Author:** analyst-b
**Date:** 2026-04-03
**Status:** DRAFT

---

## Background

### The Bug History

1. **PR #2126** — Fixed a critical bug where the browser game's `MatchEngine`
   was not calling `on_hand_start()` on the play strategy. GluttonStrategy
   treated every hand as a no-trump "high" contract, meaning bowers were
   valued as ordinary Jacks instead of the highest trump cards.

2. **PR #2194** — Fixed a cross-match state leak where `AIManager` created one
   `GluttonStrategy` instance per model, shared across all concurrent matches.
   `_seen_counts`, `_void_suits_by_seat`, and `_contract_type` leaked between
   games. The fix deep-copies the strategy at engine-build time in
   `web/routes.py::_build_engine()`.

### Why This Matters

The simulation path (`sim/simulation.py`) is the **source of truth** for all
strategy research. If the browser game diverges from it:

- Players experience different AI behavior than what experiments measure
- Strategy improvements validated in experiments may not carry over to gameplay
- Bug reports from browser playtesting may not reproduce in the experiment runner

**No test currently verifies parity between the two paths.** This plan designs
both a one-time experiment and a permanent regression test to close that gap.

---

## Architecture Comparison

### Simulation Path (`sim/simulation.py::play_single_hand`)

| Aspect | Implementation |
|--------|---------------|
| **Strategy per seat** | `strategies` list of 4 Strategy instances (or 1 shared) |
| **Bidding** | Per-seat `BiddingPolicy` or shared `BiddingPolicy` or legacy `Strategy.decide_bid` |
| **Deal generation** | `generate_deal(seed, deal_id)` or caller-provided hands |
| **Dealer derivation** | From `initial_leader`, `rng`, `deal_seed`, or fallback |
| **on_hand_start** | Called once per unique strategy instance (deduplicated by `id(s)`); uses first matching seat's hand |
| **observe_play** | Called once per unique strategy instance for every card played |
| **Trick play** | Direct loop: `strategy.choose_card()` → legality check → `hand.pop()` |
| **Sitting out** | Partner of moon/loner bidder sits out (3-player tricks) |
| **Exchange** | `perform_exchange()` for moon bids |

### Browser Game Path (`hosted_play/engine.py::MatchEngine`)

| Aspect | Implementation |
|--------|---------------|
| **Strategy** | Single `play_strategy` instance for all AI seats (deep-copied per match) |
| **Bidding** | Single `bidding_policy` instance; human at seat 0 bids interactively |
| **Deal generation** | `generate_deal(seed, deal_id)` — same function |
| **Dealer derivation** | `random.Random(seed).randrange(4)` for first hand; rotates each hand |
| **on_hand_start** | `_fire_on_hand_start()` — called once, picks first active AI seat's hand |
| **observe_play** | `_fire_observe_play()` — called after every card play (human and AI) |
| **Trick play** | Step-based: `_advance_ai()` → `choose_card()` → `_process_card_play()` |
| **Sitting out** | Same rule: partner of moon/loner bidder sits out |
| **Exchange** | `perform_exchange()` for AI-only; interactive path for human-involved |

### Key Structural Differences (Potential Divergence Sources)

| # | Difference | Risk | Severity |
|---|-----------|------|----------|
| **D1** | **on_hand_start seat selection**: Sim uses first seat that shares strategy instance; MatchEngine uses first active AI seat ≥ 1. If the starting hand differs between seats, Glutton's `_player_index` and internal state will differ. | Medium | Affects card tracking accuracy |
| **D2** | **Single strategy vs per-seat**: Sim can have distinct strategy instances per seat; MatchEngine uses one for all AI. In self-play (sim), one strategy instance is shared across 4 seats but `on_hand_start` is called once with seat 0's hand. In MatchEngine, seat 0 is human so `on_hand_start` always uses an AI seat. | Medium | `_player_index` always differs |
| **D3** | **observe_play deduplication**: Sim deduplicates by strategy instance identity; MatchEngine calls `_fire_observe_play` for every play. Both fire once per play since MatchEngine only has one strategy instance. | Low | Should be equivalent |
| **D4** | **Dealer derivation**: Sim uses `(initial_leader - 1) % 4` or complex fallback; MatchEngine uses `random.Random(seed).randrange(4)` for first hand, then rotates. | High | Different dealer → different auction order → different contracts |
| **D5** | **Human seat 0**: MatchEngine always has human at seat 0 who bids and plays differently from AI. The sim has all AI. | Structural | Must be controlled for in test design |
| **D6** | **Hand sorting**: MatchEngine calls `sort_hand_for_display()` on the human's hand in-place. This mutates `hand.hands[0]`. Does this affect AI play if the human is sitting out? | Low | Only affects human's hand, not AI |
| **D7** | **Bid processing**: Sim processes bids as BidAction objects with overcall logic; MatchEngine uses `_process_bid()` with bid_rank comparison. The logic should be equivalent but the code paths are distinct. | Medium | Could produce different auction outcomes |

---

## Experiment Design

### Approach: All-AI MatchEngine Harness

The fundamental challenge is that MatchEngine hardcodes a human at seat 0.
To achieve true parity comparison, we need a **test harness that drives
MatchEngine with a deterministic "human" bidding policy and play strategy**
at seat 0, making all 4 seats AI-controlled.

This is the cleanest approach because:
- It eliminates D5 (human seat) as a variable
- It uses the exact same code path the browser game uses
- It can be driven programmatically without HTTP/session overhead

#### Harness Design

```python
class AllAIMatchHarness:
    """Drive MatchEngine with AI at all 4 seats for parity testing.

    Seat 0 (normally human) is controlled by the same bidding_policy
    and play_strategy as the AI seats.
    """

    def __init__(self, engine: MatchEngine,
                 human_bidding_policy: BiddingPolicy,
                 human_play_strategy: Strategy):
        self.engine = engine
        self.human_bidding = human_bidding_policy
        self.human_play = human_play_strategy

    def play_hand(self, state: MatchState) -> MatchState:
        """Play one full hand, submitting human decisions programmatically."""
        while True:
            hand = state.current_hand
            if hand is None or hand.phase in ("complete", "redeal"):
                break

            if hand.current_seat == HUMAN_SEAT:
                if hand.phase == "auction":
                    bid = self._decide_human_bid(hand)
                    state = self.engine.submit_human_bid(state, bid)
                elif hand.phase == "trick_play":
                    card_idx = self._decide_human_card(hand)
                    state = self.engine.submit_human_card(state, card_idx)
                elif hand.phase == "moon_exchange":
                    indices = self._decide_human_exchange(hand)
                    state = self.engine.submit_exchange_selection(state, indices)
            elif hand.paused_after_trick:
                state = self.engine.resume_ai(state)
            else:
                break  # Unexpected state
        return state
```

### Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **Seeds** | 42, 137, 2718 | Multiple seeds to cover varied deal distributions |
| **Hands per seed** | 500 | Enough to hit all contract types including moon/loner (with forced-bid fallback if needed) |
| **Total hands** | 1,500 | Exceeds 2,000-deal minimum (see rigor rules) for bias detection across the 3 seeds |
| **Strategies** | GluttonStrategy (play), FixedBidder or forced-contract for targeted tests | GluttonStrategy is the only stateful strategy; others are pure-functional |
| **Contract coverage** | All 7: suit(C), suit(D), suit(H), suit(S), high, low, moon + loner | Forced-contract mode for targeted coverage; natural auction for integration |

### Two-Phase Experiment

#### Phase 1: Forced-Contract Parity (Eliminates Auction Differences)

Skip the auction entirely. Feed identical pre-dealt hands + fixed contract
into both paths. Compare every card play decision.

**Sim path:**
```python
play_single_hand(
    contract_type=ctype, trump_suit=trump,
    strategies=[glutton, glutton, glutton, glutton],
    hands=generate_deal(seed, deal_id),
    initial_leader=bidder,
)
```

**MatchEngine path:**
Use the AllAIMatchHarness with a FixedBidder that always bids the target
contract. (Requires controlling the auction to produce the desired contract;
alternatively, directly inject state post-auction by manipulating `HandState`.)

**What to log at each decision point:**
- `deal_id`, `trick_number`, `seat`, `hand` (remaining cards), `plays_so_far`
- `legal_indices` (from `get_legal_indices`)
- `chosen_index` (from `choose_card`)
- `chosen_card` (the Card object)

**Comparison:** Exact match on `chosen_index` and `chosen_card` for every
AI decision in every trick.

#### Phase 2: Full Auction Parity (Tests Bidding Path Alignment)

Run the natural auction through both paths with the same bidding policy.
This tests that identical hands + identical bidding policy produces the same
auction outcome and the same subsequent card play.

**Critical alignment requirement:** Both paths must use the same dealer seat
for deal 0. The sim derives dealer from the seed; MatchEngine uses
`random.Random(seed).randrange(4)`. We must verify these produce the same
dealer or normalize them.

**What to log:**
- All Phase 1 fields, plus:
- `dealer_seat`, `auction_transcript` (bid actions per seat)
- `contract_type`, `trump`, `bid_type`
- `sitting_out_seat` (for moon/loner)
- `exchange_given`, `exchange_received` (for moon)

**Comparison:**
1. Auction transcript: exact match on (seat, action, n, contract, bid_type)
2. Contract outcome: exact match on (contract_type, trump, bid_type, bidder_seat)
3. Card plays: exact match per Phase 1

---

## Instrumentation Needed

### Existing Instrumentation

| Path | What Exists | Gap |
|------|-------------|-----|
| **Sim** | `GameLogger.log_trick_end()` logs deal_id, trick_num, leader, plays, winner | Does not log per-card decision (legal_indices, chosen_index) |
| **MatchEngine** | `AIActionEvent` captures turn_number, seat, phase, legal_actions, chosen_action, game_state | **Only for AI seats.** Human seat actions are not captured in the same format |

### New Instrumentation Required

1. **Decision-level logging for both paths** — A lightweight callback/collector
   that records the exact inputs to `choose_card()` and the output, for every
   seat, in both paths. This does NOT modify production code; it uses the
   existing hook points:
   - Sim: Add an `on_card_decision` callback parameter (similar to
     `on_bidding_decision`)
   - MatchEngine: Already has `AIActionEvent`; extend to also capture human
     seat actions when driven by the test harness

2. **Alternatively: direct comparison in test** — Rather than logging to files,
   the regression test can drive both paths in lockstep and compare in-memory.
   This is simpler and more reliable.

**Recommendation:** Option 2 (in-memory comparison in test). No production
instrumentation changes needed. The test itself is the comparison mechanism.

---

## Comparison Method

### Decision Stream Comparison

For each hand, produce an ordered list of decision records:

```python
@dataclass
class DecisionRecord:
    deal_id: int
    trick_num: int
    play_order_in_trick: int  # 0-3
    seat: int
    hand_before: tuple[Card, ...]
    plays_so_far: tuple[tuple[int, Card], ...]
    legal_indices: tuple[int, ...]
    chosen_index: int
    chosen_card: Card
```

Compare the two streams element-by-element. A divergence at position N means
all subsequent decisions are potentially tainted (cascading divergence).

### Divergence Classification

| Type | Description | Severity |
|------|-------------|----------|
| **Auction divergence** | Different bid at same position | CRITICAL — different contract invalidates all card play comparison |
| **Card play divergence** | Different `chosen_index` given identical hand + plays | CRITICAL — proves behavioral difference |
| **Trick outcome divergence** | Different winner despite same plays | BUG — indicates rules implementation difference (should not happen since both delegate to `trick_winner()`) |
| **State drift** | Same decisions but different internal strategy state | WARNING — may cause future divergences |

### Expected Legitimate Differences

1. **`_player_index` in GluttonStrategy**: Sim calls `on_hand_start` with the
   first matching seat (often seat 0 in self-play); MatchEngine calls it with
   the first active AI seat (≥ 1). However, `_player_index` is currently only
   used in debug logging, not in card selection logic. **Verify this.**

2. **Card tracking across hands**: In MatchEngine, `_fire_on_hand_start()`
   resets the strategy once per hand. In the sim, `on_hand_start` is also
   called once per unique strategy instance. Both should produce equivalent
   resets. **Verify that the reset is complete.**

3. **Human hand sorting**: MatchEngine sorts the human's hand for display.
   If the test harness uses the sorted hand for the human's `choose_card`,
   the index may differ from the sim's unsorted hand. **The harness must
   use the hand as-is, not the display-sorted version.**

---

## Regression Test Design

### Location

`tests/integration/test_sim_browser_parity.py`

### Test Structure

```python
class TestSimBrowserParity:
    """Verify simulation and MatchEngine produce identical AI decisions."""

    @pytest.fixture
    def glutton(self):
        return GluttonStrategy()

    @pytest.fixture
    def fixed_bidder(self):
        """Bidder that always bids a specified contract."""
        # Use FixedBidder or a simple deterministic policy
        ...

    @pytest.mark.parametrize("contract_type,trump", [
        ("suit", "S"), ("suit", "H"), ("suit", "D"), ("suit", "C"),
        ("high", None), ("low", None),
    ])
    @pytest.mark.parametrize("seed", [42, 137, 2718])
    def test_forced_contract_parity(self, seed, contract_type, trump, glutton):
        """Phase 1: Same hands + same contract → identical card plays."""
        for deal_id in range(50):
            hands = generate_deal(seed, deal_id)
            sim_decisions = run_sim_hand(hands, contract_type, trump, glutton)
            engine_decisions = run_engine_hand(hands, contract_type, trump, glutton)
            assert sim_decisions == engine_decisions, (
                f"Divergence at seed={seed} deal={deal_id} "
                f"contract={contract_type} trump={trump}"
            )

    @pytest.mark.parametrize("seed", [42, 137, 2718])
    def test_full_auction_parity(self, seed):
        """Phase 2: Same hands + same bidding policy → identical outcomes."""
        bidding_policy = ...  # Deterministic policy
        for deal_id in range(50):
            hands = generate_deal(seed, deal_id)
            sim_result = run_sim_with_auction(hands, seed, deal_id, bidding_policy)
            engine_result = run_engine_with_auction(hands, seed, deal_id, bidding_policy)
            assert sim_result.auction == engine_result.auction
            assert sim_result.decisions == engine_result.decisions

    @pytest.mark.parametrize("seed", [42, 137])
    def test_moon_exchange_parity(self, seed):
        """Moon exchange produces identical post-exchange hands."""
        ...

    @pytest.mark.parametrize("seed", [42, 137])
    def test_loner_parity(self, seed):
        """Loner 3-player trick play matches between paths."""
        ...
```

### Helper Functions

```python
def run_sim_hand(hands, contract_type, trump, strategy) -> list[DecisionRecord]:
    """Run a hand through sim/simulation.py and capture all decisions."""
    # Create a decision-capturing wrapper around strategy.choose_card
    decisions = []
    wrapper = DecisionCapture(strategy, decisions)
    play_single_hand(
        contract_type=contract_type,
        trump_suit=trump,
        strategies=[wrapper, wrapper, wrapper, wrapper],
        hands=[list(h) for h in hands],
        initial_leader=0,  # Fixed for comparability
    )
    return decisions

def run_engine_hand(hands, contract_type, trump, strategy) -> list[DecisionRecord]:
    """Run a hand through MatchEngine and capture all decisions."""
    # Use AllAIMatchHarness with a FixedBidder
    # Extract decisions from engine.last_ai_events + human decisions
    ...
```

### Test Characteristics

| Property | Value |
|----------|-------|
| Test file | `tests/integration/test_sim_browser_parity.py` |
| Parameterized | 3 seeds × 6 contracts × 50 deals = 900 forced-contract hands |
| Marks | `@pytest.mark.integration` (included in `make check`) |
| Runtime estimate | ~30-60 seconds (no model loading for forced-contract phase) |
| Dependencies | No model artifacts needed for Phase 1 (Glutton is rule-based) |

---

## Risks and Edge Cases

### High Risk

1. **Dealer derivation mismatch (D4)**: The sim and MatchEngine derive the
   first dealer differently from the seed. Phase 1 (forced contract)
   sidesteps this by skipping the auction. Phase 2 must explicitly align
   dealer seats or the auction will diverge from the start.

2. **on_hand_start with different seats (D1)**: If Glutton's card selection
   is influenced by `_player_index` (currently only used for debug), this
   could cause false divergences. Must verify `_player_index` is not used in
   any decision path.

### Medium Risk

3. **Moon exchange hand mutation**: Both paths use `perform_exchange()` but
   the hand arrays may be mutated in different order. The post-exchange hand
   content should be identical but card ordering may differ, affecting
   `choose_card` index results.

4. **Double-deck duplicate cards**: With two copies of each card, the
   `choose_card` index can be ambiguous when two identical cards are legal.
   Both paths should choose the same index because they use the same
   strategy, but the hand ordering must be identical.

5. **Model artifact loading for Phase 2**: Testing Bud Bot and OLSa bidding
   parity requires loading model artifacts. If artifacts are not available in
   CI, Phase 2 bidding tests need a `skipif` guard or a simpler deterministic
   bidding policy.

### Low Risk

6. **Floating-point determinism**: GluttonStrategy is purely rule-based (no
   floating-point scoring). Bidding models (GBT, OLS) use floating-point
   predictions that should be deterministic given the same input features.

7. **Hand display sorting**: MatchEngine sorts the human hand for display.
   The test harness must ensure it uses the pre-sort hand for `choose_card`.

---

## Estimated Effort

### PR Decomposition

| PR | Scope | Files | Estimated Size |
|----|-------|-------|----------------|
| **PR 1: Test harness + Phase 1** | AllAIMatchHarness, DecisionCapture wrapper, forced-contract parity tests | `tests/integration/test_sim_browser_parity.py` (new), possibly `tests/integration/conftest.py` | Medium (200-300 lines) |
| **PR 2: Phase 2 auction parity** | Dealer alignment, auction comparison, full-path tests | Same test file + possibly `tests/integration/conftest.py` | Medium (150-250 lines) |
| **PR 3: Moon/loner parity** | Exchange parity, sitting-out parity, 3-player trick tests | Same test file | Small (100-150 lines) |

**Total: 3 PRs, ~500-700 lines of test code, no production code changes expected.**

If Phase 1 reveals actual divergences (not just test setup issues), additional
fix PRs will be needed. The fixes would be in `hosted_play/engine.py` to align
with the sim path.

### Dependencies

- PR 1 has no dependencies (Glutton is built-in, no model artifacts)
- PR 2 depends on PR 1 (reuses harness) and may need model artifacts
- PR 3 depends on PR 1 (reuses harness)

PRs 2 and 3 are independent of each other and can be parallelized.

---

## Validation Commands

### During Implementation (Tier 1)

```bash
uv run python -m pytest tests/integration/test_sim_browser_parity.py -v
```

### Before PR (Tier 2)

```bash
make check-quiet
```

### Smoke Test

```bash
uv run python -m pytest tests/integration/test_sim_browser_parity.py \
    -k "test_forced_contract_parity[42-suit-S]" -v
```

---

## Outcome

_To be filled after implementation._
