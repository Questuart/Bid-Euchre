"""
Unit tests for GameLogger and HandEndRecord schema versioning.

Focuses on schema version correctness and the v6 fields (redeal_flag, made_bid)
and the v7 field (auction_transcript).
"""

import json

from bid_euchre.logging.game_logger import (
    SCHEMA_VERSION,
    GameLogger,
    HandEndRecord,
    LogLevel,
)


def test_schema_version_is_7():
    """Schema version must be 7 after PR B-2 auction_transcript addition."""
    assert SCHEMA_VERSION == 7


def test_hand_end_record_has_v6_fields():
    """HandEndRecord dataclass must have redeal_flag and made_bid fields."""
    record = HandEndRecord(
        schema_version=7,
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
    assert hand_end["schema_version"] == 7
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
    assert hand_end["schema_version"] == 7
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


# ---------------------------------------------------------------------------
# v7 tests — auction_transcript
# ---------------------------------------------------------------------------


def test_hand_end_record_has_auction_transcript_field():
    """HandEndRecord dataclass must have auction_transcript field defaulting to None."""
    record = HandEndRecord(
        schema_version=7,
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
    assert hasattr(record, "auction_transcript")
    assert record.auction_transcript is None  # default


def test_log_hand_end_writes_auction_transcript(tmp_path):
    """log_hand_end writes auction_transcript entries to JSONL output."""
    log_path = str(tmp_path / "test_v7.jsonl")
    transcript = [
        {
            "seat": 1,
            "action": "PASS",
            "tricks_bid": 0,
            "contract_type": None,
            "trump": None,
        },
        {
            "seat": 2,
            "action": "BID",
            "tricks_bid": 3,
            "contract_type": "suit",
            "trump": "H",
        },
        {
            "seat": 3,
            "action": "PASS",
            "tricks_bid": 0,
            "contract_type": None,
            "trump": None,
        },
        {
            "seat": 0,
            "action": "PASS",
            "tricks_bid": 0,
            "contract_type": None,
            "trump": None,
        },
    ]
    logger = GameLogger(run_id="test_v7", strategy_id="greedy", level=LogLevel.HAND)
    logger.open(log_path)
    logger.log_hand_end(
        deal_id=0,
        seed=42,
        contract="suit",
        trump="H",
        leader=2,
        t0=7,
        t1=3,
        features=[{}, {}, {}, {}],
        redeal_flag=False,
        made_bid=True,
        auction_transcript=transcript,
    )
    logger.close()

    records = [json.loads(line) for line in open(log_path)]
    hand_end = next(r for r in records if r.get("event") == "hand_end")
    assert hand_end["schema_version"] == 7
    assert hand_end["auction_transcript"] == transcript


def test_auction_transcript_null_when_not_provided(tmp_path):
    """auction_transcript defaults to null in JSONL when not passed."""
    log_path = str(tmp_path / "test_no_transcript.jsonl")
    logger = GameLogger(run_id="test_no_tr", strategy_id="greedy", level=LogLevel.HAND)
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
    assert hand_end["auction_transcript"] is None


def test_all_pass_transcript_has_four_passes(tmp_path):
    """All-pass redeal: transcript has 4 PASS entries alongside redeal_flag=True."""
    log_path = str(tmp_path / "test_all_pass.jsonl")
    all_pass_transcript = [
        {
            "seat": 1,
            "action": "PASS",
            "tricks_bid": 0,
            "contract_type": None,
            "trump": None,
        },
        {
            "seat": 2,
            "action": "PASS",
            "tricks_bid": 0,
            "contract_type": None,
            "trump": None,
        },
        {
            "seat": 3,
            "action": "PASS",
            "tricks_bid": 0,
            "contract_type": None,
            "trump": None,
        },
        {
            "seat": 0,
            "action": "PASS",
            "tricks_bid": 0,
            "contract_type": None,
            "trump": None,
        },
    ]
    logger = GameLogger(run_id="test_ap", strategy_id="greedy", level=LogLevel.HAND)
    logger.open(log_path)
    logger.log_hand_end(
        deal_id=0,
        seed=42,
        contract="high",
        trump=None,
        leader=-1,
        t0=0,
        t1=0,
        features=[{}, {}, {}, {}],
        redeal_flag=True,
        made_bid=None,
        auction_transcript=all_pass_transcript,
    )
    logger.close()

    records = [json.loads(line) for line in open(log_path)]
    hand_end = next(r for r in records if r.get("event") == "hand_end")
    assert hand_end["redeal_flag"] is True
    tr = hand_end["auction_transcript"]
    assert len(tr) == 4
    assert all(entry["action"] == "PASS" for entry in tr)
    assert all(entry["tricks_bid"] == 0 for entry in tr)


def test_auction_transcript_bid_entry_format(tmp_path):
    """BID entries in the transcript have correct structure."""
    log_path = str(tmp_path / "test_bid_entry.jsonl")
    transcript = [
        {
            "seat": 1,
            "action": "PASS",
            "tricks_bid": 0,
            "contract_type": None,
            "trump": None,
        },
        {
            "seat": 2,
            "action": "BID",
            "tricks_bid": 4,
            "contract_type": "high",
            "trump": None,
        },
        {
            "seat": 3,
            "action": "PASS",
            "tricks_bid": 0,
            "contract_type": None,
            "trump": None,
        },
        {
            "seat": 0,
            "action": "PASS",
            "tricks_bid": 0,
            "contract_type": None,
            "trump": None,
        },
    ]
    logger = GameLogger(run_id="test_bid", strategy_id="greedy", level=LogLevel.HAND)
    logger.open(log_path)
    logger.log_hand_end(
        deal_id=0,
        seed=42,
        contract="high",
        trump=None,
        leader=2,
        t0=3,
        t1=7,
        features=[{}, {}, {}, {}],
        winning_bid=4,
        bidder_position=2,
        made_bid=False,
        auction_transcript=transcript,
    )
    logger.close()

    records = [json.loads(line) for line in open(log_path)]
    hand_end = next(r for r in records if r.get("event") == "hand_end")
    bid_entry = next(e for e in hand_end["auction_transcript"] if e["action"] == "BID")
    assert bid_entry["seat"] == 2
    assert bid_entry["tricks_bid"] == 4
    assert bid_entry["contract_type"] == "high"
    assert bid_entry["trump"] is None
