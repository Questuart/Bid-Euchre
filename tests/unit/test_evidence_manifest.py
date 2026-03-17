"""Tests for evidence manifest generation.

Covers:
- Manifest JSON has all required fields from section 14 schema
- Markdown manifest renders correctly
- Manifest includes roster, artifacts, tables, charts
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "arc_d_v2"

from bid_euchre.arc_d_v2.manifest import (
    generate_evidence_manifest,
    render_manifest_markdown,
)
from bid_euchre.arc_d_v2.tables import generate_all_tables

# Required top-level fields in the evidence manifest
REQUIRED_MANIFEST_FIELDS = [
    "schema_version",
    "lineage_id",
    "rung_id",
    "provenance_sha",
    "governing_plan",
    "anchor",
    "roster",
    "seeds",
    "mode",
    "run_ids",
    "artifacts",
    "tables",
    "charts",
]


class TestEvidenceManifest:
    @pytest.fixture
    def manifest_with_tables(self, tmp_path):
        """Generate a manifest with tables directory populated."""
        report_dir = tmp_path / "report"
        tables_dir = report_dir / "tables"
        generate_all_tables(FIXTURES_DIR, tables_dir)

        return generate_evidence_manifest(
            rung_dir=FIXTURES_DIR,
            report_dir=report_dir,
            rung_id="r0",
            lineage_id="arc_d_v2",
        )

    def test_required_fields_present(self, manifest_with_tables):
        for field in REQUIRED_MANIFEST_FIELDS:
            assert field in manifest_with_tables, f"Missing field: {field}"

    def test_schema_version(self, manifest_with_tables):
        assert manifest_with_tables["schema_version"] == "arc_d_evidence_manifest_v1"

    def test_lineage_id(self, manifest_with_tables):
        assert manifest_with_tables["lineage_id"] == "arc_d_v2"

    def test_rung_id(self, manifest_with_tables):
        assert manifest_with_tables["rung_id"] == "r0"

    def test_provenance_sha_present(self, manifest_with_tables):
        assert isinstance(manifest_with_tables["provenance_sha"], str)
        assert len(manifest_with_tables["provenance_sha"]) > 0

    def test_roster_not_empty(self, manifest_with_tables):
        assert len(manifest_with_tables["roster"]) > 0

    def test_roster_entries_have_fields(self, manifest_with_tables):
        for entry in manifest_with_tables["roster"]:
            assert "name" in entry
            assert "class_name" in entry
            assert "trainable" in entry

    def test_seeds_not_empty(self, manifest_with_tables):
        assert len(manifest_with_tables["seeds"]) > 0

    def test_artifacts_not_empty(self, manifest_with_tables):
        assert len(manifest_with_tables["artifacts"]) > 0

    def test_tables_not_empty(self, manifest_with_tables):
        assert len(manifest_with_tables["tables"]) > 0

    def test_table_entries_have_fields(self, manifest_with_tables):
        for entry in manifest_with_tables["tables"]:
            assert "name" in entry
            assert "path" in entry
            assert "size_bytes" in entry


class TestManifestMarkdown:
    def test_renders_non_empty(self):
        manifest = {
            "schema_version": "arc_d_evidence_manifest_v1",
            "lineage_id": "arc_d_v2",
            "rung_id": "r0",
            "provenance_sha": "abc123",
            "governing_plan": "plans/arc_d_v2/r0/plan.md",
            "anchor": "hybrid_r0_full",
            "roster": [
                {
                    "name": "gbt_av",
                    "class_name": "GBT",
                    "trainable": True,
                    "status": "evaluated",
                },
            ],
            "seeds": [42],
            "mode": "QUICK",
            "run_ids": ["run_001"],
            "artifacts": [],
            "tables": [],
            "charts": [],
        }
        md = render_manifest_markdown(manifest)
        assert len(md) > 0
        assert "# Rung Manifest" in md
        assert "arc_d_v2" in md
        assert "abc123" in md

    def test_includes_roster_table(self):
        manifest = {
            "schema_version": "arc_d_evidence_manifest_v1",
            "lineage_id": "arc_d_v2",
            "rung_id": "r0",
            "provenance_sha": "abc",
            "governing_plan": "",
            "anchor": "",
            "roster": [
                {
                    "name": "model_a",
                    "class_name": "ClassA",
                    "trainable": True,
                    "status": "ok",
                },
            ],
            "seeds": [],
            "mode": "QUICK",
            "run_ids": [],
            "artifacts": [],
            "tables": [],
            "charts": [],
        }
        md = render_manifest_markdown(manifest)
        assert "## Model Roster" in md
        assert "model_a" in md


class TestManifestSeeds:
    """Tests for seed discovery in evidence manifests (F3 fix)."""

    def test_seeds_from_single_seed_battery(self, tmp_path):
        """Battery with seed: 42 produces seeds=[42]."""
        import json

        rung_dir = tmp_path / "rung"
        rung_dir.mkdir()
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        # Write battery with single seed
        battery = {"seed": 42, "mode": "QUICK", "cells": {}}
        (rung_dir / "h2h_battery.json").write_text(json.dumps(battery))

        manifest = generate_evidence_manifest(
            rung_dir=rung_dir,
            report_dir=report_dir,
            rung_id="r0",
        )
        assert manifest["seeds"] == [42]

    def test_seeds_from_multi_seed_dirs(self, tmp_path):
        """Battery with seeds_merged + seed_* dirs produces correct seeds."""
        import json

        rung_dir = tmp_path / "rung"
        rung_dir.mkdir()
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        # Write merged battery
        battery = {"seeds_merged": 3, "mode": "FULL", "cells": {}}
        (rung_dir / "h2h_battery.json").write_text(json.dumps(battery))

        # Create seed directories
        for s in [42, 123, 456]:
            (rung_dir / f"seed_{s}").mkdir()

        manifest = generate_evidence_manifest(
            rung_dir=rung_dir,
            report_dir=report_dir,
            rung_id="r0",
        )
        assert sorted(manifest["seeds"]) == [42, 123, 456]
        assert manifest["mode"] == "FULL"

    def test_seeds_empty_when_no_seed_key(self, tmp_path):
        """Battery without seed key produces seeds=[]."""
        import json

        rung_dir = tmp_path / "rung"
        rung_dir.mkdir()
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        # Write battery without seed key
        battery = {"mode": "QUICK", "cells": {}}
        (rung_dir / "h2h_battery.json").write_text(json.dumps(battery))

        manifest = generate_evidence_manifest(
            rung_dir=rung_dir,
            report_dir=report_dir,
            rung_id="r0",
        )
        assert manifest["seeds"] == []

    def test_seeds_no_fabricated_default(self, tmp_path):
        """When seed key is missing, seeds should NOT default to [42]."""
        import json

        rung_dir = tmp_path / "rung"
        rung_dir.mkdir()
        report_dir = tmp_path / "report"
        report_dir.mkdir()

        # Battery without seed key — old code would produce [42]
        battery = {"mode": "QUICK", "cells": {}}
        (rung_dir / "h2h_battery.json").write_text(json.dumps(battery))

        manifest = generate_evidence_manifest(
            rung_dir=rung_dir,
            report_dir=report_dir,
            rung_id="r0",
        )
        assert 42 not in manifest["seeds"]
