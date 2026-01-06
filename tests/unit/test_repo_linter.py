from pathlib import Path

from scripts.lint_repo import (
    check_data_fixtures_allowlist,
    check_no_deprecated_changes,
    check_no_generated_artifacts,
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
