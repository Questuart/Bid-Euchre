"""Smoke test: full reporting pipeline on fixture data.

Runs the complete pipeline:
  generate_rung_tables.py -> tables/*.csv
  generate_rung_charts.py -> charts/*.png + chart_data/*.csv
  generate_evidence_manifest.py -> evidence_manifest.json + 00_manifest.md
  generate_rung_report.py -> 01_results.md

Verifies all outputs exist and are non-empty.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "arc_d_v2"
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "internal"


def _import_script(name: str):
    """Import a script as a module."""
    spec = importlib.util.spec_from_file_location(
        name,
        SCRIPTS_DIR / f"{name}.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestFullPipelineSmoke:
    def test_full_pipeline(self, tmp_path):
        """End-to-end pipeline: tables -> charts -> manifest -> report."""
        report_dir = tmp_path / "report"
        tables_dir = report_dir / "tables"
        charts_dir = report_dir / "charts"
        chart_data_dir = report_dir / "chart_data"

        # Step 1: Generate tables
        tables_mod = _import_script("generate_rung_tables")
        generated_tables = tables_mod.generate_all_tables(
            FIXTURES_DIR,
            tables_dir,
        )
        assert (
            len(generated_tables) >= 11
        ), f"Expected >= 11 tables, got {len(generated_tables)}: {generated_tables}"

        # Verify all table CSVs exist and are non-empty
        for csv_name in generated_tables:
            csv_path = tables_dir / csv_name
            assert csv_path.exists(), f"Table missing: {csv_name}"
            assert csv_path.stat().st_size > 0, f"Table empty: {csv_name}"

        # Step 2: Generate charts
        charts_mod = _import_script("generate_rung_charts")
        generated_charts = charts_mod.generate_all_charts(
            tables_dir=tables_dir,
            output_dir=charts_dir,
            chart_data_dir=chart_data_dir,
        )

        # Should generate at least the table-dependent charts
        assert (
            len(generated_charts) >= 5
        ), f"Expected >= 5 charts, got {len(generated_charts)}: {generated_charts}"

        # Verify chart PNGs exist and are non-empty
        for png_name in generated_charts:
            png_path = charts_dir / png_name
            assert png_path.exists(), f"Chart missing: {png_name}"
            assert png_path.stat().st_size > 0, f"Chart empty: {png_name}"

        # Step 3: Generate evidence manifest
        manifest_mod = _import_script("generate_evidence_manifest")
        manifest = manifest_mod.generate_evidence_manifest(
            rung_dir=FIXTURES_DIR,
            report_dir=report_dir,
            rung_id="r0",
            lineage_id="arc_d_v2",
        )

        # Verify manifest fields
        assert manifest["schema_version"] == "arc_d_evidence_manifest_v1"
        assert manifest["lineage_id"] == "arc_d_v2"
        assert manifest["rung_id"] == "r0"
        assert len(manifest["roster"]) > 0
        assert len(manifest["tables"]) > 0
        assert len(manifest["charts"]) > 0

        # Write manifest files
        import json

        manifest_json_path = report_dir / "evidence_manifest.json"
        manifest_json_path.write_text(json.dumps(manifest, indent=2) + "\n")
        assert manifest_json_path.exists()

        manifest_md_path = report_dir / "00_manifest.md"
        md_content = manifest_mod.render_manifest_markdown(manifest)
        manifest_md_path.write_text(md_content)
        assert manifest_md_path.exists()
        assert manifest_md_path.stat().st_size > 0

        # Step 4: Generate report
        report_mod = _import_script("generate_rung_report")
        report_content = report_mod.generate_report(report_dir)

        report_path = report_dir / "01_results.md"
        report_path.write_text(report_content)
        assert report_path.exists()
        assert report_path.stat().st_size > 0
        assert "# Rung Results Report" in report_content

        # Verify all required sections present
        for section in [
            "## 1. Data Sanity",
            "## 2. Offline Model Performance",
            "## 6. Comparator Rankings",
            "## 7. H2H Battery",
            "## 8. Behavioral Analysis",
            "## 9. Sanity Bounds",
        ]:
            assert section in report_content, f"Missing section: {section}"

    def test_table_names_expected(self, tmp_path):
        """Verify the specific table names generated."""
        tables_dir = tmp_path / "tables"
        tables_mod = _import_script("generate_rung_tables")
        generated = tables_mod.generate_all_tables(FIXTURES_DIR, tables_dir)

        expected_tables = [
            "comparator_rankings.csv",
            "h2h_delta_matrix.csv",
            "model_performance.csv",
            "behavior_summary.csv",
            "behavior_by_contract.csv",
            "sanity_bounds_check.csv",
            "hypothesis_outcomes.csv",
            "rung_model_spec.csv",
            "cross_rung_deltas.csv",
            "dataset_provenance.csv",
            "artifact_inventory.csv",
            "data_sanity.csv",
        ]

        for expected in expected_tables:
            assert (
                expected in generated
            ), f"Missing table {expected} in generated list: {generated}"
