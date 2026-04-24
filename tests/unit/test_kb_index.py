"""Unit tests for ``scripts/internal/kb_index.py``.

Per Primitive C shaping §4.1.3 (deterministic regeneration). Tests are
fixture-based — we construct a synthetic ``knowledge/`` tree under a
temp directory and run the regenerator against it.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "internal" / "kb_index.py"


def _load_module():
    if "kb_index" in sys.modules:
        return sys.modules["kb_index"]
    spec = importlib.util.spec_from_file_location("kb_index", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["kb_index"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def fixture_kb(tmp_path: Path) -> Path:
    """Construct a minimal valid ``knowledge/`` tree for tests."""
    kb = tmp_path / "knowledge"
    (kb / "adr").mkdir(parents=True)
    (kb / "incidents").mkdir()
    (kb / "_promoted").mkdir()

    (kb / "NOTES.md").write_text(
        "# Notes\n\n## Worked example\n\n### Example lesson\n\n"
        "**Context:** test\n**Lesson:** unit test\n**Source:** fixture\n",
        encoding="utf-8",
    )
    (kb / "PLAYBOOKS.md").write_text(
        "# Playbooks\n\n### Example runbook\n\n**When:** test\n"
        "**Steps:** 1. do 2. check\n**Verification:** ok\n",
        encoding="utf-8",
    )
    (kb / "anti_patterns.md").write_text(
        "# Anti-patterns\n\n### Example anti-pattern\n\n"
        "**Trigger:** test\n**Harm:** test\n**Preferred alternative:** test\n",
        encoding="utf-8",
    )
    (kb / "harness_assumptions.md").write_text(
        "# Harness assumptions\n\n### Example assumption\n\n"
        "**Assumption:** x\n**Observation:** y\n"
        "**Brittleness signal:** `grep foo bar`\n"
        "**Refresh trigger:** on upgrade\n",
        encoding="utf-8",
    )
    (kb / "agent_readability_scorecard.md").write_text(
        "# Scorecard\n\n**Floor:** 7/10\n**Current:** 8/10\n",
        encoding="utf-8",
    )
    (kb / "external_signal_sources.md").write_text(
        "# External Signals\n\n### Source\n\n**URL:** x\n" "**Cadence:** weekly\n",
        encoding="utf-8",
    )
    (kb / "adr" / "README.md").write_text(
        "# ADR index\n\n### ADR 001\n\nFirst ADR.\n",
        encoding="utf-8",
    )
    (kb / "adr" / "001-example.md").write_text(
        "# ADR 001 Example\n\n### Context\n\nSome context.\n",
        encoding="utf-8",
    )
    (kb / "incidents" / "_example.md").write_text(
        "# Incident example\n\n### Incident example\n\n"
        "**First seen:** 2026-04-24\n**Symptoms:** test\n",
        encoding="utf-8",
    )
    (kb / "_promoted" / "2026-04-24_notes_abc123.md").write_text(
        "# Promoted entry\n\nSource: candidate path\n",
        encoding="utf-8",
    )
    return tmp_path


def test_regenerate_produces_nonempty_output(fixture_kb: Path) -> None:
    mod = _load_module()
    out = mod.regenerate(fixture_kb)
    assert "# Knowledge Base INDEX" in out
    assert "NOTES.md" in out
    assert "PLAYBOOKS.md" in out
    assert "anti_patterns.md" in out
    assert "harness_assumptions.md" in out
    assert "## `adr/`" in out
    assert "## `incidents/`" in out
    assert "## `_promoted/`" in out


def test_index_regenerates_deterministically(fixture_kb: Path) -> None:
    """Two consecutive runs produce byte-identical output."""
    mod = _load_module()
    first = mod.regenerate(fixture_kb)
    second = mod.regenerate(fixture_kb)
    assert first == second, "regenerate() is not deterministic"


def test_schema_violation_on_missing_worked_example(tmp_path: Path) -> None:
    """NOTES.md without a worked example triggers SchemaViolation."""
    mod = _load_module()
    kb = tmp_path / "knowledge"
    (kb / "adr").mkdir(parents=True)
    (kb / "incidents").mkdir()
    # NOTES.md has no worked example (no H3, no "## Worked example").
    (kb / "NOTES.md").write_text("# Notes\n\nPlain prose.\n", encoding="utf-8")
    # Fill the others so the scanner reaches NOTES.md.
    for name in (
        "PLAYBOOKS.md",
        "anti_patterns.md",
        "harness_assumptions.md",
    ):
        (kb / name).write_text(
            f"# {name}\n\n### example\n\n**Context:** x\n",
            encoding="utf-8",
        )
    with pytest.raises(mod.SchemaViolation):
        mod.regenerate(tmp_path)


def test_atomic_write_creates_file(tmp_path: Path) -> None:
    mod = _load_module()
    path = tmp_path / "out.md"
    mod.atomic_write(path, "hello\n")
    assert path.read_text(encoding="utf-8") == "hello\n"


def test_atomic_write_overwrites(tmp_path: Path) -> None:
    mod = _load_module()
    path = tmp_path / "out.md"
    path.write_text("old\n", encoding="utf-8")
    mod.atomic_write(path, "new\n")
    assert path.read_text(encoding="utf-8") == "new\n"


def test_cli_stdout_mode(fixture_kb: Path) -> None:
    """`--stdout` prints the INDEX without writing a file."""
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--repo-root",
            str(fixture_kb),
            "--stdout",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "# Knowledge Base INDEX" in result.stdout
    assert not (fixture_kb / "knowledge" / "INDEX.md").exists()


def test_cli_write_mode(fixture_kb: Path) -> None:
    """`--write` persists the INDEX to knowledge/INDEX.md."""
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--repo-root",
            str(fixture_kb),
            "--write",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    index_path = fixture_kb / "knowledge" / "INDEX.md"
    assert index_path.exists()
    assert "# Knowledge Base INDEX" in index_path.read_text(encoding="utf-8")


def test_cli_check_mode_detects_stale(fixture_kb: Path) -> None:
    """`--check` exits 2 when INDEX.md is stale."""
    # Write a stale INDEX by hand.
    (fixture_kb / "knowledge" / "INDEX.md").write_text("# Stale\n", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--repo-root",
            str(fixture_kb),
            "--check",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "stale" in result.stderr.lower() or "stale" in result.stdout.lower()


def test_cli_check_mode_clean_after_write(fixture_kb: Path) -> None:
    """`--check` exits 0 when INDEX.md matches regenerated output."""
    # Write the current INDEX.
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--repo-root",
            str(fixture_kb),
            "--write",
        ],
        check=True,
    )
    # Then check.
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--repo-root",
            str(fixture_kb),
            "--check",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0


def test_interface_contract_present_in_output(fixture_kb: Path) -> None:
    """The C↔D Interface Contract block is part of INDEX.md per §4.3."""
    mod = _load_module()
    out = mod.regenerate(fixture_kb)
    assert "Archivist C↔D Interface Contract" in out
    assert "D writes to:" in out
    assert "C reads from:" in out
    assert "kb_artifact_promoted" in out
    assert "archivist_candidate_generated" in out
