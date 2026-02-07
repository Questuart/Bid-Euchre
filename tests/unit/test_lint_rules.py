"""Tests for custom repo lint rules."""

from pathlib import Path

from lint_repo import check_no_sys_path_insert


def _write_file(tmp_path: Path, rel_path: str, content: str) -> None:
    """Write a file at rel_path under tmp_path."""
    p = tmp_path / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def test_sys_path_insert_violation(tmp_path):
    """sys.path.insert in active Python files is flagged."""
    _write_file(tmp_path, "scripts/foo.py", 'import sys\nsys.path.insert(0, "src")\n')
    violations = check_no_sys_path_insert(["scripts/foo.py"], tmp_path)
    assert len(violations) == 1
    assert violations[0].rule == "no-sys-path-mutation"


def test_sys_path_append_violation(tmp_path):
    """sys.path.append is also flagged."""
    _write_file(tmp_path, "scripts/bar.py", 'import sys\nsys.path.append("src")\n')
    violations = check_no_sys_path_insert(["scripts/bar.py"], tmp_path)
    assert len(violations) == 1
    assert violations[0].rule == "no-sys-path-mutation"


def test_sys_path_in_comment_is_ok(tmp_path):
    """sys.path.insert in a comment should not be flagged."""
    _write_file(tmp_path, "scripts/ok.py", '# sys.path.insert(0, "src")\nprint("hello")\n')
    violations = check_no_sys_path_insert(["scripts/ok.py"], tmp_path)
    assert len(violations) == 0


def test_deprecated_files_are_allowed(tmp_path):
    """Files under experiments/_deprecated/ are grandfathered."""
    _write_file(
        tmp_path,
        "experiments/_deprecated/old.py",
        'import sys\nsys.path.insert(0, "src")\n',
    )
    violations = check_no_sys_path_insert(
        ["experiments/_deprecated/old.py"], tmp_path
    )
    assert len(violations) == 0


def test_clean_file_no_violations(tmp_path):
    """A file without sys.path mutations passes."""
    _write_file(tmp_path, "src/bid_euchre/foo.py", "from pathlib import Path\n")
    violations = check_no_sys_path_insert(["src/bid_euchre/foo.py"], tmp_path)
    assert len(violations) == 0


def test_nonexistent_file_skipped(tmp_path):
    """Nonexistent files are silently skipped."""
    violations = check_no_sys_path_insert(["does_not_exist.py"], tmp_path)
    assert len(violations) == 0


def test_non_python_files_skipped(tmp_path):
    """Non-.py files are skipped."""
    _write_file(tmp_path, "README.md", "sys.path.insert(0, 'src')\n")
    violations = check_no_sys_path_insert(["README.md"], tmp_path)
    assert len(violations) == 0
