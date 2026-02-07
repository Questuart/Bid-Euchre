"""Tests for docs freshness gate."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from check_docs_freshness import (
    check_image_references,
    check_path_references,
    check_scripts_list_complete,
)


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


# --- Image reference tests ---


def test_valid_image_reference(tmp_path):
    """Valid image reference with real PNG passes."""
    from PIL import Image

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    assets = docs_dir / "assets"
    assets.mkdir()
    img_path = assets / "chart.png"
    Image.new("RGB", (1, 1)).save(img_path)
    (docs_dir / "report.md").write_text("![Chart](assets/chart.png)\n")

    errors = check_image_references(docs_dir, tmp_path)
    assert len(errors) == 0


def test_missing_image_reference(tmp_path):
    """Missing image file is flagged."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "report.md").write_text("![Chart](assets/missing.png)\n")

    errors = check_image_references(docs_dir, tmp_path)
    assert len(errors) == 1
    assert "not found" in errors[0]


def test_corrupt_png_fails(tmp_path):
    """File with random bytes fails PNG validation."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    img_path = docs_dir / "bad.png"
    img_path.write_bytes(b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09")
    (docs_dir / "report.md").write_text("![Bad](bad.png)\n")

    errors = check_image_references(docs_dir, tmp_path)
    assert len(errors) == 1
    assert "invalid PNG" in errors[0]


def test_truncated_png_fails(tmp_path):
    """File with valid PNG signature but truncated body fails."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    img_path = docs_dir / "trunc.png"
    # Valid 8-byte PNG signature but no IHDR or IDAT chunks
    img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 4)
    (docs_dir / "report.md").write_text("![Trunc](trunc.png)\n")

    errors = check_image_references(docs_dir, tmp_path)
    assert len(errors) == 1
    assert "invalid PNG" in errors[0] or "corrupt" in errors[0].lower()


def test_url_image_references_skipped(tmp_path):
    """HTTPS image URLs are skipped (not validated)."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "report.md").write_text("![Logo](https://example.com/image.png)\n")

    errors = check_image_references(docs_dir, tmp_path)
    assert len(errors) == 0


def test_non_png_image_not_decoded(tmp_path):
    """Non-PNG images are existence-checked only, not decoded."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    # Create a .jpg file with arbitrary content (not a real JPEG)
    (docs_dir / "photo.jpg").write_bytes(b"not a real jpeg")
    (docs_dir / "icon.svg").write_text("<svg></svg>")
    (docs_dir / "report.md").write_text("![Photo](photo.jpg)\n![Icon](icon.svg)\n")

    errors = check_image_references(docs_dir, tmp_path)
    assert len(errors) == 0
