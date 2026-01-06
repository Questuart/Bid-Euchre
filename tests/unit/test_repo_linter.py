from pathlib import Path

from scripts.lint_repo import (
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
