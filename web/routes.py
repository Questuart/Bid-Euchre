"""Route handlers for the Bid Euchre browser game.

All game-action POSTs include ``turn_number`` for idempotent submission.
If the submitted turn doesn't match the current expected turn the POST
returns the current visible state without modifying anything.

Delegates game logic to :class:`~bid_euchre.hosted_play.engine.MatchEngine`;
no rule/scoring logic lives here.
"""

from __future__ import annotations

import json
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import text
from starlette.templating import Jinja2Templates

logger = logging.getLogger(__name__)

from bid_euchre.core.rules import trick_winner
from bid_euchre.hosted_play.engine import HUMAN_SEAT, MatchEngine
from bid_euchre.strategy.bidding import BidAction

from .ai_manager import AIManager
from .db import Decision, Hand, InviteCode, Match, Player
from .leaderboard import METRIC_DEFINITIONS, format_metric, get_leaderboard
from .middleware import (
    check_match_limit,
    get_player_link_from_cookie,
    lookup_active_match,
    set_player_cookie,
)

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
    """Instantiate a MatchEngine for the given *model_id*."""
    info = ai_manager.get_model_info(model_id)
    return MatchEngine(
        bidding_policy=info.bidding_policy,
        play_strategy=info.play_strategy,
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
        _has_hidden_auction(hand)
        or _has_pending_exchange(hand)
        or (hand.phase == "trick_play" and hand.paused_after_trick)
        or hand.phase == "redeal"
    )


def _next_reason(hand) -> str | None:
    """Human-readable label for the current reveal pause."""
    if _has_hidden_auction(hand):
        return "Reveal the next auction action."
    if _has_pending_exchange(hand):
        return "Review the moon exchange."
    if hand.phase == "trick_play" and hand.paused_after_trick:
        return "Continue to the next trick."
    if hand.phase == "redeal":
        return "All players passed. Deal a new hand."
    return None


def _game_phase(state) -> str:
    """Map engine state to the template ``phase`` variable.

    The ``game.html`` template dispatches on this value to select which
    partials to include.
    """
    if state.status == "complete":
        return "match_result"
    hand = state.current_hand
    if hand is None:
        return "model_select"
    if hand.phase == "complete":
        return "hand_result"
    if _has_hidden_auction(hand):
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
        contract_label = str(contract)
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


def _build_action_rail(visible: dict[str, Any], state) -> list[dict[str, str]]:
    """Build the auction-log event feed from auction/trick/redeal transitions.

    The list is capped to the most recent 12 entries for compact rendering.
    """
    hand = state.current_hand
    if hand is None:
        return []

    events: list[dict[str, str]] = []

    # Auction activity (in order).
    for entry in visible.get("auction", []):
        events.append(
            {
                "kind": "auction",
                "text": _format_auction_event(entry.get("seat"), entry),
            }
        )

    # Completed tricks — use team-based language to avoid confusion with
    # auction events (e.g. "You won trick #1" reads like "won the auction").
    for idx, trick in enumerate(visible.get("completed_tricks", []), start=1):
        winner = trick.get("winner")
        if winner is None:
            continue
        winner_int = int(winner)
        if winner_int in (0, 2):
            text = f"Your team won Trick {idx}"
        else:
            text = f"Opponents won Trick {idx}"
        events.append({"kind": "trick", "text": text})

    # Redeal transition.
    if hand.phase == "redeal":
        events.append(
            {"kind": "system", "text": "All players passed; redeal starting."}
        )

    # Hand-complete outcomes (compact summary).
    if hand.phase == "complete":
        bidder = SEAT_LABELS.get(hand.bidder_seat, f"Seat {hand.bidder_seat}")
        if hand.contract_type == "suit" and hand.trump is not None:
            contract = hand.trump
        elif hand.contract_type == "high":
            contract = "High"
        elif hand.contract_type == "low":
            contract = "Low"
        elif hand.winning_bid is None:
            contract = "No contract"
        else:
            contract = str(hand.winning_bid)

        bid_type = hand.bid_type
        if bid_type == "moon":
            contract_label = "Moon"
        elif bid_type == "loner":
            contract_label = "Loner"
        elif hand.winning_bid is None:
            contract_label = "No contract"
        else:
            contract_label = f"{hand.winning_bid} {contract}"

        events.append(
            {
                "kind": "system",
                "text": (
                    f"Hand complete: {bidder} made {contract_label}; "
                    f"scores {state.score_human} vs {state.score_ai}"
                ),
            }
        )

    return events[-12:]


def _build_game_context(
    engine: MatchEngine,
    state,
    link_uuid: str,
) -> dict[str, Any]:
    """Build the Jinja2 template context for the game board.

    Combines visible state (from ``engine.get_visible_state``) with additional
    fields needed by the partials (winning_bid, bidder_seat, current_high_bid,
    points, legal plays, AI hand counts).
    """
    visible = engine.get_visible_state(state)
    hand = state.current_hand
    phase = _game_phase(state)

    if hand is not None and _has_hidden_auction(hand):
        visible["auction"] = visible.get("auction", [])[: hand.revealed_auction_count]
        visible["contract_type"] = None
        visible["trump"] = None
        # Hide trick-play state leaked by engine auto-advance — the user
        # hasn't finished revealing auction bids yet.
        visible["current_trick"] = None
        visible["completed_tricks"] = []
        visible["tricks_team0"] = 0
        visible["tricks_team1"] = 0
    if hand is not None and hand.phase == "trick_play" and hand.paused_after_trick:
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
        ctx["winning_bid"] = None if _has_hidden_auction(hand) else hand.winning_bid
        ctx["bidder_seat"] = None if _has_hidden_auction(hand) else hand.bidder_seat
        ctx["current_high_bid"] = (
            0 if _has_hidden_auction(hand) else hand.current_high_bid
        )
        ctx["points_team0"] = hand.points_team0
        ctx["points_team1"] = hand.points_team1
        ctx["action_rail"] = _build_action_rail(visible, state)
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

    return ctx


def _render_game_board(
    request: Request,
    engine: MatchEngine,
    state,
    link_uuid: str,
) -> str:
    """Render the game board composite partial as an HTML string.

    Returns the inner HTML for the ``#game-board`` div — used by HTMX
    partial POST responses.
    """
    templates = _get_templates(request)
    ctx = _build_game_context(engine, state, link_uuid)
    ctx["request"] = request
    return templates.get_template("partials/game_board.html").render(ctx)


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

        # No nickname yet — show nickname prompt
        if not player.nickname:
            return _with_cookie(
                templates.TemplateResponse(
                    "game.html",
                    {
                        "request": request,
                        "phase": "nickname",
                        "link_uuid": link_uuid,
                        "current_page": "game",
                    },
                )
            )

        # Prefer the most recent *active* match so the reconnect prompt
        # on the landing page and the game page agree.  Fall back to any
        # match (e.g. completed) when no active match exists.  (#2056)
        match_row = (
            session.query(Match)
            .filter_by(player_id=player.id, status="active")
            .order_by(Match.created_at.desc())
            .first()
        )
        if match_row is None:
            match_row = (
                session.query(Match)
                .filter_by(player_id=player.id)
                .order_by(Match.created_at.desc())
                .first()
            )

        if match_row is None:
            # No usable match — show model selection
            ai_manager = _get_ai_manager(request)
            models = ai_manager.list_available()
            return _with_cookie(
                templates.TemplateResponse(
                    "game.html",
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
                templates.TemplateResponse(
                    "game.html",
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
        return _with_cookie(templates.TemplateResponse("game.html", ctx))
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

        # Return model selection form (HTMX partial)
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

        # Rate limit — max active matches per player
        if not check_match_limit(session, player_id=player.id):
            raise HTTPException(
                status_code=429,
                detail="Match limit reached — complete or abandon an existing match first",
            )

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
        state = engine.start_match(seed=seed, ai_model=model_id)

        match_uuid = str(uuid.uuid4())
        match_row = Match(
            match_uuid=match_uuid,
            player_id=player.id,
            ai_model=model_id,
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

        session.commit()

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
        state = _deserialize_state(engine, match_row.match_state_json)

        # Idempotency check
        hand = state.current_hand
        if hand is None or turn_number < hand.turn_number:
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))

        # State-desync recovery — return the authoritative board for stale
        # requests instead of 400 so HTMX can re-sync the DOM.
        if hand.phase != "auction":
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
        if hand.current_seat != HUMAN_SEAT:
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
        if _awaiting_next(hand):
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))

        # Build bid action
        if bid_n == 0:
            bid = BidAction.pass_bid()
        else:
            if bid_contract is None:
                raise HTTPException(
                    status_code=400, detail="bid_contract required for non-pass bids"
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
            raise HTTPException(status_code=400, detail="Illegal bid")

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
        state = engine.submit_human_bid(state, bid)
        current_hand = state.current_hand
        if current_hand is not None:
            current_hand.revealed_auction_count = min(
                len(current_hand.auction),
                pre_auction_count + 1,
            )

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
        session.commit()

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
        state = _deserialize_state(engine, match_row.match_state_json)

        # Idempotency check
        hand = state.current_hand
        if hand is None or turn_number < hand.turn_number:
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))

        # State-desync recovery — if HTMX morph left stale card buttons in
        # the DOM the player may click a card while the server is in a
        # different phase or waiting for a reveal advance.  Rather than
        # returning a 400 (which requires a full page reload to recover),
        # re-render the authoritative board so HTMX can swap in the correct
        # state.  True validation errors (illegal card) still return 400.
        if hand.phase != "trick_play":
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
        if hand.current_seat != HUMAN_SEAT:
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
        if _awaiting_next(hand):
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))

        # Validate legality
        legal_plays = engine.get_legal_plays(state)
        if card_index not in legal_plays:
            raise HTTPException(status_code=400, detail="Illegal card play")

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
        state = engine.submit_human_card(state, card_index)
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
        session.commit()

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
        if match_row is None:
            raise HTTPException(status_code=404, detail="No active match")

        ai_manager = _get_ai_manager(request)
        engine = _build_engine(ai_manager, match_row.ai_model)
        state = _deserialize_state(engine, match_row.match_state_json)

        hand = state.current_hand
        if hand is None:
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))

        if _has_hidden_auction(hand):
            hand.revealed_auction_count += 1
        elif _has_pending_exchange(hand):
            hand.exchange_revealed = True
            # Moon: trigger deferred AI advancement.  When the human is
            # sitting out (partner of the mooner), submit_exchange_selection
            # deferred _advance_ai so the interstitial could display first.
            state = engine.advance_after_exchange_reveal(state)
        elif hand.phase == "trick_play" and hand.paused_after_trick:
            # Resume AI advancement after trick-result interstitial.
            # The engine will play AI turns until the next trick
            # completion (setting paused_after_trick again), the
            # human's turn, or hand/match end.
            state = engine.resume_ai(state)
        elif hand.phase == "redeal":
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
        session.commit()

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
        state = _deserialize_state(engine, match_row.match_state_json)

        hand = state.current_hand
        if hand is None or hand.phase != "moon_exchange":
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))

        if hand.exchange_phase != "selecting":
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))

        state = engine.submit_exchange_selection(state, [card_index_0, card_index_1])

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
        session.commit()

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

        # Look for an active match first; fall back to the most recent
        # completed match so that a stale "Next Hand" click renders the
        # match-result screen instead of a 404 (P2-005 defensive fix).
        match_row = (
            session.query(Match)
            .filter_by(player_id=player.id, status="active")
            .order_by(Match.created_at.desc())
            .first()
        )
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
        state = _deserialize_state(engine, match_row.match_state_json)

        # If the match is already complete, render the result screen
        # immediately — do not advance to a new hand (P2-005).
        if state.status == "complete":
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))

        hand = state.current_hand
        if hand is None:
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))

        # Persist current hand before any hand transition
        hand_row = _ensure_hand_row(session, match_row, hand, hand.deal_id)
        if hand.phase == "complete":
            _update_hand_row(hand_row, hand)

        # Only start a new hand when we are paused on a completed hand
        state = engine.advance_to_next_hand(state)

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
        session.commit()

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

        return templates.TemplateResponse(
            "leaderboard.html",
            {
                "request": request,
                "link_uuid": link_uuid,
                "current_page": "leaderboard",
                "nickname": player.nickname,
                "rankings": rankings,
                "metric_defs": METRIC_DEFINITIONS,
                "format_metric": format_metric,
            },
        )
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

        return templates.TemplateResponse(
            "history.html",
            {
                "request": request,
                "link_uuid": link_uuid,
                "current_page": "history",
                "nickname": player.nickname,
                "matches": history_entries,
            },
        )
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
