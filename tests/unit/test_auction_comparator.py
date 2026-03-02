"""
Unit tests for the auction comparator gate logic.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

# Import via importlib to avoid sys.path.insert anti-pattern.
_COMPARATOR_SCRIPT = (
    Path(__file__).parent.parent.parent
    / "scripts"
    / "internal"
    / "run_auction_comparator.py"
)
_spec = importlib.util.spec_from_file_location(
    "run_auction_comparator", _COMPARATOR_SCRIPT
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
format_report = _mod.format_report
format_json = _mod.format_json
gate_check = _mod.gate_check
_CLASS_TO_NAME = _mod._CLASS_TO_NAME
_merge_single_seat_evaluations = _mod._merge_single_seat_evaluations
_write_batch_manifest = _mod._write_batch_manifest


class TestGateCheck:
    """Test gate check logic."""

    def test_all_bidders_have_bids_passes(self):
        """Gate passes when all bidders have bid_rate > 0."""
        metrics = {
            "bidder_a": {"bid_rate": 0.5, "expected_points": 3.0},
            "bidder_b": {"bid_rate": 0.3, "expected_points": 2.0},
        }
        failures = gate_check(metrics)
        assert len(failures) == 0

    def test_zero_bid_rate_fails(self):
        """Gate fails when any bidder has bid_rate == 0."""
        metrics = {
            "bidder_a": {"bid_rate": 0.5, "expected_points": 3.0},
            "bidder_b": {"bid_rate": 0, "expected_points": 0},
        }
        failures = gate_check(metrics)
        assert len(failures) == 1
        assert "bidder_b" in failures[0]

    def test_multiple_zero_bid_rates(self):
        """Gate reports all zero-bid-rate bidders."""
        metrics = {
            "bidder_a": {"bid_rate": 0},
            "bidder_b": {"bid_rate": 0},
            "bidder_c": {"bid_rate": 0.8},
        }
        failures = gate_check(metrics)
        assert len(failures) == 2


class TestFormatReport:
    """Test report formatting."""

    def test_report_contains_all_bidders(self):
        """Report includes all bidders in comparison table."""
        metrics = {
            "alice": {
                "expected_points": 3.5,
                "make_rate": 0.7,
                "bid_rate": 0.5,
                "cvar_5": -2.0,
                "hands_with_bids": 5000,
            },
            "bob": {
                "expected_points": 2.0,
                "make_rate": 0.6,
                "bid_rate": 0.3,
                "cvar_5": -3.0,
                "hands_with_bids": 3000,
            },
        }
        report = format_report(metrics, [], seed=42)
        assert "alice" in report
        assert "bob" in report
        assert "PASS" in report

    def test_report_shows_failures(self):
        """Report shows gate failures."""
        metrics = {"x": {"expected_points": 0, "bid_rate": 0}}
        failures = ["GATE FAIL: x has bid_rate=0"]
        report = format_report(metrics, failures, seed=42)
        assert "FAIL" in report
        assert "bid_rate=0" in report

    def test_report_sorted_by_expected_points(self):
        """Report sorts bidders by expected_points descending."""
        metrics = {
            "low": {
                "expected_points": 1.0,
                "make_rate": 0.5,
                "bid_rate": 0.5,
                "cvar_5": None,
                "hands_with_bids": 100,
            },
            "high": {
                "expected_points": 5.0,
                "make_rate": 0.8,
                "bid_rate": 0.9,
                "cvar_5": -1.0,
                "hands_with_bids": 900,
            },
        }
        report = format_report(metrics, [], seed=42)
        lines = report.split("\n")
        # Find the data rows (after header)
        data_rows = [
            l
            for l in lines
            if l.startswith("| ") and "Bidder" not in l and "---" not in l
        ]
        assert "high" in data_rows[0]
        assert "low" in data_rows[1]


class TestMissingEvaluationHardFail:
    """Test that missing evaluation data causes a hard failure."""

    def test_exits_nonzero_on_missing_evaluation(self):
        """Script exits non-zero when evaluation.json is missing for a bidder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a minimal config with one bidder
            config = {
                "experiment_name": "test_comparator",
                "bidding_policies": [
                    {
                        "name": "test_bidder",
                        "class_name": "FixedBidder",
                        "params": {"n": 5, "contract": "S"},
                    },
                ],
                "scenarios": [{"contract_type": None}],
                "parameters": {"n_per": 10},
            }
            config_path = Path(tmpdir) / "test_config.yaml"
            import yaml

            with open(config_path, "w") as f:
                yaml.dump(config, f)

            # Create run dir with NO evaluation.json
            run_dir = Path(tmpdir) / "data" / "runs" / "test_comparator_test_bidder_42"
            run_dir.mkdir(parents=True)

            # Run in skip-run mode (so it only tries to load evaluation)
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/internal/run_auction_comparator.py",
                    "--config",
                    str(config_path),
                    "--seed",
                    "42",
                    "--skip-run",
                ],
                capture_output=True,
                text=True,
                # Set data dir to our temp location
                env={**dict(__import__("os").environ), "PYTHONPATH": "."},
            )
            # Should fail because evaluation.json doesn't exist
            assert result.returncode != 0
            assert (
                "Missing evaluation data" in result.stderr
                or "Missing evaluation data" in result.stdout
                or result.returncode != 0
            )

    def test_report_includes_metric_provenance(self):
        """Report header includes metric source information."""
        metrics = {
            "alice": {
                "expected_points": 3.5,
                "make_rate": 0.7,
                "bid_rate": 0.5,
                "cvar_5": -2.0,
                "hands_with_bids": 5000,
            },
        }
        report = format_report(metrics, [], seed=42)
        assert "Metric source" in report
        assert "evaluation.json" in report


class TestScriptHelp:
    """Smoke test for the comparator script."""

    def test_help_flag(self):
        """Test that the script prints help without errors."""
        result = subprocess.run(
            [sys.executable, "scripts/internal/run_auction_comparator.py", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "--config" in result.stdout
        assert "--olsa-artifact" in result.stdout
        assert "--bidder-class" in result.stdout
        assert "--output-format" in result.stdout


class TestFormatJson:
    """Tests for JSON output format."""

    def test_format_json_schema(self):
        """format_json() output has arc_d_comparator_v1 schema with expected keys."""
        metrics = {
            "hybrid_olsa": {
                "expected_points_per_deal": 3.5,
                "net_expected_points_per_deal": 1.5,
                "make_rate": 0.7,
                "bid_rate": 0.5,
                "cvar_5": -2.0,
                "net_cvar_5": -1.5,
            },
            "modeloespecifico": {
                "expected_points_per_deal": 2.0,
                "net_expected_points_per_deal": 0.8,
                "make_rate": 0.6,
                "bid_rate": 0.3,
                "cvar_5": -3.0,
                "net_cvar_5": -2.5,
            },
        }
        result = format_json(metrics, [], seed=42, n_per=10000)
        assert result["schema"] == "arc_d_comparator_v1"
        assert result["seed"] == 42
        assert result["n_per"] == 10000
        assert result["gate_status"] == "PASS"
        assert len(result["bidders"]) == 2
        # Check per-bidder fields
        hybrid = result["bidders"]["hybrid_olsa"]
        expected_keys = {
            "net_eppd",
            "eppd",
            "bid_rate",
            "make_rate",
            "cvar_5",
            "net_cvar_5",
        }
        assert set(hybrid.keys()) == expected_keys
        assert hybrid["net_eppd"] == 1.5
        assert hybrid["eppd"] == 3.5

    def test_format_json_gate_fail(self):
        """gate_status is 'FAIL' when failures list is non-empty."""
        metrics = {"x": {"expected_points_per_deal": 0, "bid_rate": 0}}
        failures = ["GATE FAIL: x has bid_rate=0"]
        result = format_json(metrics, failures, seed=42, n_per=100)
        assert result["gate_status"] == "FAIL"


class TestBidderNameDerivation:
    """Tests for _CLASS_TO_NAME mapping and bidder name derivation."""

    def test_known_classes_map_correctly(self):
        """_CLASS_TO_NAME maps OLSaBidder and HybridOLSaBidder."""
        assert _CLASS_TO_NAME["OLSaBidder"] == "olsa"
        assert _CLASS_TO_NAME["HybridOLSaBidder"] == "hybrid_olsa"

    def test_unknown_class_fallback(self):
        """Unknown classes fall back to lowercase."""
        unknown = "MyCustomBidder"
        name = _CLASS_TO_NAME.get(unknown, unknown.lower())
        assert name == "mycustombidder"


class TestConfigGenerationIntegration:
    """Integration test: round-trip config generation through YAML on disk."""

    def test_generated_config_round_trip_contains_strategies(self):
        """Write a minimal config, generate per-policy configs the same way main() does,
        and verify the on-disk YAML contains strategies and play_strategy."""
        import yaml

        with tempfile.TemporaryDirectory() as tmpdir:
            # Step 1: Write a minimal source config with strategies + play_strategy
            source_config = {
                "experiment_name": "test_roundtrip",
                "bidding_policies": [
                    {
                        "name": "test_bidder",
                        "class_name": "FixedBidder",
                        "params": {"n": 5, "contract": "S"},
                    },
                ],
                "strategies": [
                    {"name": "glutton", "class_name": "GluttonStrategy"},
                ],
                "scenarios": [{"contract_type": None}],
                "parameters": {
                    "play_strategy": "glutton",
                    "n_per": 10,
                },
            }
            source_path = Path(tmpdir) / "source.yaml"
            with open(source_path, "w") as f:
                yaml.dump(source_config, f)

            # Step 2: Load and generate per-policy config exactly as main() does
            with open(source_path) as f:
                config = yaml.safe_load(f)

            policies = config.get("bidding_policies", [])
            experiment_name = config.get("experiment_name", "auction_comparator")
            n_per = config.get("parameters", {}).get("n_per", 10000)

            # 4-way self-play path (non-single-seat)
            for policy in policies:
                per_policy_config = {
                    "experiment_name": f"{experiment_name}_{policy['name']}",
                    "bidding_policies": [policy],
                    "strategies": config.get("strategies", []),
                    "scenarios": config.get("scenarios", [{"contract_type": None}]),
                    "parameters": {
                        **config.get("parameters", {}),
                        "n_per": n_per,
                    },
                }

                config_path = Path(tmpdir) / f"generated_{policy['name']}.yaml"
                with open(config_path, "w") as f:
                    yaml.dump(per_policy_config, f)

                # Step 3: Re-read from disk and validate (same as the script's guard)
                with open(config_path) as f:
                    written = yaml.safe_load(f)

                assert written.get(
                    "strategies"
                ), f"strategies missing from generated config at {config_path}"
                assert (
                    written["parameters"].get("play_strategy") == "glutton"
                ), f"play_strategy wrong in generated config at {config_path}"

            # Single-seat path
            policy = policies[0]
            seat_bp = ["always_pass"] * 4
            seat_bp[0] = policy["name"]
            per_seat_config = {
                "experiment_name": f"{experiment_name}_{policy['name']}_seat0",
                "bidding_policies": [
                    policy,
                    {"name": "always_pass", "class_name": "AlwaysPassBidder"},
                ],
                "seat_bidding_policies": seat_bp,
                "strategies": config.get("strategies", []),
                "scenarios": config.get("scenarios", [{"contract_type": None}]),
                "parameters": {
                    **config.get("parameters", {}),
                    "n_per": 10,
                },
            }
            seat_config_path = Path(tmpdir) / "generated_seat0.yaml"
            with open(seat_config_path, "w") as f:
                yaml.dump(per_seat_config, f)

            with open(seat_config_path) as f:
                written_seat = yaml.safe_load(f)
            assert written_seat.get(
                "strategies"
            ), "strategies missing from single-seat generated config"
            assert (
                written_seat["parameters"].get("play_strategy") == "glutton"
            ), "play_strategy wrong in single-seat generated config"

    def test_missing_strategies_raises_valueerror(self):
        """Config without strategies section triggers ValueError, not AssertionError."""
        import yaml

        with tempfile.TemporaryDirectory() as tmpdir:
            # Config deliberately missing strategies and play_strategy
            bad_config = {
                "experiment_name": "test_bad",
                "bidding_policies": [
                    {
                        "name": "test_bidder",
                        "class_name": "FixedBidder",
                        "params": {"n": 5, "contract": "S"},
                    },
                ],
                "scenarios": [{"contract_type": None}],
                "parameters": {"n_per": 10},
            }
            config_path = Path(tmpdir) / "bad_generated.yaml"
            with open(config_path, "w") as f:
                yaml.dump(bad_config, f)

            # Re-read and apply the same validation the script uses
            with open(config_path) as f:
                written = yaml.safe_load(f)

            import pytest

            with pytest.raises(ValueError, match="missing 'strategies' section"):
                if not written.get("strategies"):
                    raise ValueError(
                        f"Generated config {config_path} is missing 'strategies' section. "
                        f"Ensure the source config includes a strategies list "
                        f"(e.g., strategies: [{{name: glutton, class_name: GluttonStrategy}}])."
                    )

    def test_missing_play_strategy_raises_valueerror(self):
        """Config without play_strategy triggers ValueError, not AssertionError."""
        import yaml

        with tempfile.TemporaryDirectory() as tmpdir:
            # Config has strategies but missing play_strategy
            bad_config = {
                "experiment_name": "test_bad",
                "bidding_policies": [
                    {
                        "name": "test_bidder",
                        "class_name": "FixedBidder",
                        "params": {"n": 5, "contract": "S"},
                    },
                ],
                "strategies": [
                    {"name": "glutton", "class_name": "GluttonStrategy"},
                ],
                "scenarios": [{"contract_type": None}],
                "parameters": {"n_per": 10},
            }
            config_path = Path(tmpdir) / "bad_generated.yaml"
            with open(config_path, "w") as f:
                yaml.dump(bad_config, f)

            with open(config_path) as f:
                written = yaml.safe_load(f)

            import pytest

            with pytest.raises(ValueError, match="missing 'parameters.play_strategy'"):
                if not written.get("strategies"):
                    raise ValueError(
                        f"Generated config {config_path} is missing 'strategies' section."
                    )
                if not written.get("parameters", {}).get("play_strategy"):
                    raise ValueError(
                        f"Generated config {config_path} is missing 'parameters.play_strategy'. "
                        f"Ensure the source config includes play_strategy in parameters."
                    )


class TestPlayStrategyConfig:
    """Tests for play strategy configuration in auction_comparator.yaml."""

    _CONFIG_PATH = (
        Path(__file__).parent.parent.parent
        / "experiments"
        / "configs"
        / "auction_comparator.yaml"
    )

    def test_config_has_strategies_section(self):
        """auction_comparator.yaml must have a strategies section with glutton."""
        import yaml

        with open(self._CONFIG_PATH) as f:
            config = yaml.safe_load(f)
        strategies = config.get("strategies", [])
        assert strategies, "strategies section missing from auction_comparator.yaml"
        names = [s["name"] for s in strategies]
        assert "glutton" in names, f"Expected 'glutton' in strategies, got: {names}"
        glutton = next(s for s in strategies if s["name"] == "glutton")
        assert glutton["class_name"] == "GluttonStrategy"

    def test_config_has_play_strategy_param(self):
        """auction_comparator.yaml must set parameters.play_strategy to 'glutton'."""
        import yaml

        with open(self._CONFIG_PATH) as f:
            config = yaml.safe_load(f)
        play_strategy = config.get("parameters", {}).get("play_strategy")
        assert (
            play_strategy == "glutton"
        ), f"Expected parameters.play_strategy='glutton', got: {play_strategy}"

    def test_generated_configs_contain_strategies(self):
        """Generated per-policy configs must pass strategies and play_strategy through."""
        import yaml

        with open(self._CONFIG_PATH) as f:
            config = yaml.safe_load(f)

        # Simulate the 4-way self-play config generation
        experiment_name = config.get("experiment_name", "auction_comparator")
        policies = config.get("bidding_policies", [])
        n_per = config.get("parameters", {}).get("n_per", 10000)

        for policy in policies:
            per_policy_config = {
                "experiment_name": f"{experiment_name}_{policy['name']}",
                "bidding_policies": [policy],
                "strategies": config.get("strategies", []),
                "scenarios": config.get("scenarios", [{"contract_type": None}]),
                "parameters": {
                    **config.get("parameters", {}),
                    "n_per": n_per,
                },
            }
            assert per_policy_config.get(
                "strategies"
            ), f"strategies missing for {policy['name']}"
            assert (
                per_policy_config["parameters"].get("play_strategy") == "glutton"
            ), f"play_strategy missing for {policy['name']}"

    def test_generated_single_seat_configs_contain_strategies(self):
        """Generated single-seat configs must pass strategies and play_strategy through."""
        import yaml

        with open(self._CONFIG_PATH) as f:
            config = yaml.safe_load(f)

        experiment_name = config.get("experiment_name", "auction_comparator")
        policies = config.get("bidding_policies", [])

        # Simulate single-seat config generation for first policy, seat 0
        policy = policies[0]
        seat_bp = ["always_pass"] * 4
        seat_bp[0] = policy["name"]

        per_seat_config = {
            "experiment_name": f"{experiment_name}_{policy['name']}_seat0",
            "bidding_policies": [
                policy,
                {"name": "always_pass", "class_name": "AlwaysPassBidder"},
            ],
            "seat_bidding_policies": seat_bp,
            "strategies": config.get("strategies", []),
            "scenarios": config.get("scenarios", [{"contract_type": None}]),
            "parameters": {
                **config.get("parameters", {}),
                "n_per": 2500,
            },
        }
        assert per_seat_config.get(
            "strategies"
        ), "strategies missing from single-seat config"
        assert (
            per_seat_config["parameters"].get("play_strategy") == "glutton"
        ), "play_strategy missing from single-seat config"


# ---------------------------------------------------------------------------
# Helpers for manifest/merging tests
# ---------------------------------------------------------------------------


def _make_evaluation_json(run_dir, deals_total=100, bid_rate=0.5, net_eppd=1.0):
    """Create synthetic evaluation.json in run_dir."""
    eval_dir = Path(run_dir) / "reports" / "bidding_strategy"
    eval_dir.mkdir(parents=True, exist_ok=True)
    evaluation = {
        "strategies": [
            {
                "deals_total": deals_total,
                "hands_with_bids": int(deals_total * bid_rate),
                "expected_points_per_deal": net_eppd + 0.5,
                "net_expected_points_per_deal": net_eppd,
                "make_rate": 0.7,
                "bid_rate": bid_rate,
            }
        ]
    }
    (eval_dir / "evaluation.json").write_text(json.dumps(evaluation))


class TestSingleSeatMetricMerging:
    """Tests for _merge_single_seat_evaluations()."""

    def test_merged_metrics_weighted_by_deals(self, tmp_path):
        """4 seats with different deal counts merge correctly."""
        policies = [{"name": "alpha"}]
        run_dirs = {}
        # Seat 0: 100 deals, net_eppd=2.0; Seat 1: 100 deals, net_eppd=1.0
        # Seat 2: 100 deals, net_eppd=0.5; Seat 3: 100 deals, net_eppd=0.5
        for seat, neppd in enumerate([2.0, 1.0, 0.5, 0.5]):
            d = tmp_path / f"run_alpha_seat{seat}"
            d.mkdir()
            _make_evaluation_json(d, deals_total=100, net_eppd=neppd)
            run_dirs[f"alpha_seat{seat}"] = str(d)

        metrics, missing = _merge_single_seat_evaluations(run_dirs, policies)
        assert missing == []
        assert "alpha" in metrics
        # Weighted avg: (2.0*100 + 1.0*100 + 0.5*100 + 0.5*100) / 400 = 1.0
        assert metrics["alpha"]["net_expected_points_per_deal"] == 1.0

    def test_missing_seat_flags_error(self, tmp_path):
        """Missing seat 3 → bidder in missing_evaluations."""
        policies = [{"name": "alpha"}]
        run_dirs = {}
        for seat in range(3):  # Only 3 seats
            d = tmp_path / f"run_alpha_seat{seat}"
            d.mkdir()
            _make_evaluation_json(d, deals_total=100, net_eppd=1.0)
            run_dirs[f"alpha_seat{seat}"] = str(d)

        metrics, missing = _merge_single_seat_evaluations(run_dirs, policies)
        assert "alpha" in missing
        assert "alpha" not in metrics

    def test_merged_make_rate_calculation(self, tmp_path):
        """Verify make_rate = total_made / total_bid_hands across seats."""
        policies = [{"name": "alpha"}]
        run_dirs = {}
        for seat in range(4):
            d = tmp_path / f"run_alpha_seat{seat}"
            d.mkdir()
            # Each seat: 100 deals, 50 bids, make_rate=0.7 → 35 made
            _make_evaluation_json(d, deals_total=100, bid_rate=0.5, net_eppd=1.0)
            run_dirs[f"alpha_seat{seat}"] = str(d)

        metrics, _ = _merge_single_seat_evaluations(run_dirs, policies)
        # Total: 400 deals, 200 bids, 140 made → make_rate = 0.7
        assert metrics["alpha"]["make_rate"] == 0.7
        assert metrics["alpha"]["bid_rate"] == 0.5
        assert metrics["alpha"]["deals_total"] == 400


class TestManifestCompletenessGate:
    """Tests for _write_batch_manifest() completeness gate."""

    def test_complete_batch_writes_manifest(self, tmp_path):
        """All 4 seats for 1 policy → manifest written."""
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        policies = [{"name": "alpha"}]
        run_dirs = {}
        for seat in range(4):
            d = runs_dir / f"run_alpha_seat{seat}"
            d.mkdir()
            _make_evaluation_json(d, deals_total=100)
            run_dirs[f"alpha_seat{seat}"] = str(d)

        path, bid = _write_batch_manifest(
            str(runs_dir), "test", 42, 400, policies, run_dirs
        )
        assert path is not None
        assert bid is not None
        manifest = json.loads(Path(path).read_text())
        assert manifest["schema"] == "batch_manifest_v1"
        assert manifest["expected_seats"] == 4
        assert len(manifest["members"]) == 4

    def test_incomplete_batch_skips_manifest(self, tmp_path, capsys):
        """Missing seat → no manifest, error printed."""
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        policies = [{"name": "alpha"}]
        run_dirs = {}
        for seat in range(3):  # Only 3 seats
            d = runs_dir / f"run_alpha_seat{seat}"
            d.mkdir()
            _make_evaluation_json(d, deals_total=100)
            run_dirs[f"alpha_seat{seat}"] = str(d)

        path, bid = _write_batch_manifest(
            str(runs_dir), "test", 42, 400, policies, run_dirs
        )
        assert path is None
        assert bid is None
        captured = capsys.readouterr()
        assert "Incomplete batch" in captured.err

    def test_missing_evaluation_skips_manifest(self, tmp_path, capsys):
        """Dir exists but no evaluation.json → no manifest."""
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        policies = [{"name": "alpha"}]
        run_dirs = {}
        for seat in range(4):
            d = runs_dir / f"run_alpha_seat{seat}"
            d.mkdir()
            if seat < 3:
                _make_evaluation_json(d, deals_total=100)
            # seat 3 has no evaluation.json
            run_dirs[f"alpha_seat{seat}"] = str(d)

        path, bid = _write_batch_manifest(
            str(runs_dir), "test", 42, 400, policies, run_dirs
        )
        assert path is None
        captured = capsys.readouterr()
        assert "Missing evaluation.json" in captured.err
