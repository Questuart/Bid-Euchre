"""Unit tests for the Arc D v2 package: schemas, paths, and config.

Tests are fixture-based — no real experiment runs or files required.
All file I/O uses tmp_path.
"""

import json
from pathlib import Path

import pytest

from bid_euchre.arc_d_v2 import paths
from bid_euchre.arc_d_v2.config import (
    MODES,
    AnchorModel,
    Roster,
    RosterModel,
    RungConfig,
)
from bid_euchre.arc_d_v2.schemas import (
    VALID_ADVANCE_DECISIONS,
    VALID_STEP_STATUSES,
    AdvanceCheck,
    BestInLineage,
    CheckResult,
    HypothesesFile,
    Hypothesis,
    HypothesisBound,
    HypothesisCheckResult,
    NextAction,
    RunState,
    TimeoutPolicy,
)

# =============================================================================
# Path tests
# =============================================================================


def _ends_with(p: Path, suffix: str) -> bool:
    """Check that an absolute path ends with the expected repo-relative suffix."""
    return p.is_absolute() and str(p).endswith(suffix)


class TestPaths:
    """Verify path construction returns absolute paths with expected suffixes."""

    def test_all_root_paths_are_absolute(self):
        assert paths.PLANS_ROOT.is_absolute()
        assert paths.REPORTS_ROOT.is_absolute()
        assert paths.RUNS_ROOT.is_absolute()

    def test_lineage_root_paths(self):
        assert _ends_with(paths.PLANS_ROOT, "plans/arc_d_v2")
        assert _ends_with(paths.REPORTS_ROOT, "docs/04_reports/arc_d_v2")
        assert _ends_with(paths.RUNS_ROOT, "data/runs/arc_d_v2")

    def test_lineage_level_files(self):
        assert _ends_with(paths.LINEAGE_PLAN, "plans/arc_d_v2/lineage_plan.md")
        assert _ends_with(paths.LINEAGE_ROSTER, "plans/arc_d_v2/roster.json")
        assert _ends_with(paths.LINEAGE_AMENDMENTS, "plans/arc_d_v2/amendments.md")
        assert _ends_with(
            paths.SUB_PLAN_REGISTRY, "plans/arc_d_v2/sub_plan_registry.md"
        )
        assert _ends_with(
            paths.CROSS_RUNG_DELTAS, "docs/04_reports/arc_d_v2/cross_rung_deltas.csv"
        )

    def test_anchor_artifact(self):
        assert _ends_with(
            paths.ANCHOR_ARTIFACT, "data/artifacts/arc_d/r0/hybrid_r0_full.json"
        )

    def test_rung_plan_dir(self):
        assert _ends_with(paths.rung_plan_dir("r2.0"), "plans/arc_d_v2/r2.0")

    def test_rung_plan(self):
        assert _ends_with(paths.rung_plan("r2.0"), "plans/arc_d_v2/r2.0/plan.md")

    def test_rung_hypotheses(self):
        assert _ends_with(
            paths.rung_hypotheses("r2.0"), "plans/arc_d_v2/r2.0/hypotheses.json"
        )

    def test_rung_checkpoints(self):
        assert _ends_with(
            paths.rung_checkpoints("r2.0"), "plans/arc_d_v2/r2.0/checkpoints.md"
        )

    def test_rung_state(self):
        assert _ends_with(paths.rung_state("r2.0"), "plans/arc_d_v2/r2.0/state.json")

    def test_rung_execution_log(self):
        assert _ends_with(
            paths.rung_execution_log("r2.0"),
            "plans/arc_d_v2/r2.0/execution_log.jsonl",
        )

    def test_rung_run_dir(self):
        assert _ends_with(paths.rung_run_dir("r2.0"), "data/runs/arc_d_v2/r2.0")

    def test_seed_dir(self):
        result = paths.seed_dir("r2.0", "quick", 42)
        assert _ends_with(result, "data/runs/arc_d_v2/r2.0/quick/seed_42")

    def test_seed_dataset(self):
        result = paths.seed_dataset("r2.0", "smoke", 42)
        assert _ends_with(
            result,
            "data/runs/arc_d_v2/r2.0/smoke/seed_42/datasets/action_value.parquet",
        )

    def test_seed_artifacts_dir(self):
        result = paths.seed_artifacts_dir("r2.0", "full", 123)
        assert _ends_with(result, "data/runs/arc_d_v2/r2.0/full/seed_123/artifacts")

    def test_model_artifact(self):
        result = paths.model_artifact("r2.0", "quick", 42, "gbt_full")
        assert _ends_with(
            result,
            "data/runs/arc_d_v2/r2.0/quick/seed_42/artifacts/gbt_full/artifact.json",
        )

    def test_seed_h2h_dir(self):
        result = paths.seed_h2h_dir("r2.0", "full", 456)
        assert _ends_with(result, "data/runs/arc_d_v2/r2.0/full/seed_456/h2h")

    def test_seed_comparator_dir(self):
        result = paths.seed_comparator_dir("r2.0", "quick", 42)
        assert _ends_with(result, "data/runs/arc_d_v2/r2.0/quick/seed_42/comparator")

    def test_rung_report_dir(self):
        assert _ends_with(
            paths.rung_report_dir("r2.0"), "docs/04_reports/arc_d_v2/r2.0"
        )

    def test_rung_tables_dir(self):
        assert _ends_with(
            paths.rung_tables_dir("r2.0"), "docs/04_reports/arc_d_v2/r2.0/tables"
        )

    def test_rung_charts_dir(self):
        assert _ends_with(
            paths.rung_charts_dir("r2.0"), "docs/04_reports/arc_d_v2/r2.0/charts"
        )

    def test_rung_chart_data_dir(self):
        assert _ends_with(
            paths.rung_chart_data_dir("r2.0"),
            "docs/04_reports/arc_d_v2/r2.0/chart_data",
        )

    def test_advance_check_path(self):
        result = paths.advance_check_path("r2.0", "quick")
        assert _ends_with(result, "data/runs/arc_d_v2/r2.0/advance_check_quick.json")

    def test_evidence_manifest_path(self):
        result = paths.evidence_manifest_path("r2.0")
        assert _ends_with(
            result, "docs/04_reports/arc_d_v2/r2.0/evidence_manifest.json"
        )

    def test_step_log_path_no_detail(self):
        result = paths.step_log_path("r2.0", "3")
        assert _ends_with(result, "plans/arc_d_v2/r2.0/logs/step_3.log")

    def test_step_log_path_with_detail(self):
        result = paths.step_log_path("r2.0", "3", "gbt_full")
        assert _ends_with(result, "plans/arc_d_v2/r2.0/logs/step_3_gbt_full.log")


# =============================================================================
# RunState tests
# =============================================================================


class TestRunState:
    """Test RunState creation, save, and load roundtrip.

    Note: The canonical RunState (merged from rung_state.py) uses string keys
    for per_seed and dict-based step storage (not typed SeedStepStatus).
    """

    def test_create_fresh(self):
        state = RunState.create_fresh("r2.0", "quick", [42])
        assert state.rung == "r2.0"
        assert state.mode == "quick"
        assert state.seeds == [42]
        assert state.current_step == "0"
        assert state.step_status == "not_started"
        assert "42" in state.per_seed
        # All steps should be in per_seed (operational RunState tracks all steps)
        from bid_euchre.arc_d_v2.schemas import STEPS

        assert set(state.per_seed["42"].keys()) == set(STEPS)
        for step_data in state.per_seed["42"].values():
            assert step_data["status"] == "pending"

    def test_create_fresh_multi_seed(self):
        state = RunState.create_fresh("r2.0", "full", [42, 123, 456])
        assert state.seeds == [42, 123, 456]
        assert set(state.per_seed.keys()) == {"42", "123", "456"}

    def test_save_load_roundtrip(self, tmp_path: Path):
        state = RunState.create_fresh("r2.0", "quick", [42])
        state.current_step = "2"
        state.step_status = "in_progress"
        state.status_detail = "Training models"

        # Use the operational API to set model status
        state.update_model("2", "gbt_full", 42, "complete")

        path = tmp_path / "state.json"
        state.save(path)

        loaded = RunState.load(path)
        assert loaded.rung == "r2.0"
        assert loaded.mode == "quick"
        assert loaded.current_step == "2"
        assert loaded.step_status == "in_progress"
        assert loaded.status_detail == "Training models"
        assert loaded.model_status(42, "2", "gbt_full") == "complete"

    def test_save_load_with_blocker(self, tmp_path: Path):
        state = RunState.create_fresh("r2.0", "smoke", [42])
        state.blocker = "make check failed"
        state.active_investigation = "ruff format issue"

        path = tmp_path / "state.json"
        state.save(path)

        loaded = RunState.load(path)
        assert loaded.blocker == "make check failed"
        assert loaded.active_investigation == "ruff format issue"

    def test_save_creates_parent_dirs(self, tmp_path: Path):
        state = RunState.create_fresh("r2.0", "smoke", [42])
        path = tmp_path / "nested" / "dir" / "state.json"
        state.save(path)
        assert path.exists()

    def test_per_seed_tracking(self):
        state = RunState.create_fresh("r2.0", "quick", [42, 123])
        # Use the operational API to update
        state.mark_step_complete("1", seed=42)
        # Other seed untouched
        assert state.per_seed["123"]["1"]["status"] == "pending"
        assert state.per_seed["42"]["1"]["status"] == "complete"


# =============================================================================
# Hypothesis tests
# =============================================================================


class TestHypotheses:
    """Test hypothesis file save/load roundtrip."""

    def _sample_hypotheses(self) -> HypothesesFile:
        return HypothesesFile(
            rung="r2.0",
            hypotheses=[
                Hypothesis(
                    id="H1",
                    description="GBT pooled delta > 0",
                    metric="net_eppd",
                    source_table="h2h_summary",
                    source_column="pooled_net_eppd",
                    source_filter={"model": "gbt_full"},
                    anchor_filter={"model": "hybrid_r0"},
                    computation="value - anchor_value",
                    expected_bound=HypothesisBound(">", 0.0),
                    surprise_if=HypothesisBound("<", -0.5),
                ),
                Hypothesis(
                    id="H2",
                    description="Suit delta positive",
                    metric="suit_net_eppd",
                    source_table="h2h_by_contract",
                    source_column="net_eppd",
                    source_filter={"model": "gbt_full", "contract_type": "suit"},
                    expected_bound=HypothesisBound(">", 0.0),
                    surprise_if=HypothesisBound("<", -1.0),
                ),
            ],
        )

    def test_save_load_roundtrip(self, tmp_path: Path):
        original = self._sample_hypotheses()
        path = tmp_path / "hypotheses.json"
        original.save(path)

        loaded = HypothesesFile.load(path)
        assert loaded.schema_version == "hypotheses_v1"
        assert loaded.rung == "r2.0"
        assert len(loaded.hypotheses) == 2

        h1 = loaded.hypotheses[0]
        assert h1.id == "H1"
        assert h1.metric == "net_eppd"
        assert h1.expected_bound.op == ">"
        assert h1.expected_bound.value == 0.0
        assert h1.surprise_if.op == "<"
        assert h1.surprise_if.value == -0.5
        assert h1.anchor_filter == {"model": "hybrid_r0"}

    def test_empty_hypotheses(self, tmp_path: Path):
        empty = HypothesesFile(rung="r2.0")
        path = tmp_path / "empty.json"
        empty.save(path)
        loaded = HypothesesFile.load(path)
        assert loaded.hypotheses == []


# =============================================================================
# AdvanceCheck tests
# =============================================================================


class TestAdvanceCheck:
    """Test AdvanceCheck, especially pass_/pass renaming and all_pass."""

    def _make_check(self, *, all_passing: bool = True) -> AdvanceCheck:
        return AdvanceCheck(
            rung="r2.0",
            mode="quick",
            advance_decision="PROCEED",
            reason="All gates pass",
            timestamp="2026-03-13T10:00:00Z",
            next_action=NextAction(command="run full", prerequisite="quick complete"),
            hypothesis_checks=[
                HypothesisCheckResult(
                    id="H1",
                    description="Pooled delta > 0",
                    expected_bound="> 0.0",
                    observed=0.57,
                    pass_=all_passing,
                    surprise_threshold="< -0.5",
                    surprise_hit=False,
                ),
            ],
            sufficiency_checks=[
                CheckResult(
                    id="S1",
                    pass_=all_passing,
                    value="50000",
                    detail="n_deals sufficient",
                    level="GATE",
                ),
            ],
            canary_checks=[
                CheckResult(
                    id="CAN1",
                    pass_=True,
                    value="0.03",
                    detail="self-play bias",
                    level="WARNING",
                ),
            ],
            best_in_lineage=BestInLineage(
                model="gbt_full", pooled_net_eppd=0.57, updated=True
            ),
        )

    def test_all_pass_true(self):
        check = self._make_check(all_passing=True)
        assert check.all_pass is True

    def test_all_pass_false_hypothesis(self):
        check = self._make_check(all_passing=False)
        assert check.all_pass is False

    def test_all_pass_false_surprise(self):
        check = self._make_check(all_passing=True)
        check.hypothesis_checks[0].surprise_hit = True
        assert check.all_pass is False

    def test_all_pass_false_sufficiency(self):
        check = self._make_check(all_passing=True)
        check.sufficiency_checks[0].pass_ = False
        assert check.all_pass is False

    def test_all_pass_empty_checks(self):
        check = AdvanceCheck()
        assert check.all_pass is True  # vacuously true

    def test_save_load_roundtrip(self, tmp_path: Path):
        original = self._make_check()
        path = tmp_path / "advance_check.json"
        original.save(path)

        # Verify JSON uses "pass" not "pass_"
        raw = json.loads(path.read_text())
        assert "pass" in raw["hypothesis_checks"][0]
        assert "pass_" not in raw["hypothesis_checks"][0]
        assert "pass" in raw["sufficiency_checks"][0]

        loaded = AdvanceCheck.load(path)
        assert loaded.rung == "r2.0"
        assert loaded.mode == "quick"
        assert loaded.advance_decision == "PROCEED"
        assert loaded.hypothesis_checks[0].pass_ is True
        assert loaded.hypothesis_checks[0].observed == 0.57
        assert loaded.sufficiency_checks[0].pass_ is True
        assert loaded.canary_checks[0].level == "WARNING"
        assert loaded.best_in_lineage is not None
        assert loaded.best_in_lineage.model == "gbt_full"
        assert loaded.next_action.command == "run full"
        assert loaded.all_pass is True

    def test_load_without_best_in_lineage(self, tmp_path: Path):
        check = self._make_check()
        check.best_in_lineage = None
        path = tmp_path / "no_best.json"
        check.save(path)

        loaded = AdvanceCheck.load(path)
        assert loaded.best_in_lineage is None


# =============================================================================
# Roster tests
# =============================================================================


class TestRoster:
    """Test roster load, save, and filtering methods."""

    def _sample_roster_json(self) -> dict:
        return {
            "schema_version": "roster_v1",
            "lineage_id": "arc_d_v2",
            "models": [
                {
                    "name": "gbt_full",
                    "class": "GBTActionValueBidder",
                    "trainable": True,
                    "model_class": "gbt",
                    "feature_set": "full",
                    "selection": "forward",
                },
                {
                    "name": "ols_constrained",
                    "class": "OLSActionValueBidder",
                    "trainable": True,
                    "model_class": "ols",
                    "feature_set": "constrained",
                },
                {
                    "name": "strict_hellraiser",
                    "class": "StrictHellraiserBidder",
                    "trainable": False,
                    "category": "heuristic",
                },
                {
                    "name": "excluded_model",
                    "class": "SomeExcluded",
                    "trainable": True,
                    "status": "excluded",
                },
            ],
            "anchor": {
                "name": "hybrid_r0",
                "artifact": "data/artifacts/arc_d/r0/hybrid_r0_full.json",
                "class": "HybridOLSaBidder",
            },
        }

    def test_load_from_json(self, tmp_path: Path):
        path = tmp_path / "roster.json"
        path.write_text(json.dumps(self._sample_roster_json()))

        roster = Roster.load(path)
        assert roster.schema_version == "roster_v1"
        assert roster.lineage_id == "arc_d_v2"
        assert len(roster.models) == 4
        assert roster.anchor.name == "hybrid_r0"
        assert roster.anchor.class_name == "HybridOLSaBidder"

    def test_trainable_models(self, tmp_path: Path):
        path = tmp_path / "roster.json"
        path.write_text(json.dumps(self._sample_roster_json()))

        roster = Roster.load(path)
        trainable = roster.trainable_models()
        assert len(trainable) == 2
        names = {m.name for m in trainable}
        assert names == {"gbt_full", "ols_constrained"}

    def test_all_active_models(self, tmp_path: Path):
        path = tmp_path / "roster.json"
        path.write_text(json.dumps(self._sample_roster_json()))

        roster = Roster.load(path)
        active = roster.all_active_models()
        assert len(active) == 3
        names = {m.name for m in active}
        assert "excluded_model" not in names
        assert "strict_hellraiser" in names

    def test_save_load_roundtrip(self, tmp_path: Path):
        path = tmp_path / "roster.json"
        path.write_text(json.dumps(self._sample_roster_json()))

        roster = Roster.load(path)
        out_path = tmp_path / "roster_out.json"
        roster.save(out_path)

        reloaded = Roster.load(out_path)
        assert len(reloaded.models) == 4
        assert reloaded.anchor.name == "hybrid_r0"

        # Verify trainable filtering is preserved
        assert len(reloaded.trainable_models()) == 2

    def test_save_creates_parent_dirs(self, tmp_path: Path):
        roster = Roster(
            models=[
                RosterModel(
                    name="test_model",
                    class_name="TestBidder",
                    trainable=True,
                )
            ],
            anchor=AnchorModel(name="anchor", artifact="a.json", class_name="A"),
        )
        path = tmp_path / "nested" / "dir" / "roster.json"
        roster.save(path)
        assert path.exists()

    def test_default_fields(self):
        m = RosterModel(name="x", class_name="X", trainable=True)
        assert m.model_class == ""
        assert m.feature_set == ""
        assert m.selection == "none"
        assert m.category == ""
        assert m.status == "active"


# =============================================================================
# RungConfig tests
# =============================================================================


class TestRungConfig:
    """Test RungConfig creation for each mode."""

    def _minimal_roster(self) -> Roster:
        return Roster(
            models=[
                RosterModel(name="m1", class_name="M1", trainable=True),
            ],
            anchor=AnchorModel(name="a", artifact="a.json", class_name="A"),
        )

    def test_smoke_mode(self):
        cfg = RungConfig.create("r2.0", "smoke", self._minimal_roster())
        assert cfg.rung == "r2.0"
        assert cfg.mode == "smoke"
        assert cfg.seeds == [42]
        assert cfg.deals == 50

    def test_quick_mode(self):
        cfg = RungConfig.create("r2.0", "quick", self._minimal_roster())
        assert cfg.seeds == [42]
        assert cfg.deals == 2500

    def test_full_mode(self):
        cfg = RungConfig.create("r2.0", "full", self._minimal_roster())
        assert cfg.seeds == [42, 123, 456]
        assert cfg.deals == 50000

    def test_custom_seeds(self):
        cfg = RungConfig.create(
            "r2.0", "quick", self._minimal_roster(), seeds=[7, 8, 9]
        )
        assert cfg.seeds == [7, 8, 9]
        # deals still come from mode default
        assert cfg.deals == 2500

    def test_continuation_artifact(self):
        cfg = RungConfig.create("r2.0", "smoke", self._minimal_roster())
        assert cfg.continuation_artifact == Path(
            "data/artifacts/arc_d/r0/hybrid_r0_full.json"
        )

    def test_invalid_mode(self):
        with pytest.raises(ValueError, match="Unknown mode"):
            RungConfig.create("r2.0", "invalid", self._minimal_roster())


# =============================================================================
# Constants tests
# =============================================================================


class TestConstants:
    """Verify status and decision constants."""

    def test_valid_step_statuses(self):
        expected = {
            "pending",
            "in_progress",
            "complete",
            "partial",
            "failed_retryable",
            "failed_blocking",
            "skipped",
        }
        assert VALID_STEP_STATUSES == expected

    def test_valid_advance_decisions(self):
        assert VALID_ADVANCE_DECISIONS == {"PROCEED", "INVESTIGATE", "PAUSE"}

    def test_modes_contract(self):
        assert set(MODES.keys()) == {"smoke", "quick", "full"}
        for mode_name, spec in MODES.items():
            assert "deals" in spec, f"{mode_name} missing deals"
            assert "seeds" in spec, f"{mode_name} missing seeds"
            assert isinstance(spec["deals"], int)
            assert isinstance(spec["seeds"], list)


# =============================================================================
# TimeoutPolicy tests
# =============================================================================


class TestTimeoutPolicy:
    """Test TimeoutPolicy defaults and step override lookup."""

    def test_defaults(self):
        tp = TimeoutPolicy()
        assert tp.default == 3600
        assert tp.heartbeat_interval == 60
        assert tp.stale_threshold == 300

    def test_step_overrides_present(self):
        tp = TimeoutPolicy()
        assert tp.step_overrides["1"] == 1800
        assert tp.step_overrides["2"] == 7200
        assert tp.step_overrides["4"] == 3600
        assert tp.step_overrides["5"] == 3600
        assert tp.step_overrides["3b"] == 1800

    def test_get_timeout_override(self):
        tp = TimeoutPolicy()
        assert tp.get_timeout("2") == 7200
        assert tp.get_timeout("3b") == 1800

    def test_get_timeout_default_fallback(self):
        tp = TimeoutPolicy()
        # Steps not in overrides should return the default
        assert tp.get_timeout("0") == 3600
        assert tp.get_timeout("3") == 3600
        assert tp.get_timeout("6") == 3600
        assert tp.get_timeout("9") == 3600

    def test_custom_policy(self):
        tp = TimeoutPolicy(
            default=600,
            step_overrides={"1": 120},
            heartbeat_interval=30,
            stale_threshold=120,
        )
        assert tp.get_timeout("1") == 120
        assert tp.get_timeout("2") == 600
        assert tp.heartbeat_interval == 30
        assert tp.stale_threshold == 120

    def test_runstate_has_timeout_policy(self):
        state = RunState.create_fresh("r2.0", "quick", [42])
        assert isinstance(state.timeout_policy, TimeoutPolicy)
        assert state.timeout_policy.default == 3600

    def test_timeout_policy_roundtrip(self, tmp_path: Path):
        state = RunState.create_fresh("r2.0", "quick", [42])
        state.timeout_policy = TimeoutPolicy(
            default=1200,
            step_overrides={"1": 300},
            heartbeat_interval=30,
            stale_threshold=120,
        )
        path = tmp_path / "state.json"
        state.save(path)

        loaded = RunState.load(path)
        assert loaded.timeout_policy.default == 1200
        assert loaded.timeout_policy.step_overrides == {"1": 300}
        assert loaded.timeout_policy.heartbeat_interval == 30
        assert loaded.timeout_policy.stale_threshold == 120

    def test_timeout_policy_missing_from_json(self, tmp_path: Path):
        """Loading a state.json without timeout_policy should use defaults."""
        state = RunState.create_fresh("r2.0", "quick", [42])
        path = tmp_path / "state.json"
        state.save(path)

        # Remove timeout_policy from the JSON
        data = json.loads(path.read_text())
        data.pop("timeout_policy", None)
        path.write_text(json.dumps(data, indent=2))

        loaded = RunState.load(path)
        assert isinstance(loaded.timeout_policy, TimeoutPolicy)
        assert loaded.timeout_policy.default == 3600


# =============================================================================
# Heartbeat path test
# =============================================================================


class TestHeartbeatPath:
    """Test heartbeat path construction."""

    def test_rung_heartbeat_path(self):
        assert _ends_with(paths.rung_heartbeat("r0"), "plans/arc_d_v2/r0/heartbeat")
        assert _ends_with(paths.rung_heartbeat("r2.0"), "plans/arc_d_v2/r2.0/heartbeat")
