"""
Unit tests for optional pyarrow dependency in bidding dataset.

These tests ensure that:
- Importing bid_euchre.datasets.bidding does not require pyarrow
- Parquet writing fails gracefully with clear error when pyarrow unavailable
- JSONL writing remains unaffected
"""

import builtins
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from bid_euchre.core.cards import Card
from bid_euchre.strategy.bidding import BidAction, BiddingObservation

# Stash the real import so the selective mock can pass non-pyarrow imports through.
_real_import = builtins.__import__


def _pyarrow_blocking_import(name, *args, **kwargs):
    """Import mock that blocks only pyarrow, passes everything else through."""
    if name == "pyarrow" or name.startswith("pyarrow."):
        raise ImportError("No module named 'pyarrow' (blocked by test mock)")
    return _real_import(name, *args, **kwargs)


class TestPyarrowOptionalDependency:
    """Test that pyarrow is truly optional for bidding dataset functionality."""

    def test_module_import_does_not_require_pyarrow(self):
        """Test that importing the bidding dataset module doesn't *require* pyarrow.

        Verifies the import succeeds even when pyarrow is blocked, confirming
        that pyarrow is lazily imported (only inside write_parquet).
        """
        # Remove bidding module so it gets re-imported fresh
        modules_to_remove = [
            name
            for name in list(sys.modules.keys())
            if name.startswith("bid_euchre.datasets.bidding")
        ]
        for mod in modules_to_remove:
            del sys.modules[mod]

        # Also temporarily remove pyarrow from sys.modules and block it
        saved_pyarrow = {
            name: sys.modules.pop(name)
            for name in list(sys.modules.keys())
            if name.startswith("pyarrow")
        }
        try:
            with patch("builtins.__import__", side_effect=_pyarrow_blocking_import):
                # This should succeed even with pyarrow blocked —
                # pyarrow is only needed at write_parquet() call time
                import bid_euchre.datasets.bidding  # noqa: F401

                # Also verify we can construct a collector
                from bid_euchre.datasets.bidding import BiddingDatasetCollector

                collector = BiddingDatasetCollector("test", 1)
                assert collector is not None
        finally:
            # Restore pyarrow modules if they were previously loaded
            sys.modules.update(saved_pyarrow)

    def test_write_parquet_fails_gracefully_without_pyarrow(self):
        """Test that write_parquet raises clear ImportError when pyarrow unavailable."""
        from bid_euchre.datasets.bidding import BiddingDatasetCollector

        # Create a minimal collector with some test data
        collector = BiddingDatasetCollector("test_run", 1)

        obs = BiddingObservation(
            hand=[
                Card("9", "H"),
                Card("T", "H"),
                Card("J", "H"),
                Card("Q", "H"),
                Card("K", "H"),
            ],
            seat=0,
            dealer_seat=0,
            current_high_bid=0,
        )
        action = BidAction.bid(3, "H")
        collector.record_decision(obs, action)

        # Block pyarrow imports selectively (non-pyarrow imports still work)
        with patch.dict("sys.modules", {"pyarrow": None, "pyarrow.parquet": None}):
            with patch("builtins.__import__", side_effect=_pyarrow_blocking_import):
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

        collector = BiddingDatasetCollector("test_run", 1)

        obs = BiddingObservation(
            hand=[
                Card("9", "H"),
                Card("T", "H"),
                Card("J", "H"),
                Card("Q", "H"),
                Card("K", "H"),
            ],
            seat=0,
            dealer_seat=0,
            current_high_bid=0,
        )
        action = BidAction.bid(3, "H")
        collector.record_decision(obs, action)

        # Block pyarrow imports selectively — JSONL should still work
        with patch.dict("sys.modules", {"pyarrow": None, "pyarrow.parquet": None}):
            with patch("builtins.__import__", side_effect=_pyarrow_blocking_import):
                with tempfile.TemporaryDirectory() as temp_dir:
                    jsonl_path = Path(temp_dir) / "test.jsonl"

                    # This should work without pyarrow
                    collector.write_jsonl(str(jsonl_path))

                    # Verify file was created and has content
                    assert jsonl_path.exists()
                    content = jsonl_path.read_text()
                    assert len(content.strip()) > 0
                    assert '"hand_id": 1' in content
