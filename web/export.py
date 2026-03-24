"""JSONL export logic for hosted-play decisions.

Converts DB decision rows (with match and hand context) into the
JSONL-exportable dict format defined in SP-4-01.  Also provides
``validate_replay`` for offline verification of exported JSONL files.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from bid_euchre.core.cards import Card
from bid_euchre.core.rules import get_legal_indices, trick_winner
from bid_euchre.scoring import compute_points
from bid_euchre.sim.deals import generate_deal
from web.db import Decision, Hand, Match

# Human player is always seat 0 in hosted play.
_HUMAN_SEAT = 0

# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1
EVENT_TYPE = "hosted_decision"

# All fields required by the SP-4-01 JSONL schema (schema_version 1).
REQUIRED_FIELDS: frozenset[str] = frozenset(
    {
        "schema_version",
        "event",
        "match_uuid",
        "match_seed",
        "hand_number",
        "deal_id",
        "dealer_seat",
        "turn_number",
        "seat",
        "phase",
        "actor_type",
        "decision_source",
        "ai_model",
        "legal_actions",
        "chosen_action",
        "game_state",
        "decision_time_ms",
        "timestamp",
    }
)


# ---------------------------------------------------------------------------
# Export function
# ---------------------------------------------------------------------------


def decision_to_jsonl(
    decision_row: Decision,
    match_row: Match,
    hand_row: Hand,
) -> dict:
    """Convert a DB decision row + context to a JSONL-exportable dict.

    The output dict matches the SP-4-01 JSONL schema (``schema_version`` 1).
    JSON string columns (``legal_actions_json``, ``chosen_action_json``,
    ``game_state_json``) are parsed into Python objects so they serialize
    naturally when the caller writes the dict as a JSON line.

    Parameters
    ----------
    decision_row : Decision
        The decision DB row.
    match_row : Match
        The parent match DB row (provides ``match_uuid``, ``seed``,
        ``ai_model``).
    hand_row : Hand
        The parent hand DB row (provides ``hand_number``, ``deal_id``,
        ``dealer_seat``).

    Returns
    -------
    dict
        JSONL-serializable dictionary with all required SP-4-01 fields.
    """
    # Parse JSON string columns into Python objects
    legal_actions = json.loads(decision_row.legal_actions_json)
    chosen_action = json.loads(decision_row.chosen_action_json)
    game_state = json.loads(decision_row.game_state_json)

    # Format timestamp as ISO 8601 UTC string
    ts = decision_row.created_at
    if ts is not None and ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    timestamp = ts.isoformat() if ts is not None else None

    return {
        "schema_version": SCHEMA_VERSION,
        "event": EVENT_TYPE,
        "match_uuid": match_row.match_uuid,
        "match_seed": match_row.seed,
        "hand_number": hand_row.hand_number,
        "deal_id": hand_row.deal_id,
        "dealer_seat": hand_row.dealer_seat,
        "turn_number": decision_row.turn_number,
        "seat": decision_row.seat,
        "phase": decision_row.phase,
        "actor_type": decision_row.actor_type,
        "decision_source": decision_row.decision_source,
        "ai_model": match_row.ai_model,
        "legal_actions": legal_actions,
        "chosen_action": chosen_action,
        "game_state": game_state,
        "decision_time_ms": decision_row.decision_time_ms,
        "timestamp": timestamp,
    }


# ---------------------------------------------------------------------------
# Batch export
# ---------------------------------------------------------------------------


def export_decisions(
    db_session: Session,
    output_path: Path,
    match_uuid: Optional[str] = None,
    human_only: bool = False,
) -> int:
    """Export decisions from DB to JSONL.

    Queries ``Decision`` rows (with ``Match`` and ``Hand`` context), applies
    optional filters, and writes one JSON line per decision to *output_path*.

    Parameters
    ----------
    db_session : Session
        An active SQLAlchemy session.
    output_path : Path
        Destination file path. Parent directory must exist.
    match_uuid : str, optional
        If provided, only export decisions belonging to this match.
    human_only : bool
        If ``True``, only export decisions where ``actor_type == 'human'``.

    Returns
    -------
    int
        Number of records exported.
    """
    query = (
        db_session.query(Decision, Match, Hand)
        .join(Match, Decision.match_id == Match.id)
        .join(Hand, Decision.hand_id == Hand.id)
    )

    if match_uuid is not None:
        query = query.filter(Match.match_uuid == match_uuid)

    if human_only:
        query = query.filter(Decision.actor_type == "human")

    # Order by logical hand number (not internal hand_id FK) for
    # deterministic, semantically meaningful output (#1537).
    query = query.order_by(Decision.match_id, Hand.hand_number, Decision.turn_number)

    count = 0
    with open(output_path, "w") as f:
        # Stream results to avoid materializing all rows in memory (#1546).
        for decision_row, match_row, hand_row in query.yield_per(500):
            record = decision_to_jsonl(decision_row, match_row, hand_row)
            f.write(json.dumps(record) + "\n")
            count += 1

    return count


# ---------------------------------------------------------------------------
# Replay validation
# ---------------------------------------------------------------------------


def validate_replay(jsonl_path: Path) -> list[str]:
    """Replay all decisions in a JSONL file, return list of errors (empty = valid).

    Reads each JSONL decision record, groups by hand, and verifies:

    1. **Deal regeneration** — ``generate_deal(match_seed, deal_id)`` produces
       hands that match the logged ``human_hand`` in ``game_state``.
    2. **Action legality** — ``chosen_action`` is present in ``legal_actions``
       for every decision.
    3. **Play legality** — for play-phase decisions with sufficient game-state
       context, ``get_legal_indices()`` independently confirms the legal set.
    4. **Trick winners** — ``trick_winner()`` agrees with logged winners in
       ``completed_tricks``.
    5. **Scoring** — ``compute_points()`` agrees with logged trick counts and
       point totals.

    Parameters
    ----------
    jsonl_path : Path
        Path to a ``.jsonl`` file previously written by ``export_decisions``.

    Returns
    -------
    list[str]
        One string per detected error.  An empty list means the file is valid.
    """
    errors: list[str] = []
    records = _parse_jsonl(jsonl_path, errors)
    if not records:
        return errors

    # Group records by (match_uuid, hand_number).
    by_hand: dict[tuple[str, int], list[tuple[int, dict]]] = defaultdict(list)
    for line_num, record in records:
        key = (record["match_uuid"], record["hand_number"])
        by_hand[key].append((line_num, record))

    for (match_uuid, hand_number), group in sorted(by_hand.items()):
        group.sort(key=lambda x: x[1]["turn_number"])
        _validate_hand_group(match_uuid, hand_number, group, errors)

    return errors


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_jsonl(
    jsonl_path: Path,
    errors: list[str],
) -> list[tuple[int, dict]]:
    """Read *jsonl_path* and return ``(line_number, record)`` pairs.

    Parse errors are appended to *errors*; successfully parsed records are
    returned even when some lines fail.
    """
    records: list[tuple[int, dict]] = []
    with open(jsonl_path) as f:
        for line_num, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_num}: invalid JSON — {exc}")
                continue

            # Minimal structural check.
            for field in ("match_uuid", "hand_number", "match_seed", "deal_id"):
                if field not in record:
                    errors.append(f"line {line_num}: missing required field '{field}'")
                    break
            else:
                records.append((line_num, record))
    return records


def _card_tuples(card_list: list) -> list[tuple[str, str]]:
    """Convert ``[[suit, rank], ...]`` to a list of ``(suit, rank)`` tuples.

    Returns a list (not a set) so that duplicate cards in a double-deck
    game are preserved.
    """
    return [(c[0], c[1]) for c in card_list]


def _plays_from_list(plays_data: list) -> list[tuple[int, Card]]:
    """Convert ``[[seat, [suit, rank]], ...]`` to ``[(seat, Card), ...]``."""
    return [(int(p[0]), Card(suit=p[1][0], rank=p[1][1])) for p in plays_data]


def _validate_hand_group(
    match_uuid: str,
    hand_number: int,
    group: list[tuple[int, dict]],
    errors: list[str],
) -> None:
    """Run all validation checks on one hand's decision records."""
    prefix = f"hand {match_uuid[:8]}../{hand_number}"

    first_rec = group[0][1]
    match_seed = first_rec["match_seed"]
    deal_id = first_rec["deal_id"]

    # --- 1. Deal regeneration -------------------------------------------------
    dealt_hands = generate_deal(match_seed, deal_id)
    dealt_human_counts = Counter((c.suit, c.rank) for c in dealt_hands[_HUMAN_SEAT])

    gs_first = first_rec.get("game_state", {})
    if "human_hand" in gs_first and gs_first["human_hand"]:
        logged_human_counts = Counter(_card_tuples(gs_first["human_hand"]))
        # Each logged card must not exceed the dealt multiplicity (multiset subset).
        extra = logged_human_counts - dealt_human_counts
        if extra:
            errors.append(
                f"{prefix}: human hand contains cards not in dealt hand: {dict(extra)}"
            )

    # --- 2 & 3. Per-decision legality checks ----------------------------------
    for line_num, rec in group:
        _validate_decision_legality(line_num, rec, dealt_hands, errors)

    # --- 4. Trick winner verification -----------------------------------------
    last_gs = group[-1][1].get("game_state", {})
    contract_type = last_gs.get("contract_type")
    trump = last_gs.get("trump")

    completed = last_gs.get("completed_tricks") or []
    for i, trick in enumerate(completed):
        plays_data = trick.get("plays", [])
        if len(plays_data) != 4:
            continue  # Incomplete trick — skip winner check
        plays = _plays_from_list(plays_data)
        if contract_type is None:
            continue
        computed_winner = trick_winner(plays, contract_type, trump)
        logged_winner = trick.get("winner")
        if computed_winner != logged_winner:
            errors.append(
                f"{prefix} trick {i}: winner mismatch "
                f"(logged={logged_winner}, computed={computed_winner})"
            )

    # --- 5. Scoring verification ----------------------------------------------
    _validate_scoring(prefix, last_gs, completed, errors)


def _validate_decision_legality(
    line_num: int,
    rec: dict,
    dealt_hands: list[list[Card]],
    errors: list[str],
) -> None:
    """Check chosen_action ∈ legal_actions and, for plays, cross-check
    with ``get_legal_indices``."""
    chosen = rec.get("chosen_action")
    legal = rec.get("legal_actions")
    phase = rec.get("phase")

    # Self-consistency: chosen must be in legal.
    if legal is not None and chosen is not None and chosen not in legal:
        errors.append(f"line {line_num}: chosen action not in legal_actions")

    # For play-phase decisions, independently verify with get_legal_indices.
    if phase != "play":
        return

    gs = rec.get("game_state", {})
    contract_type = gs.get("contract_type")
    trump = gs.get("trump")
    if contract_type is None:
        return  # Can't verify without contract info

    seat = rec.get("seat")
    if seat is None:
        return

    # Reconstruct the player's current hand: dealt hand minus all cards
    # played in completed_tricks and the current trick so far.
    player_hand = _reconstruct_hand(seat, dealt_hands, gs)
    if player_hand is None:
        return  # Can't reconstruct — skip

    current_plays = _current_trick_plays(gs)

    computed_legal = get_legal_indices(
        player_hand,
        current_plays,
        contract_type,
        trump,
    )

    # Compare: legal_actions from the record should match computed.
    if isinstance(legal, list) and all(isinstance(x, int) for x in legal):
        if sorted(computed_legal) != sorted(legal):
            errors.append(
                f"line {line_num}: legal_actions mismatch "
                f"(logged={sorted(legal)}, computed={sorted(computed_legal)})"
            )


def _reconstruct_hand(
    seat: int,
    dealt_hands: list[list[Card]],
    game_state: dict,
) -> list[Card] | None:
    """Reconstruct a player's current hand by removing played cards.

    Returns ``None`` if the game-state lacks enough information.
    """
    if seat < 0 or seat >= len(dealt_hands):
        return None

    original = list(dealt_hands[seat])  # copy
    played_cards: list[Card] = []

    # Cards played in completed tricks by this seat.
    for trick in game_state.get("completed_tricks") or []:
        for play in trick.get("plays", []):
            if int(play[0]) == seat:
                played_cards.append(Card(suit=play[1][0], rank=play[1][1]))

    # Cards played in the current trick by this seat.
    ct = game_state.get("current_trick")
    if ct is not None:
        for play in ct.get("plays", []):
            if int(play[0]) == seat:
                played_cards.append(Card(suit=play[1][0], rank=play[1][1]))

    # Remove played cards from the hand.
    remaining = list(original)
    for card in played_cards:
        try:
            remaining.remove(card)
        except ValueError:
            # Card not found — deal mismatch already caught.
            return None

    return remaining


def _current_trick_plays(game_state: dict) -> list[tuple[int, Card]]:
    """Extract plays-so-far in the current trick as ``(seat, Card)`` tuples."""
    ct = game_state.get("current_trick")
    if ct is None:
        return []
    return _plays_from_list(ct.get("plays", []))


def _validate_scoring(
    prefix: str,
    game_state: dict,
    completed_tricks: list[dict],
    errors: list[str],
) -> None:
    """Verify trick counts and points against ``compute_points``."""
    if not completed_tricks:
        return

    # Count tricks per team from completed tricks.
    computed_t0 = sum(1 for t in completed_tricks if t.get("winner") in (0, 2))
    computed_t1 = sum(1 for t in completed_tricks if t.get("winner") in (1, 3))

    logged_t0 = game_state.get("tricks_team0")
    logged_t1 = game_state.get("tricks_team1")

    if logged_t0 is not None and computed_t0 != logged_t0:
        errors.append(
            f"{prefix}: team0 tricks mismatch "
            f"(logged={logged_t0}, counted={computed_t0})"
        )
    if logged_t1 is not None and computed_t1 != logged_t1:
        errors.append(
            f"{prefix}: team1 tricks mismatch "
            f"(logged={logged_t1}, counted={computed_t1})"
        )

    # If all 10 tricks are complete, verify points with compute_points.
    if len(completed_tricks) < 10:
        return

    # Need auction result from game_state.
    auction = game_state.get("auction") or []
    winning_bid = _extract_winning_bid(auction)
    bidder_seat = _extract_bidder_seat(auction)

    if winning_bid is None:
        return  # Can't verify scoring without bid info

    pts_t0, pts_t1 = compute_points(
        winning_bid=winning_bid,
        bidder_position=bidder_seat,
        tricks_team0=computed_t0,
        tricks_team1=computed_t1,
    )

    logged_pts_t0 = game_state.get("points_team0")
    logged_pts_t1 = game_state.get("points_team1")

    # Only report if the game_state actually has points to compare.
    if logged_pts_t0 is not None and pts_t0 != logged_pts_t0:
        errors.append(
            f"{prefix}: team0 points mismatch "
            f"(logged={logged_pts_t0}, computed={pts_t0})"
        )
    if logged_pts_t1 is not None and pts_t1 != logged_pts_t1:
        errors.append(
            f"{prefix}: team1 points mismatch "
            f"(logged={logged_pts_t1}, computed={pts_t1})"
        )


def _extract_winning_bid(auction: list[dict]) -> int | None:
    """Return the winning bid *n* from an auction transcript, or ``None``."""
    winning = None
    for entry in auction:
        n = entry.get("n", 0)
        if n > 0:
            winning = n
    return winning


def _extract_bidder_seat(auction: list[dict]) -> int | None:
    """Return the seat of the winning bidder from an auction transcript."""
    bidder = None
    for entry in auction:
        n = entry.get("n", 0)
        if n > 0:
            bidder = entry.get("seat")
    return bidder
