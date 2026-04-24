"""Event taxonomy helpers (Primitive A).

Per shaping §3.6-§3.7 (ADR 007 adopted pattern):

- :func:`categorize_error` — stable taxonomy for mapping a free-form
  error string to one of five buckets. Used by
  ``post_tool_use_failure.error_category``,
  ``stop_failure.failure_category``, ``task_completed.outcome`` (when
  outcome=failed), and incident-fingerprint generation.

- :func:`build_status_message` — one-line human-readable summary for
  ``notification`` events, the ``triaging-issues`` skill, the
  dashboard's recent-events panel, and archivist candidate-lesson
  templating.

- :func:`incident_fingerprint` — deterministic hash of the incident
  signature, used by the ``triaging-issues`` skill to dedupe repeat
  incidents across time. Null/empty inputs produce ``None``.

These helpers are pure: no I/O, no environment reads, no side effects.
Callers in ``events.emit`` and downstream consumers receive pure string
outputs, which keeps the taxonomy testable in isolation.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

# ---------------------------------------------------------------------------
# Category taxonomy (shaping §3.6)
# ---------------------------------------------------------------------------

#: Canonical error-category labels. Order reflects triage priority:
#: interrupted (user-initiated) first, then timeout / permission denial /
#: execution error, with ``other`` as the catch-all.
ERROR_CATEGORIES: tuple[str, ...] = (
    "interrupted",
    "timeout",
    "permission_denied",
    "execution_error",
    "other",
)

#: Regex patterns → category. Evaluated in order; first match wins.
#: Patterns intentionally broad to align with steward's existing
#: ``triaging-issues`` taxonomy (see `.claude/rules/` for the review
#: side; taxonomy is load-bearing across both).
_CATEGORY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\b(?:keyboard ?interrupt|sigint|user ?cancel|aborted by user|ctrl[- ]?c)\b",
            re.I,
        ),
        "interrupted",
    ),
    (
        re.compile(
            r"\b(?:timeout|timed?[- ]?out|deadline exceeded|operation took too long)\b",
            re.I,
        ),
        "timeout",
    ),
    (
        re.compile(
            r"\b(?:permission ?denied|not ?permitted|not ?authorized|unauthorized|"
            r"forbidden|access ?denied|eacces|eperm|permissiondenied)\b",
            re.I,
        ),
        "permission_denied",
    ),
    (
        re.compile(
            r"\b(?:traceback|exception|error|failed|failure|exited with|"
            r"exit ?code|non[- ]?zero|oserror|ioerror|runtimeerror|valueerror)\b",
            re.I,
        ),
        "execution_error",
    ),
)


def categorize_error(error_str: str | None) -> str:
    """Return one of ``ERROR_CATEGORIES`` for a free-form error string.

    Per shaping §3.6: bucket free-form errors into a stable taxonomy so
    downstream consumers (incident fingerprinting, dashboard, triage)
    have a small closed vocabulary to join on.

    Args:
        error_str: Free-form error message (stderr, exception repr,
            log line). ``None`` or empty → ``"other"``.

    Returns:
        One of ``interrupted | timeout | permission_denied |
        execution_error | other``.

    Examples:
        >>> categorize_error("KeyboardInterrupt")
        'interrupted'
        >>> categorize_error("Operation timed out after 30s")
        'timeout'
        >>> categorize_error("Permission denied: /etc/passwd")
        'permission_denied'
        >>> categorize_error("Traceback ... ValueError: x")
        'execution_error'
        >>> categorize_error("")
        'other'
    """
    if not error_str:
        return "other"
    for pattern, category in _CATEGORY_PATTERNS:
        if pattern.search(error_str):
            return category
    return "other"


# Internal alias for shaping §3.6 exact-name parity with the ADR 007
# reference plugin. External callers should use the public
# ``categorize_error``; internal modules (``events.py``) may call either.
_categorize_error = categorize_error


# ---------------------------------------------------------------------------
# Status message pattern (shaping §3.7)
# ---------------------------------------------------------------------------

# Event types routed through specialized formatters. Any type not listed
# falls through to ``_generic_status_message``.
_STATUS_FORMATTERS: dict[str, Any] = {}


def _register(event_type: str):
    def decorator(func):
        _STATUS_FORMATTERS[event_type] = func
        return func

    return decorator


def _short(value: Any, limit: int = 80) -> str:
    """Clamp a value to ``limit`` chars with ellipsis, as a string."""
    s = str(value)
    if len(s) <= limit:
        return s
    return s[: limit - 1] + "…"


@_register("task_started")
def _fmt_task_started(rec: dict) -> str:
    pid = _short(rec.get("packet_id") or rec.get("task_id") or "?")
    title = _short(rec.get("title", "(untitled)"))
    by = rec.get("dispatched_by") or "orchestrator"
    return f"Task {pid} started by {by}: {title}"


@_register("task_completed")
def _fmt_task_completed(rec: dict) -> str:
    pid = _short(rec.get("packet_id") or rec.get("task_id") or "?")
    outcome = rec.get("outcome", "unknown")
    pr_number = rec.get("pr_number")
    if pr_number:
        return f"Task {pid} {outcome} (PR #{pr_number})"
    return f"Task {pid} {outcome}"


@_register("post_tool_use_failure")
def _fmt_post_tool_use_failure(rec: dict) -> str:
    tool = rec.get("tool_name", "?")
    cat = rec.get("error_category", "other")
    return f"Tool failed: {tool} ({cat})"


@_register("stop_failure")
def _fmt_stop_failure(rec: dict) -> str:
    cat = rec.get("failure_category", "other")
    return f"Session stop failed: {cat}"


@_register("canary_run_complete")
def _fmt_canary_run_complete(rec: dict) -> str:
    run_id = _short(rec.get("canary_run_id", "?"))
    passed = rec.get("scenarios_passed", 0)
    total = rec.get("scenarios_total", 0)
    return f"Canary run {run_id} complete: {passed}/{total} scenarios passed"


@_register("canary_run_fail")
def _fmt_canary_run_fail(rec: dict) -> str:
    run_id = _short(rec.get("canary_run_id", "?"))
    failed = rec.get("scenarios_failed", "?")
    return f"Canary run {run_id} FAILED: {failed} scenarios failed"


@_register("notification")
def _fmt_notification(rec: dict) -> str:
    severity = rec.get("severity", "info")
    msg = _short(rec.get("message", ""), limit=120)
    return f"[{severity}] {msg}"


@_register("promotion_start")
def _fmt_promotion_start(rec: dict) -> str:
    surface = _short(rec.get("surface_id") or rec.get("target", "?"))
    return f"Promotion started: {surface}"


@_register("promotion_complete")
def _fmt_promotion_complete(rec: dict) -> str:
    surface = _short(rec.get("surface_id") or rec.get("target", "?"))
    return f"Promotion complete: {surface}"


@_register("rollback_triggered")
def _fmt_rollback_triggered(rec: dict) -> str:
    surface = _short(rec.get("surface_id") or rec.get("target", "?"))
    reason = _short(rec.get("reason", "unspecified"))
    return f"Rollback triggered on {surface}: {reason}"


def _generic_status_message(rec: dict) -> str:
    """Fallback formatter for event types without a specialized message."""
    et = rec.get("event_type", "event")
    lane = rec.get("lane_id", "?")
    return f"{et} ({lane})"


def build_status_message(event_record: dict) -> str:
    """Return a one-line human-readable summary of an event record.

    Per shaping §3.7: centralizes event-to-human translation in one
    function so the notification body, triaging-issues title, dashboard
    recent-events panel, and archivist candidate-lesson template all
    stay in sync.

    Args:
        event_record: Event dict with at least ``event_type``.

    Returns:
        A single-line summary (no embedded newlines).
    """
    event_type = event_record.get("event_type")
    formatter = _STATUS_FORMATTERS.get(event_type) if event_type else None
    try:
        if formatter is not None:
            msg = formatter(event_record)
        else:
            msg = _generic_status_message(event_record)
    except Exception:  # pragma: no cover — defensive; never-raises
        msg = _generic_status_message(event_record)
    # Strip embedded newlines defensively.
    return msg.replace("\n", " ").strip()


# Internal alias for shaping §3.7 exact-name parity with the ADR 007
# reference plugin.
_build_status_message = build_status_message


# ---------------------------------------------------------------------------
# Incident fingerprint (§9.7 first-class ID)
# ---------------------------------------------------------------------------


def _normalize_for_fingerprint(value: Any) -> str:
    """Normalize a fingerprint input: trim, collapse whitespace, drop paths."""
    s = str(value).strip()
    # Collapse runs of whitespace to single spaces.
    s = re.sub(r"\s+", " ", s)
    # Drop absolute paths up to the last path component to improve
    # dedup stability across workers / worktrees (e.g., temp dirs).
    s = re.sub(r"/[^\s:]+/", "/…/", s)
    return s


def incident_fingerprint(
    *,
    event_type: str | None = None,
    error_category: str | None = None,
    signature: str | None = None,
    **extra: Any,
) -> str | None:
    """Return a deterministic fingerprint for an incident, or ``None``.

    Fingerprints are used by the ``triaging-issues`` skill to dedupe
    repeat incidents across time. Two incidents with the same
    ``(event_type, error_category, normalized signature)`` tuple produce
    the same fingerprint.

    Args:
        event_type: The emitting event type (e.g., ``stop_failure``).
        error_category: A category label from :data:`ERROR_CATEGORIES`.
        signature: The stable incident signature (e.g., the first line
            of a traceback, the command that failed, the failing
            assertion). Leading / trailing whitespace is stripped and
            run-of-whitespace collapsed before hashing.
        **extra: Additional stable tokens to include in the hash
            (e.g., ``tool_name=...``). Order-independent.

    Returns:
        A 16-character hex fingerprint, or ``None`` if all three
        principal inputs are absent/empty (no incident to fingerprint).

    Examples:
        >>> fp1 = incident_fingerprint(
        ...     event_type="stop_failure",
        ...     error_category="timeout",
        ...     signature="Operation timed out after 30s",
        ... )
        >>> fp2 = incident_fingerprint(
        ...     event_type="stop_failure",
        ...     error_category="timeout",
        ...     signature="  Operation   timed out after 30s  ",
        ... )
        >>> fp1 == fp2
        True
        >>> incident_fingerprint() is None
        True
    """
    if not any((event_type, error_category, signature)) and not extra:
        return None
    parts = [
        ("event_type", event_type or ""),
        ("error_category", error_category or ""),
        ("signature", _normalize_for_fingerprint(signature) if signature else ""),
    ]
    for key in sorted(extra.keys()):
        parts.append((key, _normalize_for_fingerprint(extra[key])))
    token = "|".join(f"{k}={v}" for k, v in parts)
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return digest[:16]
