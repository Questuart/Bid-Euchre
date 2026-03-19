"""Operator tooling for steward lane monitoring and lifecycle management.

This package is internal tooling. It is not part of the public engine API
surface and should not be re-exported broadly.

Modules:
    events      -- Durable event log (append/drain/query)
    worktrees   -- Worktree registry parsing, reconciliation, lifecycle
    status      -- Status aggregation across lanes/sessions/tasks
    watchdogs   -- Watchdog rules for health and progress monitoring
    scheduler   -- Periodic tick loop and scheduler state
    reviews     -- Provider-neutral PR review outcome aggregation
    ci          -- CI status polling and failure classification
"""

# Shared constant: GitHub status/check context names that represent
# review outcomes (not CI). Used by both reviews.py and ci.py to
# exclude review statuses from CI aggregation.
# Extend this tuple when adding a new online reviewer.
DEFAULT_REVIEW_CONTEXTS: tuple[str, ...] = ("reviewing-changes",)

# Default timeout (seconds) for gh CLI subprocess calls.
# Operator surfaces must never hang indefinitely.
GH_TIMEOUT_SECONDS: int = 30
