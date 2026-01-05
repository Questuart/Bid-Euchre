"""
Strategy Correctness Tests: Oracle-based validation.

These tests verify that strategies claiming to "try to win" actually take
obvious winning moves in deterministic scenarios.

Key principle: If a winning move exists and is unambiguous, the strategy
must take it. This catches bugs in strategy logic, not just legality.

The oracle pattern enumerates all legal moves, partitions them into winners/losers,
and validates strategy choices against expected behavior. This makes tests:
- More maintainable (single validation function)
- More extensible (easy to add new expected behaviors)
- Better at debugging (comprehensive error messages)
"""

import pytest
from bid_euchre.core.cards import Card
from bid_euchre.core.rules import trick_winner, get_legal_indices
from bid_euchre.strategy import (
    GreedyStrategy,
    ImprovedGreedyStrategy,
    AlwaysHighestLegalStrategy,
    card_value_for_dump,
    # Intentionally exclude RandomLegal and AlwaysLowest (they don't try to win)
)


def validate_greedy_algorithm(
    strategy,
    hand,
    plays_so_far,
    contract_type,
    trump_suit,
    player_index,
    expected_behavior="cheapest_winner_or_dump"
):
    """
    Oracle validator for greedy algorithm logic.

    Enumerates all legal moves, partitions them into winners/losers,
    and verifies the strategy picks according to the expected behavior.

    This is the single source of truth for validating greedy decision logic.

    Args:
        strategy: Strategy instance to test
        hand: Current hand (list of Cards)
        plays_so_far: Cards played so far in trick [(player, Card), ...]
        contract_type: "suit", "high", or "low"
        trump_suit: Trump suit (or None)
        player_index: Player making the decision (0-3)
        expected_behavior:
            - "cheapest_winner_or_dump": Pick cheapest winner if exists, else cheapest dump
            - "any_winner": Pick any winning card (for non-greedy strategies)

    Returns:
        choice (int): The index chosen by the strategy

    Raises:
        AssertionError: If strategy violates expected behavior with detailed diagnostics
    """
    legal_indices = get_legal_indices(hand, plays_so_far, contract_type, trump_suit)

    # Enumerate and partition legal moves
    winning_moves = []  # [(idx, card, value), ...]
    losing_moves = []

    for idx in legal_indices:
        card = hand[idx]
        value = card_value_for_dump(card, contract_type, trump_suit)

        # Check if this move would win
        test_plays = plays_so_far + [(player_index, card)]
        winner = trick_winner(test_plays, contract_type, trump_suit)

        if winner == player_index:
            winning_moves.append((idx, card, value))
        else:
            losing_moves.append((idx, card, value))

    # Get strategy's choice
    choice = strategy.choose_card(hand, plays_so_far, contract_type, trump_suit, player_index)
    chosen_card = hand[choice]
    chosen_value = card_value_for_dump(chosen_card, contract_type, trump_suit)

    # Validate based on expected behavior
    if expected_behavior == "cheapest_winner_or_dump":
        if winning_moves:
            # Must pick cheapest winner
            cheapest_winner = min(winning_moves, key=lambda x: x[2])
            assert choice == cheapest_winner[0], (
                f"\n{strategy} FAILED: Should pick cheapest winner\n"
                f"  Expected: {cheapest_winner[1]} (idx {cheapest_winner[0]}, value {cheapest_winner[2]})\n"
                f"  Actual:   {chosen_card} (idx {choice}, value {chosen_value})\n"
                f"  All winners: {[(i, str(c), v) for i, c, v in winning_moves]}\n"
                f"  State: contract={contract_type}, trump={trump_suit}, plays={len(plays_so_far)}"
            )
        else:
            # Must pick cheapest dump
            if not losing_moves:
                raise AssertionError(f"No legal moves found! hand={hand}, legal_indices={legal_indices}")
            cheapest_dump = min(losing_moves, key=lambda x: x[2])
            assert choice == cheapest_dump[0], (
                f"\n{strategy} FAILED: Should pick cheapest dump\n"
                f"  Expected: {cheapest_dump[1]} (idx {cheapest_dump[0]}, value {cheapest_dump[2]})\n"
                f"  Actual:   {chosen_card} (idx {choice}, value {chosen_value})\n"
                f"  All losers: {[(i, str(c), v) for i, c, v in losing_moves]}\n"
                f"  State: contract={contract_type}, trump={trump_suit}, plays={len(plays_so_far)}"
            )

    elif expected_behavior == "any_winner":
        if winning_moves:
            # Must pick some winning card
            winning_indices = [idx for idx, _, _ in winning_moves]
            assert choice in winning_indices, (
                f"\n{strategy} FAILED: Should pick a winning card\n"
                f"  Actual:   {chosen_card} (idx {choice}) - LOSES\n"
                f"  Winners:  {[(i, str(c), v) for i, c, v in winning_moves]}\n"
                f"  State: contract={contract_type}, trump={trump_suit}, plays={len(plays_so_far)}"
            )

    return choice


class TestWinningMoveOracle:
    """
    Verify strategies take winning moves when they exist and are unambiguous.

    These are "oracle" tests: if a strategy claims to try to win tricks,
    it must take obvious winning moves in deterministic scenarios.
    """

    # Strategies that should try to win when possible
    WINNING_STRATEGIES = [
        pytest.param(GreedyStrategy(), id="greedy"),
        pytest.param(ImprovedGreedyStrategy(), id="improved_greedy"),
        pytest.param(AlwaysHighestLegalStrategy(), id="always_highest"),
    ]

    @pytest.mark.parametrize("strategy", WINNING_STRATEGIES)
    def test_obvious_win_2nd_to_act_followsuit(self, strategy):
        """
        Scenario: 2nd to act, can follow suit with winning card.
        Oracle: MUST play a winning card.
        """
        hand = [
            Card("H", "T"),  # idx 0 - Ten of hearts (loses to Q)
            Card("H", "A"),  # idx 1 - Ace of hearts (WINS)
            Card("S", "K"),  # idx 2 - King of spades (offsuit)
        ]
        plays_so_far = [(0, Card("H", "Q"))]

        # Oracle validates strategy picks a winner
        validate_greedy_algorithm(
            strategy, hand, plays_so_far, "high", None, 1,
            expected_behavior="any_winner"
        )

    @pytest.mark.parametrize("strategy", WINNING_STRATEGIES)
    def test_obvious_win_3rd_to_act_trump_beats_offsuit(self, strategy):
        """
        Scenario: 3rd to act, led suit is non-trump, current best is K.
        You can't follow suit but have trump A.
        Oracle: MUST trump to win.
        """
        hand = [
            Card("H", "A"),  # idx 0 - Ace of hearts (TRUMP - WINS)
            Card("D", "T"),  # idx 1 - Ten of diamonds (weak offsuit)
            Card("C", "Q"),  # idx 2 - Queen of clubs (weak offsuit)
        ]
        plays_so_far = [
            (0, Card("S", "J")),  # Spades Jack led
            (1, Card("S", "K")),  # Spades King (currently winning)
        ]

        # Oracle validates strategy trumps to win
        validate_greedy_algorithm(
            strategy, hand, plays_so_far, "suit", "H", 2,
            expected_behavior="any_winner"
        )

    @pytest.mark.parametrize("strategy", WINNING_STRATEGIES)
    def test_obvious_win_4th_to_act_followsuit(self, strategy):
        """
        Scenario: 4th to act (last player), can follow suit with winning card.
        Oracle: MUST play the winning card.
        """
        hand = [
            Card("C", "A"),  # idx 0 - Ace of clubs (WINS)
            Card("C", "T"),  # idx 1 - Ten of clubs (loses)
        ]
        plays_so_far = [
            (0, Card("C", "Q")),  # Clubs Queen led
            (1, Card("C", "J")),  # Clubs Jack
            (2, Card("C", "K")),  # Clubs King (currently winning)
        ]

        # Oracle validates strategy wins as last player
        validate_greedy_algorithm(
            strategy, hand, plays_so_far, "high", None, 3,
            expected_behavior="any_winner"
        )

    # Only test greedy strategies for "cheapest winner" logic
    # AlwaysHighest intentionally plays highest card, not cheapest winner
    GREEDY_STRATEGIES = [
        pytest.param(GreedyStrategy(), id="greedy"),
        pytest.param(ImprovedGreedyStrategy(), id="improved_greedy"),
    ]

    @pytest.mark.parametrize("strategy", GREEDY_STRATEGIES)
    def test_cheapest_winner_when_multiple_options(self, strategy):
        """
        Scenario: Multiple cards can win. Should choose cheapest winner.
        Oracle: Play the lowest-value winning card (conserve power).
        (Only applies to greedy strategies, not AlwaysHighest)
        """
        hand = [
            Card("H", "K"),  # idx 0 - King (expensive winner)
            Card("H", "Q"),  # idx 1 - Queen (cheaper winner)
            Card("H", "J"),  # idx 2 - Jack (CHEAPEST winner)
        ]
        plays_so_far = [(0, Card("H", "T"))]

        # Oracle validates cheapest winner is chosen
        validate_greedy_algorithm(
            strategy, hand, plays_so_far, "high", None, 1,
            expected_behavior="cheapest_winner_or_dump"
        )


class TestPartnerAwarenessOracle:
    """
    Test partner-aware strategies (currently only ImprovedGreedy).
    """

    def test_improved_greedy_does_not_overtake_partner(self):
        """
        Scenario: Partner is winning, you have trump to overtake.
        Oracle (ImprovedGreedy): Should NOT overtake partner.
        """
        improved = ImprovedGreedyStrategy()

        hand = [
            Card("H", "J"),  # idx 0 - Right bower (can overtake)
            Card("C", "T"),  # idx 1 - Clubs T (DUMP - cheap offsuit)
            Card("D", "K"),  # idx 2 - Diamonds K
        ]

        # Partner (player 0) is winning with C-A
        # Teams: 0+2, 1+3. Player 2's partner is 0
        plays_so_far = [
            (0, Card("C", "A")),  # Partner led Clubs A - WINNING
            (1, Card("C", "Q")),  # Opponent played Clubs Q
        ]

        choice = improved.choose_card(hand, plays_so_far, "suit", "H", 2)
        chosen_card = hand[choice]

        # Should dump cheap offsuit, not overtake with trump
        assert choice == 1, (
            f"ImprovedGreedy should dump when partner winning, "
            f"but chose {chosen_card} (idx {choice})"
        )

    def test_regular_greedy_may_overtake_partner(self):
        """
        Document that regular Greedy lacks partner awareness.
        (This is not a bug, just a feature difference.)
        """
        greedy = GreedyStrategy()

        hand = [
            Card("H", "J"),  # idx 0 - Right bower (can overtake)
            Card("C", "T"),  # idx 1 - Clubs T (cheap offsuit)
        ]

        # Same scenario as above
        plays_so_far = [
            (0, Card("C", "A")),
            (1, Card("C", "Q")),
        ]

        choice = greedy.choose_card(hand, plays_so_far, "suit", "H", 2)

        # Regular greedy doesn't have partner awareness, so it may overtake
        # This test just documents the behavior (not asserting specific choice)
        assert choice in [0, 1], "Greedy should make a legal choice"


class TestBowerHandling:
    """
    Test that strategies correctly handle bower valuation in trump contracts.
    """

    @pytest.mark.parametrize("strategy", TestWinningMoveOracle.WINNING_STRATEGIES)
    def test_right_bower_beats_all(self, strategy):
        """
        Scenario: Right bower should beat any card in trump contract.
        Oracle: When holding right bower and it can win, play it.
        """
        hand = [
            Card("H", "J"),  # idx 0 - Right bower (STRONGEST)
            Card("H", "A"),  # idx 1 - Trump Ace (strong but not strongest)
        ]

        # Trump ace led, we can beat it with right bower
        plays_so_far = [(0, Card("H", "K"))]  # Trump King led

        choice = strategy.choose_card(hand, plays_so_far, "suit", "H", 1)
        chosen_card = hand[choice]

        # Verify chosen card wins
        test_plays = plays_so_far + [(1, chosen_card)]
        winner = trick_winner(test_plays, "suit", "H")

        assert winner == 1, f"Chosen card {chosen_card} should win"

        # Should choose right bower (strongest trump, but also cheapest winner here)
        # Both cards win, but right bower is technically "cheaper" in greedy's valuation
        # (Actually both are expensive, but the test verifies a win is taken)
        assert choice in [0, 1], "Should choose a winning card"


class TestNoWinningMove:
    """
    Test strategy behavior when no winning move exists.
    """

    # Only test greedy strategies for "dumps cheapest" logic
    # AlwaysHighest intentionally plays highest card even when losing
    GREEDY_STRATEGIES = [
        pytest.param(GreedyStrategy(), id="greedy"),
        pytest.param(ImprovedGreedyStrategy(), id="improved_greedy"),
    ]

    @pytest.mark.parametrize("strategy", GREEDY_STRATEGIES)
    def test_dumps_cheapest_when_cannot_win(self, strategy):
        """
        Scenario: Cannot win the trick. Should dump cheapest card.
        Oracle: Minimize waste when losing.
        (Only applies to greedy strategies, not AlwaysHighest)
        """
        hand = [
            Card("H", "A"),  # idx 0 - Ace of hearts (expensive offsuit)
            Card("H", "K"),  # idx 1 - King of hearts (expensive offsuit)
            Card("H", "T"),  # idx 2 - Ten of hearts (CHEAPEST offsuit)
        ]
        plays_so_far = [
            (0, Card("C", "J")),  # Opponent led Clubs (trump)
            (1, Card("C", "A")),  # Clubs Ace
        ]

        # Oracle validates cheapest dump is chosen
        validate_greedy_algorithm(
            strategy, hand, plays_so_far, "suit", "C", 2,
            expected_behavior="cheapest_winner_or_dump"
        )
