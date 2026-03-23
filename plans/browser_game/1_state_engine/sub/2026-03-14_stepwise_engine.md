# SP-1-01: Stepwise Match Engine

**ID:** SP-1-01
**Parent:** Phase 1 — State Engine
**Status:** complete
**Governing plan:** `plans/browser_game/governing_plan.md`
**Created:** 2026-03-14

---

## Goal

Build a step-based match engine in `src/bid_euchre/hosted_play/` that pauses
at human turns and auto-advances AI turns. The engine delegates ALL rule
evaluation to existing `core/` functions — no logic duplication.

## Files to Create

| File | Lines (est.) | Purpose |
|------|-------------|---------|
| `src/bid_euchre/hosted_play/__init__.py` | ~10 | Package exports |
| `src/bid_euchre/hosted_play/state.py` | ~120 | State dataclasses |
| `src/bid_euchre/hosted_play/engine.py` | ~300 | MatchEngine step machine |
| `tests/unit/hosted_play/__init__.py` | ~1 | Test package |
| `tests/unit/hosted_play/test_engine.py` | ~250 | Comprehensive tests |

Total: 5 files, ~680 lines.

## State Dataclasses (`state.py`)

```python
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from bid_euchre.core.cards import Card

@dataclass
class TrickState:
    leader: int                              # seat that leads this trick
    plays: List[Tuple[int, Card]] = field(default_factory=list)

@dataclass
class TrickResult:
    leader: int
    plays: List[Tuple[int, Card]]
    winner: int                              # seat index

@dataclass
class HandState:
    phase: str                               # "auction" | "trick_play" | "complete" | "redeal"
    hands: List[List[Card]]                  # 4 hands (10 cards each at start)
    dealer_seat: int
    deal_id: int

    # Auction state
    auction: List[dict] = field(default_factory=list)  # [{seat, n, action, contract, bid_type}, ...]
    current_high_bid: int = 0
    bidder_seat: Optional[int] = None
    winning_bid: Optional[int] = None
    contract_type: Optional[str] = None
    trump: Optional[str] = None

    # Trick play state
    current_trick: Optional[TrickState] = None
    completed_tricks: List[TrickResult] = field(default_factory=list)
    tricks_team0: int = 0                    # seats (0, 2)
    tricks_team1: int = 0                    # seats (1, 3)

    # Scoring (filled on completion)
    points_team0: int = 0
    points_team1: int = 0

    # Turn tracking
    current_seat: int = 0                    # whose turn it is
    turn_number: int = 0                     # monotonic counter for idempotency

@dataclass
class MatchState:
    seed: int
    ai_model: str
    score_human: int = 0                     # team (0, 2) cumulative
    score_ai: int = 0                        # team (1, 3) cumulative
    hands_played: int = 0
    current_hand: Optional[HandState] = None
    status: str = "active"                   # "active" | "complete"
    winner: Optional[str] = None             # "human" | "ai" | None
    dealer_seat: int = 0                     # rotates each hand
    deal_id: int = 0                         # increments each hand
```

## Engine Interface (`engine.py`)

```python
from bid_euchre.core.rules import get_legal_indices, trick_winner
from bid_euchre.scoring import compute_points
from bid_euchre.sim.deals import generate_deal
from bid_euchre.strategy.base import Strategy
from bid_euchre.strategy.bidding import BiddingPolicy, BiddingObservation, BidAction

HUMAN_SEAT = 0
MATCH_TARGET = 52

class MatchEngine:
    def __init__(self, bidding_policy: BiddingPolicy, play_strategy: Strategy):
        self.bidding_policy = bidding_policy
        self.play_strategy = play_strategy

    def start_match(self, seed: int, ai_model: str) -> MatchState:
        """Create match, deal first hand, auto-advance AI until human action."""

    def submit_human_bid(self, state: MatchState, bid: BidAction) -> MatchState:
        """Process human bid, then auto-advance AI until next human action."""

    def submit_human_card(self, state: MatchState, card_index: int) -> MatchState:
        """Process human card play, then auto-advance AI until next human action."""

    def get_legal_bids(self, state: MatchState) -> List[BidAction]:
        """Legal bids for the current seat (strictly increasing)."""

    def get_legal_plays(self, state: MatchState) -> List[int]:
        """Legal card indices for the current seat. Delegates to get_legal_indices()."""

    def get_visible_state(self, state: MatchState) -> dict:
        """State visible to human: own hand, current trick, scores, but NOT other hands."""

    # --- Internal methods ---

    def _advance_ai(self, state: MatchState) -> MatchState:
        """Auto-play all AI turns until human's turn or hand/match end."""

    def _deal_new_hand(self, state: MatchState) -> MatchState:
        """Generate deal, set up auction, set current_seat to first bidder."""

    def _process_bid(self, state: MatchState, seat: int, bid: BidAction) -> MatchState:
        """Record bid, advance auction state."""

    def _process_auction_end(self, state: MatchState) -> MatchState:
        """Determine contract/declarer or trigger redeal."""

    def _process_card_play(self, state: MatchState, seat: int, card_index: int) -> MatchState:
        """Play card, advance trick state."""

    def _process_trick_end(self, state: MatchState) -> MatchState:
        """Determine winner via trick_winner(), start next trick or end hand."""

    def _process_hand_end(self, state: MatchState) -> MatchState:
        """Compute points via compute_points(), update match score, check ±52."""

    @staticmethod
    def serialize(state: MatchState) -> dict:
        """JSON-serializable dict. Cards as [suit, rank] pairs."""

    @staticmethod
    def deserialize(data: dict) -> MatchState:
        """Restore MatchState from serialized dict."""
```

## Critical Delegation Points

These are the exact functions the engine MUST call — never reimplement:

| Operation | Function | Module |
|-----------|----------|--------|
| Deal cards | `generate_deal(seed, deal_id)` | `bid_euchre.sim.deals` |
| Legal plays | `get_legal_indices(hand, plays_so_far, contract_type, trump_suit)` | `bid_euchre.core.rules` |
| Trick winner | `trick_winner(plays, contract_type, trump_suit)` | `bid_euchre.core.rules` |
| Hand scoring | `compute_points(winning_bid, bidder_position, tricks_team0, tricks_team1)` | `bid_euchre.scoring` |
| AI bid | `bidding_policy.choose_bid(BiddingObservation(...))` | `bid_euchre.strategy.bidding` |
| AI card play | `play_strategy.choose_card(hand, plays_so_far, contract_type, trump_suit, player_index)` | `bid_euchre.strategy.base` |

## State Machine Transitions

```
start_match()
    └→ _deal_new_hand()
        └→ HandState.phase = "auction"
            └→ _advance_ai() [AI bids until human's turn]
                └→ PAUSE: awaiting human bid

submit_human_bid()
    └→ _process_bid(seat=0, bid)
        ├→ More bidders remain → _advance_ai() until next human action
        └→ Auction complete (4 bids/passes) → _process_auction_end()
            ├→ All pass → HandState.phase = "redeal"
            │   └→ _deal_new_hand() [new dealer, new deal_id]
            └→ Contract set → HandState.phase = "trick_play"
                └→ _advance_ai() until human plays (or human leads)
                    └→ PAUSE: awaiting human card

submit_human_card()
    └→ _process_card_play(seat=0, card_index)
        ├→ Trick incomplete → _advance_ai() until next human action
        └→ Trick complete (4 plays) → _process_trick_end()
            ├→ More tricks remain → _advance_ai() until next human action
            └→ Hand complete (10 tricks) → _process_hand_end()
                ├→ Match not over → _deal_new_hand() → _advance_ai()
                └→ Match over (±52) → MatchState.status = "complete"
```

## Auction Rules (from RULES.md §3)

- Bid order: `(dealer+1)%4, (dealer+2)%4, (dealer+3)%4, dealer`
- Strictly increasing: `bid.n > current_high_bid` or pass (`bid.n == 0`)
- Exactly 4 actions (one per seat), then auction ends
- Contract types: `"suit"` (with trump), `"high"` (no trump, A high), `"low"` (no trump, 10 high)
- All pass → redeal (no tricks, no points, advance dealer)

## Edge Cases

1. **Human is dealer and wins auction** → human leads first trick (RULES.md §5.1: declarer leads)
2. **All-pass with human as first bidder** → human passes, AI seats also pass, auto-redeal
3. **Match ends mid-game** → after hand scoring, check ±52 before dealing
4. **Human has only one legal play** → still require explicit submission (no auto-play)
5. **Consecutive redeals** → keep dealing until someone bids. Dealer rotates each redeal.
6. **Duplicate cards in trick** → earlier play wins. `trick_winner()` handles this.
7. **Left bower effective suit** → `get_legal_indices()` handles bower suit-following

## Serialization Contract

Cards serialize as `[suit, rank]` (e.g., `["S", "A"]`). All state fields
must round-trip through `serialize()` → `deserialize()` without loss.

## Required Tests (`test_engine.py`)

1. **Full hand flow** — deal → auction (human bids 5S) → 10 tricks → hand scoring
2. **All-pass redeal** — all 4 pass → new hand dealt, dealer advanced
3. **Match win** — score reaches +52, status becomes "complete", winner = "human"
4. **Match loss** — score reaches -52, status becomes "complete", winner = "ai"
5. **Legal plays match core** — for several game states, verify `get_legal_plays()` matches `get_legal_indices()` output
6. **Scoring matches core** — verify hand points match `compute_points()` output
7. **Serialization round-trip** — serialize mid-hand state, deserialize, verify equality
8. **Idempotent turn_number** — submitting same turn twice returns same state
9. **Dealer rotation** — dealer advances correctly across multiple hands
10. **Human leads after winning auction** — verify first trick leader is correct
11. **Visible state hides other hands** — `get_visible_state()` shows only seat 0's cards

## Validation Command

```bash
uv run python -m pytest tests/unit/hosted_play/test_engine.py -v
```

## Outcome

**Completed 2026-03-23.** All deliverables shipped across three merged PRs:

| PR | Title | Key Deliverables |
|----|-------|-----------------|
| #1380 | browser-game: lock v1 serving contract and add hosted-play state foundations | `state.py` with dataclasses + JSON serialization helpers, `schema.sql`, serving contract |
| #1392 | browser-game: implement Phase 1 MatchEngine core (engine.py) | `engine.py` (450 lines) — full step-based engine, `test_engine.py` (683 lines) — all 11 required tests + bonus |
| #1402 | test: add comprehensive hosted-play state serialization coverage | Additional serialization test coverage for state dataclasses |

**Files created:**
- `src/bid_euchre/hosted_play/state.py` — State dataclasses (TrickState, TrickResult, HandState, MatchState)
- `src/bid_euchre/hosted_play/engine.py` — MatchEngine with full step-based state machine
- `tests/unit/hosted_play/test_engine.py` — 11 required tests + TestBidOrder, TestMatchDeterminism
- `tests/unit/hosted_play/test_state.py` — State serialization round-trip tests

**All delegation points honored:** `generate_deal`, `get_legal_indices`, `trick_winner`, `compute_points`, `BiddingPolicy.choose_bid`, `Strategy.choose_card` — no logic duplication.
