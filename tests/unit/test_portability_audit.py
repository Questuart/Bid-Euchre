"""Regression tests for ops package portability coupling.

Ensures coupling counts do not regress above the documented thresholds.
Run: ``uv run python -m pytest tests/unit/test_portability_audit.py -v``
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Locate ops package — works from repo root or any worktree
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_OPS_DIR = _REPO_ROOT / "src" / "bid_euchre" / "ops"


def _skip_if_no_ops() -> None:
    if not _OPS_DIR.is_dir():
        pytest.skip(f"ops directory not found: {_OPS_DIR}")


# ---------------------------------------------------------------------------
# Import the audit module
# ---------------------------------------------------------------------------


# Use importlib to import from scripts/internal without adding it to sys.path
# permanently.  This avoids polluting the test namespace.
def _load_audit_module():
    """Import audit_portability from scripts/internal/."""
    import importlib.util
    import sys as _sys

    module_name = "audit_portability"
    # Return cached module if already loaded
    if module_name in _sys.modules:
        return _sys.modules[module_name]

    script_path = _REPO_ROOT / "scripts" / "internal" / "audit_portability.py"
    if not script_path.exists():
        pytest.skip(f"audit script not found: {script_path}")

    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Register in sys.modules before exec (required by Python 3.14 dataclasses)
    _sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

# These thresholds are the documented baseline from PORTABILITY_MANIFEST.md.
# They should only decrease as decoupling work proceeds.  If a PR increases
# coupling, either fix the regression or update the threshold with justification.

NON_COSMETIC_THRESHOLD = 259  # hard-block + soft-coupling
# Baseline was 253; main drifted to 257 before Slice D landed (pre-existing,
# unrelated to token-economy work). Slice D adds 2 more hits because the
# `lane-name-in-code` regex matches the string literals `"ops"` and `"review"`
# in LANE_DEFAULT_POLICY — those are task_type taxonomy keys (#2169 Slice D),
# not lane identifiers, so this is a known audit false positive. Downstream
# portability cleanup will narrow the regex or formalize task_type as an Enum.
HARD_BLOCK_THRESHOLD = 130  # hard-block only (pinned to baseline)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPortabilityAudit:
    """Verify the audit script runs and coupling stays within bounds."""

    @pytest.fixture(autouse=True)
    def _ensure_ops(self) -> None:
        _skip_if_no_ops()

    @pytest.fixture()
    def audit(self):
        mod = _load_audit_module()
        return mod.run_audit(_OPS_DIR)

    def test_audit_runs_without_error(self, audit) -> None:
        """Smoke test: the audit completes and finds files."""
        assert audit.files_scanned > 0
        assert audit.lines_scanned > 0

    def test_non_cosmetic_coupling_below_threshold(self, audit) -> None:
        """Non-cosmetic coupling must not regress above the threshold.

        If this test fails, a PR has introduced new project-specific coupling
        in the ops package.  Options:
        1. Move the coupling to the adapter layer (preferred)
        2. Update the threshold with justification in the commit message
        """
        sev = audit.by_severity()
        non_cosmetic = sev.get("hard-block", 0) + sev.get("soft-coupling", 0)
        assert non_cosmetic <= NON_COSMETIC_THRESHOLD, (
            f"Non-cosmetic coupling ({non_cosmetic}) exceeds threshold "
            f"({NON_COSMETIC_THRESHOLD}).  Run "
            f"'uv run python scripts/internal/audit_portability.py' for details."
        )

    def test_hard_block_coupling_below_threshold(self, audit) -> None:
        """Hard-block coupling must not regress above the threshold.

        Hard-block items are string literals that make the ops package
        impossible to reuse without source edits.
        """
        sev = audit.by_severity()
        hard_block = sev.get("hard-block", 0)
        assert hard_block <= HARD_BLOCK_THRESHOLD, (
            f"Hard-block coupling ({hard_block}) exceeds threshold "
            f"({HARD_BLOCK_THRESHOLD}).  Run "
            f"'uv run python scripts/internal/audit_portability.py' for details."
        )

    def test_all_severity_levels_present(self, audit) -> None:
        """Verify the audit detects all three severity levels.

        If a severity level disappears entirely, the pattern definitions
        may have broken.
        """
        sev = audit.by_severity()
        assert (
            sev.get("hard-block", 0) > 0
        ), "Expected hard-block coupling to be detected"
        assert sev.get("soft-coupling", 0) > 0, "Expected soft-coupling to be detected"
        assert sev.get("cosmetic", 0) > 0, "Expected cosmetic coupling to be detected"

    def test_adapter_files_excluded_from_lane_names(self, audit) -> None:
        """Lane name hits should not appear in adapter files.

        The adapter module is the designated home for lane identifiers.
        The audit script should exclude it from the lane-name-in-code check.
        """
        adapter_lane_hits = [
            h
            for h in audit.hits
            if h.pattern_name == "lane-name-in-code" and "adapters/" in h.file
        ]
        assert len(adapter_lane_hits) == 0, (
            f"Found {len(adapter_lane_hits)} lane-name-in-code hits in adapter files — "
            f"these should be excluded"
        )

    def test_patterns_cover_known_coupling(self, audit) -> None:
        """Verify patterns detect the known major coupling sources.

        If any of these patterns reports 0 hits, the regex may be broken.
        """
        by_pattern = audit.by_pattern()
        expected_patterns = {
            "worktree-name-literal",
            "steward-prefix-regex",
            "tmux-session-default",
            "docstring-bid-euchre",
        }
        for p in expected_patterns:
            assert (
                by_pattern.get(p, 0) > 0
            ), f"Pattern '{p}' found 0 hits — regex may be broken"
