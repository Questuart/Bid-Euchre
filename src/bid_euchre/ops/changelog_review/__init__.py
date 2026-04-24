"""Changelog review — Primitive D Phase 0 scraper + candidate writer.

See ``plans/steward_platform/4_primitive_D/shaping.md`` §4.5 for the
design. The scraper walks a 7-entry source list, extracts feature
announcements, cross-checks against ``knowledge/harness_assumptions.md``,
and writes a dated ``knowledge/_candidates/<YYYY-MM-DD>_changelog.md``
file for operator review.

Public surface:

- :func:`run_review` — execute one full review run (fetch → extract →
  write)
- :func:`scrape_source` — fetch + parse one source
- :func:`scrape_sources` — walk multiple sources (returns :class:`ScrapeResult`)
- :class:`CandidateEntry` — candidate schema (re-exported from :mod:`.schema`)
- :func:`render_candidates_file` — render the full output file (no write)
- :func:`write_candidates_file` — render + write
- :func:`load_harness_assumptions` — load assumptions file (graceful missing)

Phase 0 scope: Phase 0 ships the deterministic extractor + fixture-driven
tests. Production WebFetch integration is a follow-on PR after
Primitive A / Primitive C coordination (shape §6.4 coordination notes).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

from .schema import (
    NATIVE_FIRST_TIERS,
    VALID_DECISIONS,
    VALID_PRIMITIVES,
    VALID_TIERS,
    CandidateEntry,
    compute_native_substrate_signal,
    render_candidate_section,
    validate_candidate,
    validate_many,
)
from .scraper import (
    DEFAULT_CANDIDATES_DIR,
    DEFAULT_HARNESS_ASSUMPTIONS_PATH,
    DEFAULT_SOURCES,
    FIXTURE_FILENAMES,
    WATERMARK_FILENAME,
    FetcherFn,
    HarnessAssumption,
    ScrapeResult,
    extract_features_from_html,
    extract_primitives_hint,
    extract_tier_hint,
    load_harness_assumptions,
    make_fixture_fetcher,
    make_null_fetcher,
    match_stale_assumption,
    read_watermark,
    render_candidates_file,
    scrape_source,
    scrape_sources,
    write_candidates_file,
    write_watermark,
)


def run_review(
    *,
    sources: tuple[str, ...] = DEFAULT_SOURCES,
    fetcher: FetcherFn | None = None,
    assumptions_path: Path | None = None,
    candidates_dir: Path = DEFAULT_CANDIDATES_DIR,
    dry_run: bool = False,
    when: datetime | None = None,
) -> ScrapeResult:
    """Execute one full changelog-review run.

    Returns the :class:`ScrapeResult`. When ``dry_run=False`` the dated
    candidate file is written and the watermark is advanced. When
    ``dry_run=True`` nothing is written; the result still reflects what
    *would* be written.

    ``when`` overrides the run timestamp — used in tests for
    deterministic filenames.
    """
    result = scrape_sources(
        sources=sources,
        fetcher=fetcher,
        assumptions_path=assumptions_path,
    )
    if when is not None:
        result = replace(result, run_ts=when)

    if dry_run:
        return result

    # Only write when we have something meaningful to record. An empty
    # result with all-unreachable sources still writes the file so the
    # operator sees the source_results — shape §4.5.4 requires the
    # source-results section even on empty scans.
    write_candidates_file(result, candidates_dir)
    write_watermark(candidates_dir, result.run_ts)
    return result


__all__ = [
    "DEFAULT_CANDIDATES_DIR",
    "DEFAULT_HARNESS_ASSUMPTIONS_PATH",
    "DEFAULT_SOURCES",
    "FIXTURE_FILENAMES",
    "NATIVE_FIRST_TIERS",
    "VALID_DECISIONS",
    "VALID_PRIMITIVES",
    "VALID_TIERS",
    "WATERMARK_FILENAME",
    "CandidateEntry",
    "FetcherFn",
    "HarnessAssumption",
    "ScrapeResult",
    "compute_native_substrate_signal",
    "extract_features_from_html",
    "extract_primitives_hint",
    "extract_tier_hint",
    "load_harness_assumptions",
    "make_fixture_fetcher",
    "make_null_fetcher",
    "match_stale_assumption",
    "read_watermark",
    "render_candidate_section",
    "render_candidates_file",
    "run_review",
    "scrape_source",
    "scrape_sources",
    "validate_candidate",
    "validate_many",
    "write_candidates_file",
    "write_watermark",
]
