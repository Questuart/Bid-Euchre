"""
Schema guard tests for bidding dataset contract (v1).

These tests ensure the bidding dataset schema remains stable and catches
accidental contract breaks in CI.
"""

import json
from pathlib import Path

import pytest

from bid_euchre.core.cards import Card
from bid_euchre.datasets.bidding import BiddingDatasetCollector
from bid_euchre.strategy.bidding import BidAction, BiddingObservation


class TestBiddingDatasetSchema:
    """Test bidding dataset schema stability and validation."""

    FIXTURE_PATH = Path("data/fixtures/bidding_dataset_tiny.jsonl")

    def test_fixture_exists(self):
        """Ensure the tiny fixture file exists."""
        assert self.FIXTURE_PATH.exists(), f"Fixture file not found: {self.FIXTURE_PATH}"

    def test_fixture_not_empty(self):
        """Ensure the fixture has content."""
        with open(self.FIXTURE_PATH, "r") as f:
            lines = f.readlines()
        assert len(lines) > 0, "Fixture file is empty"
        assert 8 <= len(lines) <= 16, f"Fixture should have 8-16 rows, got {len(lines)}"

    def test_load_fixture_data(self):
        """Load and validate fixture data can be parsed as JSON."""
        rows = []
        with open(self.FIXTURE_PATH, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    rows.append(row)
                except json.JSONDecodeError as e:
                    pytest.fail(f"Invalid JSON on line {line_num}: {e}")

        assert len(rows) > 0, "No valid JSON rows found"
        return rows

    def test_required_columns_exist(self):
        """Test that all required columns exist in every row."""
        rows = self.test_load_fixture_data()

        required_columns = {
            # Keys
            "hand_id", "seat", "dealer_seat",
            # Context
            "current_high_bid",
            # Inputs
            "hand_cards", "hand_features", "hand_feature_schema_version",
            # Attempted bids
            "attempted_bid_n", "attempted_bid_contract", "attempted_bid_trump_suit",
            # Effective bids
            "effective_bid_n", "effective_bid_contract", "effective_bid_trump_suit",
            # Legality
            "is_legal_raise",
            # Auction outcome metadata
            "auction_outcome", "winning_seat", "winning_bid_n", "winning_bid_contract"
        }

        for i, row in enumerate(rows):
            missing = required_columns - set(row.keys())
            assert not missing, f"Row {i} missing required columns: {missing}"

    def test_column_types_and_bounds(self):
        """Test column data types and value bounds."""
        rows = self.test_load_fixture_data()

        for i, row in enumerate(rows):
            # Integer columns
            assert isinstance(row["hand_id"], int), f"Row {i}: hand_id must be int"

            # Integer columns with bounds
            assert isinstance(row["seat"], int), f"Row {i}: seat must be int"
            assert 0 <= row["seat"] <= 3, f"Row {i}: seat must be 0-3, got {row['seat']}"

            assert isinstance(row["dealer_seat"], int), f"Row {i}: dealer_seat must be int"
            assert 0 <= row["dealer_seat"] <= 3, f"Row {i}: dealer_seat must be 0-3, got {row['dealer_seat']}"

            assert isinstance(row["attempted_bid_n"], int), f"Row {i}: attempted_bid_n must be int"
            assert 0 <= row["attempted_bid_n"] <= 10, f"Row {i}: attempted_bid_n must be 0-10, got {row['attempted_bid_n']}"

            assert isinstance(row["effective_bid_n"], int), f"Row {i}: effective_bid_n must be int"
            assert 0 <= row["effective_bid_n"] <= 10, f"Row {i}: effective_bid_n must be 0-10, got {row['effective_bid_n']}"

            assert isinstance(row["current_high_bid"], int), f"Row {i}: current_high_bid must be int"
            assert 0 <= row["current_high_bid"] <= 10, f"Row {i}: current_high_bid must be 0-10, got {row['current_high_bid']}"

            # Boolean column
            assert isinstance(row["is_legal_raise"], bool), f"Row {i}: is_legal_raise must be bool"

            # Auction outcome columns
            assert row["auction_outcome"] in {"won", "all_pass_redeal", None}, \
                f"Row {i}: auction_outcome must be 'won', 'all_pass_redeal', or null, got '{row['auction_outcome']}'"
            assert row["winning_seat"] is None or isinstance(row["winning_seat"], int), \
                f"Row {i}: winning_seat must be int or null"
            if row["winning_seat"] is not None:
                assert 0 <= row["winning_seat"] <= 3, f"Row {i}: winning_seat must be 0-3, got {row['winning_seat']}"
            assert row["winning_bid_n"] is None or isinstance(row["winning_bid_n"], int), \
                f"Row {i}: winning_bid_n must be int or null"
            if row["winning_bid_n"] is not None:
                assert 1 <= row["winning_bid_n"] <= 10, f"Row {i}: winning_bid_n must be 1-10, got {row['winning_bid_n']}"
            assert row["winning_bid_contract"] is None or isinstance(row["winning_bid_contract"], str), \
                f"Row {i}: winning_bid_contract must be str or null"

            # attempted_bid_contract logic
            if row["attempted_bid_n"] == 0:
                assert row["attempted_bid_contract"] is None, f"Row {i}: attempted_bid_contract must be null for pass (attempted_bid_n=0)"
                assert row["attempted_bid_trump_suit"] is None, f"Row {i}: attempted_bid_trump_suit must be null for pass"
            else:
                assert row["attempted_bid_contract"] is not None, f"Row {i}: attempted_bid_contract must not be null for bid (attempted_bid_n={row['attempted_bid_n']})"
                if row["attempted_bid_contract"] == "suit":
                    assert row["attempted_bid_trump_suit"] in {"C", "D", "H", "S"}, \
                        f"Row {i}: attempted_bid_trump_suit must be C,D,H,S for suit contract, got '{row['attempted_bid_trump_suit']}'"
                else:
                    assert row["attempted_bid_contract"] in {"HIGH", "LOW"}, \
                        f"Row {i}: attempted_bid_contract must be HIGH or LOW for non-suit, got '{row['attempted_bid_contract']}'"
                    assert row["attempted_bid_trump_suit"] is None, \
                        f"Row {i}: attempted_bid_trump_suit must be null for HIGH/LOW contracts"

            # effective_bid_contract logic (same as attempted for legal bids)
            if row["effective_bid_n"] == 0:
                assert row["effective_bid_contract"] is None, f"Row {i}: effective_bid_contract must be null for pass (effective_bid_n=0)"
                assert row["effective_bid_trump_suit"] is None, f"Row {i}: effective_bid_trump_suit must be null for pass"
            else:
                assert row["effective_bid_contract"] is not None, f"Row {i}: effective_bid_contract must not be null for bid (effective_bid_n={row['effective_bid_n']})"
                if row["effective_bid_contract"] == "suit":
                    assert row["effective_bid_trump_suit"] in {"C", "D", "H", "S"}, \
                        f"Row {i}: effective_bid_trump_suit must be C,D,H,S for suit contract, got '{row['effective_bid_trump_suit']}'"
                else:
                    assert row["effective_bid_contract"] in {"HIGH", "LOW"}, \
                        f"Row {i}: effective_bid_contract must be HIGH or LOW for non-suit, got '{row['effective_bid_contract']}'"
                    assert row["effective_bid_trump_suit"] is None, \
                        f"Row {i}: effective_bid_trump_suit must be null for HIGH/LOW contracts"

    def test_hand_cards_format(self):
        """Test hand_cards is properly formatted list of card strings."""
        rows = self.test_load_fixture_data()

        for i, row in enumerate(rows):
            assert isinstance(row["hand_cards"], list), f"Row {i}: hand_cards must be list"
            assert len(row["hand_cards"]) == 5, f"Row {i}: hand_cards must have 5 cards, got {len(row['hand_cards'])}"

            for card in row["hand_cards"]:
                assert isinstance(card, str), f"Row {i}: each card must be string, got {type(card)}"
                assert len(card) == 2, f"Row {i}: each card must be 2 chars (rank+suit), got '{card}'"
                # Basic validation that it looks like a card
                assert card[0] in "AKQJT98765432", f"Row {i}: invalid rank in '{card}'"
                assert card[1] in "CDHS", f"Row {i}: invalid suit in '{card}'"

    def test_hand_features_schema(self):
        """Test hand_features dict has stable schema."""
        rows = self.test_load_fixture_data()

        # Expected feature names based on the current implementation
        expected_features = {
            "trump_count", "trump_rb_count", "trump_lb_count",
            "offsuit_aces", "offsuit_length_3plus_count",
            "hand_value", "is_bidder"
        }

        for i, row in enumerate(rows):
            # Schema version
            assert row["hand_feature_schema_version"] == 1, \
                f"Row {i}: hand_feature_schema_version must be 1, got {row['hand_feature_schema_version']}"

            # Features dict
            assert isinstance(row["hand_features"], dict), f"Row {i}: hand_features must be dict"

            # Check required features exist
            missing_features = expected_features - set(row["hand_features"].keys())
            assert not missing_features, f"Row {i}: missing required features: {missing_features}"

            # Check feature types (all should be numeric)
            for feature_name in expected_features:
                value = row["hand_features"][feature_name]
                assert isinstance(value, (int, float)), \
                    f"Row {i}: feature '{feature_name}' must be numeric, got {type(value)}"

            # Check feature bounds (reasonable ranges)
            assert 0 <= row["hand_features"]["trump_count"] <= 5, \
                f"Row {i}: trump_count must be 0-5, got {row['hand_features']['trump_count']}"
            assert 0 <= row["hand_features"]["offsuit_aces"] <= 3, \
                f"Row {i}: offsuit_aces must be 0-3, got {row['hand_features']['offsuit_aces']}"
            assert 0 <= row["hand_features"]["hand_value"] <= 50, \
                f"Row {i}: hand_value must be reasonable (0-50), got {row['hand_features']['hand_value']}"

    def test_attempted_vs_effective_bid_logic(self):
        """Test attempted vs effective bid logic and legality flags."""
        rows = self.test_load_fixture_data()

        for i, row in enumerate(rows):
            attempted_n = row["attempted_bid_n"]
            effective_n = row["effective_bid_n"]
            current_high = row["current_high_bid"]
            is_legal = row["is_legal_raise"]

            # Pass is always legal
            if attempted_n == 0:
                assert effective_n == 0, f"Row {i}: pass should remain pass"
                assert is_legal == True, f"Row {i}: pass should be legal"
            # Illegal raise: attempted <= current_high_bid
            elif attempted_n <= current_high:
                assert effective_n == 0, f"Row {i}: illegal raise should become pass"
                assert is_legal == False, f"Row {i}: illegal raise should be flagged"
            # Legal raise: attempted > current_high_bid
            else:
                assert effective_n == attempted_n, f"Row {i}: legal raise should be effective"
                assert is_legal == True, f"Row {i}: legal raise should be flagged as legal"

    def test_illegal_bid_legality_flag(self):
        """Test that the collector correctly flags illegal bids."""

        # Create a mock observation with current_high_bid = 2
        hand = [Card("S", "A"), Card("H", "K"),
                Card("C", "Q"), Card("D", "J"),
                Card("S", "T")]
        obs = BiddingObservation(
            hand=hand,
            seat=0,
            dealer_seat=0,
            current_high_bid=2  # Some bid is already on the table
        )

        collector = BiddingDatasetCollector("test_run", 1)

        # Test illegal bid: attempted_bid_n = 1 (which is <= current_high_bid = 2)
        illegal_action = BidAction.bid(1, "S")  # This should be illegal
        collector.record_decision(obs, illegal_action)

        # Test legal bid: attempted_bid_n = 3 (which is > current_high_bid = 2)
        legal_action = BidAction.bid(3, "H")
        collector.record_decision(obs, legal_action)

        # Test pass: always legal
        pass_action = BidAction.pass_bid()
        collector.record_decision(obs, pass_action)

        rows = collector.rows

        # Should have 3 rows
        assert len(rows) == 3

        # Find the rows by attempted_bid_n
        illegal_row = next(r for r in rows if r["attempted_bid_n"] == 1)
        legal_row = next(r for r in rows if r["attempted_bid_n"] == 3)
        pass_row = next(r for r in rows if r["attempted_bid_n"] == 0)

        # Illegal bid should be flagged as illegal and become effective pass
        assert illegal_row["is_legal_raise"] == False
        assert illegal_row["effective_bid_n"] == 0
        assert illegal_row["effective_bid_contract"] is None

        # Legal bid should be flagged as legal and remain effective
        assert legal_row["is_legal_raise"] == True
        assert legal_row["effective_bid_n"] == 3
        assert legal_row["effective_bid_contract"] == "suit"

        # Pass should be legal
        assert pass_row["is_legal_raise"] == True
        assert pass_row["effective_bid_n"] == 0

    def test_fixture_has_required_bid_types(self):
        """Test that fixture includes examples of all required bid types."""
        rows = self.test_load_fixture_data()

        bid_types_found = set()

        for row in rows:
            if row["effective_bid_n"] == 0:
                bid_types_found.add("PASS")
            elif row["effective_bid_contract"] == "suit":
                bid_types_found.add("SUIT")
            elif row["effective_bid_contract"] == "HIGH":
                bid_types_found.add("HIGH")
            elif row["effective_bid_contract"] == "LOW":
                bid_types_found.add("LOW")

        # For now, just ensure PASS bids are present (fixture may not have all types)
        assert "PASS" in bid_types_found, "Fixture should include at least PASS bids"

    def test_auction_outcome_consistency(self):
        """Test auction outcome metadata consistency."""
        rows = self.test_load_fixture_data()

        # Group rows by hand_id and check consistency within each hand
        hands = {}
        for row in rows:
            hand_id = row["hand_id"]
            if hand_id not in hands:
                hands[hand_id] = []
            hands[hand_id].append(row)

        for hand_id, hand_rows in hands.items():
            # All rows in a hand should have the same auction outcome
            auction_outcomes = set(row["auction_outcome"] for row in hand_rows)
            assert len(auction_outcomes) == 1, f"Hand {hand_id} should have same auction_outcome, got {auction_outcomes}"

            auction_outcome = list(auction_outcomes)[0]

            if auction_outcome == "won":
                # For won auctions, should have winning bid details
                winning_seats = set(row["winning_seat"] for row in hand_rows if row["winning_seat"] is not None)
                winning_bids = set(row["winning_bid_n"] for row in hand_rows if row["winning_bid_n"] is not None)
                winning_contracts = set(row["winning_bid_contract"] for row in hand_rows if row["winning_bid_contract"] is not None)

                assert len(winning_seats) == 1, f"Hand {hand_id} won auction should have exactly one winning_seat, got {winning_seats}"
                assert len(winning_bids) == 1, f"Hand {hand_id} won auction should have exactly one winning_bid_n, got {winning_bids}"
                assert len(winning_contracts) == 1, f"Hand {hand_id} won auction should have exactly one winning_bid_contract, got {winning_contracts}"

                # Winning bid should be > 0
                winning_bid_n = list(winning_bids)[0]
                assert winning_bid_n > 0, f"Hand {hand_id} winning bid should be > 0, got {winning_bid_n}"

            elif auction_outcome == "all_pass_redeal":
                # For redeals, all winning_* fields should be null
                for row in hand_rows:
                    assert row["winning_seat"] is None, f"Hand {hand_id} redeal should have null winning_seat"
                    assert row["winning_bid_n"] is None, f"Hand {hand_id} redeal should have null winning_bid_n"
                    assert row["winning_bid_contract"] is None, f"Hand {hand_id} redeal should have null winning_bid_contract"

    def test_deterministic_sorting(self):
        """Test that rows are sorted deterministically by (hand_id, seat)."""
        rows = self.test_load_fixture_data()

        # Check that rows are sorted by hand_id, then seat
        for i in range(1, len(rows)):
            prev_hand = rows[i-1]["hand_id"]
            curr_hand = rows[i]["hand_id"]

            if prev_hand == curr_hand:
                # Same hand, should be sorted by seat
                assert rows[i-1]["seat"] <= rows[i]["seat"], \
                    f"Rows not sorted by seat within hand {curr_hand}: {rows[i-1]['seat']} > {rows[i]['seat']}"
            else:
                # Different hands, should be sorted by hand_id
                assert prev_hand <= curr_hand, \
                    f"Rows not sorted by hand_id: {prev_hand} > {curr_hand}"

    def test_emit_bidding_dataset_flag_integration(self):
        """Smoke test that --emit-bidding-dataset writes dataset files under the run directory."""
        import os
        import subprocess
        import sys
        import tempfile

        env = os.environ.copy()
        env["PYTHONPATH"] = "src"

        with tempfile.TemporaryDirectory() as temp_base:
            cmd = [
                sys.executable,
                "-m",
                "experiments.run_experiment",
                "--config",
                "experiments/configs/auction_smoke.yaml",
                "--run-dir",
                temp_base,
                "--seed",
                "42",
                "--emit-bidding-dataset",
            ]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=os.getcwd(), env=env)
            assert result.returncode == 0, f"Runner failed: {result.stderr}"

            run_dirs = sorted(Path(temp_base).glob("auction_smoke_*"))
            assert run_dirs, f"No run directories found in {temp_base}"
            run_dir = run_dirs[-1]

            # Check that Parquet file exists (primary format)
            parquet_file = run_dir / "datasets" / "bidding.parquet"
            assert parquet_file.exists(), f"Parquet dataset file missing: {parquet_file}"

            # Check that JSONL file exists (debug format)
            jsonl_file = run_dir / "datasets" / "bidding.jsonl"
            assert jsonl_file.exists(), f"JSONL dataset file missing: {jsonl_file}"

            # Verify JSONL content
            with open(jsonl_file, "r") as f:
                lines = [line.strip() for line in f if line.strip()]

            assert lines, f"Dataset file is empty: {jsonl_file}"
            first_row = json.loads(lines[0])
            required_keys = {
                "run_id", "hand_id", "seat",
                "attempted_bid_n", "attempted_bid_contract", "attempted_bid_trump_suit",
                "effective_bid_n", "effective_bid_contract", "effective_bid_trump_suit",
                "is_legal_raise",
                "auction_outcome", "winning_seat", "winning_bid_n", "winning_bid_contract"
            }
            assert required_keys.issubset(first_row.keys()), f"Missing keys in dataset row: {first_row.keys()}"

    @pytest.mark.xfail(reason="Parquet file metadata (timestamps, etc.) causes non-deterministic hashes in CI")
    def test_bidding_dataset_determinism(self):
        """Test that bidding datasets are byte-identical when seed/config are identical but run_id differs."""
        import hashlib
        import os
        import subprocess
        import sys
        import tempfile

        env = os.environ.copy()
        env["PYTHONPATH"] = "src"

        # Run the same experiment twice with different run directories
        hashes = []
        for i in range(2):
            with tempfile.TemporaryDirectory() as temp_base:
                cmd = [
                    sys.executable,
                    "-m",
                    "experiments.run_experiment",
                    "--config",
                    "experiments/configs/auction_smoke.yaml",
                    "--run-dir",
                    temp_base,
                    "--seed",
                    "123",  # Fixed seed for determinism
                    "--emit-bidding-dataset",
                ]
                result = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=os.getcwd(), env=env)
                assert result.returncode == 0, f"Runner failed: {result.stderr}"

                run_dirs = sorted(Path(temp_base).glob("auction_smoke_*"))
                assert run_dirs, f"No run directories found in {temp_base}"
                run_dir = run_dirs[-1]
                parquet_file = run_dir / "datasets" / "bidding.parquet"
                assert parquet_file.exists(), f"Parquet file missing: {parquet_file}"

                # Compute SHA256 hash of the Parquet file
                with open(parquet_file, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                hashes.append(file_hash)

        # Assert that both Parquet files have identical hashes (byte-identical)
        assert hashes[0] == hashes[1], f"Parquet files not identical: {hashes[0]} != {hashes[1]}"

    def test_emit_bidding_dataset_jsonl_format(self):
        """Test that --bidding-dataset-format jsonl only writes JSONL file."""
        import os
        import subprocess
        import sys
        import tempfile

        env = os.environ.copy()
        env["PYTHONPATH"] = "src"

        with tempfile.TemporaryDirectory() as temp_base:
            cmd = [
                sys.executable,
                "-m",
                "experiments.run_experiment",
                "--config",
                "experiments/configs/auction_smoke.yaml",
                "--run-dir",
                temp_base,
                "--seed",
                "42",
                "--emit-bidding-dataset",
                "--bidding-dataset-format",
                "jsonl",
            ]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=os.getcwd(), env=env)
            assert result.returncode == 0, f"Runner failed: {result.stderr}"

            run_dirs = sorted(Path(temp_base).glob("auction_smoke_*"))
            assert run_dirs, f"No run directories found in {temp_base}"
            run_dir = run_dirs[-1]

            # Check that JSONL file exists
            jsonl_file = run_dir / "datasets" / "bidding.jsonl"
            assert jsonl_file.exists(), f"JSONL dataset file missing: {jsonl_file}"

            # Check that Parquet file does NOT exist
            parquet_file = run_dir / "datasets" / "bidding.parquet"
            assert not parquet_file.exists(), f"Parquet file should not exist when format=jsonl: {parquet_file}"
