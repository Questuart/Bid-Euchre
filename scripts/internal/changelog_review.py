#!/usr/bin/env python3
"""Changelog review CLI — Primitive D Phase 0 scraper dispatcher.

Per ``plans/steward_platform/4_primitive_D/shaping.md`` §4.5.3.

Usage
-----
::

    uv run python scripts/internal/changelog_review.py [--since <ISO-date>] \\
        [--sources-file <path>] [--dry-run] [--fixture-dir <path>]

Exit codes
----------
- ``0`` — success (candidates written or dry-run listed)
- ``1`` — empty scan (sources all reachable but produced zero candidates)
- ``2`` — source-unreachable class: all configured sources failed; also used
  for a malformed ``--since`` / ``--sources-file`` input (symmetric with
  archivist CLI conventions)
- ``3`` — write failure

Production mode: when no ``--fixture-dir`` is passed, the CLI runs the
null fetcher (all sources unreachable, exit 2). The intent is that a
Phase 1+ PR swaps in a WebFetch-backed fetcher; Phase 0 is fixture-only.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from bid_euchre.ops.changelog_review import (
    DEFAULT_CANDIDATES_DIR,
    DEFAULT_HARNESS_ASSUMPTIONS_PATH,
    DEFAULT_SOURCES,
    make_fixture_fetcher,
    make_null_fetcher,
    run_review,
)


def build_parser() -> argparse.ArgumentParser:
    """Return the changelog-review CLI argparse parser."""
    parser = argparse.ArgumentParser(
        prog="changelog_review",
        description=(
            "Changelog review — scrape Claude Code changelog + ecosystem "
            "sources, extract candidate entries, write a dated candidate "
            "file under knowledge/_candidates/."
        ),
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help=(
            "ISO-8601 date override; default is the last-run watermark at "
            "knowledge/_candidates/.last_run_changelog."
        ),
    )
    parser.add_argument(
        "--sources-file",
        type=Path,
        default=None,
        help=(
            "Override the default 7-source list. One URL per line; "
            "blank lines and `#`-prefixed comments ignored."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print scraped-source count + candidate count; do not write.",
    )
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=None,
        help=(
            "Test-only: read HTML from this fixture directory instead of "
            "WebFetch. See tests/fixtures/changelog_review/ for format."
        ),
    )
    parser.add_argument(
        "--candidates-dir",
        type=Path,
        default=DEFAULT_CANDIDATES_DIR,
        help="Override candidates directory (default: knowledge/_candidates).",
    )
    parser.add_argument(
        "--assumptions-path",
        type=Path,
        default=DEFAULT_HARNESS_ASSUMPTIONS_PATH,
        help=(
            "Override path to knowledge/harness_assumptions.md (for "
            "staleness-detection tests)."
        ),
    )
    return parser


def _parse_sources(sources_file: Path | None) -> tuple[str, ...]:
    """Load a custom source list; return :data:`DEFAULT_SOURCES` on ``None``."""
    if sources_file is None:
        return DEFAULT_SOURCES
    try:
        text = sources_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(
            f"error: --sources-file unreadable ({sources_file}): {exc}"
        ) from exc
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    if not lines:
        raise SystemExit(f"error: --sources-file has no usable URLs ({sources_file})")
    return tuple(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    parser = build_parser()
    args = parser.parse_args(argv)

    # Validate --since format even though Phase 0 scraper does not yet
    # filter on it — the CLI needs to reject malformed input now so the
    # watermark-based incremental-scan work (Phase 1+) has a clean CLI
    # contract to build on.
    if args.since is not None:
        try:
            datetime.fromisoformat(args.since)
        except ValueError:
            print(
                f"error: --since not ISO-8601: {args.since!r}",
                file=sys.stderr,
            )
            return 2

    try:
        sources = _parse_sources(args.sources_file)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.fixture_dir is not None:
        if not args.fixture_dir.exists():
            print(
                f"error: --fixture-dir does not exist: {args.fixture_dir}",
                file=sys.stderr,
            )
            return 2
        fetcher = make_fixture_fetcher(args.fixture_dir)
    else:
        # Phase 0: no production WebFetch wiring yet. Use null fetcher so
        # every source reports unreachable → exit 2 (operator-visible
        # signal that production fetcher is not installed).
        fetcher = make_null_fetcher()

    try:
        result = run_review(
            sources=sources,
            fetcher=fetcher,
            assumptions_path=args.assumptions_path,
            candidates_dir=args.candidates_dir,
            dry_run=args.dry_run,
        )
    except OSError as exc:
        print(f"error: write failure: {exc}", file=sys.stderr)
        return 3

    date = result.run_ts.strftime("%Y-%m-%d")
    out_path = args.candidates_dir / f"{date}_changelog.md"

    if args.dry_run:
        print(
            f"changelog_review: dry-run target={out_path} "
            f"sources={result.sources_ok}/{result.sources_total} "
            f"candidates={len(result.candidates)}"
        )
    else:
        print(
            f"changelog_review: wrote {len(result.candidates)} candidate(s) "
            f"to {out_path} "
            f"(sources_ok={result.sources_ok}/{result.sources_total})"
        )

    # Exit-code dispatch:
    # - all unreachable → 2
    # - reachable but empty → 1
    # - anything else → 0
    if result.all_sources_unreachable:
        return 2
    if not result.candidates:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
