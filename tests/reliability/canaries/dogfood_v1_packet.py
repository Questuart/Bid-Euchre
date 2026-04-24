"""Canary task-packet generator for ``dogfood-v1``.

Builds a task-packet dict that the orchestrator dispatches to an author
lane to execute the canary scenario. The task scope is fixed by
``plans/steward_platform/canary_scenarios/dogfood.md`` §2.

The packet's ``metadata`` block carries ``canary_id`` and
``canary_version`` so downstream event emissions (task lifecycle, PR,
archivist, rollback) can be filtered back to a single canary run for
the 9-metric assertion.

Packet shape:
    {
        "title": "Canary: add last_verification_run to dashboard",
        "description": <verbatim §2 of dogfood.md>,
        "scope_declared": "src/bid_euchre/ops/dashboard.py "
                          "tests/unit/test_dashboard_canary_field.py "
                          "knowledge/adr/<adr_filename>",
        "validation": "uv run python -m pytest tests/unit/test_dashboard_canary_field.py",
        "priority": "normal",
        "task_type": "feature",
        "metadata": {
            "canary_id": "dogfood-v1-<UTC date>-<hhmm>",
            "canary_version": "dogfood-v1",
            "canary_trigger": "cron" | "on-demand" | "material-change",
        },
    }

Consumers use :func:`build_canary_packet` directly; tests use
:func:`_parse_canary_id` to round-trip the ID back to its components.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

CANARY_VERSION = "dogfood-v1"

# Trigger taxonomy — matches ``canary_run_start.trigger`` field on the
# event emission (Primitive A v1.N additive; see shaping §10).
CanaryTrigger = Literal["cron", "on-demand", "material-change"]

# Task-description verbatim from ``canary_scenarios/dogfood.md`` §2.
# Keep in sync — shaping doc explicitly calls this out as the canonical
# source (§2.1 no-duplication rule). If dogfood.md §2 ever changes,
# this constant must be updated in the same PR.
_CANARY_TASK_DESCRIPTION = (
    "Add a `last_verification_run` field to "
    "`src/bid_euchre/ops/dashboard.py` TUI output showing the "
    "timestamp and pass/fail state of the most recent canary run. "
    "Create a unit test asserting the field renders. File a mini-ADR "
    "under `knowledge/adr/` recording the field's purpose. Open a PR. "
    "Merge after CI + review passes. Confirm the archivist "
    "(Primitive D) creates a candidate entry referencing the canary's "
    "trace ID within 24h. Execute rollback: revert the merge; confirm "
    "dashboard reverts; confirm `canary_rollback_complete` event fires."
)

_CANARY_SCOPE_DECLARED = (
    "src/bid_euchre/ops/dashboard.py "
    "tests/unit/test_dashboard_canary_field.py "
    "knowledge/adr/<adr_filename>"
)

_CANARY_VALIDATION = "uv run python -m pytest tests/unit/test_dashboard_canary_field.py"


def build_canary_id(
    trigger: CanaryTrigger,
    *,
    now: datetime | None = None,
) -> str:
    """Generate a deterministic-ish canary_id.

    Format: ``dogfood-v1-<YYYY-MM-DD>-<HHMM>-<trigger>``

    Including the trigger suffix lets :func:`_parse_canary_id` recover
    the trigger without consulting the task queue (useful for the
    conditional-hook evaluator in
    ``.claude/hooks/material-platform-change-canary.sh``).
    """
    if now is None:
        now = datetime.now(timezone.utc)
    date_part = now.strftime("%Y-%m-%d")
    time_part = now.strftime("%H%M")
    return f"{CANARY_VERSION}-{date_part}-{time_part}-{trigger}"


_KNOWN_TRIGGERS: tuple[str, ...] = ("cron", "on-demand", "material-change")


def _parse_canary_id(canary_id: str) -> dict[str, str]:
    """Recover the trigger + timestamp from a canary_id string.

    Returns ``{"version": ..., "date": ..., "time": ..., "trigger": ...}``.
    Used by the conditional-hook evaluator and the canary-review skill.

    The ID format is ``<version>-<YYYY>-<MM>-<DD>-<HHMM>-<trigger>`` where
    both ``<version>`` and ``<trigger>`` may themselves contain dashes
    (e.g. ``dogfood-v1`` and ``on-demand``). We anchor on the known
    trigger suffix list, then reverse-parse the remainder from the tail.
    """
    trigger: str | None = None
    for candidate in _KNOWN_TRIGGERS:
        if canary_id.endswith("-" + candidate):
            trigger = candidate
            break
    if trigger is None:
        raise ValueError(f"Malformed canary_id (unknown trigger suffix): {canary_id!r}")

    head = canary_id[: -(len(trigger) + 1)]  # strip "-<trigger>"
    parts = head.split("-")
    # Expected remainder: [*version_tokens, "YYYY", "MM", "DD", "HHMM"]
    if len(parts) < 5:
        raise ValueError(f"Malformed canary_id: {canary_id!r}")
    time_part = parts[-1]
    date_part = "-".join(parts[-4:-1])
    version = "-".join(parts[:-4])
    return {
        "version": version,
        "date": date_part,
        "time": time_part,
        "trigger": trigger,
    }


def build_canary_packet(
    trigger: CanaryTrigger = "on-demand",
    *,
    canary_id: str | None = None,
    now: datetime | None = None,
    changed_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Build a task-packet dict for dispatch to an author lane.

    The returned dict is *packet-shape-compatible* with
    ``src/bid_euchre/ops/task_queue.py`` but does not itself call the
    queue — the ``/run-canary`` skill dispatches it.

    Args:
        trigger: ``cron`` / ``on-demand`` / ``material-change``. Flows to
            both the event emission and the canary_id suffix.
        canary_id: Override auto-generated ID (primarily for tests).
        now: Override current time (primarily for tests).
        changed_paths: If ``trigger == "material-change"``, the paths
            that fired the conditional hook. Recorded in metadata.

    Returns:
        A dict suitable for ``ops.task_queue.create_packet(...)``.
    """
    if canary_id is None:
        canary_id = build_canary_id(trigger, now=now)

    metadata: dict[str, Any] = {
        "canary_id": canary_id,
        "canary_version": CANARY_VERSION,
        "canary_trigger": trigger,
    }
    if trigger == "material-change" and changed_paths:
        metadata["canary_changed_paths"] = list(changed_paths)

    return {
        "title": f"Canary: {CANARY_VERSION} run ({trigger})",
        "description": _CANARY_TASK_DESCRIPTION,
        "scope_declared": _CANARY_SCOPE_DECLARED,
        "validation": _CANARY_VALIDATION,
        "priority": "normal",
        "task_type": "feature",
        "metadata": metadata,
    }
