"""Unit tests for the B.11 orchestration-recipe archive lint.

Covers ``agent_readability_lint.check_recipes`` rules RC0–RC4 (shaping
§8.5 — Primitive B.11). Fixtures are inline and hermetic: each test
writes one or more minimal ``*.md`` files under a ``tmp_path`` archive
root and asserts which rule IDs fire.

Shared-module note (shaping §13.2 risk #2): the recipes check rides the
same lint harness as Pattern 10 (``check verification-contract``),
Pattern 9 (``check load-bearing-ownership``), B.3 (``check prompt-policy``),
and B.6 (``check tool-risk``). Keep this file lean — shared plan-walker
regressions live in ``test_agent_readability_lint.py``.
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "agent_readability_lint",
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "internal"
    / "agent_readability_lint.py",
)
assert _SPEC is not None and _SPEC.loader is not None
arl = importlib.util.module_from_spec(_SPEC)
sys.modules["agent_readability_lint"] = arl
_SPEC.loader.exec_module(arl)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _archive_root(tmp_path: Path) -> Path:
    """Return the conventional archive root under ``tmp_path`` (created)."""
    root = tmp_path / "knowledge" / "orchestration_recipes"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_recipe(path: Path, body: str) -> Path:
    """Write ``body`` to ``path``, dedenting and stripping the leading newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).lstrip("\n"), encoding="utf-8")
    return path


def _valid_recipe(slug: str = "pattern11", version: str = "v1.0") -> str:
    """Return a minimal recipe file body that satisfies RC2–RC3."""
    return f"""
    # Recipe: {slug}

    ## Version

    `b11-recipe-{slug}-v{version[1:]}`

    ## Context

    Observed in session 2026-04-23. Trace: PR #0.

    ## Decision

    Two-packet decomposition: shape + execute.

    ## Observed outcome

    Session 2026-04-23: 25 files, zero re-litigation.

    ## Reuse guidance

    Apply when scope crosses >3 files. Do NOT apply for single-file fixes.

    ## Downstream citations

    - (none yet)
    """


def _write_index(root: Path, entries: list[str]) -> Path:
    """Write an INDEX.md that references the given filenames."""
    body = "# Orchestration recipes index\n\n## Active recipes\n\n"
    for e in entries:
        body += f"- [{e}]({e})\n"
    index = root / "INDEX.md"
    index.write_text(body, encoding="utf-8")
    return index


# ---------------------------------------------------------------------------
# RC0 — archive root missing
# ---------------------------------------------------------------------------


class TestRC0MissingRoot:
    def test_missing_root_emits_rc0(self, tmp_path: Path) -> None:
        missing = tmp_path / "knowledge" / "orchestration_recipes"
        # Not created — should emit RC0.
        findings = arl.check_recipes([missing], tmp_path)
        ids = [f.rule_id for f in findings]
        assert "RC0" in ids
        assert any(f.severity.name == "BLOCK" for f in findings if f.rule_id == "RC0")


# ---------------------------------------------------------------------------
# RC1 — INDEX.md missing
# ---------------------------------------------------------------------------


class TestRC1MissingIndex:
    def test_missing_index_emits_rc1(self, tmp_path: Path) -> None:
        root = _archive_root(tmp_path)
        # A valid recipe exists but no INDEX.md — should emit RC1.
        _write_recipe(root / "sample.md", _valid_recipe(slug="sample"))
        findings = arl.check_recipes([root], tmp_path)
        ids = [f.rule_id for f in findings]
        assert "RC1" in ids
        assert any(f.severity.name == "BLOCK" for f in findings if f.rule_id == "RC1")

    def test_empty_archive_with_index_ok(self, tmp_path: Path) -> None:
        root = _archive_root(tmp_path)
        _write_index(root, [])
        findings = arl.check_recipes([root], tmp_path)
        # No recipes + empty INDEX = 0 findings (RC0 satisfied, no RC2/3/4 to trigger).
        assert findings == []


# ---------------------------------------------------------------------------
# RC2 — required sections
# ---------------------------------------------------------------------------


class TestRC2RequiredSections:
    @pytest.mark.parametrize(
        "dropped",
        [
            "Version",
            "Context",
            "Decision",
            "Observed outcome",
            "Reuse guidance",
            "Downstream citations",
        ],
    )
    def test_missing_each_section_emits_rc2(self, tmp_path: Path, dropped: str) -> None:
        root = _archive_root(tmp_path)
        # Start from the dedented body so line prefixes match the lint.
        body = textwrap.dedent(_valid_recipe(slug="drop")).lstrip("\n")
        # Drop the section: everything from `## <dropped>` until the next H2.
        kept: list[str] = []
        skipping = False
        for line in body.splitlines():
            if line.startswith(f"## {dropped}"):
                skipping = True
                continue
            if skipping and line.startswith("## "):
                skipping = False
            if not skipping:
                kept.append(line)
        redacted = "\n".join(kept)
        # Write the redacted body directly (bypass _write_recipe's dedent,
        # since we've already dedented above).
        target = root / "incomplete.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(redacted, encoding="utf-8")
        _write_index(root, ["incomplete.md"])

        findings = arl.check_recipes([root], tmp_path)
        rc2 = [f for f in findings if f.rule_id == "RC2"]
        assert rc2, (
            f"expected RC2 for missing '{dropped}'; "
            f"got: {[f.rule_id for f in findings]}\nBody:\n{redacted}"
        )
        assert any(dropped in f.message for f in rc2)

    def test_all_sections_present_no_rc2(self, tmp_path: Path) -> None:
        root = _archive_root(tmp_path)
        _write_recipe(root / "ok.md", _valid_recipe(slug="ok"))
        _write_index(root, ["ok.md"])
        findings = arl.check_recipes([root], tmp_path)
        assert not any(f.rule_id == "RC2" for f in findings)


# ---------------------------------------------------------------------------
# RC3 — version format
# ---------------------------------------------------------------------------


class TestRC3VersionFormat:
    def test_valid_version_passes(self, tmp_path: Path) -> None:
        root = _archive_root(tmp_path)
        _write_recipe(root / "ok.md", _valid_recipe(slug="ok", version="v3.7"))
        _write_index(root, ["ok.md"])
        findings = arl.check_recipes([root], tmp_path)
        assert not any(f.rule_id == "RC3" for f in findings)

    def test_wrong_prefix_fails(self, tmp_path: Path) -> None:
        root = _archive_root(tmp_path)
        body = _valid_recipe(slug="x").replace("`b11-recipe-x-v1.0`", "`recipe-x-v1.0`")
        _write_recipe(root / "wrong.md", body)
        _write_index(root, ["wrong.md"])
        findings = arl.check_recipes([root], tmp_path)
        assert any(f.rule_id == "RC3" for f in findings)

    def test_missing_version_patch_component_fails(self, tmp_path: Path) -> None:
        root = _archive_root(tmp_path)
        body = _valid_recipe(slug="x").replace(
            "`b11-recipe-x-v1.0`", "`b11-recipe-x-v1`"
        )
        _write_recipe(root / "bad.md", body)
        _write_index(root, ["bad.md"])
        findings = arl.check_recipes([root], tmp_path)
        assert any(f.rule_id == "RC3" for f in findings)

    def test_uppercase_slug_fails(self, tmp_path: Path) -> None:
        root = _archive_root(tmp_path)
        body = _valid_recipe(slug="x").replace(
            "`b11-recipe-x-v1.0`", "`b11-recipe-PATTERN11-v1.0`"
        )
        _write_recipe(root / "caps.md", body)
        _write_index(root, ["caps.md"])
        findings = arl.check_recipes([root], tmp_path)
        assert any(f.rule_id == "RC3" for f in findings)


# ---------------------------------------------------------------------------
# RC4 — INDEX.md references every recipe
# ---------------------------------------------------------------------------


class TestRC4IndexReferencesAllRecipes:
    def test_unreferenced_recipe_emits_rc4(self, tmp_path: Path) -> None:
        root = _archive_root(tmp_path)
        _write_recipe(root / "indexed.md", _valid_recipe(slug="indexed"))
        _write_recipe(root / "orphan.md", _valid_recipe(slug="orphan"))
        _write_index(root, ["indexed.md"])  # orphan.md omitted
        findings = arl.check_recipes([root], tmp_path)
        rc4 = [f for f in findings if f.rule_id == "RC4"]
        assert rc4, f"expected RC4 for orphan.md; got: {[f.rule_id for f in findings]}"
        assert any("orphan.md" in f.message for f in rc4)
        # RC4 is non-blocking (WARN).
        assert all(f.severity.name == "WARN" for f in rc4)

    def test_all_referenced_no_rc4(self, tmp_path: Path) -> None:
        root = _archive_root(tmp_path)
        _write_recipe(root / "a.md", _valid_recipe(slug="a"))
        _write_recipe(root / "b.md", _valid_recipe(slug="b"))
        _write_index(root, ["a.md", "b.md"])
        findings = arl.check_recipes([root], tmp_path)
        assert not any(f.rule_id == "RC4" for f in findings)


# ---------------------------------------------------------------------------
# Exclusions: _template.md, INDEX.md, _archive/
# ---------------------------------------------------------------------------


class TestExclusions:
    def test_template_skipped(self, tmp_path: Path) -> None:
        root = _archive_root(tmp_path)
        # Template has minimal/invalid body; lint must skip it.
        (root / "_template.md").write_text(
            "# Template\nno required sections here\n", encoding="utf-8"
        )
        _write_index(root, [])
        findings = arl.check_recipes([root], tmp_path)
        # No RC2/RC3/RC4 findings sourced from _template.md.
        for f in findings:
            assert "_template.md" not in str(f.path)

    def test_index_skipped(self, tmp_path: Path) -> None:
        root = _archive_root(tmp_path)
        _write_index(root, [])
        # INDEX.md itself must not trigger RC2 (missing sections).
        findings = arl.check_recipes([root], tmp_path)
        for f in findings:
            assert f.path.name != "INDEX.md" or f.rule_id == "RC1"

    def test_archive_subdir_skipped(self, tmp_path: Path) -> None:
        root = _archive_root(tmp_path)
        archive_dir = root / "_archive"
        archive_dir.mkdir()
        # A retired recipe with no sections — must be skipped entirely.
        (archive_dir / "retired.md").write_text(
            "# Retired\nno sections\n", encoding="utf-8"
        )
        _write_index(root, [])
        findings = arl.check_recipes([root], tmp_path)
        for f in findings:
            assert "retired.md" not in str(f.path)


# ---------------------------------------------------------------------------
# CLI integration: invoke main() to exercise argparse + _default_roots wiring
# ---------------------------------------------------------------------------


class TestCLIIntegration:
    def test_cli_clean_archive_exits_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root = _archive_root(tmp_path)
        _write_recipe(root / "ok.md", _valid_recipe(slug="ok"))
        _write_index(root, ["ok.md"])
        code = arl.main(["--repo-root", str(tmp_path), "check", "recipes", str(root)])
        assert code == 0
        captured = capsys.readouterr()
        assert "0 findings" in captured.out

    def test_cli_missing_archive_returns_block_exit(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        missing = tmp_path / "knowledge" / "orchestration_recipes"
        code = arl.main(
            ["--repo-root", str(tmp_path), "check", "recipes", str(missing)]
        )
        # Non-strict rule-set: missing path produces RC0, exits 2.
        assert code == 2
        captured = capsys.readouterr()
        assert "RC0" in captured.out


# ---------------------------------------------------------------------------
# Live-tree regression guard: the committed archive must lint cleanly.
# ---------------------------------------------------------------------------


class TestLiveTreeClean:
    def test_repo_archive_has_no_findings(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        archive = repo_root / "knowledge" / "orchestration_recipes"
        if not archive.is_dir():
            pytest.skip("archive not present (pre-B.11)")
        findings = arl.check_recipes([archive], repo_root)
        block = [f for f in findings if f.severity.name == "BLOCK"]
        assert not block, f"live archive has BLOCK findings: {block}"
