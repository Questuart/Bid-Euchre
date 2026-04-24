"""Weekly improvement-mechanism evaluation (B.12, Primitive B Phase 0).

Reads the durable event stream plus the git log, computes five rolling-window
metrics comparing the current window versus the prior window, flags recurring
task-class signatures for codification review, and correlates per-change
mechanism deltas against the net-positive / net-negative heuristic per
``plans/steward_platform/2_primitive_B/shaping.md`` §9.

Output artifact: ``knowledge/_candidates/<YYYY-MM-DD>_improvement_metrics.md``

The five metrics (shaping §9.1):

- ``retry_rate`` — fraction of ``task_started`` events whose matched
  ``task_completed`` has an outcome other than ``"completed"`` (or a
  ``task_failed`` / ``task_blocked`` terminator).
- ``author_rework_rate`` — per-packet rework rate (ratio of
  ``review_rounds > 1`` completions to all completions).  The shaping
  spec originally called for a GitHub push-count probe; we approximate
  with the review_rounds field already on ``task_completed`` payloads
  to keep the script hermetic (no outbound HTTP).
- ``routing_correction_rate`` — fraction of ``dispatch_recommendation``
  events whose ``payload.override`` flag is true (the B.1 advisor
  ranked one lane but the dispatcher picked another). No separate
  ``dispatch_override`` event type exists — override is a field on
  the recommendation event.
- ``prompt_policy_rollback_rate`` — rate of ``git revert`` commits
  per week that touched ``.claude/rules/prompt_policy/**``.
- ``skill_promotion_usefulness`` — retry-rate delta in the N days
  after each ``skill_promoted`` event versus the N days before.
  Positive numbers mean retry rate dropped after promotion (good).

Repeat-task probe (shaping §9.2): surfaces task-class signatures that
repeat ≥3 times in the rolling window. Signature is
``(tokenize(packet_title), archetype, task_type, effort_hint)``;
tokenization strips packet-specific identifiers (task IDs, issue
numbers, file paths) so semantically similar tasks cluster.

Mechanism-change deltas (shaping §9.3): diffs this-window vs.
prior-window metric values and attributes each delta to any git
commit in the window that touched a mechanism surface
(``.claude/rules/prompt_policy/**``, ``tool_risk_registry.md``,
``effort_policy.md``, ``src/bid_euchre/ops/learning.py``, or a
skill promotion/demotion event).

Usage:

    uv run python scripts/internal/measure_improvements.py --since 2026-04-01
    uv run python scripts/internal/measure_improvements.py --window-days 7

Best-effort event emission: on success the script tries to append an
``improvement_metrics_computed`` event. Primitive A has not registered
that event type yet (shaping §9.4 phase 1), so the emission is wrapped
in a try-except — a missing event type is a warning, not a failure.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger("measure_improvements")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Canonical events file (matches ``ops.events.DEFAULT_EVENTS_DIR``).
DEFAULT_EVENTS_RELPATH = Path(".claude/runtime/events/events.jsonl")

#: Archived events file (drained entries retain chronological order).
DEFAULT_ARCHIVE_RELPATH = Path(".claude/runtime/events/events.archive.jsonl")

#: Output directory for the improvement-metrics candidate artifacts.
DEFAULT_OUTPUT_RELPATH = Path("knowledge/_candidates")

#: Default rolling-window width (per shaping §9.4 "nightly" cadence).
DEFAULT_WINDOW_DAYS: int = 14

#: Repeat-task probe threshold (shaping §9.2).
REPEAT_PROBE_MIN_OCCURRENCES: int = 3

#: Mechanism-surface path patterns (shaping §9.3).
MECHANISM_SURFACES: tuple[str, ...] = (
    ".claude/rules/prompt_policy/",
    ".claude/rules/tool_risk_registry.md",
    ".claude/rules/effort_policy.md",
    "src/bid_euchre/ops/learning.py",
)

#: Tokenization: strip packet-specific identifiers so semantically
#: similar titles cluster.  The order matters — file paths strip first,
#: then issue / PR references, then remaining integers.
_TOKEN_SUB_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Match quoted or unquoted file paths with extensions (e.g. "foo.py",
    # "scripts/internal/thing.py"). Keep the ".py" suffix visible so
    # "fix in foo.py" still tokenizes usefully, but drop the path prefix.
    (re.compile(r"[\w/\.\-]*/([\w\-]+\.\w{1,4})\b"), r"\1"),
    # Issue / PR / packet references: "#1234", "PR #567", "issue 890".
    (re.compile(r"#\d+"), ""),
    (re.compile(r"\b(?:pr|issue|ticket|packet)\s+\w+", re.IGNORECASE), ""),
    # Hex packet IDs and run IDs (8+ hex chars).
    (re.compile(r"\b[0-9a-f]{8,}\b", re.IGNORECASE), ""),
    # Remaining bare integers.
    (re.compile(r"\b\d+\b"), ""),
    # Common noise words that don't carry semantic weight.
    (re.compile(r"\b(?:the|a|an|for|to|in|on|of|at)\b", re.IGNORECASE), ""),
    # Collapse whitespace runs.
    (re.compile(r"\s+"), " "),
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WindowMetrics:
    """Five-metric snapshot for one window."""

    retry_rate: float
    author_rework_rate: float
    routing_correction_rate: float
    prompt_policy_rollback_rate: float
    skill_promotion_usefulness: float
    observations: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class RepeatProbe:
    """One recurring task-class signature."""

    signature: str
    archetype: str
    task_type: str
    effort: str
    count: int


@dataclass(frozen=True)
class MechanismChange:
    """One git commit that touched a mechanism surface."""

    commit_sha: str
    summary: str
    timestamp: datetime
    surfaces: tuple[str, ...]
    is_revert: bool


@dataclass(frozen=True)
class MechanismDelta:
    """A metric delta attributed to a specific mechanism change."""

    change: MechanismChange
    before_retry_rate: float
    after_retry_rate: float
    net_sign: str  # "net-positive", "net-negative", or "flat"


# ---------------------------------------------------------------------------
# Tokenization — repeat-task probe signature helper
# ---------------------------------------------------------------------------


def tokenize_title(title: str) -> str:
    """Normalize a packet title so semantically similar titles cluster.

    Strips file-path prefixes (keeping the basename), issue/PR
    references, hex packet IDs, and common stopwords. Returns the
    normalized title lowercased with whitespace collapsed.

    Examples
    --------
    >>> tokenize_title("Fix #1234 in foo.py")
    'fix foo.py'
    >>> tokenize_title("Fix #5678 in foo.py")
    'fix foo.py'
    >>> tokenize_title("Fix issue in foo.py")
    'fix foo.py'
    """
    normalized = title.strip().lower()
    for pattern, replacement in _TOKEN_SUB_PATTERNS:
        normalized = pattern.sub(replacement, normalized)
    return normalized.strip()


def signature_for(
    title: str,
    archetype: str | None,
    task_type: str | None,
    effort: str | None,
) -> str:
    """Build the full repeat-probe signature string."""
    return (
        f"{tokenize_title(title)!r} × {archetype or 'unknown'}"
        f" × {task_type or 'unknown'} × {effort or 'unknown'}"
    )


# ---------------------------------------------------------------------------
# Event loading
# ---------------------------------------------------------------------------


def _parse_iso(ts: str) -> datetime | None:
    """Parse an ISO-8601 timestamp; return None on failure."""
    try:
        # Python 3.11+: fromisoformat accepts the "Z" suffix.
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def load_events(
    events_path: Path | None = None,
    archive_path: Path | None = None,
    *,
    repo_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Load all events from the live log and the archive, sorted by timestamp.

    Missing files are treated as empty.  JSON parse errors on individual
    lines are dropped with a debug log (best-effort read contract).

    Parameters
    ----------
    events_path, archive_path
        Optional overrides for the live + archive event paths. When both
        are ``None``, canonical paths anchored at ``repo_root`` (or
        ``.cwd()`` fallback) are used.
    repo_root
        Optional repo root override.
    """
    if repo_root is None:
        try:
            from scripts.internal._repo_utils import find_repo_root

            repo_root = find_repo_root()
        except Exception:
            repo_root = Path.cwd()

    paths: list[Path] = []
    if events_path is not None:
        paths.append(events_path)
    else:
        paths.append(repo_root / DEFAULT_EVENTS_RELPATH)
    if archive_path is not None:
        paths.append(archive_path)
    else:
        paths.append(repo_root / DEFAULT_ARCHIVE_RELPATH)

    events: list[dict[str, Any]] = []
    for p in paths:
        if not p.exists():
            continue
        try:
            with p.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError as exc:
                        logger.debug("Skipping malformed event line in %s: %s", p, exc)
        except OSError as exc:
            logger.debug("Could not open event file %s: %s", p, exc)
    # Stable sort by timestamp so window slicing is deterministic.
    events.sort(key=lambda e: str(e.get("timestamp", "")))
    return events


# ---------------------------------------------------------------------------
# Window filtering
# ---------------------------------------------------------------------------


def _event_ts(event: dict[str, Any]) -> datetime | None:
    return _parse_iso(str(event.get("timestamp", "")))


def window_events(
    events: Iterable[dict[str, Any]],
    window_start: datetime,
    window_end: datetime,
) -> list[dict[str, Any]]:
    """Return events whose timestamp falls in ``[window_start, window_end)``."""
    out: list[dict[str, Any]] = []
    for e in events:
        ts = _event_ts(e)
        if ts is None:
            continue
        if window_start <= ts < window_end:
            out.append(e)
    return out


# ---------------------------------------------------------------------------
# Five metrics
# ---------------------------------------------------------------------------


def _packet_id(event: dict[str, Any]) -> str | None:
    payload = event.get("payload") or {}
    pid = payload.get("packet_id")
    return str(pid) if pid else None


def compute_retry_rate(
    events: list[dict[str, Any]],
) -> tuple[float, dict[str, int]]:
    """Fraction of ``task_started`` events whose terminator is not a clean completion.

    "Clean completion" = ``task_completed`` with ``payload.outcome == "completed"``
    (or simply a ``task_completed`` event when outcome is absent — we err on
    the side of success for unobservable outcomes). Any ``task_failed``,
    ``task_blocked``, or ``task_completed`` with ``outcome != "completed"``
    counts as a non-clean terminator.
    """
    started_ids: set[str] = set()
    terminator_outcome: dict[str, str] = {}

    for e in events:
        etype = e.get("event_type")
        pid = _packet_id(e)
        if not pid:
            continue
        if etype == "task_started":
            started_ids.add(pid)
        elif etype in ("task_completed", "task_failed", "task_blocked"):
            # Later terminators win (if a task was blocked then completed).
            if etype == "task_completed":
                payload = e.get("payload") or {}
                outcome = payload.get("outcome") or "completed"
                terminator_outcome[pid] = str(outcome)
            else:
                terminator_outcome[pid] = etype  # "task_failed" / "task_blocked"

    if not started_ids:
        return 0.0, {"started": 0, "retried": 0}

    retried = sum(
        1
        for pid in started_ids
        if pid in terminator_outcome and terminator_outcome[pid] != "completed"
    )
    rate = retried / len(started_ids)
    return rate, {"started": len(started_ids), "retried": retried}


def compute_author_rework_rate(
    events: list[dict[str, Any]],
) -> tuple[float, dict[str, int]]:
    """Fraction of ``task_completed`` events whose payload signals rework.

    Signals (any one counts):

    - ``payload.review_rounds > 1``
    - ``payload.rework == True``
    - ``payload.outcome == "reworked"``

    Packets without a completion event are excluded.
    """
    total = 0
    reworked = 0
    for e in events:
        if e.get("event_type") != "task_completed":
            continue
        payload = e.get("payload") or {}
        total += 1
        review_rounds = payload.get("review_rounds")
        if isinstance(review_rounds, (int, float)) and review_rounds > 1:
            reworked += 1
            continue
        if bool(payload.get("rework")):
            reworked += 1
            continue
        if str(payload.get("outcome", "")).lower() == "reworked":
            reworked += 1
    if total == 0:
        return 0.0, {"completed": 0, "reworked": 0}
    return reworked / total, {"completed": total, "reworked": reworked}


def compute_routing_correction_rate(
    events: list[dict[str, Any]],
) -> tuple[float, dict[str, int]]:
    """Fraction of ``dispatch_recommendation`` events whose ``override`` flag is true.

    No separate ``dispatch_override`` event type exists in
    ``VALID_EVENT_TYPES`` — override is tracked as a field on the
    recommendation event itself (see ``ops.learning``).
    """
    total = 0
    overrides = 0
    for e in events:
        if e.get("event_type") != "dispatch_recommendation":
            continue
        total += 1
        payload = e.get("payload") or {}
        if bool(payload.get("override")):
            overrides += 1
    if total == 0:
        return 0.0, {"recommendations": 0, "overrides": 0}
    return overrides / total, {"recommendations": total, "overrides": overrides}


def compute_prompt_policy_rollback_rate(
    window_start: datetime,
    window_end: datetime,
    *,
    repo_root: Path | None = None,
) -> tuple[float, dict[str, int]]:
    """Rate of ``git revert`` commits per week touching ``.claude/rules/prompt_policy/**``.

    Parses ``git log --grep='^Revert '`` for the given window and
    filters by paths. A rate of 1.0 means one revert per 7 days; higher
    values mean more churn.
    """
    commits = _git_log_in_window(
        window_start, window_end, repo_root=repo_root, grep="^Revert "
    )
    prompt_policy_reverts = 0
    for commit in commits:
        if any(p.startswith(".claude/rules/prompt_policy/") for p in commit["paths"]):
            prompt_policy_reverts += 1
    days = max(1.0, (window_end - window_start).total_seconds() / 86400.0)
    weeks = days / 7.0
    rate = prompt_policy_reverts / weeks if weeks > 0 else 0.0
    return rate, {
        "reverts_matching": prompt_policy_reverts,
        "window_days": int(round(days)),
    }


def compute_skill_promotion_usefulness(
    events: list[dict[str, Any]],
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> tuple[float, dict[str, int]]:
    """Retry-rate delta in the N days after each ``skill_promoted`` event.

    For each ``skill_promoted`` event, compute the retry rate in the
    post-promotion window of ``window_days`` and the retry rate in the
    equivalent-length pre-promotion window. Return the mean ``(pre -
    post)`` delta across all promotions — positive numbers mean retry
    rates dropped after promotions (i.e., the promotion helped).
    """
    promotions = [e for e in events if e.get("event_type") == "skill_promoted"]
    if not promotions:
        return 0.0, {"promotions": 0}

    deltas: list[float] = []
    for promo in promotions:
        ts = _event_ts(promo)
        if ts is None:
            continue
        pre_start = ts - timedelta(days=window_days)
        post_end = ts + timedelta(days=window_days)
        pre_events = window_events(events, pre_start, ts)
        post_events = window_events(events, ts, post_end)
        pre_rate, _ = compute_retry_rate(pre_events)
        post_rate, _ = compute_retry_rate(post_events)
        deltas.append(pre_rate - post_rate)
    if not deltas:
        return 0.0, {"promotions": len(promotions), "comparable": 0}
    return sum(deltas) / len(deltas), {
        "promotions": len(promotions),
        "comparable": len(deltas),
    }


def compute_window_metrics(
    events: list[dict[str, Any]],
    window_start: datetime,
    window_end: datetime,
    *,
    repo_root: Path | None = None,
) -> WindowMetrics:
    """Compute all five metrics for one window."""
    scoped = window_events(events, window_start, window_end)
    retry, retry_obs = compute_retry_rate(scoped)
    rework, rework_obs = compute_author_rework_rate(scoped)
    routing, routing_obs = compute_routing_correction_rate(scoped)
    revert, revert_obs = compute_prompt_policy_rollback_rate(
        window_start, window_end, repo_root=repo_root
    )
    usefulness, usefulness_obs = compute_skill_promotion_usefulness(
        events, window_days=(window_end - window_start).days or 1
    )
    observations: dict[str, int] = {}
    for label, obs in (
        ("retry", retry_obs),
        ("rework", rework_obs),
        ("routing", routing_obs),
        ("revert", revert_obs),
        ("usefulness", usefulness_obs),
    ):
        for k, v in obs.items():
            observations[f"{label}_{k}"] = int(v)
    return WindowMetrics(
        retry_rate=retry,
        author_rework_rate=rework,
        routing_correction_rate=routing,
        prompt_policy_rollback_rate=revert,
        skill_promotion_usefulness=usefulness,
        observations=observations,
    )


# ---------------------------------------------------------------------------
# Repeat-task probe
# ---------------------------------------------------------------------------


def compute_repeat_probes(
    events: list[dict[str, Any]],
    *,
    min_occurrences: int = REPEAT_PROBE_MIN_OCCURRENCES,
) -> list[RepeatProbe]:
    """Surface task-class signatures recurring ≥``min_occurrences`` times.

    Reads ``dispatch_recommendation`` events, builds the
    ``(tokenized_title, archetype, task_type, effort)`` signature per
    event, and returns a sorted list of probes.  Sort order is count
    desc → signature asc for determinism.
    """
    counter: Counter[tuple[str, str, str, str]] = Counter()
    for e in events:
        if e.get("event_type") != "dispatch_recommendation":
            continue
        payload = e.get("payload") or {}
        title = str(payload.get("packet_title") or payload.get("title") or "")
        if not title:
            # Some emissions may only carry packet_id; fall back to it.
            title = str(payload.get("packet_id") or "")
        archetype = str(payload.get("archetype") or "unknown")
        task_type = str(payload.get("task_type") or "unknown")
        effort = str(
            payload.get("resolved_effort_hint")
            or payload.get("effort_hint")
            or "unknown"
        )
        key = (tokenize_title(title), archetype, task_type, effort)
        counter[key] += 1

    probes: list[RepeatProbe] = []
    for (sig, archetype, task_type, effort), count in counter.items():
        if count < min_occurrences:
            continue
        probes.append(
            RepeatProbe(
                signature=sig,
                archetype=archetype,
                task_type=task_type,
                effort=effort,
                count=count,
            )
        )
    probes.sort(key=lambda p: (-p.count, p.signature, p.archetype))
    return probes


# ---------------------------------------------------------------------------
# Mechanism-change tracking (git integration)
# ---------------------------------------------------------------------------


def _git_log_in_window(
    window_start: datetime,
    window_end: datetime,
    *,
    repo_root: Path | None = None,
    grep: str | None = None,
) -> list[dict[str, Any]]:
    """Run ``git log`` constrained to the window and return commit metadata.

    Returns a list of dicts with keys ``sha``, ``summary``, ``timestamp``,
    ``paths``. Failures (git not available, shallow repo, etc.) return
    an empty list — the caller treats this as "no mechanism changes
    observed" rather than crashing.
    """
    if repo_root is None:
        try:
            from scripts.internal._repo_utils import find_repo_root

            repo_root = find_repo_root()
        except Exception:
            repo_root = Path.cwd()

    since = window_start.isoformat()
    until = window_end.isoformat()
    cmd = [
        "git",
        "-C",
        str(repo_root),
        "log",
        f"--since={since}",
        f"--until={until}",
        "--name-only",
        "--pretty=format:%x1f%H%x1f%cI%x1f%s",
    ]
    if grep:
        cmd.insert(4, f"--grep={grep}")
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("git log failed: %s", exc)
        return []
    if out.returncode != 0:
        logger.debug("git log non-zero: %s", out.stderr)
        return []

    commits: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    # Format: each commit starts with \x1f<sha>\x1f<iso-date>\x1f<subject>
    # followed by blank-line-separated file paths.
    for line in out.stdout.splitlines():
        if line.startswith("\x1f"):
            if current is not None:
                commits.append(current)
            parts = line.split("\x1f")
            # parts[0] is empty (leading \x1f); [1]=sha, [2]=date, [3]=subject
            if len(parts) >= 4:
                ts = _parse_iso(parts[2])
                current = {
                    "sha": parts[1],
                    "timestamp": ts if ts is not None else window_start,
                    "summary": parts[3],
                    "paths": [],
                }
            else:
                current = None
        elif line.strip() and current is not None:
            current["paths"].append(line.strip())
    if current is not None:
        commits.append(current)
    return commits


def collect_mechanism_changes(
    window_start: datetime,
    window_end: datetime,
    *,
    repo_root: Path | None = None,
) -> list[MechanismChange]:
    """Return every mechanism-surface-touching commit in the window."""
    commits = _git_log_in_window(window_start, window_end, repo_root=repo_root)
    changes: list[MechanismChange] = []
    for commit in commits:
        surfaces = tuple(
            surface
            for surface in MECHANISM_SURFACES
            if any(p.startswith(surface) or p == surface for p in commit["paths"])
        )
        if not surfaces:
            continue
        is_revert = commit["summary"].startswith("Revert ")
        changes.append(
            MechanismChange(
                commit_sha=commit["sha"],
                summary=commit["summary"],
                timestamp=commit["timestamp"],
                surfaces=surfaces,
                is_revert=is_revert,
            )
        )
    return changes


def classify_mechanism_deltas(
    changes: list[MechanismChange],
    events: list[dict[str, Any]],
    *,
    window_days: int,
) -> list[MechanismDelta]:
    """For each mechanism change compute the before/after retry-rate delta.

    ``window_days`` controls both the before and after windows. A
    "net-positive" change is one where retry rate dropped strictly;
    "net-negative" where it rose strictly; "flat" otherwise.
    """
    deltas: list[MechanismDelta] = []
    for change in changes:
        before_end = change.timestamp
        before_start = before_end - timedelta(days=window_days)
        after_start = before_end
        after_end = after_start + timedelta(days=window_days)
        before_events = window_events(events, before_start, before_end)
        after_events = window_events(events, after_start, after_end)
        before_rate, _ = compute_retry_rate(before_events)
        after_rate, _ = compute_retry_rate(after_events)
        if after_rate < before_rate:
            net = "net-positive"
        elif after_rate > before_rate:
            net = "net-negative"
        else:
            net = "flat"
        deltas.append(
            MechanismDelta(
                change=change,
                before_retry_rate=before_rate,
                after_retry_rate=after_rate,
                net_sign=net,
            )
        )
    return deltas


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def _fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _fmt_delta(before: float, after: float) -> str:
    """Formatted delta with explicit sign."""
    delta = after - before
    if delta > 0:
        return f"+{delta * 100:.2f} pp"
    if delta < 0:
        return f"{delta * 100:.2f} pp"
    return "0.00 pp"


def render_report(
    *,
    run_date: datetime,
    window_start: datetime,
    window_end: datetime,
    prior_start: datetime,
    prior_end: datetime,
    current: WindowMetrics,
    prior: WindowMetrics,
    probes: list[RepeatProbe],
    deltas: list[MechanismDelta],
) -> str:
    """Render the final markdown report."""
    lines: list[str] = []
    lines.append(f"# Improvement Metrics — {run_date.date().isoformat()}")
    lines.append("")
    lines.append(
        f"**Current window:** {window_start.isoformat()} → {window_end.isoformat()}"
    )
    lines.append(
        f"**Prior window:** {prior_start.isoformat()} → {prior_end.isoformat()}"
    )
    lines.append("")

    # Metric delta table.
    lines.append("## Metric deltas (current vs. prior window)")
    lines.append("")
    lines.append("| Metric | Prior | Current | Delta |")
    lines.append("|---|---|---|---|")
    lines.append(
        "| retry_rate | "
        f"{_fmt_pct(prior.retry_rate)} | "
        f"{_fmt_pct(current.retry_rate)} | "
        f"{_fmt_delta(prior.retry_rate, current.retry_rate)} |"
    )
    lines.append(
        "| author_rework_rate | "
        f"{_fmt_pct(prior.author_rework_rate)} | "
        f"{_fmt_pct(current.author_rework_rate)} | "
        f"{_fmt_delta(prior.author_rework_rate, current.author_rework_rate)} |"
    )
    lines.append(
        "| routing_correction_rate | "
        f"{_fmt_pct(prior.routing_correction_rate)} | "
        f"{_fmt_pct(current.routing_correction_rate)} | "
        f"{_fmt_delta(prior.routing_correction_rate, current.routing_correction_rate)} |"
    )
    lines.append(
        "| prompt_policy_rollback_rate (per week) | "
        f"{prior.prompt_policy_rollback_rate:.2f} | "
        f"{current.prompt_policy_rollback_rate:.2f} | "
        f"{current.prompt_policy_rollback_rate - prior.prompt_policy_rollback_rate:+.2f} |"
    )
    lines.append(
        "| skill_promotion_usefulness (avg Δretry) | "
        f"{prior.skill_promotion_usefulness:+.3f} | "
        f"{current.skill_promotion_usefulness:+.3f} | "
        f"{current.skill_promotion_usefulness - prior.skill_promotion_usefulness:+.3f} |"
    )
    lines.append("")

    # Observations — raw counts feeding the rates, for audit.
    lines.append("### Observations (current window)")
    lines.append("")
    if current.observations:
        for k, v in sorted(current.observations.items()):
            lines.append(f"- `{k}` = {v}")
    else:
        lines.append("- _(no observations in window)_")
    lines.append("")

    # Repeat-task probes (shaping §9.2).
    lines.append(f"## Repeat-task probes (≥{REPEAT_PROBE_MIN_OCCURRENCES} occurrences)")
    lines.append("")
    if not probes:
        lines.append(
            "_No task-class signatures recur above the threshold in this window._"
        )
    else:
        for probe in probes:
            lines.append(
                f"- **`{probe.signature}`** — {probe.archetype} × "
                f"{probe.task_type} × {probe.effort}; **{probe.count}** occurrences"
            )
    lines.append("")

    # Mechanism deltas (shaping §9.3).
    lines.append("## Mechanism-change deltas (before vs. after)")
    lines.append("")
    if not deltas:
        lines.append("_No mechanism-surface commits observed in window._")
    else:
        lines.append(
            "| Commit | Surfaces | Before retry_rate | After retry_rate | Net |"
        )
        lines.append("|---|---|---|---|---|")
        for d in deltas:
            surfaces_str = ", ".join(f"`{s.rstrip('/')}`" for s in d.change.surfaces)
            kind = " (revert)" if d.change.is_revert else ""
            lines.append(
                f"| `{d.change.commit_sha[:12]}`{kind} {d.change.summary[:60]} | "
                f"{surfaces_str} | "
                f"{_fmt_pct(d.before_retry_rate)} | "
                f"{_fmt_pct(d.after_retry_rate)} | "
                f"**{d.net_sign}** |"
            )
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "_Generated by `scripts/internal/measure_improvements.py` per "
        "`plans/steward_platform/2_primitive_B/shaping.md` §9._"
    )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Event emission (best-effort)
# ---------------------------------------------------------------------------


def emit_improvement_metrics_event(
    *,
    current: WindowMetrics,
    prior: WindowMetrics,
    output_path: Path,
    events_dir: Path | None = None,
) -> None:
    """Best-effort: emit ``improvement_metrics_computed`` event.

    Primitive A has not registered this event type yet. If the emission
    fails with ``ValueError`` (unknown type), we log a debug note and
    continue — the output markdown is the primary artifact.
    """
    try:
        from bid_euchre.ops.events import append_event
    except Exception as exc:
        logger.debug("append_event not importable: %s", exc)
        return

    payload: dict[str, Any] = {
        "output_path": str(output_path),
        "current_window": {
            "retry_rate": current.retry_rate,
            "author_rework_rate": current.author_rework_rate,
            "routing_correction_rate": current.routing_correction_rate,
            "prompt_policy_rollback_rate": current.prompt_policy_rollback_rate,
            "skill_promotion_usefulness": current.skill_promotion_usefulness,
        },
        "prior_window": {
            "retry_rate": prior.retry_rate,
            "author_rework_rate": prior.author_rework_rate,
            "routing_correction_rate": prior.routing_correction_rate,
            "prompt_policy_rollback_rate": prior.prompt_policy_rollback_rate,
            "skill_promotion_usefulness": prior.skill_promotion_usefulness,
        },
    }
    try:
        append_event(
            "improvement_metrics_computed",
            source="measure_improvements",
            lane_id="ops",
            payload=payload,
            events_dir=events_dir,
        )
    except ValueError:
        # Event type not yet registered — expected during Phase 0.
        logger.debug(
            "improvement_metrics_computed not yet in VALID_EVENT_TYPES; skipping emission"
        )
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("improvement_metrics_computed emission failed: %s", exc)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run(
    *,
    since: datetime | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    events_path: Path | None = None,
    archive_path: Path | None = None,
    output_dir: Path | None = None,
    repo_root: Path | None = None,
    now: datetime | None = None,
    _events: list[dict[str, Any]] | None = None,
    emit_event: bool = True,
) -> Path:
    """Compute metrics + probes + deltas, write the markdown artifact.

    Returns the path of the written artifact.  Accepts ``_events`` as a
    test-only pre-loaded event list (bypasses file reads) and ``now`` as
    a test-only clock override.
    """
    if repo_root is None:
        try:
            from scripts.internal._repo_utils import find_repo_root

            repo_root = find_repo_root()
        except Exception:
            repo_root = Path.cwd()

    current_end = now or datetime.now(timezone.utc)
    current_start = since or (current_end - timedelta(days=window_days))
    prior_end = current_start
    prior_start = prior_end - timedelta(days=window_days)

    if _events is None:
        events = load_events(events_path, archive_path, repo_root=repo_root)
    else:
        events = list(_events)

    current_metrics = compute_window_metrics(
        events, current_start, current_end, repo_root=repo_root
    )
    prior_metrics = compute_window_metrics(
        events, prior_start, prior_end, repo_root=repo_root
    )

    probes = compute_repeat_probes(window_events(events, current_start, current_end))

    changes = collect_mechanism_changes(current_start, current_end, repo_root=repo_root)
    deltas = classify_mechanism_deltas(changes, events, window_days=window_days)

    output_dir = output_dir or (repo_root / DEFAULT_OUTPUT_RELPATH)
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = current_end.date().isoformat()
    output_path = output_dir / f"{date_str}_improvement_metrics.md"

    report = render_report(
        run_date=current_end,
        window_start=current_start,
        window_end=current_end,
        prior_start=prior_start,
        prior_end=prior_end,
        current=current_metrics,
        prior=prior_metrics,
        probes=probes,
        deltas=deltas,
    )
    output_path.write_text(report, encoding="utf-8")

    if emit_event:
        emit_improvement_metrics_event(
            current=current_metrics,
            prior=prior_metrics,
            output_path=output_path,
        )

    return output_path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compute the Primitive B.12 improvement-mechanism metrics "
            "and write the markdown candidate artifact."
        ),
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help=(
            "ISO-8601 timestamp for the start of the current window. "
            "Defaults to (now - --window-days)."
        ),
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=DEFAULT_WINDOW_DAYS,
        help=f"Rolling-window width in days. Default {DEFAULT_WINDOW_DAYS}.",
    )
    parser.add_argument(
        "--events-path",
        type=Path,
        default=None,
        help="Override the live events.jsonl path.",
    )
    parser.add_argument(
        "--archive-path",
        type=Path,
        default=None,
        help="Override the events.archive.jsonl path.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override the output directory (default knowledge/_candidates/).",
    )
    parser.add_argument(
        "--no-event",
        action="store_true",
        help="Skip emission of the improvement_metrics_computed event.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging to stderr.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    since: datetime | None = None
    if args.since is not None:
        parsed = _parse_iso(args.since)
        if parsed is None:
            print(f"invalid --since value: {args.since!r}", file=sys.stderr)
            return 2
        # Treat naive timestamps as UTC.
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        since = parsed

    output_path = run(
        since=since,
        window_days=args.window_days,
        events_path=args.events_path,
        archive_path=args.archive_path,
        output_dir=args.output_dir,
        emit_event=not args.no_event,
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
