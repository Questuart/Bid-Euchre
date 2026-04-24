"""Effort-policy resolver — per-archetype × per-task-type effort tier defaults.

Pure-function home for B.1 adaptive-dispatch to consume at dispatch time.
The canonical policy is authored in `.claude/rules/effort_policy.md`; this
module encodes the same table as a Python dict so `effort_for(archetype,
task_type)` can be called from any lane without reading files at dispatch time.

Drift discipline: `tests/unit/test_effort_policy.py` parses the markdown
table and asserts it matches `POLICY_TABLE` 1:1. A change to the .md table
without a matching change here (or vice versa) fails the test.

The tier vocabulary here (`"lower"`, `"xhigh"`, `"max"`) is the *policy*
vocabulary. It maps to the `VALID_EFFORT_HINTS` enum in `task_queue.py` via:

    lower → low
    xhigh → high
    max   → max

See `.claude/rules/effort_policy.md` §"Tier vocabulary" for the full mapping.
"""

from __future__ import annotations

from typing import Final

POLICY_VERSION: Final[str] = "b10-v1.0"

# Tier vocabulary. `n/a` is a sentinel meaning "dispatch never routes this
# task_type to this archetype"; `effort_for()` raises on `n/a` pairings.
# Exported so callers (lint, B.1 dispatch, B.12 probe) can validate tier
# literals against the same registry.
VALID_TIERS: Final[frozenset[str]] = frozenset({"lower", "xhigh", "max", "n/a"})

_VALID_ARCHETYPES: Final[tuple[str, ...]] = (
    "orchestrator",
    "ops",
    "review",
    "analyst",
    "author",
    "brws-author",
    "flex",
)

_VALID_TASK_TYPES: Final[tuple[str, ...]] = (
    "investigation",
    "implementation",
    "refactor",
    "fix",
    "docs",
)

# Canonical policy table. Keep in sync with `.claude/rules/effort_policy.md`.
# Row order matches the markdown table so the drift test can compare 1:1.
POLICY_TABLE: Final[dict[str, dict[str, str]]] = {
    "orchestrator": {
        "investigation": "xhigh",
        "implementation": "n/a",
        "refactor": "n/a",
        "fix": "n/a",
        "docs": "n/a",
    },
    "ops": {
        "investigation": "lower",
        "implementation": "n/a",
        "refactor": "n/a",
        "fix": "lower",
        "docs": "lower",
    },
    "review": {
        "investigation": "xhigh",
        "implementation": "n/a",
        "refactor": "n/a",
        "fix": "n/a",
        "docs": "n/a",
    },
    "analyst": {
        "investigation": "max",
        "implementation": "n/a",
        "refactor": "n/a",
        "fix": "n/a",
        "docs": "xhigh",
    },
    "author": {
        "investigation": "n/a",
        "implementation": "xhigh",
        "refactor": "xhigh",
        "fix": "xhigh",
        "docs": "lower",
    },
    "brws-author": {
        "investigation": "n/a",
        "implementation": "xhigh",
        "refactor": "xhigh",
        "fix": "xhigh",
        "docs": "lower",
    },
    "flex": {
        "investigation": "xhigh",
        "implementation": "xhigh",
        "refactor": "xhigh",
        "fix": "xhigh",
        "docs": "lower",
    },
}


def effort_for(archetype: str, task_type: str) -> str:
    """Return the policy-default effort tier for `(archetype, task_type)`.

    Parameters
    ----------
    archetype:
        One of `orchestrator`, `ops`, `review`, `analyst`, `author`,
        `brws-author`, `flex`. Flex is the union-row — takes any task type.
    task_type:
        One of `investigation`, `implementation`, `refactor`, `fix`, `docs`.

    Returns
    -------
    str
        One of `"lower"`, `"xhigh"`, `"max"`.

    Raises
    ------
    ValueError
        If `archetype` or `task_type` is unknown, or if the pairing is `n/a`
        (archetype refuses that task_type — orchestrator must reassign).
    """
    if archetype not in POLICY_TABLE:
        raise ValueError(
            f"unknown archetype {archetype!r}; expected one of {_VALID_ARCHETYPES!r}"
        )
    row = POLICY_TABLE[archetype]
    if task_type not in row:
        raise ValueError(
            f"unknown task_type {task_type!r}; expected one of {_VALID_TASK_TYPES!r}"
        )
    tier = row[task_type]
    if tier == "n/a":
        raise ValueError(
            f"archetype {archetype!r} does not accept task_type "
            f"{task_type!r} (policy cell = n/a); orchestrator must reassign "
            f"to an archetype with a non-n/a cell, or reclassify the task_type"
        )
    return tier


__all__ = [
    "POLICY_TABLE",
    "POLICY_VERSION",
    "VALID_TIERS",
    "effort_for",
]
