import json
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from bid_euchre.core.cards import Card
from bid_euchre.core.rules import get_legal_indices
from bid_euchre.logging.game_logger import GameLogger, LogLevel
from bid_euchre.sim.simulation import simulate_many_hands
from bid_euchre.strategy.baselines import AlwaysHighestLegalStrategy


def _read_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _card_key(card: Card) -> tuple[str, str]:
    return (card.suit, card.rank)


def _parse_hand_end_hands(hands_payload) -> list[list[Card]]:
    """
    hands_payload schema: 4 hands, each card as [suit, rank]
    Example: [[["H","A"],["S","T"],...], [...], [...], [...]]
    """
    assert hands_payload is not None, "Expected hand_end to include hands (schema v3+)"
    assert len(hands_payload) == 4
    parsed: list[list[Card]] = []
    for seat_hand in hands_payload:
        cards = [Card(suit=s, rank=r) for (s, r) in seat_hand]
        parsed.append(cards)
    return parsed


def _assert_deal_integrity(seat_hands: list[list[Card]]) -> None:
    # 4 seats × 10 cards = 40 cards total
    assert len(seat_hands) == 4
    assert all(len(h) == 10 for h in seat_hands), f"Expected 10 cards per seat, got {[len(h) for h in seat_hands]}"
    all_cards = [c for h in seat_hands for c in h]
    assert len(all_cards) == 40, f"Expected 40 cards dealt, got {len(all_cards)}"

    # Double-deck: each (suit, rank) should appear exactly 2 times (or at least never >2)
    counts = Counter((_card_key(c) for c in all_cards))
    assert all(v <= 2 for v in counts.values()), f"Found card with count >2: {counts}"


def _assert_trick_records(trick_recs: list[dict]) -> None:
    # Expect exactly 10 trick_end records with trick_num 0..9
    assert len(trick_recs) == 10, f"Expected 10 trick_end records, got {len(trick_recs)}"
    nums = sorted(r["trick_num"] for r in trick_recs)
    assert nums == list(range(10)), f"Expected trick_num 0..9, got {nums}"

    for r in trick_recs:
        plays = r["plays"]
        assert isinstance(plays, list)
        assert len(plays) == 4, f"Expected 4 plays per trick, got {len(plays)}"
        # Each play: [player_idx, suit, rank]
        for p in plays:
            assert isinstance(p, list) and len(p) == 3, f"Bad play shape: {p}"
            player_idx, suit, rank = p
            assert player_idx in [0, 1, 2, 3]
            assert suit in ["C", "D", "H", "S"]
            assert rank in ["T", "J", "Q", "K", "A"]
        assert r["winner"] in [0, 1, 2, 3]


def _assert_card_conservation(seat_hands: list[list[Card]], trick_recs: list[dict]) -> None:
    dealt = Counter((_card_key(c) for h in seat_hands for c in h))

    played_cards = []
    played_by_player = Counter()
    for tr in trick_recs:
        for player_idx, suit, rank in tr["plays"]:
            played_cards.append((suit, rank))
            played_by_player[player_idx] += 1

    played = Counter(played_cards)

    # 40 plays total, 10 per player
    assert sum(played.values()) == 40, f"Expected 40 plays, got {sum(played.values())}"
    assert all(played_by_player[i] == 10 for i in range(4)), f"Expected 10 plays per player, got {played_by_player}"

    # Every dealt card is played exactly once (multiset equality, handles double-deck duplicates)
    assert played == dealt, f"Played multiset != dealt multiset\nDealt: {dealt}\nPlayed: {played}"


def _assert_legality(seat_hands: list[list[Card]], trick_recs: list[dict], contract: str, trump: str | None) -> None:
    """
    Reconstruct hand state and verify each played card was legal via get_legal_indices.
    This checks follow-suit enforcement as a post-condition.
    """
    hands = [list(h) for h in seat_hands]  # mutable copies

    for tr in sorted(trick_recs, key=lambda r: r["trick_num"]):
        plays_so_far: list[tuple[int, Card]] = []
        for player_idx, suit, rank in tr["plays"]:
            card = Card(suit=suit, rank=rank)

            # Card must exist in player's current hand (handle duplicates by index search)
            try:
                idx = next(i for i, c in enumerate(hands[player_idx]) if c == card)
            except StopIteration:
                raise AssertionError(f"Played card {card} not found in player {player_idx} hand at time of play")

            legal = get_legal_indices(
                hand=hands[player_idx],
                plays_so_far=plays_so_far,
                contract_type=contract,
                trump_suit=trump,
            )
            assert idx in legal, (
                f"Illegal play detected. "
                f"contract={contract}, trump={trump}, trick={tr['trick_num']}, player={player_idx}, card={card}\n"
                f"legal_indices={legal}, hand={hands[player_idx]}, plays_so_far={plays_so_far}"
            )

            # Apply play
            played_card = hands[player_idx].pop(idx)
            plays_so_far.append((player_idx, played_card))

    # After 10 tricks, all hands should be empty
    assert all(len(h) == 0 for h in hands), f"Expected all hands empty after play, got {[len(h) for h in hands]}"


@pytest.mark.parametrize("contract_type,trump_suit,deal_seed", [
    ("suit", "H", 4242),
    ("high", None, 4243),
    ("low", None, 4244),
])
def test_engine_invariants_via_trick_logs(tmp_path: Path, contract_type: str, trump_suit: str | None, deal_seed: int):
    """
    Integration invariant test:
    - Deal integrity (40 cards; double-deck duplicate bounds; 10 per player)
    - Trick integrity (10 tricks; 4 plays per trick; trick_num 0..9)
    - Card conservation (played multiset == dealt multiset; 10 plays per player)
    - Legality post-check (every card played was legal per get_legal_indices)
    
    Parametrized across all contract types to catch contract-specific bugs.
    """
    log_path = tmp_path / f"invariants_{contract_type}_{deal_seed}.jsonl"

    logger = GameLogger(run_id="test_invariants", strategy_id="always_highest", level=LogLevel.TRICK).open(str(log_path))

    # Keep this small/fast; determinism comes from deal_seed + deterministic strategy.
    simulate_many_hands(
        n=1,
        contract_type=contract_type,
        trump_suit=trump_suit,
        deal_seed=deal_seed,
        strategy=AlwaysHighestLegalStrategy(),
        logger=logger,
    )

    logger.close()

    records = _read_jsonl(log_path)

    # Group by deal_id
    by_deal = defaultdict(list)
    for r in records:
        if r.get("event") in {"hand_end", "trick_end"}:
            by_deal[r["deal_id"]].append(r)

    assert len(by_deal) == 1, f"Expected exactly 1 deal_id in logs, got {list(by_deal.keys())}"
    deal_id = next(iter(by_deal.keys()))
    deal_recs = by_deal[deal_id]

    hand_ends = [r for r in deal_recs if r["event"] == "hand_end"]
    trick_ends = [r for r in deal_recs if r["event"] == "trick_end"]

    assert len(hand_ends) == 1, f"Expected 1 hand_end record, got {len(hand_ends)}"
    hand_end = hand_ends[0]

    seat_hands = _parse_hand_end_hands(hand_end.get("hands"))

    _assert_deal_integrity(seat_hands)
    _assert_trick_records(trick_ends)
    _assert_card_conservation(seat_hands, trick_ends)
    _assert_legality(seat_hands, trick_ends, contract=hand_end["contract"], trump=hand_end.get("trump"))
