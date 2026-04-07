"""
Tests validating bower handling in GreedyStrategy and GluttonStrategy.

Confirms that both strategies correctly value bowers (Right bower = J of trump,
Left bower = J of same color) in suit contracts, and that the simulation path
has always called on_hand_start() / observe_play() correctly.

Context: PR #2126 fixed a bower bug in the hosted-play engine (MatchEngine
did not call on_hand_start, so GluttonStrategy defaulted to contract_type=high
/ trump_suit=None). The simulation path was never affected — these tests
confirm that.
"""

import pytest

from bid_euchre.core.cards import Card
from bid_euchre.strategy import GluttonStrategy, GreedyStrategy
from bid_euchre.strategy.greedy import GluttonIsolatedStrategy


class TestBowerValueGreedy:
    """Verify GreedyStrategy correctly values bowers in suit contracts."""

    def test_greedy_leads_right_bower_in_suit(self):
        """Right bower (J of trump) should be the highest-value lead in suit."""
        greedy = GreedyStrategy()
        hand = [
            Card("H", "A"),  # idx 0 - Trump Ace
            Card("H", "J"),  # idx 1 - Right bower (highest card)
            Card("C", "A"),  # idx 2 - Off-suit Ace
            Card("S", "K"),  # idx 3 - Off-suit King
        ]
        # Leading — Greedy plays highest value
        choice = greedy.choose_card(hand, [], "suit", "H", 0)
        assert (
            choice == 1
        ), f"Greedy should lead right bower (idx 1), got idx {choice} ({hand[choice]})"

    def test_greedy_leads_left_bower_over_ace(self):
        """Left bower (J of same color) ranks above trump Ace in suit."""
        greedy = GreedyStrategy()
        hand = [
            Card("H", "A"),  # idx 0 - Trump Ace
            Card("D", "J"),  # idx 1 - Left bower (H trump → D-J is left)
            Card("C", "K"),  # idx 2 - Off-suit King
        ]
        choice = greedy.choose_card(hand, [], "suit", "H", 0)
        assert (
            choice == 1
        ), f"Greedy should lead left bower (idx 1), got idx {choice} ({hand[choice]})"

    def test_greedy_right_bower_beats_left_bower(self):
        """Right bower should beat left bower when following."""
        greedy = GreedyStrategy()
        hand = [
            Card("H", "J"),  # idx 0 - Right bower
            Card("D", "J"),  # idx 1 - Left bower
            Card("S", "T"),  # idx 2 - Off-suit
        ]
        # Opponent led left bower, we can beat with right
        plays_so_far = [
            (1, Card("D", "J")),  # Opponent led left bower
        ]
        choice = greedy.choose_card(hand, plays_so_far, "suit", "H", 0)
        # Cheapest winner — right bower (idx 0) is the only card that beats left bower
        assert (
            choice == 0
        ), f"Greedy should play right bower to beat left, got idx {choice}"


class TestBowerValueGlutton:
    """Verify GluttonStrategy correctly values bowers after on_hand_start."""

    def test_glutton_values_bowers_after_hand_start(self):
        """GluttonStrategy should recognize bowers as trump after on_hand_start.

        When Glutton has 4+ trump including only one bower (not both), the
        smart lead logic draws trump with the lowest trump card. This confirms
        bowers are counted as trump in the effective suit calculation.

        Hand: right bower + trump A/K/Q + offsuit T = 4 trump + 1 offsuit.
        With ≥4 trump and NOT both bowers → draw trump with lowest (H-Q).
        """
        glutton = GluttonStrategy()
        hand = [
            Card("H", "A"),  # idx 0 - Trump Ace
            Card("H", "J"),  # idx 1 - Right bower (counts as trump)
            Card("H", "K"),  # idx 2 - Trump King
            Card("H", "Q"),  # idx 3 - Trump Queen (lowest trump)
            Card("C", "T"),  # idx 4 - Off-suit
        ]
        # Critical: call on_hand_start to set contract context
        glutton.on_hand_start(hand, "suit", "H", player_index=0)

        # No non-trump Aces → check draw trump: 4 trump, has right but not left
        # → draw trump with lowest trump card (H-Q)
        choice = glutton.choose_card(hand, [], "suit", "H", 0)
        chosen_card = hand[choice]
        assert chosen_card == Card(
            "H", "Q"
        ), f"Glutton should draw trump with lowest trump (H-Q), got {chosen_card}"

    def test_glutton_without_hand_start_defaults_to_high(self):
        """Without on_hand_start, Glutton defaults to high contract (no bowers).

        This is the bug that PR #2126 fixed in hosted-play. In this mode,
        bowers are just Jacks with no special rank.
        """
        glutton = GluttonStrategy()
        # Do NOT call on_hand_start — simulates the hosted-play bug
        hand = [
            Card("H", "J"),  # idx 0 - Would be right bower if trump=H
            Card("H", "A"),  # idx 1 - Would be below right bower
            Card("C", "K"),  # idx 2 - Off-suit
        ]
        # In "high" contract (the default), A > K > Q > J > T
        # H-A should be highest, not H-J
        choice = glutton.choose_card(hand, [], "high", None, 0)
        assert (
            choice == 1
        ), f"In high contract, Ace should outrank Jack, got idx {choice}"

    def test_glutton_bower_following_with_tracking(self):
        """Glutton should correctly play bower when following in suit contract."""
        glutton = GluttonStrategy()
        hand = [
            Card("H", "J"),  # idx 0 - Right bower
            Card("C", "T"),  # idx 1 - Off-suit
            Card("S", "Q"),  # idx 2 - Off-suit
        ]
        glutton.on_hand_start(hand, "suit", "H", player_index=2)

        # Opponent leading trump Ace, we can beat with right bower
        plays_so_far = [
            (1, Card("H", "A")),  # Opponent led trump Ace
        ]
        choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 2)
        # Right bower beats trump Ace — should play it (opponent winning, not partner)
        assert (
            choice == 0
        ), f"Glutton should play right bower to beat trump Ace, got idx {choice}"


class TestSimPathHooksAlreadyCorrect:
    """Validate that the simulation path correctly invokes strategy hooks.

    These tests don't test the sim directly but confirm the contract:
    on_hand_start resets state, observe_play tracks cards, and choose_card
    uses that state.
    """

    def test_on_hand_start_sets_contract_context(self):
        """on_hand_start should set _contract_type and _trump_suit."""
        glutton = GluttonStrategy()
        assert glutton._contract_type == "high"  # default
        assert glutton._trump_suit is None  # default

        hand = [Card("H", "A"), Card("C", "K")]
        glutton.on_hand_start(hand, "suit", "S", player_index=0)
        assert glutton._contract_type == "suit"
        assert glutton._trump_suit == "S"

    def test_on_hand_start_resets_tracking(self):
        """on_hand_start should clear seen counts and void inference."""
        glutton = GluttonStrategy()
        # Simulate some tracking
        glutton._seen_counts[Card("H", "A")] = 1
        glutton._void_suits_by_seat[1].add("C")

        hand = [Card("H", "A"), Card("C", "K")]
        glutton.on_hand_start(hand, "suit", "H", player_index=0)

        assert len(glutton._seen_counts) == 0
        assert len(glutton._void_suits_by_seat[1]) == 0

    def test_observe_play_tracks_cards(self):
        """observe_play should increment seen counts."""
        glutton = GluttonStrategy()
        glutton.on_hand_start([Card("H", "A")], "suit", "H", player_index=0)

        card = Card("C", "A")
        glutton.observe_play(1, card, [(1, card)], "suit", "H")
        assert glutton._seen_counts[card] == 1

        glutton.observe_play(3, card, [(3, card)], "suit", "H")
        assert glutton._seen_counts[card] == 2  # Double deck: max 2

    def test_observe_play_infers_voids(self):
        """observe_play should infer voids when player doesn't follow suit."""
        glutton = GluttonStrategy()
        glutton.on_hand_start([Card("H", "A")], "suit", "H", player_index=0)

        # Player 1 led clubs, player 2 played diamonds (void in clubs)
        led_card = Card("C", "A")
        off_card = Card("D", "K")
        glutton.observe_play(1, led_card, [(1, led_card)], "suit", "H")
        glutton.observe_play(2, off_card, [(1, led_card), (2, off_card)], "suit", "H")
        assert "C" in glutton._void_suits_by_seat[2]


class TestCashWinnersOnLead:
    """Cash-A: sure-winner lead + draw-trump-first + draw trump from the top.

    All behavior is gated by ``cash_winners_on_lead`` **and** contract-type
    gating: Cash-A only fires for high/low contracts. In suit contracts,
    ``cash_winners_on_lead=True`` produces identical behavior to ``False``
    (experiment data: -0.13 Δ tricks in suit, +0.66 in high/low).

    See plans/sessions/2026-04-07_cash_a_h2h_experiment_report.md §5
    for the gating recommendation.
    """

    def test_sure_winner_lead_high_contract(self):
        """Fix 1 (high/low fallback): with flag on, AI leads a short-suit
        sure winner (A♠ in high) instead of the longest-suit heuristic."""
        hand = [
            Card("S", "A"),  # idx 0 - sure winner in high (nothing beats A)
            Card("C", "K"),  # idx 1 - longest-suit top card under baseline
            Card("C", "Q"),  # idx 2
            Card("C", "T"),  # idx 3
        ]

        # Baseline (flag off, the shipping default): longest-suit heuristic
        # picks K♣ from the 3-card clubs run, ignoring A♠.
        baseline = GluttonStrategy()
        baseline.on_hand_start(hand, "high", None, player_index=0)
        baseline_choice = baseline.choose_card(hand, [], "high", None, 0)
        assert hand[baseline_choice] == Card(
            "C", "K"
        ), f"Baseline (flag off) should lead K♣, got {hand[baseline_choice]}"

        # Cash-A (flag on): high/low fallback guard spots A♠ sure winner.
        cash = GluttonStrategy(cash_winners_on_lead=True)
        cash.on_hand_start(hand, "high", None, player_index=0)
        cash_choice = cash.choose_card(hand, [], "high", None, 0)
        assert hand[cash_choice] == Card(
            "S", "A"
        ), f"Cash-A (flag on) should lead A♠, got {hand[cash_choice]}"

    def test_sure_winner_lead_low_contract(self):
        """Fix 1 in low: with flag on, AI leads T♠ (sure winner in low)
        instead of the longest-suit heuristic."""
        hand = [
            Card("S", "T"),  # idx 0 - sure winner in low (nothing beats T)
            Card("C", "K"),  # idx 1
            Card("C", "Q"),  # idx 2
            Card("C", "J"),  # idx 3 - highest club value in low
        ]

        baseline = GluttonStrategy()
        baseline.on_hand_start(hand, "low", None, player_index=0)
        baseline_choice = baseline.choose_card(hand, [], "low", None, 0)
        assert (
            hand[baseline_choice] == Card("C", "J")
        ), f"Baseline (flag off) should lead longest-suit J♣, got {hand[baseline_choice]}"

        cash = GluttonStrategy(cash_winners_on_lead=True)
        cash.on_hand_start(hand, "low", None, player_index=0)
        cash_choice = cash.choose_card(hand, [], "low", None, 0)
        assert hand[cash_choice] == Card(
            "S", "T"
        ), f"Cash-A (flag on) should lead sure-winner T♠, got {hand[cash_choice]}"

    def test_suit_contract_suppresses_cash_a(self):
        """Contract-type gating: in suit contracts, ``cash_winners_on_lead=True``
        behaves identically to baseline (flag off). Cash-A steps 0.5, 0.75,
        and step 2 modification are all suppressed."""
        hand = [
            Card("S", "K"),  # idx 0 - trump K (not a sure winner)
            Card("H", "A"),  # idx 1 - side-suit ace
            Card("H", "Q"),  # idx 2 - heart filler
            Card("D", "T"),  # idx 3 - diamond filler
        ]

        # Baseline (flag off): non-trump-ace heuristic leads A♥.
        baseline = GluttonStrategy()
        baseline.on_hand_start(hand, "suit", "S", player_index=0)
        baseline_choice = baseline.choose_card(hand, [], "suit", "S", 0)
        assert hand[baseline_choice] == Card(
            "H", "A"
        ), f"Baseline (flag off) should lead A♥, got {hand[baseline_choice]}"

        # Cash-A (flag on, suit contract): gating suppresses Cash-A, so
        # behavior matches baseline — leads A♥, not trump K♠.
        cash = GluttonStrategy(cash_winners_on_lead=True)
        cash.on_hand_start(hand, "suit", "S", player_index=0)
        cash_choice = cash.choose_card(hand, [], "suit", "S", 0)
        assert hand[cash_choice] == Card(
            "H", "A"
        ), f"Cash-A gated in suit should lead A♥ like baseline, got {hand[cash_choice]}"

    def test_suit_gating_step2_leads_lowest_trump(self):
        """Contract-type gating in step 2: with flag on in suit, the
        ≥4-trump-no-both-bowers branch uses baseline behavior (min trump)
        because Cash-A is suppressed."""
        hand = [
            Card("S", "T"),  # idx 0 - trump (value 10)
            Card("S", "Q"),  # idx 1 - trump (value 12)
            Card("S", "K"),  # idx 2 - trump (value 13)
            Card("C", "J"),  # idx 3 - LB, effective trump (value 15)
            Card("D", "T"),  # idx 4 - offsuit filler
        ]

        # Seed opponent trump voids so step 0.75 path is suppressed and
        # step 2 is the branch under test.
        def _seed_voids(strategy):
            strategy._void_suits_by_seat[1].add("S")
            strategy._void_suits_by_seat[3].add("S")

        baseline = GluttonStrategy()
        baseline.on_hand_start(hand, "suit", "S", player_index=0)
        _seed_voids(baseline)
        baseline_choice = baseline.choose_card(hand, [], "suit", "S", 0)
        assert (
            hand[baseline_choice] == Card("S", "T")
        ), f"Baseline (flag off) should draw lowest trump T♠, got {hand[baseline_choice]}"

        # Flag on in suit: gating suppresses Cash-A, same result as baseline.
        cash = GluttonStrategy(cash_winners_on_lead=True)
        cash.on_hand_start(hand, "suit", "S", player_index=0)
        _seed_voids(cash)
        cash_choice = cash.choose_card(hand, [], "suit", "S", 0)
        assert hand[cash_choice] == Card(
            "S", "T"
        ), f"Cash-A gated in suit should lead T♠ like baseline, got {hand[cash_choice]}"

    def test_default_flag_preserves_baseline_behavior(self):
        """Explicit regression guard: ``GluttonStrategy()`` with no
        constructor args must behave identically to pre-Cash-A in the
        scenario Cash-A is designed to change. This protects the
        operator proving window — merging Cash-A does not change
        production behavior until the flag is flipped.
        """
        hand = [
            Card("S", "K"),
            Card("H", "A"),
            Card("H", "Q"),
            Card("D", "T"),
        ]

        default = GluttonStrategy()  # no flag
        assert default.cash_winners_on_lead is False
        default.on_hand_start(hand, "suit", "S", player_index=0)
        default_choice = default.choose_card(hand, [], "suit", "S", 0)
        # Pre-Cash-A behavior: non-trump ace heuristic leads A♥.
        assert hand[default_choice] == Card("H", "A"), (
            "Default GluttonStrategy() must preserve pre-Cash-A lead (A♥) "
            f"— got {hand[default_choice]}"
        )

    def test_isolated_strategy_flag_off_by_default(self):
        """``GluttonIsolatedStrategy`` defaults to flag off so baseline
        comparison runs are unaffected."""
        hand = [
            Card("S", "K"),
            Card("H", "A"),
            Card("H", "Q"),
            Card("D", "T"),
        ]

        isolated = GluttonIsolatedStrategy(smart_leads=True)
        assert isolated.cash_winners_on_lead is False
        isolated.on_hand_start(hand, "suit", "S", player_index=0)
        choice = isolated.choose_card(hand, [], "suit", "S", 0)
        # Pre-Cash-A smart-leads: non-trump ace.
        assert hand[choice] == Card("H", "A"), (
            "GluttonIsolatedStrategy with smart_leads=True and flag off "
            f"must preserve baseline lead (A♥) — got {hand[choice]}"
        )

    def test_isolated_strategy_suit_gating(self):
        """``GluttonIsolatedStrategy`` with ``cash_winners_on_lead=True``
        in a suit contract behaves like baseline (A♥) — Cash-A suppressed."""
        hand = [
            Card("S", "K"),
            Card("H", "A"),
            Card("H", "Q"),
            Card("D", "T"),
        ]

        isolated = GluttonIsolatedStrategy(smart_leads=True, cash_winners_on_lead=True)
        isolated.on_hand_start(hand, "suit", "S", player_index=0)
        choice = isolated.choose_card(hand, [], "suit", "S", 0)
        assert hand[choice] == Card("H", "A"), (
            "GluttonIsolatedStrategy with cash_winners_on_lead=True in suit "
            f"must lead A♥ (gating suppresses Cash-A) — got {hand[choice]}"
        )

    def test_version_bumped_to_0_10_0(self):
        """Suit continuity (#2506) bumps version to 0.10.0."""
        from bid_euchre.strategy.greedy import GLUTTON_STRATEGY_VERSION

        assert GLUTTON_STRATEGY_VERSION == "0.10.0"
        assert GluttonStrategy.VERSION == "0.10.0"
        assert GluttonIsolatedStrategy.VERSION == "0.10.0"

    # ---- Contract-type gating tests (Cash-A.1 → 0.9.0 update) ----

    @pytest.mark.parametrize(
        "cls,kwargs",
        [
            (GluttonStrategy, {"cash_winners_on_lead": True}),
            (
                GluttonIsolatedStrategy,
                {"smart_leads": True, "cash_winners_on_lead": True},
            ),
        ],
        ids=["Glutton", "GluttonIsolated"],
    )
    def test_suit_gating_suppresses_step0_5_sure_winners(self, cls, kwargs):
        """With flag on in a suit contract, step 0.5 (cash sure winners)
        is suppressed. The baseline path fires instead — non-trump ace (A♥)
        leads instead of any sure-winner trump."""
        hand = [
            Card("C", "J"),  # LB (value 15, but NOT a sure winner)
            Card("S", "A"),  # trump A (value 14)
            Card("S", "K"),  # trump K (value 13)
            Card("S", "T"),  # trump T (value 10)
            Card("H", "A"),  # offsuit — baseline non-trump ace lead
        ]

        strat = cls(**kwargs)
        strat.on_hand_start(hand, "suit", "S", player_index=0)
        strat._seen_counts[Card("S", "J")] = 1

        choice = strat.choose_card(hand, [], "suit", "S", 0)
        # Gating suppresses Cash-A; baseline step 1 leads A♥.
        assert hand[choice] == Card("H", "A"), (
            f"{cls.__name__}: suit gating should suppress Cash-A, "
            f"leading baseline A♥ — got {hand[choice]}"
        )

    @pytest.mark.parametrize(
        "cls,kwargs",
        [
            (GluttonStrategy, {"cash_winners_on_lead": True}),
            (
                GluttonIsolatedStrategy,
                {"smart_leads": True, "cash_winners_on_lead": True},
            ),
        ],
        ids=["Glutton", "GluttonIsolated"],
    )
    def test_suit_gating_suppresses_step2_draw_top(self, cls, kwargs):
        """With flag on in suit, step 2 modification (draw trump from top
        via _draw_trump_lead) is suppressed. Baseline leads A♥."""
        hand = [
            Card("C", "J"),  # LB — sure winner now (both RBs gone)
            Card("S", "A"),  # trump A — also sure winner
            Card("S", "K"),  # trump K
            Card("S", "T"),  # trump T
            Card("H", "A"),  # offsuit — baseline leads this
        ]

        strat = cls(**kwargs)
        strat.on_hand_start(hand, "suit", "S", player_index=0)
        strat._seen_counts[Card("S", "J")] = 2

        choice = strat.choose_card(hand, [], "suit", "S", 0)
        # Gating suppresses Cash-A step 0.5 and 2; baseline leads A♥.
        assert hand[choice] == Card("H", "A"), (
            f"{cls.__name__}: suit gating should suppress Cash-A, "
            f"leading baseline A♥ — got {hand[choice]}"
        )

    @pytest.mark.parametrize(
        "cls,kwargs",
        [
            (GluttonStrategy, {"cash_winners_on_lead": True}),
            (
                GluttonIsolatedStrategy,
                {"smart_leads": True, "cash_winners_on_lead": True},
            ),
        ],
        ids=["Glutton", "GluttonIsolated"],
    )
    def test_suit_gating_trump_dominant_leads_baseline(self, cls, kwargs):
        """Trump-dominant hand in suit with flag on: gating suppresses
        Cash-A, so baseline step 1 leads A♥ (non-trump ace)."""
        hand = [
            Card("S", "A"),  # trump A (value 14)
            Card("S", "K"),  # trump K (value 13)
            Card("S", "Q"),  # trump Q (value 12)
            Card("S", "T"),  # trump T (value 10)
            Card("H", "A"),  # offsuit — baseline leads this
        ]

        strat = cls(**kwargs)
        strat.on_hand_start(hand, "suit", "S", player_index=0)
        strat._seen_counts[Card("S", "J")] = 2
        strat._seen_counts[Card("C", "J")] = 2

        choice = strat.choose_card(hand, [], "suit", "S", 0)
        # Gating suppresses Cash-A; baseline step 1 leads A♥.
        assert hand[choice] == Card("H", "A"), (
            f"{cls.__name__}: suit gating should suppress Cash-A, "
            f"leading baseline A♥ — got {hand[choice]}"
        )

    @pytest.mark.parametrize(
        "cls,kwargs",
        [
            (GluttonStrategy, {"cash_winners_on_lead": True}),
            (
                GluttonIsolatedStrategy,
                {"smart_leads": True, "cash_winners_on_lead": True},
            ),
        ],
        ids=["Glutton", "GluttonIsolated"],
    )
    def test_high_contract_cash_a_still_fires(self, cls, kwargs):
        """In high contracts, Cash-A fallback guard still fires when flag
        is on — sure winner A♠ is preferred over longest-suit K♣."""
        hand = [
            Card("S", "A"),  # sure winner in high (nothing beats A)
            Card("C", "K"),  # longest-suit top card under baseline
            Card("C", "Q"),
            Card("C", "T"),
        ]

        strat = cls(**kwargs)
        strat.on_hand_start(hand, "high", None, player_index=0)
        choice = strat.choose_card(hand, [], "high", None, 0)
        assert hand[choice] == Card("S", "A"), (
            f"{cls.__name__} in high: Cash-A should fire, "
            f"leading A♠ — got {hand[choice]}"
        )

    @pytest.mark.parametrize(
        "cls,kwargs",
        [
            (GluttonStrategy, {"cash_winners_on_lead": True}),
            (
                GluttonIsolatedStrategy,
                {"smart_leads": True, "cash_winners_on_lead": True},
            ),
        ],
        ids=["Glutton", "GluttonIsolated"],
    )
    def test_low_contract_cash_a_still_fires(self, cls, kwargs):
        """In low contracts, Cash-A fallback guard still fires when flag
        is on — sure winner T♠ is preferred over longest-suit J♣."""
        hand = [
            Card("S", "T"),  # sure winner in low (T is highest value)
            Card("C", "K"),
            Card("C", "Q"),
            Card("C", "J"),  # longest-suit best in low (J has value 3)
        ]

        strat = cls(**kwargs)
        strat.on_hand_start(hand, "low", None, player_index=0)
        choice = strat.choose_card(hand, [], "low", None, 0)
        assert hand[choice] == Card("S", "T"), (
            f"{cls.__name__} in low: Cash-A should fire, "
            f"leading T♠ — got {hand[choice]}"
        )
