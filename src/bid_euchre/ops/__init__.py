"""Operator tooling for steward lane monitoring and lifecycle management.

This package is internal tooling. It is not part of the public engine API
surface and should not be re-exported broadly.

Modules:
    events      -- Durable event log (append/drain/query)
    worktrees   -- Worktree registry parsing, reconciliation, lifecycle
    status      -- Status aggregation across lanes/sessions/tasks
    watchdogs   -- Watchdog rules for health and progress monitoring
    scheduler   -- Periodic tick loop and scheduler state
"""
