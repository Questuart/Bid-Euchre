"""Unit tests for ``scripts/internal/agent_readability_score.py``.

Per Primitive C shaping §4.2 (``plans/steward_platform/3_primitive_C/shaping.md``).
The tests build a minimum viable repo fixture that satisfies each of
the 10 items, then poke individual items off to verify FAIL paths.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "internal" / "agent_readability_score.py"


def _load_module():
    if "agent_readability_score" in sys.modules:
        return sys.modules["agent_readability_score"]
    spec = importlib.util.spec_from_file_location(
        "agent_readability_score", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["agent_readability_score"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixture: a repo tree that *passes* every scorecard item
# ---------------------------------------------------------------------------


def _build_passing_repo(root: Path) -> None:
    """Populate ``root`` with a fixture that scores 10/10.

    The layout mirrors the live repo structure closely enough that each
    item's check finds what it looks for without false positives.
    """
    # Item 1 & 2 — CLAUDE.md: one H1, Project Overview, ≤200 lines.
    # Also references 75_worktree_protection.md so item 10 passes.
    (root / "CLAUDE.md").write_text(
        "# Project Title\n"
        "\n"
        "## Project Overview\n"
        "\n"
        "Entry point for new sessions.\n"
        "\n"
        "## Active Governing Plans\n"
        "\n"
        "- `plans/example_initiative/governing_plan.md`\n"
        "\n"
        "See `.claude/rules/75_worktree_protection.md` for lane pool registry.\n",
        encoding="utf-8",
    )
    # Item 2 — .claude/CLAUDE.md with marker (redundant but present).
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    (root / ".claude" / "CLAUDE.md").write_text(
        "# Dotclaude\n\n## Project Overview\n\npointer\n", encoding="utf-8"
    )
    # Item 3 — MEMORY.md with governing-plan reference + high link ratio.
    (root / "MEMORY.md").write_text(
        "# Memory\n\n"
        "See [plan](plans/example_initiative/governing_plan.md) for details.\n"
        "See [rules](.claude/rules/10_workflow.md) for rules.\n"
        "See [skills](.claude/skills/create-plan/SKILL.md) for skills.\n",
        encoding="utf-8",
    )
    # Item 4 — .claude/skills with valid frontmatter.
    skill_dir = root / ".claude" / "skills" / "demo-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: a demo skill.\n---\n\nBody.\n",
        encoding="utf-8",
    )
    # Item 5 — 75_worktree_protection.md with all five pools.
    rules_dir = root / ".claude" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / "75_worktree_protection.md").write_text(
        textwrap.dedent(
            """\
            # Worktree Protection

            **Platform pool:**
            - `Bid-Euchre-steward-author`
            - `Bid-Euchre-steward-author-b`

            **Browser-game pool:**
            - `Bid-Euchre-steward-brws-author-a`

            **Analyst pool:**
            - `Bid-Euchre-steward-analyst`

            **Flex pool:**
            - `Bid-Euchre-steward-flex-a`

            **Control plane:**
            - `Bid-Euchre-steward-review`
            - `Bid-Euchre-steward-ops`
            """
        ),
        encoding="utf-8",
    )
    # Item 10 — rules files must all be referenced. Already the case
    # because 75_worktree_protection.md is the only rule.
    # Item 7 — ADR directory with one file + README index row.
    adr_dir = root / "knowledge" / "adr"
    adr_dir.mkdir(parents=True, exist_ok=True)
    (adr_dir / "001-example.md").write_text("# ADR 001\n\nBody.\n", encoding="utf-8")
    (adr_dir / "README.md").write_text(
        "# ADRs\n\n## Index\n\n" "| ID | Title |\n|---|---|\n" "| 001 | example |\n",
        encoding="utf-8",
    )
    # Item 8 — stub kb_index.py that always exits 0 on --check.
    scripts_dir = root / "scripts" / "internal"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "kb_index.py").write_text(
        "import sys\nsys.exit(0)\n", encoding="utf-8"
    )
    # Item 9 — stub agent_readability_lint.py that always exits 0.
    (scripts_dir / "agent_readability_lint.py").write_text(
        "import sys\nsys.exit(0)\n", encoding="utf-8"
    )


@pytest.fixture
def passing_repo(tmp_path: Path) -> Path:
    _build_passing_repo(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# Floor enforcement (ADR 001)
# ---------------------------------------------------------------------------


def test_floor_below_adr_floor_is_rejected(passing_repo: Path) -> None:
    mod = _load_module()
    rc = mod.main(["--repo-root", str(passing_repo), "--floor", "6", "--stdout"])
    assert rc == 2


def test_floor_default_is_seven(passing_repo: Path) -> None:
    mod = _load_module()
    assert mod.ADR_FLOOR == 7


def test_cli_rejects_floor_below_seven(passing_repo: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--repo-root",
            str(passing_repo),
            "--floor",
            "5",
            "--stdout",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "ADR 001" in result.stderr


# ---------------------------------------------------------------------------
# Happy path: fixture scores 10/10
# ---------------------------------------------------------------------------


def test_passing_fixture_scores_ten_of_ten(passing_repo: Path) -> None:
    mod = _load_module()
    results = mod.score(passing_repo)
    failed = [r for r in results if not r.passed]
    assert (
        not failed
    ), f"expected all pass; got fails: {[(r.number, r.detail) for r in failed]}"


def test_stdout_report_shape(
    passing_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mod = _load_module()
    rc = mod.main(["--repo-root", str(passing_repo), "--stdout"])
    captured = capsys.readouterr()
    assert rc == 0
    lines = captured.out.strip().splitlines()
    assert lines[0] == "agent_readability_score: 10/10"
    # One line per item plus the header.
    assert len(lines) == 11


# ---------------------------------------------------------------------------
# Individual items — FAIL paths
# ---------------------------------------------------------------------------


def test_item_1_fails_when_claude_md_exceeds_200_lines(passing_repo: Path) -> None:
    mod = _load_module()
    (passing_repo / "CLAUDE.md").write_text(
        "# Title\n\n## Project Overview\n\n"
        + ("filler line\n" * 250)
        + "\n`plans/example_initiative/governing_plan.md`\n",
        encoding="utf-8",
    )
    results = mod.score(passing_repo)
    r1 = results[0]
    assert r1.slug == "claude_md_line_count"
    assert not r1.passed
    assert "limit 200" in r1.detail


def test_item_2_fails_on_multiple_h1(passing_repo: Path) -> None:
    mod = _load_module()
    (passing_repo / "CLAUDE.md").write_text(
        "# A\n\n## Project Overview\n\n# B\n"
        "\n`plans/example_initiative/governing_plan.md`\n",
        encoding="utf-8",
    )
    results = mod.score(passing_repo)
    r2 = results[1]
    assert r2.slug == "canonical_entry"
    assert not r2.passed


def test_item_3_fails_when_no_governing_plan_ref(passing_repo: Path) -> None:
    mod = _load_module()
    (passing_repo / "CLAUDE.md").write_text(
        "# Title\n\n## Project Overview\n\nNo plans ref.\n", encoding="utf-8"
    )
    (passing_repo / "MEMORY.md").write_text("# Memory\n\nNo refs.\n", encoding="utf-8")
    results = mod.score(passing_repo)
    r3 = results[2]
    assert r3.slug == "governing_plan_findable"
    assert not r3.passed


def test_item_4_fails_on_skill_without_frontmatter(passing_repo: Path) -> None:
    mod = _load_module()
    bad_skill = passing_repo / ".claude" / "skills" / "bad-skill"
    bad_skill.mkdir(parents=True, exist_ok=True)
    (bad_skill / "SKILL.md").write_text("no frontmatter here\n", encoding="utf-8")
    results = mod.score(passing_repo)
    r4 = results[3]
    assert r4.slug == "skills_discoverable"
    assert not r4.passed


def test_item_5_fails_when_pool_missing(passing_repo: Path) -> None:
    mod = _load_module()
    (passing_repo / ".claude" / "rules" / "75_worktree_protection.md").write_text(
        "# Protection\n- `Bid-Euchre-steward-author`\n", encoding="utf-8"
    )
    results = mod.score(passing_repo)
    r5 = results[4]
    assert r5.slug == "lane_registry_authoritative"
    assert not r5.passed
    assert "browser" in r5.detail or "control" in r5.detail


def test_item_6_fails_when_memory_missing(passing_repo: Path) -> None:
    mod = _load_module()
    (passing_repo / "MEMORY.md").unlink()
    results = mod.score(passing_repo)
    r6 = results[5]
    assert r6.slug == "memory_indexes"
    assert not r6.passed
    assert "not found" in r6.detail


def test_item_6_fails_when_link_ratio_below_threshold(passing_repo: Path) -> None:
    mod = _load_module()
    # 20 non-blank lines, 1 link → ratio 0.05 < 0.10.
    body = "# Memory\n\n" + "\n".join(f"line {i}" for i in range(20))
    body += "\n\n[only](one/link.md)\n"
    (passing_repo / "MEMORY.md").write_text(body, encoding="utf-8")
    results = mod.score(passing_repo)
    r6 = results[5]
    assert not r6.passed
    assert "link-ratio" in r6.detail


def test_item_7_fails_when_adr_missing_from_index(passing_repo: Path) -> None:
    mod = _load_module()
    # Add a second ADR file but keep the index showing only 001.
    (passing_repo / "knowledge" / "adr" / "002-new.md").write_text(
        "# ADR 002\n", encoding="utf-8"
    )
    results = mod.score(passing_repo)
    r7 = results[6]
    assert r7.slug == "adr_index_current"
    assert not r7.passed
    assert "002" in r7.detail


def test_item_8_fails_when_kb_index_check_exits_nonzero(passing_repo: Path) -> None:
    mod = _load_module()
    (passing_repo / "scripts" / "internal" / "kb_index.py").write_text(
        "import sys\nsys.exit(2)\n", encoding="utf-8"
    )
    results = mod.score(passing_repo)
    r8 = results[7]
    assert r8.slug == "kb_index_current"
    assert not r8.passed


def test_item_9_fails_when_lint_exits_block(passing_repo: Path) -> None:
    mod = _load_module()
    (passing_repo / "scripts" / "internal" / "agent_readability_lint.py").write_text(
        "import sys\nprint('BLOCK LBO1 fake finding')\nsys.exit(2)\n",
        encoding="utf-8",
    )
    results = mod.score(passing_repo)
    r9 = results[8]
    assert r9.slug == "no_orphan_refs"
    assert not r9.passed


def test_item_10_fails_when_rule_file_is_orphan(passing_repo: Path) -> None:
    mod = _load_module()
    (passing_repo / ".claude" / "rules" / "99_orphan_rule.md").write_text(
        "# Orphan\n", encoding="utf-8"
    )
    results = mod.score(passing_repo)
    r10 = results[9]
    assert r10.slug == "rules_grep_discoverable"
    assert not r10.passed
    assert "99_orphan_rule.md" in r10.detail


# ---------------------------------------------------------------------------
# --write mode
# ---------------------------------------------------------------------------


def test_write_mode_creates_scorecard_file(passing_repo: Path) -> None:
    mod = _load_module()
    rc = mod.main(["--repo-root", str(passing_repo), "--write"])
    assert rc == 0
    scorecard = passing_repo / "knowledge" / "agent_readability_scorecard.md"
    assert scorecard.exists()
    text = scorecard.read_text(encoding="utf-8")
    assert "Floor (per ADR 001)" in text
    assert "10/10" in text


def test_write_mode_rewrites_existing_scorecard(passing_repo: Path) -> None:
    mod = _load_module()
    mod.main(["--repo-root", str(passing_repo), "--write"])
    scorecard = passing_repo / "knowledge" / "agent_readability_scorecard.md"
    first = scorecard.read_text(encoding="utf-8")
    mod.main(["--repo-root", str(passing_repo), "--write"])
    second = scorecard.read_text(encoding="utf-8")
    # Same score; content is timestamp-dependent but must still contain 10/10.
    assert "10/10" in first and "10/10" in second


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------


def test_cli_stdout_smoke(passing_repo: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--repo-root",
            str(passing_repo),
            "--stdout",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "agent_readability_score: 10/10" in result.stdout


def test_cli_exits_two_when_score_below_floor(passing_repo: Path) -> None:
    # Break a few items to push score below 7.
    (passing_repo / "MEMORY.md").unlink()
    (passing_repo / ".claude" / "skills" / "bad").mkdir(parents=True, exist_ok=True)
    (passing_repo / ".claude" / "skills" / "bad" / "SKILL.md").write_text(
        "no frontmatter\n", encoding="utf-8"
    )
    (passing_repo / "knowledge" / "adr" / "002-new.md").write_text(
        "# ADR 002\n", encoding="utf-8"
    )
    (passing_repo / ".claude" / "rules" / "99_orphan.md").write_text(
        "# Orphan\n", encoding="utf-8"
    )
    (passing_repo / "scripts" / "internal" / "kb_index.py").write_text(
        "import sys\nsys.exit(2)\n", encoding="utf-8"
    )
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--repo-root",
            str(passing_repo),
            "--stdout",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "floor" in result.stderr.lower()
