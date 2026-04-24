#!/usr/bin/env python3
"""Archivist candidate-generator CLI — lessons + GC + postmortem modes.

Primitive D Phase 0 per ``plans/steward_platform/4_primitive_D/shaping.md``
§4.1.4 (lessons CLI) and §4.2 (GC dispatch).

This module is the **D-side candidate-generator** (the nightly /
end-of-session inflow). ``scripts/internal/archivist.py`` is the
complementary **C-side promotion / rollback surface** (Primitive C
Packet C-Exec). The two cooperate via the ``knowledge/_candidates/``
inflow directory per the C↔D interface contract in
``scripts/internal/archivist.py`` docstring:

- D writes to ``knowledge/_candidates/<YYYY-MM-DD>_<kind>.md``
- C reads from ``knowledge/_candidates/*.md`` and, on operator-gated
  promote, writes into ``knowledge/NOTES.md`` / ``PLAYBOOKS.md`` /
  ``anti_patterns.md`` + an archive entry under ``_promoted/``.

Usage
-----
::

    uv run python scripts/internal/archivist_candidates.py --mode lessons [--since <ts>] [--dry-run] [--fixture <path>]
    uv run python scripts/internal/archivist_candidates.py --mode gc [--fixture-dir <path>] [--dry-run]
    uv run python scripts/internal/archivist_candidates.py --mode postmortem --session-id <id> [--dry-run]

Exit codes
----------
- ``0`` — success (candidates written or dry-run listed)
- ``1`` — empty scan (no candidates — not an error)
- ``2`` — source unreachable
- ``3`` — write failure
- nonzero from argparse — invocation error (unknown flag, missing mode)
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from bid_euchre.ops.archivist import (
    DEFAULT_CANDIDATES_DIR,
    load_fake_kb_snapshot,
    run_gc,
    run_lessons,
)


def build_parser() -> argparse.ArgumentParser:
    """Return the archivist candidate-generator CLI argparse parser."""
    parser = argparse.ArgumentParser(
        prog="archivist_candidates",
        description="Archivist — Primitive D Phase 0 candidate generator.",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["lessons", "gc", "postmortem"],
        help="Archivist run mode.",
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="ISO-8601 timestamp override (lessons mode only).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute candidates but do not write output or advance watermarks.",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=None,
        help="Test-only: read events from this JSONL fixture (lessons mode).",
    )
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=None,
        help="Test-only: read fake-KB snapshot from this directory (gc mode).",
    )
    parser.add_argument(
        "--candidates-dir",
        type=Path,
        default=DEFAULT_CANDIDATES_DIR,
        help="Override candidates directory (default: knowledge/_candidates).",
    )
    parser.add_argument(
        "--session-id",
        type=str,
        default=None,
        help="Session identifier (postmortem mode only).",
    )
    parser.add_argument(
        "--memory-md",
        type=Path,
        default=Path("MEMORY.md"),
        help="Path to MEMORY.md (postmortem mode only).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
    )
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.mode == "lessons":
        return _run_lessons(args)
    if args.mode == "gc":
        return _run_gc(args)
    if args.mode == "postmortem":
        return _run_postmortem(args)
    parser.error(f"Unknown mode: {args.mode}")
    return 2  # unreachable


def _run_lessons(args: argparse.Namespace) -> int:
    since: datetime | None = None
    if args.since is not None:
        try:
            since = datetime.fromisoformat(args.since)
        except ValueError:
            print(f"error: --since not ISO-8601: {args.since!r}", file=sys.stderr)
            return 2

    result = run_lessons(
        candidates_dir=args.candidates_dir,
        since=since,
        dry_run=args.dry_run,
        fixture_path=args.fixture,
    )

    if args.dry_run:
        print(
            f"lessons: dry-run target={result.output_path} "
            f"candidates={result.candidate_count} events={result.event_count}"
        )
    elif result.output_path is not None:
        print(
            f"lessons: wrote {result.candidate_count} candidate(s) to "
            f"{result.output_path} (events={result.event_count})"
        )
    else:
        print("lessons: no candidates this run")

    return result.exit_code


def _run_gc(args: argparse.Namespace) -> int:
    snapshot = None
    if args.fixture_dir is not None:
        try:
            snapshot = load_fake_kb_snapshot(args.fixture_dir)
        except OSError as exc:
            print(f"error: fixture-dir unreadable: {exc}", file=sys.stderr)
            return 2

    result = run_gc(
        candidates_dir=args.candidates_dir,
        snapshot=snapshot,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        print(
            f"gc: dry-run target={result.output_path} "
            f"proposals={result.proposal_count} "
            f"classes={','.join(result.classes_covered) or '(none)'}"
        )
    elif result.output_path is not None:
        print(
            f"gc: wrote {result.proposal_count} proposal(s) to "
            f"{result.output_path} (classes={','.join(result.classes_covered)})"
        )
    else:
        print("gc: no proposals this run (Phase 0 live-load is not implemented)")

    return result.exit_code


def _run_postmortem(args: argparse.Namespace) -> int:
    if not args.session_id:
        print("error: --session-id is required for postmortem mode", file=sys.stderr)
        return 2

    # Lazy import — postmortem lives in a sibling module that itself imports
    # the archivist (circular-avoidance via lazy resolution).
    from bid_euchre.ops.session_postmortem import run_postmortem

    result = run_postmortem(
        session_id=args.session_id,
        memory_md_path=args.memory_md,
        candidates_dir=args.candidates_dir,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        print(
            f"postmortem: dry-run session={args.session_id} "
            f"candidate_path={result.candidate_path} "
            f"memory_md_path={result.memory_md_path}"
        )
    else:
        print(
            f"postmortem: session={args.session_id} "
            f"candidate={result.candidate_path} "
            f"memory_md_appended={result.memory_appended}"
        )

    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
