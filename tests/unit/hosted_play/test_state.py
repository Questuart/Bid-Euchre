from bid_euchre.core.cards import Card
from bid_euchre.hosted_play import HandState, MatchState, TrickResult, TrickState


def test_match_state_round_trip_with_nested_hand_state() -> None:
    state = MatchState(
        seed=42,
        ai_model="hybrid_olsa",
        score_human=12,
        score_ai=-3,
        hands_played=4,
        status="active",
        dealer_seat=2,
        deal_id=9,
        current_hand=HandState(
            phase="trick_play",
            hands=[
                [Card("S", "A"), Card("H", "K")],
                [Card("C", "Q")],
                [Card("D", "J")],
                [Card("S", "T")],
            ],
            dealer_seat=2,
            deal_id=9,
            auction=[
                {"seat": 3, "n": 0, "contract": None},
                {"seat": 0, "n": 5, "contract": "S"},
            ],
            current_high_bid=5,
            bidder_seat=0,
            winning_bid=5,
            contract_type="suit",
            trump="S",
            current_trick=TrickState(
                leader=0,
                plays=[(0, Card("S", "A")), (1, Card("C", "Q"))],
            ),
            completed_tricks=[
                TrickResult(
                    leader=3,
                    plays=[
                        (3, Card("H", "A")),
                        (0, Card("H", "K")),
                        (1, Card("H", "Q")),
                        (2, Card("H", "J")),
                    ],
                    winner=3,
                )
            ],
            tricks_team0=1,
            tricks_team1=0,
            points_team0=0,
            points_team1=0,
            current_seat=2,
            turn_number=6,
        ),
    )

    restored = MatchState.from_dict(state.to_dict())

    assert restored == state


def test_match_state_round_trip_without_current_hand() -> None:
    state = MatchState(
        seed=7,
        ai_model="heuristic",
        score_human=52,
        score_ai=18,
        hands_played=11,
        current_hand=None,
        status="complete",
        winner="human",
        dealer_seat=1,
        deal_id=11,
    )

    restored = MatchState.from_dict(state.to_dict())

    assert restored == state
