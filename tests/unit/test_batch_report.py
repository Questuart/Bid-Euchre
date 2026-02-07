"""Tests for batch report generation."""

import json
import sys

# Import from scripts directory
sys.path.insert(0, "scripts")
from generate_report import generate_batch_report


def test_batch_gate_json_structure(tmp_path):
    """batch_gate.json has correct structure."""
    # Set up a fake suite rollup directory
    rollup_dir = tmp_path / "suite_test_42"
    rollup_dir.mkdir()

    # Create a fake member run
    run_dir = tmp_path / "test_run_42"
    run_dir.mkdir()
    (run_dir / "results").mkdir()
    (run_dir / "artifacts").mkdir()

    # Write canonical_summary.json for member
    summary = {
        "run_id": "test_run_42",
        "sanity": {
            "pass_count": 3,
            "warn_count": 0,
            "fail_count": 0,
            "skip_count": 1,
            "all_passed": True,
            "failing_tests": [],
        },
    }
    with open(run_dir / "artifacts" / "canonical_summary.json", "w") as f:
        json.dump(summary, f)

    # Write rollup.json
    rollup = {
        "schema_version": 1,
        "suite_name": "test_suite",
        "configs": [
            {
                "run_id": "test_run_42",
                "run_dir": "test_run_42",
                "config_path": "test.yaml",
                "status": "ok",
                "git_sha": "abc123",
            },
        ],
    }
    with open(rollup_dir / "rollup.json", "w") as f:
        json.dump(rollup, f)

    result = generate_batch_report(rollup_dir, verbose=False)
    assert result == 0

    # Verify batch_gate.json
    gate_path = rollup_dir / "artifacts" / "batch_gate.json"
    assert gate_path.exists()
    gate = json.loads(gate_path.read_text())
    assert gate["gate_type"] == "batch_promotion"
    assert gate["gate_version"] == 1
    assert gate["eligible"] is True
    assert gate["reasons"] == []
    assert len(gate["member_runs"]) == 1
    assert gate["member_runs"][0]["gate_status"] == "PASS"


def test_batch_report_with_failures(tmp_path):
    """Batch report correctly identifies failures."""
    rollup_dir = tmp_path / "suite_fail"
    rollup_dir.mkdir()

    # Create member with failures
    run_dir = tmp_path / "fail_run"
    run_dir.mkdir()
    (run_dir / "results").mkdir()
    (run_dir / "artifacts").mkdir()

    summary = {
        "run_id": "fail_run",
        "sanity": {
            "pass_count": 1,
            "warn_count": 0,
            "fail_count": 2,
            "skip_count": 0,
            "all_passed": False,
            "failing_tests": ["test_a", "test_b"],
        },
    }
    with open(run_dir / "artifacts" / "canonical_summary.json", "w") as f:
        json.dump(summary, f)

    rollup = {
        "schema_version": 1,
        "suite_name": "fail_suite",
        "configs": [
            {
                "run_id": "fail_run",
                "run_dir": "fail_run",
                "config_path": "test.yaml",
                "status": "ok",
                "git_sha": "abc",
            },
        ],
    }
    with open(rollup_dir / "rollup.json", "w") as f:
        json.dump(rollup, f)

    result = generate_batch_report(rollup_dir, verbose=False)
    assert result == 0

    gate = json.loads(
        (rollup_dir / "artifacts" / "batch_gate.json").read_text()
    )
    assert gate["eligible"] is False
    assert len(gate["reasons"]) > 0


def test_batch_report_markdown_generated(tmp_path):
    """BATCH_REPORT.md is generated."""
    rollup_dir = tmp_path / "suite_md"
    rollup_dir.mkdir()

    rollup = {
        "schema_version": 1,
        "suite_name": "md_suite",
        "configs": [],
    }
    with open(rollup_dir / "rollup.json", "w") as f:
        json.dump(rollup, f)

    generate_batch_report(rollup_dir, verbose=False)

    md_path = rollup_dir / "reports" / "BATCH_REPORT.md"
    assert md_path.exists()
    content = md_path.read_text()
    assert "# Batch Report" in content
    assert "md_suite" in content
