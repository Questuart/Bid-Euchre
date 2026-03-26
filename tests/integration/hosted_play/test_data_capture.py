"""Integration tests for the deployment data-capture pipeline.

Validates the full hosted-play → data-capture pipeline end to end:

1. Create a match via the test client.
2. Play through at least one human decision (bid and/or card play).
3. Verify decision rows are written to the DB.
4. Verify JSONL export works for the match.

This proves the hosted play → DB decision logging → JSONL export pipeline
works correctly.
"""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.integration

from starlette.testclient import TestClient

from bid_euchre.hosted_play.engine import HUMAN_SEAT, MatchEngine
from tests.unit.hosted_play.conftest import make_hosted_play_test_config
from web.app import create_app
from web.db import Decision, Hand, Match, Player
from web.export import REQUIRED_FIELDS, export_decisions

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def config(tmp_path):
    """File-based SQLite config for test isolation."""
    db_path = tmp_path / "test_data_capture.db"
    return make_hosted_play_test_config(tmp_path, database_url=f"sqlite:///{db_path}")


@pytest.fixture()
def app(config):
    """FastAPI app configured with test DB."""
    return create_app(config=config)


@pytest.fixture()
def client(app):
    """TestClient for the app."""
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_game(client: TestClient) -> str:
    """POST /new and return the link_uuid from the redirect URL."""
    resp = client.post("/new", follow_redirects=False)
    assert resp.status_code == 302
    location = resp.headers["location"]
    link_uuid = location.split("/play/")[1]
    return link_uuid


def _set_nickname(client: TestClient, link_uuid: str, nickname: str = "Tester"):
    """Set nickname and return the response."""
    return client.post(
        f"/play/{link_uuid}/nickname",
        data={"nickname": nickname},
    )


def _select_ai(client: TestClient, link_uuid: str, model_id: str = "olsa"):
    """Select AI model and return the response."""
    return client.post(
        f"/play/{link_uuid}/select-ai",
        data={"model_id": model_id},
    )


def _get_match_state(app, link_uuid: str):
    """Load the current match state from the DB for assertions.

    Returns (state, match_row, session) or None if no match found.
    Caller must close the session.
    """
    session_factory = app.state.session_factory
    session = session_factory()
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            session.close()
            return None

        match_row = (
            session.query(Match)
            .filter_by(player_id=player.id)
            .order_by(Match.created_at.desc())
            .first()
        )
        if match_row is None:
            session.close()
            return None

        ai_manager = app.state.ai_manager
        info = ai_manager.get_model_info(match_row.ai_model)
        engine = MatchEngine(
            bidding_policy=info.bidding_policy,
            play_strategy=info.play_strategy,
        )
        state = engine.deserialize(json.loads(match_row.match_state_json))
        return state, match_row, session
    except Exception:
        session.close()
        raise


def _setup_game(client: TestClient) -> str:
    """Create game, set nickname, select AI, return link_uuid."""
    link_uuid = _create_game(client)
    _set_nickname(client, link_uuid)
    _select_ai(client, link_uuid)
    return link_uuid


def _play_human_turns(client: TestClient, app, link_uuid: str) -> int:
    """Play human turns until at least one bid and one card play are made.

    Returns the number of human actions submitted.  Iterates the game
    loop: when it's the human's turn in auction, submit a pass; when
    in trick play, play the first legal card.

    Safety-bounded to 40 iterations to avoid infinite loops on redeals.
    """
    human_bids = 0
    human_plays = 0
    max_iterations = 40

    for _ in range(max_iterations):
        result = _get_match_state(app, link_uuid)
        assert result is not None, "Match disappeared unexpectedly"
        state, _, session = result
        session.close()

        hand = state.current_hand
        if hand is None or state.status == "complete":
            break

        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            client.post(
                f"/play/{link_uuid}/bid",
                data={
                    "turn_number": hand.turn_number,
                    "bid_n": 0,
                    "bid_contract": "",
                },
            )
            human_bids += 1

        elif hand.phase == "trick_play" and hand.current_seat == HUMAN_SEAT:
            ai_manager = app.state.ai_manager
            info = ai_manager.get_model_info(state.ai_model)
            engine = MatchEngine(
                bidding_policy=info.bidding_policy,
                play_strategy=info.play_strategy,
            )
            legal = engine.get_legal_plays(state)
            assert len(legal) > 0, "No legal plays available"

            client.post(
                f"/play/{link_uuid}/play-card",
                data={
                    "turn_number": hand.turn_number,
                    "card_index": legal[0],
                },
            )
            human_plays += 1

            # Once we have at least one card play, we have enough data
            if human_plays >= 1:
                break

        else:
            # Not human's turn (shouldn't happen, but guard against spin)
            break

    return human_bids + human_plays


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDataCapturePipeline:
    """End-to-end test of the hosted play → data capture pipeline.

    Exercises the full flow: match creation → human decisions → DB
    persistence → JSONL export.
    """

    def test_match_creation_persists_to_db(self, client, app):
        """Creating a match via the API produces DB rows (player, match, hand)."""
        link_uuid = _setup_game(client)

        session = app.state.session_factory()
        try:
            # Player exists
            player = session.query(Player).filter_by(link_uuid=link_uuid).first()
            assert player is not None, "Player row not created"
            assert player.nickname == "Tester"

            # Match exists
            match_row = session.query(Match).filter_by(player_id=player.id).first()
            assert match_row is not None, "Match row not created"
            assert match_row.status == "active"
            assert match_row.ai_model == "olsa"
            assert match_row.seed is not None

            # Hand row exists (first hand is dealt on match creation)
            hand_row = session.query(Hand).filter_by(match_id=match_row.id).first()
            assert hand_row is not None, "Initial hand row not created"
            assert hand_row.status == "in_progress"
        finally:
            session.close()

    def test_human_decisions_logged_to_db(self, client, app):
        """Playing human turns produces decision rows in the DB."""
        link_uuid = _setup_game(client)
        actions_played = _play_human_turns(client, app, link_uuid)
        assert actions_played > 0, "No human actions were played"

        session = app.state.session_factory()
        try:
            decisions = session.query(Decision).all()
            assert len(decisions) > 0, "No decision rows in DB"

            # At least one human decision must exist
            human_decisions = [d for d in decisions if d.actor_type == "human"]
            assert len(human_decisions) > 0, "No human decision rows logged"

            # At least one persisted play decision (not just bids)
            human_play_decisions = [d for d in human_decisions if d.phase == "play"]
            assert (
                len(human_play_decisions) > 0
            ), "No human play decision rows persisted in DB"

            # Verify decision row structure
            for d in human_decisions:
                assert d.seat == HUMAN_SEAT
                assert d.phase in ("bid", "play")
                assert d.decision_source == "human"
                assert d.legal_actions_json is not None
                assert d.chosen_action_json is not None
                assert d.game_state_json is not None

                # JSON columns must be valid JSON
                json.loads(d.legal_actions_json)
                json.loads(d.chosen_action_json)
                json.loads(d.game_state_json)

            # AI decisions should also be logged (from auto-advance)
            ai_decisions = [d for d in decisions if d.actor_type == "ai"]
            assert len(ai_decisions) > 0, "No AI decision rows logged"

            for d in ai_decisions:
                assert d.decision_source == "olsa"
                assert d.phase in ("bid", "play")
        finally:
            session.close()

    def test_jsonl_export_produces_valid_output(self, client, app, tmp_path):
        """JSONL export of a match with decisions produces valid records."""
        link_uuid = _setup_game(client)
        actions_played = _play_human_turns(client, app, link_uuid)
        assert actions_played > 0, "No human actions were played"

        # Get the match UUID for filtered export
        session = app.state.session_factory()
        try:
            player = session.query(Player).filter_by(link_uuid=link_uuid).first()
            match_row = session.query(Match).filter_by(player_id=player.id).first()
            match_uuid = match_row.match_uuid
        finally:
            session.close()

        # Export to JSONL
        export_path = tmp_path / "decisions.jsonl"
        session = app.state.session_factory()
        try:
            count = export_decisions(session, export_path, match_uuid=match_uuid)
        finally:
            session.close()

        assert count > 0, "export_decisions returned 0 records"
        assert export_path.exists(), "JSONL file was not created"

        # Parse and validate each line
        records = []
        with open(export_path) as f:
            for line_num, raw in enumerate(f, 1):
                raw = raw.strip()
                assert raw, f"Empty line at {line_num}"
                record = json.loads(raw)
                records.append(record)

        assert (
            len(records) == count
        ), f"Line count ({len(records)}) != export count ({count})"

        # Every record must have all required SP-4-01 fields
        for i, record in enumerate(records):
            missing = REQUIRED_FIELDS - set(record.keys())
            assert not missing, f"Record {i} missing required fields: {missing}"
            assert record["schema_version"] == 1
            assert record["event"] == "hosted_decision"
            assert record["match_uuid"] == match_uuid

    def test_jsonl_export_human_only_filter(self, client, app, tmp_path):
        """JSONL export with human_only=True only includes human decisions."""
        link_uuid = _setup_game(client)
        actions_played = _play_human_turns(client, app, link_uuid)
        assert actions_played > 0

        session = app.state.session_factory()
        try:
            player = session.query(Player).filter_by(link_uuid=link_uuid).first()
            match_row = session.query(Match).filter_by(player_id=player.id).first()
            match_uuid = match_row.match_uuid
        finally:
            session.close()

        export_path = tmp_path / "human_decisions.jsonl"
        session = app.state.session_factory()
        try:
            count = export_decisions(
                session,
                export_path,
                match_uuid=match_uuid,
                human_only=True,
            )
        finally:
            session.close()

        assert count > 0, "No human decisions exported"

        with open(export_path) as f:
            for raw in f:
                record = json.loads(raw.strip())
                assert (
                    record["actor_type"] == "human"
                ), f"Non-human record in human_only export: {record['actor_type']}"

    def test_decision_ordering_in_export(self, client, app, tmp_path):
        """Exported decisions are ordered by hand_number then turn_number."""
        link_uuid = _setup_game(client)
        _play_human_turns(client, app, link_uuid)

        session = app.state.session_factory()
        try:
            player = session.query(Player).filter_by(link_uuid=link_uuid).first()
            match_row = session.query(Match).filter_by(player_id=player.id).first()
            match_uuid = match_row.match_uuid
        finally:
            session.close()

        export_path = tmp_path / "ordered.jsonl"
        session = app.state.session_factory()
        try:
            export_decisions(session, export_path, match_uuid=match_uuid)
        finally:
            session.close()

        records = []
        with open(export_path) as f:
            for raw in f:
                records.append(json.loads(raw.strip()))

        if len(records) < 2:
            pytest.skip("Not enough decisions to verify ordering")

        # Verify monotonic ordering: (hand_number, turn_number)
        for i in range(1, len(records)):
            prev = (records[i - 1]["hand_number"], records[i - 1]["turn_number"])
            curr = (records[i]["hand_number"], records[i]["turn_number"])
            assert curr >= prev, f"Records not ordered: {prev} > {curr} at index {i}"

    def test_hand_rows_track_match_progress(self, client, app):
        """Hand rows are created as the match progresses through deals."""
        link_uuid = _setup_game(client)
        _play_human_turns(client, app, link_uuid)

        session = app.state.session_factory()
        try:
            player = session.query(Player).filter_by(link_uuid=link_uuid).first()
            match_row = session.query(Match).filter_by(player_id=player.id).first()
            hands = (
                session.query(Hand)
                .filter_by(match_id=match_row.id)
                .order_by(Hand.hand_number)
                .all()
            )

            assert len(hands) >= 1, "Expected at least one hand row"

            for hand in hands:
                assert hand.deal_id is not None
                assert hand.dealer_seat in (0, 1, 2, 3)
                assert hand.status in ("in_progress", "redeal", "complete")
                # hand_state_json must be valid JSON
                json.loads(hand.hand_state_json)
        finally:
            session.close()

    def test_full_pipeline_match_to_export(self, client, app, tmp_path):
        """Full pipeline: create match → play decisions → export JSONL → validate.

        This is the primary smoke test for the deployment data-capture pipeline.
        It exercises every layer: HTTP routes, DB persistence, decision logging,
        and JSONL export.
        """
        # 1. Create a match
        link_uuid = _setup_game(client)

        # 2. Play through human decisions
        actions_played = _play_human_turns(client, app, link_uuid)
        assert actions_played > 0, "No human actions were played"

        # 3. Verify DB state
        session = app.state.session_factory()
        try:
            player = session.query(Player).filter_by(link_uuid=link_uuid).first()
            assert player is not None
            match_row = session.query(Match).filter_by(player_id=player.id).first()
            assert match_row is not None
            match_uuid = match_row.match_uuid

            decisions = session.query(Decision).filter_by(match_id=match_row.id).all()
            assert len(decisions) > 0, "No decisions in DB"

            hands = session.query(Hand).filter_by(match_id=match_row.id).all()
            assert len(hands) > 0, "No hands in DB"

            # Decisions reference valid hands
            hand_ids = {h.id for h in hands}
            for d in decisions:
                assert (
                    d.hand_id in hand_ids
                ), f"Decision {d.id} references unknown hand {d.hand_id}"
        finally:
            session.close()

        # 4. Export to JSONL and validate
        export_path = tmp_path / "pipeline.jsonl"
        session = app.state.session_factory()
        try:
            count = export_decisions(session, export_path, match_uuid=match_uuid)
        finally:
            session.close()

        assert count == len(
            decisions
        ), f"Export count ({count}) != DB decision count ({len(decisions)})"

        # Parse all records and verify structural integrity
        with open(export_path) as f:
            records = [json.loads(line.strip()) for line in f if line.strip()]

        assert len(records) == count
        for record in records:
            assert record["match_uuid"] == match_uuid
            assert record["schema_version"] == 1
            assert record["event"] == "hosted_decision"
            assert record["phase"] in ("bid", "play")
            assert record["actor_type"] in ("human", "ai")
            assert record["seat"] in (0, 1, 2, 3)
            assert isinstance(record["legal_actions"], (list, dict))
            assert record["chosen_action"] is not None
