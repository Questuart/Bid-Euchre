"""JSONL export logic for hosted-play decisions.

Converts DB decision rows (with match and hand context) into the
JSONL-exportable dict format defined in SP-4-01.
"""

from __future__ import annotations

import json
from datetime import timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from web.db import Decision, Hand, Match

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

    # Order deterministically for reproducible exports
    query = query.order_by(Decision.match_id, Decision.hand_id, Decision.turn_number)

    count = 0
    with open(output_path, "w") as f:
        for decision_row, match_row, hand_row in query:
            record = decision_to_jsonl(decision_row, match_row, hand_row)
            f.write(json.dumps(record) + "\n")
            count += 1

    return count
