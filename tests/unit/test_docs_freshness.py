"""Tests for docs freshness gate."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from check_docs_freshness import check_path_references, check_scripts_list_complete


def test_valid_path_reference(tmp_path):
    """Valid backtick path references pass."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (tmp_path / "src" / "foo.py").parent.mkdir(parents=True)
    (tmp_path / "src" / "foo.py").touch()
    (docs_dir / "test.md").write_text("See `src/foo.py` for details.\n")

    errors = check_path_references(docs_dir, tmp_path)
    assert len(errors) == 0


def test_broken_path_reference(tmp_path):
    """Broken backtick path references are flagged."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "test.md").write_text("See `src/nonexistent.py` for details.\n")

    errors = check_path_references(docs_dir, tmp_path)
    assert len(errors) == 1
    assert "nonexistent.py" in errors[0]


def test_scripts_list_complete(tmp_path):
    """All scripts should be listed in ARCHITECTURE.md."""
    arch_doc = tmp_path / "ARCHITECTURE.md"
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "foo.py").touch()
    (scripts_dir / "bar.py").touch()
    (scripts_dir / "_private.py").touch()
    arch_doc.write_text("Scripts: foo.py and bar.py\n")

    errors = check_scripts_list_complete(arch_doc, scripts_dir)
    assert len(errors) == 0


def test_missing_script_in_docs(tmp_path):
    """Missing script in ARCHITECTURE.md is flagged."""
    arch_doc = tmp_path / "ARCHITECTURE.md"
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "foo.py").touch()
    (scripts_dir / "missing.py").touch()
    arch_doc.write_text("Scripts: foo.py\n")

    errors = check_scripts_list_complete(arch_doc, scripts_dir)
    assert len(errors) == 1
    assert "missing.py" in errors[0]


def test_private_scripts_ignored(tmp_path):
    """Scripts starting with _ are ignored."""
    arch_doc = tmp_path / "ARCHITECTURE.md"
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "_internal.py").touch()
    arch_doc.write_text("No scripts here\n")

    errors = check_scripts_list_complete(arch_doc, scripts_dir)
    assert len(errors) == 0
