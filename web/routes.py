"""Route handlers for the Bid Euchre browser game.

All game-action POSTs include ``turn_number`` for idempotent submission.
If the submitted turn doesn't match the current expected turn the POST
returns the current visible state without modifying anything.

Delegates game logic to :class:`~bid_euchre.hosted_play.engine.MatchEngine`;
no rule/scoring logic lives here.
"""

from __future__ import annotations

import copy
import json
import logging
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import text
from starlette.templating import Jinja2Templates

logger = logging.getLogger(__name__)

from bid_euchre.core.rules import trick_winner
from bid_euchre.hosted_play.engine import HUMAN_SEAT, MatchEngine, sort_hand_for_display
from bid_euchre.strategy.bidding import BidAction

from .ai_manager import AIManager
from .cleanup import abandon_player_active_matches
from .db import Comment, Decision, Hand, InviteCode, Match, Player
from .leaderboard import METRIC_DEFINITIONS, format_metric, get_leaderboard
from .middleware import (
    get_player_link_from_cookie,
    get_request_id,
    lookup_active_match,
    set_player_cookie,
)

# Threshold (ms) above which a sub-phase is flagged as slow.
_SLOW_SUBPHASE_MS = 200.0

router = APIRouter()

# ---------------------------------------------------------------------------
# AI character names — replace positional labels with personality
# ---------------------------------------------------------------------------
# Positional info is conveyed by seat position on the board.  Character names
# add flavour to the card-game feel.
SEAT_LABELS: dict[int, str] = {
    0: "You",
    1: "Slim",  # left opponent
    2: "Ace",  # partner
    3: "Deuce",  # right opponent
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_slow_subphases(
    action: str,
    match_uuid: str,
    *,
    deser_ms: float = 0.0,
    engine_ms: float = 0.0,
    commit_ms: float = 0.0,
) -> None:
    """Emit a WARNING log when any sub-phase exceeds the slow threshold."""
    if (
        deser_ms > _SLOW_SUBPHASE_MS
        or engine_ms > _SLOW_SUBPHASE_MS
        or commit_ms > _SLOW_SUBPHASE_MS
    ):
        logger.warning(
            "slow_subphase action=%s match=%s deser_ms=%.1f engine_ms=%.1f commit_ms=%.1f request_id=%s",
            action,
            match_uuid,
            deser_ms,
            engine_ms,
            commit_ms,
            get_request_id(),
        )


def _get_templates(request: Request) -> Jinja2Templates:
    """Retrieve the Jinja2Templates stashed on ``app.state`` during startup."""
    return request.app.state.templates


def _get_ai_manager(request: Request) -> AIManager:
    """Retrieve the AIManager stashed on ``app.state`` during startup."""
    return request.app.state.ai_manager


def _get_config(request: Request):
    """Retrieve the HostedPlayConfig stashed on ``app.state`` during startup."""
    return request.app.state.config


def _get_session(request: Request):
    """Create a new DB session from the factory on ``app.state``."""
    return request.app.state.session_factory()


def _build_engine(ai_manager: AIManager, model_id: str) -> MatchEngine:
    """Instantiate a MatchEngine for the given *model_id*.

    The play strategy is deep-copied so each match gets its own mutable
    state (seen_counts, void_suits, contract context).  Without this,
    concurrent matches sharing a single GluttonStrategy instance would
    contaminate each other's tracking state.  See #2168.
    """
    info = ai_manager.get_model_info(model_id)
    return MatchEngine(
        bidding_policy=info.bidding_policy,
        play_strategy=copy.deepcopy(info.play_strategy),
    )


def _serialize_state(engine: MatchEngine, state) -> str:
    """Serialize match state to JSON string."""
    return json.dumps(engine.serialize(state))


def _deserialize_state(engine: MatchEngine, data: str):
    """Deserialize match state from JSON string."""
    return engine.deserialize(json.loads(data))


def _ensure_hand_row(
    session,
    match_row: Match,
    hand_state,
    hand_number: int,
) -> Hand:
    """Get or create the Hand row for the current hand.

    Returns the existing row if it already exists for this
    (match_id, hand_number) pair; creates a new one otherwise.
    """
    hand_row = (
        session.query(Hand)
        .filter_by(match_id=match_row.id, hand_number=hand_number)
        .first()
    )
    if hand_row is None:
        hand_row = Hand(
            match_id=match_row.id,
            hand_number=hand_number,
            deal_id=hand_state.deal_id,
            dealer_seat=hand_state.dealer_seat,
            status="in_progress",
            hand_state_json=json.dumps(hand_state.to_dict()),
        )
        session.add(hand_row)
        session.flush()
    return hand_row


def _update_hand_row(hand_row: Hand, hand_state) -> None:
    """Sync a Hand row with completed/redeal hand state."""
    hand_row.hand_state_json = json.dumps(hand_state.to_dict())
    if hand_state.phase == "complete":
        hand_row.status = "complete"
        hand_row.winning_bid_n = hand_state.winning_bid
        hand_row.winning_bid_type = hand_state.bid_type
        hand_row.bidder_seat = hand_state.bidder_seat
        hand_row.sitting_out_seat = hand_state.sitting_out_seat
        hand_row.contract_type = hand_state.contract_type
        hand_row.trump_suit = hand_state.trump
        hand_row.winning_contract = _winning_contract_code(hand_state)
        hand_row.tricks_team0 = hand_state.tricks_team0
        hand_row.tricks_team1 = hand_state.tricks_team1
        hand_row.points_team0 = hand_state.points_team0
        hand_row.points_team1 = hand_state.points_team1
        hand_row.completed_at = datetime.now(timezone.utc)
    elif hand_state.phase == "redeal":
        hand_row.status = "redeal"


def _winning_contract_code(hand_state) -> str | None:
    """Derive the winning_contract column value from hand state."""
    ct = hand_state.contract_type
    if ct is None:
        return None
    if ct == "suit":
        return hand_state.trump  # 'C', 'D', 'H', or 'S'
    return ct.upper()  # 'HIGH' or 'LOW'


def _update_match_row(match_row: Match, state) -> None:
    """Sync the Match row with current match state."""
    match_row.match_state_json = json.dumps(state.to_dict())
    match_row.score_human = state.score_human
    match_row.score_ai = state.score_ai
    match_row.hands_played = state.hands_played
    if state.status == "complete":
        match_row.status = "complete"
        match_row.completed_at = datetime.now(timezone.utc)


def _log_decision(
    session,
    match_row: Match,
    hand_row: Hand,
    turn_number: int,
    seat: int,
    phase: str,
    actor_type: str,
    decision_source: str,
    legal_actions: Any,
    chosen_action: Any,
    game_state: Any,
    decision_time_ms: int | None = None,
) -> None:
    """Insert a decision row (idempotent — skips if turn already logged)."""
    exists = (
        session.query(Decision)
        .filter_by(hand_id=hand_row.id, turn_number=turn_number)
        .first()
    )
    if exists is not None:
        return
    decision = Decision(
        match_id=match_row.id,
        hand_id=hand_row.id,
        turn_number=turn_number,
        seat=seat,
        phase=phase,
        actor_type=actor_type,
        decision_source=decision_source,
        legal_actions_json=json.dumps(legal_actions),
        chosen_action_json=json.dumps(chosen_action),
        game_state_json=json.dumps(game_state),
        decision_time_ms=decision_time_ms,
    )
    session.add(decision)


def _has_hidden_auction(hand) -> bool:
    """Return True when the auction transcript still has hidden entries."""
    return hand.revealed_auction_count < len(hand.auction)


def _auction_reveal_active(hand) -> bool:
    """Return True when auction reveal or settle pause is in progress.

    Covers two states:
    1. Hidden bids remain to reveal (_has_hidden_auction)
    2. All bids revealed but settle pause not yet dismissed (!auction_settled)
    """
    return _has_hidden_auction(hand) or not hand.auction_settled


def _has_pending_exchange(hand) -> bool:
    """Return True when a moon exchange happened but hasn't been shown yet."""
    return (
        hand.bid_type == "moon"
        and hand.exchange_given is not None
        and not hand.exchange_revealed
    )


def _awaiting_next(hand) -> bool:
    """Whether hosted play is paused waiting on a reveal-step advance."""
    return (
        _auction_reveal_active(hand)
        or _has_pending_exchange(hand)
        or (hand.phase == "trick_play" and hand.paused_after_play)
        or (hand.phase == "trick_play" and hand.paused_after_trick)
        or (hand.phase == "complete" and hand.paused_after_trick)
        or hand.phase == "redeal"
    )


def _last_played_seat(hand) -> int | None:
    """Return the seat that played the most recent card in the active trick."""
    trick = hand.current_trick
    if trick is not None and trick.plays:
        return trick.plays[-1][0]
    return None


def _next_reason(hand) -> str | None:
    """Human-readable label for the current reveal pause."""
    if _has_hidden_auction(hand):
        return "Reveal the next auction action."
    if not hand.auction_settled:
        return "Auction complete. Continue to play."
    if _has_pending_exchange(hand):
        return "Review the moon exchange."
    if hand.phase == "trick_play" and hand.paused_after_play:
        last_seat = _last_played_seat(hand)
        if last_seat == HUMAN_SEAT:
            return "Your card is played. Press Next to continue."
        return "Reveal the next card."
    if hand.phase == "trick_play" and hand.paused_after_trick:
        return "Continue to the next trick."
    if hand.phase == "complete" and hand.paused_after_trick:
        return "See the hand result."
    if hand.phase == "redeal":
        return "All players passed. Deal a new hand."
    return None


def _game_phase(state, *, force_match_result: bool = False) -> str:
    """Map engine state to the template ``phase`` variable.

    The ``game.html`` template dispatches on this value to select which
    partials to include.

    Parameters
    ----------
    force_match_result:
        When *True*, skip the hand-result interstitial and go straight to
        the match-result screen.  Used by the ``/next-hand`` handler after
        the player has already seen the final hand result (#2239).
    """
    hand = state.current_hand

    # Trick-result interstitial: when the last trick just completed and
    # paused_after_trick is set (including trick 10 where hand.phase is
    # already "complete"), show the trick_play board so the player sees
    # the final trick result before advancing to hand_result (#2210).
    if (
        hand is not None
        and hand.paused_after_trick
        and hand.phase in ("trick_play", "complete")
    ):
        return "trick_play"

    if state.status == "complete":
        # Show the final hand result before the match-over screen so the
        # player can review the last hand (#2239).  The hand_result partial
        # renders a "See Match Results" CTA when match_status == "complete".
        if not force_match_result and hand is not None and hand.phase == "complete":
            return "hand_result"
        return "match_result"
    if hand is None:
        return "model_select"
    if hand.phase == "complete":
        return "hand_result"
    if _auction_reveal_active(hand):
        return "auction"
    if hand.phase == "moon_exchange" and hand.exchange_phase == "selecting":
        return "moon_exchange_select"
    if _has_pending_exchange(hand):
        return "moon_exchange"
    # "auction", "trick_play", "moon_exchange", or "redeal" pass through
    return hand.phase


def _format_auction_event(seat: int | None, action: dict[str, Any]) -> str:
    """Format a single auction event for the auction log."""
    seat_label = SEAT_LABELS.get(int(seat), f"Seat {seat}")

    if action.get("action") == "pass":
        return f"{seat_label} passed"

    bid_type = action.get("bid_type", "regular")
    if bid_type == "moon":
        return f"{seat_label} bid Moon"
    if bid_type == "loner":
        return f"{seat_label} bid Loner"

    # Regular bid
    n = action.get("n", 0)
    contract = action.get("contract", "")
    if contract == "HIGH":
        contract_label = "High"
    elif contract == "LOW":
        contract_label = "Low"
    else:
        contract_label = _SUIT_SYMBOLS.get(str(contract), str(contract))
    return f"{seat_label} bid {n} {contract_label}"


_SUIT_SYMBOLS: dict[str, str] = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}


def _build_seat_bids(auction: list[dict[str, Any]]) -> dict[int, str]:
    """Build a mapping from seat → compact bid text for inline display.

    Returns at most one entry per seat (the most recent bid from each player
    who has bid so far in the visible auction transcript).
    """
    seat_bids: dict[int, str] = {}
    for entry in auction:
        seat = entry.get("seat")
        if seat is None:
            continue
        seat = int(seat)
        if entry.get("action") == "pass":
            seat_bids[seat] = "Pass"
        else:
            bid_type = entry.get("bid_type", "regular")
            if bid_type == "moon":
                seat_bids[seat] = "Moon"
            elif bid_type == "loner":
                seat_bids[seat] = "Loner"
            else:
                n = entry.get("n", 0)
                contract = entry.get("contract", "")
                if contract == "HIGH":
                    seat_bids[seat] = f"{n} Hi"
                elif contract == "LOW":
                    seat_bids[seat] = f"{n} Lo"
                else:
                    sym = _SUIT_SYMBOLS.get(str(contract), str(contract))
                    seat_bids[seat] = f"{n}{sym}"
    return seat_bids


def _build_action_rail(state) -> list[dict[str, str]]:
    """Build the auction-log event feed with auction actions only.

    Shows bids, passes, the auction result, and redeal notices.
    Trick results are intentionally excluded — they belong in the trick
    history panel, not the auction log (#2477).

    The list is capped to the most recent 12 entries for compact rendering.

    Auction entries are sourced from ``state.current_hand.auction`` (the full
    persisted transcript), sliced to ``revealed_auction_count``, so a page
    refresh never loses already-revealed auction entries (#2207).
    """
    hand = state.current_hand
    if hand is None:
        return []

    events: list[dict[str, str]] = []

    # Auction activity (in order).
    # Use the full persisted auction from the hand state, sliced to the
    # revealed count, so a page refresh cannot drop entries (#2207).
    full_auction = list(hand.auction)
    revealed = full_auction[: hand.revealed_auction_count]
    for entry in revealed:
        events.append(
            {
                "kind": "auction",
                "text": _format_auction_event(entry.get("seat"), entry),
            }
        )

    # Auction result — shown once the auction is settled and a winner exists.
    # Guard on phase != "auction" so the result line does not appear
    # prematurely when AIs have bid (setting bidder_seat) but the human
    # hasn't taken their turn yet (#2493).
    if (
        hand.phase != "auction"
        and hand.auction_settled
        and hand.bidder_seat is not None
    ):
        bidder = SEAT_LABELS.get(hand.bidder_seat, f"Seat {hand.bidder_seat}")
        bid_type = hand.bid_type
        if bid_type == "moon":
            result_label = "Moon"
        elif bid_type == "loner":
            result_label = "Loner"
        elif hand.contract_type == "suit" and hand.trump is not None:
            sym = _SUIT_SYMBOLS.get(hand.trump, hand.trump)
            result_label = f"{hand.winning_bid} {sym}"
        elif hand.contract_type == "high":
            result_label = f"{hand.winning_bid} High"
        elif hand.contract_type == "low":
            result_label = f"{hand.winning_bid} Low"
        else:
            result_label = str(hand.winning_bid)
        events.append(
            {"kind": "result", "text": f"{bidder} wins auction: {result_label}"}
        )

    # Redeal transition (all players passed — an auction-phase event).
    if hand.phase == "redeal":
        events.append(
            {"kind": "system", "text": "All players passed; redeal starting."}
        )

    return events[-12:]


def _build_game_context(
    engine: MatchEngine,
    state,
    link_uuid: str,
    *,
    force_match_result: bool = False,
) -> dict[str, Any]:
    """Build the Jinja2 template context for the game board.

    Combines visible state (from ``engine.get_visible_state``) with additional
    fields needed by the partials (winning_bid, bidder_seat, current_high_bid,
    points, legal plays, AI hand counts).
    """
    visible = engine.get_visible_state(state)
    hand = state.current_hand
    phase = _game_phase(state, force_match_result=force_match_result)

    # Defensive normalization: when the auction is settled (or we're past
    # auction), ensure revealed_auction_count covers the full auction.
    # Without this a stale revealed_auction_count could cause _build_action_rail
    # to omit entries that were already shown before a page refresh (#2207).
    if hand is not None and hand.auction_settled and not _has_hidden_auction(hand):
        hand.revealed_auction_count = max(
            hand.revealed_auction_count, len(hand.auction)
        )

    if hand is not None and _has_hidden_auction(hand):
        visible["auction"] = visible.get("auction", [])[: hand.revealed_auction_count]
        visible["contract_type"] = None
        visible["trump"] = None
        # Re-sort visible hand WITHOUT trump knowledge so card order doesn't
        # reveal trump prematurely during the hidden auction reveal (#2133).
        auction_hand = list(hand.hands[HUMAN_SEAT])
        sort_hand_for_display(auction_hand)  # no contract_type / trump
        visible["human_hand"] = [[c.suit, c.rank] for c in auction_hand]
        # Hide trick-play state leaked by engine auto-advance — the user
        # hasn't finished revealing auction bids yet.
        visible["current_trick"] = None
        visible["completed_tricks"] = []
        visible["tricks_team0"] = 0
        visible["tricks_team1"] = 0
    elif hand is not None and not hand.auction_settled:
        # Settle pause — all bids revealed but the user hasn't dismissed
        # the auction-complete interstitial yet.  The engine may have
        # already auto-advanced into trick play (processing AI trick cards
        # during the submit_bid call), but the user hasn't seen the
        # auction result.  Hide trick-play state so the transition screen
        # shows a clean "Auction complete" view (#2208).
        visible["current_trick"] = None
        visible["completed_tricks"] = []
        visible["tricks_team0"] = 0
        visible["tricks_team1"] = 0
        # Suppress the turn indicator — current_seat may reflect the first
        # trick-play turn after auto-advance, which is misleading during the
        # auction-settle interstitial (#2237).
        visible["current_seat"] = None
    if (
        hand is not None
        and hand.paused_after_trick
        and hand.phase
        in (
            "trick_play",
            "complete",
        )
    ):
        visible["current_trick"] = None

    ctx: dict[str, Any] = {
        "link_uuid": link_uuid,
        "current_page": "game",
        "match_status": state.status,
        "seat_labels": SEAT_LABELS,
        **visible,
    }
    ctx["phase"] = phase

    # Fields only available from hand state (not in visible dict)
    if hand is not None:
        show_next = _awaiting_next(hand)
        ctx["show_next"] = show_next
        ctx["next_reason"] = _next_reason(hand)
        # Show "Skip" button when mid-trick per-card pacing is active
        ctx["show_skip"] = hand.phase == "trick_play" and (
            hand.paused_after_play or hand.paused_after_trick
        )

        # AI card delay — flag tells the template to add a reveal
        # animation on the last-played card when an AI just played.
        last_seat = _last_played_seat(hand)
        ctx["last_played_seat"] = last_seat
        ctx["ai_just_played"] = (
            hand.phase == "trick_play"
            and hand.paused_after_play
            and last_seat is not None
            and last_seat != HUMAN_SEAT
        )

        # Auto-advance — JS auto-triggers Next after AI card animations
        # so the player doesn't click for every AI card (#2442, #2386).
        # Suppressed during auction reveal/settle and moon-exchange so the
        # JS doesn't cascade through hidden bid reveals (#2503).
        if (
            hand.phase == "trick_play"
            and hand.paused_after_play
            and not _auction_reveal_active(hand)
            and not _has_pending_exchange(hand)
        ):
            is_ai = last_seat is not None and last_seat != HUMAN_SEAT
            # AI cards: match the CSS animation duration (750ms) + buffer.
            # Human card: brief pause to see own card on the table.
            ctx["auto_advance"] = True
            ctx["auto_advance_delay_ms"] = 850 if is_ai else 500
        else:
            ctx["auto_advance"] = False
            ctx["auto_advance_delay_ms"] = 0

        ctx["winning_bid"] = None if _has_hidden_auction(hand) else hand.winning_bid
        ctx["bidder_seat"] = None if _has_hidden_auction(hand) else hand.bidder_seat
        ctx["current_high_bid"] = (
            0 if _has_hidden_auction(hand) else hand.current_high_bid
        )
        ctx["auction_settled"] = hand.auction_settled
        ctx["points_team0"] = hand.points_team0
        ctx["points_team1"] = hand.points_team1
        ctx["action_rail"] = _build_action_rail(state)
        ctx["seat_bids"] = _build_seat_bids(visible.get("auction", []))
        ctx["show_bid_panel"] = (
            phase == "auction"
            and hand.phase == "auction"
            and hand.current_seat == HUMAN_SEAT
            and not show_next
        )

        # Legal plays for the hand partial
        if (
            phase == "trick_play"
            and hand.phase == "trick_play"
            and hand.current_seat == HUMAN_SEAT
            and not show_next
        ):
            ctx["legal_plays"] = engine.get_legal_plays(state)
        else:
            ctx["legal_plays"] = None

        # Currently winning seat in the active trick (for highlight).
        trick = hand.current_trick if hand.current_trick is not None else None
        if (
            trick is not None
            and len(trick.plays) >= 1
            and hand.contract_type is not None
        ):
            ctx["trick_winning_seat"] = trick_winner(
                trick.plays, hand.contract_type, hand.trump
            )
        else:
            ctx["trick_winning_seat"] = None

        # Moon exchange selection context
        if phase == "moon_exchange_select":
            mooner_seat = hand.bidder_seat
            ctx["is_mooner"] = HUMAN_SEAT == mooner_seat
            ctx["exchange_prompt"] = (
                "Choose 2 cards to give to your partner"
                if HUMAN_SEAT == mooner_seat
                else "Choose 2 cards to give to the mooner"
            )

        # AI hand card counts (face-down display).
        # During hidden-auction reveal the engine may have auto-advanced
        # into trick play (reducing AI hand sizes), but the user hasn't
        # seen the auction result yet — show pre-play counts.
        if _has_hidden_auction(hand):
            ctx["opp_left_count"] = 10
            ctx["partner_count"] = 10
            ctx["opp_right_count"] = 10
        else:
            ctx["opp_left_count"] = len(hand.hands[1]) if len(hand.hands) > 1 else 0
            ctx["partner_count"] = len(hand.hands[2]) if len(hand.hands) > 2 else 0
            ctx["opp_right_count"] = len(hand.hands[3]) if len(hand.hands) > 3 else 0
    else:
        ctx["winning_bid"] = None
        ctx["bidder_seat"] = None
        ctx["current_high_bid"] = 0
        ctx["points_team0"] = 0
        ctx["points_team1"] = 0
        ctx["legal_plays"] = None
        ctx["trick_winning_seat"] = None
        ctx["opp_left_count"] = 0
        ctx["partner_count"] = 0
        ctx["opp_right_count"] = 0
        ctx["action_rail"] = []
        ctx["seat_bids"] = {}
        ctx["show_next"] = False
        ctx["next_reason"] = None
        ctx["show_bid_panel"] = False
        ctx["last_played_seat"] = None
        ctx["ai_just_played"] = False
        ctx["auto_advance"] = False
        ctx["auto_advance_delay_ms"] = 0

    return ctx


def _render_game_board(
    request: Request,
    engine: MatchEngine,
    state,
    link_uuid: str,
    *,
    error_message: str | None = None,
    force_match_result: bool = False,
) -> str:
    """Render the game board composite partial as an HTML string.

    Returns the inner HTML for the ``#game-board`` div — used by HTMX
    partial POST responses.

    Parameters
    ----------
    error_message:
        Optional transient error string displayed as an inline alert
        above the board (e.g. "Illegal bid").  Cleared on the next
        normal render.
    force_match_result:
        When *True*, skip the hand-result interstitial and render the
        match-result screen directly.  Used by the ``/next-hand`` handler
        after the player has already seen the final hand result (#2239).
    """
    templates = _get_templates(request)
    ctx = _build_game_context(
        engine, state, link_uuid, force_match_result=force_match_result
    )
    ctx["request"] = request
    if error_message is not None:
        ctx["board_error"] = error_message
    return templates.get_template("partials/game_board.html").render(ctx)


def _handle_corrupted_match(
    request: Request,
    session,
    match_row: Match,
    link_uuid: str,
) -> HTMLResponse:
    """Mark a match with corrupted state as abandoned and redirect.

    Used by POST handlers when ``_deserialize_state`` fails.  Mirrors the
    GET handler pattern (mark abandoned → show model selection) but returns
    an ``HX-Redirect`` header so HTMX performs a full page navigation back
    to ``/play/{link_uuid}``, which will render the model-select screen.

    See :issue:`2218`.
    """
    match_row.status = "abandoned"
    match_row.completed_at = datetime.now(timezone.utc)
    session.commit()
    redirect_url = f"/play/{link_uuid}"
    return HTMLResponse(
        content="",
        status_code=200,
        headers={"HX-Redirect": redirect_url},
    )


# ---------------------------------------------------------------------------
# Health / Readiness
# ---------------------------------------------------------------------------


@router.get("/health")
async def health(request: Request):
    """Liveness probe with operational metrics.

    Always returns 200 OK.  Includes ``active_matches``,
    ``total_players``, ``db_size_bytes`` (SQLite only, -1 otherwise),
    and ``uptime_seconds`` for operational observability.
    """
    info: dict[str, Any] = {"status": "ok"}

    try:
        session = _get_session(request)
        try:
            info["active_matches"] = (
                session.query(Match).filter_by(status="active").count()
            )
            info["total_players"] = session.query(Player).count()

            # DB file size — only meaningful for SQLite file-based databases
            db_url = str(request.app.state.engine.url)
            if db_url.startswith("sqlite:///") and ":memory:" not in db_url:
                import os

                db_path = db_url.replace("sqlite:///", "")
                try:
                    info["db_size_bytes"] = os.path.getsize(db_path)
                except OSError:
                    info["db_size_bytes"] = -1
            else:
                info["db_size_bytes"] = -1
        finally:
            session.close()
    except Exception:
        info["active_matches"] = -1
        info["total_players"] = -1
        info["db_size_bytes"] = -1

    # Uptime
    started_at = getattr(request.app.state, "started_at", None)
    if started_at is not None:
        delta = datetime.now(timezone.utc) - started_at
        info["uptime_seconds"] = int(delta.total_seconds())
    else:
        info["uptime_seconds"] = -1

    return JSONResponse(info)


@router.get("/ready")
async def ready(request: Request):
    """Readiness probe — checks DB read and write capability.

    Returns 200 if the database supports both reads and writes, 503 otherwise.
    """
    try:
        session = _get_session(request)
        try:
            # Read check
            session.execute(text("SELECT 1"))
            # Write check — session-scoped temp table, cleaned up on close
            session.execute(
                text("CREATE TEMPORARY TABLE IF NOT EXISTS _ready_check (v INTEGER)")
            )
            session.execute(text("INSERT INTO _ready_check (v) VALUES (1)"))
            session.execute(text("DELETE FROM _ready_check"))
        finally:
            session.close()
    except Exception:
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return JSONResponse({"status": "ready"})


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    """Landing page — invite code form or reconnect prompt.

    When the player has a session cookie with an active match, renders a
    reconnect partial so they can resume without re-entering their invite
    code.  Falls through to the standard invite code form otherwise.
    """
    templates = _get_templates(request)
    link_uuid = get_player_link_from_cookie(request)
    if link_uuid is not None:
        session = _get_session(request)
        try:
            match_info = lookup_active_match(session, link_uuid)
            if match_info is not None:
                return templates.TemplateResponse(
                    "landing.html",
                    {
                        "request": request,
                        "reconnect": match_info,
                    },
                )
        finally:
            session.close()
    return templates.TemplateResponse("landing.html", {"request": request})


@router.post("/enter-code")
async def enter_code(
    request: Request,
    code: str = Form(...),
):
    """Validate an invite code and redirect to the game.

    If the code is valid and unused, creates a new Player and binds the
    code.  If the code was already redeemed, returns the existing player's
    link.  Invalid or revoked codes show an error on the landing page.

    HTMX-aware: when the request comes from HTMX, returns an HX-Redirect
    header so the client performs a full navigation to the game page.
    """
    templates = _get_templates(request)
    session = _get_session(request)
    try:
        normalized = code.strip().upper()
        invite = session.query(InviteCode).filter_by(code=normalized).first()

        # --- Reject invalid / revoked codes ---
        if invite is None:
            ctx = {"request": request, "error": "Invalid invite code."}
            return HTMLResponse(
                templates.get_template("partials/invite_code_form.html").render(ctx),
                status_code=200,
            )

        if invite.status == "revoked":
            ctx = {
                "request": request,
                "error": "This invite code has been revoked.",
            }
            return HTMLResponse(
                templates.get_template("partials/invite_code_form.html").render(ctx),
                status_code=200,
            )

        # --- Already redeemed — return existing player link ---
        if invite.status == "redeemed" and invite.player_id is not None:
            player = session.query(Player).get(invite.player_id)
            if player is not None:
                redirect_url = f"/play/{player.link_uuid}"
                # HTMX-aware redirect
                if request.headers.get("HX-Request"):
                    resp = HTMLResponse(
                        "",
                        headers={"HX-Redirect": redirect_url},
                    )
                    set_player_cookie(resp, player.link_uuid)
                    return resp
                resp = RedirectResponse(url=redirect_url, status_code=302)
                set_player_cookie(resp, player.link_uuid)
                return resp

        # --- Active code — create player and redeem ---
        link_uuid = str(uuid.uuid4())
        player = Player(link_uuid=link_uuid)
        session.add(player)
        session.flush()

        invite.status = "redeemed"
        invite.player_id = player.id
        invite.redeemed_at = datetime.now(timezone.utc)
        session.commit()

        redirect_url = f"/play/{link_uuid}"
        # HTMX-aware redirect
        if request.headers.get("HX-Request"):
            resp = HTMLResponse(
                "",
                headers={"HX-Redirect": redirect_url},
            )
            set_player_cookie(resp, link_uuid)
            return resp
        resp = RedirectResponse(url=redirect_url, status_code=302)
        set_player_cookie(resp, link_uuid)
        return resp
    finally:
        session.close()


@router.post("/new")
async def create_game(request: Request):
    """Create a new game link and redirect to the play page.

    Legacy route — kept for backwards compatibility.  New pilot access
    goes through ``/enter-code``.
    """
    session = _get_session(request)
    try:
        link_uuid = str(uuid.uuid4())
        player = Player(link_uuid=link_uuid)
        session.add(player)
        session.commit()
        resp = RedirectResponse(url=f"/play/{link_uuid}", status_code=302)
        set_player_cookie(resp, link_uuid)
        return resp
    finally:
        session.close()


@router.get("/play/{link_uuid}", response_class=HTMLResponse)
async def game_page(request: Request, link_uuid: str):
    """Game page — shows nickname prompt or game board."""
    templates = _get_templates(request)
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Game not found")

        # Backfill the reconnect cookie so returning visitors see the
        # reconnect prompt on the landing page even if they arrived here
        # via a direct link or bookmark (not the invite-code flow).
        # Only set the cookie when no existing cookie is present — avoid
        # clobbering a different player's session if someone follows a
        # shared /play/ link.  (Fixes #2069)
        existing_cookie = get_player_link_from_cookie(request)
        should_set_cookie = existing_cookie is None or existing_cookie == link_uuid

        def _with_cookie(resp: HTMLResponse) -> HTMLResponse:
            if should_set_cookie:
                set_player_cookie(resp, link_uuid)
            return resp

        is_htmx_tab = bool(request.headers.get("HX-Request"))

        def _render_game(ctx: dict) -> HTMLResponse:
            """Render game page — partial for HTMX tab switch, full otherwise."""
            if is_htmx_tab:
                return HTMLResponse(
                    templates.get_template("partials/game_content.html").render(ctx)
                )
            return templates.TemplateResponse("game.html", ctx)

        # No nickname yet — show nickname prompt
        if not player.nickname:
            return _with_cookie(
                _render_game(
                    {
                        "request": request,
                        "phase": "nickname",
                        "link_uuid": link_uuid,
                        "current_page": "game",
                    },
                )
            )

        # Onboarding not yet complete — show welcome letter
        if not player.onboarding_complete:
            return _with_cookie(
                _render_game(
                    {
                        "request": request,
                        "phase": "onboarding_welcome",
                        "link_uuid": link_uuid,
                        "nickname": player.nickname,
                        "current_page": "game",
                    },
                )
            )

        # Find the most recently created non-abandoned match — active or
        # complete.  Previous logic preferred active matches first, which
        # returned a stale active match from an earlier session instead of
        # the just-completed match the player was looking at (#2467).
        # This now matches the ``next_hand`` POST handler pattern (#2446).
        # Abandoned matches are excluded — they would render a stale board
        # whose POST handlers reject non-active state with 404.  (#2056, #2410)
        match_row = (
            session.query(Match)
            .filter_by(player_id=player.id)
            .filter(Match.status.in_(["active", "complete"]))
            .order_by(Match.created_at.desc())
            .first()
        )

        if match_row is None:
            # No usable match — show model selection
            ai_manager = _get_ai_manager(request)
            models = ai_manager.list_available()
            return _with_cookie(
                _render_game(
                    {
                        "request": request,
                        "phase": "model_select",
                        "link_uuid": link_uuid,
                        "current_page": "game",
                        "nickname": player.nickname,
                        "models": models,
                        "default_model_id": ai_manager.default_model_id,
                    },
                )
            )

        # Active or completed match — restore current state
        ai_manager = _get_ai_manager(request)
        engine = _build_engine(ai_manager, match_row.ai_model)
        try:
            state = _deserialize_state(engine, match_row.match_state_json)
        except Exception:
            logger.warning(
                "Failed to deserialize match %s — marking abandoned",
                match_row.match_uuid,
                exc_info=True,
            )
            # Mark the corrupt match as abandoned and show model selection
            match_row.status = "abandoned"
            match_row.completed_at = datetime.now(timezone.utc)
            session.commit()
            models = ai_manager.list_available()
            return _with_cookie(
                _render_game(
                    {
                        "request": request,
                        "phase": "model_select",
                        "link_uuid": link_uuid,
                        "nickname": player.nickname,
                        "models": models,
                        "default_model_id": ai_manager.default_model_id,
                    },
                )
            )
        ctx = _build_game_context(engine, state, link_uuid)
        ctx["request"] = request
        ctx["nickname"] = player.nickname
        return _with_cookie(_render_game(ctx))
    finally:
        session.close()


@router.post("/play/{link_uuid}/nickname", response_class=HTMLResponse)
async def set_nickname(
    request: Request,
    link_uuid: str,
    nickname: str = Form(...),
):
    """Set the player's nickname."""
    templates = _get_templates(request)
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Game not found")

        player.nickname = nickname
        session.commit()

        # New player → show onboarding welcome letter
        if not player.onboarding_complete:
            return HTMLResponse(
                templates.get_template("partials/onboarding_welcome.html").render(
                    {
                        "request": request,
                        "link_uuid": link_uuid,
                        "nickname": nickname,
                    }
                )
            )

        # Returning player (onboarding already complete) → model selection
        ai_manager = _get_ai_manager(request)
        models = ai_manager.list_available()
        return HTMLResponse(
            templates.get_template("partials/model_select.html").render(
                {
                    "request": request,
                    "link_uuid": link_uuid,
                    "nickname": nickname,
                    "models": models,
                    "default_model_id": ai_manager.default_model_id,
                }
            )
        )
    finally:
        session.close()


# Onboarding flow step layout:
#   step 0 = welcome letter (already shown on page load)
#   step 1 = dedication page
#   steps 2..4 = guide walkthrough (3 steps)
# After step 4 → model selection.
_ONBOARDING_DEDICATION_STEP = 1
_ONBOARDING_GUIDE_FIRST_STEP = 2
_ONBOARDING_GUIDE_STEPS = 3  # number of guide walkthrough steps
_ONBOARDING_LAST_STEP = _ONBOARDING_GUIDE_FIRST_STEP + _ONBOARDING_GUIDE_STEPS - 1


@router.post("/play/{link_uuid}/onboarding/next", response_class=HTMLResponse)
async def onboarding_next(
    request: Request,
    link_uuid: str,
    step: int = Form(0),
):
    """Advance through onboarding steps.

    Step 0 = welcome letter (already shown) → returns dedication page.
    Step 1 = dedication page → returns guide step 1.
    Steps 2..4 = guide walkthrough pages.
    After the last guide step, marks onboarding complete and returns model
    selection.
    """
    templates = _get_templates(request)
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Game not found")

        next_step = step + 1

        # Past the last guide step → complete onboarding
        if next_step > _ONBOARDING_LAST_STEP:
            player.onboarding_complete = 1
            session.commit()
            ai_manager = _get_ai_manager(request)
            models = ai_manager.list_available()
            return HTMLResponse(
                templates.get_template("partials/model_select.html").render(
                    {
                        "request": request,
                        "link_uuid": link_uuid,
                        "nickname": player.nickname,
                        "models": models,
                        "default_model_id": ai_manager.default_model_id,
                    }
                )
            )

        # Dedication page
        if next_step == _ONBOARDING_DEDICATION_STEP:
            return HTMLResponse(
                templates.get_template("partials/onboarding_dedication.html").render(
                    {
                        "request": request,
                        "link_uuid": link_uuid,
                    }
                )
            )

        # Show the next guide step
        guide_step = next_step - _ONBOARDING_GUIDE_FIRST_STEP + 1
        return HTMLResponse(
            templates.get_template("partials/onboarding_guide.html").render(
                {
                    "request": request,
                    "link_uuid": link_uuid,
                    "nickname": player.nickname,
                    "step": guide_step,
                    "total_steps": _ONBOARDING_GUIDE_STEPS,
                    "onboarding_step": next_step,
                }
            )
        )
    finally:
        session.close()


@router.post("/play/{link_uuid}/onboarding/skip", response_class=HTMLResponse)
async def onboarding_skip(
    request: Request,
    link_uuid: str,
):
    """Skip remaining onboarding and go directly to model selection."""
    templates = _get_templates(request)
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Game not found")

        player.onboarding_complete = 1
        session.commit()

        ai_manager = _get_ai_manager(request)
        models = ai_manager.list_available()
        return HTMLResponse(
            templates.get_template("partials/model_select.html").render(
                {
                    "request": request,
                    "link_uuid": link_uuid,
                    "nickname": player.nickname,
                    "models": models,
                    "default_model_id": ai_manager.default_model_id,
                }
            )
        )
    finally:
        session.close()


@router.post("/play/{link_uuid}/select-ai", response_class=HTMLResponse)
async def select_ai(
    request: Request,
    link_uuid: str,
    model_id: str = Form(...),
):
    """Select AI model, create match, deal first hand."""
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Game not found")

        # Abandon all active matches for this player before creating the
        # new one.  This prevents stale active matches from shadowing the
        # new match on page refresh (#2467).  It also subsumes the previous
        # expire_player_stale_matches() call (#2211) — we no longer need an
        # age threshold because starting a new match is an explicit signal
        # that the player is done with prior matches.
        abandon_player_active_matches(session, player.id)

        ai_manager = _get_ai_manager(request)
        try:
            ai_manager.get_model_info(model_id)
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Unknown model: {model_id}")

        engine = _build_engine(ai_manager, model_id)
        config = _get_config(request)
        if config.test_seed is not None:
            seed = config.test_seed
        else:
            seed = random.Random().randint(0, 2**31 - 1)

        t_engine = time.monotonic()
        state = engine.start_match(seed=seed, ai_model=model_id)
        engine_ms = round((time.monotonic() - t_engine) * 1000, 1)

        match_uuid = str(uuid.uuid4())
        # Stamp the play strategy's version onto the match row for cohort
        # tracking.  Read polymorphically via ``type(...).VERSION`` so any
        # future Glutton subclass — or an entirely different strategy —
        # contributes its own version without extra wiring.  Raises
        # AttributeError if the strategy forgot to declare VERSION, which
        # is the correct fail-loud behavior (see
        # docs/02_agent/STRATEGY_VERSIONING.md).  The attribute is not on
        # the Strategy base class today, so the static type:ignore is
        # required until every strategy declares one.
        play_strategy_version = type(engine.play_strategy).VERSION  # type: ignore[attr-defined]
        match_row = Match(
            match_uuid=match_uuid,
            player_id=player.id,
            ai_model=model_id,
            play_strategy_version=play_strategy_version,
            status="active",
            seed=seed,
            match_state_json=_serialize_state(engine, state),
        )
        session.add(match_row)
        session.flush()

        # Create the initial hand row (use deal_id as hand_number to stay
        # unique even when redeals occur before any hand completes)
        if state.current_hand is not None:
            _ensure_hand_row(
                session, match_row, state.current_hand, state.current_hand.deal_id
            )

        t_commit = time.monotonic()
        session.commit()
        commit_ms = round((time.monotonic() - t_commit) * 1000, 1)

        logger.info(
            "action=select_ai match=%s model=%s seed=%d result=ok engine_ms=%.1f commit_ms=%.1f request_id=%s",
            match_uuid,
            model_id,
            seed,
            engine_ms,
            commit_ms,
            get_request_id(),
        )
        _check_slow_subphases(
            "select_ai", match_uuid, engine_ms=engine_ms, commit_ms=commit_ms
        )

        # Return game board (HTMX partial)
        return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
    finally:
        session.close()


@router.post("/play/{link_uuid}/bid", response_class=HTMLResponse)
async def submit_bid(
    request: Request,
    link_uuid: str,
    turn_number: int = Form(...),
    bid_n: int = Form(...),
    bid_contract: str = Form(None),
    bid_type: str = Form("regular"),
):
    """Submit a bid action."""
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Game not found")

        match_row = (
            session.query(Match)
            .filter_by(player_id=player.id, status="active")
            .order_by(Match.created_at.desc())
            .first()
        )
        if match_row is None:
            raise HTTPException(status_code=404, detail="No active match")

        ai_manager = _get_ai_manager(request)
        engine = _build_engine(ai_manager, match_row.ai_model)
        t_deser = time.monotonic()
        try:
            state = _deserialize_state(engine, match_row.match_state_json)
        except Exception:
            logger.warning(
                "action=bid match=%s result=error reason=deserialize_failed request_id=%s",
                match_row.match_uuid,
                get_request_id(),
                exc_info=True,
            )
            return _handle_corrupted_match(request, session, match_row, link_uuid)
        deser_ms = round((time.monotonic() - t_deser) * 1000, 1)

        # Turn-number conflict — return the authoritative board at 409 so
        # HTMX can re-sync the DOM without re-submitting the stale action.
        hand = state.current_hand
        if hand is None:
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
        if turn_number != hand.turn_number:
            logger.info(
                "action=bid match=%s turn=%d expected_turn=%d result=conflict request_id=%s",
                match_row.match_uuid,
                turn_number,
                hand.turn_number,
                get_request_id(),
            )
            return HTMLResponse(
                _render_game_board(request, engine, state, link_uuid),
                status_code=409,
            )

        # State-desync recovery — return the authoritative board for stale
        # requests instead of 400 so HTMX can re-sync the DOM.
        if hand.phase != "auction":
            logger.info(
                "action=bid match=%s turn=%d result=desync expected_phase=auction actual_phase=%s request_id=%s",
                match_row.match_uuid,
                turn_number,
                hand.phase,
                get_request_id(),
            )
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
        if hand.current_seat != HUMAN_SEAT:
            logger.info(
                "action=bid match=%s turn=%d result=desync reason=not_human_turn current_seat=%d request_id=%s",
                match_row.match_uuid,
                turn_number,
                hand.current_seat,
                get_request_id(),
            )
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
        if _awaiting_next(hand):
            logger.info(
                "action=bid match=%s turn=%d result=desync reason=awaiting_next request_id=%s",
                match_row.match_uuid,
                turn_number,
                get_request_id(),
            )
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))

        # Build bid action
        if bid_n == 0:
            bid = BidAction.pass_bid()
        else:
            # Treat both None and empty string as "no contract selected" —
            # the bid form now defaults the contract dropdown to an empty
            # placeholder option (#2521 item 4), so the submitted form may
            # include bid_contract="" if the client bypasses the disabled
            # Submit Bid button.
            if not bid_contract:
                return HTMLResponse(
                    _render_game_board(
                        request,
                        engine,
                        state,
                        link_uuid,
                        error_message="Please select a contract type for your bid.",
                    )
                )
            if bid_type == "moon":
                bid = BidAction.moon(bid_contract)
            elif bid_type == "loner":
                bid = BidAction.loner(bid_contract)
            else:
                bid = BidAction.bid(bid_n, bid_contract)

        # Validate legality using overcall-aware comparison
        legal_bids = engine.get_legal_bids(state)
        if not any(
            b.n == bid.n and b.contract == bid.contract and b.bid_type == bid.bid_type
            for b in legal_bids
        ):
            logger.info(
                "action=bid match=%s turn=%d result=illegal bid_n=%d bid_contract=%s bid_type=%s request_id=%s",
                match_row.match_uuid,
                turn_number,
                bid_n,
                bid_contract,
                bid_type,
                get_request_id(),
            )
            return HTMLResponse(
                _render_game_board(
                    request,
                    engine,
                    state,
                    link_uuid,
                    error_message="Illegal bid — please choose a valid bid.",
                )
            )

        # Record pre-action state for decision logging
        pre_turn = hand.turn_number

        # Ensure hand row exists (keyed by deal_id for redeal-safe uniqueness)
        hand_row = _ensure_hand_row(session, match_row, hand, hand.deal_id)

        # Log human decision
        _log_decision(
            session,
            match_row,
            hand_row,
            turn_number=pre_turn,
            seat=HUMAN_SEAT,
            phase="bid",
            actor_type="human",
            decision_source="human",
            legal_actions=[
                {"n": b.n, "contract": b.contract, "bid_type": b.bid_type}
                for b in legal_bids
            ],
            chosen_action={
                "n": bid.n,
                "contract": bid.contract,
                "bid_type": bid.bid_type,
            },
            game_state=engine.get_visible_state(state),
        )

        pre_auction_count = len(hand.auction)

        # Apply action — engine auto-advances AI
        t_engine = time.monotonic()
        state = engine.submit_human_bid(state, bid)
        engine_ms = round((time.monotonic() - t_engine) * 1000, 1)
        current_hand = state.current_hand
        if current_hand is not None:
            current_hand.revealed_auction_count = min(
                len(current_hand.auction),
                pre_auction_count + 1,
            )
            # Activate settle pause so the user can review the auction
            # result before play begins.  Two cases:
            # 1. Hidden bids remain (AI bid after the human) — reveal one
            #    at a time, then show the settle interstitial.
            # 2. No hidden bids but auction just completed (human bid last)
            #    — still pause so the user sees who won and what was bid
            #    before trick play starts (#2438).
            # Redeals (all passed) skip the settle pause because the redeal
            # interstitial already communicates the outcome.
            if _has_hidden_auction(current_hand):
                current_hand.auction_settled = False
            elif current_hand.phase != "auction" and current_hand.phase != "redeal":
                current_hand.auction_settled = False

        # Log AI decisions captured during auto-advance
        _log_ai_decisions_after_advance(
            session,
            match_row,
            hand_row,
            engine,
            state,
        )

        # Update hand row based on resulting phase.
        # Redeals are NOT auto-advanced here — the user sees a "redeal"
        # interstitial and clicks Next to deal the new hand (handled
        # by the /next endpoint).
        if current_hand is not None and current_hand.phase == "redeal":
            _update_hand_row(hand_row, current_hand)
        elif current_hand is not None and current_hand.phase == "complete":
            _update_hand_row(hand_row, current_hand)
        elif current_hand is not None:
            hand_row.hand_state_json = json.dumps(current_hand.to_dict())

        _update_match_row(match_row, state)
        t_commit = time.monotonic()
        session.commit()
        commit_ms = round((time.monotonic() - t_commit) * 1000, 1)

        logger.info(
            "action=bid match=%s turn=%d result=ok deser_ms=%.1f engine_ms=%.1f commit_ms=%.1f request_id=%s",
            match_row.match_uuid,
            turn_number,
            deser_ms,
            engine_ms,
            commit_ms,
            get_request_id(),
        )
        _check_slow_subphases(
            "bid",
            match_row.match_uuid,
            deser_ms=deser_ms,
            engine_ms=engine_ms,
            commit_ms=commit_ms,
        )

        return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
    finally:
        session.close()


@router.post("/play/{link_uuid}/play-card", response_class=HTMLResponse)
async def submit_card(
    request: Request,
    link_uuid: str,
    turn_number: int = Form(...),
    card_index: int = Form(...),
):
    """Submit a card play action."""
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Game not found")

        match_row = (
            session.query(Match)
            .filter_by(player_id=player.id, status="active")
            .order_by(Match.created_at.desc())
            .first()
        )
        if match_row is None:
            raise HTTPException(status_code=404, detail="No active match")

        ai_manager = _get_ai_manager(request)
        engine = _build_engine(ai_manager, match_row.ai_model)
        t_deser = time.monotonic()
        try:
            state = _deserialize_state(engine, match_row.match_state_json)
        except Exception:
            logger.warning(
                "action=play_card match=%s result=error reason=deserialize_failed request_id=%s",
                match_row.match_uuid,
                get_request_id(),
                exc_info=True,
            )
            return _handle_corrupted_match(request, session, match_row, link_uuid)
        deser_ms = round((time.monotonic() - t_deser) * 1000, 1)

        # Turn-number conflict — return the authoritative board at 409 so
        # HTMX can re-sync the DOM without re-submitting the stale action.
        # Prevents race conditions from fast-clickers (#2223).
        hand = state.current_hand
        if hand is None:
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
        if turn_number != hand.turn_number:
            logger.info(
                "action=play_card match=%s turn=%d expected_turn=%d result=conflict request_id=%s",
                match_row.match_uuid,
                turn_number,
                hand.turn_number,
                get_request_id(),
            )
            return HTMLResponse(
                _render_game_board(request, engine, state, link_uuid),
                status_code=409,
            )

        # State-desync recovery — if HTMX morph left stale card buttons in
        # the DOM the player may click a card while the server is in a
        # different phase or waiting for a reveal advance.  Rather than
        # returning a 400 (which requires a full page reload to recover),
        # re-render the authoritative board so HTMX can swap in the correct
        # state.  True validation errors (illegal card) still return 400.
        if hand.phase != "trick_play":
            logger.info(
                "action=play_card match=%s turn=%d result=desync expected_phase=trick_play actual_phase=%s request_id=%s",
                match_row.match_uuid,
                turn_number,
                hand.phase,
                get_request_id(),
            )
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
        if hand.current_seat != HUMAN_SEAT:
            logger.info(
                "action=play_card match=%s turn=%d result=desync reason=not_human_turn current_seat=%d request_id=%s",
                match_row.match_uuid,
                turn_number,
                hand.current_seat,
                get_request_id(),
            )
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
        if _awaiting_next(hand):
            logger.info(
                "action=play_card match=%s turn=%d result=desync reason=awaiting_next request_id=%s",
                match_row.match_uuid,
                turn_number,
                get_request_id(),
            )
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))

        # Validate legality
        legal_plays = engine.get_legal_plays(state)
        if card_index not in legal_plays:
            logger.info(
                "action=play_card match=%s turn=%d result=illegal card_index=%d request_id=%s",
                match_row.match_uuid,
                turn_number,
                card_index,
                get_request_id(),
            )
            return HTMLResponse(
                _render_game_board(
                    request,
                    engine,
                    state,
                    link_uuid,
                    error_message="Illegal card play — please choose a valid card.",
                )
            )

        # Record pre-action state for decision logging
        pre_turn = hand.turn_number

        # Ensure hand row exists (keyed by deal_id for redeal-safe uniqueness)
        hand_row = _ensure_hand_row(session, match_row, hand, hand.deal_id)

        # Log human decision
        _log_decision(
            session,
            match_row,
            hand_row,
            turn_number=pre_turn,
            seat=HUMAN_SEAT,
            phase="play",
            actor_type="human",
            decision_source="human",
            legal_actions=legal_plays,
            chosen_action=card_index,
            game_state=engine.get_visible_state(state),
        )

        # Apply action — engine auto-advances AI and sets
        # paused_after_trick when a trick completes.
        t_engine = time.monotonic()
        state = engine.submit_human_card(state, card_index)
        engine_ms = round((time.monotonic() - t_engine) * 1000, 1)
        current_hand = state.current_hand

        # Log AI decisions captured during auto-advance
        _log_ai_decisions_after_advance(
            session,
            match_row,
            hand_row,
            engine,
            state,
        )

        # Update hand row if hand completed (redeals cannot occur during
        # card play, but keep the check consistent)
        if current_hand is not None and current_hand.phase == "complete":
            _update_hand_row(hand_row, current_hand)
        elif current_hand is not None:
            hand_row.hand_state_json = json.dumps(current_hand.to_dict())

        _update_match_row(match_row, state)
        t_commit = time.monotonic()
        session.commit()
        commit_ms = round((time.monotonic() - t_commit) * 1000, 1)

        logger.info(
            "action=play_card match=%s turn=%d result=ok deser_ms=%.1f engine_ms=%.1f commit_ms=%.1f request_id=%s",
            match_row.match_uuid,
            turn_number,
            deser_ms,
            engine_ms,
            commit_ms,
            get_request_id(),
        )
        _check_slow_subphases(
            "play_card",
            match_row.match_uuid,
            deser_ms=deser_ms,
            engine_ms=engine_ms,
            commit_ms=commit_ms,
        )
        # Log match completion when the game ends after this card play.
        if state.status == "complete":
            logger.info(
                "action=match_complete match=%s score_human=%d score_ai=%d hands_played=%d request_id=%s",
                match_row.match_uuid,
                state.score_human,
                state.score_ai,
                state.hands_played,
                get_request_id(),
            )

        return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
    finally:
        session.close()


@router.post("/play/{link_uuid}/next", response_class=HTMLResponse)
async def next_step(
    request: Request,
    link_uuid: str,
):
    """Advance one paused auction/trick reveal step."""
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Game not found")

        match_row = (
            session.query(Match)
            .filter_by(player_id=player.id, status="active")
            .order_by(Match.created_at.desc())
            .first()
        )
        # Fallback: when the final trick completed AND ended the match,
        # the match is already "complete" in the DB but paused_after_trick
        # still needs to be cleared for the trick-result interstitial (#2210).
        if match_row is None:
            match_row = (
                session.query(Match)
                .filter_by(player_id=player.id, status="complete")
                .order_by(Match.created_at.desc())
                .first()
            )
        if match_row is None:
            raise HTTPException(status_code=404, detail="No active match")

        ai_manager = _get_ai_manager(request)
        engine = _build_engine(ai_manager, match_row.ai_model)
        t_deser = time.monotonic()
        try:
            state = _deserialize_state(engine, match_row.match_state_json)
        except Exception:
            logger.warning(
                "action=next match=%s result=error reason=deserialize_failed request_id=%s",
                match_row.match_uuid,
                get_request_id(),
                exc_info=True,
            )
            return _handle_corrupted_match(request, session, match_row, link_uuid)
        deser_ms = round((time.monotonic() - t_deser) * 1000, 1)

        hand = state.current_hand
        if hand is None:
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))

        # Determine which next-step branch we take for logging.
        next_sub = "unknown"
        t_engine = time.monotonic()
        if _has_hidden_auction(hand):
            next_sub = "auction_reveal"
            hand.revealed_auction_count += 1
        elif not hand.auction_settled:
            next_sub = "auction_settle"
            # Settle pause dismissed — all bids were visible, user acknowledged.
            hand.auction_settled = True
        elif _has_pending_exchange(hand):
            next_sub = "exchange_reveal"
            hand.exchange_revealed = True
            # Moon: trigger deferred AI advancement.  When the human is
            # sitting out (partner of the mooner), submit_exchange_selection
            # deferred _advance_ai so the interstitial could display first.
            state = engine.advance_after_exchange_reveal(state)
        elif hand.phase == "trick_play" and hand.paused_after_play:
            next_sub = "resume_after_play"
            # Resume AI advancement after per-card reveal pause.
            # The engine will play one more AI card and pause again,
            # or return immediately if the next turn is the human's.
            state = engine.resume_after_play(state)
        elif hand.phase == "trick_play" and hand.paused_after_trick:
            next_sub = "resume_after_trick"
            # Resume AI advancement after trick-result interstitial.
            # The engine will play one AI card (with per-card pacing),
            # reach the human's turn, or hit hand/match end.
            state = engine.resume_ai(state)
        elif hand.phase == "complete" and hand.paused_after_trick:
            # Final trick (trick 10) result dismissed — clear the pause
            # flag so the game shows the hand-result screen (#2210).
            hand.paused_after_trick = False
        elif hand.phase == "redeal":
            next_sub = "redeal"
            # All players passed — persist the terminal redeal hand,
            # then deal the next hand and auto-advance AI bids.
            hand_row = _ensure_hand_row(session, match_row, hand, hand.deal_id)
            _update_hand_row(hand_row, hand)
            state = engine.deal_after_redeal(state)
            # Create a hand row for the newly dealt hand
            if state.current_hand is not None:
                _ensure_hand_row(
                    session,
                    match_row,
                    state.current_hand,
                    state.current_hand.deal_id,
                )
        else:
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
        engine_ms = round((time.monotonic() - t_engine) * 1000, 1)

        # Ensure hand row exists for the current hand (may have changed
        # after redeal or resume).
        current_hand = state.current_hand
        if current_hand is not None:
            hand_row = _ensure_hand_row(
                session, match_row, current_hand, current_hand.deal_id
            )
        else:
            hand_row = _ensure_hand_row(session, match_row, hand, hand.deal_id)

        # Log AI decisions captured during auto-advance
        _log_ai_decisions_after_advance(
            session,
            match_row,
            hand_row,
            engine,
            state,
        )

        # After exchange-reveal auto-advance (especially moon/loner where
        # human sits out), the hand may have completed and the match may
        # have ended.  Ensure hand row metadata is persisted (P2-005).
        if current_hand is not None and current_hand.phase == "complete":
            _update_hand_row(hand_row, current_hand)
        elif current_hand is not None:
            hand_row.hand_state_json = json.dumps(current_hand.to_dict())
        else:
            hand_row.hand_state_json = json.dumps(hand.to_dict())
        _update_match_row(match_row, state)
        t_commit = time.monotonic()
        session.commit()
        commit_ms = round((time.monotonic() - t_commit) * 1000, 1)

        logger.info(
            "action=next match=%s sub=%s result=ok deser_ms=%.1f engine_ms=%.1f commit_ms=%.1f request_id=%s",
            match_row.match_uuid,
            next_sub,
            deser_ms,
            engine_ms,
            commit_ms,
            get_request_id(),
        )
        _check_slow_subphases(
            "next",
            match_row.match_uuid,
            deser_ms=deser_ms,
            engine_ms=engine_ms,
            commit_ms=commit_ms,
        )
        # Log match completion when the game ends after a next-step advance
        # (e.g. moon/loner with human sitting out).
        if state.status == "complete":
            logger.info(
                "action=match_complete match=%s score_human=%d score_ai=%d hands_played=%d request_id=%s",
                match_row.match_uuid,
                state.score_human,
                state.score_ai,
                state.hands_played,
                get_request_id(),
            )

        return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
    finally:
        session.close()


@router.post("/play/{link_uuid}/skip", response_class=HTMLResponse)
async def skip_pacing(
    request: Request,
    link_uuid: str,
):
    """Skip per-card reveal pauses and advance to the next decision point.

    Clears paused_after_play flags and advances AI until the next trick
    completion (paused_after_trick), human turn, or hand/match end.
    """
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Game not found")

        match_row = (
            session.query(Match)
            .filter_by(player_id=player.id, status="active")
            .order_by(Match.created_at.desc())
            .first()
        )
        if match_row is None:
            raise HTTPException(status_code=404, detail="No active match")

        ai_manager = _get_ai_manager(request)
        engine = _build_engine(ai_manager, match_row.ai_model)
        t_deser = time.monotonic()
        try:
            state = _deserialize_state(engine, match_row.match_state_json)
        except Exception:
            logger.warning(
                "action=skip match=%s result=error reason=deserialize_failed request_id=%s",
                match_row.match_uuid,
                get_request_id(),
                exc_info=True,
            )
            return _handle_corrupted_match(request, session, match_row, link_uuid)
        deser_ms = round((time.monotonic() - t_deser) * 1000, 1)

        hand = state.current_hand
        if hand is None:
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))

        t_engine = time.monotonic()
        state = engine.skip_to_next_decision(state)
        engine_ms = round((time.monotonic() - t_engine) * 1000, 1)

        # Ensure hand row exists for the current hand
        current_hand = state.current_hand
        if current_hand is not None:
            hand_row = _ensure_hand_row(
                session, match_row, current_hand, current_hand.deal_id
            )
        else:
            hand_row = _ensure_hand_row(session, match_row, hand, hand.deal_id)

        # Log AI decisions captured during skip advance
        _log_ai_decisions_after_advance(
            session,
            match_row,
            hand_row,
            engine,
            state,
        )

        if current_hand is not None and current_hand.phase == "complete":
            _update_hand_row(hand_row, current_hand)
        elif current_hand is not None:
            hand_row.hand_state_json = json.dumps(current_hand.to_dict())
        else:
            hand_row.hand_state_json = json.dumps(hand.to_dict())
        _update_match_row(match_row, state)
        t_commit = time.monotonic()
        session.commit()
        commit_ms = round((time.monotonic() - t_commit) * 1000, 1)

        logger.info(
            "action=skip match=%s result=ok deser_ms=%.1f engine_ms=%.1f commit_ms=%.1f request_id=%s",
            match_row.match_uuid,
            deser_ms,
            engine_ms,
            commit_ms,
            get_request_id(),
        )
        _check_slow_subphases(
            "skip",
            match_row.match_uuid,
            deser_ms=deser_ms,
            engine_ms=engine_ms,
            commit_ms=commit_ms,
        )
        # Log match completion when the game ends after skipping pacing.
        if state.status == "complete":
            logger.info(
                "action=match_complete match=%s score_human=%d score_ai=%d hands_played=%d request_id=%s",
                match_row.match_uuid,
                state.score_human,
                state.score_ai,
                state.hands_played,
                get_request_id(),
            )

        return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
    finally:
        session.close()


@router.post("/play/{link_uuid}/exchange", response_class=HTMLResponse)
async def submit_exchange(
    request: Request,
    link_uuid: str,
    card_index_0: int = Form(...),
    card_index_1: int = Form(...),
):
    """Submit the human's 2-card selection for moon exchange."""
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Game not found")

        match_row = (
            session.query(Match)
            .filter_by(player_id=player.id, status="active")
            .order_by(Match.created_at.desc())
            .first()
        )
        if match_row is None:
            raise HTTPException(status_code=404, detail="No active match")

        ai_manager = _get_ai_manager(request)
        engine = _build_engine(ai_manager, match_row.ai_model)
        t_deser = time.monotonic()
        try:
            state = _deserialize_state(engine, match_row.match_state_json)
        except Exception:
            logger.warning(
                "action=exchange match=%s result=error reason=deserialize_failed request_id=%s",
                match_row.match_uuid,
                get_request_id(),
                exc_info=True,
            )
            return _handle_corrupted_match(request, session, match_row, link_uuid)
        deser_ms = round((time.monotonic() - t_deser) * 1000, 1)

        hand = state.current_hand
        if hand is None or hand.phase != "moon_exchange":
            logger.info(
                "action=exchange match=%s result=desync expected_phase=moon_exchange actual_phase=%s request_id=%s",
                match_row.match_uuid,
                hand.phase if hand is not None else "no_hand",
                get_request_id(),
            )
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))

        if hand.exchange_phase != "selecting":
            logger.info(
                "action=exchange match=%s result=desync reason=not_selecting exchange_phase=%s request_id=%s",
                match_row.match_uuid,
                hand.exchange_phase,
                get_request_id(),
            )
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))

        t_engine = time.monotonic()
        state = engine.submit_exchange_selection(state, [card_index_0, card_index_1])
        engine_ms = round((time.monotonic() - t_engine) * 1000, 1)

        hand_row = _ensure_hand_row(session, match_row, hand, hand.deal_id)

        # Log AI decisions captured during exchange auto-advance
        _log_ai_decisions_after_advance(
            session,
            match_row,
            hand_row,
            engine,
            state,
        )

        hand_row.hand_state_json = json.dumps(hand.to_dict())
        _update_match_row(match_row, state)
        t_commit = time.monotonic()
        session.commit()
        commit_ms = round((time.monotonic() - t_commit) * 1000, 1)

        logger.info(
            "action=exchange match=%s result=ok deser_ms=%.1f engine_ms=%.1f commit_ms=%.1f request_id=%s",
            match_row.match_uuid,
            deser_ms,
            engine_ms,
            commit_ms,
            get_request_id(),
        )
        _check_slow_subphases(
            "exchange",
            match_row.match_uuid,
            deser_ms=deser_ms,
            engine_ms=engine_ms,
            commit_ms=commit_ms,
        )

        return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
    finally:
        session.close()


@router.post("/play/{link_uuid}/next-hand", response_class=HTMLResponse)
async def next_hand(
    request: Request,
    link_uuid: str,
):
    """Advance from hand result to next hand.

    If the match is already complete (score reached ±52 on a previous
    hand), this renders the match-result screen instead of dealing a new
    hand.  This guards against the case where the hand-result template
    is shown but the match has already ended (P2-005 defensive fix).
    """
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Game not found")

        # Find the player's most recently created non-abandoned match.
        # Previous logic prioritized active matches, which returned stale
        # active matches from earlier sessions instead of the just-completed
        # match the player is actually advancing from (#2446).
        match_row = (
            session.query(Match)
            .filter_by(player_id=player.id)
            .filter(Match.status.in_(["active", "complete"]))
            .order_by(Match.created_at.desc())
            .first()
        )
        if match_row is None:
            raise HTTPException(status_code=404, detail="No active match")

        ai_manager = _get_ai_manager(request)
        engine = _build_engine(ai_manager, match_row.ai_model)
        t_deser = time.monotonic()
        try:
            state = _deserialize_state(engine, match_row.match_state_json)
        except Exception:
            logger.warning(
                "action=next_hand match=%s result=error reason=deserialize_failed request_id=%s",
                match_row.match_uuid,
                get_request_id(),
                exc_info=True,
            )
            return _handle_corrupted_match(request, session, match_row, link_uuid)
        deser_ms = round((time.monotonic() - t_deser) * 1000, 1)

        # If the match is already complete, show the match-result screen.
        # The player has already seen the final hand result (with the
        # "See Match Results" CTA) and is now advancing (#2239).
        if state.status == "complete":
            logger.info(
                "action=next_hand match=%s result=ok sub=match_already_complete request_id=%s",
                match_row.match_uuid,
                get_request_id(),
            )
            return HTMLResponse(
                _render_game_board(
                    request, engine, state, link_uuid, force_match_result=True
                )
            )

        hand = state.current_hand
        if hand is None:
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))

        # Persist current hand before any hand transition
        hand_row = _ensure_hand_row(session, match_row, hand, hand.deal_id)
        if hand.phase == "complete":
            _update_hand_row(hand_row, hand)

        # Only start a new hand when we are paused on a completed hand
        t_engine = time.monotonic()
        state = engine.advance_to_next_hand(state)
        engine_ms = round((time.monotonic() - t_engine) * 1000, 1)

        if state.current_hand is not None:
            next_hand_row = _ensure_hand_row(
                session,
                match_row,
                state.current_hand,
                state.current_hand.deal_id,
            )
            if state.current_hand.deal_id != hand.deal_id:
                _log_ai_decisions_after_advance(
                    session,
                    match_row,
                    next_hand_row,
                    engine,
                    state,
                )

        _update_match_row(match_row, state)
        t_commit = time.monotonic()
        session.commit()
        commit_ms = round((time.monotonic() - t_commit) * 1000, 1)

        logger.info(
            "action=next_hand match=%s result=ok deser_ms=%.1f engine_ms=%.1f commit_ms=%.1f request_id=%s",
            match_row.match_uuid,
            deser_ms,
            engine_ms,
            commit_ms,
            get_request_id(),
        )
        _check_slow_subphases(
            "next_hand",
            match_row.match_uuid,
            deser_ms=deser_ms,
            engine_ms=engine_ms,
            commit_ms=commit_ms,
        )

        return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
    finally:
        session.close()


@router.post("/play/{link_uuid}/new-match", response_class=HTMLResponse)
async def new_match(
    request: Request,
    link_uuid: str,
):
    """Start a new match (after a previous one completed)."""
    templates = _get_templates(request)
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Game not found")

        # Return model selection form (HTMX partial)
        ai_manager = _get_ai_manager(request)
        models = ai_manager.list_available()
        logger.info(
            "action=new_match result=ok request_id=%s",
            get_request_id(),
        )
        return HTMLResponse(
            templates.get_template("partials/model_select.html").render(
                {
                    "request": request,
                    "link_uuid": link_uuid,
                    "nickname": player.nickname or "Player",
                    "models": models,
                    "default_model_id": ai_manager.default_model_id,
                }
            )
        )
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------


@router.get("/leaderboard/{link_uuid}", response_class=HTMLResponse)
async def leaderboard(request: Request, link_uuid: str):
    """Leaderboard page — ranked table of player stats.

    Gated behind invite-code auth: the ``link_uuid`` must correspond to a
    valid player (created via invite code redemption).  Returns 404 for
    unknown UUIDs.
    """
    templates = _get_templates(request)
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Player not found")

        # Build AI display name mapping from the roster
        ai_manager = _get_ai_manager(request)
        ai_display_names = {
            model_id: info.name
            for model_id, info in ai_manager.available_models.items()
        }

        rankings = get_leaderboard(session, ai_display_names=ai_display_names)

        ctx = {
            "request": request,
            "link_uuid": link_uuid,
            "current_page": "leaderboard",
            "nickname": player.nickname,
            "current_player_id": player.id,
            "rankings": rankings,
            "metric_defs": METRIC_DEFINITIONS,
            "format_metric": format_metric,
        }

        if request.headers.get("HX-Request"):
            return HTMLResponse(
                templates.get_template("partials/leaderboard_content.html").render(ctx)
            )

        return templates.TemplateResponse("leaderboard.html", ctx)
    finally:
        session.close()


@router.get("/history/{link_uuid}", response_class=HTMLResponse)
async def match_history(request: Request, link_uuid: str):
    """Match history page — list of completed matches with scores.

    Shows all completed matches for the player identified by *link_uuid*,
    ordered most-recent first.  Displays opponent AI name, final score,
    win/loss result, date played, and number of hands.
    """
    templates = _get_templates(request)
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Player not found")

        matches = (
            session.query(Match)
            .filter_by(player_id=player.id, status="complete")
            .order_by(Match.completed_at.desc())
            .all()
        )

        ai_manager = _get_ai_manager(request)
        history_entries = []
        for m in matches:
            # Resolve AI display name from roster; fall back to raw model id
            try:
                ai_name = ai_manager.get_model_info(m.ai_model).name
            except KeyError:
                ai_name = m.ai_model

            # Use the authoritative winner from match state rather than
            # naive score comparison — tied scores (e.g. 55-55) are decided
            # by the declaring-team rule and the engine records the correct
            # winner in match_state_json.  Fall back to score comparison for
            # legacy rows missing the winner field or malformed JSON.
            try:
                match_data = (
                    json.loads(m.match_state_json) if m.match_state_json else {}
                )
            except (json.JSONDecodeError, TypeError):
                match_data = {}
            winner = match_data.get("winner") if isinstance(match_data, dict) else None
            if winner is not None:
                won = winner == "human"
            else:
                won = m.score_human > m.score_ai
            history_entries.append(
                {
                    "ai_name": ai_name,
                    "score_human": m.score_human,
                    "score_ai": m.score_ai,
                    "won": won,
                    "hands_played": m.hands_played,
                    "completed_at": m.completed_at,
                }
            )

        ctx = {
            "request": request,
            "link_uuid": link_uuid,
            "current_page": "history",
            "nickname": player.nickname,
            "matches": history_entries,
        }

        if request.headers.get("HX-Request"):
            return HTMLResponse(
                templates.get_template("partials/history_content.html").render(ctx)
            )

        return templates.TemplateResponse("history.html", ctx)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Comments board
# ---------------------------------------------------------------------------

# Maximum comment length (characters) and page size
_COMMENT_MAX_LENGTH = 500
_COMMENTS_PAGE_SIZE = 50


def _fetch_comments(session, *, limit: int = _COMMENTS_PAGE_SIZE) -> list[dict]:
    """Return recent comments with player nicknames, newest first."""
    rows = (
        session.query(Comment, Player.nickname)
        .join(Player, Comment.player_id == Player.id)
        .order_by(Comment.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "nickname": nickname,
            "content": comment.content,
            "created_at": comment.created_at,
        }
        for comment, nickname in rows
    ]


@router.get("/comments/{link_uuid}", response_class=HTMLResponse)
async def comments_page(request: Request, link_uuid: str):
    """Comments board page — community message board for all players.

    Lists recent comments newest-first with a form to post new ones.
    Gated behind invite-code auth: the ``link_uuid`` must correspond to
    a valid player.
    """
    templates = _get_templates(request)
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Player not found")

        comments = _fetch_comments(session)

        ctx = {
            "request": request,
            "link_uuid": link_uuid,
            "current_page": "comments",
            "nickname": player.nickname,
            "comments": comments,
            "error": None,
        }

        if request.headers.get("HX-Request"):
            return HTMLResponse(
                templates.get_template("partials/comments_content.html").render(ctx)
            )

        return templates.TemplateResponse("comments.html", ctx)
    finally:
        session.close()


@router.get("/comments/{link_uuid}/list", response_class=HTMLResponse)
async def comments_list(request: Request, link_uuid: str):
    """HTMX partial — return the comments list for polling refresh."""
    templates = _get_templates(request)
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Player not found")

        comments = _fetch_comments(session)

        return HTMLResponse(
            templates.get_template("partials/comments_list.html").render(
                {"comments": comments}
            )
        )
    finally:
        session.close()


@router.post("/play/{link_uuid}/comment", response_class=HTMLResponse)
async def post_comment(
    request: Request,
    link_uuid: str,
    content: str = Form(...),
):
    """Submit a new comment to the board.

    For HTMX requests, returns the updated comments list partial.
    For regular form submissions, redirects back to the comments page.
    """
    templates = _get_templates(request)
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Player not found")

        # Validate content
        content = content.strip()
        if not content:
            error = "Comment cannot be empty."
        elif len(content) > _COMMENT_MAX_LENGTH:
            error = f"Comment too long (max {_COMMENT_MAX_LENGTH} characters)."
        else:
            error = None

        if error is None:
            comment = Comment(
                player_id=player.id,
                content=content,
            )
            session.add(comment)
            session.commit()

        # HTMX request — return the updated list partial
        is_htmx = request.headers.get("HX-Request") == "true"

        comments = _fetch_comments(session)

        if is_htmx:
            ctx: dict = {"comments": comments}
            if error is not None:
                ctx["error"] = error
            return HTMLResponse(
                templates.get_template("partials/comments_list.html").render(ctx)
            )

        # Non-HTMX fallback — render full page with error (if any)
        if error is not None:
            return HTMLResponse(
                templates.get_template("comments.html").render(
                    {
                        "request": request,
                        "link_uuid": link_uuid,
                        "comments": comments,
                        "error": error,
                    }
                )
            )
        return RedirectResponse(
            url=f"/comments/{link_uuid}",
            status_code=303,
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Guide
# ---------------------------------------------------------------------------


@router.get("/guide/{link_uuid}", response_class=HTMLResponse)
async def guide(request: Request, link_uuid: str):
    """New player guide — rules walkthrough, tips, and strategies.

    Gated behind invite-code auth: the ``link_uuid`` must correspond to
    a valid player.  Returns 404 for unknown UUIDs.
    """
    templates = _get_templates(request)
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Player not found")

        ctx = {
            "request": request,
            "link_uuid": link_uuid,
            "current_page": "guide",
            "nickname": player.nickname,
        }

        if request.headers.get("HX-Request"):
            return HTMLResponse(
                templates.get_template("partials/guide_content.html").render(ctx)
            )

        return templates.TemplateResponse("guide.html", ctx)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# AI decision logging helper
# ---------------------------------------------------------------------------


def _log_ai_decisions_after_advance(
    session,
    match_row: Match,
    hand_row: Hand,
    engine: MatchEngine,
    state,
) -> None:
    """Log AI decisions captured during the engine's last auto-advance.

    Uses the exact per-turn action events emitted by ``MatchEngine._advance_ai``
    (via ``engine.last_ai_events``) so that every AI decision row has the actual
    seat, legal_actions, chosen_action, and game_state snapshot.
    """
    ai_model = state.ai_model

    for event in engine.last_ai_events:
        _log_decision(
            session,
            match_row,
            hand_row,
            turn_number=event.turn_number,
            seat=event.seat,
            phase=event.phase,
            actor_type="ai",
            decision_source=ai_model,
            legal_actions=event.legal_actions,
            chosen_action=event.chosen_action,
            game_state=event.game_state,
        )
