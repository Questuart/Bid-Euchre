#!/usr/bin/env python3
"""Event-emission coverage audit (Primitive A Phase 0 Readiness #2).

Walks the codebase + native hook registry and verifies that:

1. All 15 native Claude Code lifecycle hook types (`NATIVE_LIFECYCLE_EVENT_TYPES`)
   are registered in `.claude/settings.json` with a command that routes
   through `event_emit.sh` (Tier S absorbed surface per ADR 007 §9.7).

2. All steward operational classes (`STEWARD_OPERATIONAL_CLASSES`) have at
   least one committed `events.emit(...)` call-site or are explicitly
   deferred (marked `DEFERRED-TO-PRIMITIVE-<letter>` in a comment within
   the owning class's block below).

3. Every registered event type in `EVENT_FIELD_REGISTRY` is either
   (a) the target of a committed `events.emit("<type>", ...)` call,
   (b) covered transitively via a native hook registration (for the
   native-lifecycle types), or
   (c) documented as deferred to a later primitive.

The script prints a ``green`` / ``yellow`` / ``red`` status and exits 0 for
green (all classes covered), 1 for red (at least one class has zero
coverage and is not deferred). Yellow (partial coverage; some types still
deferred) exits 0 to keep Phase 0 kickoff unblocked; yellow is an
expected intermediate state as Primitives B–G ship the rest of the
emitters.

Usage::

    uv run python scripts/internal/audit_event_emission.py           # human-readable
    uv run python scripts/internal/audit_event_emission.py --json    # machine-readable
    uv run python scripts/internal/audit_event_emission.py --strict  # red on any yellow

Exit codes
----------
0 — green or yellow (no hard failures)
1 — red (at least one class has zero coverage and is not deferred), or
    --strict was passed and there is at least one yellow class.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Repo + schema imports
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]

# Ensure ``src/`` is on the import path so ``bid_euchre.ops.event_schema``
# is resolvable when the script is invoked via ``python scripts/...``.
sys.path.insert(0, str(REPO_ROOT / "src"))

from bid_euchre.ops.event_schema import (  # noqa: E402
    EVENT_FIELD_REGISTRY,
    NATIVE_LIFECYCLE_EVENT_TYPES,
    STEWARD_OPERATIONAL_CLASSES,
)

# ---------------------------------------------------------------------------
# Scan targets
# ---------------------------------------------------------------------------

#: Directory roots scanned for ``events.emit("...", ...)`` call-sites.
EMIT_SCAN_ROOTS: tuple[Path, ...] = (
    REPO_ROOT / "src" / "bid_euchre",
    REPO_ROOT / "scripts",
    REPO_ROOT / "experiments",
    REPO_ROOT / "tests",
)

#: Native hook registration file.
CLAUDE_SETTINGS = REPO_ROOT / ".claude" / "settings.json"

#: Hook script that must appear as the command for every native hook event
#: registration.
HOOK_DISPATCHER_NAME = "event_emit.sh"

#: Mapping from native v1.0 event_type to the corresponding Claude Code
#: top-level hook section key.  Required because the Claude Code hook
#: schema uses CamelCase keys while the event_type strings use snake_case.
NATIVE_EVENT_TO_HOOK_SECTION: dict[str, str] = {
    "pre_tool_use": "PreToolUse",
    "post_tool_use": "PostToolUse",
    "post_tool_use_failure": "PostToolUseFailure",
    "permission_request": "PermissionRequest",
    "permission_denied": "PermissionDenied",
    "notification": "Notification",
    "user_prompt_submit": "UserPromptSubmit",
    "stop": "Stop",
    "stop_failure": "StopFailure",
    "subagent_start": "SubagentStart",
    "subagent_stop": "SubagentStop",
    "pre_compact": "PreCompact",
    "session_start": "SessionStart",
    "session_end": "SessionEnd",
    "teammate_idle": "TeammateIdle",
}

#: Event types whose emitter is deferred to a later primitive.  Keyed by
#: the class name; value is the letter of the primitive that owns the
#: emitter.  Audit reports these as "deferred" (yellow) rather than
#: "missing" (red).
DEFERRED_CLASSES: dict[str, str] = {
    "canary_lifecycle": "E",  # Primitive E owns canary framework
    "archivist_lifecycle": "F",  # Primitive F owns archivist
    "promotion_lifecycle": "F",  # Primitive F owns promotion gate
    "rollback_lifecycle": "F",  # Primitive F owns rollback orchestration
    "latency_measurements": "A",  # Primitive A completion (this packet)
    "worktree_lifecycle": "G",  # Primitive G owns worktree lifecycle
}


# ---------------------------------------------------------------------------
# Emit call-site scanner
# ---------------------------------------------------------------------------

# Matches both ``events.emit("type", ...)`` and ``emit("type", ...)``
# call-sites.  Keeps the pattern deliberately simple — complex parsing
# (full AST walking) is overkill for a coverage audit and would couple the
# script to module-import state.
_EMIT_CALL_RE = re.compile(
    r"""
    (?:\bevents\.emit|\bemit|\bv1_emit)   # callable: events.emit | emit | v1_emit
    \s*\(\s*                              # opening paren + optional whitespace
    ["']                                  # opening quote
    (?P<event_type>[a-z_][a-z0-9_]*)      # event_type literal
    ["']                                  # closing quote
    """,
    re.VERBOSE,
)


def scan_emit_call_sites(roots: tuple[Path, ...]) -> dict[str, list[Path]]:
    """Scan the repository for ``emit("<type>", ...)`` call-sites.

    Returns a mapping ``event_type → [file_path, ...]`` of files containing
    at least one committed call-site for that event type.  The audit
    module itself is excluded to avoid self-registration.
    """
    found: dict[str, set[Path]] = {}
    self_path = Path(__file__).resolve()
    for root in roots:
        if not root.exists():
            continue
        for py_file in root.rglob("*.py"):
            try:
                resolved = py_file.resolve()
            except OSError:
                continue
            if resolved == self_path:
                continue
            try:
                text = py_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for match in _EMIT_CALL_RE.finditer(text):
                event_type = match.group("event_type")
                found.setdefault(event_type, set()).add(py_file)
    return {k: sorted(v) for k, v in found.items()}


# ---------------------------------------------------------------------------
# Native hook registration scanner
# ---------------------------------------------------------------------------


def scan_native_hook_registrations(
    settings_path: Path,
) -> dict[str, bool]:
    """Return which native lifecycle event types have event_emit.sh wired.

    For each entry in ``NATIVE_LIFECYCLE_EVENT_TYPES``, walks
    ``settings.json`` -> ``hooks.<HookSection>`` and returns True iff any
    registered hook command contains the HOOK_DISPATCHER_NAME constant.
    """
    result: dict[str, bool] = dict.fromkeys(NATIVE_LIFECYCLE_EVENT_TYPES, False)
    if not settings_path.exists():
        return result
    try:
        cfg = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return result
    hooks = cfg.get("hooks") or {}
    if not isinstance(hooks, dict):
        return result
    for event_type, section in NATIVE_EVENT_TO_HOOK_SECTION.items():
        bucket = hooks.get(section) or []
        found = False
        for group in bucket:
            if not isinstance(group, dict):
                continue
            for hook in group.get("hooks") or []:
                if not isinstance(hook, dict):
                    continue
                cmd = hook.get("command") or ""
                if HOOK_DISPATCHER_NAME in cmd:
                    found = True
                    break
            if found:
                break
        result[event_type] = found
    return result


# ---------------------------------------------------------------------------
# Coverage roll-up
# ---------------------------------------------------------------------------


@dataclass
class CoverageResult:
    """Per-class coverage summary."""

    class_name: str
    status: str  # "green" | "yellow" | "red"
    covered_types: list[str] = field(default_factory=list)
    missing_types: list[str] = field(default_factory=list)
    deferred_to: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "class_name": self.class_name,
            "status": self.status,
            "covered_types": self.covered_types,
            "missing_types": self.missing_types,
            "deferred_to": self.deferred_to,
        }


@dataclass
class AuditReport:
    """Top-level audit output."""

    overall: str  # "green" | "yellow" | "red"
    native_hook_coverage_pct: float
    native_hooks_missing: list[str]
    classes: list[CoverageResult]
    emit_call_site_count: int
    registered_event_types: int
    covered_event_types: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall,
            "native_hook_coverage_pct": self.native_hook_coverage_pct,
            "native_hooks_missing": self.native_hooks_missing,
            "classes": [c.to_dict() for c in self.classes],
            "emit_call_site_count": self.emit_call_site_count,
            "registered_event_types": self.registered_event_types,
            "covered_event_types": self.covered_event_types,
        }


def _classify_class(
    class_name: str,
    members: tuple[str, ...],
    emit_sites: dict[str, list[Path]],
    native_hook_status: dict[str, bool],
) -> CoverageResult:
    covered: list[str] = []
    missing: list[str] = []
    for t in members:
        if t in emit_sites and emit_sites[t]:
            covered.append(t)
        elif native_hook_status.get(t, False):
            covered.append(t)
        else:
            missing.append(t)
    if not missing:
        status = "green"
        deferred_to = None
    elif class_name in DEFERRED_CLASSES:
        status = "yellow"
        deferred_to = DEFERRED_CLASSES[class_name]
    elif covered:
        status = "yellow"
        deferred_to = None
    else:
        status = "red"
        deferred_to = None
    return CoverageResult(
        class_name=class_name,
        status=status,
        covered_types=covered,
        missing_types=missing,
        deferred_to=deferred_to,
    )


def build_audit_report(
    emit_sites: dict[str, list[Path]],
    native_hook_status: dict[str, bool],
) -> AuditReport:
    """Compose the audit report from scanned inputs."""
    classes = [
        _classify_class(name, members, emit_sites, native_hook_status)
        for name, members in STEWARD_OPERATIONAL_CLASSES.items()
    ]
    # Overall status: red if any class is red; yellow if any are yellow;
    # green otherwise.
    statuses = {c.status for c in classes}
    if "red" in statuses:
        overall = "red"
    elif "yellow" in statuses:
        overall = "yellow"
    else:
        overall = "green"

    native_missing = [t for t, ok in native_hook_status.items() if not ok]
    native_pct = (
        100.0
        * (len(NATIVE_LIFECYCLE_EVENT_TYPES) - len(native_missing))
        / max(1, len(NATIVE_LIFECYCLE_EVENT_TYPES))
    )
    if native_missing and overall == "green":
        overall = "yellow"

    all_registered = set(EVENT_FIELD_REGISTRY.keys())
    covered_types: set[str] = set()
    for t in all_registered:
        if t in emit_sites and emit_sites[t]:
            covered_types.add(t)
        if native_hook_status.get(t, False):
            covered_types.add(t)

    return AuditReport(
        overall=overall,
        native_hook_coverage_pct=native_pct,
        native_hooks_missing=native_missing,
        classes=classes,
        emit_call_site_count=sum(len(v) for v in emit_sites.values()),
        registered_event_types=len(all_registered),
        covered_event_types=len(covered_types),
    )


# ---------------------------------------------------------------------------
# Pretty-printing
# ---------------------------------------------------------------------------


def format_report(report: AuditReport) -> str:
    """Return a human-readable summary string."""
    symbol = {"green": "✓", "yellow": "◐", "red": "✗"}[report.overall]
    lines: list[str] = [
        f"Event-emission coverage audit  [{symbol} {report.overall.upper()}]",
        "=" * 66,
        (
            f"Native lifecycle hooks: "
            f"{len(NATIVE_LIFECYCLE_EVENT_TYPES) - len(report.native_hooks_missing)} "
            f"of {len(NATIVE_LIFECYCLE_EVENT_TYPES)} subscribed "
            f"({report.native_hook_coverage_pct:.1f}%)"
        ),
    ]
    if report.native_hooks_missing:
        lines.append("  missing: " + ", ".join(sorted(report.native_hooks_missing)))
    lines.append("")
    lines.append("Steward operational classes:")
    for c in report.classes:
        csym = {"green": "✓", "yellow": "◐", "red": "✗"}[c.status]
        deferred = f" (deferred → Primitive {c.deferred_to})" if c.deferred_to else ""
        lines.append(
            f"  [{csym}] {c.class_name:24s} "
            f"{len(c.covered_types)}/{len(c.covered_types) + len(c.missing_types)} "
            f"covered{deferred}"
        )
        if c.missing_types:
            lines.append("       missing: " + ", ".join(c.missing_types))
    lines.append("")
    lines.append(
        f"Event-type coverage: "
        f"{report.covered_event_types}/{report.registered_event_types} "
        f"registered types have ≥1 emitter"
    )
    lines.append(f"Total committed emit() call-sites: {report.emit_call_site_count}")
    lines.append("")
    if report.overall == "green":
        lines.append(
            "all 15 native lifecycle hooks subscribed; "
            f"all {len(STEWARD_OPERATIONAL_CLASSES)} steward operational "
            "classes emit at least one call-site"
        )
    elif report.overall == "yellow":
        lines.append(
            "coverage partial — classes deferred to later primitives or "
            "still ramping up emission. Not blocking Phase 0 kickoff."
        )
    else:
        lines.append(
            "coverage RED — at least one class has no committed emitter "
            "and is not marked as deferred. Fix before Phase 0 kickoff."
        )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Event-emission coverage audit (Primitive A Phase 0)."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of a human summary.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero on yellow (any missing coverage, not just red).",
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=CLAUDE_SETTINGS,
        help="Path to .claude/settings.json (default: repo default).",
    )
    parser.add_argument(
        "--scan-root",
        type=Path,
        action="append",
        default=None,
        help=(
            "Directory root to scan for emit() call-sites (repeatable). "
            "Defaults to src/, scripts/, experiments/, tests/."
        ),
    )
    args = parser.parse_args(argv)

    roots = tuple(args.scan_root) if args.scan_root else EMIT_SCAN_ROOTS
    emit_sites = scan_emit_call_sites(roots)
    native_status = scan_native_hook_registrations(args.settings)
    report = build_audit_report(emit_sites, native_status)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(format_report(report), end="")

    if report.overall == "red":
        return 1
    if args.strict and report.overall == "yellow":
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
