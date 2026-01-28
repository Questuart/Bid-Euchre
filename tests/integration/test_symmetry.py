"""
Integration tests: Seat permutation symmetry.

These tests verify that the game engine treats all seats symmetrically.
Rotating the hands should rotate the results accordingly.

Key insight: Test symmetry by permuting a FIXED deal, not by re-running
RNG with different seat mappings (which changes RNG consumption order).

Key invariants tested:
- Rotating hands by 2 preserves team membership (seats 0,2 vs 1,3)
- Rotating hands produces rotated trick winners
- No hardcoded seat assumptions in the engine
"""

from typing import List

import pytest

from bid_euchre.core.cards import Card
from bid_euchre.core.rules import trick_winner
from bid_euchre.sim.deals import generate_deal
from bid_euchre.sim.simulation import play_single_hand
from bid_euchre.strategy.baselines import (
    AlwaysHighestLegalStrategy,
    AlwaysLowestLegalStrategy,
)


def _rotate_hands(hands: List[List[Card]], rotation: int) -> List[List[Card]]:
    """Rotate hands by a given amount. Seat i gets hand (i - rotation) % 4."""
    n = len(hands)
    return [hands[(i - rotation) % n] for i in range(n)]


def _rotate_seat(seat: int, rotation: int) -> int:
    """Rotate a seat index."""
    return (seat + rotation) % 4


class TestSeatRotationSymmetry:
    """Tests for seat rotation invariance."""

    def test_rotation_by_2_preserves_teams(self) -> None:
        """Rotating by 2 keeps teams intact (0,2 stay together, 1,3 stay together).

        Team0 = seats 0, 2
        Team1 = seats 1, 3

        After rotation by 2:
        - New seat 0 gets old seat 2's hand (still Team0)
        - New seat 2 gets old seat 0's hand (still Team0)
        - Team trick totals should be identical
        """
        seed = 42
        deal_id = 0
        original_hands = generate_deal(seed=seed, deal_id=deal_id)
        rotated_hands = _rotate_hands(original_hands, rotation=2)

        strategy = AlwaysHighestLegalStrategy()

        # Run with original hands
        result_orig = play_single_hand(
            contract_type="suit",
            trump_suit="H",
            strategy=strategy,
            hands=[list(h) for h in original_hands],
            deal_seed=seed,
            initial_leader=0,
        )
        t0_orig, t1_orig = result_orig[0], result_orig[1]

        # Run with rotated hands (rotation by 2)
        # New leader should be rotated too
        result_rot = play_single_hand(
            contract_type="suit",
            trump_suit="H",
            strategy=strategy,
            hands=[list(h) for h in rotated_hands],
            deal_seed=seed,
            initial_leader=2,  # Old seat 0 is now at seat 2
        )
        t0_rot, t1_rot = result_rot[0], result_rot[1]

        # With rotation by 2, team composition is preserved
        # So team trick counts should match
        assert t0_orig == t0_rot, (
            f"Team0 tricks differ after rotation by 2: {t0_orig} vs {t0_rot}"
        )
        assert t1_orig == t1_rot, (
            f"Team1 tricks differ after rotation by 2: {t1_orig} vs {t1_rot}"
        )

    def test_rotation_by_1_swaps_teams(self) -> None:
        """Rotating by 1 swaps team membership.

        After rotation by 1:
        - New seat 0 gets old seat 3's hand (was Team1)
        - New seat 1 gets old seat 0's hand (was Team0)
        - Team assignments swap: new Team0 = old Team1, new Team1 = old Team0
        """
        seed = 42
        deal_id = 0
        original_hands = generate_deal(seed=seed, deal_id=deal_id)
        rotated_hands = _rotate_hands(original_hands, rotation=1)

        strategy = AlwaysHighestLegalStrategy()

        # Run with original hands
        result_orig = play_single_hand(
            contract_type="suit",
            trump_suit="H",
            strategy=strategy,
            hands=[list(h) for h in original_hands],
            deal_seed=seed,
            initial_leader=0,
        )
        t0_orig, t1_orig = result_orig[0], result_orig[1]

        # Run with rotated hands (rotation by 1)
        result_rot = play_single_hand(
            contract_type="suit",
            trump_suit="H",
            strategy=strategy,
            hands=[list(h) for h in rotated_hands],
            deal_seed=seed,
            initial_leader=1,  # Old seat 0 is now at seat 1
        )
        t0_rot, t1_rot = result_rot[0], result_rot[1]

        # With rotation by 1, teams swap
        # Old Team0 (seats 0,2) becomes new Team1 (seats 1,3)
        # Old Team1 (seats 1,3) becomes new Team0 (seats 0,2)
        assert t0_orig == t1_rot, (
            f"Expected old Team0 ({t0_orig}) = new Team1 ({t1_rot})"
        )
        assert t1_orig == t0_rot, (
            f"Expected old Team1 ({t1_orig}) = new Team0 ({t0_rot})"
        )


class TestTrickWinnerSymmetry:
    """Tests for trick_winner function symmetry."""

    def test_trick_winner_rotation_invariance(self) -> None:
        """Rotating play order should rotate the winner accordingly."""
        trump_suit = "H"

        # Original plays
        plays_orig = [
            (0, Card(suit="C", rank="A")),
            (1, Card(suit="C", rank="K")),
            (2, Card(suit="C", rank="Q")),
            (3, Card(suit="C", rank="T")),
        ]

        winner_orig = trick_winner(plays_orig, "suit", trump_suit)
        assert winner_orig == 0, "Ace should win"

        # Rotate plays by 1 (player indices shift)
        plays_rot1 = [
            (1, Card(suit="C", rank="A")),
            (2, Card(suit="C", rank="K")),
            (3, Card(suit="C", rank="Q")),
            (0, Card(suit="C", rank="T")),
        ]

        winner_rot1 = trick_winner(plays_rot1, "suit", trump_suit)
        assert winner_rot1 == 1, "Rotated Ace holder (seat 1) should win"

    def test_trick_winner_all_rotations(self) -> None:
        """Winner rotates correctly for all 4 rotations."""
        trump_suit = "S"

        # Cards in order of strength for this trick
        cards = [
            Card(suit="H", rank="A"),  # Winner
            Card(suit="H", rank="K"),
            Card(suit="H", rank="Q"),
            Card(suit="H", rank="T"),
        ]

        for rotation in range(4):
            plays = [
                ((i + rotation) % 4, cards[i])
                for i in range(4)
            ]

            winner = trick_winner(plays, "suit", trump_suit)
            expected_winner = rotation  # The Ace holder's seat
            assert winner == expected_winner, (
                f"Rotation {rotation}: expected winner {expected_winner}, got {winner}"
            )


class TestContractSymmetry:
    """Tests that different contracts maintain symmetry."""

    @pytest.mark.parametrize("contract_type,trump_suit", [
        ("suit", "H"),
        ("suit", "S"),
        ("high", None),
        ("low", None),
    ])
    def test_rotation_symmetry_across_contracts(
        self, contract_type: str, trump_suit: str | None
    ) -> None:
        """All contract types should exhibit rotation symmetry."""
        seed = 123
        deal_id = 5
        original_hands = generate_deal(seed=seed, deal_id=deal_id)

        strategy = AlwaysLowestLegalStrategy()

        # Original
        result_orig = play_single_hand(
            contract_type=contract_type,
            trump_suit=trump_suit,
            strategy=strategy,
            hands=[list(h) for h in original_hands],
            deal_seed=seed,
            initial_leader=0,
        )
        t0_orig, t1_orig = result_orig[0], result_orig[1]

        # Rotation by 2 (preserves teams)
        rotated_hands = _rotate_hands(original_hands, rotation=2)
        result_rot = play_single_hand(
            contract_type=contract_type,
            trump_suit=trump_suit,
            strategy=strategy,
            hands=[list(h) for h in rotated_hands],
            deal_seed=seed,
            initial_leader=2,
        )
        t0_rot, t1_rot = result_rot[0], result_rot[1]

        assert (t0_orig, t1_orig) == (t0_rot, t1_rot), (
            f"{contract_type}/{trump_suit}: rotation by 2 should preserve team tricks. "
            f"Original: ({t0_orig}, {t1_orig}), Rotated: ({t0_rot}, {t1_rot})"
        )


class TestEdgeCases:
    """Edge case tests for symmetry."""

    def test_all_same_strategy_is_symmetric(self) -> None:
        """When all players use the same strategy, teams should be balanced over many deals."""
        seed = 42
        strategy = AlwaysHighestLegalStrategy()

        t0_total = 0
        t1_total = 0
        n_deals = 100

        for deal_id in range(n_deals):
            hands = generate_deal(seed=seed, deal_id=deal_id)
            result = play_single_hand(
                contract_type="suit",
                trump_suit="H",
                strategy=strategy,
                hands=[list(h) for h in hands],
                deal_seed=seed,
                initial_leader=deal_id % 4,  # Rotate leader
            )
            t0_total += result[0]
            t1_total += result[1]

        total = t0_total + t1_total
        t0_ratio = t0_total / total

        # With symmetric strategy and many deals, should be close to 50%
        # Allow 40-60% range
        assert 0.40 <= t0_ratio <= 0.60, (
            f"Team0 ratio {t0_ratio:.2%} outside expected 40-60% range"
        )

    def test_identity_rotation_is_noop(self) -> None:
        """Rotation by 0 should produce identical results."""
        seed = 42
        deal_id = 0
        hands = generate_deal(seed=seed, deal_id=deal_id)
        rotated = _rotate_hands(hands, rotation=0)

        strategy = AlwaysHighestLegalStrategy()

        result1 = play_single_hand(
            contract_type="suit",
            trump_suit="H",
            strategy=strategy,
            hands=[list(h) for h in hands],
            deal_seed=seed,
            initial_leader=0,
        )

        result2 = play_single_hand(
            contract_type="suit",
            trump_suit="H",
            strategy=strategy,
            hands=[list(h) for h in rotated],
            deal_seed=seed,
            initial_leader=0,
        )

        assert result1[:2] == result2[:2], "Rotation by 0 changed results"

    def test_full_rotation_is_noop(self) -> None:
        """Rotation by 4 should produce identical results (full cycle)."""
        seed = 42
        deal_id = 0
        hands = generate_deal(seed=seed, deal_id=deal_id)
        rotated = _rotate_hands(hands, rotation=4)

        strategy = AlwaysHighestLegalStrategy()

        result1 = play_single_hand(
            contract_type="suit",
            trump_suit="H",
            strategy=strategy,
            hands=[list(h) for h in hands],
            deal_seed=seed,
            initial_leader=0,
        )

        result2 = play_single_hand(
            contract_type="suit",
            trump_suit="H",
            strategy=strategy,
            hands=[list(h) for h in rotated],
            deal_seed=seed,
            initial_leader=0,
        )

        assert result1[:2] == result2[:2], "Rotation by 4 changed results"
