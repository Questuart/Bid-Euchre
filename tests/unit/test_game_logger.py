"""
Unit tests for GameLogger and HandEndRecord schema versioning.

Focuses on schema version correctness and the v6 fields (redeal_flag, made_bid).
"""

import json

from bid_euchre.logging.game_logger import (
    SCHEMA_VERSION,
    GameLogger,
    HandEndRecord,
    LogLevel,
)


def test_schema_version_is_6():
    """Schema version must be 6 after PR B-1 additions."""
    assert SCHEMA_VERSION == 6


def test_hand_end_record_has_v6_fields():
    """HandEndRecord dataclass must have redeal_flag and made_bid fields."""
    record = HandEndRecord(
        schema_version=6,
        event="hand_end",
        run_id="test",
        strategy_id="greedy",
        deal_id=0,
        seed=42,
        contract="suit",
        trump="H",
        leader=0,
        t0=6,
        t1=4,
        features=[{}, {}, {}, {}],
        scores=None,
        hands=None,
    )
    assert hasattr(record, "redeal_flag")
    assert hasattr(record, "made_bid")
    assert record.redeal_flag is None  # default
    assert record.made_bid is None  # default


def test_log_hand_end_writes_v6_fields(tmp_path):
    """log_hand_end writes redeal_flag and made_bid to JSONL output."""
    log_path = str(tmp_path / "test.jsonl")
    logger = GameLogger(run_id="test_v6", strategy_id="greedy", level=LogLevel.HAND)
    logger.open(log_path)
    logger.log_hand_end(
        deal_id=0,
        seed=42,
        contract="suit",
        trump="H",
        leader=0,
        t0=6,
        t1=4,
        features=[{}, {}, {}, {}],
        redeal_flag=False,
        made_bid=True,
    )
    logger.close()

    records = [json.loads(line) for line in open(log_path)]
    hand_end = next(r for r in records if r.get("event") == "hand_end")
    assert hand_end["schema_version"] == 6
    assert hand_end["redeal_flag"] is False
    assert hand_end["made_bid"] is True


def test_log_hand_end_null_v6_fields_when_not_provided(tmp_path):
    """redeal_flag and made_bid default to null when not passed."""
    log_path = str(tmp_path / "test_null.jsonl")
    logger = GameLogger(run_id="test_null", strategy_id="greedy", level=LogLevel.HAND)
    logger.open(log_path)
    logger.log_hand_end(
        deal_id=0,
        seed=42,
        contract="high",
        trump=None,
        leader=0,
        t0=5,
        t1=5,
        features=[{}, {}, {}, {}],
    )
    logger.close()

    records = [json.loads(line) for line in open(log_path)]
    hand_end = next(r for r in records if r.get("event") == "hand_end")
    assert hand_end["schema_version"] == 6
    assert hand_end["redeal_flag"] is None
    assert hand_end["made_bid"] is None


def test_redeal_flag_true_for_all_pass_hand(tmp_path):
    """A redeal hand should have redeal_flag=True, t0=0, t1=0."""
    log_path = str(tmp_path / "test_redeal.jsonl")
    logger = GameLogger(run_id="test_redeal", strategy_id="greedy", level=LogLevel.HAND)
    logger.open(log_path)
    logger.log_hand_end(
        deal_id=0,
        seed=42,
        contract="suit",
        trump=None,
        leader=0,
        t0=0,
        t1=0,
        features=[{}, {}, {}, {}],
        redeal_flag=True,
        made_bid=None,  # no bid was made (all-pass)
    )
    logger.close()

    records = [json.loads(line) for line in open(log_path)]
    hand_end = next(r for r in records if r.get("event") == "hand_end")
    assert hand_end["redeal_flag"] is True
    assert hand_end["t0"] == 0
    assert hand_end["t1"] == 0
