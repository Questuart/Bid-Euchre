"""Changelog review scraper — source walker + candidate assembler.

Per Primitive D shape §4.5 (Changelog review). This module:

- walks a 7-entry source list (§4.5.2)
- extracts feature announcements per source (WebFetch in production;
  fixture-dir reads local HTML files in tests)
- cross-checks extracted features against
  ``knowledge/harness_assumptions.md`` for staleness (§4.8.3)
- assembles ``CandidateEntry`` records + a per-source status map
- writes a dated ``knowledge/_candidates/<YYYY-MM-DD>_changelog.md``
  file per the §4.5.4 schema

Phase 0 extraction uses a **deterministic, heuristic parser** over the
fetched HTML/text (no LLM-in-the-loop) — per shape §2.2 the compile
step is *operator review*, not autonomous synthesis. The parser:

- reads an HTML-ish fixture line by line
- treats each ``<h2>``/``<h3>`` / ``##`` / ``###`` as a feature boundary
- extracts the feature name from the heading text
- looks for optional ``Tier:`` and ``Affected primitives:`` hints in the
  following paragraph
- defaults conservatively (tier C, primitive D) when hints are absent

This parser is intentionally simple: fixtures feed it well-structured
HTML, and production WebFetch output is expected to be already
summarized by the fetch prompt (see §4.5.2). Production parsing quality
is an operator-review surface — false positives/negatives are expected
and the operator edits the candidate file before promoting anything.

Source-list walk behavior (§4.5.2):

- the walker iterates the configured 7-source list in order
- each source's result is ``"OK"``, ``"404"``, or ``"timeout"``
- ``--fixture-dir`` replaces live fetches with fixture file reads
- WebFetch / fixture failures are logged and continue to the next source
- an empty-result + all-reachable state yields exit code 1 (handled by CLI)
- all-unreachable yields exit code 2 (handled by CLI)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional

from .schema import CandidateEntry, render_candidate_section, validate_candidate

logger = logging.getLogger("ops.changelog_review.scraper")

# Repo-rooted default path for harness assumptions (shape §4.8.3 + C.2).
DEFAULT_HARNESS_ASSUMPTIONS_PATH = Path("knowledge/harness_assumptions.md")
DEFAULT_CANDIDATES_DIR = Path("knowledge/_candidates")

# The 7-source list (shape §4.5.2). Order is load-bearing: the walker
# short-circuits on cache-hits as earlier sources cross-reference later ones.
DEFAULT_SOURCES: tuple[str, ...] = (
    "https://code.claude.com/docs/en/changelog",
    "https://code.claude.com/docs/en/whats-new",
    # Per-week pages walked from the current ISO week — the walker
    # resolves the URL at fetch time; the string here is the template.
    "https://code.claude.com/docs/en/whats-new/{iso_week}",
    "https://github.com/anthropics/claude-code/releases",
    "https://docs.anthropic.com",
    "https://github.com/anthropics/claude-code-plugins",
    # Operator-curated seed; path resolved to
    # knowledge/external_signal_sources.md at walk time.
    "file://knowledge/external_signal_sources.md",
)

# Fixture-dir filename convention — the scraper picks these up by name
# when `--fixture-dir` is set. Missing files are treated as "source
# unavailable" (reported in source_results; not an error).
FIXTURE_FILENAMES: dict[str, str] = {
    "https://code.claude.com/docs/en/changelog": "fake_official.html",
    "https://code.claude.com/docs/en/whats-new": "fake_whats_new.html",
    "https://github.com/anthropics/claude-code/releases": "fake_github_release.html",
}


@dataclass
class ScrapeResult:
    """Outcome of a full scraper run."""

    candidates: list[CandidateEntry] = field(default_factory=list)
    # Per-source status map: url → "OK" | "404" | "timeout" | "skipped".
    source_results: dict[str, str] = field(default_factory=dict)
    # Timestamp used for the dated output filename and run-ts header.
    run_ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # True when scraper ran but all sources failed — CLI exits 2.
    all_sources_unreachable: bool = False

    @property
    def sources_total(self) -> int:
        return len(self.source_results)

    @property
    def sources_ok(self) -> int:
        return sum(1 for status in self.source_results.values() if status == "OK")


@dataclass
class HarnessAssumption:
    """One entry from ``knowledge/harness_assumptions.md``.

    The scraper uses ``entry_id`` as the handle when flagging staleness
    on a candidate (shape §4.8.3). Keywords are a deterministic, cheap
    staleness signal — the parser extracts them from the entry's heading
    and first paragraph; a scraped feature whose title or body contains
    any of them is flagged stale.
    """

    entry_id: str
    heading: str
    keywords: frozenset[str] = field(default_factory=frozenset)


def load_harness_assumptions(
    path: Path | None = None,
) -> list[HarnessAssumption]:
    """Load harness assumptions from ``knowledge/harness_assumptions.md``.

    Graceful degradation path (shape §4.8.3): missing / unreadable file
    returns ``[]`` with a single INFO log line. Callers use the empty
    list to skip staleness annotation — all candidates get
    ``stales_harness_assumption=False``.
    """
    p = path if path is not None else DEFAULT_HARNESS_ASSUMPTIONS_PATH
    if not p.exists():
        logger.info(
            "harness_assumptions.md not present (path=%s); "
            "staleness annotation disabled this run",
            p,
        )
        return []
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("harness_assumptions.md unreadable: %s", exc)
        return []

    assumptions: list[HarnessAssumption] = []
    # The file is `## Entry N — <heading>` delimited; each entry's
    # keywords are taken from the heading text (the ``assumption``
    # one-liner from ADR G10 lines 172-177).
    entry_pattern = re.compile(r"^## Entry (\d+)\s*[—–-]\s*(.+?)$", re.MULTILINE)
    for match in entry_pattern.finditer(text):
        entry_id = match.group(1).strip()
        heading = match.group(2).strip()
        # Keywords = lower-cased alnum tokens ≥4 chars from heading.
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9_\-]+", heading)
        keywords = frozenset(t.lower() for t in tokens if len(t) >= 4)
        assumptions.append(
            HarnessAssumption(
                entry_id=f"Entry {entry_id}",
                heading=heading,
                keywords=keywords,
            )
        )
    logger.info("loaded %d harness assumption(s)", len(assumptions))
    return assumptions


def match_stale_assumption(
    feature_name: str,
    feature_body: str,
    assumptions: list[HarnessAssumption],
) -> Optional[HarnessAssumption]:
    """Return the first assumption whose keywords intersect the feature.

    Very cheap substring / token matching — the point is to surface
    *potential* staleness for operator review, not to make definitive
    determinations. False positives are fine (operator reviews each
    candidate); false negatives are the real risk and the keyword
    extraction in :func:`load_harness_assumptions` is intentionally
    generous.
    """
    if not assumptions:
        return None
    haystack = f"{feature_name}\n{feature_body}".lower()
    for assumption in assumptions:
        for kw in assumption.keywords:
            # Whole-word-ish match to avoid e.g. "cat" inside "catalog".
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, haystack):
                return assumption
    return None


# ----- Deterministic HTML/markdown extractor -----


def extract_features_from_html(content: str) -> list[tuple[str, str]]:
    """Extract ``[(feature_name, body), ...]`` pairs from HTML/markdown text.

    Recognizes ``<h2>``, ``<h3>``, ``##``, and ``###`` headings as feature
    boundaries. Body is the text between headings (up to 500 chars).
    Does not validate — invalid headings become empty feature names,
    which the schema validator catches downstream.

    This is a *heuristic* extractor — production-quality parsing is
    Phase 1+ work (§4.5 closes the Phase 0 surface). The shape mandates
    fixture-driven testing (§4.5.6) so this parser only needs to cover
    the fixture shape plus typical changelog HTML well enough to
    bootstrap the candidate queue.
    """
    # Normalize <h2>/<h3> headings + <p>/<li> bodies into markdown-ish lines.
    normalized = _html_to_markdown(content)
    features: list[tuple[str, str]] = []
    # Split on heading boundaries; treat everything until the next
    # heading as that feature's body.
    heading_split = re.split(r"^(#{2,3}\s+.+?)$", normalized, flags=re.MULTILINE)
    # After split, chunks alternate: [preamble, heading1, body1, heading2, body2, ...]
    for i in range(1, len(heading_split), 2):
        heading = heading_split[i]
        body = heading_split[i + 1] if i + 1 < len(heading_split) else ""
        # Strip leading ``## `` / ``### ``.
        name = re.sub(r"^#{2,3}\s+", "", heading).strip()
        body = body.strip()
        if not name:
            continue
        features.append((name, body[:500]))
    return features


def _html_to_markdown(content: str) -> str:
    """Lightly normalize HTML so the heading regex matches both forms."""
    # Replace <h2>/<h3> tags with ## / ### (and closing tags with newlines).
    t = content
    t = re.sub(r"<h2[^>]*>", "\n## ", t, flags=re.IGNORECASE)
    t = re.sub(r"</h2>", "\n", t, flags=re.IGNORECASE)
    t = re.sub(r"<h3[^>]*>", "\n### ", t, flags=re.IGNORECASE)
    t = re.sub(r"</h3>", "\n", t, flags=re.IGNORECASE)
    # Strip remaining HTML tags — sufficient for fixture quality.
    t = re.sub(r"<[^>]+>", " ", t)
    # Collapse whitespace.
    t = re.sub(r"[ \t]+", " ", t)
    return t


def extract_tier_hint(body: str) -> str:
    """Parse a ``Tier: <S|A|B|C>`` annotation from the feature body.

    Returns ``"C"`` when no hint is present (conservative default per
    shape §4.5.4 schema validator).
    """
    match = re.search(r"Tier:\s*([SABC])\b", body, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return "C"


def extract_primitives_hint(body: str) -> list[str]:
    """Parse ``Affected primitive(s): A, B, D`` hints from the body.

    Returns ``["D"]`` as the conservative default — D is the lane
    downstream-of-all-primitives catch-all when no hint is provided.
    Single-letter tokens outside A-H (e.g., "Z") are dropped without
    truncating subsequent valid tokens — the match captures a generous
    alphanumeric run and the validator-style filter drops invalid tokens.
    """
    # Capture up to end-of-line or sentence punctuation; let the per-token
    # filter drop anything that is not A-H. This preserves valid tokens
    # that follow an invalid one (e.g., "A, Z, B" → ["A", "B"]).
    match = re.search(r"Affected primitives?:\s*([A-Za-z0-9, ]+)", body, re.IGNORECASE)
    if match:
        raw = match.group(1)
        tokens = [t.strip().upper() for t in raw.split(",")]
        out = [t for t in tokens if t in {"A", "B", "C", "D", "E", "F", "G", "H"}]
        if out:
            return out
    return ["D"]


# ----- Fixture / WebFetch source dispatch -----


FetcherFn = Callable[[str], Optional[str]]
"""Signature: ``(url_or_fixture_path) -> content_or_None``.

Production passes a WebFetch-backed implementation; tests pass a
fixture-file reader. Returns ``None`` on unreachable.
"""


def make_fixture_fetcher(fixture_dir: Path) -> FetcherFn:
    """Return a :data:`FetcherFn` that reads fixture files by URL mapping.

    Falls back to URL → filename slugification for sources not in
    :data:`FIXTURE_FILENAMES` (test hook for ad-hoc fixtures).
    """

    def fetch(url: str) -> Optional[str]:
        filename = FIXTURE_FILENAMES.get(url)
        if filename is None:
            # Slugify the URL into a conservative filename.
            slug = re.sub(r"[^A-Za-z0-9]+", "_", url).strip("_").lower()
            filename = f"fake_{slug}.html"
        path = fixture_dir / filename
        if not path.exists():
            logger.debug("fixture missing for %s: %s", url, path)
            return None
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("fixture unreadable %s: %s", path, exc)
            return None

    return fetch


def make_null_fetcher() -> FetcherFn:
    """Return a :data:`FetcherFn` that always reports unreachable.

    Used as the default in ``scrape_sources`` when neither a fixture
    fetcher nor a production WebFetch fetcher is injected — runs with
    this fetcher will exit 2 (all-unreachable).
    """

    def fetch(url: str) -> Optional[str]:
        logger.info("null fetcher: %s marked unreachable", url)
        return None

    return fetch


# ----- Top-level scrape + write API -----


def scrape_source(
    url: str,
    *,
    fetcher: FetcherFn,
    assumptions: list[HarnessAssumption],
) -> tuple[list[CandidateEntry], str]:
    """Scrape one source and return ``(candidates, status)``.

    Status is ``"OK"`` on any non-empty response, ``"404"`` when fetcher
    returns ``None``. (``"timeout"`` is reserved for the production
    WebFetch wrapper; Phase 0 fixture path only distinguishes OK vs 404.)
    """
    content = fetcher(url)
    if content is None:
        return [], "404"
    features = extract_features_from_html(content)
    candidates: list[CandidateEntry] = []
    for name, body in features:
        if not name.strip():
            continue
        tier = extract_tier_hint(body)
        primitives = extract_primitives_hint(body)
        stale = match_stale_assumption(name, body, assumptions)
        entry = CandidateEntry(
            feature_name=name,
            source_url=url,
            affected_primitives=primitives,
            stales_harness_assumption=stale is not None,
            stale_entry_id=stale.entry_id if stale else None,
            tier_recommendation=tier,
        )
        # Skip invalid entries in the scrape phase; the caller can aggregate
        # validation errors separately if needed.
        if not validate_candidate(entry):
            candidates.append(entry)
        else:
            logger.debug("skipping invalid candidate from %s: %s", url, name)
    return candidates, "OK"


def _resolve_source_url(url: str, *, now: datetime | None = None) -> str:
    """Expand templated defaults in ``url`` to a concrete form.

    Two template forms appear in :data:`DEFAULT_SOURCES` and must be
    resolved before being passed to the fetcher (per shape §4.5.2):

    - ``{iso_week}`` — replaced with the current ISO year-week token
      (e.g. ``2026-W17``). ``now`` is injectable for deterministic tests.
    - ``file://`` URLs — kept verbatim; the fetcher reads the local
      file. The operator-curated seed at
      ``file://knowledge/external_signal_sources.md`` is treated as a
      regular source so the 7-source default count is honoured.
    """
    if "{iso_week}" in url:
        if now is None:
            now = datetime.now(timezone.utc)
        iso_year, iso_week, _ = now.isocalendar()
        token = f"{iso_year}-W{iso_week:02d}"
        url = url.replace("{iso_week}", token)
    return url


def scrape_sources(
    sources: Iterable[str] = DEFAULT_SOURCES,
    *,
    fetcher: FetcherFn | None = None,
    assumptions_path: Path | None = None,
    now: datetime | None = None,
) -> ScrapeResult:
    """Scrape every source in ``sources`` and return a :class:`ScrapeResult`.

    Fetcher defaults to the null fetcher (always unreachable) for safety
    — production callers inject a WebFetch-backed fetcher and tests
    inject :func:`make_fixture_fetcher`. The shape §4.5.3 `--fixture-dir`
    CLI flag drives the fixture path in tests.

    ``now`` is injectable for deterministic tests of
    :func:`_resolve_source_url`'s ``{iso_week}`` expansion (shape §4.5.2).
    """
    if fetcher is None:
        fetcher = make_null_fetcher()
    assumptions = load_harness_assumptions(assumptions_path)

    result = ScrapeResult()
    for raw_url in sources:
        resolved_url = _resolve_source_url(raw_url, now=now)
        try:
            candidates, status = scrape_source(
                resolved_url, fetcher=fetcher, assumptions=assumptions
            )
        except Exception as exc:  # pragma: no cover — defensive
            logger.exception("scrape of %s raised: %s", resolved_url, exc)
            result.source_results[resolved_url] = "timeout"
            continue
        result.source_results[resolved_url] = status
        result.candidates.extend(candidates)

    # Detect all-unreachable (shape §4.5.3 exit 2 path).
    if result.source_results and all(
        status != "OK" for status in result.source_results.values()
    ):
        result.all_sources_unreachable = True
    return result


def render_candidates_file(result: ScrapeResult) -> str:
    """Render the full ``<YYYY-MM-DD>_changelog.md`` file text.

    Header matches shape §4.5.4; sections 1..N are
    :func:`render_candidate_section` output joined by a blank line.
    """
    date = result.run_ts.strftime("%Y-%m-%d")
    run_ts = result.run_ts.replace(microsecond=0).isoformat()
    sources_total = result.sources_total
    sources_ok = result.sources_ok
    source_results_lines = (
        "\n".join(
            f"- {url} — {status}" for url, status in result.source_results.items()
        )
        or "_(no sources queried)_"
    )

    header = (
        f"# Changelog Review Candidate — {date}\n"
        f"\n"
        f"**Run timestamp:** {run_ts}\n"
        f"**Sources scraped:** {sources_ok}/{sources_total}\n"
        f"**Source results:**\n{source_results_lines}\n"
        f"**Candidate count:** {len(result.candidates)}\n"
        f"\n"
    )

    body_parts: list[str] = []
    for idx, entry in enumerate(result.candidates, start=1):
        body_parts.append(render_candidate_section(idx, entry))
    body = "\n".join(body_parts) if body_parts else "_(no candidates this run)_\n"

    footer = (
        "\n"
        "## Verification: operator review\n"
        "Each candidate has: feature name, source URL, affected primitive, "
        "staleness annotation, tier, decision fields.\n"
    )

    return header + body + footer


def write_candidates_file(
    result: ScrapeResult,
    candidates_dir: Path = DEFAULT_CANDIDATES_DIR,
) -> Path:
    """Write the rendered file to ``candidates_dir/<date>_changelog.md``.

    Creates parent directory as needed. Returns the output path.
    """
    candidates_dir.mkdir(parents=True, exist_ok=True)
    date = result.run_ts.strftime("%Y-%m-%d")
    out_path = candidates_dir / f"{date}_changelog.md"
    text = render_candidates_file(result)
    out_path.write_text(text, encoding="utf-8")
    return out_path


# ----- Watermark helpers -----


WATERMARK_FILENAME = ".last_run_changelog"


def read_watermark(candidates_dir: Path) -> Optional[datetime]:
    """Return the last-run timestamp, or ``None`` when watermark is absent."""
    path = candidates_dir / WATERMARK_FILENAME
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def write_watermark(candidates_dir: Path, when: datetime) -> None:
    """Persist ``when`` as the last-run watermark."""
    candidates_dir.mkdir(parents=True, exist_ok=True)
    path = candidates_dir / WATERMARK_FILENAME
    path.write_text(when.isoformat(), encoding="utf-8")
