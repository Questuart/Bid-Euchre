"""
Core simulation engine for Bid Euchre.

This module is library code (no CLI). It supports:
- self-play (same strategy for all seats)
- head-to-head by seat (different strategies per player)
"""

import random
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from ..core.cards import Card, create_deck, deal_hands, shuffle_deck
from ..core.rules import get_legal_indices, trick_winner
from ..datasets.bidding import BiddingDatasetCollector
from ..features.hand_eval import get_hand_features, score_hand
from ..scoring import compute_points
from ..strategy import GreedyStrategy, Strategy
from ..strategy.bidding import BidAction, BiddingObservation, BiddingPolicy
from .deals import generate_deal, generate_initial_leader
from .exchange import perform_exchange
from .hooks import BiddingDecisionEvent, HandEndEvent, SimulationHooks

if TYPE_CHECKING:
    from ..logging import GameLogger


def play_single_hand(
    contract_type: Optional[str],
    trump_suit: Optional[str] = None,
    strategy: Optional[Strategy] = None,
    strategies: Optional[List[Strategy]] = None,
    bidding_policy: Optional[BiddingPolicy] = None,
    bidding_policies: Optional[List[BiddingPolicy]] = None,
    logger: Optional["GameLogger"] = None,
    deal_id: int = 0,
    hands: Optional[List[List[Card]]] = None,
    deal_seed: Optional[int] = None,
    initial_leader: Optional[int] = None,
    rng: Optional[random.Random] = None,
    bidding_collector: Optional[BiddingDatasetCollector] = None,
    on_bidding_decision: Optional[Callable[[BiddingDecisionEvent], None]] = None,
) -> Tuple[
    int,
    int,
    List[int],
    List[Dict[str, int]],
    int,
    List[List[Card]],
    Optional[int],
    Optional[int],
    Optional[int],
    str,
    Optional[str],
    Optional[List[Dict[str, Any]]],
]:
    """
    Play one full 10-trick hand.

    If contract_type is None, a bidding phase is conducted first.
    The winner of the bid chooses the contract and leads the first trick.

    Returns:
        (t0, t1, scores, features, leader, hands, bid, dealer_pos, bidder_pos, final_contract, final_trump, auction_transcript)
    """
    # Resolve strategy-per-seat.
    if strategies is not None:
        if len(strategies) != 4:
            raise ValueError(f"`strategies` must have length 4 (got {len(strategies)})")
        seat_strategies = strategies
    else:
        if strategy is None:
            strategy = GreedyStrategy()
        seat_strategies = [strategy, strategy, strategy, strategy]

    # Resolve bidding policy-per-seat.
    if bidding_policies is not None:
        if len(bidding_policies) != 4:
            raise ValueError(
                f"`bidding_policies` must have length 4 (got {len(bidding_policies)})"
            )
        seat_bidding_policies = bidding_policies
    else:
        seat_bidding_policies = None

    if hands is None:
        deck: List[Card] = create_deck()
        shuffle_deck(deck, rng=rng)
        hands = deal_hands(deck, num_players=4, hand_size=10)
    else:
        hands = [list(h) for h in hands]

    starting_hands = [list(h) for h in hands]

    # BIDDING PHASE
    bidding_data = None
    dealer_index = None  # Track dealer position (0-3 or None if no bidding)
    bidder_position = None  # Track auction winner (0-3 or None)
    _transcript: Optional[List[Dict[str, Any]]] = None  # Auction transcript (schema v7)

    if contract_type is None:
        # Determine dealer
        if initial_leader is not None:
            dealer_index = (initial_leader - 1) % 4
        else:
            if rng is not None:
                dealer_index = rng.randrange(4)
            else:
                # For determinism, derive dealer from deal_seed and deal_id when available
                if deal_seed is not None:
                    dealer_rng = random.Random(deal_seed + deal_id)
                    dealer_index = dealer_rng.randrange(4)
                else:
                    # Fallback: use local RNG to avoid global random state
                    dealer_index = random.Random().randrange(4)

        current_high_bid = 0
        winning_bid_action: Optional[BidAction] = None  # Track full winning bid
        winning_bidder = None
        final_contract = None
        final_trump = None
        _transcript = []  # Accumulate per-seat bid actions (schema v7)

        # Use new bidding policy interface if provided, otherwise fall back to old interface
        if seat_bidding_policies is not None:
            # New interface: per-seat bidding policies
            for offset in range(1, 5):
                player_idx = (dealer_index + offset) % 4

                # Create bidding observation
                obs = BiddingObservation(
                    hand=starting_hands[player_idx],
                    seat=player_idx,
                    dealer_seat=dealer_index,
                    current_high_bid=current_high_bid,
                    auction_transcript=tuple(dict(e) for e in _transcript),
                )

                # Get bid from policy
                bid_action = seat_bidding_policies[player_idx].choose_bid(obs)

                if bidding_collector is not None:
                    bidding_collector.record_decision(obs, bid_action, deal_id)

                # Determine legality using overcall hierarchy
                is_dealer = player_idx == dealer_index
                if bid_action.is_pass():
                    _is_legal = True
                elif winning_bid_action is None:
                    _is_legal = True  # First bid is always legal
                elif bid_action.overcalls(winning_bid_action):
                    _is_legal = True
                elif (
                    is_dealer
                    and bid_action.bid_type in {"moon", "loner"}
                    and winning_bid_action.bid_type == bid_action.bid_type
                ):
                    _is_legal = True  # Dealer takeover
                else:
                    _is_legal = False

                # Fire bidding decision event if handler registered
                if on_bidding_decision is not None:
                    on_bidding_decision(
                        BiddingDecisionEvent(
                            deal_id=deal_id,
                            seat=player_idx,
                            hand=list(
                                starting_hands[player_idx]
                            ),  # Copy to avoid aliasing
                            dealer_seat=dealer_index,
                            current_high_bid=current_high_bid,
                            bid_amount=bid_action.n,
                            bid_contract=bid_action.contract,
                            is_legal=_is_legal,
                        )
                    )

                # Determine if this bid is an effective pass
                if bid_action.is_pass():
                    is_effective_pass = True
                elif winning_bid_action is None:
                    is_effective_pass = False  # First bid always accepted
                elif bid_action.overcalls(winning_bid_action):
                    is_effective_pass = False
                elif (
                    is_dealer
                    and bid_action.bid_type in {"moon", "loner"}
                    and winning_bid_action.bid_type == bid_action.bid_type
                ):
                    is_effective_pass = False  # Dealer takeover
                else:
                    is_effective_pass = True  # Does not overcall

                if is_effective_pass:
                    _transcript.append(
                        {
                            "seat": player_idx,
                            "action": "PASS",
                            "tricks_bid": 0,
                            "contract_type": None,
                            "trump": None,
                        }
                    )
                    continue

                # Valid higher bid - accept it
                _ctype, _trump = bid_action.to_contract_tuple()
                _transcript.append(
                    {
                        "seat": player_idx,
                        "action": "BID",
                        "tricks_bid": bid_action.n,
                        "contract_type": _ctype,
                        "trump": _trump,
                        "bid_type": bid_action.bid_type,
                    }
                )
                current_high_bid = bid_action.n

                winning_bid_action = bid_action
                winning_bidder = player_idx
                final_contract, final_trump = _ctype, _trump
        elif bidding_policy is not None:
            # New interface: sequential bidding (LOD order) using BiddingPolicy
            for offset in range(1, 5):
                player_idx = (dealer_index + offset) % 4

                # Create bidding observation
                obs = BiddingObservation(
                    hand=starting_hands[player_idx],
                    seat=player_idx,
                    dealer_seat=dealer_index,
                    current_high_bid=current_high_bid,
                    auction_transcript=tuple(dict(e) for e in _transcript),
                )

                # Get bid from policy
                bid_action = bidding_policy.choose_bid(obs)

                if bidding_collector is not None:
                    bidding_collector.record_decision(obs, bid_action, deal_id)

                # Determine legality using overcall hierarchy
                is_dealer = player_idx == dealer_index
                if bid_action.is_pass():
                    _is_legal = True
                elif winning_bid_action is None:
                    _is_legal = True
                elif bid_action.overcalls(winning_bid_action):
                    _is_legal = True
                elif (
                    is_dealer
                    and bid_action.bid_type in {"moon", "loner"}
                    and winning_bid_action.bid_type == bid_action.bid_type
                ):
                    _is_legal = True  # Dealer takeover
                else:
                    _is_legal = False

                # Fire bidding decision event if handler registered
                if on_bidding_decision is not None:
                    on_bidding_decision(
                        BiddingDecisionEvent(
                            deal_id=deal_id,
                            seat=player_idx,
                            hand=list(
                                starting_hands[player_idx]
                            ),  # Copy to avoid aliasing
                            dealer_seat=dealer_index,
                            current_high_bid=current_high_bid,
                            bid_amount=bid_action.n,
                            bid_contract=bid_action.contract,
                            is_legal=_is_legal,
                        )
                    )

                # Determine if this bid is an effective pass
                if bid_action.is_pass():
                    is_effective_pass = True
                elif winning_bid_action is None:
                    is_effective_pass = False
                elif bid_action.overcalls(winning_bid_action):
                    is_effective_pass = False
                elif (
                    is_dealer
                    and bid_action.bid_type in {"moon", "loner"}
                    and winning_bid_action.bid_type == bid_action.bid_type
                ):
                    is_effective_pass = False  # Dealer takeover
                else:
                    is_effective_pass = True

                if is_effective_pass:
                    _transcript.append(
                        {
                            "seat": player_idx,
                            "action": "PASS",
                            "tricks_bid": 0,
                            "contract_type": None,
                            "trump": None,
                        }
                    )
                    continue

                # Valid higher bid - accept it
                _ctype, _trump = bid_action.to_contract_tuple()
                _transcript.append(
                    {
                        "seat": player_idx,
                        "action": "BID",
                        "tricks_bid": bid_action.n,
                        "contract_type": _ctype,
                        "trump": _trump,
                        "bid_type": bid_action.bid_type,
                    }
                )
                current_high_bid = bid_action.n

                winning_bid_action = bid_action
                winning_bidder = player_idx
                final_contract, final_trump = _ctype, _trump
        else:
            # Old interface: sequential bidding using Strategy.decide_bid
            # Bidding order: LOD, Partner of LOD, ROD, Dealer
            for i in range(1, 5):
                player_idx = (dealer_index + i) % 4
                partner_idx = (player_idx + 2) % 4
                strat = seat_strategies[player_idx]

                bid, ctype, trump = strat.decide_bid(
                    hand=starting_hands[player_idx],
                    current_high_bid=current_high_bid,
                    current_winner_index=winning_bidder,
                    partner_index=partner_idx,
                    player_index=player_idx,
                )

                obs = BiddingObservation(
                    hand=starting_hands[player_idx],
                    seat=player_idx,
                    dealer_seat=dealer_index,
                    current_high_bid=current_high_bid,
                    auction_transcript=tuple(dict(e) for e in _transcript),
                )
                bid_action = None
                if bid == 0:
                    bid_action = BidAction.pass_bid()
                elif 1 <= bid <= 10:
                    if ctype == "suit":
                        contract_for_action = trump
                    else:
                        contract_for_action = (
                            ctype.upper() if isinstance(ctype, str) else ctype
                        )
                    bid_action = BidAction.bid(bid, contract_for_action)
                if bidding_collector is not None and bid_action is not None:
                    bidding_collector.record_decision(obs, bid_action, deal_id)

                # Fire bidding decision event if handler registered
                if on_bidding_decision is not None and bid_action is not None:
                    is_legal = bid_action.is_pass() or bid_action.n > current_high_bid
                    on_bidding_decision(
                        BiddingDecisionEvent(
                            deal_id=deal_id,
                            seat=player_idx,
                            hand=list(
                                starting_hands[player_idx]
                            ),  # Copy to avoid aliasing
                            dealer_seat=dealer_index,
                            current_high_bid=current_high_bid,
                            bid_amount=bid_action.n,
                            bid_contract=bid_action.contract,
                            is_legal=is_legal,
                        )
                    )

                # Dealer-partner pass rule: dealer passes if partner has the high bid
                if player_idx == dealer_index and winning_bidder == partner_idx:
                    _transcript.append(
                        {
                            "seat": player_idx,
                            "action": "PASS",
                            "tricks_bid": 0,
                            "contract_type": None,
                            "trump": None,
                        }
                    )
                    continue

                is_effective_pass = bid == 0 or bid <= current_high_bid
                if is_effective_pass:
                    _transcript.append(
                        {
                            "seat": player_idx,
                            "action": "PASS",
                            "tricks_bid": 0,
                            "contract_type": None,
                            "trump": None,
                        }
                    )
                else:
                    _transcript.append(
                        {
                            "seat": player_idx,
                            "action": "BID",
                            "tricks_bid": bid,
                            "contract_type": ctype,
                            "trump": trump,
                        }
                    )
                    current_high_bid = bid
                    winning_bidder = player_idx
                    final_contract = ctype
                    final_trump = trump

        if winning_bidder is None or current_high_bid == 0:
            # Misdeal: everyone passed or no valid bids
            # Return zeros but still need scores/features (use dummy contract for logging)
            dummy_ctype = "high"
            all_player_scores = [
                score_hand(h, dummy_ctype, None) for h in starting_hands
            ]
            all_player_features = [
                get_hand_features(h, dummy_ctype, None) for h in starting_hands
            ]
            # dealer_index is known, bidder_position is None (misdeal)
            if bidding_collector is not None:
                bidding_collector.set_final_contract(dummy_ctype, None)
            return (
                0,
                0,
                all_player_scores,
                all_player_features,
                -1,
                starting_hands,
                0,
                dealer_index,
                None,
                dummy_ctype,
                None,
                _transcript,
            )

        contract_type = final_contract
        trump_suit = final_trump
        if bidding_collector is not None:
            bidding_collector.set_final_contract(contract_type, trump_suit)
        initial_leader = winning_bidder
        bidder_position = winning_bidder  # Capture bidder for logging
        bidding_data = {
            "winner": winning_bidder,
            "bid": current_high_bid,
            "contract": contract_type,
            "trump": trump_suit,
        }

        # EXCHANGE PHASE: moon bids trigger a 2-card exchange with partner
        if winning_bid_action is not None and winning_bid_action.bid_type == "moon":
            mooner_seat = winning_bidder
            partner_seat = (mooner_seat + 2) % 4
            hands[mooner_seat], hands[partner_seat] = perform_exchange(
                mooner_hand=hands[mooner_seat],
                partner_hand=hands[partner_seat],
                contract_type=contract_type,
                trump_suit=trump_suit,
            )
    else:
        # Contract was fixed, no bid was made
        current_high_bid = None
        # No bidding phase: dealer and bidder are unknown
        dealer_index = None
        bidder_position = None
        _transcript = None  # null distinguishes "no bidding mode" from "all passed"

    # Validation (now that contract is decided)
    if contract_type == "suit" and trump_suit is None:
        raise ValueError("trump_suit must be provided or decided for 'suit' contracts")
    if contract_type in ("high", "low") and trump_suit is not None:
        raise ValueError(
            "trump_suit must be None for 'high'/'low' (no-trump) contracts"
        )

    # Extract features for ALL 4 players
    all_player_scores: List[int] = []
    all_player_features: List[Dict[str, int]] = []
    for player_idx in range(4):
        score = score_hand(
            starting_hands[player_idx],
            contract_type=contract_type,
            trump_suit=trump_suit,
            mode="scalar",
        )
        features = get_hand_features(
            starting_hands[player_idx],
            contract_type=contract_type,
            trump_suit=trump_suit,
        )
        all_player_scores.append(score)
        all_player_features.append(features)

    # Log bidding if it happened
    if logger and bidding_data:
        # We need a new log event or just include it in hand_end.
        # For now, we can pass it via logger context if we had one.
        # Let's assume the logger will be updated or we'll just use the hand_end features.
        pass

    team_tricks = {0: 0, 1: 0}
    if initial_leader is None:
        if deal_seed is not None:
            initial_leader = generate_initial_leader(deal_seed, deal_id)
        else:
            if rng is not None:
                initial_leader = rng.randrange(4)
            else:
                # Fallback: use local RNG to avoid global random state
                initial_leader = random.Random().randrange(4)
    leader = initial_leader

    # Fire on_hand_start hooks for strategies that implement them
    # CRITICAL: De-duplicate by instance identity to avoid calling hooks multiple times
    # when a single strategy instance is shared across seats (common in self-play)
    seen_strategy_ids: set = set()
    unique_strategies = []
    for s in seat_strategies:
        if id(s) not in seen_strategy_ids:
            seen_strategy_ids.add(id(s))
            unique_strategies.append(s)

    # Filter to strategies that override on_hand_start (not default no-op)
    hand_start_targets = [
        s
        for s in unique_strategies
        if type(s).on_hand_start is not Strategy.on_hand_start
    ]
    for s in hand_start_targets:
        # Find which seat(s) this strategy is assigned to (use first seat for player_index)
        for seat_idx, seat_strat in enumerate(seat_strategies):
            if seat_strat is s:
                s.on_hand_start(
                    starting_hand=list(
                        starting_hands[seat_idx]
                    ),  # Copy to avoid aliasing
                    contract_type=contract_type,
                    trump_suit=trump_suit,
                    player_index=seat_idx,
                )
                break

    # Filter to strategies that override observe_play (not default no-op)
    observe_play_targets = [
        s
        for s in unique_strategies
        if type(s).observe_play is not Strategy.observe_play
    ]

    # 10 tricks in a 10-card hand
    for trick_num in range(10):
        plays = []
        trick_leader = leader

        # Players act in order starting from leader
        for offset in range(4):
            player = (leader + offset) % 4
            hand = hands[player]

            # Engine-level guardrail: enforce legal plays (not just in strategies).
            legal_indices = get_legal_indices(hand, plays, contract_type, trump_suit)
            strat = seat_strategies[player]
            card_index = strat.choose_card(
                hand=hand,
                plays_so_far=plays,
                contract_type=contract_type,
                trump_suit=trump_suit,
                player_index=player,
            )
            if card_index not in legal_indices:
                raise ValueError(
                    f"Illegal play from strategy={getattr(strat, 'name', type(strat).__name__)} "
                    f"player={player} contract={contract_type} trump={trump_suit} "
                    f"chosen_index={card_index} legal_indices={legal_indices} hand_size={len(hand)}"
                )

            # Index integrity check: verify strategy returns valid index into actual hand
            # (catches bugs where strategy sorts/filters hand and returns wrong index)
            if card_index < 0 or card_index >= len(hand):
                raise ValueError(
                    f"Index integrity failure: strategy={getattr(strat, 'name', type(strat).__name__)} "
                    f"returned out-of-bounds index {card_index} for hand of size {len(hand)} "
                    f"player={player}"
                )

            card = hand.pop(card_index)
            plays.append((player, card))

            # Fire observe_play hooks for strategies that implement them
            for s in observe_play_targets:
                s.observe_play(
                    player_index=player,
                    card=card,
                    trick_plays=list(plays),  # Copy to avoid aliasing
                    contract_type=contract_type,
                    trump_suit=trump_suit,
                )

        winner = trick_winner(
            plays,
            contract_type=contract_type,
            trump_suit=trump_suit,
        )

        # Log trick completion (if logger enabled)
        if logger and logger.log_tricks:
            logger.log_trick_end(deal_id, trick_num, trick_leader, plays, winner)

        # Assign trick to a team
        if winner in (0, 2):
            team_tricks[0] += 1
        else:
            team_tricks[1] += 1

        leader = winner  # winner leads next trick

    return (
        team_tricks[0],
        team_tricks[1],
        all_player_scores,
        all_player_features,
        initial_leader,
        starting_hands,
        current_high_bid,
        dealer_index,
        bidder_position,
        contract_type,
        trump_suit,
        _transcript,
    )


def simulate_many_hands(
    n: int,
    contract_type: Optional[str],
    trump_suit: Optional[str] = None,
    seed: Optional[int] = None,
    strategy: Optional[Strategy] = None,
    strategies: Optional[List[Strategy]] = None,
    bidding_policy: Optional[BiddingPolicy] = None,
    bidding_policies: Optional[List[BiddingPolicy]] = None,
    logger: Optional["GameLogger"] = None,
    deal_seed: Optional[int] = None,
    bidding_dataset_run_id: Optional[str] = None,
    bidding_hand_id_offset: int = 0,
    hooks: Optional[SimulationHooks] = None,
    deal_method: str = "round_robin",
) -> Dict:
    """
    Run Monte Carlo simulation of n hands.

    Args:
        n: Number of hands to simulate
        contract_type: "suit", "high", or "low" (None for auction mode)
        trump_suit: Trump suit for suit contracts
        seed: Random seed for reproducibility
        strategy: Strategy to use (defaults to GreedyStrategy)
        strategies: Optional per-seat strategies (length 4)
        bidding_policy: Optional bidding policy (single policy used for all seats)
        bidding_policies: Optional per-seat bidding policies (length 4)
        logger: Optional GameLogger for structured JSONL logging
        bidding_dataset_run_id: Run ID for bidding dataset collection (auction mode only)
        bidding_hand_id_offset: Offset to add to hand_id for globally unique IDs
        hooks: Optional SimulationHooks for event-based instrumentation

    Returns a summary dict:
        {
            "hands": n,
            "contract_type": contract_type,
            "trump_suit": trump_suit,
            "avg_team0": float,
            "avg_team1": float,
            "distribution_team0": {0..10: count},
            "win_rate_team0": float or None,  # wins_team0 / hands (None if hands=0)
            "win_rate_team1": float or None,  # wins_team1 / hands (None if hands=0)
            "tie_rate": float or None,  # ties / hands (None if hands=0)
            "avg_score": float,  # avg across all 4 players
            "score_buckets": { score -> {count, total_tricks, avg_tricks} },
            "feature_buckets": {
                feature_name -> {
                    value -> {count, total_tricks, avg_tricks}
                }
            },
            "player_samples": int,  # total player-hand samples (n * 4)
        }

    Features are tracked for ALL 4 players per hand, bucketed by their team's tricks.
    This removes measurement anchoring and 4x the effective sample size.
    """
    # Create local RNG for reproducibility (never mutate global random state)
    local_rng: Optional[random.Random] = None
    if seed is not None and deal_seed is None:
        local_rng = random.Random(seed)

    dist_team0 = {i: 0 for i in range(11)}  # possible tricks 0–10

    total0 = 0
    total1 = 0
    total_score_all = 0  # sum across all 4 players

    # Win-rate tracking (floats for weighted win rate with ties = 0.5)
    wins_team0 = 0.0
    wins_team1 = 0.0
    ties = 0

    # Points-based scoring aggregates
    total_points_team0 = 0
    total_points_team1 = 0
    # Points distributions allow negative values (for sets), so we use dicts
    dist_points_team0: Dict[int, int] = {}
    dist_points_team1: Dict[int, int] = {}

    # Bidding-related tracking (only when bidding occurred)
    hands_with_bids = 0
    bid_values: List[int] = []
    made_count = 0
    set_count = 0

    # score -> stats dict (aggregated across all players)
    score_buckets: Dict[int, Dict[str, float]] = {}

    # feature_name -> value -> stats dict (aggregated across all players)
    feature_buckets: Dict[str, Dict[int, Dict[str, float]]] = {}

    player_samples = 0  # count of player-hand observations

    collectors: List[BiddingDatasetCollector] = []
    if bidding_dataset_run_id is not None and contract_type is None:
        collectors = [
            BiddingDatasetCollector(
                bidding_dataset_run_id, bidding_hand_id_offset + hand_id
            )
            for hand_id in range(n)
        ]

    for deal_id in range(n):
        collector = collectors[deal_id] if collectors else None
        # Extract bidding decision callback from hooks if present
        on_bidding_decision = hooks.on_bidding_decision if hooks else None

        if deal_seed is not None:
            deal_hands_ = generate_deal(deal_seed, deal_id, deal_method=deal_method)
            (
                t0,
                t1,
                all_scores,
                all_feats,
                initial_leader,
                starting_hands,
                winning_bid,
                dealer_pos,
                bidder_pos,
                actual_contract,
                actual_trump,
                auction_transcript,
            ) = play_single_hand(
                contract_type=contract_type,
                trump_suit=trump_suit,
                strategy=strategy,
                strategies=strategies,
                bidding_policy=bidding_policy,
                bidding_policies=bidding_policies,
                logger=logger,
                deal_id=deal_id,
                hands=deal_hands_,
                deal_seed=deal_seed,
                bidding_collector=collector,
                on_bidding_decision=on_bidding_decision,
            )
        else:
            (
                t0,
                t1,
                all_scores,
                all_feats,
                initial_leader,
                starting_hands,
                winning_bid,
                dealer_pos,
                bidder_pos,
                actual_contract,
                actual_trump,
                auction_transcript,
            ) = play_single_hand(
                contract_type=contract_type,
                trump_suit=trump_suit,
                strategy=strategy,
                strategies=strategies,
                bidding_policy=bidding_policy,
                bidding_policies=bidding_policies,
                logger=logger,
                deal_id=deal_id,
                rng=local_rng,
                bidding_collector=collector,
                on_bidding_decision=on_bidding_decision,
            )

        # Log hand completion (if logger enabled)
        if logger and logger.is_enabled:
            # Compute v6 fields: redeal when all passed (winning_bid==0, no bidder)
            redeal_flag = (
                (winning_bid == 0 and bidder_pos is None)
                if winning_bid is not None
                else None
            )
            if bidder_pos is None or winning_bid == 0 or winning_bid is None:
                made_bid = None
            elif bidder_pos in (0, 2):
                made_bid = t0 >= winning_bid
            else:
                made_bid = t1 >= winning_bid
            logger.log_hand_end(
                deal_id=deal_id,
                seed=seed,
                contract=actual_contract,
                trump=actual_trump,
                leader=initial_leader,
                t0=t0,
                t1=t1,
                features=all_feats,
                scores=all_scores,
                hands=starting_hands,
                winning_bid=winning_bid,
                dealer_position=dealer_pos,
                bidder_position=bidder_pos,
                redeal_flag=redeal_flag,
                made_bid=made_bid,
                auction_transcript=auction_transcript,
            )

        # Fire HandEndEvent if hooks registered
        if hooks is not None:
            hooks.fire_hand_end(
                HandEndEvent(
                    deal_id=deal_id,
                    seed=seed,
                    hands=[
                        list(h) for h in starting_hands
                    ],  # Deep copy to avoid aliasing
                    dealer_seat=dealer_pos,
                    contract_type=actual_contract,
                    trump_suit=actual_trump,
                    initial_leader=initial_leader,
                    tricks_team0=t0,
                    tricks_team1=t1,
                    scores=list(all_scores),
                    features=[
                        dict(f) for f in all_feats
                    ],  # Copy dicts to avoid aliasing
                    winning_bid=winning_bid,
                    bidder_seat=bidder_pos,
                )
            )

        total0 += t0
        total1 += t1
        dist_team0[t0] += 1

        # Track win-rate counts (weighted: ties contribute 0.5 to each team)
        if t0 > 5:
            wins_team0 += 1.0
        elif t0 < 5:
            wins_team1 += 1.0
        else:  # t0 == 5 (tie)
            wins_team0 += 0.5
            wins_team1 += 0.5
            ties += 1

        # Compute and track points-based scoring
        points_team0, points_team1 = compute_points(winning_bid, bidder_pos, t0, t1)
        total_points_team0 += points_team0
        total_points_team1 += points_team1
        dist_points_team0[points_team0] = dist_points_team0.get(points_team0, 0) + 1
        dist_points_team1[points_team1] = dist_points_team1.get(points_team1, 0) + 1

        # Track bidding-related stats only when bidding occurred
        if winning_bid is not None and bidder_pos is not None:
            hands_with_bids += 1
            bid_values.append(winning_bid)
            bid_team_tricks = t0 if bidder_pos in (0, 2) else t1
            if bid_team_tricks >= winning_bid:
                made_count += 1
            else:
                set_count += 1

        # Process ALL 4 players' features
        for player_idx in range(4):
            # Determine this player's team's tricks
            if player_idx in (0, 2):
                team_tricks = t0
            else:
                team_tricks = t1

            score = all_scores[player_idx]
            feats = all_feats[player_idx]

            total_score_all += score
            player_samples += 1

            # Scalar score buckets (by this player's team's tricks)
            sb = score_buckets.setdefault(score, {"count": 0, "total_tricks": 0.0})
            sb["count"] += 1
            sb["total_tricks"] += team_tricks

            # Feature buckets (by this player's team's tricks)
            for fname, val in feats.items():
                fb = feature_buckets.setdefault(fname, {})
                vb = fb.setdefault(val, {"count": 0, "total_tricks": 0.0})
                vb["count"] += 1
                vb["total_tricks"] += team_tricks

    # Compute avg_tricks in each score bucket
    for score, stats in score_buckets.items():
        if stats["count"] > 0:
            stats["avg_tricks"] = stats["total_tricks"] / stats["count"]
        else:
            stats["avg_tricks"] = 0.0

    # Compute avg_tricks in each feature bucket
    for fname, by_val in feature_buckets.items():
        for val, stats in by_val.items():
            if stats["count"] > 0:
                stats["avg_tricks"] = stats["total_tricks"] / stats["count"]
            else:
                stats["avg_tricks"] = 0.0

    # Compute win rates (handle n=0 case)
    if n > 0:
        win_rate_team0 = wins_team0 / n
        win_rate_team1 = wins_team1 / n
        tie_rate = ties / n
    else:
        win_rate_team0 = None
        win_rate_team1 = None
        tie_rate = None

    # Build bidding_points object
    bidding_points = {
        "enabled": hands_with_bids > 0,
        "hands_with_bids": hands_with_bids,
    }
    if hands_with_bids > 0:
        bidding_points.update(
            {
                "avg_bid": sum(bid_values) / len(bid_values),
                "bid_distribution": {
                    bid: bid_values.count(bid) for bid in set(bid_values)
                },
                "make_rate": made_count / hands_with_bids,
                "set_rate": set_count / hands_with_bids,
            }
        )

    bidding_collectors = [c for c in collectors if c.rows] if collectors else []

    return {
        "hands": n,
        "contract_type": contract_type,
        "trump_suit": trump_suit,
        "avg_team0": total0 / n,
        "avg_team1": total1 / n,
        "distribution_team0": dist_team0,
        "win_rate_team0": win_rate_team0,
        "win_rate_team1": win_rate_team1,
        "tie_rate": tie_rate,
        "avg_score": total_score_all / player_samples if player_samples > 0 else 0,
        "score_buckets": score_buckets,
        "feature_buckets": feature_buckets,
        "player_samples": player_samples,
        # New points-based scoring aggregates
        "avg_points_team0": total_points_team0 / n,
        "avg_points_team1": total_points_team1 / n,
        "distribution_points_team0": dist_points_team0,
        "distribution_points_team1": dist_points_team1,
        "bidding_points": bidding_points,
        # Backward compatibility aliases
        "avg_score_player0": total_score_all / player_samples
        if player_samples > 0
        else 0,
        "score_buckets_player0": score_buckets,
        "feature_buckets_player0": feature_buckets,
        "bidding_collectors": bidding_collectors,
    }


def run_all_scenarios(
    n_per: int = 5000,
    seed: Optional[int] = None,
    strategy: Optional[Strategy] = None,
    logger: Optional["GameLogger"] = None,
) -> None:
    """
    Run simulations for:
      - High no-trump
      - Low no-trump
      - Suit contracts for C, D, H, S

    Args:
    n_per: number of hands per scenario.
        seed: random seed for reproducibility (each scenario gets seed + offset).
        strategy: strategy to use (defaults to GreedyStrategy).
        logger: optional GameLogger for structured JSONL logging.
    """
    scenarios = []

    # High and Low no-trump (no trump_suit)
    scenarios.append(("high", None, "High no-trump"))
    scenarios.append(("low", None, "Low no-trump"))

    # Suit contracts for each trump suit
    for suit in ["C", "D", "H", "S"]:
        label = f"Suit contract, trump={suit}"
        scenarios.append(("suit", suit, label))

    for i, (contract_type, trump_suit, label) in enumerate(scenarios):
        # Each scenario gets a different seed offset for variety
        scenario_seed = seed + i if seed is not None else None
        results = simulate_many_hands(
            n=n_per,
            contract_type=contract_type,
            trump_suit=trump_suit,
            seed=scenario_seed,
            strategy=strategy,
            logger=logger,
        )

        print("\n========================================")
        print(f"Scenario: {label}")
        print("========================================")
        print("Hands:            ", results["hands"])
        print("Player samples:   ", results["player_samples"], "(4x hands)")
        print("Contract type:    ", results["contract_type"])
        print("Trump suit:       ", results["trump_suit"])
        print("Avg score:        ", f"{results['avg_score']:.2f}")
        print("Avg tricks Team 0:", f"{results['avg_team0']:.3f}")
        print("Avg tricks Team 1:", f"{results['avg_team1']:.3f}")
        print(
            "Sum of avgs (≈10):", f"{results['avg_team0'] + results['avg_team1']:.3f}"
        )

        print("\nDistribution of Team 0 tricks:")
        dist = results["distribution_team0"]
        total_count = sum(dist.values())
        for k in range(11):
            count = dist[k]
            pct = 100.0 * count / total_count if total_count > 0 else 0.0
            print(f"  {k}: {count:5d}  ({pct:5.1f}%)")

        # Optional: print a small sample of score buckets for sanity checking
        buckets = results["score_buckets"]
        if buckets:
            print("\nSample of score buckets (hand score → avg tricks for team):")
            for score in sorted(buckets.keys())[:8]:
                b = buckets[score]
                print(
                    f"  Score {score:3d}: "
                    f"n={b['count']:4d}, avg_tricks={b['avg_tricks']:.3f}"
                )
