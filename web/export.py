"""JSONL export logic for hosted-play decisions.

Converts DB decision rows (with match and hand context) into the
JSONL-exportable dict format defined in SP-4-01.
"""

from __future__ import annotations

import json
from datetime import timezone

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
