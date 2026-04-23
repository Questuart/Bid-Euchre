"""Unit tests for scripts/internal/verify_map_coverage.py.

Covers parsing, coverage math, placeholder detection, and CLI exit codes.
Seeded fixtures are inline so the test is hermetic.
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

import pytest

# Import the script directly since it lives under scripts/internal, which is
# not an importable package. The module must be registered in sys.modules
# *before* exec_module so that @dataclass can resolve cls.__module__ during
# class body evaluation (Python 3.12+ behavior).
_SPEC = importlib.util.spec_from_file_location(
    "verify_map_coverage",
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "internal"
    / "verify_map_coverage.py",
)
assert _SPEC is not None and _SPEC.loader is not None
vmc = importlib.util.module_from_spec(_SPEC)
sys.modules["verify_map_coverage"] = vmc
_SPEC.loader.exec_module(vmc)


def _write_map(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "map.md"
    p.write_text(textwrap.dedent(body).lstrip("\n"))
    return p


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_parse_single_row(tmp_path: Path) -> None:
    path = _write_map(
        tmp_path,
        """
        # Title

        | Deliverable | Class | Verification surface | Owner | Acceptance condition |
        |---|---|---|---|---|
        | A.1 schema | new module | tests/unit/test_schema.py | author | pytest passes |
        """,
    )
    rows = vmc.parse_map(path)
    assert len(rows) == 1
    assert rows[0].deliverable == "A.1 schema"
    assert rows[0].surface == "tests/unit/test_schema.py"


def test_parse_skips_header_and_separator(tmp_path: Path) -> None:
    path = _write_map(
        tmp_path,
        """
        | Deliverable | Class | Verification surface | Owner | Acceptance condition |
        |---|---|---|---|---|
        | D1 | c1 | s1 | o1 | a1 |
        | D2 | c2 | s2 | o2 | a2 |
        """,
    )
    rows = vmc.parse_map(path)
    assert [r.deliverable for r in rows] == ["D1", "D2"]


def test_parse_skips_illustrative_placeholder(tmp_path: Path) -> None:
    path = _write_map(
        tmp_path,
        """
        | Deliverable | Class | Verification surface | Owner | Acceptance condition |
        |---|---|---|---|---|
        | (row per Work bullet) | (per Pattern 10) | (path or command) | (lane) | (observable) |
        | A.1 | new module | tests/t.py | author | passes |
        """,
    )
    rows = vmc.parse_map(path)
    assert len(rows) == 1


def test_parse_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        vmc.parse_map(tmp_path / "nope.md")


# ---------------------------------------------------------------------------
# Coverage math
# ---------------------------------------------------------------------------


def test_coverage_all_rows_covered(tmp_path: Path) -> None:
    path = _write_map(
        tmp_path,
        """
        | Deliverable | Class | Verification surface | Owner | Acceptance |
        |---|---|---|---|---|
        | D1 | c | tests/x.py | author | passes |
        | D2 | c | tests/y.py | author | passes |
        """,
    )
    rows = vmc.parse_map(path)
    report = vmc.compute_coverage(rows)
    assert report.rows_total == 2
    assert report.rows_with_surface == 2
    assert report.coverage == 1.0


def test_coverage_placeholder_counted_against(tmp_path: Path) -> None:
    path = _write_map(
        tmp_path,
        """
        | Deliverable | Class | Verification surface | Owner | Acceptance |
        |---|---|---|---|---|
        | D1 | c | tests/x.py | author | passes |
        | D2 | c | TBD | author | passes |
        """,
    )
    rows = vmc.parse_map(path)
    report = vmc.compute_coverage(rows)
    assert report.rows_total == 2
    assert report.rows_with_surface == 1
    assert report.rows_with_placeholder == 1
    assert report.coverage == 0.5


@pytest.mark.parametrize("token", ["TBD", "TODO", "FIXME", "XXX"])
def test_coverage_each_placeholder_token(tmp_path: Path, token: str) -> None:
    path = _write_map(
        tmp_path,
        f"""
        | Deliverable | Class | Verification surface | Owner | Acceptance |
        |---|---|---|---|---|
        | D1 | c | includes {token} marker | author | passes |
        """,
    )
    rows = vmc.parse_map(path)
    report = vmc.compute_coverage(rows)
    assert report.rows_with_placeholder == 1


def test_coverage_empty_surface_counts_as_no_surface(tmp_path: Path) -> None:
    path = _write_map(
        tmp_path,
        """
        | Deliverable | Class | Verification surface | Owner | Acceptance |
        |---|---|---|---|---|
        | D1 | c | — | author | passes |
        """,
    )
    rows = vmc.parse_map(path)
    report = vmc.compute_coverage(rows)
    assert report.rows_with_surface == 0
    assert len(report.no_surface_rows) == 1


def test_coverage_empty_rows_returns_zero(tmp_path: Path) -> None:
    path = _write_map(tmp_path, "# No rows at all\n")
    rows = vmc.parse_map(path)
    assert rows == []
    report = vmc.compute_coverage(rows)
    assert report.coverage == 0.0
    assert report.rows_total == 0


# ---------------------------------------------------------------------------
# CLI exit codes
# ---------------------------------------------------------------------------


def test_cli_exit_zero_on_full_coverage(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write_map(
        tmp_path,
        """
        | Deliverable | Class | Verification surface | Owner | Acceptance |
        |---|---|---|---|---|
        | D1 | c | tests/x.py | author | passes |
        """,
    )
    rc = vmc.main([str(path), "--threshold", "0.90"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Coverage:              100.00%" in out


def test_cli_exit_two_on_under_threshold(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write_map(
        tmp_path,
        """
        | Deliverable | Class | Verification surface | Owner | Acceptance |
        |---|---|---|---|---|
        | D1 | c | tests/x.py | author | passes |
        | D2 | c | TBD | author | passes |
        """,
    )
    rc = vmc.main([str(path), "--threshold", "0.90"])
    assert rc == 2
    out = capsys.readouterr().out
    assert "Placeholder surfaces (BLOCK):" in out


def test_cli_exit_one_on_missing_file(tmp_path: Path) -> None:
    rc = vmc.main([str(tmp_path / "nope.md")])
    assert rc == 1


def test_cli_allow_under_coverage_override(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write_map(
        tmp_path,
        """
        | Deliverable | Class | Verification surface | Owner | Acceptance |
        |---|---|---|---|---|
        | D1 | c | TBD | author | passes |
        """,
    )
    rc = vmc.main([str(path), "--allow-under-coverage"])
    assert rc == 0
    err = capsys.readouterr().err
    assert "would have failed" in err


def test_cli_default_map_path_used_when_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invoking main([...]) resolves the default path; parser plumbing is exercised."""
    parser_argv: list[str] = []

    def fake_parse_map(path):  # type: ignore[no-untyped-def]
        parser_argv.append(str(path))
        return []

    monkeypatch.setattr(vmc, "parse_map", fake_parse_map)

    # With default threshold (0.90) and 0 rows → coverage 0.0 < 0.90 → exit 2.
    rc = vmc.main([])
    assert rc == 2
    assert parser_argv[0].endswith("map.md")

    # Re-run with threshold=0 to confirm default path plumbing also works when
    # coverage meets threshold.
    parser_argv.clear()
    rc = vmc.main(["--threshold", "0.0"])
    assert rc == 0
    assert parser_argv[0].endswith("map.md")
