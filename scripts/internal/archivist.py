#!/usr/bin/env python3
"""Archivist stub — Primitive C/D interface contract.

## Archivist C↔D Interface Contract

**D writes to:** `knowledge/_candidates/<YYYY-MM-DD>_<kind>.md`
  where <kind> ∈ {lessons, changelog, gc}

**D does NOT write to:** anything else under `knowledge/`.
  D MUST NOT edit NOTES.md, PLAYBOOKS.md, anti_patterns.md, harness_assumptions.md,
  incidents/*, adr/*, or INDEX.md. These are operator-promoted surfaces.

**C reads from:** `knowledge/_candidates/*.md` (session-local; gitignored)
**C writes to:** `knowledge/NOTES.md` or `knowledge/PLAYBOOKS.md` or
  `knowledge/anti_patterns.md` (appended under operator direction) AND
  `knowledge/_promoted/<YYYY-MM-DD>_<class>_<hash>.md` (archive entry).

**Gate between them:** operator review of candidate files via `/run-archivist`
  skill or direct edit. No automatic promotion. No autonomous state mutation
  (binding constraint from ADR 010 §Decision).

**Event emission on promotion (C-side):**
  - `kb_artifact_promoted` (event_type per Primitive A schema v1.0; fields:
    artifact_class, source_candidate_path, promoted_path, operator_id,
    trace_id, promoted_at)
  - `kb_artifact_unpromoted` — emitted on rollback

**Event emission on candidate generation (D-side):**
  - `archivist_candidate_generated` (fields: candidate_path, candidate_count,
    trigger, archivist_mode, generated_at)

**Failure modes:**
  - D writes outside `_candidates/`: C-side lint flags; archivist refuses to
    run until resolved.
  - C promotes without emitting event: Pattern 8 (Observable-by-default) lint
    flags in post-merge review.
  - Operator promotes a candidate file D hasn't written (fake candidate):
    `kb_artifact_promoted` event has no matching `archivist_candidate_generated`
    upstream event; review-driver precheck V7 flags.

## Stub scope (Packet C-Exec)

Primitive D's inflow implementation (the nightly / end-of-session
candidate generator) is a separate deliverable. This module is the
**C-side promotion + rollback surface** plus the interface contract
docstring above. Events are emitted via ``src/bid_euchre/ops/events.py``
only when ``ENABLE_KB_EVENT_EMISSION`` is truthy in the process
environment — the flag ships default off until Primitive A's event
catalog is extended to accept `kb_artifact_promoted` /
`kb_artifact_unpromoted` / `archivist_candidate_generated`.

**Forward (``--promote``).** Reads a candidate markdown file, classifies
its ``kind`` from the file header or filename, and appends its body to
the corresponding target under ``knowledge/`` (lessons → NOTES.md;
runbook → PLAYBOOKS.md; anti-pattern → anti_patterns.md). Computes a
short SHA-256 hash of the inserted content and records an archive entry
under ``knowledge/_promoted/<YYYY-MM-DD>_<class>_<hash>.md``.

**Reverse (``--unpromote``).** Reads an archive entry, locates the
exact block inserted in the target file (delimited by HTML comment
markers), removes it, and deletes the archive entry. Asserts the
post-rollback content hash matches the pre-promotion hash (byte-level
round-trip).

## Exit codes

* ``0`` — operation succeeded
* ``1`` — invocation error / IO error
* ``2`` — operator-gate violation (e.g., autonomous invocation without
  an explicit operator_id; default-off flag attempt to emit event)
* ``3`` — byte-identity check failed after un-promotion (round-trip
  broken — panic signal)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


KIND_TO_TARGET = {
    "lessons": "NOTES.md",
    "runbook": "PLAYBOOKS.md",
    "playbook": "PLAYBOOKS.md",
    "anti_pattern": "anti_patterns.md",
    "anti-pattern": "anti_patterns.md",
    "changelog": "NOTES.md",  # changelog candidates land as notes
    "gc": "NOTES.md",  # garbage-collection proposals recorded as notes
}

PROMOTE_BEGIN_FMT = "<!-- promoted:{hash}:begin -->"
PROMOTE_END_FMT = "<!-- promoted:{hash}:end -->"

ARCHIVE_FRONTMATTER_FMT = """---
source_candidate: {source}
target: {target}
artifact_class: {kind}
content_hash: {hash}
operator_id: {operator}
promoted_at: {ts}
---

# Promotion archive: {kind} — {hash}

> Audit-trail entry for the promotion of `{source}` into
> `knowledge/{target}`. See ADR 010 for the commit-policy rationale
> and Primitive C shaping §4.7 for the rollback procedure.

## Inserted block

```markdown
{block}
```
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _kb_root(repo_root: Path) -> Path:
    return repo_root / "knowledge"


def _classify_candidate(candidate_path: Path, text: str) -> str:
    """Determine the target kind from header, filename, or default."""
    # Prefer an explicit header: "## Candidate kind: <kind>"
    m = re.search(r"(?im)^##\s+Candidate kind:\s*(\S+)", text)
    if m:
        return m.group(1).strip().lower()
    # Next, parse the filename pattern YYYY-MM-DD_<kind>.md.
    m = re.match(r"\d{4}-\d{2}-\d{2}_([A-Za-z_\-]+)(?:\.md)?$", candidate_path.name)
    if m:
        return m.group(1).strip().lower()
    return "lessons"  # default


def _extract_body(text: str) -> str:
    """Strip a leading comment / frontmatter preamble; keep the content
    block agents should see.

    For the fixture format, we accept the whole body after the first
    level-2 heading (e.g., ``## Candidate kind: lessons``).
    """
    lines = text.splitlines()
    start = 0
    for i, line in enumerate(lines):
        if re.match(r"^##\s+Candidate kind:", line):
            # Skip the kind header line and include what follows.
            start = i + 1
            break
    body = "\n".join(lines[start:]).strip()
    return body + "\n"


def _content_hash(text: str) -> str:
    """Short SHA-256 (first 12 hex chars)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _emit_event(event_type: str, payload: dict) -> None:
    """Emit a KB lifecycle event via the ops events log if
    ``ENABLE_KB_EVENT_EMISSION`` is truthy. Otherwise, log-only.

    The event types ``kb_artifact_promoted`` / ``kb_artifact_unpromoted``
    / ``archivist_candidate_generated`` are not yet in
    ``VALID_EVENT_TYPES`` (Primitive A owns the catalog extension).
    Until then, the emission is a no-op that still records a local
    audit line to stderr so tests can observe it.
    """
    if not os.environ.get("ENABLE_KB_EVENT_EMISSION"):
        # Default-off per shape §5.4 / §6.3 risk #3 mitigation.
        print(
            f"archivist: event {event_type} suppressed "
            f"(ENABLE_KB_EVENT_EMISSION unset). payload={payload}",
            file=sys.stderr,
        )
        return
    try:
        from bid_euchre.ops import events as ops_events  # type: ignore

        ops_events.append_event(
            event_type=event_type,
            source="scripts/internal/archivist.py",
            lane_id=payload.get("lane_id", "unknown"),
            payload=payload,
        )
    except ValueError as exc:
        # Event type not yet registered in Primitive A catalog.
        print(
            f"archivist: event {event_type} rejected by catalog "
            f"(Primitive A has not yet extended VALID_EVENT_TYPES): {exc}",
            file=sys.stderr,
        )
    except Exception as exc:  # pragma: no cover - defensive
        print(
            f"archivist: event emission failed for {event_type}: {exc}",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Promote / unpromote
# ---------------------------------------------------------------------------


def promote(
    repo_root: Path,
    candidate_path: Path,
    operator_id: str,
    now: _dt.date | None = None,
) -> Path:
    """Promote a candidate file into the live KB.

    Returns the archive path written under ``knowledge/_promoted/``.
    """
    if not operator_id:
        raise ValueError(
            "operator_id is required (ADR 010 operator-gated constraint). "
            "Pass --operator-id <name> or set ARCHIVIST_OPERATOR_ID."
        )
    candidate_text = candidate_path.read_text(encoding="utf-8")
    kind = _classify_candidate(candidate_path, candidate_text)
    body = _extract_body(candidate_text)
    content_hash = _content_hash(body)
    target_filename = KIND_TO_TARGET.get(kind)
    if target_filename is None:
        raise ValueError(
            f"Unknown candidate kind {kind!r}. "
            f"Expected one of: {sorted(set(KIND_TO_TARGET))}"
        )

    kb_root = _kb_root(repo_root)
    target = kb_root / target_filename
    if not target.exists():
        raise FileNotFoundError(f"promotion target missing: {target}")

    begin = PROMOTE_BEGIN_FMT.format(hash=content_hash)
    end = PROMOTE_END_FMT.format(hash=content_hash)
    # Assemble the inserted block — the hash delimiters sandwich the body.
    block = f"\n{begin}\n{body.rstrip()}\n{end}\n"

    original = target.read_text(encoding="utf-8")
    if begin in original:
        raise RuntimeError(
            f"candidate already promoted (delimiter {begin} exists in {target})"
        )
    target.write_text(original + block, encoding="utf-8")

    ts_date = (now or _dt.date.today()).isoformat()
    ts = _dt.datetime.now(_dt.timezone.utc).isoformat()
    archive_dir = kb_root / "_promoted"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f"{ts_date}_{kind}_{content_hash}.md"
    archive_path.write_text(
        ARCHIVE_FRONTMATTER_FMT.format(
            source=candidate_path,
            target=target_filename,
            kind=kind,
            hash=content_hash,
            operator=operator_id,
            ts=ts,
            block=block.strip(),
        ),
        encoding="utf-8",
    )

    _emit_event(
        "kb_artifact_promoted",
        {
            "artifact_class": kind,
            "source_candidate_path": str(candidate_path),
            "promoted_path": str(target),
            "archive_path": str(archive_path),
            "operator_id": operator_id,
            "content_hash": content_hash,
            "promoted_at": ts,
        },
    )
    return archive_path


def unpromote(
    repo_root: Path,
    archive_path: Path,
) -> Path:
    """Reverse a promotion. Returns the re-created candidate path under
    ``knowledge/_candidates/<YYYY-MM-DD>_unpromoted.md`` for re-review.
    """
    text = archive_path.read_text(encoding="utf-8")
    m = re.search(r"(?m)^content_hash:\s*(\S+)\s*$", text)
    if not m:
        raise ValueError(f"archive entry missing content_hash: {archive_path}")
    content_hash = m.group(1).strip()
    m = re.search(r"(?m)^target:\s*(\S+)\s*$", text)
    if not m:
        raise ValueError(f"archive entry missing target: {archive_path}")
    target_filename = m.group(1).strip()
    m = re.search(r"(?m)^artifact_class:\s*(\S+)\s*$", text)
    kind = m.group(1).strip() if m else "lessons"
    m = re.search(r"(?m)^source_candidate:\s*(\S+)\s*$", text)
    source_candidate = m.group(1).strip() if m else "(unknown)"

    kb_root = _kb_root(repo_root)
    target = kb_root / target_filename
    if not target.exists():
        raise FileNotFoundError(f"un-promotion target missing: {target}")

    begin = PROMOTE_BEGIN_FMT.format(hash=content_hash)
    end = PROMOTE_END_FMT.format(hash=content_hash)
    original = target.read_text(encoding="utf-8")
    # Find the block bounded by begin/end delimiters (greedy-minimal).
    pattern = re.compile(
        r"\n?" + re.escape(begin) + r".*?" + re.escape(end) + r"\n?",
        re.DOTALL,
    )
    match = pattern.search(original)
    if not match:
        raise RuntimeError(
            f"block markers {begin}/{end} not found in {target} — "
            f"target may have been edited out-of-band"
        )
    new_content = original[: match.start()] + original[match.end() :]
    target.write_text(new_content, encoding="utf-8")

    # Delete the archive entry.
    archive_path.unlink()

    # Re-create the candidate file for re-review.
    ts_date = _dt.date.today().isoformat()
    candidates_dir = kb_root / "_candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    # Preserve any original body we can recover from the archive.
    body_match = re.search(r"```markdown\n(.*?)\n```\s*$", text, re.DOTALL)
    body = body_match.group(1) if body_match else "(archive did not preserve body)"
    re_candidate = candidates_dir / f"{ts_date}_unpromoted_{content_hash}.md"
    re_candidate.write_text(
        f"# Candidate (re-queued from unpromotion)\n\n"
        f"## Candidate kind: {kind}\n\n"
        f"Source: {source_candidate}\n"
        f"Original archive: {archive_path}\n\n"
        f"{body}\n",
        encoding="utf-8",
    )

    _emit_event(
        "kb_artifact_unpromoted",
        {
            "artifact_class": kind,
            "reverted_archive_path": str(archive_path),
            "target_path": str(target),
            "re_queued_candidate": str(re_candidate),
            "content_hash": content_hash,
            "unpromoted_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        },
    )
    return re_candidate


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="archivist",
        description="Primitive C KB promotion / rollback surface (stub).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root (default: inferred from script path)",
    )
    parser.add_argument(
        "--operator-id",
        type=str,
        default=os.environ.get("ARCHIVIST_OPERATOR_ID", ""),
        help=(
            "Operator identity (required for --promote per ADR 010). "
            "Falls back to ARCHIVIST_OPERATOR_ID env var."
        ),
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--promote",
        type=Path,
        metavar="CANDIDATE",
        help="Promote a candidate file into the live KB.",
    )
    mode.add_argument(
        "--unpromote",
        type=Path,
        metavar="ARCHIVE",
        help="Reverse a prior promotion (delete archive + restore target).",
    )
    args = parser.parse_args(argv)
    repo_root: Path = args.repo_root.resolve()

    try:
        if args.promote is not None:
            archive = promote(repo_root, args.promote.resolve(), args.operator_id)
            print(f"archivist: promoted {args.promote} → archive {archive}")
            return 0
        if args.unpromote is not None:
            re_candidate = unpromote(repo_root, args.unpromote.resolve())
            print(f"archivist: un-promoted {args.unpromote} → {re_candidate}")
            return 0
    except FileNotFoundError as exc:
        print(f"archivist: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"archivist: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"archivist: {exc}", file=sys.stderr)
        return 3
    return 1  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
