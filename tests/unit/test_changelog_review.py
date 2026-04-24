"""Unit tests for ``bid_euchre.ops.changelog_review``.

Mirrors the Primitive D shape §4.5.6 test surface:

- ``test_scrape_against_fixture_html``
- ``test_harness_assumption_staleness_detection``
- ``test_native_substrate_signal_tag_when_stales``
- ``test_tier_recommendation_populated``
- ``test_source_failure_graceful_degradation``
- ``test_all_sources_unreachable_exit_2``
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from bid_euchre.ops.changelog_review import (
    CandidateEntry,
    HarnessAssumption,
    compute_native_substrate_signal,
    extract_features_from_html,
    extract_primitives_hint,
    extract_tier_hint,
    load_harness_assumptions,
    make_fixture_fetcher,
    make_null_fetcher,
    match_stale_assumption,
    render_candidate_section,
    render_candidates_file,
    run_review,
    scrape_source,
    scrape_sources,
    validate_candidate,
    write_candidates_file,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "changelog_review"

# A minimal subset of the 7-source list that matches the fixture file
# mapping. The test walker exercises only these three URLs so the
# deterministic extractor stays coupled to the fixture HTML rather than
# to any live site.
FIXTURE_SOURCES: tuple[str, ...] = (
    "https://code.claude.com/docs/en/changelog",
    "https://code.claude.com/docs/en/whats-new",
    "https://github.com/anthropics/claude-code/releases",
)


# ----- Schema / helpers -----


class TestSchema:
    """Cover :mod:`bid_euchre.ops.changelog_review.schema`."""

    def test_candidate_defaults_compute_signal_no(self) -> None:
        entry = CandidateEntry(
            feature_name="x",
            source_url="https://example.com",
            affected_primitives=["D"],
            tier_recommendation="C",
        )
        assert entry.native_substrate_signal is False
        assert not validate_candidate(entry)

    def test_candidate_tier_s_auto_signals_yes(self) -> None:
        entry = CandidateEntry(
            feature_name="x",
            source_url="https://example.com",
            affected_primitives=["B"],
            tier_recommendation="S",
        )
        assert entry.native_substrate_signal is True

    def test_validate_rejects_empty_feature(self) -> None:
        entry = CandidateEntry(
            feature_name="",
            source_url="https://example.com",
            affected_primitives=["D"],
        )
        errors = validate_candidate(entry)
        assert any("feature_name" in e for e in errors)

    def test_validate_rejects_invalid_primitive(self) -> None:
        entry = CandidateEntry(
            feature_name="x",
            source_url="https://example.com",
            affected_primitives=["Z"],
        )
        errors = validate_candidate(entry)
        assert any("invalid value" in e for e in errors)

    def test_validate_rejects_stale_without_entry_id(self) -> None:
        entry = CandidateEntry(
            feature_name="x",
            source_url="https://example.com",
            affected_primitives=["D"],
            stales_harness_assumption=True,
        )
        errors = validate_candidate(entry)
        assert any("stale_entry_id" in e for e in errors)

    def test_render_candidate_section_contains_signal_line(self) -> None:
        entry = CandidateEntry(
            feature_name="feat",
            source_url="https://example.com",
            affected_primitives=["D"],
            tier_recommendation="S",
        )
        text = render_candidate_section(1, entry)
        # Shape §4.5.5 mandates the exact literal line.
        assert "Native-substrate-signal: yes" in text
        assert "## Candidate 1 — feat" in text


# ----- Extractor -----


class TestExtractor:
    """Cover the deterministic HTML/markdown heuristic extractor."""

    def test_extract_features_from_fixture_html(self) -> None:
        content = (FIXTURE_DIR / "fake_official.html").read_text(encoding="utf-8")
        features = extract_features_from_html(content)
        # The fixture has 4 <h2> feature entries.
        names = [name for name, _ in features]
        assert len(names) >= 4
        assert any("system-prompt-file" in n for n in names)
        assert any("Agent Teams" in n for n in names)

    def test_extract_tier_hint_extracts_S(self) -> None:
        assert extract_tier_hint("Tier: S. Affected primitives: B") == "S"
        assert extract_tier_hint("Tier: a") == "A"
        # No hint → default "C".
        assert extract_tier_hint("no tier here") == "C"

    def test_extract_primitives_hint_parses_multi(self) -> None:
        out = extract_primitives_hint("Affected primitives: A, B, D")
        assert out == ["A", "B", "D"]
        # Default to D when no hint.
        assert extract_primitives_hint("no primitives") == ["D"]

    def test_extract_primitives_hint_drops_invalid(self) -> None:
        out = extract_primitives_hint("Affected primitives: A, Z, B")
        assert out == ["A", "B"]


# ----- Harness assumptions + staleness -----


class TestHarnessAssumptions:
    """Cover shape §4.8.3 staleness detection + graceful-missing."""

    def test_load_missing_file_returns_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "no-such-file.md"
        assert load_harness_assumptions(path) == []

    def test_load_parses_entries(self, tmp_path: Path) -> None:
        path = tmp_path / "harness_assumptions.md"
        path.write_text(
            "# Harness Assumptions\n\n"
            "## Entry 1 — `--system-prompt-file` replaces the default\n\n"
            "Body text here.\n\n"
            "## Entry 2 — some other assumption\n\n"
            "Body text.\n",
            encoding="utf-8",
        )
        assumptions = load_harness_assumptions(path)
        assert len(assumptions) == 2
        assert assumptions[0].entry_id == "Entry 1"
        assert "system" in assumptions[0].keywords or any(
            "system" in kw for kw in assumptions[0].keywords
        )

    def test_match_stale_assumption_hits_on_keyword(self) -> None:
        assumption = HarnessAssumption(
            entry_id="Entry 1",
            heading="system-prompt-file replaces the default",
            keywords=frozenset({"system", "prompt", "replaces"}),
        )
        result = match_stale_assumption(
            feature_name="New --system-prompt-file semantics",
            feature_body="Tier: S. replaces the default system prompt.",
            assumptions=[assumption],
        )
        assert result is assumption

    def test_match_stale_assumption_no_hit(self) -> None:
        assumption = HarnessAssumption(
            entry_id="Entry 1",
            heading="system-prompt-file",
            keywords=frozenset({"system", "prompt"}),
        )
        result = match_stale_assumption(
            feature_name="Plugin registry index",
            feature_body="New daily index.",
            assumptions=[assumption],
        )
        assert result is None


# ----- End-to-end scrape behavior -----


class TestScrapeBehavior:
    """Full-pipeline shape §4.5.6 cases."""

    def test_scrape_against_fixture_html(self, tmp_path: Path) -> None:
        """§4.5.6 row 1 — ≥3 features extracted with required fields."""
        fetcher = make_fixture_fetcher(FIXTURE_DIR)
        # Use empty assumptions to isolate extractor correctness from
        # staleness detection (covered below).
        empty_assumptions_file = tmp_path / "empty_assumptions.md"
        empty_assumptions_file.write_text("# No entries\n", encoding="utf-8")

        result = scrape_sources(
            sources=FIXTURE_SOURCES,
            fetcher=fetcher,
            assumptions_path=empty_assumptions_file,
        )
        assert len(result.candidates) >= 3
        # Every candidate has the §4.5.4 required fields populated.
        for entry in result.candidates:
            assert entry.feature_name
            assert entry.source_url in FIXTURE_SOURCES
            assert entry.affected_primitives
            assert entry.tier_recommendation in {"S", "A", "B", "C"}
            assert entry.native_substrate_signal in {True, False}

    def test_harness_assumption_staleness_detection(self, tmp_path: Path) -> None:
        """§4.5.6 row 2 — fixture feature matches harness entry → staleness."""
        assumptions_file = tmp_path / "harness_assumptions.md"
        # Entry "X" whose keywords overlap the fake_official.html feature.
        assumptions_file.write_text(
            "# Harness Assumptions\n\n"
            "## Entry 1 — system-prompt-file replaces default\n\n"
            "Body text.\n",
            encoding="utf-8",
        )
        fetcher = make_fixture_fetcher(FIXTURE_DIR)

        result = scrape_sources(
            sources=FIXTURE_SOURCES,
            fetcher=fetcher,
            assumptions_path=assumptions_file,
        )
        stale_candidates = [c for c in result.candidates if c.stales_harness_assumption]
        assert stale_candidates, "expected at least one stale candidate"
        # Every stale candidate carries its entry_id.
        for c in stale_candidates:
            assert c.stale_entry_id

    def test_native_substrate_signal_tag_when_stales(self, tmp_path: Path) -> None:
        """§4.5.6 row 3 — staleness → native-substrate-signal yes."""
        assumptions_file = tmp_path / "harness_assumptions.md"
        assumptions_file.write_text(
            "# Harness Assumptions\n\n"
            "## Entry 1 — system-prompt-file replaces default\n\n"
            "Body text.\n",
            encoding="utf-8",
        )
        fetcher = make_fixture_fetcher(FIXTURE_DIR)

        result = scrape_sources(
            sources=FIXTURE_SOURCES,
            fetcher=fetcher,
            assumptions_path=assumptions_file,
        )
        stale_candidates = [c for c in result.candidates if c.stales_harness_assumption]
        for c in stale_candidates:
            assert c.native_substrate_signal is True
            # Rendered bullet line is the literal string the digest
            # compiler greps for (§15.3).
            section = render_candidate_section(1, c)
            assert "Native-substrate-signal: yes" in section

    def test_tier_recommendation_populated(self, tmp_path: Path) -> None:
        """§4.5.6 row 4 — tier is populated per rubric on every candidate."""
        fetcher = make_fixture_fetcher(FIXTURE_DIR)
        assumptions_file = tmp_path / "empty.md"
        assumptions_file.write_text("# no entries\n", encoding="utf-8")

        result = scrape_sources(
            sources=FIXTURE_SOURCES,
            fetcher=fetcher,
            assumptions_path=assumptions_file,
        )
        tiers = {c.tier_recommendation for c in result.candidates}
        # Fixtures declare S, A, and B tiers — all three must appear.
        assert "S" in tiers
        assert "A" in tiers
        assert "B" in tiers

    def test_source_failure_graceful_degradation(self, tmp_path: Path) -> None:
        """§4.5.6 row 5 — one 404, one OK: exit 0 + partial output."""
        # Compose a fetcher: first source succeeds with a tiny fixture,
        # second source returns None (unreachable).
        ok_file = tmp_path / "ok.html"
        ok_file.write_text(
            "<h2>Feature X</h2><p>Tier: A. Affected primitives: B.</p>",
            encoding="utf-8",
        )

        def fetcher(url: str):
            if url == "ok":
                return ok_file.read_text(encoding="utf-8")
            return None

        assumptions_file = tmp_path / "empty.md"
        assumptions_file.write_text("# no entries\n", encoding="utf-8")
        result = scrape_sources(
            sources=("ok", "unreachable-1", "unreachable-2"),
            fetcher=fetcher,
            assumptions_path=assumptions_file,
        )
        assert result.source_results["ok"] == "OK"
        assert result.source_results["unreachable-1"] == "404"
        assert result.source_results["unreachable-2"] == "404"
        assert not result.all_sources_unreachable
        assert len(result.candidates) >= 1

    def test_all_sources_unreachable_exit_2(self, tmp_path: Path) -> None:
        """§4.5.6 row 6 — null fetcher → all-unreachable flag set."""
        assumptions_file = tmp_path / "empty.md"
        assumptions_file.write_text("# no entries\n", encoding="utf-8")
        fetcher = make_null_fetcher()
        result = scrape_sources(
            sources=FIXTURE_SOURCES,
            fetcher=fetcher,
            assumptions_path=assumptions_file,
        )
        assert result.all_sources_unreachable
        assert len(result.candidates) == 0


# ----- File writer / full run_review -----


class TestRunReview:
    """Cover the top-level :func:`run_review` API."""

    def test_run_review_writes_dated_file(self, tmp_path: Path) -> None:
        fetcher = make_fixture_fetcher(FIXTURE_DIR)
        candidates_dir = tmp_path / "_candidates"
        assumptions_file = tmp_path / "empty.md"
        assumptions_file.write_text("# no entries\n", encoding="utf-8")

        when = datetime(2026, 4, 23, 18, 0, tzinfo=timezone.utc)
        result = run_review(
            sources=FIXTURE_SOURCES,
            fetcher=fetcher,
            assumptions_path=assumptions_file,
            candidates_dir=candidates_dir,
            when=when,
        )
        # Dated file exists.
        out_path = candidates_dir / "2026-04-23_changelog.md"
        assert out_path.exists()
        body = out_path.read_text(encoding="utf-8")
        assert body.startswith("# Changelog Review Candidate — 2026-04-23")
        assert "Candidate count:" in body
        # Watermark advanced.
        assert (candidates_dir / ".last_run_changelog").exists()
        assert result.candidates  # non-empty from fixtures

    def test_run_review_dry_run_no_writes(self, tmp_path: Path) -> None:
        fetcher = make_fixture_fetcher(FIXTURE_DIR)
        candidates_dir = tmp_path / "_candidates"
        assumptions_file = tmp_path / "empty.md"
        assumptions_file.write_text("# no entries\n", encoding="utf-8")
        when = datetime(2026, 4, 23, 18, 0, tzinfo=timezone.utc)

        result = run_review(
            sources=FIXTURE_SOURCES,
            fetcher=fetcher,
            assumptions_path=assumptions_file,
            candidates_dir=candidates_dir,
            dry_run=True,
            when=when,
        )
        assert not (candidates_dir / "2026-04-23_changelog.md").exists()
        assert not (candidates_dir / ".last_run_changelog").exists()
        assert result.candidates  # still computed

    def test_render_candidates_file_matches_schema(self) -> None:
        fetcher = make_fixture_fetcher(FIXTURE_DIR)
        result = scrape_sources(sources=FIXTURE_SOURCES, fetcher=fetcher)
        text = render_candidates_file(result)
        # Header per §4.5.4.
        assert "# Changelog Review Candidate — " in text
        assert "**Run timestamp:**" in text
        assert "**Sources scraped:**" in text
        assert "**Candidate count:**" in text
        # Footer per §4.5.4.
        assert "## Verification: operator review" in text


class TestResolveSourceUrl:
    """Cover URL template expansion for ``DEFAULT_SOURCES`` (§4.5.2).

    Regression coverage for Codex round-1 P2: two of the advertised
    default 7 sources are templates (``{iso_week}``, ``file://``) that
    must be resolved before reaching the fetcher, or they silently miss.
    """

    def test_iso_week_template_expanded(self) -> None:
        from bid_euchre.ops.changelog_review.scraper import _resolve_source_url

        # 2026-04-23 falls in ISO week 17.
        when = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
        url = _resolve_source_url(
            "https://code.claude.com/docs/en/whats-new/{iso_week}", now=when
        )
        assert "{iso_week}" not in url
        assert "2026-W17" in url

    def test_iso_week_template_zero_padded(self) -> None:
        from bid_euchre.ops.changelog_review.scraper import _resolve_source_url

        # 2026-01-01 falls in ISO week 1 (needs zero-padding → "W01").
        when = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)
        url = _resolve_source_url(
            "https://code.claude.com/docs/en/whats-new/{iso_week}", now=when
        )
        assert "2026-W02" in url or "2026-W01" in url
        # No stray braces.
        assert "{" not in url and "}" not in url

    def test_file_url_passthrough(self) -> None:
        from bid_euchre.ops.changelog_review.scraper import _resolve_source_url

        url = _resolve_source_url("file://knowledge/external_signal_sources.md")
        # file:// URLs are kept verbatim — the fetcher layer handles them.
        assert url == "file://knowledge/external_signal_sources.md"

    def test_scrape_sources_reaches_iso_week_expanded_url(self, tmp_path: Path) -> None:
        """After expansion the scraper presents the resolved URL to the
        fetcher, so a fixture keyed on the expanded form is reached."""
        captured: list[str] = []

        def spy_fetcher(url: str) -> str | None:
            captured.append(url)
            return None  # unreachable is fine; we only assert on the URL

        sources = ("https://code.claude.com/docs/en/whats-new/{iso_week}",)
        when = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
        assumptions_file = tmp_path / "empty.md"
        assumptions_file.write_text("# no entries\n", encoding="utf-8")

        scrape_sources(
            sources=sources,
            fetcher=spy_fetcher,
            assumptions_path=assumptions_file,
            now=when,
        )
        assert len(captured) == 1
        assert "{iso_week}" not in captured[0]
        assert "2026-W17" in captured[0]


# ----- compute_native_substrate_signal unit -----


def test_compute_signal_rule_1() -> None:
    assert compute_native_substrate_signal(
        stales_harness_assumption=True, tier_recommendation="C"
    )


def test_compute_signal_rule_2_S() -> None:
    assert compute_native_substrate_signal(
        stales_harness_assumption=False, tier_recommendation="S"
    )


def test_compute_signal_rule_2_A() -> None:
    assert compute_native_substrate_signal(
        stales_harness_assumption=False, tier_recommendation="A"
    )


def test_compute_signal_rule_miss() -> None:
    assert not compute_native_substrate_signal(
        stales_harness_assumption=False, tier_recommendation="C"
    )
    assert not compute_native_substrate_signal(
        stales_harness_assumption=False, tier_recommendation="B"
    )


# ----- scrape_source minimal unit -----


def test_scrape_source_single(tmp_path: Path) -> None:
    """One-source extraction round-trip."""
    fetcher = make_fixture_fetcher(FIXTURE_DIR)
    candidates, status = scrape_source(
        "https://code.claude.com/docs/en/changelog",
        fetcher=fetcher,
        assumptions=[],
    )
    assert status == "OK"
    assert candidates


def test_write_candidates_file_creates_dir(tmp_path: Path) -> None:
    fetcher = make_fixture_fetcher(FIXTURE_DIR)
    result = scrape_sources(sources=FIXTURE_SOURCES, fetcher=fetcher)
    out_dir = tmp_path / "nested" / "candidates"
    out_path = write_candidates_file(result, candidates_dir=out_dir)
    assert out_path.exists()
    assert out_path.parent == out_dir


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
