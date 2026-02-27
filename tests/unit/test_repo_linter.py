from pathlib import Path

from scripts.lint_repo import (
    check_canonical_runs_registry_consistency,
    check_data_fixtures_allowlist,
    check_no_deprecated_changes,
    check_no_generated_artifacts,
    check_promotion_report_requires_integrity_review,
    check_registry_requires_gate_reference,
    check_src_no_experiments_or_tests_imports,
)


def test_blocks_generated_artifacts():
    changed = ["data/runs/abc/meta.json", "data/reports/x.png"]
    v = check_no_generated_artifacts(changed)
    assert len(v) == 2


def test_allows_gitkeep_in_artifact_dirs():
    changed = ["data/runs/.gitkeep", "data/reports/.gitkeep"]
    v = check_no_generated_artifacts(changed)
    assert v == []


def test_blocks_deprecated_changes():
    changed = ["experiments/_deprecated/old_runner.py"]
    v = check_no_deprecated_changes(changed)
    assert len(v) == 1


def test_blocks_src_importing_experiments(tmp_path: Path):
    # Create a fake repo root with a src file
    repo_root = tmp_path
    p = repo_root / "src" / "bid_euchre" / "core"
    p.mkdir(parents=True)
    target = p / "cards.py"
    target.write_text("import experiments\n", encoding="utf-8")

    v = check_src_no_experiments_or_tests_imports(
        ["src/bid_euchre/core/cards.py"],
        repo_root,
    )
    assert len(v) == 1
    assert "experiments" in v[0].message


def test_allows_src_without_bad_imports(tmp_path: Path):
    repo_root = tmp_path
    p = repo_root / "src" / "bid_euchre" / "core"
    p.mkdir(parents=True)
    target = p / "cards.py"
    target.write_text(
        "import os\nfrom bid_euchre.core.cards import Card\n", encoding="utf-8"
    )

    v = check_src_no_experiments_or_tests_imports(
        ["src/bid_euchre/core/cards.py"],
        repo_root,
    )
    assert v == []


def test_data_allowlist_blocks_runs(tmp_path: Path):
    """Block files under data/runs/"""
    changed = ["data/runs/example/meta.json"]
    v = check_data_fixtures_allowlist(changed, tmp_path)
    assert len(v) == 1
    assert "not allowed" in v[0].message
    assert "data/fixtures/**" in v[0].message


def test_data_allowlist_blocks_training(tmp_path: Path):
    """Block files under data/training/"""
    changed = ["data/training/foo.csv"]
    v = check_data_fixtures_allowlist(changed, tmp_path)
    assert len(v) == 1
    assert "not allowed" in v[0].message


def test_data_allowlist_blocks_reports(tmp_path: Path):
    """Block files under data/reports/"""
    changed = ["data/reports/foo.png"]
    v = check_data_fixtures_allowlist(changed, tmp_path)
    assert len(v) == 1
    assert "not allowed" in v[0].message


def test_data_allowlist_blocks_deprecated(tmp_path: Path):
    """Block files under data/_deprecated/"""
    changed = ["data/_deprecated/foo.png"]
    v = check_data_fixtures_allowlist(changed, tmp_path)
    assert len(v) == 1
    assert "not allowed" in v[0].message


def test_data_allowlist_allows_small_fixture(tmp_path: Path):
    """Allow small fixtures under data/fixtures/"""
    repo_root = tmp_path
    fixture_dir = repo_root / "data" / "fixtures"
    fixture_dir.mkdir(parents=True)
    fixture_file = fixture_dir / "example.json"
    fixture_file.write_text('{"test": "data"}', encoding="utf-8")  # ~16 bytes

    v = check_data_fixtures_allowlist(["data/fixtures/example.json"], repo_root)
    assert v == []


def test_data_allowlist_blocks_oversized_fixture(tmp_path: Path):
    """Block fixtures exceeding 100KB"""
    repo_root = tmp_path
    fixture_dir = repo_root / "data" / "fixtures"
    fixture_dir.mkdir(parents=True)
    fixture_file = fixture_dir / "oversize.bin"
    fixture_file.write_bytes(b"x" * 150000)  # 150KB

    v = check_data_fixtures_allowlist(["data/fixtures/oversize.bin"], repo_root)
    assert len(v) == 1
    assert "exceeds 100KB limit" in v[0].message
    assert "147KB" in v[0].message  # 150000 / 1024 = 146.48, rounds up to 147


def test_data_allowlist_allows_empty_fixture(tmp_path: Path):
    """Allow empty fixture files (0 bytes)"""
    repo_root = tmp_path
    fixture_dir = repo_root / "data" / "fixtures"
    fixture_dir.mkdir(parents=True)
    fixture_file = fixture_dir / "empty.json"
    fixture_file.write_text("", encoding="utf-8")  # 0 bytes

    v = check_data_fixtures_allowlist(["data/fixtures/empty.json"], repo_root)
    assert v == []


def test_data_allowlist_allows_gitkeep(tmp_path: Path):
    """Allow data/.gitkeep"""
    changed = ["data/.gitkeep"]
    v = check_data_fixtures_allowlist(changed, tmp_path)
    assert v == []


def test_data_allowlist_allows_subdirectory_fixtures(tmp_path: Path):
    """Allow fixtures in subdirectories under data/fixtures/"""
    repo_root = tmp_path
    fixture_dir = repo_root / "data" / "fixtures" / "deals"
    fixture_dir.mkdir(parents=True)
    fixture_file = fixture_dir / "example.json"
    fixture_file.write_text('{"deal": "data"}', encoding="utf-8")

    v = check_data_fixtures_allowlist(["data/fixtures/deals/example.json"], repo_root)
    assert v == []


def test_data_allowlist_handles_deleted_files(tmp_path: Path):
    """Deleted files don't exist in working tree, should not fail size check"""
    # Simulate a changed file that doesn't exist (deleted or not yet created)
    changed = ["data/fixtures/deleted.json"]
    v = check_data_fixtures_allowlist(changed, tmp_path)
    # Should pass because file doesn't exist (no size to check)
    assert v == []


# --- Promotion contract lint rule tests ---


def test_registry_gate_reference_present_passes(tmp_path: Path):
    """Report with gate evidence reference passes."""
    repo_root = tmp_path
    reports_dir = repo_root / "docs" / "04_reports"
    reports_dir.mkdir(parents=True)
    report = reports_dir / "phase1_report.md"
    report.write_text(
        "# Report\nSee notebook_gate.json for details.\n", encoding="utf-8"
    )

    v = check_registry_requires_gate_reference(
        ["docs/04_reports/phase1_report.md"],
        repo_root,
    )
    assert v == []


def test_registry_gate_reference_missing_fails(tmp_path: Path):
    """Report without gate evidence reference fails."""
    repo_root = tmp_path
    reports_dir = repo_root / "docs" / "04_reports"
    reports_dir.mkdir(parents=True)
    report = reports_dir / "phase1_report.md"
    report.write_text("# Report\nNo gate evidence here.\n", encoding="utf-8")

    v = check_registry_requires_gate_reference(
        ["docs/04_reports/phase1_report.md"],
        repo_root,
    )
    assert len(v) == 1
    assert v[0].rule == "registry-requires-gate-reference"


def test_registry_unrelated_doc_ignored(tmp_path: Path):
    """Doc outside registry patterns is not checked."""
    repo_root = tmp_path
    docs_dir = repo_root / "docs" / "01_core"
    docs_dir.mkdir(parents=True)
    doc = docs_dir / "RULES.md"
    doc.write_text("# Rules\nNo gate evidence.\n", encoding="utf-8")

    v = check_registry_requires_gate_reference(
        ["docs/01_core/RULES.md"],
        repo_root,
    )
    assert v == []


def test_registry_readme_skipped(tmp_path: Path):
    """README.md in reports dir is not checked."""
    repo_root = tmp_path
    reports_dir = repo_root / "docs" / "04_reports"
    reports_dir.mkdir(parents=True)
    readme = reports_dir / "README.md"
    readme.write_text("# Reports Index\nNo gate evidence.\n", encoding="utf-8")

    v = check_registry_requires_gate_reference(
        ["docs/04_reports/README.md"],
        repo_root,
    )
    assert v == []


def test_consistency_no_code_registry_noop(tmp_path: Path):
    """Code registry absent (post-#305) -> no violation."""
    repo_root = tmp_path
    # Don't create CODE_REGISTRY_PATH file
    v = check_canonical_runs_registry_consistency(
        ["docs/04_reports/report.md"],
        repo_root,
    )
    assert v == []


def test_consistency_both_changed_passes(tmp_path: Path):
    """Both code+doc changed -> no violation."""
    repo_root = tmp_path
    # Create code registry file
    code_path = repo_root / "src" / "bid_euchre" / "datasets"
    code_path.mkdir(parents=True)
    (code_path / "canonical_runs.py").write_text("# registry\n", encoding="utf-8")

    v = check_canonical_runs_registry_consistency(
        [
            "src/bid_euchre/datasets/canonical_runs.py",
            "docs/04_reports/report.md",
        ],
        repo_root,
    )
    assert v == []


def test_consistency_code_only_changed_fails(tmp_path: Path):
    """Code changed but not doc -> violation."""
    repo_root = tmp_path
    code_path = repo_root / "src" / "bid_euchre" / "datasets"
    code_path.mkdir(parents=True)
    (code_path / "canonical_runs.py").write_text("# registry\n", encoding="utf-8")

    v = check_canonical_runs_registry_consistency(
        ["src/bid_euchre/datasets/canonical_runs.py"],
        repo_root,
    )
    assert len(v) == 1
    assert v[0].rule == "canonical-runs-registry-consistency"


def test_non_md_files_ignored(tmp_path: Path):
    """Non-.md file in reports dir is not checked by gate reference rule."""
    repo_root = tmp_path
    reports_dir = repo_root / "docs" / "04_reports"
    reports_dir.mkdir(parents=True)
    png = reports_dir / "chart.png"
    png.write_bytes(b"\x89PNG")

    v = check_registry_requires_gate_reference(
        ["docs/04_reports/chart.png"],
        repo_root,
    )
    assert v == []


# --- Promotion report integrity review lint rule tests ---


def test_promotion_report_with_matched_integrity_file_passes(tmp_path: Path):
    """Promotion report with rung-matched measurement_integrity file passes."""
    repo_root = tmp_path
    reports_dir = repo_root / "docs" / "04_reports" / "r0"
    reports_dir.mkdir(parents=True)
    (reports_dir / "r0_promotion_report.md").write_text("# Promo\n", encoding="utf-8")
    (reports_dir / "measurement_integrity_r0.md").write_text(
        "# Review\n", encoding="utf-8"
    )

    v = check_promotion_report_requires_integrity_review(
        ["docs/04_reports/r0/r0_promotion_report.md"],
        repo_root,
    )
    assert v == []


def test_promotion_report_without_integrity_file_fails(tmp_path: Path):
    """Promotion report without companion measurement_integrity file fails."""
    repo_root = tmp_path
    reports_dir = repo_root / "docs" / "04_reports" / "r0"
    reports_dir.mkdir(parents=True)
    (reports_dir / "r0_promotion_report.md").write_text("# Promo\n", encoding="utf-8")

    v = check_promotion_report_requires_integrity_review(
        ["docs/04_reports/r0/r0_promotion_report.md"],
        repo_root,
    )
    assert len(v) == 1
    assert v[0].rule == "promotion-requires-integrity-review"


def test_promotion_report_with_wrong_rung_integrity_file_fails(tmp_path: Path):
    """Promotion report with mismatched rung integrity file fails."""
    repo_root = tmp_path
    reports_dir = repo_root / "docs" / "04_reports" / "r1"
    reports_dir.mkdir(parents=True)
    (reports_dir / "r1_promotion_report.md").write_text("# Promo\n", encoding="utf-8")
    (reports_dir / "measurement_integrity_r0.md").write_text(
        "# Wrong rung\n", encoding="utf-8"
    )

    v = check_promotion_report_requires_integrity_review(
        ["docs/04_reports/r1/r1_promotion_report.md"],
        repo_root,
    )
    assert len(v) == 1
    assert v[0].rule == "promotion-requires-integrity-review"


def test_non_promotion_report_not_checked(tmp_path: Path):
    """Non-promotion report under 04_reports is not checked."""
    repo_root = tmp_path
    reports_dir = repo_root / "docs" / "04_reports" / "r0"
    reports_dir.mkdir(parents=True)
    (reports_dir / "comparator_rankings.md").write_text(
        "# Rankings\n", encoding="utf-8"
    )

    v = check_promotion_report_requires_integrity_review(
        ["docs/04_reports/r0/comparator_rankings.md"],
        repo_root,
    )
    assert v == []
