"""Review loop state schema and persistence.

Manages the persisted state machine for the autonomous review loop.
State files live under .claude/runtime/review_loops/pr_<N>/state.json
(gitignored). Each PR gets its own state directory with per-round artifacts.
"""

from __future__ import annotations

import enum
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


class ReviewState(str, enum.Enum):
    """States in the review loop state machine."""

    INITIALIZED = "initialized"
    AUTHORING = "authoring"
    PR_OPEN = "pr_open"
    WAITING_FOR_CI = "waiting_for_ci"
    WAITING_FOR_CODEX = "waiting_for_codex"
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
        ReviewState.APPLYING_FIXES,
        ReviewState.READY_TO_MERGE,
        ReviewState.STOPPED_REVIEW_FAILURE,
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


def load_state(pr_number: int, base: Path | None = None) -> ReviewLoopState | None:
    """Load persisted state from disk. Returns None if no state file exists."""
    path = state_dir(pr_number, base) / "state.json"
    if not path.exists():
        return None
    with open(path) as f:
        return ReviewLoopState.from_dict(json.load(f))


def save_state(loop_state: ReviewLoopState, base: Path | None = None) -> Path:
    """Save state to disk, creating directories as needed."""
    directory = state_dir(loop_state.pr_number, base)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "state.json"
    with open(path, "w") as f:
        json.dump(loop_state.to_dict(), f, indent=2)
    return path
