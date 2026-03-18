"""Tests for the cross-rung progression table CLI script.

Covers:
- JSON loading resolution (deterministic, bare, glob fallback)
- CLI main() integration with fixture data
- Error handling for missing artifacts
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd

# The CLI script lives in scripts/internal/ and is imported via importlib
# since it is not a package.  We import it as a module.
SCRIPT_DIR = Path(__file__).resolve().parents[2] / "scripts" / "internal"
FIXTURES_DIR = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "arc_d_v2"


def _import_cli():
    """Import the CLI module dynamically from scripts/internal/."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "generate_cross_rung_tables",
        SCRIPT_DIR / "generate_cross_rung_tables.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_comparator_cis(seed, net_eppd_a, net_eppd_b):
    """Create a minimal comparator CIs fixture for testing."""
    return {
        "schema": "comparator_cis_v1",
        "seed": seed,
        "n_bootstrap": 1000,
        "ranked_order": ["model_a", "model_b"]
        if net_eppd_a >= net_eppd_b
        else ["model_b", "model_a"],
        "bidders": {
            "model_a": {
                "net_eppd": net_eppd_a,
                "bid_rate": 0.40,
                "make_rate": 0.65,
                "cvar_5": -1.5,
            },
            "model_b": {
                "net_eppd": net_eppd_b,
                "bid_rate": 0.35,
                "make_rate": 0.60,
                "cvar_5": -2.0,
            },
        },
    }


cli = _import_cli()


class TestLoadComparatorCis:
    """Tests for the _load_comparator_cis resolution logic."""

    def test_deterministic_path(self, tmp_path):
        """Loads from {rung}/comparator_cis_{mode}_{seed}.json when present."""
        rung_dir = tmp_path / "r0"
        rung_dir.mkdir()
        cis = _make_comparator_cis(42, 2.0, 1.0)
        (rung_dir / "comparator_cis_quick_42.json").write_text(json.dumps(cis))

        result = cli._load_comparator_cis(tmp_path, "r0", "quick", 42)
        assert result is not None
        assert result["seed"] == 42
        assert "model_a" in result["bidders"]

    def test_bare_name_fallback(self, tmp_path):
        """Falls back to comparator_cis.json when deterministic path missing."""
        rung_dir = tmp_path / "r0"
        rung_dir.mkdir()
        cis = _make_comparator_cis(42, 2.0, 1.0)
        (rung_dir / "comparator_cis.json").write_text(json.dumps(cis))

        result = cli._load_comparator_cis(tmp_path, "r0", "quick", 99)
        assert result is not None
        assert result["seed"] == 42

    def test_glob_fallback(self, tmp_path):
        """Falls back to glob when neither deterministic nor bare exist."""
        rung_dir = tmp_path / "r1"
        rung_dir.mkdir()
        cis = _make_comparator_cis(123, 1.5, 0.5)
        (rung_dir / "comparator_cis_full_123.json").write_text(json.dumps(cis))

        # Request mode=quick seed=42 -- neither deterministic nor bare exist
        result = cli._load_comparator_cis(tmp_path, "r1", "quick", 42)
        assert result is not None
        assert result["seed"] == 123

    def test_no_mode_or_seed(self, tmp_path):
        """When mode/seed are None, loads bare name."""
        rung_dir = tmp_path / "r0"
        rung_dir.mkdir()
        cis = _make_comparator_cis(42, 2.0, 1.0)
        (rung_dir / "comparator_cis.json").write_text(json.dumps(cis))

        result = cli._load_comparator_cis(tmp_path, "r0", None, None)
        assert result is not None

    def test_missing_rung_returns_none(self, tmp_path):
        """Returns None when the rung directory does not exist."""
        result = cli._load_comparator_cis(tmp_path, "r99", "quick", 42)
        assert result is None

    def test_empty_rung_dir_returns_none(self, tmp_path):
        """Returns None when rung dir exists but has no matching JSON."""
        rung_dir = tmp_path / "r0"
        rung_dir.mkdir()

        result = cli._load_comparator_cis(tmp_path, "r0", "quick", 42)
        assert result is None


class TestCLIMain:
    """Integration tests for the CLI main() function."""

    def test_basic_two_rung_output(self, tmp_path):
        """Produces cross_rung_progression.csv from two rungs."""
        artifacts_base = tmp_path / "artifacts"
        for rung, net_a, net_b in [("r0", 2.0, 1.0), ("r1", 2.5, 1.2)]:
            rung_dir = artifacts_base / rung
            rung_dir.mkdir(parents=True)
            cis = _make_comparator_cis(42, net_a, net_b)
            (rung_dir / "comparator_cis_quick_42.json").write_text(json.dumps(cis))

        output_dir = tmp_path / "output"

        with patch(
            "sys.argv",
            [
                "generate_cross_rung_tables.py",
                "--artifacts-base",
                str(artifacts_base),
                "--rungs",
                "r0,r1",
                "--mode",
                "quick",
                "--seed",
                "42",
                "--output-dir",
                str(output_dir),
            ],
        ):
            rc = cli.main()

        assert rc == 0
        csv_path = output_dir / "cross_rung_progression.csv"
        assert csv_path.exists()

        df = pd.read_csv(csv_path)
        assert "rung" in df.columns
        assert "model" in df.columns
        assert "rank" in df.columns
        assert "net_eppd" in df.columns
        assert set(df["rung"].unique()) == {"r0", "r1"}
        # 2 models * 2 rungs = 4 rows
        assert len(df) == 4

    def test_missing_all_rungs_returns_error(self, tmp_path):
        """Returns nonzero when no artifacts found for any rung."""
        artifacts_base = tmp_path / "empty"
        artifacts_base.mkdir()
        output_dir = tmp_path / "output"

        with patch(
            "sys.argv",
            [
                "generate_cross_rung_tables.py",
                "--artifacts-base",
                str(artifacts_base),
                "--rungs",
                "r0,r1",
                "--output-dir",
                str(output_dir),
            ],
        ):
            rc = cli.main()

        assert rc == 1
        assert not (output_dir / "cross_rung_progression.csv").exists()

    def test_partial_rungs_still_succeeds(self, tmp_path):
        """Succeeds when only some rungs have artifacts (others are skipped)."""
        artifacts_base = tmp_path / "artifacts"
        rung_dir = artifacts_base / "r0"
        rung_dir.mkdir(parents=True)
        cis = _make_comparator_cis(42, 2.0, 1.0)
        (rung_dir / "comparator_cis.json").write_text(json.dumps(cis))

        output_dir = tmp_path / "output"

        with patch(
            "sys.argv",
            [
                "generate_cross_rung_tables.py",
                "--artifacts-base",
                str(artifacts_base),
                "--rungs",
                "r0,r1,r2",
                "--output-dir",
                str(output_dir),
            ],
        ):
            rc = cli.main()

        assert rc == 0
        df = pd.read_csv(output_dir / "cross_rung_progression.csv")
        # Only r0 loaded successfully
        assert set(df["rung"].unique()) == {"r0"}

    def test_empty_rungs_arg_returns_error(self, tmp_path):
        """Returns nonzero when --rungs is empty."""
        with patch(
            "sys.argv",
            [
                "generate_cross_rung_tables.py",
                "--artifacts-base",
                str(tmp_path),
                "--rungs",
                "",
                "--output-dir",
                str(tmp_path / "out"),
            ],
        ):
            rc = cli.main()

        assert rc == 1

    def test_uses_fixture_data(self, tmp_path):
        """Loads the committed fixture comparator_cis.json via bare-name path."""
        # Create artifacts base with symlink-like structure pointing to fixture
        artifacts_base = tmp_path / "artifacts"
        rung_dir = artifacts_base / "r0"
        rung_dir.mkdir(parents=True)

        # Copy the fixture into the test artifacts directory
        fixture_cis = json.loads((FIXTURES_DIR / "comparator_cis.json").read_text())
        (rung_dir / "comparator_cis.json").write_text(json.dumps(fixture_cis))

        output_dir = tmp_path / "output"

        with patch(
            "sys.argv",
            [
                "generate_cross_rung_tables.py",
                "--artifacts-base",
                str(artifacts_base),
                "--rungs",
                "r0",
                "--output-dir",
                str(output_dir),
            ],
        ):
            rc = cli.main()

        assert rc == 0
        df = pd.read_csv(output_dir / "cross_rung_progression.csv")
        # Fixture has 3 bidders
        assert len(df) == 3
        assert set(df["model"].unique()) == {
            "gbt_av",
            "selected_ols_av",
            "modeloespecifico",
        }
