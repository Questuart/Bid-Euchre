"""Review loop state schema and persistence.

Manages the persisted state machine for the autonomous review loop.
State files live under .claude/runtime/review_loops/pr_<N>/state.json
(gitignored). Each PR gets its own state directory with per-round artifacts.
"""

from __future__ import annotations

import enum
import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("review_state")


class ReviewState(str, enum.Enum):
    """States in the review loop state machine."""

    INITIALIZED = "initialized"
    AUTHORING = "authoring"
    PR_OPEN = "pr_open"
    WAITING_FOR_CI = "waiting_for_ci"
    WAITING_FOR_CODEX = "waiting_for_codex"
    SCORING_FINDINGS = "scoring_findings"
    APPLYING_FIXES = "applying_fixes"
    RETESTING = "retesting"
    READY_TO_MERGE = "ready_to_merge"
    MERGED = "merged"
    STOPPED_MAX_ITERATIONS = "stopped_max_iterations"
    STOPPED_NO_PROGRESS = "stopped_no_progress"
    STOPPED_CI_FAILURE = "stopped_ci_failure"
    STOPPED_REVIEW_FAILURE = "stopped_review_failure"


class ReviewMode(str, enum.Enum):
    """Review mode determines which Codex prompt to use."""

    STANDARD = "standard"
    REPORT_AUDIT = "report-audit"
    PLAN_AUDIT = "plan-audit"


# Valid state transitions: {from_state: [to_states]}
VALID_TRANSITIONS: dict[ReviewState, list[ReviewState]] = {
    ReviewState.INITIALIZED: [ReviewState.PR_OPEN],
    ReviewState.AUTHORING: [ReviewState.PR_OPEN],
    ReviewState.PR_OPEN: [
        ReviewState.WAITING_FOR_CI,
        ReviewState.STOPPED_CI_FAILURE,
    ],
    ReviewState.WAITING_FOR_CI: [
        ReviewState.WAITING_FOR_CODEX,
        ReviewState.STOPPED_CI_FAILURE,
    ],
    ReviewState.WAITING_FOR_CODEX: [
        ReviewState.SCORING_FINDINGS,
        ReviewState.STOPPED_REVIEW_FAILURE,
    ],
    ReviewState.SCORING_FINDINGS: [
        ReviewState.APPLYING_FIXES,
        ReviewState.READY_TO_MERGE,
    ],
    ReviewState.APPLYING_FIXES: [
        ReviewState.RETESTING,
        ReviewState.STOPPED_MAX_ITERATIONS,
        ReviewState.STOPPED_NO_PROGRESS,
    ],
    ReviewState.RETESTING: [
        ReviewState.WAITING_FOR_CI,
        ReviewState.STOPPED_CI_FAILURE,
    ],
    ReviewState.READY_TO_MERGE: [ReviewState.MERGED],
    # Terminal states have no outgoing transitions
    ReviewState.MERGED: [],
    ReviewState.STOPPED_MAX_ITERATIONS: [],
    ReviewState.STOPPED_NO_PROGRESS: [],
    ReviewState.STOPPED_CI_FAILURE: [],
    ReviewState.STOPPED_REVIEW_FAILURE: [],
}

TERMINAL_STATES = frozenset(
    s for s, targets in VALID_TRANSITIONS.items() if not targets
)

# Maps loop status labels to GitHub commit status API state values.
# GitHub only supports 4 states: pending, success, failure, error.
REVIEW_STATUS_MAP: dict[str, str] = {
    "pending": "pending",  # Loop started
    "in_progress": "pending",  # Mapped to pending for GitHub API
    "fail": "failure",  # Blocking findings
    "warn": "success",  # Non-blocking follow-ups only
    "ready": "success",  # Clean pass
    "degraded": "success",  # Review unavailable/unparseable (advisory)
}


def review_status_to_github(status: str) -> str:
    """Map a review loop status label to a GitHub commit status API state.

    Args:
        status: One of "pending", "in_progress", "fail", "warn", "ready".

    Returns:
        GitHub API state: "pending", "success", or "failure".
    """
    return REVIEW_STATUS_MAP.get(status, "pending")


@dataclass
class NormalizedFinding:
    """Unified finding schema used by prechecks, Codex CLI, and follow-up issues.

    Both ``deterministic_prechecks.Finding`` and ``codex_review_adapter.CodexFinding``
    can be converted to this schema via their ``to_dict()`` methods.
    """

    severity: str  # "P0", "P1", "P2"
    file: str  # relative path
    line: int  # 1-indexed
    category: str  # "correctness", "convention", "process", "test"
    check_id: str | None  # "C1", "C2", "N1", etc.
    message: str
    source: str  # "deterministic_precheck", "codex_cli"
    rationale: str | None = None  # Why this is flagged (for handoff clarity)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NormalizedFinding:
        """Create from a dict, ignoring unknown keys."""
        # Map raw_source to source if present (for Finding/CodexFinding compat)
        if "raw_source" in data and "source" not in data:
            data = {**data, "source": data["raw_source"]}
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ReviewLoopState:
    """Persisted state for one PR's review loop."""

    pr_number: int
    branch: str
    mode: str = ReviewMode.STANDARD.value
    state: str = ReviewState.INITIALIZED.value
    iteration_count: int = 0
    max_iterations: int = 5
    last_findings_hash: str | None = None
    last_head_sha: str | None = None
    last_ci_status: str | None = None
    last_codex_status: str | None = None
    opened_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    stop_reason: str | None = None
    codex_retry_count: int = 0
    ci_retry_count: int = 0
    # SHA tracking for idempotency
    initial_head_sha: str | None = None  # SHA when loop started
    current_head_sha: str | None = None  # tracks pushes (auto-fix commits)
    run_id: str | None = None  # unique ID: f"pr_{pr_number}_{head_sha[:7]}"
    # Plan tracking
    plan_path: str | None = None  # declared plan file from PR body

    @property
    def current_state(self) -> ReviewState:
        return ReviewState(self.state)

    @property
    def is_terminal(self) -> bool:
        return self.current_state in TERMINAL_STATES

    def transition(self, new_state: ReviewState) -> None:
        """Advance to a new state, validating the transition."""
        current = self.current_state
        if current in TERMINAL_STATES:
            raise InvalidTransitionError(
                f"Cannot transition from terminal state {current.value}"
            )

        # Global transitions: any non-terminal state can go to these
        global_targets = {
            ReviewState.STOPPED_MAX_ITERATIONS,
            ReviewState.STOPPED_NO_PROGRESS,
        }
        valid = set(VALID_TRANSITIONS.get(current, [])) | global_targets

        if new_state not in valid:
            raise InvalidTransitionError(
                f"Invalid transition: {current.value} → {new_state.value}. "
                f"Valid targets: {sorted(s.value for s in valid)}"
            )

        self.state = new_state.value
        self.updated_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewLoopState:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class InvalidTransitionError(Exception):
    """Raised when a state transition is not valid."""


def compute_findings_hash(findings: list[dict[str, Any]]) -> str:
    """Compute a deterministic hash of normalized findings for stagnation detection."""
    normalized = sorted(
        (f.get("file", ""), f.get("line", 0), f.get("message", "")) for f in findings
    )
    return hashlib.sha256(json.dumps(normalized).encode()).hexdigest()[:16]


def state_dir(pr_number: int, base: Path | None = None) -> Path:
    """Return the state directory for a PR's review loop."""
    if base is None:
        base = Path(".claude/runtime/review_loops")
    return base / f"pr_{pr_number}"


def round_dir(pr_number: int, iteration: int, base: Path | None = None) -> Path:
    """Return the directory for a specific round's artifacts."""
    return state_dir(pr_number, base) / f"round_{iteration}"


def load_state(
    pr_number: int,
    base: Path | None = None,
    *,
    head_sha: str | None = None,
) -> ReviewLoopState | None:
    """Load persisted state from disk.

    Args:
        pr_number: PR number to load state for.
        base: Override for state persistence directory.
        head_sha: If provided, check for stale state. Returns None if
            the loaded state's initial_head_sha doesn't match and the
            head_sha isn't a known auto-fix SHA (current_head_sha).

    Returns:
        ReviewLoopState if found and not stale, None otherwise.
    """
    path = state_dir(pr_number, base) / "state.json"
    if not path.exists():
        return None
    with open(path) as f:
        state = ReviewLoopState.from_dict(json.load(f))

    # SHA-based idempotency check
    if head_sha is not None and state.initial_head_sha is not None:
        if head_sha != state.initial_head_sha and head_sha != state.current_head_sha:
            logger.info(
                "PR #%d: head SHA changed %s -> %s (current_head: %s) -- stale",
                pr_number,
                state.initial_head_sha[:7],
                head_sha[:7],
                (state.current_head_sha or "none")[:7],
            )
            return None

    return state


def save_state(loop_state: ReviewLoopState, base: Path | None = None) -> Path:
    """Save state to disk, creating directories as needed."""
    directory = state_dir(loop_state.pr_number, base)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "state.json"
    with open(path, "w") as f:
        json.dump(loop_state.to_dict(), f, indent=2)
    return path


# --- Plan Review State ---


class PlanReviewState(str, enum.Enum):
    """States in the plan review loop state machine."""

    INITIALIZED = "initialized"
    CODEX_REVIEWING = "codex_reviewing"
    FINDINGS_RECEIVED = "findings_received"
    CLAUDE_FIXING = "claude_fixing"
    CODEX_FALLBACK = "codex_fallback"
    CLAUDE_FALLBACK_REVIEWING = "claude_fallback_reviewing"
    REVIEW_COMPLETE = "review_complete"
    REVIEW_COMPLETE_WITH_ISSUES = "review_complete_with_issues"


PLAN_REVIEW_VALID_TRANSITIONS: dict[PlanReviewState, list[PlanReviewState]] = {
    PlanReviewState.INITIALIZED: [PlanReviewState.CODEX_REVIEWING],
    PlanReviewState.CODEX_REVIEWING: [
        PlanReviewState.FINDINGS_RECEIVED,
        PlanReviewState.CODEX_FALLBACK,
    ],
    PlanReviewState.FINDINGS_RECEIVED: [
        PlanReviewState.CLAUDE_FIXING,
        PlanReviewState.REVIEW_COMPLETE,
        PlanReviewState.REVIEW_COMPLETE_WITH_ISSUES,
    ],
    PlanReviewState.CLAUDE_FIXING: [
        PlanReviewState.CODEX_REVIEWING,  # re-review after fix
    ],
    PlanReviewState.CODEX_FALLBACK: [
        PlanReviewState.CLAUDE_FALLBACK_REVIEWING,
    ],
    PlanReviewState.CLAUDE_FALLBACK_REVIEWING: [
        PlanReviewState.FINDINGS_RECEIVED,
    ],
    PlanReviewState.REVIEW_COMPLETE: [],
    PlanReviewState.REVIEW_COMPLETE_WITH_ISSUES: [],
}

PLAN_REVIEW_TERMINAL_STATES = frozenset(
    s for s, targets in PLAN_REVIEW_VALID_TRANSITIONS.items() if not targets
)


@dataclass
class PlanReviewLoopState:
    """Persisted state for one plan's review loop."""

    plan_path: str
    state_key: str  # hash of plan_path for directory naming
    tier: str  # "small", "medium", "governing"
    state: str = PlanReviewState.INITIALIZED.value
    iteration_count: int = 0
    max_iterations: int = 5
    last_findings_hash: str | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    stop_reason: str | None = None

    @property
    def current_state(self) -> PlanReviewState:
        return PlanReviewState(self.state)

    @property
    def is_terminal(self) -> bool:
        return self.current_state in PLAN_REVIEW_TERMINAL_STATES

    def transition(self, new_state: PlanReviewState) -> None:
        """Advance to a new state, validating the transition."""
        current = self.current_state
        if current in PLAN_REVIEW_TERMINAL_STATES:
            raise InvalidTransitionError(
                f"Cannot transition from terminal state {current.value}"
            )
        valid = set(PLAN_REVIEW_VALID_TRANSITIONS.get(current, []))
        # Global: any non-terminal can go to terminal
        valid |= PLAN_REVIEW_TERMINAL_STATES
        if new_state not in valid:
            raise InvalidTransitionError(
                f"Invalid plan review transition: {current.value} -> {new_state.value}. "
                f"Valid targets: {sorted(s.value for s in valid)}"
            )
        self.state = new_state.value
        self.updated_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlanReviewLoopState:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def plan_review_state_dir(state_key: str, base: Path | None = None) -> Path:
    """Return the state directory for a plan's review loop."""
    if base is None:
        base = Path(".claude/runtime/plan_reviews")
    return base / state_key


def load_plan_review_state(
    state_key: str, base: Path | None = None
) -> PlanReviewLoopState | None:
    """Load persisted plan review state from disk."""
    path = plan_review_state_dir(state_key, base) / "state.json"
    if not path.exists():
        return None
    with open(path) as f:
        return PlanReviewLoopState.from_dict(json.load(f))


def save_plan_review_state(
    loop_state: PlanReviewLoopState, base: Path | None = None
) -> Path:
    """Save plan review state to disk, creating directories as needed."""
    directory = plan_review_state_dir(loop_state.state_key, base)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "state.json"
    with open(path, "w") as f:
        json.dump(loop_state.to_dict(), f, indent=2)
    return path
