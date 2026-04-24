"""Unit tests for ``scripts/internal/audit_event_emission.py``.

Covers Primitive A §8.2 step 8 acceptance: the audit walks scanned roots
+ native hook registry, classifies coverage into green/yellow/red, and
prints/exits accordingly.

Fixtures are seeded (in-memory JSON + tmp_path Python files); no
dependency on the live repo tree so the tests remain deterministic.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Make the script importable as a module so internal helpers can be
# exercised without re-invoking ``python`` for every test.
SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "internal"
    / "audit_event_emission.py"
)
sys.path.insert(0, str(SCRIPT_PATH.parent))

import audit_event_emission as audit  # noqa: E402

# ---------------------------------------------------------------------------
# scan_emit_call_sites
# ---------------------------------------------------------------------------


class TestScanEmitCallSites:
    def test_finds_events_emit_call(self, tmp_path: Path) -> None:
        """``events.emit("<type>", ...)`` is picked up as a call-site."""
        src = tmp_path / "example.py"
        src.write_text('from foo import events\nevents.emit("task_started", x=1)\n')
        found = audit.scan_emit_call_sites((tmp_path,))
        assert "task_started" in found
        assert src in found["task_started"]

    def test_finds_bare_emit_alias(self, tmp_path: Path) -> None:
        """``emit("<type>", ...)`` (bare name) is also picked up."""
        src = tmp_path / "bare.py"
        src.write_text('emit("task_completed", outcome="merged")\n')
        found = audit.scan_emit_call_sites((tmp_path,))
        assert "task_completed" in found

    def test_finds_v1_emit_alias(self, tmp_path: Path) -> None:
        """The ``v1_emit`` alias used in ops.py is also recognised."""
        src = tmp_path / "ops_alias.py"
        src.write_text('v1_emit("task_started", packet_id="x")\n')
        found = audit.scan_emit_call_sites((tmp_path,))
        assert "task_started" in found

    def test_ignores_non_emit_lines(self, tmp_path: Path) -> None:
        """Unrelated lines do not produce spurious matches."""
        src = tmp_path / "quiet.py"
        src.write_text(
            "# events.emit is mentioned in a comment but has no parens\n"
            'print("task_started")\n'
        )
        found = audit.scan_emit_call_sites((tmp_path,))
        assert found == {}

    def test_dedupes_same_file(self, tmp_path: Path) -> None:
        """Multiple emit calls in one file → one path entry per type."""
        src = tmp_path / "many.py"
        src.write_text(
            'events.emit("task_started", x=1)\n'
            'events.emit("task_started", x=2)\n'
            'events.emit("task_completed", outcome="x")\n'
        )
        found = audit.scan_emit_call_sites((tmp_path,))
        assert found["task_started"] == [src]
        assert found["task_completed"] == [src]

    def test_excludes_audit_script_itself(self) -> None:
        """Self-matches from the audit script are filtered (regex prevents
        feedback-loop counting)."""
        # By default the scanner excludes the audit module (it imports
        # constants referencing event names). Using the real repo roots
        # for this tests the live repo's audit.py exclusion.
        repo_root = Path(__file__).resolve().parents[2]
        found = audit.scan_emit_call_sites((repo_root / "scripts" / "internal",))
        for paths in found.values():
            assert audit.__file__ not in {
                str(p.resolve()) for p in paths
            }, "audit_event_emission.py should not appear as an emitter"


# ---------------------------------------------------------------------------
# scan_native_hook_registrations
# ---------------------------------------------------------------------------


class TestScanNativeHookRegistrations:
    def test_detects_registered_hook(self, tmp_path: Path) -> None:
        cfg = {
            "hooks": {
                "PreToolUse": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/event_emit.sh pre_tool_use",
                            }
                        ]
                    }
                ]
            }
        }
        settings = tmp_path / "settings.json"
        settings.write_text(json.dumps(cfg))
        result = audit.scan_native_hook_registrations(settings)
        assert result["pre_tool_use"] is True
        # Unregistered types flagged False.
        assert result["post_tool_use"] is False

    def test_missing_settings_returns_all_false(self, tmp_path: Path) -> None:
        """A nonexistent settings.json yields all-False (no crash)."""
        result = audit.scan_native_hook_registrations(tmp_path / "missing.json")
        assert all(v is False for v in result.values())

    def test_malformed_settings_returns_all_false(self, tmp_path: Path) -> None:
        """Malformed JSON does not crash the audit."""
        bad = tmp_path / "settings.json"
        bad.write_text("not-json {{{{")
        result = audit.scan_native_hook_registrations(bad)
        assert all(v is False for v in result.values())

    def test_detects_all_15_native_hooks_in_live_settings(self) -> None:
        """The live .claude/settings.json registers all 15 native hook types."""
        repo_root = Path(__file__).resolve().parents[2]
        settings = repo_root / ".claude" / "settings.json"
        result = audit.scan_native_hook_registrations(settings)
        # All 15 native types should now be registered (Step 6 completed).
        missing = [t for t, ok in result.items() if not ok]
        assert not missing, f"Missing native hook registrations: {missing}"


# ---------------------------------------------------------------------------
# build_audit_report
# ---------------------------------------------------------------------------


class TestBuildAuditReport:
    def test_green_when_all_classes_have_emitter(self) -> None:
        """All classes covered → overall green."""
        # Build a fake emit_sites dict that covers every class member.
        emit_sites = {
            t: [Path("fake/fake.py")]
            for members in audit.STEWARD_OPERATIONAL_CLASSES.values()
            for t in members
        }
        native_status = dict.fromkeys(audit.NATIVE_LIFECYCLE_EVENT_TYPES, True)
        report = audit.build_audit_report(emit_sites, native_status)
        assert report.overall == "green"
        assert all(c.status == "green" for c in report.classes)
        assert report.native_hooks_missing == []

    def test_yellow_for_deferred_class(self) -> None:
        """Class with no coverage but in DEFERRED_CLASSES → yellow."""
        emit_sites = {
            # Only task_lifecycle covered; others bare.
            "task_started": [Path("fake.py")],
            "task_completed": [Path("fake.py")],
        }
        native_status = dict.fromkeys(audit.NATIVE_LIFECYCLE_EVENT_TYPES, True)
        report = audit.build_audit_report(emit_sites, native_status)
        # task_lifecycle green, deferred classes yellow.
        by_name = {c.class_name: c for c in report.classes}
        assert by_name["task_lifecycle"].status == "green"
        for deferred_class in audit.DEFERRED_CLASSES:
            assert by_name[deferred_class].status == "yellow"
            assert (
                by_name[deferred_class].deferred_to
                == (audit.DEFERRED_CLASSES[deferred_class])
            )
        # Overall yellow because deferred classes lack emitters (yet).
        assert report.overall == "yellow"

    def test_red_when_non_deferred_class_has_zero_coverage(self) -> None:
        """If a class is missing coverage and NOT in DEFERRED_CLASSES, red."""
        emit_sites: dict[str, list[Path]] = {}
        native_status = dict.fromkeys(audit.NATIVE_LIFECYCLE_EVENT_TYPES, True)
        # Stub DEFERRED_CLASSES to empty so task_lifecycle is not deferred.
        import copy

        original_deferred = copy.copy(audit.DEFERRED_CLASSES)
        try:
            audit.DEFERRED_CLASSES.clear()
            report = audit.build_audit_report(emit_sites, native_status)
            by_name = {c.class_name: c for c in report.classes}
            assert by_name["task_lifecycle"].status == "red"
            assert report.overall == "red"
        finally:
            audit.DEFERRED_CLASSES.update(original_deferred)

    def test_native_hook_missing_promotes_green_to_yellow(self) -> None:
        """Full class coverage but missing native hook → overall yellow."""
        emit_sites = {
            t: [Path("x.py")]
            for members in audit.STEWARD_OPERATIONAL_CLASSES.values()
            for t in members
        }
        native_status = dict.fromkeys(audit.NATIVE_LIFECYCLE_EVENT_TYPES, True)
        native_status["pre_tool_use"] = False  # One missing.
        report = audit.build_audit_report(emit_sites, native_status)
        assert "pre_tool_use" in report.native_hooks_missing
        assert report.overall == "yellow"

    def test_registered_types_count_reflects_schema(self) -> None:
        """registered_event_types matches EVENT_FIELD_REGISTRY."""
        emit_sites: dict[str, list[Path]] = {}
        native_status = dict.fromkeys(audit.NATIVE_LIFECYCLE_EVENT_TYPES, True)
        report = audit.build_audit_report(emit_sites, native_status)
        assert report.registered_event_types == len(audit.EVENT_FIELD_REGISTRY)


# ---------------------------------------------------------------------------
# format_report
# ---------------------------------------------------------------------------


class TestFormatReport:
    def test_renders_green_banner(self) -> None:
        emit_sites = {
            t: [Path("f.py")]
            for members in audit.STEWARD_OPERATIONAL_CLASSES.values()
            for t in members
        }
        native_status = dict.fromkeys(audit.NATIVE_LIFECYCLE_EVENT_TYPES, True)
        report = audit.build_audit_report(emit_sites, native_status)
        out = audit.format_report(report)
        assert "GREEN" in out
        assert "all 15 native lifecycle hooks subscribed" in out
        assert "all 7 steward operational classes" in out

    def test_renders_yellow_summary_for_deferred(self) -> None:
        emit_sites = {
            "task_started": [Path("f.py")],
            "task_completed": [Path("f.py")],
        }
        native_status = dict.fromkeys(audit.NATIVE_LIFECYCLE_EVENT_TYPES, True)
        report = audit.build_audit_report(emit_sites, native_status)
        out = audit.format_report(report)
        assert "YELLOW" in out
        assert "deferred → Primitive" in out


# ---------------------------------------------------------------------------
# CLI integration (subprocess) — verifies exit codes + arg parsing
# ---------------------------------------------------------------------------


class TestCliIntegration:
    def _run(self, *extra: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        cmd = [sys.executable, str(SCRIPT_PATH), *extra]
        return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, check=False)

    def test_json_mode_parses(self) -> None:
        """--json prints a parseable payload with required top-level keys."""
        result = self._run("--json")
        assert result.returncode in (0, 1)
        payload = json.loads(result.stdout)
        for key in (
            "overall",
            "native_hook_coverage_pct",
            "native_hooks_missing",
            "classes",
            "emit_call_site_count",
            "registered_event_types",
            "covered_event_types",
        ):
            assert key in payload

    def test_exit_zero_on_live_repo_green_or_yellow(self) -> None:
        """Run against the actual repo — Phase 0 expects green or yellow."""
        result = self._run()
        # Exit 0 for green/yellow; exit 1 if any class is red.
        assert result.returncode == 0, (
            f"Audit failed on live repo (stdout below):\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    def test_strict_mode_tightens_exit_code(self) -> None:
        """--strict exits non-zero on yellow too."""
        result = self._run("--strict", "--json")
        # Current Phase 0 expected state is yellow (deferred classes);
        # --strict should be non-zero.  If repo progresses to green, this
        # becomes 0, which is also acceptable.
        payload = json.loads(result.stdout)
        if payload["overall"] == "yellow":
            assert result.returncode == 1
        elif payload["overall"] == "green":
            assert result.returncode == 0
        else:
            assert result.returncode == 1


# ---------------------------------------------------------------------------
# Coverage invariants (regression guards)
# ---------------------------------------------------------------------------


class TestCoverageInvariants:
    def test_native_event_mapping_covers_all_15_types(self) -> None:
        """NATIVE_EVENT_TO_HOOK_SECTION is exhaustive over native types."""
        for t in audit.NATIVE_LIFECYCLE_EVENT_TYPES:
            assert (
                t in audit.NATIVE_EVENT_TO_HOOK_SECTION
            ), f"Missing hook-section mapping for {t!r}"

    def test_deferred_classes_are_real_classes(self) -> None:
        """Every deferred class is a member of STEWARD_OPERATIONAL_CLASSES."""
        for class_name in audit.DEFERRED_CLASSES:
            assert class_name in audit.STEWARD_OPERATIONAL_CLASSES

    def test_primitive_a_completion_deferral_labeled(self) -> None:
        """latency_measurements is deferred to Primitive A completion.

        This is the only within-Primitive-A deferral — audit yellow is
        expected until the dashboard panel ships.
        """
        assert audit.DEFERRED_CLASSES.get("latency_measurements") == "A"


def test_task_lifecycle_class_is_live_covered() -> None:
    """Integration guard: task_lifecycle should be green after Step 7.

    ops.py (step 7 dual-write) installs the emit call-sites; confirming
    this test passes is a regression guard against future accidental
    removal of the emitters.
    """
    repo_root = Path(__file__).resolve().parents[2]
    roots = (
        repo_root / "src" / "bid_euchre",
        repo_root / "scripts",
        repo_root / "tests",
    )
    sites = audit.scan_emit_call_sites(roots)
    assert "task_started" in sites, "task_started emitter missing"
    assert "task_completed" in sites, "task_completed emitter missing"


@pytest.mark.parametrize("class_name", list(audit.STEWARD_OPERATIONAL_CLASSES.keys()))
def test_each_class_appears_in_live_report(class_name: str) -> None:
    """Every class shows up in the report, regardless of green/yellow/red."""
    repo_root = Path(__file__).resolve().parents[2]
    emit_sites = audit.scan_emit_call_sites(
        (repo_root / "src" / "bid_euchre", repo_root / "scripts", repo_root / "tests")
    )
    native_status = audit.scan_native_hook_registrations(
        repo_root / ".claude" / "settings.json"
    )
    report = audit.build_audit_report(emit_sites, native_status)
    names = [c.class_name for c in report.classes]
    assert class_name in names
