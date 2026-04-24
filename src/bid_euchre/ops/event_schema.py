"""Event Schema v1.0 for steward observability (Primitive A).

This module is the canonical source of truth for the v1.0 event catalog,
the per-event-type field contract, and the §9.7 first-class IDs that
every event record carries as top-level fields.

See ``plans/steward_platform/1_primitive_A/shaping.md`` §2 for the
design, and ADR 007 (observability dispatcher pattern) for the
underlying decision.

**Version policy:**

- ``SCHEMA_VERSION = "1.0"`` is the Phase 0 Readiness target.
- Additive evolutions (new event types; new fields on existing types;
  new top-level correlation fields with default values) are ``v1.N`` and
  remain replay-compatible. Bump ``SCHEMA_VERSION`` when adding.
- Breaking changes require ``v2.0`` + migration plan + ADR.

**Top-level §9.7 IDs (§2.3 of shaping):** every event record carries
nine first-class identity fields (``project_id``, ``cell_id``,
``session_id``, ``task_id``, ``lane_id``, ``trace_id``,
``incident_fingerprint``, ``prompt_policy_version``, ``schema_version``)
regardless of event type. ``extra_fields`` is a **bug marker**, not a
fallback: known emitters must populate fields into the registry's
declared slots.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# ---------------------------------------------------------------------------
# Version constant
# ---------------------------------------------------------------------------

SCHEMA_VERSION: str = "1.0"
"""Current schema version. Bumped additively for v1.N; bumped to v2.0 on
breaking change (requires migration adapter in Primitive H.1)."""


# ---------------------------------------------------------------------------
# Verbosity tiers (ADR 007 adopted pattern; §3.3 of shaping)
# ---------------------------------------------------------------------------

VerbosityTier = Literal["minimal", "summary", "full"]

VERBOSITY_TIERS: tuple[VerbosityTier, ...] = ("minimal", "summary", "full")
"""Allowed verbosity levels: ``minimal`` (~200 B), ``summary`` (~500 B),
``full`` (1-50 KB). Selection per §3.3 of shaping."""


# ---------------------------------------------------------------------------
# §9.7 first-class IDs (§2.3 of shaping)
# ---------------------------------------------------------------------------

FIRST_CLASS_ID_FIELDS: tuple[str, ...] = (
    "project_id",
    "cell_id",
    "session_id",
    "task_id",
    "lane_id",
    "trace_id",
    "incident_fingerprint",
    "prompt_policy_version",
    "schema_version",
)
"""Nine §9.7 identity fields that must be present (may be ``null``) on
every event record. Emissions that route a §9.7 ID through
``extra_fields`` are a Pattern 8 bug-marker violation.
"""


# ---------------------------------------------------------------------------
# Correlation fields (ADR 007 adopted; §2.4 of shaping)
# ---------------------------------------------------------------------------

CORRELATION_FIELDS: tuple[str, ...] = ("seq", "pid", "timestamp_ns", "turn_id")
"""Four correlation fields set by the dispatcher; drive event ordering
and per-session turn bounding."""


# ---------------------------------------------------------------------------
# EventTypeSpec dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EventTypeSpec:
    """Per-event-type contract row.

    ``required_fields`` and ``optional_fields`` are *beyond* the baseline
    ``FIRST_CLASS_ID_FIELDS + CORRELATION_FIELDS + ("event_type",)``, which
    every event carries. A field listed in ``required_fields`` must be
    passed to ``events.emit()`` by the caller (or dispatcher rejects the
    emission).
    """

    required_fields: tuple[str, ...] = field(default_factory=tuple)
    optional_fields: tuple[str, ...] = field(default_factory=tuple)
    verbosity_default: VerbosityTier = "summary"
    schema_version_added: str = "1.0"
    replay_compat_window: str = "v1.x"

    def known_field(self, name: str) -> bool:
        """Return True if ``name`` is a registered known field for this type."""
        return name in self.required_fields or name in self.optional_fields


# ---------------------------------------------------------------------------
# EVENT_FIELD_REGISTRY — 35 event types in v1.0
# ---------------------------------------------------------------------------

# Baseline fields every event carries (populated by the dispatcher itself).
BASELINE_FIELDS: frozenset[str] = frozenset(
    FIRST_CLASS_ID_FIELDS + CORRELATION_FIELDS + ("event_type",)
)

EVENT_FIELD_REGISTRY: dict[str, EventTypeSpec] = {
    # -----------------------------------------------------------------------
    # Native Claude Code lifecycle hook events (§2.2 rows 1-15)
    # -----------------------------------------------------------------------
    "pre_tool_use": EventTypeSpec(
        required_fields=("tool_name", "tool_input"),
        optional_fields=("tool_use_id",),
        verbosity_default="minimal",
    ),
    "post_tool_use": EventTypeSpec(
        required_fields=("tool_name", "tool_input", "tool_response"),
        optional_fields=("tool_use_id", "duration_ms"),
        verbosity_default="minimal",
    ),
    "post_tool_use_failure": EventTypeSpec(
        required_fields=("tool_name", "tool_input", "error", "error_category"),
        optional_fields=("tool_use_id", "is_interrupt"),
        verbosity_default="summary",
    ),
    "permission_request": EventTypeSpec(
        required_fields=("tool_name", "tool_input", "permission_suggestions"),
    ),
    "permission_denied": EventTypeSpec(
        required_fields=("tool_name", "tool_input", "denial_reason"),
    ),
    "notification": EventTypeSpec(
        required_fields=("message",),
        optional_fields=("notification_id",),
    ),
    "user_prompt_submit": EventTypeSpec(
        required_fields=("prompt",),
        verbosity_default="full",
    ),
    "stop": EventTypeSpec(
        required_fields=("stop_hook_active",),
        optional_fields=("last_assistant_message",),
    ),
    "stop_failure": EventTypeSpec(
        required_fields=("stop_hook_active", "failure_category"),
        optional_fields=("last_assistant_message",),
    ),
    "subagent_start": EventTypeSpec(
        required_fields=("agent_id", "agent_type"),
        optional_fields=("parent_agent_id", "agent_transcript_path"),
    ),
    "subagent_stop": EventTypeSpec(
        required_fields=("agent_id", "agent_type"),
        optional_fields=("parent_agent_id", "agent_transcript_path"),
    ),
    "pre_compact": EventTypeSpec(
        required_fields=("trigger",),
        optional_fields=("custom_instructions",),
    ),
    "session_start": EventTypeSpec(
        required_fields=("source", "model", "archetype"),
        optional_fields=("agent_type",),
    ),
    "session_end": EventTypeSpec(
        required_fields=("reason",),
        optional_fields=("last_assistant_message",),
    ),
    "teammate_idle": EventTypeSpec(
        required_fields=("teammate_name", "idle_seconds"),
        optional_fields=("team_name",),
    ),
    # -----------------------------------------------------------------------
    # Steward task-lifecycle events (§2.2 rows 16-17)
    # -----------------------------------------------------------------------
    "task_started": EventTypeSpec(
        required_fields=("packet_id", "dispatched_by", "priority", "domain"),
        optional_fields=(
            "effort_hint",
            "model_hint",
            "task_type",
            "complexity_estimate",
        ),
    ),
    "task_completed": EventTypeSpec(
        required_fields=("packet_id", "outcome"),
        optional_fields=(
            "pr_number",
            "merged_at",
            "source",  # "steward" | "native" — native+steward merged per §2.2
            "title",
            "summary",
            "completed_by",
            "task_type",
            "complexity_estimate",
            "model_hint",
            "effort_hint",
            "actual_lane",
            "recommended_lane",
            "token_spend",
            "elapsed_seconds",
            "review_rounds",
            "shipped_outcome",
        ),
    ),
    # -----------------------------------------------------------------------
    # Worktree events (§2.2 row 18; emitters land in Primitive G)
    # -----------------------------------------------------------------------
    "worktree_create": EventTypeSpec(
        required_fields=("worktree_path", "branch", "protected"),
    ),
    "worktree_remove": EventTypeSpec(
        required_fields=("worktree_path", "branch", "protected"),
    ),
    # -----------------------------------------------------------------------
    # Canary lifecycle (4 types; owning primitive H.0)
    # -----------------------------------------------------------------------
    "canary_run_start": EventTypeSpec(
        required_fields=("canary_id", "trigger", "canary_version"),
    ),
    "canary_run_complete": EventTypeSpec(
        required_fields=(
            "canary_id",
            "success",
            "elapsed_seconds",
            "pass_metrics",
            "event_type_hash",
        ),
    ),
    "canary_run_fail": EventTypeSpec(
        required_fields=("canary_id", "failed_assertions", "elapsed_seconds"),
    ),
    "canary_rollback_complete": EventTypeSpec(
        required_fields=("canary_id", "rollback_pr"),
    ),
    # -----------------------------------------------------------------------
    # Archivist lifecycle (4 types; owning primitive D)
    # -----------------------------------------------------------------------
    "archivist_candidate_proposed": EventTypeSpec(
        required_fields=("candidate_path", "candidate_class"),
        optional_fields=("source_event_ids",),
    ),
    "archivist_candidate_promoted": EventTypeSpec(
        required_fields=("candidate_path", "promoted_path"),
        optional_fields=("operator",),
    ),
    "archivist_candidate_rejected": EventTypeSpec(
        required_fields=("candidate_path", "rejection_reason"),
        optional_fields=("operator",),
    ),
    "archivist_gc_proposed": EventTypeSpec(
        required_fields=("candidate_path", "gc_class"),
        optional_fields=("target_paths",),
    ),
    # -----------------------------------------------------------------------
    # Promotion lifecycle (4 types; owning primitives F + B)
    # -----------------------------------------------------------------------
    "promotion_evaluated": EventTypeSpec(
        required_fields=("candidate_id", "gates", "verdict"),
        optional_fields=("evidence_paths",),
    ),
    "promotion_passed": EventTypeSpec(
        required_fields=("candidate_id", "verdict_ids"),
    ),
    "promotion_failed": EventTypeSpec(
        required_fields=("candidate_id", "verdict_ids"),
    ),
    "promotion_rolled_back": EventTypeSpec(
        required_fields=("candidate_id", "rollback_pr", "reason"),
    ),
    # -----------------------------------------------------------------------
    # Rollback lifecycle (3 types; owning primitive G + per-primitive)
    # -----------------------------------------------------------------------
    "rollback_initiated": EventTypeSpec(
        required_fields=("change_id", "rollback_class"),
    ),
    "rollback_completed": EventTypeSpec(
        required_fields=("change_id", "rollback_pr"),
        optional_fields=("forward_event_ids", "reverse_event_ids"),
    ),
    "rollback_validated": EventTypeSpec(
        required_fields=("change_id", "validation_method"),
    ),
    # -----------------------------------------------------------------------
    # Latency measurements (2 types; self-instrumentation by Primitive A)
    # -----------------------------------------------------------------------
    "event_to_signal_latency": EventTypeSpec(
        required_fields=("source_event_id", "signal_type", "latency_ms"),
        verbosity_default="minimal",
    ),
    "bus_delivery_latency": EventTypeSpec(
        required_fields=("message_id", "delivery_ms"),
        verbosity_default="minimal",
    ),
}

# ---------------------------------------------------------------------------
# Registry introspection helpers
# ---------------------------------------------------------------------------


def is_known_event_type(event_type: str) -> bool:
    """Return True if ``event_type`` is registered in v1.0."""
    return event_type in EVENT_FIELD_REGISTRY


def get_spec(event_type: str) -> EventTypeSpec | None:
    """Return the :class:`EventTypeSpec` for ``event_type`` or None."""
    return EVENT_FIELD_REGISTRY.get(event_type)


def registered_types() -> tuple[str, ...]:
    """Return a sorted tuple of all registered event types."""
    return tuple(sorted(EVENT_FIELD_REGISTRY))


def baseline_fields() -> frozenset[str]:
    """Return the baseline fields populated on every event record."""
    return BASELINE_FIELDS


def known_field_for_event(event_type: str, field_name: str) -> bool:
    """Return True if ``field_name`` is a registered slot for ``event_type``.

    This check excludes baseline fields (see :func:`baseline_fields`);
    the registry is scanned for per-event-type required/optional slots.
    """
    spec = get_spec(event_type)
    if spec is None:
        return False
    return spec.known_field(field_name)


# Coverage classes (§2.2 of shaping): used by audit_event_emission.py
# to verify the ≥4 steward operational classes expected at Phase 0.
STEWARD_OPERATIONAL_CLASSES: dict[str, tuple[str, ...]] = {
    "task_lifecycle": ("task_started", "task_completed"),
    "canary_lifecycle": (
        "canary_run_start",
        "canary_run_complete",
        "canary_run_fail",
        "canary_rollback_complete",
    ),
    "archivist_lifecycle": (
        "archivist_candidate_proposed",
        "archivist_candidate_promoted",
        "archivist_candidate_rejected",
        "archivist_gc_proposed",
    ),
    "promotion_lifecycle": (
        "promotion_evaluated",
        "promotion_passed",
        "promotion_failed",
        "promotion_rolled_back",
    ),
    "rollback_lifecycle": (
        "rollback_initiated",
        "rollback_completed",
        "rollback_validated",
    ),
    "latency_measurements": (
        "event_to_signal_latency",
        "bus_delivery_latency",
    ),
    "worktree_lifecycle": ("worktree_create", "worktree_remove"),
}

# Native Claude Code lifecycle hook event types — the 15 absorbed at v1.0
# per shaping §4.1 (the `task_completed` row is merged with steward, so
# it's counted under `task_lifecycle` above and not duplicated here).
NATIVE_LIFECYCLE_EVENT_TYPES: tuple[str, ...] = (
    "pre_tool_use",
    "post_tool_use",
    "post_tool_use_failure",
    "permission_request",
    "permission_denied",
    "notification",
    "user_prompt_submit",
    "stop",
    "stop_failure",
    "subagent_start",
    "subagent_stop",
    "pre_compact",
    "session_start",
    "session_end",
    "teammate_idle",
)
