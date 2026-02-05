"""Unit tests for outcomes loader parquet preference logic.

Tests that load_outcomes_from_run_dir and load_features_and_outcomes_from_run_dir
prefer outcomes parquet when present and fall back to logs when not.
"""

import json
import os
import shutil
import tempfile

import pandas as pd
import pytest


class TestOutcomesLoaderPreference:
    """Test outcomes loader prefers parquet over logs."""

    @pytest.fixture
    def temp_run_dir(self):
        """Create a temporary run directory structure."""
        tmpdir = tempfile.mkdtemp(prefix="outcomes_loader_test_")
        os.makedirs(os.path.join(tmpdir, "datasets"))
        os.makedirs(os.path.join(tmpdir, "logs"))
        yield tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)

    def _create_outcomes_parquet(self, run_dir: str, rows: list) -> None:
        """Create a bidless_outcomes.parquet file."""
        df = pd.DataFrame(rows)
        df.to_parquet(os.path.join(run_dir, "datasets", "bidless_outcomes.parquet"))

    def _create_outcomes_jsonl(self, run_dir: str, hand_records: list) -> None:
        """Create a JSONL log file with hand_end events."""
        log_path = os.path.join(run_dir, "logs", "test_run.jsonl")
        with open(log_path, "w") as f:
            for record in hand_records:
                f.write(json.dumps(record) + "\n")

    def test_prefers_parquet_when_present(self, temp_run_dir):
        """Loader uses parquet when both parquet and logs exist."""
        from bid_euchre.diagnostics.notebook_data import load_outcomes_from_run_dir

        # Create parquet with specific data
        parquet_rows = [
            {
                "hand_id": 100,
                "deal_id": 0,
                "dealer_seat": 0,
                "contract_type": "suit",
                "trump_suit": "H",
                "strategy_id": "parquet_strategy",
                "matchup_id": "parquet_vs_parquet",
                "team0_strategy": "parquet_team0",
                "team1_strategy": "parquet_team1",
                "tricks_team0": 7,
                "tricks_team1": 3,
                "team0_win": 1.0,
            }
        ]
        self._create_outcomes_parquet(temp_run_dir, parquet_rows)

        # Create logs with different data
        log_records = [
            {
                "event": "hand_end",
                "deal_id": 999,
                "contract": "high",
                "trump": None,
                "strategy_id": "log_strategy",
                "t0": 5,
                "t1": 5,
            }
        ]
        self._create_outcomes_jsonl(temp_run_dir, log_records)

        # Load and verify parquet was used
        df = load_outcomes_from_run_dir(temp_run_dir)

        # Should have 4 rows (1 hand × 4 seats from parquet expansion)
        assert len(df) == 4
        # Should have parquet-specific strategy_id
        assert df["strategy_id"].iloc[0] == "parquet_strategy"
        # Should have hand_id (only in parquet)
        assert "hand_id" in df.columns
        assert df["hand_id"].iloc[0] == 100

    def test_falls_back_to_logs_when_no_parquet(self, temp_run_dir):
        """Loader uses logs when parquet doesn't exist."""
        from bid_euchre.diagnostics.notebook_data import load_outcomes_from_run_dir

        # Create only logs
        log_records = [
            {
                "event": "hand_end",
                "deal_id": 0,
                "contract": "high",
                "trump": None,
                "strategy_id": "log_strategy",
                "t0": 6,
                "t1": 4,
            }
        ]
        self._create_outcomes_jsonl(temp_run_dir, log_records)

        # Load and verify logs were used
        df = load_outcomes_from_run_dir(temp_run_dir)

        # Should have 4 rows (1 hand × 4 seats)
        assert len(df) == 4
        # Should have log-specific strategy_id
        assert df["strategy_id"].iloc[0] == "log_strategy"
        # Should NOT have hand_id (only in parquet)
        assert "hand_id" not in df.columns

    def test_prefer_parquet_false_forces_logs(self, temp_run_dir):
        """prefer_parquet=False forces log parsing even when parquet exists."""
        from bid_euchre.diagnostics.notebook_data import load_outcomes_from_run_dir

        # Create parquet
        parquet_rows = [
            {
                "hand_id": 100,
                "deal_id": 0,
                "dealer_seat": 0,
                "contract_type": "suit",
                "trump_suit": "H",
                "strategy_id": "parquet_strategy",
                "matchup_id": "parquet_vs_parquet",
                "team0_strategy": "parquet",
                "team1_strategy": "parquet",
                "tricks_team0": 7,
                "tricks_team1": 3,
                "team0_win": 1.0,
            }
        ]
        self._create_outcomes_parquet(temp_run_dir, parquet_rows)

        # Create logs with different data
        log_records = [
            {
                "event": "hand_end",
                "deal_id": 999,
                "contract": "high",
                "trump": None,
                "strategy_id": "log_strategy",
                "t0": 5,
                "t1": 5,
            }
        ]
        self._create_outcomes_jsonl(temp_run_dir, log_records)

        # Load with prefer_parquet=False
        df = load_outcomes_from_run_dir(temp_run_dir, prefer_parquet=False)

        # Should have log-specific data
        assert df["strategy_id"].iloc[0] == "log_strategy"
        # Should NOT have hand_id
        assert "hand_id" not in df.columns

    def test_parquet_expanded_to_per_seat(self, temp_run_dir):
        """Parquet data is expanded from per-hand to per-seat."""
        from bid_euchre.diagnostics.notebook_data import load_outcomes_from_run_dir

        # Create parquet with 2 hands
        parquet_rows = [
            {
                "hand_id": 0,
                "deal_id": 0,
                "dealer_seat": 0,
                "contract_type": "suit",
                "trump_suit": "C",
                "strategy_id": "greedy",
                "matchup_id": "greedy_vs_greedy",
                "team0_strategy": "greedy",
                "team1_strategy": "greedy",
                "tricks_team0": 6,
                "tricks_team1": 4,
                "team0_win": 1.0,
            },
            {
                "hand_id": 1,
                "deal_id": 1,
                "dealer_seat": 1,
                "contract_type": "high",
                "trump_suit": None,
                "strategy_id": "greedy",
                "matchup_id": "greedy_vs_greedy",
                "team0_strategy": "greedy",
                "team1_strategy": "greedy",
                "tricks_team0": 5,
                "tricks_team1": 5,
                "team0_win": 0.5,
            },
        ]
        self._create_outcomes_parquet(temp_run_dir, parquet_rows)

        df = load_outcomes_from_run_dir(temp_run_dir)

        # Should have 8 rows (2 hands × 4 seats)
        assert len(df) == 8

        # Check seat expansion for hand 0 (tricks_team0=6, tricks_team1=4)
        hand0 = df[df["hand_id"] == 0]
        assert len(hand0) == 4
        # Seats 0, 2 get team0 tricks (6)
        assert hand0[hand0["seat"] == 0]["tricks_won"].iloc[0] == 6
        assert hand0[hand0["seat"] == 2]["tricks_won"].iloc[0] == 6
        # Seats 1, 3 get team1 tricks (4)
        assert hand0[hand0["seat"] == 1]["tricks_won"].iloc[0] == 4
        assert hand0[hand0["seat"] == 3]["tricks_won"].iloc[0] == 4

    def test_error_when_no_data_source(self, temp_run_dir):
        """Error raised when neither parquet nor logs exist."""
        from bid_euchre.diagnostics.notebook_data import load_outcomes_from_run_dir

        # Don't create any data files

        with pytest.raises(FileNotFoundError):
            load_outcomes_from_run_dir(temp_run_dir)

    def test_error_when_run_dir_not_found(self):
        """Error raised when run directory doesn't exist."""
        from bid_euchre.diagnostics.notebook_data import load_outcomes_from_run_dir

        with pytest.raises(FileNotFoundError):
            load_outcomes_from_run_dir("/nonexistent/path")


class TestFeaturesAndOutcomesLoaderPreference:
    """Test features+outcomes loader prefers outcomes parquet."""

    @pytest.fixture
    def temp_run_dir(self):
        """Create a temporary run directory structure."""
        tmpdir = tempfile.mkdtemp(prefix="features_outcomes_test_")
        os.makedirs(os.path.join(tmpdir, "datasets"))
        os.makedirs(os.path.join(tmpdir, "logs"))
        yield tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)

    def _create_features_parquet(self, run_dir: str, rows: list) -> None:
        """Create a bidless.parquet features file."""
        df = pd.DataFrame(rows)
        df.to_parquet(os.path.join(run_dir, "datasets", "bidless.parquet"))

    def _create_outcomes_parquet(self, run_dir: str, rows: list) -> None:
        """Create a bidless_outcomes.parquet file."""
        df = pd.DataFrame(rows)
        df.to_parquet(os.path.join(run_dir, "datasets", "bidless_outcomes.parquet"))

    def _create_outcomes_jsonl(self, run_dir: str, hand_records: list) -> None:
        """Create a JSONL log file with hand_end events."""
        log_path = os.path.join(run_dir, "logs", "test_run.jsonl")
        with open(log_path, "w") as f:
            for record in hand_records:
                f.write(json.dumps(record) + "\n")

    def test_joins_features_with_parquet_outcomes(self, temp_run_dir):
        """Features are joined with outcomes from parquet when available."""
        from bid_euchre.diagnostics.notebook_data import (
            load_features_and_outcomes_from_run_dir,
        )

        # Create features (per-seat)
        features_rows = [
            {
                "hand_id": 0,
                "deal_id": 0,
                "seat": seat,
                "contract_type": "suit",
                "trump_suit": "H",
                "hand_cards": ["AH", "KH"],
                "hand_features": {"trump_count": 2},
                "hand_feature_schema_version": 1,
                "dealer_seat": 0,
            }
            for seat in range(4)
        ]
        self._create_features_parquet(temp_run_dir, features_rows)

        # Create outcomes parquet
        outcomes_rows = [
            {
                "hand_id": 0,
                "deal_id": 0,
                "dealer_seat": 0,
                "contract_type": "suit",
                "trump_suit": "H",
                "strategy_id": "greedy",
                "matchup_id": "greedy_vs_greedy",
                "team0_strategy": "greedy",
                "team1_strategy": "greedy",
                "tricks_team0": 7,
                "tricks_team1": 3,
                "team0_win": 1.0,
            }
        ]
        self._create_outcomes_parquet(temp_run_dir, outcomes_rows)

        df = load_features_and_outcomes_from_run_dir(temp_run_dir)

        # Should have 4 rows (joined on all 4 seats)
        assert len(df) == 4
        # Should have features
        assert "hand_cards" in df.columns
        # Should have outcomes
        assert "tricks_won" in df.columns
        # Should have parquet-specific columns
        assert "matchup_id" in df.columns
        assert "team0_win" in df.columns

    def test_falls_back_to_logs_for_outcomes(self, temp_run_dir):
        """Falls back to logs when outcomes parquet doesn't exist."""
        from bid_euchre.diagnostics.notebook_data import (
            load_features_and_outcomes_from_run_dir,
        )

        # Create features (per-seat)
        features_rows = [
            {
                "hand_id": 0,
                "deal_id": 0,
                "seat": seat,
                "contract_type": "high",
                "trump_suit": None,
                "hand_cards": ["AH", "KH"],
                "hand_features": {"trump_count": 0},
                "hand_feature_schema_version": 1,
                "dealer_seat": 0,
            }
            for seat in range(4)
        ]
        self._create_features_parquet(temp_run_dir, features_rows)

        # Create logs only (no outcomes parquet)
        log_records = [
            {
                "event": "hand_end",
                "deal_id": 0,
                "contract": "high",
                "trump": None,
                "strategy_id": "log_strategy",
                "t0": 6,
                "t1": 4,
            }
        ]
        self._create_outcomes_jsonl(temp_run_dir, log_records)

        df = load_features_and_outcomes_from_run_dir(temp_run_dir)

        # Should have 4 rows
        assert len(df) == 4
        # Should have features
        assert "hand_cards" in df.columns
        # Should have outcomes from logs
        assert "tricks_won" in df.columns
        assert df["strategy_id"].iloc[0] == "log_strategy"
        # Should NOT have parquet-specific columns
        assert "matchup_id" not in df.columns
