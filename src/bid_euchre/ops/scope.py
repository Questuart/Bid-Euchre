"""Scope drift detection for task lifecycle management.

Compares a task's declared file scope (glob patterns) against its
actual touched files and flags any out-of-scope edits.  This is the
automation layer between the ``status.py`` scope persistence
(``update_task_scope``/``get_task_scope``) and the event bus.

Use ``check_scope_drift()`` to detect drift, and
``emit_scope_drift_event()`` to publish a ``watchdog_finding`` event
when drift is found.
"""

from __future__ import annotations

import fnmatch
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("ops.scope")


@dataclass
class ScopeDriftReport:
    """Result of a scope drift check for a single task."""

    task_id: str
    declared_patterns: list[str]
    touched_files: list[str]
    in_scope: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        """True if any touched files are outside declared scope."""
        return len(self.out_of_scope) > 0

    @property
    def drift_ratio(self) -> float:
        """Fraction of touched files that are out of scope (0.0–1.0)."""
        if not self.touched_files:
            return 0.0
        return len(self.out_of_scope) / len(self.touched_files)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "declared_patterns": self.declared_patterns,
            "touched_files": self.touched_files,
            "in_scope": self.in_scope,
            "out_of_scope": self.out_of_scope,
            "has_drift": self.has_drift,
            "drift_ratio": round(self.drift_ratio, 3),
        }


def _matches_any_pattern(path: str, patterns: list[str]) -> bool:
    """Check whether *path* matches at least one glob pattern.

    Supports both basename matching (``*.py``) and path matching
    (``src/bid_euchre/ops/*.py``).  Uses ``fnmatch.fnmatch`` which
    handles ``*``, ``?``, and ``[…]`` wildcards.
    """
    for pattern in patterns:
        if fnmatch.fnmatch(path, pattern):
            return True
        # Also try matching just the basename for simple patterns
        # like "*.py" against full paths like "src/foo/bar.py"
        if "/" not in pattern and fnmatch.fnmatch(Path(path).name, pattern):
            return True
    return False


def check_scope_drift(
    task_id: str,
    *,
    runtime_dir: Path | None = None,
) -> ScopeDriftReport:
    """Compare declared file scope against actual touched files.

    Reads scope data from the task state file (via
    ``status.get_task_scope``) and classifies each touched file as
    in-scope or out-of-scope based on declared glob patterns.

    If no declared patterns exist, all touched files are considered
    in-scope (no scope to drift from).

    Args:
        task_id: Task identifier.
        runtime_dir: Override for the runtime directory root.

    Returns:
        ScopeDriftReport with classified files.

    Raises:
        FileNotFoundError: If the task state file does not exist.
    """
    from bid_euchre.ops.status import get_task_scope

    scope = get_task_scope(task_id, runtime_dir=runtime_dir)
    declared = scope.get("declared_files", [])
    touched = scope.get("touched_files", [])

    if not declared:
        # No declared scope — nothing to drift from
        return ScopeDriftReport(
            task_id=task_id,
            declared_patterns=declared,
            touched_files=touched,
            in_scope=list(touched),
            out_of_scope=[],
        )

    in_scope: list[str] = []
    out_of_scope: list[str] = []

    for path in touched:
        if _matches_any_pattern(path, declared):
            in_scope.append(path)
        else:
            out_of_scope.append(path)

    return ScopeDriftReport(
        task_id=task_id,
        declared_patterns=declared,
        touched_files=touched,
        in_scope=in_scope,
        out_of_scope=out_of_scope,
    )


def emit_scope_drift_event(
    report: ScopeDriftReport,
    lane_id: str,
    events_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Emit a ``watchdog_finding`` event when scope drift is detected.

    Only emits an event if the report has drift (out-of-scope files).
    Returns None if no drift was found.

    Args:
        report: Scope drift check result.
        lane_id: Canonical lane identity (e.g., ``"author-a"``).
        events_dir: Override for events directory.

    Returns:
        The emitted event dict, or None if no drift detected.
    """
    if not report.has_drift:
        return None

    from bid_euchre.ops.events import append_event

    return append_event(
        event_type="watchdog_finding",
        source="ops.scope",
        lane_id=lane_id,
        payload={
            "finding": "scope_drift",
            "task_id": report.task_id,
            "out_of_scope_count": len(report.out_of_scope),
            "out_of_scope_files": report.out_of_scope,
            "drift_ratio": round(report.drift_ratio, 3),
        },
        events_dir=events_dir,
    )


# --- Formatting ---


def format_scope_drift_text(report: ScopeDriftReport) -> str:
    """Format a scope drift report as human-readable text."""
    lines = [f"=== Scope Drift — Task {report.task_id} ===", ""]

    if not report.touched_files:
        lines.append("No files touched yet.")
        return "\n".join(lines)

    if not report.declared_patterns:
        lines.append("No declared scope — all files considered in-scope.")
        lines.append(f"Touched: {len(report.touched_files)} file(s)")
        return "\n".join(lines)

    status = "DRIFT DETECTED" if report.has_drift else "Clean"
    lines.append(f"Status: {status}")
    lines.append(
        f"Drift ratio: {report.drift_ratio:.1%} "
        f"({len(report.out_of_scope)}/{len(report.touched_files)})"
    )
    lines.append("")
    lines.append(f"Declared patterns ({len(report.declared_patterns)}):")
    for p in report.declared_patterns:
        lines.append(f"  - {p}")

    if report.out_of_scope:
        lines.append("")
        lines.append(f"Out-of-scope files ({len(report.out_of_scope)}):")
        for f in report.out_of_scope:
            lines.append(f"  ! {f}")

    if report.in_scope:
        lines.append("")
        lines.append(f"In-scope files ({len(report.in_scope)}):")
        for f in report.in_scope:
            lines.append(f"  + {f}")

    return "\n".join(lines)


def format_scope_drift_json(report: ScopeDriftReport) -> dict[str, Any]:
    """Format a scope drift report as JSON-serializable dict."""
    return report.to_dict()
