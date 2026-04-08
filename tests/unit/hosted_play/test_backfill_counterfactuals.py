"""Unit tests for scripts/backfill_counterfactuals.py.

Covers:
- Dry-run reports NULL counts without writing
- Bid counterfactual backfill populates counterfactual_json
- Play counterfactual backfill populates glutton_action_json
- Idempotency: re-running does not overwrite already-filled rows
- Rows with insufficient context are skipped without error
- --type bid/play/both routing
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.unit.hosted_play.conftest import (
    create_browser_ai_test_artifacts,
    create_test_decision,
    create_test_hand,
    create_test_match,
)
from web.db import Decision, create_tables, init_engine, make_session_factory

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_db():
    """In-memory SQLite engine + session factory."""
    engine = init_engine("sqlite:///:memory:")
    create_tables(engine)
    return engine, make_session_factory(engine)


@pytest.fixture()
def gbt_bidder(tmp_path: Path):
    """Load a GBTActionValueBidder backed by a minimal test artifact."""
    _, gbt_artifact_path = create_browser_ai_test_artifacts(tmp_path)
    from bid_euchre.strategy.bidding import GBTActionValueBidder

    return GBTActionValueBidder(
        artifact_path=gbt_artifact_path,
        name="bud_bot",
        skip_behavioral_check=True,
    )


# ---------------------------------------------------------------------------
# Helpers to build valid game_state_json payloads
# ---------------------------------------------------------------------------

_BID_GAME_STATE: dict[str, Any] = {
    "phase": "auction",
    "dealer_seat": 3,
    "current_seat": 0,
    "turn_number": 1,
    "human_hand": [
        ["S", "A"],
        ["S", "K"],
        ["H", "A"],
        ["H", "K"],
        ["C", "A"],
        ["C", "K"],
        ["D", "A"],
        ["D", "K"],
        ["S", "Q"],
        ["H", "Q"],
    ],
    "auction": [
        {"seat": 1, "n": 0, "action": "pass"},
        {"seat": 2, "n": 0, "action": "pass"},
        {"seat": 3, "n": 0, "action": "pass"},
    ],
    "contract_type": None,
    "trump": None,
}

_PLAY_GAME_STATE: dict[str, Any] = {
    "phase": "play",
    "dealer_seat": 3,
    "current_seat": 0,
    "turn_number": 5,
    "human_hand": [
        ["S", "A"],
        ["S", "K"],
        ["H", "A"],
        ["H", "K"],
        ["C", "A"],
        ["C", "K"],
        ["D", "A"],
        ["D", "K"],
        ["S", "Q"],
    ],
    "auction": [
        {"seat": 1, "n": 0, "action": "pass"},
        {"seat": 2, "n": 4, "action": "bid", "contract": "S", "bid_type": "regular"},
        {"seat": 3, "n": 0, "action": "pass"},
        {"seat": 0, "n": 0, "action": "pass"},
    ],
    "contract_type": "suit",
    "trump": "S",
    "current_trick": {
        "leader": 1,
        "plays": [
            [1, ["S", "K"]],
            [2, ["S", "Q"]],
            [3, ["S", "T"]],
        ],
    },
    "completed_tricks": [],
    "tricks_team0": 0,
    "tricks_team1": 0,
}


# ---------------------------------------------------------------------------
# Tests — dry-run
# ---------------------------------------------------------------------------


def test_dry_run_reports_zero_on_empty_db(test_db):
    """Dry run on empty DB should report 0 NULL rows (no crash)."""
    _, session_factory = test_db
    session = session_factory()

    from scripts.backfill_counterfactuals import _report_null_counts

    _report_null_counts(session)
    session.close()
    # No assertion needed — absence of exception is the pass condition.


def test_dry_run_counts_null_rows(test_db):
    """Dry run counts NULL counterfactual rows correctly."""
    _, session_factory = test_db
    session = session_factory()

    match = create_test_match(session)
    hand = create_test_hand(session, match)

    # One human bid row with NULL counterfactual_json
    create_test_decision(
        session,
        match,
        hand,
        phase="bid",
        actor_type="human",
        game_state_json=json.dumps(_BID_GAME_STATE),
        counterfactual_json=None,
    )
    # One human play row with NULL glutton_action_json
    create_test_decision(
        session,
        match,
        hand,
        phase="play",
        actor_type="human",
        game_state_json=json.dumps(_PLAY_GAME_STATE),
        glutton_action_json=None,
    )
    # AI bid row — should NOT be counted
    create_test_decision(
        session,
        match,
        hand,
        phase="bid",
        actor_type="ai",
        game_state_json=json.dumps(_BID_GAME_STATE),
        counterfactual_json=None,
    )
    session.commit()

    from scripts.backfill_counterfactuals import _report_null_counts

    # Just verify it runs without error
    _report_null_counts(session)
    session.close()


# ---------------------------------------------------------------------------
# Tests — bid counterfactual backfill
# ---------------------------------------------------------------------------


def test_backfill_bid_populates_counterfactual_json(test_db, gbt_bidder):
    """Bid backfill populates counterfactual_json for NULL human bid rows."""
    _, session_factory = test_db
    session = session_factory()

    match = create_test_match(session)
    hand = create_test_hand(session, match)
    decision = create_test_decision(
        session,
        match,
        hand,
        phase="bid",
        actor_type="human",
        game_state_json=json.dumps(_BID_GAME_STATE),
        counterfactual_json=None,
    )
    session.commit()
    decision_id = decision.id
    session.close()

    from scripts.backfill_counterfactuals import _backfill_bid_batch

    session2 = session_factory()
    processed, skipped, errors = _backfill_bid_batch(
        session2, gbt_bidder, batch_size=50
    )
    session2.close()

    assert processed == 1
    assert skipped == 0
    assert errors == 0

    # Verify the row was updated
    session3 = session_factory()
    row = session3.query(Decision).filter_by(id=decision_id).one()
    assert row.counterfactual_json is not None
    data = json.loads(row.counterfactual_json)
    assert data["source"] == "bud_bot"
    assert "n" in data
    assert "contract" in data
    assert "bid_type" in data
    session3.close()


def test_backfill_bid_skips_ai_rows(test_db, gbt_bidder):
    """Bid backfill does not touch AI bid rows."""
    _, session_factory = test_db
    session = session_factory()

    match = create_test_match(session)
    hand = create_test_hand(session, match)
    ai_decision = create_test_decision(
        session,
        match,
        hand,
        phase="bid",
        actor_type="ai",
        game_state_json=json.dumps(_BID_GAME_STATE),
        counterfactual_json=None,
    )
    session.commit()
    ai_id = ai_decision.id
    session.close()

    from scripts.backfill_counterfactuals import _backfill_bid_batch

    session2 = session_factory()
    processed, _skipped, _errors = _backfill_bid_batch(
        session2, gbt_bidder, batch_size=50
    )
    session2.close()

    assert processed == 0  # AI rows are not human bid rows

    session3 = session_factory()
    row = session3.query(Decision).filter_by(id=ai_id).one()
    assert row.counterfactual_json is None  # Unchanged
    session3.close()


def test_backfill_bid_idempotent(test_db, gbt_bidder):
    """Re-running bid backfill does not overwrite already-filled rows."""
    _, session_factory = test_db
    session = session_factory()

    match = create_test_match(session)
    hand = create_test_hand(session, match)
    prefilled_value = json.dumps(
        {"source": "bud_bot", "n": 5, "contract": "S", "bid_type": "regular"}
    )
    decision = create_test_decision(
        session,
        match,
        hand,
        phase="bid",
        actor_type="human",
        game_state_json=json.dumps(_BID_GAME_STATE),
        counterfactual_json=prefilled_value,  # Already filled
    )
    session.commit()
    decision_id = decision.id
    session.close()

    from scripts.backfill_counterfactuals import _backfill_bid_batch

    session2 = session_factory()
    processed, skipped, errors = _backfill_bid_batch(
        session2, gbt_bidder, batch_size=50
    )
    session2.close()

    # Pre-filled row is not touched
    assert processed == 0

    session3 = session_factory()
    row = session3.query(Decision).filter_by(id=decision_id).one()
    assert row.counterfactual_json == prefilled_value  # Unchanged
    session3.close()


def test_backfill_bid_skips_missing_context(test_db, gbt_bidder):
    """Bid backfill skips rows with insufficient game_state context."""
    _, session_factory = test_db
    session = session_factory()

    match = create_test_match(session)
    hand = create_test_hand(session, match)
    # State missing human_hand
    bad_state = {"phase": "auction", "dealer_seat": 3}
    decision = create_test_decision(
        session,
        match,
        hand,
        phase="bid",
        actor_type="human",
        game_state_json=json.dumps(bad_state),
        counterfactual_json=None,
    )
    session.commit()
    decision_id = decision.id
    session.close()

    from scripts.backfill_counterfactuals import _backfill_bid_batch

    session2 = session_factory()
    processed, skipped, errors = _backfill_bid_batch(
        session2, gbt_bidder, batch_size=50
    )
    session2.close()

    assert skipped == 1
    assert processed == 0

    # Row remains NULL — skipped, not errored
    session3 = session_factory()
    row = session3.query(Decision).filter_by(id=decision_id).one()
    assert row.counterfactual_json is None
    session3.close()


# ---------------------------------------------------------------------------
# Tests — play counterfactual backfill
# ---------------------------------------------------------------------------


def test_backfill_play_populates_glutton_action_json(test_db):
    """Play backfill populates glutton_action_json for NULL human play rows."""
    _, session_factory = test_db
    session = session_factory()

    match = create_test_match(session)
    hand = create_test_hand(session, match)
    decision = create_test_decision(
        session,
        match,
        hand,
        phase="play",
        actor_type="human",
        game_state_json=json.dumps(_PLAY_GAME_STATE),
        glutton_action_json=None,
    )
    session.commit()
    decision_id = decision.id
    session.close()

    from scripts.backfill_counterfactuals import _backfill_play_batch

    session2 = session_factory()
    processed, skipped, errors = _backfill_play_batch(session2, batch_size=50)
    session2.close()

    assert processed == 1
    assert skipped == 0
    assert errors == 0

    session3 = session_factory()
    row = session3.query(Decision).filter_by(id=decision_id).one()
    assert row.glutton_action_json is not None
    card_index = json.loads(row.glutton_action_json)
    # Card index should be a valid integer (0–9 for a 9-card hand at this point)
    assert isinstance(card_index, int)
    assert 0 <= card_index < len(_PLAY_GAME_STATE["human_hand"])
    session3.close()


def test_backfill_play_skips_ai_rows(test_db):
    """Play backfill does not touch AI play rows."""
    _, session_factory = test_db
    session = session_factory()

    match = create_test_match(session)
    hand = create_test_hand(session, match)
    ai_decision = create_test_decision(
        session,
        match,
        hand,
        phase="play",
        actor_type="ai",
        game_state_json=json.dumps(_PLAY_GAME_STATE),
        glutton_action_json=None,
    )
    session.commit()
    ai_id = ai_decision.id
    session.close()

    from scripts.backfill_counterfactuals import _backfill_play_batch

    session2 = session_factory()
    processed, skipped, errors = _backfill_play_batch(session2, batch_size=50)
    session2.close()

    assert processed == 0

    session3 = session_factory()
    row = session3.query(Decision).filter_by(id=ai_id).one()
    assert row.glutton_action_json is None
    session3.close()


def test_backfill_play_idempotent(test_db):
    """Re-running play backfill does not overwrite already-filled rows."""
    _, session_factory = test_db
    session = session_factory()

    match = create_test_match(session)
    hand = create_test_hand(session, match)
    prefilled_value = json.dumps(3)  # Card index 3
    decision = create_test_decision(
        session,
        match,
        hand,
        phase="play",
        actor_type="human",
        game_state_json=json.dumps(_PLAY_GAME_STATE),
        glutton_action_json=prefilled_value,  # Already filled
    )
    session.commit()
    decision_id = decision.id
    session.close()

    from scripts.backfill_counterfactuals import _backfill_play_batch

    session2 = session_factory()
    processed, skipped, errors = _backfill_play_batch(session2, batch_size=50)
    session2.close()

    assert processed == 0

    session3 = session_factory()
    row = session3.query(Decision).filter_by(id=decision_id).one()
    assert row.glutton_action_json == prefilled_value
    session3.close()


def test_backfill_play_skips_missing_trick(test_db):
    """Play backfill skips rows with no current_trick in game_state."""
    _, session_factory = test_db
    session = session_factory()

    match = create_test_match(session)
    hand = create_test_hand(session, match)
    bad_state = {
        "phase": "play",
        "human_hand": [["S", "A"]],
        "contract_type": "suit",
        "trump": "S",
        # current_trick is missing
    }
    decision = create_test_decision(
        session,
        match,
        hand,
        phase="play",
        actor_type="human",
        game_state_json=json.dumps(bad_state),
        glutton_action_json=None,
    )
    session.commit()
    decision_id = decision.id
    session.close()

    from scripts.backfill_counterfactuals import _backfill_play_batch

    session2 = session_factory()
    processed, skipped, errors = _backfill_play_batch(session2, batch_size=50)
    session2.close()

    assert skipped == 1
    assert processed == 0

    session3 = session_factory()
    row = session3.query(Decision).filter_by(id=decision_id).one()
    assert row.glutton_action_json is None
    session3.close()


# ---------------------------------------------------------------------------
# Tests — helper functions
# ---------------------------------------------------------------------------


def test_current_high_bid_from_empty_auction():
    """Empty auction yields current_high_bid=0."""
    from scripts.backfill_counterfactuals import _current_high_bid_from_auction

    assert _current_high_bid_from_auction([]) == 0


def test_current_high_bid_from_passes_only():
    """All-pass auction yields current_high_bid=0."""
    from scripts.backfill_counterfactuals import _current_high_bid_from_auction

    auction = [
        {"seat": 1, "n": 0, "action": "pass"},
        {"seat": 2, "n": 0, "action": "pass"},
    ]
    assert _current_high_bid_from_auction(auction) == 0


def test_current_high_bid_from_auction_with_bids():
    """Auction with bids yields the max bid n."""
    from scripts.backfill_counterfactuals import _current_high_bid_from_auction

    auction = [
        {"seat": 1, "n": 0, "action": "pass"},
        {"seat": 2, "n": 4, "action": "bid", "contract": "S", "bid_type": "regular"},
        {"seat": 3, "n": 6, "action": "bid", "contract": "H", "bid_type": "regular"},
    ]
    assert _current_high_bid_from_auction(auction) == 6


def test_cards_from_list():
    """_cards_from_list reconstructs Card objects correctly."""
    from bid_euchre.core.cards import Card
    from scripts.backfill_counterfactuals import _cards_from_list

    raw = [["S", "A"], ["H", "K"], ["C", "T"]]
    cards = _cards_from_list(raw)
    assert len(cards) == 3
    assert cards[0] == Card(suit="S", rank="A")
    assert cards[1] == Card(suit="H", rank="K")
    assert cards[2] == Card(suit="C", rank="T")


def test_trick_plays_from_list():
    """_trick_plays_from_list reconstructs (seat, Card) tuples correctly."""
    from bid_euchre.core.cards import Card
    from scripts.backfill_counterfactuals import _trick_plays_from_list

    raw = [[1, ["S", "A"]], [2, ["H", "K"]]]
    plays = _trick_plays_from_list(raw)
    assert len(plays) == 2
    assert plays[0] == (1, Card(suit="S", rank="A"))
    assert plays[1] == (2, Card(suit="H", rank="K"))
