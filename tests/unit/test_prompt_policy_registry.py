"""Unit tests for the B.3 prompt-policy registry lint.

Covers ``agent_readability_lint.check_prompt_policy`` rules PP0–PP4
(shaping §4.2 / §10.1 / §10.6 — Primitive B execution spec). Fixtures are
inline and hermetic: each test writes one or more minimal ``*.md`` files
under a ``tmp_path`` policy root and asserts which rule IDs fire.

Shared-module note (shaping §13.2 risk #2): the prompt-policy check rides
the same lint harness as Pattern 10 (``check verification-contract``).
Keep this file lean — shared plan-walker regressions live in
``test_agent_readability_lint.py``.
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


def _policy_root(tmp_path: Path) -> Path:
    """Return the conventional policy root under ``tmp_path`` (created)."""
    root = tmp_path / ".claude" / "rules" / "prompt_policy"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_policy(path: Path, body: str) -> Path:
    """Write ``body`` to ``path``, dedenting and stripping the leading newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).lstrip("\n"), encoding="utf-8")
    return path


def _valid_policy(archetype: str = "author", version: str = "v1.0") -> str:
    """Return a minimal policy file body that satisfies PP1–PP4."""
    return f"""
    # {archetype.title()} Prompt Policy

    > One-line doc blockquote.

    ## Version

    `{archetype}-{version}`

    ## Trigger

    Initial registry version. Landed in PR #0 (commit `abc1234`).

    ## Expected effect

    Visible signal: observable X rises from baseline to Y in the proving run.

    ## Rollback

    `git revert <SHA>` restores the prior version. Trace signature: field Z.

    ## Policy clauses

    ### Example clause

    Do the thing.
    """


# ---------------------------------------------------------------------------
# Happy path — live-tree shape passes
# ---------------------------------------------------------------------------


def test_valid_policy_file_emits_no_findings(tmp_path: Path) -> None:
    root = _policy_root(tmp_path)
    _write_policy(root / "author.md", _valid_policy("author"))
    findings = arl.check_prompt_policy([root], repo_root=tmp_path)
    assert findings == [], f"expected clean, got {[f.format_line() for f in findings]}"


def test_multiple_valid_policy_files_clean(tmp_path: Path) -> None:
    root = _policy_root(tmp_path)
    for name in ("orchestrator", "author", "analyst", "common"):
        _write_policy(root / f"{name}.md", _valid_policy(name))
    findings = arl.check_prompt_policy([root], repo_root=tmp_path)
    assert findings == [], f"expected clean, got {[f.format_line() for f in findings]}"


# ---------------------------------------------------------------------------
# PP0 — zero files is a WARN (pointer/typo likely)
# ---------------------------------------------------------------------------


def test_pp0_warns_on_empty_policy_tree(tmp_path: Path) -> None:
    empty_root = tmp_path / ".claude" / "rules" / "prompt_policy"
    empty_root.mkdir(parents=True, exist_ok=True)
    findings = arl.check_prompt_policy([empty_root], repo_root=tmp_path)
    pp0 = [f for f in findings if f.rule_id == "PP0"]
    assert len(pp0) == 1, f"expected 1 PP0 finding, got {len(pp0)}"
    assert pp0[0].severity == arl.Severity.WARN


def test_pp0_warns_when_default_root_missing(tmp_path: Path) -> None:
    # No .claude/rules/prompt_policy under tmp_path → default-root scan
    # should emit PP0 (and nothing else).
    findings = arl.check_prompt_policy([], repo_root=tmp_path)
    rule_ids = {f.rule_id for f in findings}
    assert rule_ids == {"PP0"}


# ---------------------------------------------------------------------------
# PP2 — missing required sections
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "missing", ["Version", "Trigger", "Expected effect", "Rollback"]
)
def test_pp2_flags_missing_required_section(tmp_path: Path, missing: str) -> None:
    root = _policy_root(tmp_path)
    body = _valid_policy()
    # Strip the single offending section (heading + content up to next ##).
    # Keep it simple: replace the full section block with an empty line.
    lines = body.splitlines()
    out: list[str] = []
    skipping = False
    for ln in lines:
        stripped = ln.strip()
        if stripped.lower() == f"## {missing}".lower():
            skipping = True
            continue
        if skipping and stripped.startswith("## "):
            skipping = False
        if not skipping:
            out.append(ln)
    _write_policy(root / "author.md", "\n".join(out) + "\n")
    findings = arl.check_prompt_policy([root], repo_root=tmp_path)
    pp2 = [f for f in findings if f.rule_id == "PP2"]
    assert any(missing in f.message for f in pp2), (
        f"expected PP2 mentioning {missing!r}, got "
        f"{[f.format_line() for f in findings]}"
    )
    assert all(f.severity == arl.Severity.BLOCK for f in pp2)


def test_pp2_reports_each_missing_section_separately(tmp_path: Path) -> None:
    root = _policy_root(tmp_path)
    # Missing Trigger AND Rollback.
    _write_policy(
        root / "broken.md",
        """
        # Broken Policy

        ## Version

        `author-v1.0`

        ## Expected effect

        Something observable.

        ## Policy clauses
        """,
    )
    findings = arl.check_prompt_policy([root], repo_root=tmp_path)
    pp2 = [f for f in findings if f.rule_id == "PP2"]
    assert len(pp2) == 2, f"expected 2 PP2 findings, got {len(pp2)}"
    messages = " | ".join(f.message for f in pp2)
    assert "Trigger" in messages
    assert "Rollback" in messages


# ---------------------------------------------------------------------------
# PP3 — Version format rules
# ---------------------------------------------------------------------------


def test_pp3_flags_missing_backticks(tmp_path: Path) -> None:
    root = _policy_root(tmp_path)
    _write_policy(
        root / "author.md",
        """
        # Author Prompt Policy

        ## Version

        author-v1.0

        ## Trigger

        Initial.

        ## Expected effect

        Works.

        ## Rollback

        Revert.
        """,
    )
    findings = arl.check_prompt_policy([root], repo_root=tmp_path)
    pp3 = [f for f in findings if f.rule_id == "PP3"]
    assert len(pp3) == 1
    assert pp3[0].severity == arl.Severity.BLOCK
    assert "backticked" in pp3[0].message.lower() or "does not match" in pp3[0].message


@pytest.mark.parametrize(
    "bad_version",
    [
        "`author`",  # no version
        "`author-1.0`",  # missing v prefix
        "`author-v1`",  # missing minor
        "`Author-v1.0`",  # uppercase archetype
        "`author-vX.0`",  # non-numeric major
        "`v1.0`",  # no archetype
    ],
)
def test_pp3_flags_malformed_version(tmp_path: Path, bad_version: str) -> None:
    root = _policy_root(tmp_path)
    _write_policy(
        root / "author.md",
        f"""
        # Policy

        ## Version

        {bad_version}

        ## Trigger

        x

        ## Expected effect

        y

        ## Rollback

        z
        """,
    )
    findings = arl.check_prompt_policy([root], repo_root=tmp_path)
    pp3 = [f for f in findings if f.rule_id == "PP3"]
    assert pp3, f"expected PP3 for {bad_version!r}, got {[f.rule_id for f in findings]}"
    assert all(f.severity == arl.Severity.BLOCK for f in pp3)


def test_pp3_flags_empty_version_body(tmp_path: Path) -> None:
    root = _policy_root(tmp_path)
    _write_policy(
        root / "author.md",
        """
        # Policy

        ## Version

        ## Trigger

        x

        ## Expected effect

        y

        ## Rollback

        z
        """,
    )
    findings = arl.check_prompt_policy([root], repo_root=tmp_path)
    pp3 = [f for f in findings if f.rule_id == "PP3"]
    assert len(pp3) == 1
    assert pp3[0].severity == arl.Severity.BLOCK
    assert "empty" in pp3[0].message.lower()


def test_pp3_accepts_multidigit_versions(tmp_path: Path) -> None:
    root = _policy_root(tmp_path)
    _write_policy(root / "author.md", _valid_policy("author", "v12.37"))
    findings = arl.check_prompt_policy([root], repo_root=tmp_path)
    assert not any(f.rule_id == "PP3" for f in findings)


def test_pp3_accepts_hyphenated_archetype(tmp_path: Path) -> None:
    root = _policy_root(tmp_path)
    _write_policy(root / "brws-author.md", _valid_policy("brws-author"))
    findings = arl.check_prompt_policy([root], repo_root=tmp_path)
    assert not any(f.rule_id == "PP3" for f in findings)


# ---------------------------------------------------------------------------
# PP4 — empty body under Trigger / Expected effect / Rollback
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("section", ["Trigger", "Expected effect", "Rollback"])
def test_pp4_flags_empty_body(tmp_path: Path, section: str) -> None:
    root = _policy_root(tmp_path)
    lines = [
        "# Policy",
        "",
        "## Version",
        "",
        "`author-v1.0`",
        "",
        "## Trigger",
        "",
        "Real trigger text." if section != "Trigger" else "",
        "",
        "## Expected effect",
        "",
        "Real effect text." if section != "Expected effect" else "",
        "",
        "## Rollback",
        "",
        "Real rollback text." if section != "Rollback" else "",
        "",
    ]
    _write_policy(root / "author.md", "\n".join(lines) + "\n")
    findings = arl.check_prompt_policy([root], repo_root=tmp_path)
    pp4 = [f for f in findings if f.rule_id == "PP4"]
    assert len(pp4) == 1, (
        f"expected 1 PP4 for empty {section!r} body, got "
        f"{[f.format_line() for f in findings]}"
    )
    assert pp4[0].severity == arl.Severity.BLOCK
    assert section in pp4[0].message


# ---------------------------------------------------------------------------
# CLI integration — exit code round-trip
# ---------------------------------------------------------------------------


def test_cli_prompt_policy_clean_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _policy_root(tmp_path)
    _write_policy(root / "author.md", _valid_policy("author"))
    rc = arl.main(
        [
            "--repo-root",
            str(tmp_path),
            "check",
            "prompt-policy",
            str(root),
        ]
    )
    assert rc == 0
    assert "0 findings" in capsys.readouterr().out


def test_cli_prompt_policy_block_exits_two(tmp_path: Path) -> None:
    root = _policy_root(tmp_path)
    _write_policy(
        root / "broken.md",
        """
        # Broken

        ## Version

        author-v1.0
        """,
    )
    rc = arl.main(
        [
            "--repo-root",
            str(tmp_path),
            "check",
            "prompt-policy",
            str(root),
        ]
    )
    assert rc == 2


def test_cli_prompt_policy_default_root_used_when_no_path(tmp_path: Path) -> None:
    # No path argument; default_root = tmp_path/.claude/rules/prompt_policy.
    # We do not create it → PP0 fires → exit 2 (WARN, strict mode).
    rc = arl.main(
        [
            "--repo-root",
            str(tmp_path),
            "check",
            "prompt-policy",
        ]
    )
    assert rc == 2

    # With --warnings-ok, PP0 downgrades to exit 0.
    rc_relaxed = arl.main(
        [
            "--repo-root",
            str(tmp_path),
            "--warnings-ok",
            "check",
            "prompt-policy",
        ]
    )
    assert rc_relaxed == 0


# ---------------------------------------------------------------------------
# Self-run: the live policy directory must be clean at B-exec.α merge time.
# ---------------------------------------------------------------------------


def test_live_prompt_policy_tree_is_clean() -> None:
    """Regression guard: B.3 schema lint exits clean against the live tree.

    If this fails after editing a policy file, restore the 4 required
    sections or the canonical backticked version line — do not relax the
    lint.
    """
    repo_root = Path(__file__).resolve().parents[2]
    target = repo_root / ".claude" / "rules" / "prompt_policy"
    if not target.exists():
        pytest.skip(f"prompt_policy tree not found at {target}")
    findings = arl.check_prompt_policy([target], repo_root=repo_root)
    blocks = [f for f in findings if f.severity == arl.Severity.BLOCK]
    assert not blocks, "BLOCK findings:\n" + "\n".join(f.format_line() for f in blocks)
