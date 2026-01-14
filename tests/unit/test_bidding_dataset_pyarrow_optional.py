"""
Unit tests for optional pyarrow dependency in bidding dataset.

These tests ensure that:
- Importing bid_euchre.datasets.bidding does not require pyarrow
- Parquet writing fails gracefully with clear error when pyarrow unavailable
- JSONL writing remains unaffected
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from bid_euchre.core.cards import Card
from bid_euchre.strategy.bidding import BidAction, BiddingObservation


class TestPyarrowOptionalDependency:
    """Test that pyarrow is truly optional for bidding dataset functionality."""

    def test_module_import_does_not_import_pyarrow(self):
        """Test that importing the bidding dataset module doesn't import pyarrow."""
        import sys

        # Record pyarrow modules before import
        pyarrow_modules_before = {
            name: module for name, module in sys.modules.items()
            if name.startswith('pyarrow')
        }

        # Force reimport by removing bidding module from sys.modules
        modules_to_remove = [
            name for name in sys.modules.keys()
            if name.startswith('bid_euchre.datasets.bidding')
        ]
        for mod in modules_to_remove:
            del sys.modules[mod]

        # Import the module fresh
        import bid_euchre.datasets.bidding  # noqa: F401

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

    def test_write_parquet_fails_gracefully_without_pyarrow(self):
        """Test that write_parquet raises clear ImportError when pyarrow unavailable."""
        from bid_euchre.datasets.bidding import BiddingDatasetCollector

        # Create a minimal collector with some test data
        collector = BiddingDatasetCollector("test_run", 1)

        # Create a fake observation and action
        obs = BiddingObservation(
            hand=[Card('9', 'H'), Card('T', 'H'), Card('J', 'H'), Card('Q', 'H'), Card('K', 'H')],
            seat=0,
            dealer_seat=0,
            current_high_bid=0,
        )
        action = BidAction.bid(3, "H")

        # Record a decision
        collector.record_decision(obs, action)

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

    def test_write_jsonl_works_without_pyarrow(self):
        """Test that JSONL writing works even when pyarrow is unavailable."""
        from bid_euchre.datasets.bidding import BiddingDatasetCollector

        # Create a minimal collector with some test data
        collector = BiddingDatasetCollector("test_run", 1)

        # Create a fake observation and action
        obs = BiddingObservation(
            hand=[Card('9', 'H'), Card('T', 'H'), Card('J', 'H'), Card('Q', 'H'), Card('K', 'H')],
            seat=0,
            dealer_seat=0,
            current_high_bid=0,
        )
        action = BidAction.bid(3, "H")

        # Record a decision
        collector.record_decision(obs, action)

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
