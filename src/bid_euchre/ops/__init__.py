"""Operator tooling for steward lane monitoring and lifecycle management.

This package is internal tooling. It is not part of the public engine API
surface and should not be re-exported broadly.

Modules:
    events      -- Durable event log (append/drain/query)
    worktrees   -- Worktree registry parsing, reconciliation, lifecycle
    snapshots   -- Shadow snapshots for auditable rollback of autonomous edits
    status      -- Status aggregation across lanes/sessions/tasks
    watchdogs   -- Watchdog rules for health and progress monitoring
                    (heartbeats, task progress, worktree health,
                     CI stuck, sub-agent failures, scope drift)
    scheduler   -- Periodic tick loop, scheduler state, daemon mode
    reviews     -- Provider-neutral PR review outcome aggregation
    ci          -- CI status polling and failure classification
    scope       -- Scope drift detection (declared vs touched files)
    retries     -- Retry follow-through scanning and summary
    index       -- SQLite FTS5 audit index for operational history
    memory      -- Curated memory for stable operator facts
    context_safety -- Content scanning for memory/summary/skill promotion
    compaction  -- Session compaction and non-lossy context archival
    message_bus -- Durable lane-to-lane communication bus (Platform-3)
    task_queue  -- Durable task packet queue (Platform-2)
"""

# Shared constant: GitHub status/check context names that represent
# review outcomes (not CI). Used by both reviews.py and ci.py to
# exclude review statuses from CI aggregation.
# Extend this tuple when adding a new online reviewer.
DEFAULT_REVIEW_CONTEXTS: tuple[str, ...] = ("reviewing-changes",)

# --- Three-category check classification ---
#
# review_gate: merge-relevant review statuses (branch protection may require these)
# advisory:   informational review checks (never block CI or merge)
# ci:         everything else (real CI checks)

REVIEW_GATE_CONTEXTS: tuple[str, ...] = DEFAULT_REVIEW_CONTEXTS
"""Check names that are merge-relevant review gates (alias for DEFAULT_REVIEW_CONTEXTS)."""

ADVISORY_CONTEXTS: tuple[str, ...] = ("claude-review", "enable-auto-merge")
"""Check names that are advisory-only — infrastructure failures here must not poison CI.

``enable-auto-merge`` is GitHub plumbing (the auto-merge queue action), not a
validation check. Its failures should never count as CI failures.

NOTE: When Codex Cloud review is enabled (via chatgpt.com/codex), observe
the actual GitHub check/status context name it emits, then add it here.
Do not add speculative names — verify on a real PR first.
"""

NON_CI_CONTEXTS: tuple[str, ...] = REVIEW_GATE_CONTEXTS + ADVISORY_CONTEXTS
"""Union of all non-CI check contexts (review gate + advisory)."""


def classify_check(name: str) -> str:
    """Classify a GitHub check/status context name into a category.

    Args:
        name: The check or status context name (e.g. ``"tests"``,
            ``"reviewing-changes"``, ``"claude-review"``).

    Returns:
        ``"review_gate"`` for merge-relevant review statuses,
        ``"advisory"`` for informational review checks, or
        ``"ci"`` for everything else (conservative default).
    """
    if name in REVIEW_GATE_CONTEXTS:
        return "review_gate"
    if name in ADVISORY_CONTEXTS:
        return "advisory"
    return "ci"


# DEPRECATED fail-closed allowlist — prefer classify_check() (fail-open denylist).
# New CI jobs are included by default via classify_check(); this set is retained
# for backward compat only.  Updated for sharded CI (PR #1086): the old
# "prechecks" and "governance" jobs were removed; the new jobs are "checks",
# "tests-shard" (matrix: "tests-shard (1)", "tests-shard (2)"), "notebooks",
# "promotion-gate", and the "tests" aggregation gate.  See #1036, #1041, #1093.
CI_CHECK_NAMES: frozenset[str] = frozenset(
    {
        "changes",
        "checks",
        "tests-shard",
        "tests-shard (1)",
        "tests-shard (2)",
        "notebooks",
        "promotion-gate",
        "tests",
    }
)

# Default timeout (seconds) for gh CLI subprocess calls.
# Operator surfaces must never hang indefinitely.
GH_TIMEOUT_SECONDS: int = 30
