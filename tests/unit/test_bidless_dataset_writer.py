"""
Unit tests for BidlessDatasetWriter streaming functionality.

Tests the memory-safe streaming writer that replaced in-memory accumulation
of bidless dataset rows.
"""

import json
import os
import tempfile

import pyarrow.parquet as pq
import pytest

from bid_euchre.core.cards import Card
from bid_euchre.datasets.bidless import BidlessDatasetCollector, BidlessDatasetWriter


def make_test_hand() -> list[Card]:
    """Create a simple 10-card test hand."""
    return [
        Card("S", "A"), Card("S", "K"), Card("H", "A"), Card("H", "K"), Card("H", "Q"),
        Card("D", "A"), Card("D", "K"), Card("C", "A"), Card("C", "K"), Card("C", "Q"),
    ]


def make_rows_for_hand(run_id: str, hand_id: int, contract_type: str, trump_suit: str | None) -> list[dict]:
    """Create 4 rows (one per seat) for a single hand using BidlessDatasetCollector."""
    collector = BidlessDatasetCollector(run_id, hand_id)
    hand = make_test_hand()
    for seat in range(4):
        collector.record_hand_value(
            hand=hand,
            seat=seat,
            dealer_seat=0,
            contract_type=contract_type,
            trump_suit=trump_suit,
            deal_id=hand_id % 100,
        )
    return collector.get_rows_sorted()


class TestBidlessDatasetWriter:
    """Tests for the streaming BidlessDatasetWriter."""

    def test_writer_two_hands(self):
        """Write two hands (8 rows) and verify output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            run_id = "test_run_123"
            writer = BidlessDatasetWriter(
                run_dir=temp_dir,
                run_id=run_id,
                format="parquet",
                flush_rows=100,  # Don't flush early
            )

            # Write two hands (8 rows total)
            rows_hand1 = make_rows_for_hand(run_id, hand_id=0, contract_type="suit", trump_suit="H")
            rows_hand2 = make_rows_for_hand(run_id, hand_id=1, contract_type="suit", trump_suit="S")
            writer.append_rows(rows_hand1)
            writer.append_rows(rows_hand2)

            primary_path = writer.finalize()

            # Verify parquet file
            assert os.path.isfile(primary_path)
            assert primary_path.endswith("bidless.parquet")
            table = pq.read_table(primary_path)
            assert len(table) == 8

            # Verify JSONL debug file exists
            jsonl_path = os.path.join(temp_dir, "datasets", "bidless.jsonl")
            assert os.path.isfile(jsonl_path)
            with open(jsonl_path) as f:
                lines = [line.strip() for line in f if line.strip()]
            assert len(lines) == 8

            # Verify metadata
            meta_path = os.path.join(temp_dir, "datasets", "bidless_meta.json")
            assert os.path.isfile(meta_path)
            with open(meta_path) as f:
                meta = json.load(f)
            assert meta["row_count"] == 8
            assert meta["run_id"] == run_id

            # Verify required columns
            df = table.to_pandas()
            required_cols = ["hand_id", "seat", "contract_type", "trump_suit", "hand_cards", "hand_features"]
            for col in required_cols:
                assert col in df.columns, f"Missing required column: {col}"

            # Verify ordering by (hand_id, seat)
            assert list(df["hand_id"]) == [0, 0, 0, 0, 1, 1, 1, 1]
            assert list(df["seat"]) == [0, 1, 2, 3, 0, 1, 2, 3]

    def test_null_trump_then_suit_rows(self):
        """
        Schema promotion test: write high rows (trump_suit=None) first, then suit rows.

        This tests the critical schema promotion logic where the first batch has all-null
        trump_suit values. Without promotion, pyarrow would infer a null type and fail
        when string values appear later.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            run_id = "test_schema_promotion"
            writer = BidlessDatasetWriter(
                run_dir=temp_dir,
                run_id=run_id,
                format="parquet",
                flush_rows=5,  # Force early flush after first hand
            )

            # Write high contract rows first (trump_suit=None for all)
            rows_high = make_rows_for_hand(run_id, hand_id=0, contract_type="high", trump_suit=None)
            writer.append_rows(rows_high)  # 4 rows

            # Add one more row to trigger flush (5 rows total)
            extra_high = make_rows_for_hand(run_id, hand_id=1, contract_type="low", trump_suit=None)
            writer.append_rows(extra_high[:1])  # Just 1 row to hit flush_rows=5

            # Now write suit contract rows (trump_suit="H") - should not fail
            rows_suit = make_rows_for_hand(run_id, hand_id=2, contract_type="suit", trump_suit="H")
            writer.append_rows(rows_suit)

            # Finalize should succeed
            primary_path = writer.finalize()

            # Verify parquet file is readable
            table = pq.read_table(primary_path)
            assert len(table) == 9  # 4 + 1 + 4

            # Verify trump_suit column has correct values
            df = table.to_pandas()
            # First 5 rows have null trump_suit
            assert df["trump_suit"].iloc[:5].isna().all()
            # Last 4 rows have "H" trump_suit
            assert (df["trump_suit"].iloc[5:] == "H").all()

    def test_jsonl_format_no_run_id(self):
        """Verify jsonl primary format doesn't inject run_id into rows."""
        with tempfile.TemporaryDirectory() as temp_dir:
            run_id = "test_jsonl_format"
            writer = BidlessDatasetWriter(
                run_dir=temp_dir,
                run_id=run_id,
                format="jsonl",  # Primary is JSONL
                flush_rows=100,
            )

            rows = make_rows_for_hand(run_id, hand_id=0, contract_type="suit", trump_suit="H")
            writer.append_rows(rows)
            primary_path = writer.finalize()

            # Verify JSONL file exists
            assert primary_path.endswith("bidless.jsonl")
            assert os.path.isfile(primary_path)

            # Verify rows do NOT have run_id injected
            with open(primary_path) as f:
                lines = [json.loads(line) for line in f if line.strip()]

            assert len(lines) == 4
            for row in lines:
                assert "run_id" not in row, "run_id should not be injected for jsonl format"

            # Verify no parquet file created
            parquet_path = os.path.join(temp_dir, "datasets", "bidless.parquet")
            assert not os.path.exists(parquet_path), "Parquet should not be created for jsonl format"

    def test_parquet_format_debug_jsonl_has_run_id(self):
        """Verify parquet primary format writes debug JSONL with run_id injected."""
        with tempfile.TemporaryDirectory() as temp_dir:
            run_id = "test_parquet_debug_jsonl"
            writer = BidlessDatasetWriter(
                run_dir=temp_dir,
                run_id=run_id,
                format="parquet",  # Primary is parquet
                flush_rows=100,
            )

            rows = make_rows_for_hand(run_id, hand_id=0, contract_type="suit", trump_suit="S")
            writer.append_rows(rows)
            writer.finalize()

            # Verify debug JSONL has run_id injected
            jsonl_path = os.path.join(temp_dir, "datasets", "bidless.jsonl")
            with open(jsonl_path) as f:
                lines = [json.loads(line) for line in f if line.strip()]

            assert len(lines) == 4
            for row in lines:
                assert row.get("run_id") == run_id, "Debug JSONL should have run_id injected"

    def test_finalize_twice_raises(self):
        """Calling finalize() twice should raise RuntimeError."""
        with tempfile.TemporaryDirectory() as temp_dir:
            writer = BidlessDatasetWriter(
                run_dir=temp_dir,
                run_id="test",
                format="parquet",
            )
            writer.finalize()

            with pytest.raises(RuntimeError, match="finalize.*already been called"):
                writer.finalize()

    def test_append_after_finalize_raises(self):
        """Appending rows after finalize() should raise RuntimeError."""
        with tempfile.TemporaryDirectory() as temp_dir:
            writer = BidlessDatasetWriter(
                run_dir=temp_dir,
                run_id="test",
                format="parquet",
            )
            writer.finalize()

            with pytest.raises(RuntimeError, match="Cannot append.*finalize"):
                writer.append_rows([{"hand_id": 0, "seat": 0}])

    def test_invalid_format_raises(self):
        """Invalid format should raise ValueError."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ValueError, match="format must be"):
                BidlessDatasetWriter(
                    run_dir=temp_dir,
                    run_id="test",
                    format="csv",  # Invalid
                )

    def test_empty_dataset(self):
        """Finalizing without writing any rows should produce valid (empty) output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            writer = BidlessDatasetWriter(
                run_dir=temp_dir,
                run_id="empty_test",
                format="jsonl",
            )
            primary_path = writer.finalize()

            # JSONL file should exist but be empty
            assert os.path.isfile(primary_path)
            with open(primary_path) as f:
                content = f.read()
            assert content == ""

            # Metadata should show 0 rows
            meta_path = os.path.join(temp_dir, "datasets", "bidless_meta.json")
            with open(meta_path) as f:
                meta = json.load(f)
            assert meta["row_count"] == 0

    def test_jsonl_flush_before_finalize(self):
        """Verify jsonl format flushes to disk before finalize() is called.

        This tests the memory safety fix: format="jsonl" should flush rows to disk
        when buffer exceeds flush_rows threshold, not buffer indefinitely until finalize().
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            run_id = "test_jsonl_flush"
            writer = BidlessDatasetWriter(
                run_dir=temp_dir,
                run_id=run_id,
                format="jsonl",
                flush_rows=5,  # Flush after 5 rows
            )

            # Write 2 hands (8 rows total) - should trigger flush after 5
            rows_hand1 = make_rows_for_hand(run_id, hand_id=0, contract_type="suit", trump_suit="H")
            rows_hand2 = make_rows_for_hand(run_id, hand_id=1, contract_type="suit", trump_suit="S")
            writer.append_rows(rows_hand1)  # 4 rows, no flush yet
            writer.append_rows(rows_hand2)  # 8 rows total, flush triggered

            # BEFORE finalize: verify file exists and has at least 5 rows
            jsonl_path = os.path.join(temp_dir, "datasets", "bidless.jsonl")
            assert os.path.isfile(jsonl_path), "JSONL file should exist before finalize()"

            with open(jsonl_path) as f:
                lines_before = [line.strip() for line in f if line.strip()]
            assert len(lines_before) >= 5, (
                f"Expected at least 5 flushed rows before finalize(), got {len(lines_before)}"
            )

            # Finalize and verify all 8 rows are present
            primary_path = writer.finalize()
            with open(primary_path) as f:
                lines_after = [line.strip() for line in f if line.strip()]
            assert len(lines_after) == 8, f"Expected 8 total rows after finalize(), got {len(lines_after)}"

            # Verify ordering is (hand_id, seat)
            parsed_rows = [json.loads(line) for line in lines_after]
            assert [r["hand_id"] for r in parsed_rows] == [0, 0, 0, 0, 1, 1, 1, 1]
            assert [r["seat"] for r in parsed_rows] == [0, 1, 2, 3, 0, 1, 2, 3]
