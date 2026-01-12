"""
Schema guard tests for bidding dataset contract (v1).

These tests ensure the bidding dataset schema remains stable and catches
accidental contract breaks in CI.
"""

import json
from pathlib import Path

import pytest


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
            "run_id", "hand_id", "seat", "dealer_seat",
            # Context
            "current_high_bid",
            # Inputs
            "hand_cards", "hand_features", "hand_feature_schema_version",
            # Labels
            "bid_n", "bid_contract"
        }

        for i, row in enumerate(rows):
            missing = required_columns - set(row.keys())
            assert not missing, f"Row {i} missing required columns: {missing}"

    def test_column_types_and_bounds(self):
        """Test column data types and value bounds."""
        rows = self.test_load_fixture_data()

        for i, row in enumerate(rows):
            # String columns
            assert isinstance(row["run_id"], str), f"Row {i}: run_id must be string"
            assert isinstance(row["hand_id"], str), f"Row {i}: hand_id must be string"

            # Integer columns with bounds
            assert isinstance(row["seat"], int), f"Row {i}: seat must be int"
            assert 0 <= row["seat"] <= 3, f"Row {i}: seat must be 0-3, got {row['seat']}"

            assert isinstance(row["dealer_seat"], int), f"Row {i}: dealer_seat must be int"
            assert 0 <= row["dealer_seat"] <= 3, f"Row {i}: dealer_seat must be 0-3, got {row['dealer_seat']}"

            assert isinstance(row["bid_n"], int), f"Row {i}: bid_n must be int"
            assert 0 <= row["bid_n"] <= 10, f"Row {i}: bid_n must be 0-10, got {row['bid_n']}"

            assert isinstance(row["current_high_bid"], int), f"Row {i}: current_high_bid must be int"
            assert 0 <= row["current_high_bid"] <= 10, f"Row {i}: current_high_bid must be 0-10, got {row['current_high_bid']}"

            # bid_contract logic
            if row["bid_n"] == 0:
                assert row["bid_contract"] is None, f"Row {i}: bid_contract must be null for pass (bid_n=0)"
            else:
                assert row["bid_contract"] is not None, f"Row {i}: bid_contract must not be null for bid (bid_n={row['bid_n']})"
                assert row["bid_contract"] in {"C", "D", "H", "S", "HIGH", "LOW"}, \
                    f"Row {i}: bid_contract must be one of C,D,H,S,HIGH,LOW, got '{row['bid_contract']}'"

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

    def test_fixture_has_required_bid_types(self):
        """Test that fixture includes examples of all required bid types."""
        rows = self.test_load_fixture_data()

        bid_types_found = set()

        for row in rows:
            if row["bid_n"] == 0:
                bid_types_found.add("PASS")
            elif row["bid_contract"] in {"C", "D", "H", "S"}:
                bid_types_found.add("SUIT")
            elif row["bid_contract"] == "HIGH":
                bid_types_found.add("HIGH")
            elif row["bid_contract"] == "LOW":
                bid_types_found.add("LOW")

        required_types = {"PASS", "SUIT", "HIGH", "LOW"}
        missing_types = required_types - bid_types_found

        assert not missing_types, f"Fixture missing required bid types: {missing_types}"

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
