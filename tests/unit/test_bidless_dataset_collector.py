"""
Schema guard tests for bidless dataset contract (v1).

These tests ensure the bidless dataset schema remains stable and catches
accidental contract breaks in CI.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from bid_euchre.core.cards import Card
from bid_euchre.datasets.bidless import BidlessDatasetCollector


class TestBidlessDatasetSchema:
    """Test bidless dataset schema stability and validation."""

    def test_collector_initialization(self):
        """Test basic collector initialization."""
        collector = BidlessDatasetCollector("test_run", 1)
        assert collector.run_id == "test_run"
        assert collector.hand_id == 1
        assert collector.rows == []

    def test_record_hand_value_basic(self):
        """Test basic hand value recording."""
        collector = BidlessDatasetCollector("test_run", 1)

        hand = [Card("S", "A"), Card("D", "K"), Card("H", "Q"), Card("C", "J"), Card("D", "T")]
        collector.record_hand_value(
            hand=hand,
            seat=0,
            dealer_seat=1,
            contract_type="suit",
            trump_suit="S"
        )

        assert len(collector.rows) == 1
        row = collector.rows[0]
        assert row["hand_id"] == 1
        assert row["seat"] == 0
        assert row["dealer_seat"] == 1
        assert row["contract_type"] == "suit"
        assert row["trump_suit"] == "S"
        assert row["hand_cards"] == ["AS", "KD", "QH", "JC", "TD"]

    def test_contract_validation(self):
        """Test contract type and trump suit validation."""
        collector = BidlessDatasetCollector("test_run", 1)
        hand = [Card("S", "A"), Card("D", "K"), Card("H", "Q"), Card("C", "J"), Card("D", "T")]

        # Valid suit contract
        collector.record_hand_value(
            hand=hand,
            seat=0,
            dealer_seat=1,
            contract_type="suit",
            trump_suit="S"
        )

        # Valid HIGH contract
        collector.record_hand_value(
            hand=hand,
            seat=1,
            dealer_seat=1,
            contract_type="HIGH",
            trump_suit=None
        )

        # Valid LOW contract
        collector.record_hand_value(
            hand=hand,
            seat=2,
            dealer_seat=1,
            contract_type="LOW",
            trump_suit=None
        )

        assert len(collector.rows) == 3

    def test_invalid_contract_type(self):
        """Test invalid contract type raises ValueError."""
        collector = BidlessDatasetCollector("test_run", 1)
        hand = [Card("S", "A"), Card("D", "K"), Card("H", "Q"), Card("C", "J"), Card("D", "T")]

        with pytest.raises(ValueError, match="Invalid contract_type"):
            collector.record_hand_value(
                hand=hand,
                seat=0,
                dealer_seat=1,
                contract_type="invalid",
                trump_suit=None
            )

    def test_suit_contract_requires_trump_suit(self):
        """Test suit contract requires trump_suit."""
        collector = BidlessDatasetCollector("test_run", 1)
        hand = [Card("S", "A"), Card("D", "K"), Card("H", "Q"), Card("C", "J"), Card("D", "T")]

        with pytest.raises(ValueError, match="trump_suit must be provided"):
            collector.record_hand_value(
                hand=hand,
                seat=0,
                dealer_seat=1,
                contract_type="suit",
                trump_suit=None
            )

    def test_high_low_contracts_reject_trump_suit(self):
        """Test HIGH/LOW contracts reject trump_suit."""
        collector = BidlessDatasetCollector("test_run", 1)
        hand = [Card("S", "A"), Card("D", "K"), Card("H", "Q"), Card("C", "J"), Card("D", "T")]

        with pytest.raises(ValueError, match="trump_suit must be None"):
            collector.record_hand_value(
                hand=hand,
                seat=0,
                dealer_seat=1,
                contract_type="HIGH",
                trump_suit="S"
            )

    def test_seat_validation(self):
        """Test seat position validation."""
        collector = BidlessDatasetCollector("test_run", 1)
        hand = [Card("S", "A"), Card("D", "K"), Card("H", "Q"), Card("C", "J"), Card("D", "T")]

        # Valid seats
        for seat in range(4):
            collector.record_hand_value(
                hand=hand,
                seat=seat,
                dealer_seat=0,
                contract_type="suit",
                trump_suit="S"
            )

        # Invalid seats
        for invalid_seat in [-1, 4, 5]:
            with pytest.raises(ValueError, match="seat must be 0-3"):
                collector.record_hand_value(
                    hand=hand,
                    seat=invalid_seat,
                    dealer_seat=0,
                    contract_type="suit",
                    trump_suit="S"
                )

    def test_get_rows_sorted(self):
        """Test deterministic sorting of rows."""
        collector = BidlessDatasetCollector("test_run", 1)
        hand = [Card("S", "A"), Card("D", "K"), Card("H", "Q"), Card("C", "J"), Card("D", "T")]

        # Record hands for different seats
        for seat in [2, 0, 3, 1]:  # Record out of order
            collector.record_hand_value(
                hand=hand,
                seat=seat,
                dealer_seat=0,
                contract_type="suit",
                trump_suit="S"
            )

        rows = collector.get_rows_sorted()

        # Should be sorted by (hand_id, seat)
        assert len(rows) == 4
        assert rows[0]["seat"] == 0
        assert rows[1]["seat"] == 1
        assert rows[2]["seat"] == 2
        assert rows[3]["seat"] == 3

    def test_hand_features_computation(self):
        """Test hand features are computed correctly."""
        collector = BidlessDatasetCollector("test_run", 1)
        hand = [Card("S", "A"), Card("D", "K"), Card("H", "Q"), Card("C", "J"), Card("D", "T")]

        collector.record_hand_value(
            hand=hand,
            seat=0,
            dealer_seat=1,
            contract_type="suit",
            trump_suit="S"
        )

        rows = collector.get_rows_sorted()
        row = rows[0]

        assert row["hand_feature_schema_version"] == 1
        assert isinstance(row["hand_features"], dict)
        assert "hand_value" in row["hand_features"]
        assert "trump_count" in row["hand_features"]
        assert isinstance(row["hand_features"]["hand_value"], (int, float))

    def test_write_jsonl(self):
        """Test JSONL writing functionality."""
        import tempfile

        collector = BidlessDatasetCollector("test_run", 1)
        hand = [Card("S", "A"), Card("D", "K"), Card("H", "Q"), Card("C", "J"), Card("D", "T")]

        collector.record_hand_value(
            hand=hand,
            seat=0,
            dealer_seat=1,
            contract_type="suit",
            trump_suit="S"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            jsonl_path = Path(temp_dir) / "test.jsonl"
            collector.write_jsonl(str(jsonl_path))

            assert jsonl_path.exists()

            # Verify content
            with open(jsonl_path, "r") as f:
                lines = [line.strip() for line in f if line.strip()]

            assert len(lines) == 1
            row = json.loads(lines[0])

            assert row["hand_id"] == 1
            assert row["seat"] == 0
            assert row["contract_type"] == "suit"
            assert row["trump_suit"] == "S"

    def test_jsonl_deterministic_output(self):
        """Test JSONL output is deterministic (sorted keys)."""
        import tempfile

        collector = BidlessDatasetCollector("test_run", 1)
        hand = [Card("S", "A"), Card("D", "K"), Card("H", "Q"), Card("C", "J"), Card("D", "T")]

        collector.record_hand_value(
            hand=hand,
            seat=0,
            dealer_seat=1,
            contract_type="suit",
            trump_suit="S"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            jsonl_path = Path(temp_dir) / "test.jsonl"
            collector.write_jsonl(str(jsonl_path))

            with open(jsonl_path, "r") as f:
                content = f.read()

            # Run again with same input
            collector2 = BidlessDatasetCollector("test_run", 1)
            collector2.record_hand_value(
                hand=hand,
                seat=0,
                dealer_seat=1,
                contract_type="suit",
                trump_suit="S"
            )

            jsonl_path2 = Path(temp_dir) / "test2.jsonl"
            collector2.write_jsonl(str(jsonl_path2))

            with open(jsonl_path2, "r") as f:
                content2 = f.read()

            # Should be identical
            assert content == content2


class TestPyarrowOptionalDependency:
    """Test that pyarrow is truly optional for bidless dataset functionality."""

    def test_module_import_does_not_import_pyarrow(self):
        """Test that importing the bidless dataset module doesn't import pyarrow."""
        import sys

        # Record pyarrow modules before import
        pyarrow_modules_before = {
            name: module for name, module in sys.modules.items()
            if name.startswith('pyarrow')
        }

        # Force reimport by removing bidless module from sys.modules
        modules_to_remove = [
            name for name in sys.modules.keys()
            if name.startswith('bid_euchre.datasets.bidless')
        ]
        for mod in modules_to_remove:
            del sys.modules[mod]

        # Import the module fresh
        import bid_euchre.datasets.bidless  # noqa: F401

        # Check that no new pyarrow modules were imported
        pyarrow_modules_after = {
            name: module for name, module in sys.modules.items()
            if name.startswith('pyarrow')
        }

        # The pyarrow modules should be the same (none added during import)
        assert pyarrow_modules_before == pyarrow_modules_after, (
            "pyarrow should not be imported at module level. "
            f"Pyarrow modules before: {set(pyarrow_modules_before.keys())}, "
            f"after: {set(pyarrow_modules_after.keys())}"
        )

    @pytest.mark.skip(reason="Pyarrow mocking interferes with other imports in test environment")
    def test_write_parquet_fails_gracefully_without_pyarrow(self):
        """Test that write_parquet raises clear ImportError when pyarrow unavailable."""
        import tempfile

        collector = BidlessDatasetCollector("test_run", 1)
        hand = [Card('H', 'T'), Card('H', 'J'), Card('H', 'Q'), Card('H', 'K'), Card('H', 'A')]

        collector.record_hand_value(
            hand=hand,
            seat=0,
            dealer_seat=0,
            contract_type="suit",
            trump_suit="H"
        )
        collector.set_contract_context("suit", "H")

        # Try to write parquet without pyarrow available
        with patch.dict('sys.modules', {'pyarrow': None, 'pyarrow.parquet': None}):
            with patch('builtins.__import__', side_effect=ImportError("No module named 'pyarrow'")):
                with tempfile.TemporaryDirectory() as temp_dir:
                    parquet_path = Path(temp_dir) / "test.parquet"

                    with pytest.raises(ImportError) as exc_info:
                        collector.write_parquet(str(parquet_path))

                    # Verify the error message is clear and actionable
                    error_msg = str(exc_info.value)
                    assert "pyarrow is required for Parquet output" in error_msg
                    assert "pip install pyarrow" in error_msg

    @pytest.mark.skip(reason="Pyarrow mocking interferes with other imports in test environment")
    def test_write_jsonl_works_without_pyarrow(self):
        """Test that JSONL writing works even when pyarrow is unavailable."""
        import tempfile

        collector = BidlessDatasetCollector("test_run", 1)
        hand = [Card('H', 'T'), Card('H', 'J'), Card('H', 'Q'), Card('H', 'K'), Card('H', 'A')]

        collector.record_hand_value(
            hand=hand,
            seat=0,
            dealer_seat=0,
            contract_type="suit",
            trump_suit="H"
        )
        collector.set_contract_context("suit", "H")

        # Write JSONL without pyarrow available
        with patch.dict('sys.modules', {'pyarrow': None, 'pyarrow.parquet': None}):
            with patch('builtins.__import__', side_effect=ImportError("No module named 'pyarrow'")):
                with tempfile.TemporaryDirectory() as temp_dir:
                    jsonl_path = Path(temp_dir) / "test.jsonl"

                    # This should work without pyarrow
                    collector.write_jsonl(str(jsonl_path))

                    # Verify file was created and has content
                    assert jsonl_path.exists()
                    content = jsonl_path.read_text()
                    assert len(content.strip()) > 0
                    assert '"hand_id": 1' in content
