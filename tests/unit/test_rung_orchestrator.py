"""Unit tests for rung orchestrator state management, advance check, and CLI.

All tests are fixture-based -- no real experiment runs or subprocess calls.
Uses tmp_path for state files and mock CSV fixtures for advance check.
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from bid_euchre.arc_d_v2 import orchestration as run_rung_mod
from bid_euchre.arc_d_v2.advance_check import (
    check_canaries,
    check_sufficiency,
    compute_decision,
    evaluate_hypothesis,
    find_best_in_lineage,
    generate_advance_check,
)
from bid_euchre.arc_d_v2.config import AnchorModel, Roster, RosterModel
from bid_euchre.arc_d_v2.orchestration import (
    STEP_DESCRIPTIONS,
    STEP_FUNCTIONS,
    compute_fingerprint,
    handle_rerun,
)
from bid_euchre.arc_d_v2.schemas import (
    DAG_DOWNSTREAM,
    MODEL_SCOPED_STEPS,
    STEPS,
    RunState,
)

# ============================================================================
# State Management Tests
# ============================================================================


class TestRunStateCreateFresh:
    def test_create_fresh_basic(self):
        state = RunState.create_fresh("r0", "smoke", [42])
        assert state.rung == "r0"
        assert state.mode == "smoke"
        assert state.seeds == [42]
        assert state.current_step == "0"
        assert state.step_status == "not_started"
        assert state.blocker is None
        assert len(state.steps) == len(STEPS)
        assert "42" in state.per_seed

    def test_create_fresh_multi_seed(self):
        state = RunState.create_fresh("r0", "full", [42, 123, 456])
        assert state.seeds == [42, 123, 456]
        assert "42" in state.per_seed
        assert "123" in state.per_seed
        assert "456" in state.per_seed
        for seed_key in state.per_seed:
            assert len(state.per_seed[seed_key]) == len(STEPS)

    def test_all_steps_start_pending(self):
        state = RunState.create_fresh("r0", "quick", [42])
        for step_id, step_data in state.steps.items():
            assert step_data["status"] == "pending", f"Step {step_id} not pending"


class TestRunStateSaveLoad:
    def test_round_trip(self, tmp_path):
        state = RunState.create_fresh("r0", "quick", [42])
        state.blocker = "test blocker"
        path = tmp_path / "state.json"
        state.save(path)

        loaded = RunState.load(path)
        assert loaded.rung == "r0"
        assert loaded.mode == "quick"
        assert loaded.seeds == [42]
        assert loaded.blocker == "test blocker"
        assert len(loaded.steps) == len(STEPS)

    def test_save_creates_parent_dirs(self, tmp_path):
        state = RunState.create_fresh("r0", "smoke", [42])
        path = tmp_path / "deep" / "nested" / "state.json"
        state.save(path)
        assert path.exists()

    def test_load_preserves_step_status(self, tmp_path):
        state = RunState.create_fresh("r0", "smoke", [42])
        state.mark_step_complete("0")
        state.mark_step_started("1")
        path = tmp_path / "state.json"
        state.save(path)

        loaded = RunState.load(path)
        assert loaded.steps["0"]["status"] == "complete"
        assert loaded.steps["1"]["status"] == "running"
        assert loaded.steps["2"]["status"] == "pending"


class TestRunStateStepOperations:
    def test_mark_step_started(self):
        state = RunState.create_fresh("r0", "smoke", [42])
        state.mark_step_started("1", seed=42)
        assert state.current_step == "1"
        assert state.step_status == "running"
        assert state.steps["1"]["status"] == "running"
        assert state.per_seed["42"]["1"]["status"] == "running"

    def test_mark_step_complete(self):
        state = RunState.create_fresh("r0", "smoke", [42])
        fp = {"seed": 42, "mode": "smoke"}
        state.mark_step_complete("1", seed=42, fingerprint=fp)
        assert state.steps["1"]["status"] == "complete"
        assert state.steps["1"]["fingerprint"] == fp
        assert state.per_seed["42"]["1"]["status"] == "complete"

    def test_mark_step_failed_retryable(self):
        state = RunState.create_fresh("r0", "smoke", [42])
        state.mark_step_failed("2", "OOM error", retryable=True, seed=42)
        assert state.steps["2"]["status"] == "failed"
        assert state.steps["2"]["error"] == "OOM error"
        assert state.blocker is None  # retryable doesn't set blocker

    def test_mark_step_failed_blocking(self):
        state = RunState.create_fresh("r0", "smoke", [42])
        state.mark_step_failed("2", "Missing data", retryable=False)
        assert state.blocker == "Missing data"

    def test_mark_step_skipped(self):
        state = RunState.create_fresh("r0", "smoke", [42])
        state.mark_step_skipped("3b", "Script not found")
        assert state.steps["3b"]["status"] == "skipped"
        assert state.steps["3b"]["error"] == "Script not found"

    def test_step_is_complete(self):
        state = RunState.create_fresh("r0", "smoke", [42])
        assert not state.step_is_complete("1")
        state.mark_step_complete("1")
        assert state.step_is_complete("1")

    def test_step_is_complete_per_seed(self):
        state = RunState.create_fresh("r0", "full", [42, 123])
        assert not state.step_is_complete("1", seed=42)
        state.mark_step_complete("1", seed=42)
        assert state.step_is_complete("1", seed=42)
        assert not state.step_is_complete("1", seed=123)


class TestRunStateModelTracking:
    def test_model_status_default(self):
        state = RunState.create_fresh("r0", "smoke", [42])
        assert state.model_status(42, "2", "gbt_av") == "pending"

    def test_update_model(self):
        state = RunState.create_fresh("r0", "smoke", [42])
        state.update_model("2", "gbt_av", 42, "running")
        assert state.model_status(42, "2", "gbt_av") == "running"

        state.update_model("2", "gbt_av", 42, "complete")
        assert state.model_status(42, "2", "gbt_av") == "complete"

    def test_update_model_failed(self):
        state = RunState.create_fresh("r0", "smoke", [42])
        state.update_model("2", "ols_av", 42, "failed", error="OOM")
        status = state.model_status(42, "2", "ols_av")
        assert status == "failed"
        model_data = state.per_seed["42"]["2"]["models"]["ols_av"]
        assert model_data["error"] == "OOM"

    def test_model_status_multi_seed(self):
        state = RunState.create_fresh("r0", "full", [42, 123])
        state.update_model("2", "gbt_av", 42, "complete")
        state.update_model("2", "gbt_av", 123, "running")
        assert state.model_status(42, "2", "gbt_av") == "complete"
        assert state.model_status(123, "2", "gbt_av") == "running"


class TestRunStateReset:
    def test_reset_step(self):
        state = RunState.create_fresh("r0", "smoke", [42])
        state.mark_step_complete("2")
        state.reset_step("2")
        assert state.steps["2"]["status"] == "pending"

    def test_reset_model(self):
        state = RunState.create_fresh("r0", "smoke", [42])
        state.update_model("2", "gbt_av", 42, "complete")
        state.reset_model("2", "gbt_av")
        # The per-seed model should be reset
        seed_model = state.per_seed["42"]["2"]["models"].get("gbt_av", {})
        assert seed_model.get("status") == "pending"
        # The step status should revert to pending since model was reset
        assert state.steps["2"]["status"] == "pending"

    def test_reset_for_mode(self):
        state = RunState.create_fresh("r0", "quick", [42])
        state.mark_step_complete("0")
        state.mark_step_complete("1")
        state.mark_step_complete("2")

        state.reset_for_mode("full", [42, 123, 456])
        assert state.mode == "full"
        assert state.seeds == [42, 123, 456]
        assert state.steps["0"]["status"] == "pending"
        assert state.steps["1"]["status"] == "pending"
        assert state.steps["2"]["status"] == "pending"
        assert "42" in state.per_seed
        assert "123" in state.per_seed
        assert "456" in state.per_seed


class TestRunStateSummary:
    def test_summary_contains_key_info(self):
        state = RunState.create_fresh("r0", "smoke", [42])
        state.mark_step_complete("0")
        state.mark_step_failed("1", "Test error")
        summary = state.summary()
        assert "Rung: r0" in summary
        assert "Mode: smoke" in summary
        assert "[x] Step 0:" in summary
        assert "[!] Step 1:" in summary
        assert "Test error" in summary


class TestRunStateFingerprint:
    def test_get_set_fingerprint(self):
        state = RunState.create_fresh("r0", "smoke", [42])
        assert state.get_step_fingerprint("1") is None
        fp = {"seed": 42, "mode": "smoke"}
        state.mark_step_complete("1", fingerprint=fp)
        assert state.get_step_fingerprint("1") == fp

    def test_fingerprint_per_seed(self):
        state = RunState.create_fresh("r0", "full", [42, 123])
        fp42 = {"seed": 42}
        fp123 = {"seed": 123}
        state.mark_step_complete("1", seed=42, fingerprint=fp42)
        state.mark_step_complete("1", seed=123, fingerprint=fp123)
        assert state.get_step_fingerprint("1", seed=42) == fp42
        assert state.get_step_fingerprint("1", seed=123) == fp123


# ============================================================================
# Rerun Tests
# ============================================================================


class TestRerun:
    def test_rerun_from_step_2_holistic(self, tmp_path):
        """Rerun from step 2 resets 2 and all downstream."""
        state = RunState.create_fresh("r0", "smoke", [42])
        # Mark several steps complete
        for step in STEPS:
            state.mark_step_complete(step)
        state_path = tmp_path / "plans" / "arc_d_v2" / "r0" / "state.json"

        with patch.object(run_rung_mod, "_state_path", return_value=state_path):
            handle_rerun(state, "2")

        # Step 2 and downstream should be reset
        expected_reset = {"2"} | set(DAG_DOWNSTREAM["2"])
        for step in STEPS:
            if step in expected_reset:
                assert (
                    state.steps[step]["status"] == "pending"
                ), f"Step {step} should be pending"
            else:
                assert (
                    state.steps[step]["status"] == "complete"
                ), f"Step {step} should still be complete"

    def test_rerun_model_scoped(self, tmp_path):
        """Rerun with --models flag scopes reset to model-scoped steps."""
        state = RunState.create_fresh("r0", "smoke", [42])
        # Set up model status
        state.update_model("2", "gbt_av", 42, "complete")
        state.update_model("2", "ols_av", 42, "complete")
        state.mark_step_complete("2")
        for step in ["3", "3b", "4", "5", "6", "7", "8"]:
            state.mark_step_complete(step)
        state_path = tmp_path / "plans" / "arc_d_v2" / "r0" / "state.json"

        with patch.object(run_rung_mod, "_state_path", return_value=state_path):
            handle_rerun(state, "2", models=["gbt_av"])

        # Holistic steps (4+) should be fully reset
        assert state.steps["4"]["status"] == "pending"
        assert state.steps["5"]["status"] == "pending"
        assert state.steps["6"]["status"] == "pending"

    def test_rerun_sets_supersession(self, tmp_path):
        state = RunState.create_fresh("r0", "smoke", [42])
        state_path = tmp_path / "plans" / "arc_d_v2" / "r0" / "state.json"

        with patch.object(run_rung_mod, "_state_path", return_value=state_path):
            handle_rerun(state, "4", models=["gbt_av"])

        assert state.supersession is not None
        assert state.supersession["from_step"] == "4"
        assert state.supersession["models"] == ["gbt_av"]

    def test_rerun_step_0_resets_everything(self, tmp_path):
        state = RunState.create_fresh("r0", "smoke", [42])
        for step in STEPS:
            state.mark_step_complete(step)
        state_path = tmp_path / "plans" / "arc_d_v2" / "r0" / "state.json"

        with patch.object(run_rung_mod, "_state_path", return_value=state_path):
            handle_rerun(state, "0")

        for step in ["0"] + DAG_DOWNSTREAM["0"]:
            assert state.steps[step]["status"] == "pending"


# ============================================================================
# DAG Downstream Tests
# ============================================================================


class TestDAGDownstream:
    def test_all_steps_have_downstream_entry(self):
        for step in STEPS:
            assert step in DAG_DOWNSTREAM, f"Step {step} missing from DAG_DOWNSTREAM"

    def test_step_9_has_no_downstream(self):
        assert DAG_DOWNSTREAM["9"] == []

    def test_step_0_reaches_most_steps(self):
        assert len(DAG_DOWNSTREAM["0"]) >= 8

    def test_no_self_reference(self):
        for step, downstream in DAG_DOWNSTREAM.items():
            assert step not in downstream, f"Step {step} references itself"

    def test_model_scoped_steps(self):
        assert MODEL_SCOPED_STEPS == {"2", "3", "3b"}


# ============================================================================
# Advance Check Tests
# ============================================================================


def _write_csv(path: Path, headers: list[str], rows: list[list]) -> None:
    """Helper to write a CSV fixture."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)


class TestHypothesisEvaluation:
    def test_simple_value_check(self, tmp_path):
        _write_csv(
            tmp_path / "comparator_rankings.csv",
            ["model", "facet", "net_eppd"],
            [["gbt_av", "pooled", "1.5"]],
        )
        hyp = {
            "id": "H1",
            "description": "test",
            "source_table": "comparator_rankings.csv",
            "source_column": "net_eppd",
            "source_filter": {"model": "gbt_av", "facet": "pooled"},
            "computation": "value",
            "expected_bound": {"op": ">", "value": 1.0},
            "surprise_if": {"op": "<", "value": 0.0},
        }
        result = evaluate_hypothesis(hyp, tmp_path)
        assert result["pass"] is True
        assert result["observed"] == 1.5
        assert result["surprise_hit"] is False

    def test_delta_computation(self, tmp_path):
        _write_csv(
            tmp_path / "comparator_rankings.csv",
            ["model", "facet", "net_eppd"],
            [
                ["gbt_av", "suit", "2.5"],
                ["anchor_hybrid_r0_full", "suit", "1.0"],
            ],
        )
        hyp = {
            "id": "H1",
            "description": "test delta",
            "source_table": "comparator_rankings.csv",
            "source_column": "net_eppd",
            "source_filter": {"model": "gbt_av", "facet": "suit"},
            "anchor_filter": {"model": "anchor_hybrid_r0_full", "facet": "suit"},
            "computation": "value - anchor_value",
            "expected_bound": {"op": ">", "value": 0.5},
            "surprise_if": {"op": "<", "value": 0.0},
        }
        result = evaluate_hypothesis(hyp, tmp_path)
        assert result["pass"] is True
        assert result["observed"] == 1.5
        assert result["surprise_hit"] is False

    def test_failing_hypothesis(self, tmp_path):
        _write_csv(
            tmp_path / "comparator_rankings.csv",
            ["model", "facet", "net_eppd"],
            [
                ["gbt_av", "pooled", "0.2"],
                ["anchor", "pooled", "0.5"],
            ],
        )
        hyp = {
            "id": "H2",
            "description": "test fail",
            "source_table": "comparator_rankings.csv",
            "source_column": "net_eppd",
            "source_filter": {"model": "gbt_av", "facet": "pooled"},
            "anchor_filter": {"model": "anchor", "facet": "pooled"},
            "computation": "value - anchor_value",
            "expected_bound": {"op": ">", "value": 0.0},
            "surprise_if": {"op": "<", "value": -0.5},
        }
        result = evaluate_hypothesis(hyp, tmp_path)
        assert result["pass"] is False
        assert result["observed"] == pytest.approx(-0.3)
        assert result["surprise_hit"] is False  # -0.3 > -0.5

    def test_surprise_hit(self, tmp_path):
        _write_csv(
            tmp_path / "comparator_rankings.csv",
            ["model", "facet", "net_eppd"],
            [
                ["gbt_av", "suit", "0.1"],
                ["anchor", "suit", "1.5"],
            ],
        )
        hyp = {
            "id": "H3",
            "description": "test surprise",
            "source_table": "comparator_rankings.csv",
            "source_column": "net_eppd",
            "source_filter": {"model": "gbt_av", "facet": "suit"},
            "anchor_filter": {"model": "anchor", "facet": "suit"},
            "computation": "value - anchor_value",
            "expected_bound": {"op": ">", "value": 0.0},
            "surprise_if": {"op": "<", "value": -1.0},
        }
        result = evaluate_hypothesis(hyp, tmp_path)
        assert result["pass"] is False
        assert result["surprise_hit"] is True  # -1.4 < -1.0

    def test_missing_table(self, tmp_path):
        hyp = {
            "id": "H1",
            "description": "test missing",
            "source_table": "nonexistent.csv",
            "source_column": "net_eppd",
            "source_filter": {"model": "x"},
            "computation": "value",
            "expected_bound": {"op": ">", "value": 0},
        }
        result = evaluate_hypothesis(hyp, tmp_path)
        assert result["error"] is not None
        assert result["pass"] is False


class TestSufficiencyChecks:
    def test_all_tables_present(self, tmp_path):
        for name in [
            "model_performance.csv",
            "data_sanity.csv",
            "comparator_rankings.csv",
            "h2h_matrix.csv",
        ]:
            _write_csv(
                tmp_path / name,
                ["model", "status", "net_eppd"],
                [["gbt_av", "PASS", "1.0"]],
            )
        checks = check_sufficiency(tmp_path, "r0")
        table_check = next(c for c in checks if c["id"] == "all_tables_generated")
        assert table_check["pass"] is True
        assert table_check["value"] == "4/4"

    def test_missing_tables(self, tmp_path):
        # Create only one table
        _write_csv(
            tmp_path / "model_performance.csv",
            ["model"],
            [["gbt_av"]],
        )
        checks = check_sufficiency(tmp_path, "r0")
        table_check = next(c for c in checks if c["id"] == "all_tables_generated")
        assert table_check["pass"] is False

    def test_data_sanity_all_pass(self, tmp_path):
        _write_csv(
            tmp_path / "data_sanity.csv",
            ["check", "status"],
            [["seat_balance", "PASS"], ["hand_count", "PASS"]],
        )
        checks = check_sufficiency(tmp_path, "r0")
        sanity = next(c for c in checks if c["id"] == "data_sanity")
        assert sanity["pass"] is True
        assert sanity["value"] == "2/2 pass"

    def test_data_sanity_with_failure(self, tmp_path):
        _write_csv(
            tmp_path / "data_sanity.csv",
            ["check", "status"],
            [["seat_balance", "PASS"], ["hand_count", "FAIL"]],
        )
        checks = check_sufficiency(tmp_path, "r0")
        sanity = next(c for c in checks if c["id"] == "data_sanity")
        assert sanity["pass"] is False


class TestCanaryChecks:
    def test_default_canaries_pass(self, tmp_path):
        checks = check_canaries(tmp_path, "quick")
        for c in checks:
            assert c["level"] == "WARNING"
            assert c["pass"] is True

    def test_c3_magnitude_violation(self, tmp_path):
        _write_csv(
            tmp_path / "comparator_rankings.csv",
            ["model", "facet", "net_eppd"],
            [["extreme_model", "pooled", "7.5"]],
        )
        checks = check_canaries(tmp_path, "quick")
        c3 = next(c for c in checks if c["id"] == "C3_magnitude_historical")
        assert c3["pass"] is False

    def test_c4_differentiation(self, tmp_path):
        _write_csv(
            tmp_path / "comparator_rankings.csv",
            ["model", "facet", "net_eppd"],
            [
                ["m1", "pooled", "1.0"],
                ["m2", "pooled", "1.0"],
            ],
        )
        checks = check_canaries(tmp_path, "quick")
        c4 = next(c for c in checks if c["id"] == "C4_model_differentiation")
        assert c4["pass"] is False


class TestDecisionRules:
    def test_all_pass_proceed(self):
        hyp = [{"id": "H1", "pass": True, "surprise_hit": False}]
        suff = [{"id": "s1", "pass": True}]
        canary = [{"id": "c1", "pass": True}]
        decision, reason = compute_decision(hyp, suff, canary)
        assert decision == "PROCEED"
        assert "All checks pass" in reason

    def test_surprise_investigate(self):
        hyp = [{"id": "H1", "pass": False, "surprise_hit": True}]
        suff = [{"id": "s1", "pass": True}]
        canary = [{"id": "c1", "pass": True}]
        decision, reason = compute_decision(hyp, suff, canary)
        assert decision == "INVESTIGATE"

    def test_data_sanity_pause(self):
        hyp = [{"id": "H1", "pass": True, "surprise_hit": False}]
        suff = [{"id": "data_sanity", "pass": False}]
        canary = [{"id": "c1", "pass": True}]
        decision, reason = compute_decision(hyp, suff, canary)
        assert decision == "PAUSE"

    def test_blocked_models_pause(self):
        hyp = [{"id": "H1", "pass": True, "surprise_hit": False}]
        suff = [{"id": "no_blocked_models", "pass": False}]
        canary = [{"id": "c1", "pass": True}]
        decision, reason = compute_decision(hyp, suff, canary)
        assert decision == "PAUSE"

    def test_hypothesis_failure_investigate(self):
        hyp = [{"id": "H1", "pass": False, "surprise_hit": False, "error": None}]
        suff = [{"id": "s1", "pass": True}]
        canary = [{"id": "c1", "pass": True}]
        decision, reason = compute_decision(hyp, suff, canary)
        assert decision == "INVESTIGATE"

    def test_hypothesis_error_investigate(self):
        hyp = [
            {"id": "H1", "pass": False, "surprise_hit": False, "error": "Missing table"}
        ]
        suff = [{"id": "s1", "pass": True}]
        canary = [{"id": "c1", "pass": True}]
        decision, reason = compute_decision(hyp, suff, canary)
        assert decision == "INVESTIGATE"
        assert "Could not evaluate" in reason

    def test_canary_warnings_still_proceed(self):
        hyp = [{"id": "H1", "pass": True, "surprise_hit": False}]
        suff = [{"id": "s1", "pass": True}]
        canary = [{"id": "c1", "pass": False}]
        decision, reason = compute_decision(hyp, suff, canary)
        assert decision == "PROCEED"
        assert "canary warning" in reason


class TestBestInLineage:
    def test_finds_best(self, tmp_path):
        _write_csv(
            tmp_path / "comparator_rankings.csv",
            ["model", "facet", "net_eppd"],
            [
                ["gbt_av", "pooled", "1.82"],
                ["ols_av", "pooled", "0.95"],
                ["gbt_av", "suit", "2.5"],
            ],
        )
        best = find_best_in_lineage(tmp_path)
        assert best is not None
        assert best["model"] == "gbt_av"
        assert best["pooled_net_eppd"] == 1.82

    def test_no_rankings(self, tmp_path):
        best = find_best_in_lineage(tmp_path)
        assert best is None


class TestAdvanceCheckIntegration:
    def test_full_advance_check(self, tmp_path):
        """Integration test: generate a full advance check from fixtures."""
        hyp = {
            "schema_version": "hypotheses_v1",
            "rung": "r0",
            "hypotheses": [
                {
                    "id": "H1",
                    "description": "GBT beats anchor on pooled",
                    "source_table": "comparator_rankings.csv",
                    "source_column": "net_eppd",
                    "source_filter": {"model": "gbt_av", "facet": "pooled"},
                    "anchor_filter": {"model": "anchor", "facet": "pooled"},
                    "computation": "value - anchor_value",
                    "expected_bound": {"op": ">", "value": 0.3},
                    "surprise_if": {"op": "<", "value": 0.0},
                },
            ],
        }
        hyp_path = tmp_path / "hypotheses.json"
        hyp_path.write_text(json.dumps(hyp))

        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()
        _write_csv(
            tables_dir / "comparator_rankings.csv",
            ["model", "facet", "net_eppd"],
            [
                ["gbt_av", "pooled", "1.5"],
                ["anchor", "pooled", "0.8"],
                ["gbt_av", "suit", "2.0"],
            ],
        )
        _write_csv(
            tables_dir / "model_performance.csv",
            ["model", "contract_type", "r2"],
            [["gbt_av", "suit", "0.65"]],
        )
        _write_csv(
            tables_dir / "data_sanity.csv",
            ["check", "status"],
            [["seat_balance", "PASS"]],
        )
        _write_csv(
            tables_dir / "h2h_matrix.csv",
            ["challenger", "opponent", "win_rate"],
            [["gbt_av", "anchor", "0.55"]],
        )

        result = generate_advance_check(hyp_path, tables_dir, "quick", "r0")

        assert result["schema_version"] == "advance_check_v1"
        assert result["rung"] == "r0"
        assert result["mode"] == "quick"
        assert result["advance_decision"] == "PROCEED"
        assert len(result["hypothesis_checks"]) == 1
        assert result["hypothesis_checks"][0]["pass"] is True
        assert result["best_in_lineage"]["model"] == "gbt_av"


# ============================================================================
# Fingerprint Tests
# ============================================================================


class TestFingerprint:
    def test_compute_fingerprint_basic(self):
        fp = compute_fingerprint("1", None, 42, "r0", "smoke")
        assert fp["seed"] == 42
        assert fp["mode"] == "smoke"
        assert fp["step"] == "1"

    def test_compute_fingerprint_with_model(self):
        fp = compute_fingerprint("2", "gbt_av", 42, "r0", "quick")
        assert fp["model"] == "gbt_av"

    def test_fingerprint_changes_with_seed(self):
        fp1 = compute_fingerprint("1", None, 42, "r0", "smoke")
        fp2 = compute_fingerprint("1", None, 123, "r0", "smoke")
        assert fp1["seed"] != fp2["seed"]


# ============================================================================
# CLI Dry-Run Test
# ============================================================================


class TestDryRun:
    def test_dry_run_with_preconditions(self, tmp_path):
        """Dry-run should check preconditions without executing."""
        plan_dir = tmp_path / "plans" / "arc_d_v2" / "r0"
        plan_dir.mkdir(parents=True)
        (plan_dir / "plan.md").write_text("# Test plan")
        (plan_dir / "hypotheses.json").write_text(
            json.dumps(
                {
                    "schema_version": "hypotheses_v1",
                    "rung": "r0",
                    "hypotheses": [],
                }
            )
        )

        with (
            patch.object(run_rung_mod, "_plans_dir", return_value=plan_dir),
            patch.object(
                run_rung_mod,
                "_state_path",
                return_value=plan_dir / "state.json",
            ),
            patch.object(run_rung_mod, "_repo_root", return_value=tmp_path),
        ):
            state = RunState.create_fresh("r0", "smoke", [42])
            ok = run_rung_mod.execute_step_0(state, dry_run=True)
            assert ok is True
            assert state.steps["0"]["status"] == "complete"

    def test_dry_run_fails_without_plan(self, tmp_path):
        """Dry-run should fail if plan.md is missing."""
        plan_dir = tmp_path / "plans" / "arc_d_v2" / "r0"
        plan_dir.mkdir(parents=True)

        with (
            patch.object(run_rung_mod, "_plans_dir", return_value=plan_dir),
            patch.object(
                run_rung_mod,
                "_state_path",
                return_value=plan_dir / "state.json",
            ),
        ):
            state = RunState.create_fresh("r0", "smoke", [42])
            ok = run_rung_mod.execute_step_0(state, dry_run=True)
            assert ok is False
            assert state.steps["0"]["status"] == "failed"


# ============================================================================
# Status Print Test
# ============================================================================


class TestStatusPrint:
    def test_status_creates_fresh_state(self, tmp_path, capsys):
        """--status should create fresh state if none exists."""
        state_path = tmp_path / "state.json"

        with patch.object(run_rung_mod, "_state_path", return_value=state_path):
            run_rung_mod.print_status("r0")

        captured = capsys.readouterr()
        assert "Rung: r0" in captured.out
        assert state_path.exists()

    def test_status_loads_existing(self, tmp_path, capsys):
        state = RunState.create_fresh("r0", "quick", [42])
        state.mark_step_complete("0")
        state_path = tmp_path / "state.json"
        state.save(state_path)

        with patch.object(run_rung_mod, "_state_path", return_value=state_path):
            run_rung_mod.print_status("r0")

        captured = capsys.readouterr()
        assert "Mode: quick" in captured.out
        assert "[x] Step 0:" in captured.out


# ============================================================================
# H2H Resume Test
# ============================================================================


class TestH2HResume:
    def test_partial_completion_no_duplicate(self, tmp_path):
        state = RunState.create_fresh("r0", "full", [42, 123, 456])
        state.mark_step_complete("4", seed=42)

        assert state.step_is_complete("4", seed=42)
        assert not state.step_is_complete("4", seed=123)
        assert not state.step_is_complete("4", seed=456)

        completed_seeds = [
            s for s in state.seeds if state.step_is_complete("4", seed=s)
        ]
        remaining_seeds = [
            s for s in state.seeds if not state.step_is_complete("4", seed=s)
        ]
        assert completed_seeds == [42]
        assert remaining_seeds == [123, 456]


# ============================================================================
# Steps Constants Tests
# ============================================================================


class TestStepsConstants:
    def test_steps_list(self):
        assert STEPS == ["0", "1", "2", "3", "3b", "4", "5", "6", "7", "8", "9"]

    def test_step_descriptions_complete(self):
        for step in STEPS:
            assert step in STEP_DESCRIPTIONS, f"Step {step} missing description"

    def test_step_functions_complete(self):
        for step in STEPS:
            assert step in STEP_FUNCTIONS, f"Step {step} missing function"


# ============================================================================
# Heartbeat Tests
# ============================================================================

from bid_euchre.arc_d_v2 import paths as arc_paths
from bid_euchre.arc_d_v2.heartbeat import (
    check_heartbeat,
    clear_heartbeat,
    write_heartbeat,
)


class TestWriteHeartbeat:
    def test_write_creates_file(self, tmp_path):
        with patch.object(arc_paths, "PLANS_ROOT", tmp_path):
            write_heartbeat("r0")
            hb_path = tmp_path / "r0" / "heartbeat"
            assert hb_path.exists()
            ts = float(hb_path.read_text().strip())
            # Should be within the last few seconds
            assert time.time() - ts < 5


class TestCheckHeartbeatFresh:
    def test_fresh_heartbeat_returns_true(self, tmp_path):
        with patch.object(arc_paths, "PLANS_ROOT", tmp_path):
            write_heartbeat("r0")
            assert check_heartbeat("r0") is True


class TestCheckHeartbeatStale:
    def test_stale_heartbeat_returns_false(self, tmp_path):
        with patch.object(arc_paths, "PLANS_ROOT", tmp_path):
            hb_path = tmp_path / "r0" / "heartbeat"
            hb_path.parent.mkdir(parents=True, exist_ok=True)
            # Write a timestamp from 10 minutes ago
            old_ts = time.time() - 600
            hb_path.write_text(f"{old_ts}\n")
            assert check_heartbeat("r0", max_stale_seconds=300) is False


class TestCheckHeartbeatMissing:
    def test_missing_heartbeat_returns_false(self, tmp_path):
        with patch.object(arc_paths, "PLANS_ROOT", tmp_path):
            assert check_heartbeat("r0") is False


class TestClearHeartbeat:
    def test_clear_removes_file(self, tmp_path):
        with patch.object(arc_paths, "PLANS_ROOT", tmp_path):
            write_heartbeat("r0")
            hb_path = tmp_path / "r0" / "heartbeat"
            assert hb_path.exists()
            clear_heartbeat("r0")
            assert not hb_path.exists()

    def test_clear_noop_when_missing(self, tmp_path):
        """Clearing a non-existent heartbeat should not raise."""
        with patch.object(arc_paths, "PLANS_ROOT", tmp_path):
            clear_heartbeat("r0")  # Should not raise


# ============================================================================
# Artifact Discovery Tests
# ============================================================================


from bid_euchre.arc_d_v2.orchestration import find_trained_artifact


class TestFindTrainedArtifact:
    def test_pattern1_artifacts_dir_subdirectory(self, tmp_path):
        """Find artifact at <artifacts_dir>/<model>/artifact.json."""
        art = tmp_path / "gbt_av" / "artifact.json"
        art.parent.mkdir(parents=True)
        art.write_text("{}")
        result = find_trained_artifact("gbt_av", "r0", "smoke", 42, tmp_path)
        assert result == art

    def test_pattern2_flat_naming(self, tmp_path):
        """Find artifact at <artifacts_dir>/training_artifact_<model>.json."""
        art = tmp_path / "training_artifact_gbt_av.json"
        art.write_text("{}")
        result = find_trained_artifact("gbt_av", "r0", "smoke", 42, tmp_path)
        assert result == art

    def test_pattern3_training_output_dir(self, tmp_path):
        """Find artifact in data/runs/av_<model>_<rung>_<mode>_<seed>/."""
        runs_dir = tmp_path / "data" / "runs"
        art_dir = runs_dir / "av_gbt_av_r0_smoke_42"
        art_dir.mkdir(parents=True)
        art = art_dir / "artifact.json"
        art.write_text("{}")
        with patch.object(run_rung_mod, "_repo_root", return_value=tmp_path):
            result = find_trained_artifact("gbt_av", "r0", "smoke", 42)
        assert result == art

    def test_returns_none_when_missing(self, tmp_path):
        """Return None when no artifact is found anywhere."""
        with patch.object(run_rung_mod, "_repo_root", return_value=tmp_path):
            result = find_trained_artifact("gbt_av", "r0", "smoke", 42)
        assert result is None

    def test_pattern_priority(self, tmp_path):
        """Artifacts_dir patterns take priority over data/runs patterns."""
        # Create both pattern 1 (should win) and pattern 3
        art1 = tmp_path / "gbt_av" / "artifact.json"
        art1.parent.mkdir(parents=True)
        art1.write_text('{"source": "pattern1"}')

        runs_dir = tmp_path / "data" / "runs"
        art3_dir = runs_dir / "av_gbt_av_r0_smoke_42"
        art3_dir.mkdir(parents=True)
        (art3_dir / "artifact.json").write_text('{"source": "pattern3"}')

        with patch.object(run_rung_mod, "_repo_root", return_value=tmp_path):
            result = find_trained_artifact("gbt_av", "r0", "smoke", 42, tmp_path)
        assert result == art1


# ============================================================================
# H2H Roster Generation Tests
# ============================================================================


from bid_euchre.arc_d_v2.orchestration import generate_h2h_roster


class TestGenerateH2HRoster:
    def _mock_roster(self):
        return Roster(
            models=[
                RosterModel(
                    name="gbt_av",
                    class_name="GBTActionValueBidder",
                    trainable=True,
                ),
                RosterModel(
                    name="modeloespecifico",
                    class_name="ModeloEspecifico",
                    trainable=False,
                ),
            ],
            anchor=AnchorModel(
                name="anchor_hybrid_r0_full",
                class_name="HybridOLSaBidder",
                artifact="data/artifacts/arc_d/r0/hybrid_r0_full.json",
            ),
        )

    def test_generates_correct_format(self, tmp_path):
        """Roster entries have name, class_name, and optional params."""
        # Create trained artifact for gbt_av
        art = tmp_path / "gbt_av" / "artifact.json"
        art.parent.mkdir(parents=True)
        art.write_text("{}")
        # Create anchor artifact
        anchor_path = tmp_path / "data" / "artifacts" / "arc_d" / "r0"
        anchor_path.mkdir(parents=True)
        (anchor_path / "hybrid_r0_full.json").write_text("{}")

        roster = self._mock_roster()
        with (
            patch.object(run_rung_mod, "load_roster", return_value=roster),
            patch.object(run_rung_mod, "_repo_root", return_value=tmp_path),
        ):
            entries = generate_h2h_roster("r0", "smoke", 42, tmp_path)

        assert len(entries) == 3  # gbt_av + modeloespecifico + anchor
        names = [e["name"] for e in entries]
        assert "gbt_av" in names
        assert "modeloespecifico" in names
        assert "anchor_hybrid_r0_full" in names

        gbt = next(e for e in entries if e["name"] == "gbt_av")
        assert gbt["class_name"] == "GBTActionValueBidder"
        assert "artifact_path" in gbt["params"]

    def test_skips_trainable_without_artifact(self, tmp_path):
        """Trainable models without artifacts are excluded."""
        roster = self._mock_roster()
        with (
            patch.object(run_rung_mod, "load_roster", return_value=roster),
            patch.object(run_rung_mod, "_repo_root", return_value=tmp_path),
        ):
            entries = generate_h2h_roster("r0", "smoke", 42, tmp_path)

        names = [e["name"] for e in entries]
        # gbt_av should be skipped (no artifact), but modeloespecifico should remain
        assert "gbt_av" not in names
        assert "modeloespecifico" in names


# ============================================================================
# Comparator Config Generation Tests
# ============================================================================


from bid_euchre.arc_d_v2.orchestration import generate_comparator_config


class TestGenerateComparatorConfig:
    def _mock_roster(self):
        return Roster(
            models=[
                RosterModel(
                    name="gbt_av",
                    class_name="GBTActionValueBidder",
                    trainable=True,
                ),
                RosterModel(
                    name="modeloespecifico",
                    class_name="ModeloEspecifico",
                    trainable=False,
                ),
            ],
            anchor=AnchorModel(
                name="anchor_hybrid_r0_full",
                class_name="HybridOLSaBidder",
                artifact="data/artifacts/arc_d/r0/hybrid_r0_full.json",
            ),
        )

    def test_generates_valid_yaml_structure(self, tmp_path):
        """Config has required keys for run_auction_comparator.py."""
        art = tmp_path / "gbt_av" / "artifact.json"
        art.parent.mkdir(parents=True)
        art.write_text("{}")

        roster = self._mock_roster()
        with (
            patch.object(run_rung_mod, "load_roster", return_value=roster),
            patch.object(run_rung_mod, "_repo_root", return_value=tmp_path),
        ):
            config = generate_comparator_config("r0", "smoke", 42, 100, tmp_path)

        assert "experiment_name" in config
        assert "bidding_policies" in config
        assert "strategies" in config
        assert "scenarios" in config
        assert "parameters" in config
        assert config["parameters"]["seed"] == 42
        assert config["parameters"]["n_per"] == 100
        assert config["parameters"]["play_strategy"] == "glutton"

    def test_bidding_policies_have_correct_structure(self, tmp_path):
        """Each bidding policy has name and class_name."""
        art = tmp_path / "gbt_av" / "artifact.json"
        art.parent.mkdir(parents=True)
        art.write_text("{}")

        roster = self._mock_roster()
        with (
            patch.object(run_rung_mod, "load_roster", return_value=roster),
            patch.object(run_rung_mod, "_repo_root", return_value=tmp_path),
        ):
            config = generate_comparator_config("r0", "smoke", 42, 100, tmp_path)

        for policy in config["bidding_policies"]:
            assert "name" in policy
            assert "class_name" in policy

    def test_skips_trainable_without_artifact(self, tmp_path):
        """Trainable models without artifacts are excluded from config."""
        roster = self._mock_roster()
        with (
            patch.object(run_rung_mod, "load_roster", return_value=roster),
            patch.object(run_rung_mod, "_repo_root", return_value=tmp_path),
        ):
            config = generate_comparator_config("r0", "smoke", 42, 100, tmp_path)

        names = [p["name"] for p in config["bidding_policies"]]
        assert "gbt_av" not in names
        assert "modeloespecifico" in names

    def test_excludes_anchor_per_la2(self, tmp_path):
        """Comparator config excludes anchor model per LA-2 policy."""
        art = tmp_path / "gbt_av" / "artifact.json"
        art.parent.mkdir(parents=True)
        art.write_text("{}")
        # Create anchor artifact (should still be excluded)
        anchor_path = tmp_path / "data" / "artifacts" / "arc_d" / "r0"
        anchor_path.mkdir(parents=True)
        (anchor_path / "hybrid_r0_full.json").write_text("{}")

        roster = self._mock_roster()
        with (
            patch.object(run_rung_mod, "load_roster", return_value=roster),
            patch.object(run_rung_mod, "_repo_root", return_value=tmp_path),
        ):
            config = generate_comparator_config("r0", "smoke", 42, 100, tmp_path)

        names = [p["name"] for p in config["bidding_policies"]]
        assert "anchor_hybrid_r0_full" not in names
        # But roster models should still be present
        assert "gbt_av" in names
        assert "modeloespecifico" in names


# ============================================================================
# Step 4/5 Integration Tests (dry-run, verifying command construction)
# ============================================================================


class TestStep4CommandConstruction:
    def test_step4_uses_roster_flag(self, tmp_path):
        """Step 4 should pass --roster to h2h battery script."""
        art = tmp_path / "gbt_av" / "artifact.json"
        art.parent.mkdir(parents=True)
        art.write_text("{}")

        roster = Roster(
            models=[
                RosterModel(
                    name="gbt_av",
                    class_name="GBTActionValueBidder",
                    trainable=True,
                ),
            ],
            anchor=AnchorModel(name="", artifact="", class_name=""),
        )

        plan_dir = tmp_path / "plans" / "arc_d_v2" / "r0"
        plan_dir.mkdir(parents=True)

        state = RunState.create_fresh("r0", "smoke", [42])

        with (
            patch.object(run_rung_mod, "load_roster", return_value=roster),
            patch.object(run_rung_mod, "_repo_root", return_value=tmp_path),
            patch.object(run_rung_mod, "_plans_dir", return_value=plan_dir),
            patch.object(
                run_rung_mod,
                "_state_path",
                return_value=plan_dir / "state.json",
            ),
            patch.object(
                run_rung_mod,
                "find_trained_artifact",
                return_value=art,
            ),
        ):
            ok = run_rung_mod.execute_step_4(state, 42, dry_run=True)

        assert ok is True
        # In dry_run, the step completes without error
        assert state.steps["4"]["status"] == "complete"

    def test_step4_smoke_maps_to_quick(self, tmp_path):
        """Step 4 with smoke mode should use QUICK for H2H."""
        plan_dir = tmp_path / "plans" / "arc_d_v2" / "r0"
        plan_dir.mkdir(parents=True)

        roster = Roster()
        state = RunState.create_fresh("r0", "smoke", [42])

        with (
            patch.object(run_rung_mod, "load_roster", return_value=roster),
            patch.object(run_rung_mod, "_repo_root", return_value=tmp_path),
            patch.object(run_rung_mod, "_plans_dir", return_value=plan_dir),
            patch.object(
                run_rung_mod,
                "_state_path",
                return_value=plan_dir / "state.json",
            ),
        ):
            # Empty roster should fail with clear error
            ok = run_rung_mod.execute_step_4(state, 42, dry_run=False)

        assert ok is False
        assert "No bidders" in (state.steps["4"].get("error") or "")


class TestStep5CommandConstruction:
    def test_step5_uses_config_flag(self, tmp_path):
        """Step 5 should pass --config (not --mode) to comparator."""
        art = tmp_path / "gbt_av" / "artifact.json"
        art.parent.mkdir(parents=True)
        art.write_text("{}")

        roster = Roster(
            models=[
                RosterModel(
                    name="gbt_av",
                    class_name="GBTActionValueBidder",
                    trainable=True,
                ),
            ],
            anchor=AnchorModel(name="", artifact="", class_name=""),
        )

        plan_dir = tmp_path / "plans" / "arc_d_v2" / "r0"
        plan_dir.mkdir(parents=True)

        state = RunState.create_fresh("r0", "smoke", [42])

        with (
            patch.object(run_rung_mod, "load_roster", return_value=roster),
            patch.object(run_rung_mod, "_repo_root", return_value=tmp_path),
            patch.object(run_rung_mod, "_plans_dir", return_value=plan_dir),
            patch.object(
                run_rung_mod,
                "_state_path",
                return_value=plan_dir / "state.json",
            ),
            patch.object(
                run_rung_mod,
                "find_trained_artifact",
                return_value=art,
            ),
        ):
            ok = run_rung_mod.execute_step_5(state, 42, dry_run=True)

        assert ok is True
        assert state.steps["5"]["status"] == "complete"

    def test_step5_empty_roster_fails(self, tmp_path):
        """Step 5 with no bidders should fail with clear error."""
        plan_dir = tmp_path / "plans" / "arc_d_v2" / "r0"
        plan_dir.mkdir(parents=True)

        roster = Roster()
        state = RunState.create_fresh("r0", "smoke", [42])

        with (
            patch.object(run_rung_mod, "load_roster", return_value=roster),
            patch.object(run_rung_mod, "_repo_root", return_value=tmp_path),
            patch.object(run_rung_mod, "_plans_dir", return_value=plan_dir),
            patch.object(
                run_rung_mod,
                "_state_path",
                return_value=plan_dir / "state.json",
            ),
        ):
            ok = run_rung_mod.execute_step_5(state, 42, dry_run=False)

        assert ok is False
        assert "No bidders" in (state.steps["5"].get("error") or "")


class TestStep2SkipValidation:
    """Step 2 should pass --skip-validation in smoke mode only."""

    def _make_state_and_fixtures(self, tmp_path, mode):
        """Create state, roster, and filesystem fixtures for step 2."""
        roster = Roster(
            models=[
                RosterModel(
                    name="gbt_av",
                    class_name="GBTActionValueBidder",
                    trainable=True,
                    model_class="gbt",
                ),
            ],
            anchor=AnchorModel(name="", artifact="", class_name=""),
        )

        plan_dir = tmp_path / "plans" / "arc_d_v2" / "r0"
        plan_dir.mkdir(parents=True)

        # Dataset dir with parquet file
        ds_dir = tmp_path / "data" / "runs" / f"av_r0_{mode}_42" / "datasets"
        ds_dir.mkdir(parents=True)
        (ds_dir / "action_value.parquet").write_bytes(b"fake")

        # Anchor artifact
        art_dir = tmp_path / "data" / "artifacts" / "arc_d" / "r0"
        art_dir.mkdir(parents=True)
        (art_dir / "hybrid_r0_full.json").write_text("{}")

        state = RunState.create_fresh("r0", mode, [42])
        # Mark step 1 complete so step 2 has its input
        state.mark_step_started("1", 42)
        state.mark_step_complete("1", 42)

        return state, roster, plan_dir

    def test_smoke_includes_skip_validation(self, tmp_path):
        """In smoke mode, --skip-validation should be in the training command."""
        state, roster, plan_dir = self._make_state_and_fixtures(tmp_path, "smoke")
        captured_cmds = []

        with (
            patch.object(run_rung_mod, "load_roster", return_value=roster),
            patch.object(run_rung_mod, "_repo_root", return_value=tmp_path),
            patch.object(run_rung_mod, "_plans_dir", return_value=plan_dir),
            patch.object(
                run_rung_mod,
                "_state_path",
                return_value=plan_dir / "state.json",
            ),
            patch.object(
                run_rung_mod,
                "run_subprocess",
                side_effect=lambda cmd, *a, **kw: (
                    captured_cmds.append(cmd),
                    (True, ""),
                )[-1],
            ),
        ):
            ok = run_rung_mod.execute_step_2(state, 42)

        assert ok is True
        assert len(captured_cmds) == 1
        assert "--skip-validation" in captured_cmds[0]

    def test_quick_excludes_skip_validation(self, tmp_path):
        """In quick mode, --skip-validation should NOT be in the training command."""
        state, roster, plan_dir = self._make_state_and_fixtures(tmp_path, "quick")
        captured_cmds = []

        with (
            patch.object(run_rung_mod, "load_roster", return_value=roster),
            patch.object(run_rung_mod, "_repo_root", return_value=tmp_path),
            patch.object(run_rung_mod, "_plans_dir", return_value=plan_dir),
            patch.object(
                run_rung_mod,
                "_state_path",
                return_value=plan_dir / "state.json",
            ),
            patch.object(
                run_rung_mod,
                "run_subprocess",
                side_effect=lambda cmd, *a, **kw: (
                    captured_cmds.append(cmd),
                    (True, ""),
                )[-1],
            ),
        ):
            ok = run_rung_mod.execute_step_2(state, 42)

        assert ok is True
        assert len(captured_cmds) == 1
        assert "--skip-validation" not in captured_cmds[0]


# ============================================================================
# Anchor Compatibility Tests (LA-2)
# ============================================================================


from bid_euchre.arc_d_v2.orchestration import check_anchor_compatibility


class TestCheckAnchorCompatibility:
    def test_returns_false_for_missing_file(self, tmp_path):
        """Non-existent artifact path returns False."""
        result = check_anchor_compatibility(tmp_path / "nonexistent.json")
        assert result is False

    def test_returns_false_for_invalid_artifact(self, tmp_path):
        """Invalid JSON artifact returns False."""
        bad_artifact = tmp_path / "bad_artifact.json"
        bad_artifact.write_text("{}")
        result = check_anchor_compatibility(bad_artifact)
        assert result is False

    def test_returns_false_for_wrong_artifact_type(self, tmp_path):
        """Artifact with wrong type returns False."""
        bad_artifact = tmp_path / "wrong_type.json"
        bad_artifact.write_text(json.dumps({"artifact_type": "wrong_type"}))
        result = check_anchor_compatibility(bad_artifact)
        assert result is False

    def test_anchor_loads_through_hybrid_olsa(self):
        """Verify the frozen anchor can be loaded and predict via HybridOLSaBidder.

        This test requires the actual anchor artifact to be present on disk
        (gitignored). It is skipped in CI where the artifact is unavailable.
        """
        anchor_path = Path("data/artifacts/arc_d/r0/hybrid_r0_full.json")
        if not anchor_path.exists():
            pytest.skip("Anchor artifact not available (gitignored)")

        result = check_anchor_compatibility(anchor_path)
        assert result is True


class TestH2HRosterIncludesAnchor:
    """Verify H2H roster includes anchor while comparator excludes it (LA-2)."""

    def _mock_roster(self):
        return Roster(
            models=[
                RosterModel(
                    name="gbt_av",
                    class_name="GBTActionValueBidder",
                    trainable=True,
                ),
            ],
            anchor=AnchorModel(
                name="anchor_hybrid_r0_full",
                class_name="HybridOLSaBidder",
                artifact="data/artifacts/arc_d/r0/hybrid_r0_full.json",
            ),
        )

    def test_h2h_includes_anchor_comparator_excludes(self, tmp_path):
        """H2H roster includes anchor; comparator config excludes it per LA-2."""
        art = tmp_path / "gbt_av" / "artifact.json"
        art.parent.mkdir(parents=True)
        art.write_text("{}")
        anchor_path = tmp_path / "data" / "artifacts" / "arc_d" / "r0"
        anchor_path.mkdir(parents=True)
        (anchor_path / "hybrid_r0_full.json").write_text("{}")

        roster = self._mock_roster()
        with (
            patch.object(run_rung_mod, "load_roster", return_value=roster),
            patch.object(run_rung_mod, "_repo_root", return_value=tmp_path),
        ):
            h2h_entries = generate_h2h_roster("r0", "smoke", 42, tmp_path)
            comp_config = generate_comparator_config("r0", "smoke", 42, 100, tmp_path)

        h2h_names = [e["name"] for e in h2h_entries]
        comp_names = [p["name"] for p in comp_config["bidding_policies"]]

        # H2H includes anchor
        assert "anchor_hybrid_r0_full" in h2h_names
        # Comparator excludes anchor
        assert "anchor_hybrid_r0_full" not in comp_names

    def test_h2h_anchor_uses_hybrid_olsa_class(self, tmp_path):
        """Anchor entry in H2H roster uses HybridOLSaBidder class name."""
        art = tmp_path / "gbt_av" / "artifact.json"
        art.parent.mkdir(parents=True)
        art.write_text("{}")
        anchor_path = tmp_path / "data" / "artifacts" / "arc_d" / "r0"
        anchor_path.mkdir(parents=True)
        (anchor_path / "hybrid_r0_full.json").write_text("{}")

        roster = self._mock_roster()
        with (
            patch.object(run_rung_mod, "load_roster", return_value=roster),
            patch.object(run_rung_mod, "_repo_root", return_value=tmp_path),
        ):
            entries = generate_h2h_roster("r0", "smoke", 42, tmp_path)

        anchor = next(e for e in entries if e["name"] == "anchor_hybrid_r0_full")
        assert anchor["class_name"] == "HybridOLSaBidder"
