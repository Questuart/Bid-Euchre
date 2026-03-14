"""Unit tests for artifact lifecycle management.

Tests are fixture-based — all file I/O uses tmp_path.
"""

from __future__ import annotations

import json
import re

import pytest

from bid_euchre.arc_d_v2.lifecycle import (
    VALID_STATUSES,
    ArtifactStatus,
    RerunManifest,
    generate_run_id,
    get_status,
    is_active,
    list_runs,
    mark_canonical,
    mark_quarantined,
    mark_superseded,
    prune_superseded,
    supersede_run,
)

# ── generate_run_id ──────────────────────────────────────────────────────


class TestGenerateRunId:
    """Test run ID generation matches the section 18 naming contract."""

    def test_format_matches_convention(self):
        run_id = generate_run_id("r0", "smoke", 42)
        # Pattern: arc_d_v2_<rung>_<mode>_seed<N>_<YYYYMMDDTHHMMSSZ>
        pattern = r"^arc_d_v2_r0_smoke_seed42_\d{8}T\d{6}Z$"
        assert re.match(pattern, run_id), f"Run ID {run_id!r} does not match pattern"

    def test_different_params_produce_different_ids(self):
        id1 = generate_run_id("r0", "smoke", 42)
        id2 = generate_run_id("r1", "quick", 123)
        assert "r0_smoke_seed42" in id1
        assert "r1_quick_seed123" in id2

    def test_contains_all_components(self):
        run_id = generate_run_id("r2.0", "full", 456)
        assert "arc_d_v2" in run_id
        assert "r2.0" in run_id
        assert "full" in run_id
        assert "seed456" in run_id


# ── ArtifactStatus validation ────────────────────────────────────────────


class TestArtifactStatus:
    """Test ArtifactStatus dataclass validation."""

    def test_valid_status_accepted(self):
        for status_name in VALID_STATUSES:
            s = ArtifactStatus(
                status=status_name,
                run_id="test_run",
                timestamp="2026-01-01T00:00:00Z",
            )
            assert s.status == status_name

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError, match="Invalid status"):
            ArtifactStatus(
                status="bogus",
                run_id="test_run",
                timestamp="2026-01-01T00:00:00Z",
            )

    def test_optional_fields_default_to_none(self):
        s = ArtifactStatus(
            status="canonical",
            run_id="test_run",
            timestamp="2026-01-01T00:00:00Z",
        )
        assert s.superseded_by is None
        assert s.supersedes is None
        assert s.quarantine_reason is None
        assert s.notes == ""


# ── mark_superseded ──────────────────────────────────────────────────────


class TestMarkSuperseded:
    """Test marking a run as superseded."""

    def test_writes_status_json(self, tmp_path):
        run_dir = tmp_path / "old_run"
        run_dir.mkdir()
        mark_superseded(run_dir, "new_run_id")

        status_path = run_dir / "status.json"
        assert status_path.exists()

        data = json.loads(status_path.read_text())
        assert data["status"] == "superseded"
        assert data["superseded_by"] == "new_run_id"
        assert data["run_id"] == "old_run"
        assert data["timestamp"]  # Non-empty

    def test_preserves_run_directory(self, tmp_path):
        run_dir = tmp_path / "old_run"
        run_dir.mkdir()
        (run_dir / "artifact.json").write_text("{}")
        mark_superseded(run_dir, "new_run_id")

        # Directory and contents still exist
        assert run_dir.exists()
        assert (run_dir / "artifact.json").exists()


# ── mark_quarantined ─────────────────────────────────────────────────────


class TestMarkQuarantined:
    """Test marking a run as quarantined."""

    def test_writes_status_json_with_reason(self, tmp_path):
        run_dir = tmp_path / "bad_run"
        run_dir.mkdir()
        mark_quarantined(run_dir, "corrupt training data")

        data = json.loads((run_dir / "status.json").read_text())
        assert data["status"] == "quarantined"
        assert data["quarantine_reason"] == "corrupt training data"
        assert data["run_id"] == "bad_run"


# ── mark_canonical ───────────────────────────────────────────────────────


class TestMarkCanonical:
    """Test marking a run as canonical."""

    def test_writes_status_json(self, tmp_path):
        run_dir = tmp_path / "good_run"
        run_dir.mkdir()
        mark_canonical(run_dir)

        data = json.loads((run_dir / "status.json").read_text())
        assert data["status"] == "canonical"
        assert data["run_id"] == "good_run"


# ── get_status ───────────────────────────────────────────────────────────


class TestGetStatus:
    """Test reading status from run directories."""

    def test_returns_none_for_no_marker(self, tmp_path):
        run_dir = tmp_path / "unmarked"
        run_dir.mkdir()
        assert get_status(run_dir) is None

    def test_reads_canonical_status(self, tmp_path):
        run_dir = tmp_path / "good_run"
        run_dir.mkdir()
        mark_canonical(run_dir)

        status = get_status(run_dir)
        assert status is not None
        assert status.status == "canonical"
        assert status.run_id == "good_run"

    def test_reads_superseded_status(self, tmp_path):
        run_dir = tmp_path / "old_run"
        run_dir.mkdir()
        mark_superseded(run_dir, "new_run")

        status = get_status(run_dir)
        assert status is not None
        assert status.status == "superseded"
        assert status.superseded_by == "new_run"

    def test_reads_quarantined_status(self, tmp_path):
        run_dir = tmp_path / "bad_run"
        run_dir.mkdir()
        mark_quarantined(run_dir, "data corruption")

        status = get_status(run_dir)
        assert status is not None
        assert status.status == "quarantined"
        assert status.quarantine_reason == "data corruption"


# ── is_active ────────────────────────────────────────────────────────────


class TestIsActive:
    """Test active status checking."""

    def test_unmarked_is_active(self, tmp_path):
        run_dir = tmp_path / "unmarked"
        run_dir.mkdir()
        assert is_active(run_dir) is True

    def test_canonical_is_active(self, tmp_path):
        run_dir = tmp_path / "canonical"
        run_dir.mkdir()
        mark_canonical(run_dir)
        assert is_active(run_dir) is True

    def test_exploratory_is_active(self, tmp_path):
        run_dir = tmp_path / "exploratory"
        run_dir.mkdir()
        (run_dir / "status.json").write_text(
            json.dumps(
                {
                    "status": "exploratory",
                    "run_id": "exploratory",
                    "timestamp": "2026-01-01T00:00:00Z",
                }
            )
        )
        assert is_active(run_dir) is True

    def test_superseded_is_not_active(self, tmp_path):
        run_dir = tmp_path / "old"
        run_dir.mkdir()
        mark_superseded(run_dir, "new")
        assert is_active(run_dir) is False

    def test_quarantined_is_not_active(self, tmp_path):
        run_dir = tmp_path / "bad"
        run_dir.mkdir()
        mark_quarantined(run_dir, "bad data")
        assert is_active(run_dir) is False

    def test_archived_is_not_active(self, tmp_path):
        run_dir = tmp_path / "archived"
        run_dir.mkdir()
        (run_dir / "status.json").write_text(
            json.dumps(
                {
                    "status": "archived",
                    "run_id": "archived",
                    "timestamp": "2026-01-01T00:00:00Z",
                }
            )
        )
        assert is_active(run_dir) is False


# ── supersede_run ────────────────────────────────────────────────────────


class TestSupersedeRun:
    """Test full supersession workflow."""

    def test_marks_old_run_and_creates_manifest(self, tmp_path):
        old_dir = tmp_path / "old_run"
        new_dir = tmp_path / "new_run"
        old_dir.mkdir()
        new_dir.mkdir()

        manifest = supersede_run(old_dir, new_dir)

        # Old run marked superseded
        old_status = get_status(old_dir)
        assert old_status is not None
        assert old_status.status == "superseded"
        assert old_status.superseded_by == "new_run"

        # Manifest created in new dir
        manifest_path = new_dir / "rerun_manifest.json"
        assert manifest_path.exists()
        loaded = RerunManifest.load(manifest_path)
        assert loaded.supersedes_run_id == "old_run"
        assert loaded.new_run_id == "new_run"
        assert loaded.trigger == "manual"

        # Return value matches
        assert manifest.rerun_id.startswith("rerun_")
        assert manifest.supersedes_run_id == "old_run"


# ── RerunManifest ────────────────────────────────────────────────────────


class TestRerunManifest:
    """Test rerun manifest serialization."""

    def test_save_and_load_roundtrip(self, tmp_path):
        manifest = RerunManifest(
            rerun_id="rerun_20260101T000000Z",
            rung="r0",
            trigger="canary_check",
            issue="drift detected in model outputs",
            affected_models=["gbt_av", "ols_av"],
            affected_steps=["2", "3"],
            supersedes_run_id="old_run",
            new_run_id="new_run",
            cross_rung_impact="r1 may need retraining",
            timestamp="2026-01-01T00:00:00Z",
        )
        path = tmp_path / "manifest.json"
        manifest.save(path)

        loaded = RerunManifest.load(path)
        assert loaded.rerun_id == manifest.rerun_id
        assert loaded.rung == "r0"
        assert loaded.trigger == "canary_check"
        assert loaded.affected_models == ["gbt_av", "ols_av"]
        assert loaded.affected_steps == ["2", "3"]
        assert loaded.supersedes_run_id == "old_run"
        assert loaded.new_run_id == "new_run"
        assert loaded.cross_rung_impact == "r1 may need retraining"


# ── list_runs ────────────────────────────────────────────────────────────


class TestListRuns:
    """Test listing runs in a rung directory."""

    def test_returns_sorted_results(self, tmp_path):
        # Create directories in non-alphabetical order
        (tmp_path / "c_run").mkdir()
        (tmp_path / "a_run").mkdir()
        (tmp_path / "b_run").mkdir()

        runs = list_runs(tmp_path)
        names = [p.name for p, _ in runs]
        assert names == ["a_run", "b_run", "c_run"]

    def test_includes_status(self, tmp_path):
        (tmp_path / "canonical_run").mkdir()
        mark_canonical(tmp_path / "canonical_run")

        (tmp_path / "superseded_run").mkdir()
        mark_superseded(tmp_path / "superseded_run", "canonical_run")

        (tmp_path / "unmarked_run").mkdir()

        runs = list_runs(tmp_path)
        statuses = {p.name: s for p, s in runs}

        assert statuses["canonical_run"] is not None
        assert statuses["canonical_run"].status == "canonical"
        assert statuses["superseded_run"] is not None
        assert statuses["superseded_run"].status == "superseded"
        assert statuses["unmarked_run"] is None

    def test_skips_dotfiles(self, tmp_path):
        (tmp_path / ".hidden").mkdir()
        (tmp_path / "visible").mkdir()

        runs = list_runs(tmp_path)
        assert len(runs) == 1
        assert runs[0][0].name == "visible"

    def test_returns_empty_for_nonexistent_dir(self, tmp_path):
        runs = list_runs(tmp_path / "nonexistent")
        assert runs == []

    def test_skips_files(self, tmp_path):
        (tmp_path / "a_file.txt").write_text("not a dir")
        (tmp_path / "b_dir").mkdir()

        runs = list_runs(tmp_path)
        assert len(runs) == 1
        assert runs[0][0].name == "b_dir"


# ── prune_superseded ─────────────────────────────────────────────────────


class TestPruneSuperseded:
    """Test pruning of superseded/quarantined runs."""

    def test_dry_run_lists_without_deleting(self, tmp_path):
        # Create superseded and quarantined dirs
        sup_dir = tmp_path / "superseded_run"
        sup_dir.mkdir()
        mark_superseded(sup_dir, "replacement")

        quar_dir = tmp_path / "quarantined_run"
        quar_dir.mkdir()
        mark_quarantined(quar_dir, "bad data")

        # Active dir should not be listed
        active_dir = tmp_path / "active_run"
        active_dir.mkdir()
        mark_canonical(active_dir)

        prunable = prune_superseded(tmp_path, dry_run=True)
        prunable_names = [p.name for p in prunable]
        assert "superseded_run" in prunable_names
        assert "quarantined_run" in prunable_names
        assert "active_run" not in prunable_names

        # Directories still exist
        assert sup_dir.exists()
        assert quar_dir.exists()

    def test_execute_removes_directories(self, tmp_path):
        sup_dir = tmp_path / "superseded_run"
        sup_dir.mkdir()
        (sup_dir / "artifact.json").write_text("{}")
        mark_superseded(sup_dir, "replacement")

        active_dir = tmp_path / "active_run"
        active_dir.mkdir()

        prunable = prune_superseded(tmp_path, dry_run=False)
        assert len(prunable) == 1
        assert not sup_dir.exists()
        assert active_dir.exists()

    def test_no_prunable_returns_empty(self, tmp_path):
        active_dir = tmp_path / "active_run"
        active_dir.mkdir()
        mark_canonical(active_dir)

        prunable = prune_superseded(tmp_path, dry_run=True)
        assert prunable == []
