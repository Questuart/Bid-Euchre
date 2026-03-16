"""Codex CLI plan review adapter -- tier detection and plan-scoped invocation.

Extends the code review adapter for plan file review with:
- Tier detection (frontmatter override -> heuristic classification)
- Codex invocation in the provided working directory (relies on worktree workflow)
- Pre-flight auth check for Codex CLI credentials
- Claude failsafe (CLAUDE_REVIEW_CMD env var for testing)
- Plan-specific finding schema (PlanReviewFinding)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger("codex_plan_review_adapter")

# --- Tier Detection ---

# Frontmatter override pattern: <!-- review-tier: small|medium|governing -->
_TIER_OVERRIDE_RE = re.compile(r"<!--\s*review-tier:\s*(small|medium|governing)\s*-->")

# Strong research signals for governing escalation (rule 3)
_GOVERNING_SIGNALS = [
    re.compile(r"^##\s+Hypotheses", re.MULTILINE),  # Section header
    re.compile(r"\brung\s+ladder\b", re.IGNORECASE),
    re.compile(r"\b[Rr][0-3]\*?\b"),  # R0, R1, R2, R3, R0*
    re.compile(r"\bpromotion\s+gate\b", re.IGNORECASE),
    re.compile(r"\bADVANCE\b"),
    re.compile(r"\bHALT\b"),
]

VALID_TIERS = ("small", "medium", "governing")

# Pattern to detect backtick-quoted file paths
_FILE_REF_RE = re.compile(r"`[a-zA-Z_./][a-zA-Z0-9_./]+\.\w+`")

# Pattern to detect multi-PR references
_MULTI_PR_RE = re.compile(r"\bmulti-PR\b|\bPR-\d+\b", re.IGNORECASE)


@dataclass
class PlanReviewFinding:
    """A single finding from plan review (Codex or Claude failsafe)."""

    severity: str  # "CRITICAL", "WARNING", "INFO"
    category: str  # "convention", "risk", "research"
    file: str
    line: int
    description: str
    check_id: str | None  # "P1", "P2", "R4", etc.
    source: str = "codex_cli"  # or "claude_failsafe"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> PlanReviewFinding:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class PlanReviewResult:
    """Result of a plan review invocation."""

    success: bool
    findings: list[PlanReviewFinding]
    tier: str
    reviewer: str  # "codex_cli" or "claude_failsafe"
    raw_output: str
    latency_seconds: float
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "findings": [f.to_dict() for f in self.findings],
            "tier": self.tier,
            "reviewer": self.reviewer,
            "raw_output": self.raw_output,
            "latency_seconds": self.latency_seconds,
            "error": self.error,
        }


def detect_plan_tier(plan_path: Path) -> str:
    """Classify a plan file into small, medium, or governing tier.

    Tier detection follows the rules in PLAN_REVIEW_TIERS.md:
    1. Frontmatter override (first 10 lines)
    2. Initiative path (plans/<initiative>/, not sessions or _templates)
    3. Content escalation to governing (>300 lines + research signals,
       or ## Governing Plan header)
    4. Content escalation to medium (4+ file refs, multi-PR, or >80 lines)
    5. Default: small
    """
    try:
        content = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        logger.warning("Cannot read plan file %s, defaulting to small", plan_path)
        return "small"

    lines = content.split("\n")

    # Rule 1: Frontmatter override in first 10 lines
    header = "\n".join(lines[:10])
    override_match = _TIER_OVERRIDE_RE.search(header)
    if override_match:
        return override_match.group(1)

    # Rule 2: Initiative path detection
    path_str = str(plan_path)
    # Normalize to forward slashes for matching
    path_str_normalized = path_str.replace("\\", "/")
    # Check if under plans/<initiative>/ but NOT plans/sessions/ or plans/_templates/
    if "/plans/" in path_str_normalized:
        # Extract the segment after plans/
        parts_after_plans = path_str_normalized.split("/plans/", 1)[1]
        first_segment = (
            parts_after_plans.split("/")[0] if "/" in parts_after_plans else ""
        )
        if first_segment and first_segment not in ("sessions", "_templates"):
            return "governing"

    # Rule 3: Content escalation to governing
    line_count = len(lines)

    # Check for ## Governing Plan header
    if re.search(r"^##\s+Governing\s+Plan\b", content, re.MULTILINE):
        return "governing"

    # >300 lines AND any strong research signal
    if line_count > 300:
        for pattern in _GOVERNING_SIGNALS:
            if pattern.search(content):
                return "governing"

    # Rule 4: Content escalation to medium
    file_refs = _FILE_REF_RE.findall(content)
    has_multi_pr = bool(_MULTI_PR_RE.search(content))

    if len(file_refs) >= 4 or has_multi_pr or line_count > 80:
        return "medium"

    # Rule 5: Default
    return "small"


def plan_state_key(plan_path: Path) -> str:
    """Compute a stable key from the repo-relative path using hashlib.

    Uses SHA-256 of the string path, truncated to 12 hex chars.
    This ensures different directories with the same basename get different keys.
    """
    rel = str(plan_path)  # already repo-relative
    return hashlib.sha256(rel.encode()).hexdigest()[:12]


def _check_codex_auth(auth_path: Path | None = None) -> str | None:
    """Check whether Codex CLI credentials are present.

    Args:
        auth_path: Path to the auth file. Defaults to ``~/.codex/auth.json``.

    Returns:
        ``None`` if auth looks valid, or an error message string if not.
    """
    if auth_path is None:
        auth_path = Path.home() / ".codex" / "auth.json"

    if not auth_path.exists():
        return f"Codex auth file not found at {auth_path}"

    try:
        data = json.loads(auth_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return f"Cannot read Codex auth file: {exc}"

    # Check for API key auth
    if data.get("OPENAI_API_KEY"):
        return None

    # Check for ChatGPT token auth
    tokens = data.get("tokens")
    if isinstance(tokens, dict) and tokens:
        return None

    return "Codex auth file exists but contains no valid credentials (no API key or tokens)"


def invoke_codex_plan_review(
    plan_path: Path,
    tier: str,
    *,
    base: str = "main",
    timeout: int = 300,
    cwd: Path | None = None,
) -> PlanReviewResult:
    """Invoke Codex CLI for plan-specific review.

    Invokes Codex CLI in the provided working directory. Relies on worktree
    workflow -- the cwd should be a worktree with plan changes committed on
    a branch.

    Args:
        plan_path: Path to the plan file (repo-relative).
        tier: Detected plan tier ("small", "medium", "governing").
        base: Git base ref for the review.
        timeout: Maximum wait time in seconds.
        cwd: Working directory (defaults to cwd).

    Returns:
        PlanReviewResult with parsed findings or error info.
    """
    # Lazy import to avoid circular dependency / missing module at import time
    from codex_review_adapter import (
        _CLEAN_REVIEW_PATTERNS,
        _classify_error,
        _resolve_codex_binary,
        parse_codex_output,
    )

    work_dir = cwd or Path.cwd()
    start = time.monotonic()

    # Pre-flight auth check
    auth_error = _check_codex_auth()
    if auth_error:
        elapsed = time.monotonic() - start
        logger.warning("Codex auth check failed: %s", auth_error)
        return PlanReviewResult(
            success=False,
            findings=[],
            tier=tier,
            reviewer="codex_cli",
            raw_output="",
            latency_seconds=elapsed,
            error=auth_error,
        )

    try:
        cmd = [*_resolve_codex_binary(), "review", "--base", base]
        logger.info(
            "Invoking Codex CLI for plan review (tier=%s, base=%s, file=%s)",
            tier,
            base,
            plan_path,
        )

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=work_dir,
        )
        elapsed = time.monotonic() - start

        if result.returncode != 0:
            error_type = _classify_error(result.stderr)
            logger.warning(
                "Codex CLI plan review failed (exit %d, %.1fs, %s): %s",
                result.returncode,
                elapsed,
                error_type,
                result.stderr[:200],
            )
            return PlanReviewResult(
                success=False,
                findings=[],
                tier=tier,
                reviewer="codex_cli",
                raw_output=result.stdout + result.stderr,
                latency_seconds=elapsed,
                error=f"Exit code {result.returncode}: {result.stderr[:200]}",
            )

        # Parse findings using the shared parser
        codex_findings = parse_codex_output(result.stdout)
        plan_findings = _convert_codex_findings(codex_findings, str(plan_path))

        # Fail-safe: unparseable non-empty output
        if not codex_findings and result.stdout.strip():
            if not _CLEAN_REVIEW_PATTERNS.search(result.stdout):
                logger.warning(
                    "Codex CLI plan review returned unparseable output (%.1fs, %d chars)",
                    elapsed,
                    len(result.stdout),
                )
                return PlanReviewResult(
                    success=False,
                    findings=[],
                    tier=tier,
                    reviewer="codex_cli",
                    raw_output=result.stdout,
                    latency_seconds=elapsed,
                    error="Unparseable output: no findings matched and no clean-review signal",
                )

        logger.info(
            "Codex CLI plan review completed (%.1fs): %d findings",
            elapsed,
            len(plan_findings),
        )
        return PlanReviewResult(
            success=True,
            findings=plan_findings,
            tier=tier,
            reviewer="codex_cli",
            raw_output=result.stdout,
            latency_seconds=elapsed,
        )

    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        logger.warning("Codex CLI plan review timed out after %.1fs", elapsed)
        return PlanReviewResult(
            success=False,
            findings=[],
            tier=tier,
            reviewer="codex_cli",
            raw_output="",
            latency_seconds=elapsed,
            error=f"Timeout after {timeout}s",
        )

    except FileNotFoundError:
        elapsed = time.monotonic() - start
        logger.error("Codex CLI not found for plan review")
        return PlanReviewResult(
            success=False,
            findings=[],
            tier=tier,
            reviewer="codex_cli",
            raw_output="",
            latency_seconds=elapsed,
            error="Codex CLI not found (codex not in PATH, npx unavailable)",
        )


def invoke_claude_failsafe(
    plan_path: Path,
    tier: str,
    *,
    timeout: int = 120,
) -> PlanReviewResult:
    """Invoke Claude failsafe reviewer when Codex CLI is unavailable.

    Checks ``CLAUDE_REVIEW_CMD`` env var for a test seam. If set, runs
    that command with plan_path and tier as arguments and parses JSON output.
    If not set, returns a minimal result indicating no live session available.

    Args:
        plan_path: Path to the plan file.
        tier: Detected plan tier.
        timeout: Maximum wait time in seconds.

    Returns:
        PlanReviewResult with findings from Claude or a placeholder.
    """
    start = time.monotonic()
    claude_cmd = os.environ.get("CLAUDE_REVIEW_CMD", "").strip()

    if not claude_cmd:
        elapsed = time.monotonic() - start
        return PlanReviewResult(
            success=False,
            findings=[],
            tier=tier,
            reviewer="claude_failsafe",
            raw_output="",
            latency_seconds=elapsed,
            error="CLAUDE_REVIEW_CMD not set -- Claude failsafe requires a live session",
        )

    try:
        cmd = [*claude_cmd.split(), str(plan_path), tier]
        logger.info(
            "Invoking Claude failsafe (cmd=%s, tier=%s, file=%s)",
            cmd,
            tier,
            plan_path,
        )

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = time.monotonic() - start

        if result.returncode != 0:
            return PlanReviewResult(
                success=False,
                findings=[],
                tier=tier,
                reviewer="claude_failsafe",
                raw_output=result.stdout + result.stderr,
                latency_seconds=elapsed,
                error=f"Claude failsafe exited with code {result.returncode}",
            )

        # Parse JSON output as list of PlanReviewFinding dicts
        findings = _parse_claude_json_output(result.stdout)

        return PlanReviewResult(
            success=True,
            findings=findings,
            tier=tier,
            reviewer="claude_failsafe",
            raw_output=result.stdout,
            latency_seconds=elapsed,
        )

    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        return PlanReviewResult(
            success=False,
            findings=[],
            tier=tier,
            reviewer="claude_failsafe",
            raw_output="",
            latency_seconds=elapsed,
            error=f"Claude failsafe timed out after {timeout}s",
        )

    except (FileNotFoundError, OSError) as exc:
        elapsed = time.monotonic() - start
        return PlanReviewResult(
            success=False,
            findings=[],
            tier=tier,
            reviewer="claude_failsafe",
            raw_output="",
            latency_seconds=elapsed,
            error=f"Claude failsafe command failed: {exc}",
        )


def parse_plan_findings(
    raw_output: str,
    source: str = "codex_cli",
) -> list[PlanReviewFinding]:
    """Parse raw Codex CLI output into PlanReviewFinding objects.

    Reuses ``parse_codex_output`` from the code review adapter, then
    converts each ``CodexFinding`` to a ``PlanReviewFinding``.

    Args:
        raw_output: Raw stdout from Codex CLI.
        source: Source label for the findings.

    Returns:
        List of PlanReviewFinding objects.
    """
    from codex_review_adapter import parse_codex_output

    codex_findings = parse_codex_output(raw_output)
    return _convert_codex_findings(codex_findings, source=source)


# --- Internal helpers ---

# Severity mapping from Codex P-levels to plan review severity
_CODEX_TO_PLAN_SEVERITY = {
    "P0": "CRITICAL",
    "P1": "WARNING",
    "P2": "INFO",
}


def _convert_codex_findings(
    codex_findings: list,
    plan_file: str = "",
    *,
    source: str = "codex_cli",
) -> list[PlanReviewFinding]:
    """Convert CodexFinding objects to PlanReviewFinding objects."""
    results = []
    for cf in codex_findings:
        results.append(
            PlanReviewFinding(
                severity=_CODEX_TO_PLAN_SEVERITY.get(cf.severity, "INFO"),
                category=cf.category,
                file=cf.file or plan_file,
                line=cf.line,
                description=cf.message,
                check_id=cf.check_id,
                source=source,
            )
        )
    return results


def _parse_claude_json_output(raw_output: str) -> list[PlanReviewFinding]:
    """Parse JSON output from Claude failsafe command.

    Expects a JSON array of objects matching the PlanReviewFinding schema.
    """
    try:
        data = json.loads(raw_output.strip())
    except (json.JSONDecodeError, ValueError):
        logger.warning("Claude failsafe output is not valid JSON")
        return []

    if not isinstance(data, list):
        logger.warning("Claude failsafe output is not a JSON array")
        return []

    findings = []
    for item in data:
        if isinstance(item, dict):
            try:
                item.setdefault("source", "claude_failsafe")
                findings.append(PlanReviewFinding.from_dict(item))
            except (TypeError, KeyError) as exc:
                logger.warning("Skipping malformed finding: %s (%s)", item, exc)
    return findings
