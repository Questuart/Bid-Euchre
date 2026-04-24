"""Unit tests for the B.6 tool risk registry lint.

Covers ``agent_readability_lint.check_tool_risk`` rules TR0–TR4
(shaping §5.1 / §5.2 — Primitive B-exec.α execution spec) and the
allow-list cross-check helper ``_load_permissions_allow``.

Fixtures are inline and hermetic — each test writes a minimal
``tool_risk_registry.md`` (and a matching ``.claude/settings.json``
when the allow-coverage rule is under test) under ``tmp_path`` and
asserts which rule IDs fire.
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


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).lstrip("\n"), encoding="utf-8")
    return path


def _registry_path(tmp_path: Path) -> Path:
    return tmp_path / ".claude" / "rules" / "tool_risk_registry.md"


def _settings_path(tmp_path: Path) -> Path:
    return tmp_path / ".claude" / "settings.json"


def _write_valid_registry(tmp_path: Path, extra_rows: str = "") -> Path:
    """Write a minimal valid registry at the canonical path."""
    body = """
    # Tool Risk Registry

    > Dual-envelope classification.

    ## Version

    `tool-risk-v1.0`

    ## Trigger

    Initial version.

    ## Expected effect

    Lookup succeeds.

    ## Rollback

    Revert.

    ## Approval classes

    - direct / approve / edit / reject.

    ## Registry

    | Tool | Auto-mode envelope (Opus) | Bypass envelope (Sonnet/Haiku) | Notes |
    |---|---|---|---|
    | `Read` | direct | direct | Read-only |
    | `Bash(git *)` | direct | direct | Version control |
    {extra_rows}
    """
    return _write(
        _registry_path(tmp_path),
        body.format(extra_rows=extra_rows),
    )


def _write_settings(tmp_path: Path, allow: list[str]) -> Path:
    entries = ",\n    ".join(f'"{e}"' for e in allow)
    body = f"""{{
  "permissions": {{
    "allow": [
    {entries}
    ],
    "deny": []
  }}
}}
"""
    return _write(_settings_path(tmp_path), body)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_valid_registry_emits_no_findings(tmp_path: Path) -> None:
    _write_valid_registry(tmp_path)
    _write_settings(tmp_path, ["Bash(git *)"])
    findings = arl.check_tool_risk([], repo_root=tmp_path)
    assert findings == [], f"expected clean, got {[f.format_line() for f in findings]}"


# ---------------------------------------------------------------------------
# TR0 — registry file missing
# ---------------------------------------------------------------------------


def test_tr0_flags_missing_registry(tmp_path: Path) -> None:
    findings = arl.check_tool_risk([], repo_root=tmp_path)
    tr0 = [f for f in findings if f.rule_id == "TR0"]
    assert len(tr0) == 1
    assert tr0[0].severity == arl.Severity.BLOCK
    # No other rules run when the registry is missing — short-circuit.
    assert {f.rule_id for f in findings} == {"TR0"}


# ---------------------------------------------------------------------------
# TR1 — registry has no rows
# ---------------------------------------------------------------------------


def test_tr1_flags_empty_registry(tmp_path: Path) -> None:
    _write(
        _registry_path(tmp_path),
        """
        # Tool Risk Registry

        ## Registry

        Table coming soon.
        """,
    )
    findings = arl.check_tool_risk([], repo_root=tmp_path)
    tr1 = [f for f in findings if f.rule_id == "TR1"]
    assert len(tr1) == 1
    assert tr1[0].severity == arl.Severity.BLOCK


# ---------------------------------------------------------------------------
# TR2 — invalid envelope column
# ---------------------------------------------------------------------------


def test_tr2_flags_empty_envelope_cell(tmp_path: Path) -> None:
    _write(
        _registry_path(tmp_path),
        """
        # Registry

        | Tool | Auto-mode envelope | Bypass envelope | Notes |
        |---|---|---|---|
        | `Read` |  | direct | missing auto |
        """,
    )
    _write_settings(tmp_path, [])
    findings = arl.check_tool_risk([], repo_root=tmp_path)
    tr2 = [f for f in findings if f.rule_id == "TR2"]
    assert tr2, f"expected TR2; got {[f.format_line() for f in findings]}"
    assert all(f.severity == arl.Severity.BLOCK for f in tr2)


def test_tr2_flags_tbd_envelope_cell(tmp_path: Path) -> None:
    _write(
        _registry_path(tmp_path),
        """
        # Registry

        | Tool | Auto-mode envelope | Bypass envelope | Notes |
        |---|---|---|---|
        | `Read` | TBD | direct | placeholder auto |
        """,
    )
    _write_settings(tmp_path, [])
    findings = arl.check_tool_risk([], repo_root=tmp_path)
    tr2 = [f for f in findings if f.rule_id == "TR2"]
    assert tr2


@pytest.mark.parametrize("bad_class", ["allowed", "blocked", "review", "maybe"])
def test_tr2_flags_non_taxonomy_class(tmp_path: Path, bad_class: str) -> None:
    _write(
        _registry_path(tmp_path),
        f"""
        # Registry

        | Tool | Auto-mode envelope | Bypass envelope | Notes |
        |---|---|---|---|
        | `Read` | {bad_class} | direct | non-taxonomy word |
        """,
    )
    _write_settings(tmp_path, [])
    findings = arl.check_tool_risk([], repo_root=tmp_path)
    tr2 = [f for f in findings if f.rule_id == "TR2"]
    assert tr2
    assert any(bad_class in f.message for f in tr2)


def test_tr2_accepts_class_with_parenthetical(tmp_path: Path) -> None:
    _write(
        _registry_path(tmp_path),
        """
        # Registry

        | Tool | Auto-mode envelope | Bypass envelope | Notes |
        |---|---|---|---|
        | `Bash(git push --force)` | approve (requires User Intent) | reject | destructive |
        """,
    )
    _write_settings(tmp_path, [])
    findings = arl.check_tool_risk([], repo_root=tmp_path)
    assert not any(f.rule_id == "TR2" for f in findings)


# ---------------------------------------------------------------------------
# TR3 — reject-under-bypass with no Notes
# ---------------------------------------------------------------------------


def test_tr3_warns_on_reject_bypass_without_notes(tmp_path: Path) -> None:
    _write(
        _registry_path(tmp_path),
        """
        # Registry

        | Tool | Auto-mode envelope | Bypass envelope | Notes |
        |---|---|---|---|
        | `Bash(rm -rf *)` | approve | reject |  |
        """,
    )
    _write_settings(tmp_path, [])
    findings = arl.check_tool_risk([], repo_root=tmp_path)
    tr3 = [f for f in findings if f.rule_id == "TR3"]
    assert len(tr3) == 1
    assert tr3[0].severity == arl.Severity.WARN


def test_tr3_silent_when_notes_present(tmp_path: Path) -> None:
    _write(
        _registry_path(tmp_path),
        """
        # Registry

        | Tool | Auto-mode envelope | Bypass envelope | Notes |
        |---|---|---|---|
        | `Bash(rm -rf *)` | approve | reject | Destructive — data loss |
        """,
    )
    _write_settings(tmp_path, [])
    findings = arl.check_tool_risk([], repo_root=tmp_path)
    assert not any(f.rule_id == "TR3" for f in findings)


# ---------------------------------------------------------------------------
# TR4 — permissions.allow coverage
# ---------------------------------------------------------------------------


def test_tr4_flags_uncovered_allow_entry(tmp_path: Path) -> None:
    _write_valid_registry(tmp_path)
    # `Bash(ls *)` is not in the registry.
    _write_settings(tmp_path, ["Bash(git *)", "Bash(ls *)"])
    findings = arl.check_tool_risk([], repo_root=tmp_path)
    tr4 = [f for f in findings if f.rule_id == "TR4"]
    assert len(tr4) == 1
    assert "Bash(ls *)" in tr4[0].message
    assert tr4[0].severity == arl.Severity.BLOCK


def test_tr4_silent_when_every_entry_covered(tmp_path: Path) -> None:
    # Add a row for ls so the allow-list is fully covered.
    _write_valid_registry(
        tmp_path, extra_rows="| `Bash(ls *)` | direct | direct | Read-only |"
    )
    _write_settings(tmp_path, ["Bash(git *)", "Bash(ls *)"])
    findings = arl.check_tool_risk([], repo_root=tmp_path)
    assert not any(f.rule_id == "TR4" for f in findings)


def test_tr4_lenient_substring_match(tmp_path: Path) -> None:
    # A single row can cover both Edit(X) and Write(X) by listing both.
    _write_valid_registry(
        tmp_path,
        extra_rows=(
            "| `Edit(src/**)` `Write(src/**)` | direct | direct | Project source |"
        ),
    )
    _write_settings(tmp_path, ["Edit(src/**)", "Write(src/**)"])
    findings = arl.check_tool_risk([], repo_root=tmp_path)
    assert not any(f.rule_id == "TR4" for f in findings)


# ---------------------------------------------------------------------------
# _load_permissions_allow helper
# ---------------------------------------------------------------------------


def test_load_permissions_allow_extracts_entries(tmp_path: Path) -> None:
    entries = ["Bash(git *)", "Edit(src/**)", "Write(tests/**)"]
    _write_settings(tmp_path, entries)
    loaded = arl._load_permissions_allow(_settings_path(tmp_path))
    assert loaded == entries


def test_load_permissions_allow_missing_file_returns_empty(tmp_path: Path) -> None:
    loaded = arl._load_permissions_allow(tmp_path / "nope.json")
    assert loaded == []


def test_load_permissions_allow_no_allow_block_returns_empty(tmp_path: Path) -> None:
    _write(
        _settings_path(tmp_path),
        """
        {
          "hooks": []
        }
        """,
    )
    loaded = arl._load_permissions_allow(_settings_path(tmp_path))
    assert loaded == []


# ---------------------------------------------------------------------------
# _approval_class_first_token helper
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cell,expected",
    [
        ("direct", "direct"),
        ("approve (classifier gates)", "approve"),
        ("reject", "reject"),
        ("Approve", "approve"),
        ("  direct  ", "direct"),
        ("edit (reviewer required)", "edit"),
        ("", ""),
        ("42 invalid", ""),
    ],
)
def test_approval_class_first_token(cell: str, expected: str) -> None:
    assert arl._approval_class_first_token(cell) == expected


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def test_cli_tool_risk_clean_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_valid_registry(tmp_path)
    _write_settings(tmp_path, ["Bash(git *)"])
    rc = arl.main(["--repo-root", str(tmp_path), "check", "tool-risk"])
    assert rc == 0
    assert "0 findings" in capsys.readouterr().out


def test_cli_tool_risk_block_exits_two(tmp_path: Path) -> None:
    # Missing registry → TR0 BLOCK → exit 2.
    rc = arl.main(["--repo-root", str(tmp_path), "check", "tool-risk"])
    assert rc == 2


# ---------------------------------------------------------------------------
# Self-run: the live registry is clean + covers every allow entry.
# ---------------------------------------------------------------------------


def test_live_tool_risk_registry_is_clean() -> None:
    """Regression guard: B.6 lint exits clean against the live registry.

    If this fails after editing ``.claude/settings.json`` or the
    registry, add a registry row for the new allow entry (do not relax
    the lint).
    """
    repo_root = Path(__file__).resolve().parents[2]
    target = repo_root / ".claude" / "rules" / "tool_risk_registry.md"
    if not target.exists():
        pytest.skip(f"tool_risk_registry.md not found at {target}")
    findings = arl.check_tool_risk([], repo_root=repo_root)
    blocks = [f for f in findings if f.severity == arl.Severity.BLOCK]
    assert not blocks, "BLOCK findings:\n" + "\n".join(f.format_line() for f in blocks)
