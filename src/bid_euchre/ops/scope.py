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

    Note: ``fnmatch`` does not handle ``**`` the same way as
    ``pathlib.glob``.  ``fnmatch('src/a.py', 'src/**/*.py')`` is
    ``False`` because ``**/`` requires at least one directory segment.
    As a workaround, patterns containing ``**/`` are also tested with
    the ``**/`` segment removed so that direct children match too.
    """
    for pattern in patterns:
        if fnmatch.fnmatch(path, pattern):
            return True
        # Also try matching just the basename for simple patterns
        # like "*.py" against full paths like "src/foo/bar.py"
        if "/" not in pattern and fnmatch.fnmatch(Path(path).name, pattern):
            return True
        # fnmatch does not treat ** like pathlib.glob: "src/**/*.py"
        # won't match "src/a.py" (direct child).  Collapse the **/
        # segment and retry so direct children are included.
        if "**/" in pattern:
            collapsed = pattern.replace("**/", "")
            if fnmatch.fnmatch(path, collapsed):
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


@dataclass
class ScopeEnforcementResult:
    """Result of scope drift enforcement against staged files.

    Actions:
    - ``"skip"``  — no active task or no declared scope, nothing to enforce.
    - ``"allow"`` — all staged files are within declared scope.
    - ``"warn"``  — drift ratio exceeds the warning threshold.
    - ``"block"`` — drift ratio exceeds the blocking threshold.
    """

    action: str  # "skip" | "allow" | "warn" | "block"
    task_id: str | None
    declared_patterns: list[str]
    staged_files: list[str]
    in_scope: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    drift_ratio: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "task_id": self.task_id,
            "declared_patterns": self.declared_patterns,
            "staged_files": self.staged_files,
            "in_scope": self.in_scope,
            "out_of_scope": self.out_of_scope,
            "drift_ratio": round(self.drift_ratio, 3),
            "reason": self.reason,
        }


# Default thresholds
WARN_DRIFT_RATIO = 0.5
BLOCK_DRIFT_RATIO = 0.8


def enforce_scope_drift(
    staged_files: list[str],
    declared_patterns: list[str],
    task_id: str | None = None,
    *,
    warn_threshold: float = WARN_DRIFT_RATIO,
    block_threshold: float = BLOCK_DRIFT_RATIO,
) -> ScopeEnforcementResult:
    """Enforce scope drift policy against staged files.

    Compares *staged_files* (relative to repo root) against
    *declared_patterns* (glob patterns from the task packet) and
    returns an enforcement action:

    - ``"skip"``  — no declared patterns (nothing to enforce).
    - ``"allow"`` — drift ratio ≤ *warn_threshold*.
    - ``"warn"``  — drift ratio > *warn_threshold* but ≤ *block_threshold*.
    - ``"block"`` — drift ratio > *block_threshold*.

    Args:
        staged_files: Paths staged for commit (relative to repo root).
        declared_patterns: Glob patterns from the active task packet.
        task_id: Optional task identifier for reporting.
        warn_threshold: Drift ratio above which a warning is emitted.
        block_threshold: Drift ratio above which the commit is blocked.

    Returns:
        ScopeEnforcementResult with the verdict and details.
    """
    if not declared_patterns:
        return ScopeEnforcementResult(
            action="skip",
            task_id=task_id,
            declared_patterns=declared_patterns,
            staged_files=staged_files,
            in_scope=list(staged_files),
            out_of_scope=[],
            drift_ratio=0.0,
            reason="No declared scope patterns — skipping enforcement.",
        )

    if not staged_files:
        return ScopeEnforcementResult(
            action="allow",
            task_id=task_id,
            declared_patterns=declared_patterns,
            staged_files=[],
            in_scope=[],
            out_of_scope=[],
            drift_ratio=0.0,
            reason="No staged files.",
        )

    in_scope: list[str] = []
    out_of_scope: list[str] = []
    for path in staged_files:
        if _matches_any_pattern(path, declared_patterns):
            in_scope.append(path)
        else:
            out_of_scope.append(path)

    drift_ratio = len(out_of_scope) / len(staged_files) if staged_files else 0.0

    if drift_ratio > block_threshold:
        action = "block"
        reason = (
            f"Drift ratio {drift_ratio:.0%} exceeds block threshold "
            f"({block_threshold:.0%}). "
            f"{len(out_of_scope)} of {len(staged_files)} staged file(s) "
            f"are outside declared scope."
        )
    elif drift_ratio > warn_threshold:
        action = "warn"
        reason = (
            f"Drift ratio {drift_ratio:.0%} exceeds warn threshold "
            f"({warn_threshold:.0%}). "
            f"{len(out_of_scope)} of {len(staged_files)} staged file(s) "
            f"are outside declared scope."
        )
    else:
        action = "allow"
        reason = "Staged files are within acceptable scope."
        if out_of_scope:
            reason = (
                f"{len(out_of_scope)} file(s) outside scope "
                f"(ratio {drift_ratio:.0%} ≤ {warn_threshold:.0%})."
            )

    return ScopeEnforcementResult(
        action=action,
        task_id=task_id,
        declared_patterns=declared_patterns,
        staged_files=staged_files,
        in_scope=in_scope,
        out_of_scope=out_of_scope,
        drift_ratio=drift_ratio,
        reason=reason,
    )


def get_active_task_scope(
    lane_id: str,
    task_queue_root: Path | None = None,
) -> tuple[str | None, list[str]]:
    """Look up the active dispatched task and its declared scope patterns.

    Args:
        lane_id: Canonical lane identity (e.g., ``"author-a"``).
        task_queue_root: Override for the task queue root directory.

    Returns:
        ``(packet_id, scope_declared)`` — the active task's ID and declared
        scope patterns.  ``(None, [])`` if no active task is found.
    """
    from bid_euchre.ops.task_queue import list_packets

    dispatched = list_packets(
        task_queue_root, status_filter="dispatched", owner_filter=lane_id
    )
    if not dispatched:
        return None, []
    pkt = dispatched[0]
    return pkt.packet_id, list(pkt.scope_declared)


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
