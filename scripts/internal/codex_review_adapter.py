"""Codex CLI review adapter — invocation and output parsing.

Invokes the Codex CLI (`codex review --base main`) and parses the output
into normalized findings compatible with the review loop's Finding schema.

The Codex CLI runs locally, uses the ChatGPT subscription (no API billing),
and typically completes in ~60 seconds.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger("codex_review_adapter")

# Default timeout for Codex CLI invocation (5 minutes)
DEFAULT_TIMEOUT_SECONDS = 300

# Max retries before giving up
MAX_RETRIES = 3

# Known path for macOS Codex app bundle binary
_CODEX_APP_PATH = Path("/Applications/Codex.app/Contents/Resources/codex")

# Patterns in stderr that indicate a CLI argument/invocation error
# (as opposed to a review-time error like auth failure or network issue)
_CLI_ARG_ERROR_PATTERNS = [
    "cannot be used with",
    "unexpected argument",
    "invalid value",
    "usage: codex review",
]

# Mode-specific review prompts (aligned with AGENTS.md guidance).
#
# NOTE: Codex CLI currently ignores these prompts because --base and a
# positional prompt argument are mutually exclusive (codex-cli v0.114.0+).
# The prompt text is logged for diagnostics only. The CLI relies on
# repo-level AGENTS.md for review guidance. This tightening takes effect
# if/when Codex CLI adds --prompt flag support.
_PROMPTS = {
    "standard": (
        "Review for these specific issues, reporting each as [P0], [P1], or [P2] "
        "with format: [severity] file:line -- message (check_id)\n\n"
        "P0/P1 (blocking):\n"
        "- C1: Unseeded random.Random() or global random.* calls\n"
        "- C2: Falsy numeric guard (x = x or fallback where 0.0 is valid)\n"
        "- X3: Merge markers, TODO-remove, large commented-out blocks\n"
        "P2 (non-blocking):\n"
        "- C3: Gate check ordering (most-restrictive first)\n"
        "- C4: Functions >50 lines or nesting >4\n"
        "- T1: Behavior change without test change\n"
        "- X1: Changes span 3+ unrelated modules\n\n"
        "If no issues found, respond with: 'No issues found.'\n"
        "Do not include stylistic nits or formatting suggestions."
    ),
    "report-audit": (
        "Review for provenance errors, irreproducible published metrics, "
        "missing generator scripts, and gate-result/adjudication mismatches. "
        "Treat each as P1. "
        "See docs/04_reports/AGENTS.md for report-audit guidance."
    ),
    "plan-audit": (
        "Review for nonexistent file references, contradictory rollout steps, "
        "and unenforceable or deadlocking gates. Treat each as P1. "
        "See plans/AGENTS.md for plan-audit guidance."
    ),
}

# Patterns for parsing Codex CLI output
# Matches lines like: [P1] src/foo.py:42 — message (C1)
# or: [P0] src/bar.py:10 - message
_FINDING_LINE_RE = re.compile(
    r"\[(?P<severity>P[012])\]\s+"
    r"(?P<file>[^\s:]+)"
    r"(?::(?P<line>\d+))?"
    r"\s*[-—–]\s*"
    r"(?P<message>.+)"
)

# Extract check ID from message (e.g., "(C1)" or "[C1]" at end)
_CHECK_ID_RE = re.compile(r"[(\[]([A-Z]\d+)[)\]]")

# Alternative format: severity tag in brackets without P prefix
# e.g., [CRITICAL] or [WARNING]
_ALT_SEVERITY_RE = re.compile(
    r"\[(?P<severity>CRITICAL|WARNING|NIT)\]"
    r"(?:\[(?P<check_id>[A-Z]\d+)\])?\s*"
    r"(?P<file>[^\s:]+)"
    r"(?::(?P<line>\d+))?"
    r"\s*[-—–]\s*"
    r"(?P<message>.+)"
)

_SEVERITY_MAP = {
    "CRITICAL": "P0",
    "WARNING": "P1",
    "NIT": "P2",
}

# Patterns that indicate a genuinely clean review (no findings expected)
_CLEAN_REVIEW_PATTERNS = re.compile(
    r"(?i)"
    r"(?:no\s+(?:issues?|findings?|problems?)\s+found)"
    r"|(?:(?:changes?\s+)?look(?:s)?\s+good)"
    r"|(?:0\s+findings)"
    r"|(?:lgtm)"
)


@dataclass
class CodexFinding:
    """A single finding from Codex CLI review."""

    severity: str  # "P0", "P1", "P2"
    file: str
    line: int
    category: str  # "correctness", "provenance", "convention", "process"
    check_id: str | None  # "C1", "C2", "X3", etc.
    message: str
    raw_source: str = "codex_cli"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CodexReviewResult:
    """Result of a Codex CLI review invocation."""

    success: bool
    findings: list[CodexFinding]
    raw_output: str
    latency_seconds: float
    error: str | None = None
    exit_code: int | None = None
    error_type: str | None = None  # "cli_invocation_error" or "cli_review_error"

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "findings": [f.to_dict() for f in self.findings],
            "raw_output": self.raw_output,
            "latency_seconds": self.latency_seconds,
            "error": self.error,
            "exit_code": self.exit_code,
            "error_type": self.error_type,
        }


def _categorize_finding(message: str, check_id: str | None) -> str:
    """Infer finding category from message content and check ID."""
    if check_id in ("C1", "C2"):
        return "correctness"
    if check_id in ("N1", "N2", "N3"):
        return "process"
    if check_id in ("T1",):
        return "test"
    if check_id in ("X1", "X2", "X3"):
        return "process"
    if check_id in ("C3", "C4"):
        return "convention"

    msg_lower = message.lower()
    if any(k in msg_lower for k in ("provenance", "irreproducible", "generator")):
        return "provenance"
    if any(k in msg_lower for k in ("merge conflict", "breakpoint", "todo")):
        return "process"
    if any(
        k in msg_lower for k in ("random", "seed", "determinism", "import boundary")
    ):
        return "correctness"
    return "convention"


def parse_codex_output(raw_output: str) -> list[CodexFinding]:
    """Parse Codex CLI stdout into structured findings.

    Handles two output formats:
    1. Standard: [P1] file:line — message (C1)
    2. Alternative: [CRITICAL][C1] file:line — message

    Args:
        raw_output: Raw stdout from Codex CLI.

    Returns:
        List of parsed CodexFinding objects.
    """
    findings: list[CodexFinding] = []
    seen = set()  # Deduplicate (file, line, message)

    for line in raw_output.split("\n"):
        line = line.strip()
        if not line:
            continue

        finding = _parse_standard_format(line) or _parse_alt_format(line)
        if finding is None:
            continue

        key = (finding.file, finding.line, finding.message)
        if key in seen:
            continue
        seen.add(key)
        findings.append(finding)

    return findings


def _parse_standard_format(line: str) -> CodexFinding | None:
    """Parse [P1] file:line — message format."""
    match = _FINDING_LINE_RE.search(line)
    if not match:
        return None

    severity = match.group("severity")
    file_path = match.group("file")
    line_num = int(match.group("line") or 0)
    message = match.group("message").strip()

    # Extract check ID from message
    check_match = _CHECK_ID_RE.search(message)
    check_id = check_match.group(1) if check_match else None

    return CodexFinding(
        severity=severity,
        file=file_path,
        line=line_num,
        category=_categorize_finding(message, check_id),
        check_id=check_id,
        message=message,
    )


def _parse_alt_format(line: str) -> CodexFinding | None:
    """Parse [CRITICAL][C1] file:line — message format."""
    match = _ALT_SEVERITY_RE.search(line)
    if not match:
        return None

    severity = _SEVERITY_MAP.get(match.group("severity"), "P2")
    file_path = match.group("file")
    line_num = int(match.group("line") or 0)
    message = match.group("message").strip()
    check_id = match.group("check_id")

    # Also check message for check ID if not in brackets
    if not check_id:
        check_match = _CHECK_ID_RE.search(message)
        check_id = check_match.group(1) if check_match else None

    return CodexFinding(
        severity=severity,
        file=file_path,
        line=line_num,
        category=_categorize_finding(message, check_id),
        check_id=check_id,
        message=message,
    )


def _resolve_codex_binary() -> list[str]:
    """Return the command prefix for invoking Codex CLI.

    Preference order:
    1. ``CODEX_REVIEW_CMD`` env var (custom launcher, e.g. Docker wrapper)
    2. ``codex`` in PATH (fastest — no npx overhead)
    3. macOS app bundle binary at known path
    4. ``npx @openai/codex`` fallback (downloads if needed)
    """
    custom_cmd = os.environ.get("CODEX_REVIEW_CMD", "").strip()
    if custom_cmd:
        parts = custom_cmd.split()
        logger.info("Using custom Codex launcher from CODEX_REVIEW_CMD: %s", parts)
        return parts
    if shutil.which("codex"):
        return ["codex"]
    if _CODEX_APP_PATH.is_file():
        return [str(_CODEX_APP_PATH)]
    return ["npx", "@openai/codex"]


def _classify_error(stderr: str) -> str:
    """Classify a CLI error as invocation vs. runtime.

    Returns ``"cli_invocation_error"`` for argument parsing failures
    (bad flags, mutually exclusive args) or ``"cli_review_error"`` for
    runtime issues (auth, network, model errors).
    """
    stderr_lower = stderr.lower()
    if any(p in stderr_lower for p in _CLI_ARG_ERROR_PATTERNS):
        return "cli_invocation_error"
    return "cli_review_error"


def invoke_codex_cli(
    *,
    mode: str = "standard",
    base: str = "main",
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    cwd: Path | None = None,
) -> CodexReviewResult:
    """Invoke Codex CLI review and parse the output.

    Args:
        mode: Review mode ("standard", "report-audit", "plan-audit").
            Currently logged for diagnostics only — the CLI relies on
            repo-level AGENTS.md for review guidance rather than a
            positional prompt (which is mutually exclusive with --base).
        base: Git base ref for the review.
        timeout: Maximum wait time in seconds.
        cwd: Working directory (defaults to cwd).

    Returns:
        CodexReviewResult with parsed findings or error info.
    """
    cmd = [*_resolve_codex_binary(), "review", "--base", base]

    logger.info(
        "Invoking Codex CLI (mode=%s, base=%s, timeout=%ds, cmd=%s)",
        mode,
        base,
        timeout,
        cmd,
    )
    start = time.monotonic()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        elapsed = time.monotonic() - start

        if result.returncode != 0:
            error_type = _classify_error(result.stderr)
            logger.warning(
                "Codex CLI returned exit code %d (%.1fs, %s): %s",
                result.returncode,
                elapsed,
                error_type,
                result.stderr[:200],
            )
            return CodexReviewResult(
                success=False,
                findings=[],
                raw_output=result.stdout + result.stderr,
                latency_seconds=elapsed,
                error=f"Exit code {result.returncode}: {result.stderr[:200]}",
                exit_code=result.returncode,
                error_type=error_type,
            )

        findings = parse_codex_output(result.stdout)

        # Fail-safe: if zero findings parsed from non-trivial output
        # and no recognizable "clean review" signal, treat as unparseable.
        # This prevents format drift from silently bypassing review.
        if not findings and result.stdout.strip():
            if not _CLEAN_REVIEW_PATTERNS.search(result.stdout):
                logger.warning(
                    "Codex CLI returned output (%.1fs, %d chars) but no findings "
                    "were parsed and no clean-review signal detected — treating "
                    "as unparseable",
                    elapsed,
                    len(result.stdout),
                )
                return CodexReviewResult(
                    success=False,
                    findings=[],
                    raw_output=result.stdout,
                    latency_seconds=elapsed,
                    error="Unparseable output: no findings matched and no clean-review signal",
                    exit_code=0,
                )

        logger.info(
            "Codex CLI completed (%.1fs): %d findings",
            elapsed,
            len(findings),
        )
        return CodexReviewResult(
            success=True,
            findings=findings,
            raw_output=result.stdout,
            latency_seconds=elapsed,
            exit_code=0,
        )

    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        logger.warning("Codex CLI timed out after %.1fs", elapsed)
        return CodexReviewResult(
            success=False,
            findings=[],
            raw_output="",
            latency_seconds=elapsed,
            error=f"Timeout after {timeout}s",
        )

    except FileNotFoundError:
        elapsed = time.monotonic() - start
        logger.error("Codex CLI not found — codex not in PATH and npx unavailable")
        return CodexReviewResult(
            success=False,
            findings=[],
            raw_output="",
            latency_seconds=elapsed,
            error="Codex CLI not found (codex not in PATH, npx unavailable)",
        )


def get_blocking_findings(findings: list[CodexFinding]) -> list[CodexFinding]:
    """Filter to only P0/P1 findings (blocking)."""
    return [f for f in findings if f.severity in ("P0", "P1")]


def save_review_result(
    result: CodexReviewResult,
    pr_number: int,
    iteration: int,
    base_dir: Path | None = None,
) -> Path:
    """Save review result to the round directory.

    Args:
        result: The review result to save.
        pr_number: PR number.
        iteration: Current iteration number.
        base_dir: Override for state persistence directory.

    Returns:
        Path to the saved JSON file.
    """
    from review_state import round_dir

    rdir = round_dir(pr_number, iteration, base_dir)
    rdir.mkdir(parents=True, exist_ok=True)
    path = rdir / "codex_review.json"
    with open(path, "w") as f:
        json.dump(result.to_dict(), f, indent=2)
    return path
