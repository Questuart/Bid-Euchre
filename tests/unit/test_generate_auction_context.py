"""
Unit tests for auction-context dataset generator.

Tests the JSONL parsing and dataset building logic (not the experiment runner).
"""

import importlib.util
import json
from pathlib import Path

import pandas as pd

from bid_euchre.features.auction_context import PARTNER_FEATURE_NAMES

# Import script via importlib (no sys.path manipulation)
_SCRIPT = (
    Path(__file__).parent.parent.parent
    / "scripts"
    / "internal"
    / "generate_auction_context_dataset.py"
)
_spec = importlib.util.spec_from_file_location(
    "generate_auction_context_dataset", _SCRIPT
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
build_dataset_from_jsonl = _mod.build_dataset_from_jsonl
validate_dataset = _mod.validate_dataset
_parse_contract = _mod._parse_contract


def _make_hand_end_record(
    hand_id=0,
    contract="H",
    trump="H",
    t0=6,
    t1=4,
    dealer=0,
    hands=None,
    auction_transcript=None,
):
    """Create a minimal hand_end JSONL record for testing."""
    if hands is None:
        # 4 hands of 10 cards each (simplified — just enough to extract features)
        default_hand = [
            ["H", "A"],
            ["H", "K"],
            ["H", "Q"],
            ["S", "A"],
            ["S", "K"],
            ["D", "A"],
            ["D", "K"],
            ["C", "A"],
            ["C", "K"],
            ["C", "Q"],
        ]
        hands = [default_hand] * 4

    if auction_transcript is None:
        auction_transcript = [
            {"seat": 0, "action": "BID", "tricks_bid": 6, "contract_type": "suit"},
            {"seat": 1, "action": "PASS"},
            {"seat": 2, "action": "BID", "tricks_bid": 4, "contract_type": "suit"},
            {"seat": 3, "action": "PASS"},
        ]

    return {
        "schema_version": 7,
        "event": "hand_end",
        "run_id": "test_run",
        "strategy_id": "test",
        "deal_id": hand_id,
        "seed": 42,
        "contract": contract,
        "trump": trump,
        "leader": 0,
        "t0": t0,
        "t1": t1,
        "features": [{}, {}, {}, {}],
        "scores": [0, 0, 0, 0],
        "hands": hands,
        "dealer_position": dealer,
        "auction_transcript": auction_transcript,
    }


def _write_jsonl(records, path):
    """Write records to a JSONL file."""
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r, sort_keys=True) + "\n")


class TestBuildDataset:
    """Test JSONL parsing and dataset building."""

    def test_single_hand_produces_4_bidless_rows(self, tmp_path):
        """One hand_end record produces 4 bidless rows (one per seat)."""
        jsonl_path = str(tmp_path / "test.jsonl")
        records = [
            {"event": "run_start", "schema_version": 7, "run_id": "test"},
            _make_hand_end_record(hand_id=0),
            {"event": "run_end", "schema_version": 7, "run_id": "test"},
        ]
        _write_jsonl(records, jsonl_path)

        bidless, outcomes = build_dataset_from_jsonl(jsonl_path)

        assert len(bidless) == 4
        assert len(outcomes) == 1
        assert {r["seat"] for r in bidless} == {0, 1, 2, 3}

    def test_partner_features_present(self, tmp_path):
        """All 4 partner features are present in hand_features dict."""
        jsonl_path = str(tmp_path / "test.jsonl")
        _write_jsonl([_make_hand_end_record()], jsonl_path)

        bidless, _ = build_dataset_from_jsonl(jsonl_path)

        for row in bidless:
            features = row["hand_features"]
            for fname in PARTNER_FEATURE_NAMES:
                assert fname in features, f"Missing: {fname}"
                assert features[fname] is not None

    def test_42_features_per_row(self, tmp_path):
        """Each row has 42 features (39 hand + 3 partner)."""
        jsonl_path = str(tmp_path / "test.jsonl")
        _write_jsonl([_make_hand_end_record()], jsonl_path)

        bidless, _ = build_dataset_from_jsonl(jsonl_path)

        for row in bidless:
            assert len(row["hand_features"]) == 42

    def test_outcomes_schema_matches_bidless_format(self, tmp_path):
        """Outcomes DataFrame has the expected columns."""
        jsonl_path = str(tmp_path / "test.jsonl")
        _write_jsonl([_make_hand_end_record()], jsonl_path)

        _, outcomes = build_dataset_from_jsonl(jsonl_path)
        outcomes_df = pd.DataFrame(outcomes)

        required_cols = {
            "hand_id",
            "deal_id",
            "dealer_seat",
            "contract_type",
            "trump_suit",
            "tricks_team0",
            "tricks_team1",
            "team0_win",
        }
        assert required_cols.issubset(set(outcomes_df.columns))

    def test_high_contract_parsing(self, tmp_path):
        """HIGH contract maps to contract_type='high', trump_suit=None."""
        jsonl_path = str(tmp_path / "test.jsonl")
        record = _make_hand_end_record(contract="HIGH", trump=None)
        _write_jsonl([record], jsonl_path)

        bidless, outcomes = build_dataset_from_jsonl(jsonl_path)

        assert outcomes[0]["contract_type"] == "high"
        assert outcomes[0]["trump_suit"] is None
        assert bidless[0]["contract_type"] == "high"

    def test_low_contract_parsing(self, tmp_path):
        """LOW contract maps to contract_type='low', trump_suit=None."""
        jsonl_path = str(tmp_path / "test.jsonl")
        record = _make_hand_end_record(contract="LOW", trump=None)
        _write_jsonl([record], jsonl_path)

        _, outcomes = build_dataset_from_jsonl(jsonl_path)
        assert outcomes[0]["contract_type"] == "low"

    def test_multiple_hands(self, tmp_path):
        """Multiple hand_end records produce correct row counts."""
        jsonl_path = str(tmp_path / "test.jsonl")
        records = [
            _make_hand_end_record(hand_id=0),
            _make_hand_end_record(hand_id=1, contract="HIGH", trump=None),
            _make_hand_end_record(hand_id=2, contract="LOW", trump=None),
        ]
        _write_jsonl(records, jsonl_path)

        bidless, outcomes = build_dataset_from_jsonl(jsonl_path)

        assert len(bidless) == 12  # 3 hands × 4 seats
        assert len(outcomes) == 3

    def test_redeal_hands_skipped(self, tmp_path):
        """Hands with redeal_flag=True are skipped."""
        jsonl_path = str(tmp_path / "test.jsonl")
        record = _make_hand_end_record(hand_id=0)
        record["redeal_flag"] = True
        _write_jsonl([record], jsonl_path)

        bidless, outcomes = build_dataset_from_jsonl(jsonl_path)

        assert len(bidless) == 0
        assert len(outcomes) == 0

    def test_compatible_with_join_features_outcomes(self, tmp_path):
        """Output parquet is compatible with join_features_outcomes()."""
        from bid_euchre.datasets.join import join_features_outcomes

        jsonl_path = str(tmp_path / "test.jsonl")
        records = [
            _make_hand_end_record(hand_id=0),
            _make_hand_end_record(hand_id=1),
        ]
        _write_jsonl(records, jsonl_path)

        bidless_rows, outcomes_rows = build_dataset_from_jsonl(jsonl_path)

        bidless_df = pd.DataFrame(bidless_rows)
        outcomes_df = pd.DataFrame(outcomes_rows)

        bidless_path = str(tmp_path / "bidless.parquet")
        outcomes_path = str(tmp_path / "bidless_outcomes.parquet")
        bidless_df.to_parquet(bidless_path)
        outcomes_df.to_parquet(outcomes_path)

        # join_features_outcomes should work without error
        joined = join_features_outcomes(bidless_path, outcomes_path)

        assert len(joined) > 0
        assert "tricks_won" in joined.columns

        # Partner features should be flattened into columns
        for fname in PARTNER_FEATURE_NAMES:
            assert fname in joined.columns


class TestValidateDataset:
    """Test the gate X1 validation function."""

    def test_valid_dataset_passes(self, tmp_path):
        """Valid dataset passes validation without error."""
        jsonl_path = str(tmp_path / "test.jsonl")
        _write_jsonl([_make_hand_end_record()], jsonl_path)

        bidless_rows, outcomes_rows = build_dataset_from_jsonl(jsonl_path)
        bidless_df = pd.DataFrame(bidless_rows)
        outcomes_df = pd.DataFrame(outcomes_rows)

        # Should not raise
        validate_dataset(bidless_df, outcomes_df)


class TestParseContract:
    """Test contract string parsing."""

    def test_suit_contract(self):
        assert _parse_contract("H", "H") == ("suit", "H")
        assert _parse_contract("S", "S") == ("suit", "S")

    def test_high_contract(self):
        assert _parse_contract("HIGH", None) == ("high", None)
        assert _parse_contract("high", None) == ("high", None)

    def test_low_contract(self):
        assert _parse_contract("LOW", None) == ("low", None)
        assert _parse_contract("low", None) == ("low", None)
