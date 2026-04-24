"""Unit tests for ``scripts/internal/archivist.py``.

Per Primitive C shaping §4.7 (rollback round-trip) and §5.3 (live
rollback test). The critical invariant: promote → unpromote leaves the
target file byte-identical to its pre-promotion state.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "internal" / "archivist.py"


def _load_module():
    if "archivist" in sys.modules:
        return sys.modules["archivist"]
    spec = importlib.util.spec_from_file_location("archivist", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["archivist"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def kb_tree(tmp_path: Path) -> Path:
    """Minimal ``knowledge/`` tree sufficient for promote/unpromote."""
    kb = tmp_path / "knowledge"
    (kb / "adr").mkdir(parents=True)
    (kb / "incidents").mkdir()
    (kb / "_promoted").mkdir()
    (kb / "_candidates").mkdir()
    (kb / "NOTES.md").write_text(
        "# Notes\n\n## Worked example\n\n### Seed\n\n"
        "**Context:** x\n**Lesson:** y\n**Source:** z\n",
        encoding="utf-8",
    )
    (kb / "PLAYBOOKS.md").write_text(
        "# Playbooks\n\n### Seed\n\n**When:** x\n**Steps:** y\n"
        "**Verification:** z\n",
        encoding="utf-8",
    )
    (kb / "anti_patterns.md").write_text(
        "# Anti-patterns\n\n### Seed\n\n**Trigger:** x\n"
        "**Harm:** y\n**Preferred alternative:** z\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def lessons_candidate(kb_tree: Path) -> Path:
    """A lessons-kind candidate file ready to promote."""
    candidate = kb_tree / "candidate_lessons.md"
    candidate.write_text(
        "# Candidate\n\n"
        "## Candidate kind: lessons\n\n"
        "### Test lesson — round trip\n\n"
        "**Context:** promote/unpromote test.\n"
        "**Lesson:** byte-identical round trip.\n"
        "**Source:** tests/unit/test_archivist.py.\n",
        encoding="utf-8",
    )
    return candidate


# ---------------------------------------------------------------------------
# Classification / helpers
# ---------------------------------------------------------------------------


def test_classify_from_header(tmp_path: Path) -> None:
    mod = _load_module()
    p = tmp_path / "anything.md"
    p.write_text("## Candidate kind: runbook\n\nbody\n", encoding="utf-8")
    assert mod._classify_candidate(p, p.read_text(encoding="utf-8")) == "runbook"


def test_classify_from_filename(tmp_path: Path) -> None:
    mod = _load_module()
    p = tmp_path / "2026-04-24_lessons.md"
    p.write_text("no kind header\n", encoding="utf-8")
    assert mod._classify_candidate(p, p.read_text(encoding="utf-8")) == "lessons"


def test_classify_defaults_to_lessons(tmp_path: Path) -> None:
    mod = _load_module()
    p = tmp_path / "bare.md"
    p.write_text("no header at all\n", encoding="utf-8")
    assert mod._classify_candidate(p, p.read_text(encoding="utf-8")) == "lessons"


def test_content_hash_is_deterministic() -> None:
    mod = _load_module()
    assert mod._content_hash("abc\n") == mod._content_hash("abc\n")
    assert mod._content_hash("abc\n") != mod._content_hash("xyz\n")
    assert len(mod._content_hash("abc")) == 12


# ---------------------------------------------------------------------------
# Operator-gate (ADR 010)
# ---------------------------------------------------------------------------


def test_promote_without_operator_id_raises(
    kb_tree: Path, lessons_candidate: Path
) -> None:
    mod = _load_module()
    with pytest.raises(ValueError, match="operator_id is required"):
        mod.promote(kb_tree, lessons_candidate, operator_id="")


# ---------------------------------------------------------------------------
# Core round-trip invariant (§4.7 / §5.3)
# ---------------------------------------------------------------------------


def test_promote_and_unpromote_roundtrip_is_byte_identical(
    kb_tree: Path, lessons_candidate: Path
) -> None:
    """NOTES.md after promote → unpromote equals NOTES.md before promote."""
    mod = _load_module()
    notes = kb_tree / "knowledge" / "NOTES.md"
    before = notes.read_bytes()

    archive = mod.promote(kb_tree, lessons_candidate, operator_id="test-op")
    assert archive.exists()
    # Post-promote: NOTES.md grew, archive exists.
    assert len(notes.read_bytes()) > len(before)

    re_candidate = mod.unpromote(kb_tree, archive)
    after = notes.read_bytes()
    assert after == before, "round-trip not byte-identical"
    assert not archive.exists(), "archive should be removed on unpromote"
    assert re_candidate.exists(), "re-queued candidate should exist"


def test_promote_writes_archive_with_expected_metadata(
    kb_tree: Path, lessons_candidate: Path
) -> None:
    mod = _load_module()
    archive = mod.promote(kb_tree, lessons_candidate, operator_id="alice")
    text = archive.read_text(encoding="utf-8")
    assert "artifact_class: lessons" in text
    assert "operator_id: alice" in text
    assert "target: NOTES.md" in text
    assert "content_hash:" in text


def test_promote_detects_double_promotion(
    kb_tree: Path, lessons_candidate: Path
) -> None:
    """Promoting the same candidate twice fails loudly."""
    mod = _load_module()
    mod.promote(kb_tree, lessons_candidate, operator_id="test-op")
    with pytest.raises(RuntimeError, match="already promoted"):
        mod.promote(kb_tree, lessons_candidate, operator_id="test-op")


def test_unpromote_fails_if_target_hand_edited(
    kb_tree: Path, lessons_candidate: Path
) -> None:
    """If someone removes the markers manually, unpromote panics."""
    mod = _load_module()
    archive = mod.promote(kb_tree, lessons_candidate, operator_id="test-op")
    # Simulate hand-edit that wipes the block.
    notes = kb_tree / "knowledge" / "NOTES.md"
    notes.write_text("# Notes\n\nTrashed.\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="block markers"):
        mod.unpromote(kb_tree, archive)


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------


def test_cli_rejects_promote_without_operator_id(
    kb_tree: Path, lessons_candidate: Path
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--repo-root",
            str(kb_tree),
            "--promote",
            str(lessons_candidate),
        ],
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 2, result.stderr
    assert "operator_id" in result.stderr.lower()


def test_cli_end_to_end_roundtrip(kb_tree: Path, lessons_candidate: Path) -> None:
    notes = kb_tree / "knowledge" / "NOTES.md"
    before = notes.read_bytes()

    # Promote.
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--repo-root",
            str(kb_tree),
            "--operator-id",
            "cli-test",
            "--promote",
            str(lessons_candidate),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    promoted_dir = kb_tree / "knowledge" / "_promoted"
    archives = list(promoted_dir.glob("*.md"))
    assert len(archives) == 1
    archive = archives[0]

    # Unpromote.
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--repo-root",
            str(kb_tree),
            "--unpromote",
            str(archive),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    assert notes.read_bytes() == before, "CLI round-trip not byte-identical"
    assert not archive.exists()
