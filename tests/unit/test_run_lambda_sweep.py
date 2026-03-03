"""
Unit tests for the lambda sweep simulation tooling.
"""

import importlib.util
import json
from pathlib import Path

import pytest

# Import via importlib to avoid sys.path.insert anti-pattern.
_SWEEP_SCRIPT = (
    Path(__file__).parent.parent.parent / "scripts" / "internal" / "run_lambda_sweep.py"
)
_spec = importlib.util.spec_from_file_location("run_lambda_sweep", _SWEEP_SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

parse_lambda_grid = _mod.parse_lambda_grid
generate_self_play_config = _mod.generate_self_play_config
apply_guardrails = _mod.apply_guardrails
select_lambda_star = _mod.select_lambda_star
paired_bootstrap_ci = _mod.paired_bootstrap_ci
validate_pairing = _mod.validate_pairing
write_sweep_manifest = _mod.write_sweep_manifest
format_sweep_summary = _mod.format_sweep_summary


# ---------------------------------------------------------------------------
# ParseGrid tests
# ---------------------------------------------------------------------------


class TestParseGrid:
    """Tests for parse_lambda_grid()."""

    def test_default_grid(self):
        """Default grid string yields 7 sorted floats."""
        result = parse_lambda_grid("0.0,0.05,0.1,0.2,0.5,1.0,2.0")
        assert result == [0.0, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0]
        assert len(result) == 7

    def test_single_value(self):
        """Single value string yields a one-element list."""
        result = parse_lambda_grid("0.5")
        assert result == [0.5]

    def test_whitespace(self):
        """Whitespace around values is stripped."""
        result = parse_lambda_grid("0.0, 0.1")
        assert result == [0.0, 0.1]


# ---------------------------------------------------------------------------
# GenConfig tests
# ---------------------------------------------------------------------------


class TestGenConfig:
    """Tests for generate_self_play_config()."""

    def _make_config(self, **kwargs):
        defaults = {
            "lambda_val": 0.5,
            "artifact_path": "/tmp/artifact.json",
            "pass_threshold": 0.0,
            "seed": 42,
            "n_per": 1000,
        }
        defaults.update(kwargs)
        return generate_self_play_config(**defaults)

    def test_required_keys(self):
        """Config has all required top-level keys."""
        config = self._make_config()
        required = {
            "experiment_name",
            "bidding_policies",
            "strategies",
            "scenarios",
            "parameters",
        }
        assert required.issubset(set(config.keys()))

    def test_risk_lambda_in_params(self):
        """risk_lambda is propagated into bidding_policies params."""
        config = self._make_config(lambda_val=1.5)
        bp_params = config["bidding_policies"][0]["params"]
        assert bp_params["risk_lambda"] == 1.5

    def test_bid_level_search_true(self):
        """bid_level_search is always True."""
        config = self._make_config()
        bp_params = config["bidding_policies"][0]["params"]
        assert bp_params["bid_level_search"] is True

    def test_pass_threshold_in_params(self):
        """pass_threshold is propagated into bidding_policies params."""
        config = self._make_config(pass_threshold=0.3)
        bp_params = config["bidding_policies"][0]["params"]
        assert bp_params["pass_threshold"] == 0.3

    def test_play_strategy_glutton(self):
        """parameters.play_strategy is 'glutton'."""
        config = self._make_config()
        assert config["parameters"]["play_strategy"] == "glutton"

    def test_log_level_hand(self):
        """parameters.log_level is 'hand'."""
        config = self._make_config()
        assert config["parameters"]["log_level"] == "hand"

    def test_experiment_name_contains_lambda(self):
        """experiment_name encodes the lambda value."""
        config = self._make_config(lambda_val=0.1)
        assert "0.1" in config["experiment_name"]


# ---------------------------------------------------------------------------
# Guardrails tests
# ---------------------------------------------------------------------------


class TestGuardrails:
    """Tests for apply_guardrails()."""

    def test_all_pass(self):
        """Metrics within bounds pass all guardrails."""
        metrics = {"bid_rate": 0.5, "make_rate": 0.7}
        result = apply_guardrails(metrics)
        assert result["all_pass"] is True

    def test_bid_rate_below_floor(self):
        """bid_rate below floor fails."""
        metrics = {"bid_rate": 0.03, "make_rate": 0.7}
        result = apply_guardrails(metrics)
        assert result["pass_bid_rate_floor"] is False
        assert result["all_pass"] is False

    def test_bid_rate_above_cap(self):
        """bid_rate above cap fails."""
        metrics = {"bid_rate": 0.97, "make_rate": 0.7}
        result = apply_guardrails(metrics)
        assert result["pass_bid_rate_cap"] is False
        assert result["all_pass"] is False

    def test_make_rate_below_floor(self):
        """make_rate below floor fails."""
        metrics = {"bid_rate": 0.5, "make_rate": 0.40}
        result = apply_guardrails(metrics)
        assert result["pass_make_rate"] is False
        assert result["all_pass"] is False

    def test_boundary_inclusive(self):
        """Boundary values (exact floor/cap) pass."""
        metrics = {"bid_rate": 0.05, "make_rate": 0.45}
        result = apply_guardrails(metrics)
        assert result["pass_bid_rate_floor"] is True
        assert result["pass_make_rate"] is True
        assert result["all_pass"] is True


# ---------------------------------------------------------------------------
# Selection tests
# ---------------------------------------------------------------------------


class TestSelection:
    """Tests for select_lambda_star()."""

    def _make_result(self, lam, net_eppd, guardrails_pass=True):
        return {
            "risk_lambda": lam,
            "net_eppd": net_eppd,
            "guardrails": {"all_pass": guardrails_pass},
        }

    def test_baseline_wins(self):
        """When lambda=0.0 has best net_eppd, it is selected."""
        results = [
            self._make_result(0.0, 1.5),
            self._make_result(0.5, 1.0),
            self._make_result(1.0, 0.5),
        ]
        assert select_lambda_star(results) == 0.0

    def test_epsilon_smallest(self):
        """Two lambdas within epsilon: smaller lambda selected."""
        results = [
            self._make_result(0.0, 1.50),
            self._make_result(0.1, 1.51),  # Best, but 0.0 is within epsilon=0.02
            self._make_result(1.0, 1.00),
        ]
        # 1.51 - 1.50 = 0.01 < epsilon=0.02, so 0.0 wins (smallest)
        assert select_lambda_star(results, epsilon=0.02) == 0.0

    def test_clear_winner_outside_epsilon(self):
        """When best is clearly outside epsilon, it wins."""
        results = [
            self._make_result(0.0, 1.00),
            self._make_result(0.5, 1.50),  # Best by 0.50 >> epsilon
            self._make_result(1.0, 0.50),
        ]
        assert select_lambda_star(results, epsilon=0.02) == 0.5

    def test_all_disqualified(self):
        """No survivors -> returns 0.0."""
        results = [
            self._make_result(0.0, 1.5, guardrails_pass=False),
            self._make_result(0.5, 1.0, guardrails_pass=False),
        ]
        assert select_lambda_star(results) == 0.0


# ---------------------------------------------------------------------------
# Bootstrap tests
# ---------------------------------------------------------------------------


class TestBootstrap:
    """Tests for paired_bootstrap_ci()."""

    def test_identical_nets(self):
        """Identical nets produce delta near 0 with CI containing 0."""
        nets = {i: 1.0 for i in range(100)}
        delta, ci_lo, ci_hi = paired_bootstrap_ci(nets, nets)
        assert abs(delta) < 1e-10
        assert ci_lo <= 0.0 <= ci_hi

    def test_clear_positive(self):
        """Candidate clearly better: CI should exclude 0."""
        baseline = {i: 0.0 for i in range(500)}
        candidate = {i: 5.0 for i in range(500)}
        delta, ci_lo, ci_hi = paired_bootstrap_ci(baseline, candidate, n_bootstrap=5000)
        assert delta > 0
        assert ci_lo > 0  # CI excludes 0

    def test_reproducible_seed(self):
        """Same seed produces identical results."""
        baseline = {i: float(i % 5) for i in range(200)}
        candidate = {i: float(i % 5 + 0.1) for i in range(200)}
        r1 = paired_bootstrap_ci(baseline, candidate, seed=99)
        r2 = paired_bootstrap_ci(baseline, candidate, seed=99)
        assert r1 == r2

    def test_mismatched_deals(self):
        """Mismatched deal_ids raises ValueError."""
        baseline = {1: 1.0, 2: 2.0}
        candidate = {1: 1.0, 3: 3.0}  # deal 3 not in baseline
        with pytest.raises(ValueError, match="Deal sets don't match"):
            validate_pairing(baseline, candidate)
            paired_bootstrap_ci(baseline, candidate)


# ---------------------------------------------------------------------------
# Pairing validation tests
# ---------------------------------------------------------------------------


class TestPairing:
    """Tests for validate_pairing()."""

    def test_validate_pairing_pass(self):
        """Identical deal sets pass validation."""
        nets_a = {1: 1.0, 2: 2.0, 3: 3.0}
        nets_b = {1: 0.5, 2: 1.5, 3: 2.5}
        validate_pairing(nets_a, nets_b)  # Should not raise

    def test_validate_pairing_fail(self):
        """Disjoint deal sets raise ValueError."""
        nets_a = {1: 1.0, 2: 2.0}
        nets_b = {3: 1.0, 4: 2.0}
        with pytest.raises(ValueError, match="Deal sets don't match"):
            validate_pairing(nets_a, nets_b)

    def test_validate_pairing_subset(self):
        """Subset (one has extra deals) raises ValueError."""
        nets_a = {1: 1.0, 2: 2.0, 3: 3.0}
        nets_b = {1: 1.0, 2: 2.0}
        with pytest.raises(ValueError, match="Deal sets don't match"):
            validate_pairing(nets_a, nets_b)


# ---------------------------------------------------------------------------
# Manifest tests
# ---------------------------------------------------------------------------


class TestManifest:
    """Tests for write_sweep_manifest()."""

    def test_round_trip(self, tmp_path):
        """Write manifest, read back, verify identical content."""
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()

        # Create fake run dirs
        for lam in [0.0, 0.5, 1.0]:
            (runs_dir / f"lambda_sweep_{lam}_42_20260302").mkdir()

        run_dirs = {
            0.0: str(runs_dir / "lambda_sweep_0.0_42_20260302"),
            0.5: str(runs_dir / "lambda_sweep_0.5_42_20260302"),
            1.0: str(runs_dir / "lambda_sweep_1.0_42_20260302"),
        }

        path = write_sweep_manifest(
            str(runs_dir), [0.0, 0.5, 1.0], seed=42, n_per=1000, run_dirs=run_dirs
        )
        assert Path(path).exists()

        manifest = json.loads(Path(path).read_text())
        assert manifest["schema"] == "lambda_sweep_manifest_v1"
        assert manifest["seed"] == 42
        assert manifest["n_per"] == 1000
        assert len(manifest["members"]) == 3
        assert manifest["grid"] == [0.0, 0.5, 1.0]


# ---------------------------------------------------------------------------
# Summary / schema tests
# ---------------------------------------------------------------------------


class TestSummary:
    """Tests for format_sweep_summary()."""

    def _make_sweep_results(self, lambdas_and_eppds):
        return [
            {
                "risk_lambda": lam,
                "net_eppd": eppd,
                "bid_rate": 0.5,
                "make_rate": 0.7,
                "guardrails": {"all_pass": True},
            }
            for lam, eppd in lambdas_and_eppds
        ]

    def test_schema_correct(self):
        """Output has lambda_sweep_v1 schema."""
        results = self._make_sweep_results([(0.0, 1.0), (0.5, 0.8)])
        summary = format_sweep_summary(
            grid=[0.0, 0.5],
            sweep_results=results,
            lambda_star=0.0,
            seed=42,
            n_per=1000,
            pass_threshold=0.0,
            artifact_path="/tmp/art.json",
            epsilon=0.02,
        )
        assert summary["schema"] == "lambda_sweep_v1"

    def test_all_grid_in_results(self):
        """Every lambda from sweep_results appears in output results."""
        results = self._make_sweep_results([(0.0, 1.0), (0.1, 0.9), (0.5, 0.8)])
        summary = format_sweep_summary(
            grid=[0.0, 0.1, 0.5],
            sweep_results=results,
            lambda_star=0.0,
            seed=42,
            n_per=1000,
            pass_threshold=0.0,
            artifact_path="/tmp/art.json",
            epsilon=0.02,
        )
        result_lambdas = {r["risk_lambda"] for r in summary["results"]}
        assert result_lambdas == {0.0, 0.1, 0.5}

    def test_provisional_status(self):
        """lambda_star > 0 produces PROVISIONAL status."""
        results = self._make_sweep_results([(0.0, 1.0), (0.5, 1.5)])
        summary = format_sweep_summary(
            grid=[0.0, 0.5],
            sweep_results=results,
            lambda_star=0.5,
            seed=42,
            n_per=1000,
            pass_threshold=0.0,
            artifact_path="/tmp/art.json",
            epsilon=0.02,
        )
        assert summary["status"] == "PROVISIONAL"
        assert summary["requires_h2h_confirmation"] is True

    def test_final_status(self):
        """lambda_star == 0 produces FINAL status."""
        results = self._make_sweep_results([(0.0, 1.0), (0.5, 0.5)])
        summary = format_sweep_summary(
            grid=[0.0, 0.5],
            sweep_results=results,
            lambda_star=0.0,
            seed=42,
            n_per=1000,
            pass_threshold=0.0,
            artifact_path="/tmp/art.json",
            epsilon=0.02,
        )
        assert summary["status"] == "FINAL"
        assert summary["requires_h2h_confirmation"] is False

    def test_bootstrap_results_included(self):
        """Bootstrap results are included when provided."""
        results = self._make_sweep_results([(0.0, 1.0), (0.5, 1.5)])
        bootstrap = {0.5: (0.5, 0.2, 0.8)}
        summary = format_sweep_summary(
            grid=[0.0, 0.5],
            sweep_results=results,
            lambda_star=0.5,
            seed=42,
            n_per=1000,
            pass_threshold=0.0,
            artifact_path="/tmp/art.json",
            epsilon=0.02,
            bootstrap_results=bootstrap,
        )
        lam_05_result = next(r for r in summary["results"] if r["risk_lambda"] == 0.5)
        assert lam_05_result["delta_vs_baseline"] == 0.5
        assert lam_05_result["ci_95_lo"] == 0.2
        assert lam_05_result["ci_95_hi"] == 0.8
        assert lam_05_result["ci_excludes_zero"] is True
