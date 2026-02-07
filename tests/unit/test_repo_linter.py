from pathlib import Path

from scripts.lint_repo import (
    check_canonical_runs_consistency,
    check_data_fixtures_allowlist,
    check_no_deprecated_changes,
    check_no_generated_artifacts,
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
    target.write_text("import os\nfrom bid_euchre.core.cards import Card\n", encoding="utf-8")

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


# --- canonical-runs-registry-consistency tests ---


def _create_registry_file(tmp_path: Path) -> None:
    """Helper: create canonical_runs.py so the consistency rule activates."""
    registry = tmp_path / "notebooks" / "phase0_bidless"
    registry.mkdir(parents=True, exist_ok=True)
    (registry / "canonical_runs.py").write_text("RUNS = {}\n")


def test_canonical_runs_both_changed(tmp_path: Path):
    """No violation when both registry files change together."""
    _create_registry_file(tmp_path)
    changed = [
        "notebooks/phase0_bidless/canonical_runs.py",
        "docs/02_agent/CANONICAL_BIDLESS_RUNS.md",
    ]
    v = check_canonical_runs_consistency(changed, tmp_path)
    assert v == []


def test_canonical_runs_code_only(tmp_path: Path):
    """Violation when canonical_runs.py changes but doc does not."""
    _create_registry_file(tmp_path)
    changed = ["notebooks/phase0_bidless/canonical_runs.py"]
    v = check_canonical_runs_consistency(changed, tmp_path)
    assert len(v) == 1
    assert v[0].rule == "canonical-runs-registry-consistency"
    assert "canonical_runs.py" in v[0].message


def test_canonical_runs_doc_only(tmp_path: Path):
    """Violation when doc changes but canonical_runs.py does not."""
    _create_registry_file(tmp_path)
    changed = ["docs/02_agent/CANONICAL_BIDLESS_RUNS.md"]
    v = check_canonical_runs_consistency(changed, tmp_path)
    assert len(v) == 1
    assert v[0].rule == "canonical-runs-registry-consistency"
    assert "CANONICAL_BIDLESS_RUNS.md" in v[0].message


def test_canonical_runs_neither_changed(tmp_path: Path):
    """No violation when neither registry file changes."""
    _create_registry_file(tmp_path)
    changed = ["src/bid_euchre/core/cards.py"]
    v = check_canonical_runs_consistency(changed, tmp_path)
    assert v == []


def test_canonical_runs_skipped_when_registry_missing(tmp_path: Path):
    """Rule is skipped when canonical_runs.py doesn't exist (deleted in #305)."""
    changed = ["docs/02_agent/CANONICAL_BIDLESS_RUNS.md"]
    v = check_canonical_runs_consistency(changed, tmp_path)
    assert v == []


# --- registry-requires-gate-reference tests ---


def test_registry_gate_ref_present(tmp_path: Path):
    """No violation when doc references a gate artifact."""
    doc_dir = tmp_path / "docs" / "02_agent"
    doc_dir.mkdir(parents=True)
    doc_path = doc_dir / "CANONICAL_BIDLESS_RUNS.md"
    doc_path.write_text(
        "# Registry\nPromoted via batch_gate.json evidence.\n",
        encoding="utf-8",
    )
    changed = ["docs/02_agent/CANONICAL_BIDLESS_RUNS.md"]
    v = check_registry_requires_gate_reference(changed, tmp_path)
    assert v == []


def test_registry_gate_ref_missing(tmp_path: Path):
    """Violation when doc changes without gate artifact reference."""
    doc_dir = tmp_path / "docs" / "02_agent"
    doc_dir.mkdir(parents=True)
    doc_path = doc_dir / "CANONICAL_BIDLESS_RUNS.md"
    doc_path.write_text(
        "# Registry\nUpdated run IDs.\n",
        encoding="utf-8",
    )
    changed = ["docs/02_agent/CANONICAL_BIDLESS_RUNS.md"]
    v = check_registry_requires_gate_reference(changed, tmp_path)
    assert len(v) == 1
    assert v[0].rule == "registry-requires-gate-reference"


def test_registry_gate_ref_canonical_summary(tmp_path: Path):
    """canonical_summary.json reference is acceptable."""
    doc_dir = tmp_path / "docs" / "02_agent"
    doc_dir.mkdir(parents=True)
    doc_path = doc_dir / "CANONICAL_BIDLESS_RUNS.md"
    doc_path.write_text(
        "# Registry\nBacked by canonical_summary.json.\n",
        encoding="utf-8",
    )
    changed = ["docs/02_agent/CANONICAL_BIDLESS_RUNS.md"]
    v = check_registry_requires_gate_reference(changed, tmp_path)
    assert v == []


def test_registry_gate_ref_not_triggered_without_doc_change(tmp_path: Path):
    """No violation when doc is not in changed files."""
    changed = ["src/bid_euchre/core/cards.py"]
    v = check_registry_requires_gate_reference(changed, tmp_path)
    assert v == []
