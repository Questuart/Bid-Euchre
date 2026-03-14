"""Confidence scoring for P2 review findings.

Filters low-confidence P2 findings to reduce false positives in the
autonomous review loop. P0 and P1 findings always pass through unfiltered.

Uses deterministic heuristics (not LLM calls) to keep the review loop
fast and reproducible.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ScoredFinding:
    """A finding with an attached confidence score."""

    finding: dict  # Original finding dict
    confidence: int  # 0-100 score
    reasoning: str  # Why this score
    filtered: bool  # True if below threshold


CONFIDENCE_THRESHOLD = 75

# Files known to be legitimately complex — C4 (complexity) findings
# in these files are expected and should not be flagged.
_KNOWN_COMPLEX_FILES = (
    "orchestration.py",
    "review_driver.py",
    "run_rung.py",
    "semantic_gate.py",
    "train_hybrid_olsa.py",
)


def score_findings(
    findings: list[dict],
    pr_diff: str,
    threshold: int = CONFIDENCE_THRESHOLD,
) -> tuple[list[dict], list[ScoredFinding]]:
    """Score P2 findings and filter by confidence.

    Args:
        findings: List of finding dicts (from prechecks or Codex adapter,
            with keys: severity, file, line, check_id, message, category).
        pr_diff: The PR diff text (``git diff main...HEAD``) for context.
        threshold: Minimum confidence to keep (default 75).

    Returns:
        Tuple of (filtered_findings, all_scored_findings).
        ``filtered_findings`` contains P0/P1 unchanged plus P2 findings
        whose confidence >= threshold.
    """
    passed: list[dict] = []
    scored: list[ScoredFinding] = []

    for finding in findings:
        severity = finding.get("severity", "P2")

        # P0/P1 always pass through
        if severity in ("P0", "P1"):
            passed.append(finding)
            scored.append(
                ScoredFinding(
                    finding=finding,
                    confidence=100,
                    reasoning="P0/P1 findings are never filtered",
                    filtered=False,
                )
            )
            continue

        # Score P2 findings
        score_result = _score_single_finding(finding, pr_diff)
        is_filtered = score_result.confidence < threshold
        score_result.filtered = is_filtered
        scored.append(score_result)

        if not is_filtered:
            passed.append(finding)

    return passed, scored


def _is_test_file(file_path: str) -> bool:
    """Return True if the file is under a tests/ directory."""
    return file_path.startswith("tests/") or "/tests/" in file_path


def _score_single_finding(finding: dict, pr_diff: str) -> ScoredFinding:
    """Score a single P2 finding using heuristic rules.

    Uses deterministic heuristics rather than LLM calls to keep the
    review loop fast and reproducible.
    """
    confidence = 80  # Default: likely genuine
    reasons: list[str] = []

    file_path = finding.get("file", "")
    line = finding.get("line", 0)
    check_id = finding.get("check_id", "")

    # Check 1: Is the finding on a line that was actually modified?
    if pr_diff and file_path and line:
        if not _line_in_diff(file_path, line, pr_diff):
            confidence -= 40
            reasons.append("Finding is on an unmodified line")

    # Check 2: Convention checks in test files are lower priority
    if _is_test_file(file_path) and check_id in ("C4", "X3"):
        confidence -= 20
        reasons.append("Convention check in test code")

    # Check 3: Complexity (C4) in known-complex files
    if check_id == "C4" and any(p in file_path for p in _KNOWN_COMPLEX_FILES):
        confidence -= 25
        reasons.append("Complexity finding in a file known to be legitimately complex")

    # Check 4: N3 inference claims — high false positive rate from regex heuristics
    if check_id == "N3":
        confidence -= 15
        reasons.append("N3 inference-without-test has high false positive rate")

    # Check 5: X2 undocumented contract change — check if docs were also changed
    if check_id == "X2" and "docs/01_core/" in pr_diff:
        confidence -= 30
        reasons.append("X2 flagged but docs/01_core/ was also modified in this PR")

    # Clamp to [0, 100]
    confidence = max(0, min(100, confidence))

    reasoning = "; ".join(reasons) if reasons else "No deductions applied"

    return ScoredFinding(
        finding=finding,
        confidence=confidence,
        reasoning=reasoning,
        filtered=False,  # Set by caller
    )


def _line_in_diff(file_path: str, line: int, diff_text: str) -> bool:
    """Check if a specific line was modified in the diff.

    Parses unified diff format to extract added line numbers.
    Returns True if the given line number appears as an added line
    in the specified file's diff hunk.
    """
    in_file = False
    current_line = 0

    for diff_line in diff_text.split("\n"):
        if diff_line.startswith("+++ b/"):
            in_file = diff_line[6:] == file_path
            continue

        if not in_file:
            continue

        if diff_line.startswith("@@"):
            # Parse @@ -old,count +new,count @@
            try:
                plus_part = diff_line.split("+")[1].split("@@")[0].strip()
                current_line = int(plus_part.split(",")[0])
            except (IndexError, ValueError):
                continue
        elif diff_line.startswith("+") and not diff_line.startswith("+++"):
            if current_line == line:
                return True
            current_line += 1
        elif diff_line.startswith("-"):
            pass  # Removed lines don't increment new-file line counter
        else:
            current_line += 1

    return False


def save_scoring_report(
    scored: list[ScoredFinding],
    output_path: Path,
) -> None:
    """Save scoring results to JSON for audit trail.

    Args:
        scored: List of ScoredFinding objects from ``score_findings``.
        output_path: Path to write the JSON report.
    """
    report = {
        "total_findings": len(scored),
        "passed": sum(1 for s in scored if not s.filtered),
        "filtered": sum(1 for s in scored if s.filtered),
        "threshold": CONFIDENCE_THRESHOLD,
        "findings": [
            {
                "file": s.finding.get("file", ""),
                "line": s.finding.get("line", 0),
                "check_id": s.finding.get("check_id", ""),
                "severity": s.finding.get("severity", ""),
                "confidence": s.confidence,
                "reasoning": s.reasoning,
                "filtered": s.filtered,
            }
            for s in scored
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n")
