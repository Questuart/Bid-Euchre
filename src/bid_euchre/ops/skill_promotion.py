"""Skill-promotion workflow for the steward operator.

Repeated successful multi-step workflows can be proposed as skill
candidates, reviewed by an operator, scanned for context safety,
and promoted into the ``.claude/skills/`` directory with full
provenance.  This is PR-5 rollout/safety scope — not the governed
Platform-11 skill-learning loop.

Lifecycle::

    propose → review (approve/reject) → promote → [disable]

Storage:

- **Candidates:** ``.claude/runtime/skill_candidates/<id>.json``
  (gitignored, runtime-only)
- **Promoted skills:** ``.claude/skills/<name>/SKILL.md``
  (committed, repo-owned)

Integration:

- Context-safety scanning (``context_safety.scan_content``) is
  mandatory at proposal time and again at promotion time.
- Events are emitted to the durable ops event log on promote and
  disable.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from bid_euchre.ops.context_safety import scan_content

logger = logging.getLogger("ops.skill_promotion")

# ── Defaults ────────────────────────────────────────────────────

DEFAULT_CANDIDATES_DIR = Path(".claude/runtime/skill_candidates")
DEFAULT_SKILLS_DIR = Path(".claude/skills")

# Kebab-case: lowercase letters, digits, and hyphens; 2-60 chars.
_NAME_RE = re.compile(r"^[a-z][a-z0-9]+(?:-[a-z0-9]+)*$")
_NAME_MIN_LEN = 2
_NAME_MAX_LEN = 60


# ── Data contracts ──────────────────────────────────────────────


@dataclass
class SkillCandidate:
    """A proposed skill awaiting review and promotion."""

    candidate_id: str
    name: str
    description: str
    content: str
    source_workflow: str
    proposed_by: str
    proposed_at: str
    provenance: dict[str, Any]
    status: Literal["pending", "approved", "rejected", "promoted"] = "pending"
    review_notes: str | None = None
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    safety_scan_hash: str | None = None
    safety_scan_outcome: Literal["allow", "warn", "reject"] | None = None
    safety_scan_findings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillCandidate:
        """Deserialise from a JSON-compatible dict."""
        # Strip unknown keys for forward compat
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known})


# ── Validation helpers ──────────────────────────────────────────


def _validate_candidate_id(candidate_id: str) -> None:
    """Validate *candidate_id* is a well-formed UUID to prevent path traversal.

    Raises:
        ValueError: If the string is not a valid UUID.
    """
    try:
        uuid.UUID(candidate_id)
    except (ValueError, AttributeError):
        raise ValueError(
            f"Invalid candidate ID '{candidate_id}': must be a valid UUID."
        )


def validate_skill_name(name: str) -> list[str]:
    """Return a list of validation errors for *name* (empty if valid)."""
    errors: list[str] = []
    if not name:
        errors.append("Skill name must not be empty.")
        return errors
    if len(name) < _NAME_MIN_LEN:
        errors.append(f"Skill name must be at least {_NAME_MIN_LEN} characters.")
    if len(name) > _NAME_MAX_LEN:
        errors.append(f"Skill name must be at most {_NAME_MAX_LEN} characters.")
    if not _NAME_RE.match(name):
        errors.append(
            "Skill name must be kebab-case (lowercase letters, digits, hyphens; "
            "must start with a letter and not end with a hyphen)."
        )
    return errors


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_candidate(path: Path) -> SkillCandidate:
    """Load a single candidate from JSON."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return SkillCandidate.from_dict(data)


def _save_candidate(candidate: SkillCandidate, candidates_dir: Path) -> Path:
    """Persist a candidate to disk atomically (temp + rename)."""
    candidates_dir.mkdir(parents=True, exist_ok=True)
    path = candidates_dir / f"{candidate.candidate_id}.json"
    content = json.dumps(candidate.to_dict(), indent=2, ensure_ascii=False) + "\n"

    # Atomic write: write to temp file, fsync, then rename
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(candidates_dir), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(path))
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise
    return path


# ── Core workflow ───────────────────────────────────────────────


def propose_skill(
    *,
    name: str,
    description: str,
    content: str,
    source_workflow: str,
    proposed_by: str,
    provenance: dict[str, Any] | None = None,
    candidates_dir: Path | None = None,
) -> SkillCandidate:
    """Create a new skill candidate and run context-safety scanning.

    The candidate is always persisted (even if the scan rejects it)
    so the operator can inspect the reason and revise the content.

    Raises:
        ValueError: If the skill name or other required fields are invalid.
    """
    # Validate name
    name_errors = validate_skill_name(name)
    if name_errors:
        raise ValueError(f"Invalid skill name '{name}': {'; '.join(name_errors)}")

    if not description.strip():
        raise ValueError("Skill description must not be empty.")

    if not content.strip():
        raise ValueError("Skill content must not be empty.")

    if not source_workflow.strip():
        raise ValueError("Source workflow must not be empty.")

    if not proposed_by.strip():
        raise ValueError("proposed_by must not be empty.")

    cdir = candidates_dir or DEFAULT_CANDIDATES_DIR

    # Run context-safety scan
    scan_result = scan_content(
        content,
        metadata={
            "source_file": f"skill_candidate:{name}",
            "added_by": proposed_by,
        },
    )

    candidate = SkillCandidate(
        candidate_id=str(uuid.uuid4()),
        name=name,
        description=description,
        content=content,
        source_workflow=source_workflow,
        proposed_by=proposed_by,
        proposed_at=_now_iso(),
        provenance=provenance or {},
        status="pending",
        safety_scan_hash=scan_result.content_hash,
        safety_scan_outcome=scan_result.outcome,
        safety_scan_findings=[f.to_dict() for f in scan_result.findings],
    )

    _save_candidate(candidate, cdir)
    logger.info(
        "Proposed skill '%s' (id=%s, safety=%s)",
        name,
        candidate.candidate_id,
        scan_result.outcome,
    )

    return candidate


def review_skill(
    candidate_id: str,
    *,
    approve: bool,
    reviewed_by: str,
    review_notes: str = "",
    candidates_dir: Path | None = None,
) -> SkillCandidate:
    """Approve or reject a pending skill candidate.

    Raises:
        FileNotFoundError: If the candidate does not exist.
        ValueError: If the candidate is not in a reviewable state, or
            the candidate_id is not a valid UUID.
    """
    _validate_candidate_id(candidate_id)
    cdir = candidates_dir or DEFAULT_CANDIDATES_DIR
    path = cdir / f"{candidate_id}.json"

    if not path.exists():
        raise FileNotFoundError(f"Candidate '{candidate_id}' not found.")

    candidate = _load_candidate(path)

    if candidate.status not in ("pending",):
        raise ValueError(
            f"Candidate '{candidate_id}' is '{candidate.status}', "
            f"not 'pending'. Only pending candidates can be reviewed."
        )

    if not reviewed_by.strip():
        raise ValueError("reviewed_by must not be empty.")

    candidate.status = "approved" if approve else "rejected"
    candidate.reviewed_by = reviewed_by
    candidate.reviewed_at = _now_iso()
    candidate.review_notes = review_notes or None

    _save_candidate(candidate, cdir)
    logger.info(
        "Reviewed skill '%s' (id=%s) → %s by %s",
        candidate.name,
        candidate_id,
        candidate.status,
        reviewed_by,
    )

    return candidate


def promote_skill(
    candidate_id: str,
    *,
    candidates_dir: Path | None = None,
    skills_dir: Path | None = None,
    events_dir: Path | None = None,
) -> tuple[SkillCandidate, Path]:
    """Promote an approved candidate to ``.claude/skills/<name>/SKILL.md``.

    Re-runs context-safety scanning as defense in depth.

    Returns:
        Tuple of (updated candidate, path to SKILL.md).

    Raises:
        FileNotFoundError: If the candidate does not exist.
        ValueError: If the candidate is not approved, or the safety scan
            rejects the content, or a skill with that name already exists,
            or the candidate_id is not a valid UUID.
    """
    _validate_candidate_id(candidate_id)
    cdir = candidates_dir or DEFAULT_CANDIDATES_DIR
    sdir = skills_dir or DEFAULT_SKILLS_DIR

    path = cdir / f"{candidate_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Candidate '{candidate_id}' not found.")

    candidate = _load_candidate(path)

    # Re-validate name after loading from disk (defense against tampered JSON)
    name_errors = validate_skill_name(candidate.name)
    if name_errors:
        raise ValueError(
            f"Candidate '{candidate_id}' has invalid skill name "
            f"'{candidate.name}': {'; '.join(name_errors)}"
        )

    if candidate.status != "approved":
        raise ValueError(
            f"Candidate '{candidate_id}' is '{candidate.status}', "
            f"not 'approved'. Only approved candidates can be promoted."
        )

    # Check for name collision with existing skills
    skill_dir = sdir / candidate.name
    if skill_dir.exists():
        raise ValueError(
            f"Skill directory '{skill_dir}' already exists. "
            f"Choose a different name or disable the existing skill first."
        )

    # Re-scan at promotion time (defense in depth)
    scan_result = scan_content(
        candidate.content,
        metadata={
            "source_file": f"skill_promotion:{candidate.name}",
            "added_by": candidate.proposed_by,
        },
    )
    candidate.safety_scan_hash = scan_result.content_hash
    candidate.safety_scan_outcome = scan_result.outcome
    candidate.safety_scan_findings = [f.to_dict() for f in scan_result.findings]

    if scan_result.outcome == "reject":
        # Save updated scan info but don't promote
        _save_candidate(candidate, cdir)
        findings_summary = "; ".join(f.message for f in scan_result.findings)
        raise ValueError(
            f"Context-safety scan rejected content at promotion time: "
            f"{findings_summary}"
        )

    # Write the skill atomically (temp + fsync + rename)
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_content = _render_skill_md(candidate)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(skill_dir), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(skill_content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(skill_md))
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise

    # Update candidate status
    candidate.status = "promoted"
    _save_candidate(candidate, cdir)

    # Emit event
    _emit_event(
        "skill_promoted",
        candidate,
        events_dir=events_dir,
    )

    logger.info(
        "Promoted skill '%s' (id=%s) → %s",
        candidate.name,
        candidate.candidate_id,
        skill_md,
    )

    return candidate, skill_md


def disable_skill(
    name: str,
    *,
    reason: str = "",
    disabled_by: str = "operator",
    skills_dir: Path | None = None,
    events_dir: Path | None = None,
) -> Path:
    """Disable a promoted skill by renaming SKILL.md to SKILL.md.disabled.

    Does NOT delete the candidate record — provenance is retained.

    Returns:
        Path to the disabled file.

    Raises:
        FileNotFoundError: If the skill directory or SKILL.md does not exist.
    """
    # Validate name to prevent path traversal
    name_errors = validate_skill_name(name)
    if name_errors:
        raise ValueError(f"Invalid skill name '{name}': {'; '.join(name_errors)}")

    sdir = skills_dir or DEFAULT_SKILLS_DIR
    skill_md = sdir / name / "SKILL.md"

    if not skill_md.exists():
        raise FileNotFoundError(f"Skill '{name}' not found at {skill_md}.")

    disabled_path = skill_md.with_suffix(".md.disabled")
    skill_md.rename(disabled_path)

    # Emit event
    _emit_disable_event(name, reason, disabled_by, events_dir=events_dir)

    logger.info("Disabled skill '%s' → %s", name, disabled_path)

    return disabled_path


def list_candidates(
    *,
    status_filter: str | None = None,
    candidates_dir: Path | None = None,
) -> list[SkillCandidate]:
    """List all skill candidates, optionally filtered by status.

    Args:
        status_filter: If given, only return candidates with this status.
        candidates_dir: Override for candidates directory.

    Returns:
        List of candidates sorted by proposed_at (newest first).
    """
    cdir = candidates_dir or DEFAULT_CANDIDATES_DIR
    if not cdir.exists():
        return []

    candidates = []
    for p in cdir.glob("*.json"):
        try:
            candidates.append(_load_candidate(p))
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.warning("Skipping malformed candidate file: %s", p)
            continue

    if status_filter:
        candidates = [c for c in candidates if c.status == status_filter]

    # Sort newest first
    candidates.sort(key=lambda c: c.proposed_at, reverse=True)
    return candidates


def get_candidate(
    candidate_id: str,
    *,
    candidates_dir: Path | None = None,
) -> SkillCandidate:
    """Load a single candidate by ID.

    Raises:
        FileNotFoundError: If the candidate does not exist.
        ValueError: If the candidate_id is not a valid UUID.
    """
    _validate_candidate_id(candidate_id)
    cdir = candidates_dir or DEFAULT_CANDIDATES_DIR
    path = cdir / f"{candidate_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Candidate '{candidate_id}' not found.")
    return _load_candidate(path)


# ── Rendering ───────────────────────────────────────────────────


def _sanitize_comment(value: object) -> str:
    """Strip HTML comment close sequences to prevent injection.

    Handles both standard ``-->`` and HTML5 ``--!>`` terminators.
    """
    if value is None:
        return "None"
    return str(value).replace("--!>", "--! >").replace("-->", "-- >")


def _render_skill_md(candidate: SkillCandidate) -> str:
    """Render a SKILL.md file from a candidate."""
    # YAML front matter matching existing skill conventions
    provenance_lines = []
    for key, val in sorted(candidate.provenance.items()):
        safe_key = _sanitize_comment(key)
        if isinstance(val, list):
            safe_vals = ", ".join(_sanitize_comment(v) for v in val)
            provenance_lines.append(f"#   {safe_key}: {safe_vals}")
        else:
            provenance_lines.append(f"#   {safe_key}: {_sanitize_comment(val)}")

    provenance_block = "\n".join(provenance_lines)

    # Escape YAML-significant characters in quoted scalar values.
    # Newlines would break out of the quoted scalar and allow injection
    # of extra front-matter keys; backslashes need escaping first.
    safe_desc = (
        candidate.description.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )

    return (
        (
            f"---\n"
            f'name: "{candidate.name}"\n'
            f'description: "{safe_desc}"\n'
            f"---\n"
            f"\n"
            f"<!-- Promoted by skill-promotion workflow -->\n"
            f"<!-- candidate_id: {_sanitize_comment(candidate.candidate_id)} -->\n"
            f"<!-- proposed_by: {_sanitize_comment(candidate.proposed_by)} -->\n"
            f"<!-- proposed_at: {_sanitize_comment(candidate.proposed_at)} -->\n"
            f"<!-- reviewed_by: {_sanitize_comment(candidate.reviewed_by)} -->\n"
            f"<!-- reviewed_at: {_sanitize_comment(candidate.reviewed_at)} -->\n"
            f"<!-- source_workflow: {_sanitize_comment(candidate.source_workflow)} -->\n"
            f"<!-- safety_scan_outcome: {_sanitize_comment(candidate.safety_scan_outcome)} -->\n"
        )
        + (
            f"<!-- provenance:\n{provenance_block}\n-->\n\n"
            if provenance_lines
            else "\n"
        )
        + candidate.content
        + ("\n" if not candidate.content.endswith("\n") else "")
    )


# ── Event helpers ───────────────────────────────────────────────


def _emit_event(
    event_type: str,
    candidate: SkillCandidate,
    *,
    events_dir: Path | None = None,
) -> None:
    """Emit a skill event to the ops event log (best-effort)."""
    try:
        from bid_euchre.ops.events import append_event

        append_event(
            event_type=event_type,
            source="ops.skill_promotion",
            lane_id=candidate.proposed_by,
            payload={
                "candidate_id": candidate.candidate_id,
                "skill_name": candidate.name,
                "safety_outcome": candidate.safety_scan_outcome,
            },
            events_dir=events_dir,
        )
    except Exception:
        logger.debug("Failed to emit %s event (non-fatal)", event_type, exc_info=True)


def _emit_disable_event(
    name: str,
    reason: str,
    disabled_by: str,
    *,
    events_dir: Path | None = None,
) -> None:
    """Emit a skill-disabled event (best-effort)."""
    try:
        from bid_euchre.ops.events import append_event

        append_event(
            event_type="skill_disabled",
            source="ops.skill_promotion",
            lane_id=disabled_by,
            payload={
                "skill_name": name,
                "reason": reason,
            },
            events_dir=events_dir,
        )
    except Exception:
        logger.debug("Failed to emit skill_disabled event (non-fatal)", exc_info=True)


# ── Formatting ──────────────────────────────────────────────────


def format_candidates_text(candidates: list[SkillCandidate]) -> str:
    """Format a list of candidates as human-readable text."""
    if not candidates:
        return "No skill candidates found."

    lines = [f"Skill candidates ({len(candidates)} total):\n"]
    for c in candidates:
        safety = f"safety={c.safety_scan_outcome}" if c.safety_scan_outcome else ""
        reviewer = f"by {c.reviewed_by}" if c.reviewed_by else ""
        lines.append(
            f"  [{c.status.upper():>9s}] {c.name} — {c.description}\n"
            f"             id={c.candidate_id[:8]}… {safety} {reviewer}\n"
            f"             proposed by {c.proposed_by} at {c.proposed_at}\n"
        )
    return "\n".join(lines)


def format_candidates_json(candidates: list[SkillCandidate]) -> list[dict[str, Any]]:
    """Format a list of candidates as JSON-serialisable dicts."""
    return [c.to_dict() for c in candidates]
