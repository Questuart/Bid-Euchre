"""Tests for chart snapshot publishing and versioning."""

import json

from bid_euchre.reporting.publish import (
    _next_snapshot_id,
    publish_chart_snapshot,
    update_versions_manifest,
)


class TestNextSnapshotId:
    """Tests for _next_snapshot_id."""

    def test_first_snapshot_for_date(self, tmp_path):
        """First snapshot uses bare date."""
        sid = _next_snapshot_id(tmp_path, "phase0", "20260207")
        assert sid == "phase0_20260207"

    def test_second_snapshot_same_day(self, tmp_path):
        """Second snapshot on same day gets _r2 suffix."""
        (tmp_path / "phase0_20260207").mkdir()
        sid = _next_snapshot_id(tmp_path, "phase0", "20260207")
        assert sid == "phase0_20260207_r2"

    def test_third_snapshot_same_day(self, tmp_path):
        """Third snapshot gets _r3."""
        (tmp_path / "phase0_20260207").mkdir()
        (tmp_path / "phase0_20260207_r2").mkdir()
        sid = _next_snapshot_id(tmp_path, "phase0", "20260207")
        assert sid == "phase0_20260207_r3"


class TestPublishChartSnapshot:
    """Tests for publish_chart_snapshot."""

    def _make_source(self, tmp_path, n_pngs=2):
        """Create a source dir with dummy PNGs."""
        from PIL import Image

        src = tmp_path / "source"
        src.mkdir()
        for i in range(n_pngs):
            Image.new("RGB", (1, 1)).save(src / f"chart_{i}.png")
        return src

    def test_creates_snapshot_dir(self, tmp_path):
        """Snapshot directory is created with all PNGs."""
        src = self._make_source(tmp_path)
        assets = tmp_path / "assets"
        assets.mkdir()

        sid = publish_chart_snapshot(
            src, assets, "phase0", snapshot_id="phase0_20260207"
        )

        snap_dir = assets / "phase0_20260207"
        assert snap_dir.exists()
        assert len(list(snap_dir.glob("*.png"))) == 2
        assert sid == "phase0_20260207"

    def test_updates_latest(self, tmp_path):
        """Latest alias directory is created."""
        src = self._make_source(tmp_path)
        assets = tmp_path / "assets"
        assets.mkdir()

        publish_chart_snapshot(src, assets, "phase0", snapshot_id="phase0_20260207")

        latest = assets / "phase0_latest"
        assert latest.exists()
        assert len(list(latest.glob("*.png"))) == 2

    def test_skips_latest_when_disabled(self, tmp_path):
        """Latest alias is not created when update_latest=False."""
        src = self._make_source(tmp_path)
        assets = tmp_path / "assets"
        assets.mkdir()

        publish_chart_snapshot(
            src, assets, "phase0", snapshot_id="phase0_20260207", update_latest=False
        )

        assert not (assets / "phase0_latest").exists()

    def test_missing_source_raises(self, tmp_path):
        """FileNotFoundError for missing source dir."""
        import pytest

        assets = tmp_path / "assets"
        assets.mkdir()

        with pytest.raises(FileNotFoundError):
            publish_chart_snapshot(tmp_path / "nonexistent", assets, "phase0")

    def test_empty_source_raises(self, tmp_path):
        """ValueError when source has no PNGs."""
        import pytest

        src = tmp_path / "empty"
        src.mkdir()
        assets = tmp_path / "assets"
        assets.mkdir()

        with pytest.raises(ValueError, match="No PNG"):
            publish_chart_snapshot(src, assets, "phase0")


class TestUpdateVersionsManifest:
    """Tests for update_versions_manifest."""

    def test_creates_new_manifest(self, tmp_path):
        """Creates manifest from scratch."""
        path = update_versions_manifest(
            tmp_path, "phase0", "phase0_20260207", ["a.png", "b.png"]
        )

        data = json.loads(path.read_text())
        assert len(data["snapshots"]) == 1
        assert data["latest"] == "phase0_20260207"
        assert data["snapshots"][0]["chart_files"] == ["a.png", "b.png"]

    def test_appends_to_existing(self, tmp_path):
        """Appends to existing manifest."""
        update_versions_manifest(tmp_path, "phase0", "phase0_20260207", ["a.png"])
        path = update_versions_manifest(
            tmp_path, "phase0", "phase0_20260207_r2", ["a.png", "c.png"]
        )

        data = json.loads(path.read_text())
        assert len(data["snapshots"]) == 2
        assert data["latest"] == "phase0_20260207_r2"

    def test_chart_files_sorted(self, tmp_path):
        """Chart file list is sorted."""
        path = update_versions_manifest(
            tmp_path, "phase0", "snap1", ["z.png", "a.png", "m.png"]
        )

        data = json.loads(path.read_text())
        assert data["snapshots"][0]["chart_files"] == ["a.png", "m.png", "z.png"]

    def test_latest_field_updated(self, tmp_path):
        """Latest field always reflects most recent snapshot."""
        update_versions_manifest(tmp_path, "phase0", "snap_v1", ["a.png"])
        path = update_versions_manifest(tmp_path, "phase0", "snap_v2", ["b.png"])

        data = json.loads(path.read_text())
        assert data["latest"] == "snap_v2"
