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
import time
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger("codex_review_adapter")

# Default timeout for Codex CLI invocation (10 minutes).
# Override via CODEX_REVIEW_TIMEOUT env var. Increased from 300s after
# observing 5/9 plan reviews and multiple PR reviews timing out at 300s.
DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("CODEX_REVIEW_TIMEOUT", "600"))

# Max retries before giving up
MAX_RETRIES = 3

# Patterns in stderr that indicate a CLI argument/invocation error
# (as opposed to a review-time error like auth failure or network issue)
_CLI_ARG_ERROR_PATTERNS = [
    "cannot be used with",
    "unexpected argument",
    "invalid value",
    "usage: codex review",
]

# Patterns in output that indicate a retryable backend interruption
# (as opposed to a permanent invocation error). These produce
# parse_confidence="backend_error" instead of success=False.
_RETRYABLE_BACKEND_RE = re.compile(
    r"(?i)(?:interrupted|re-run\s+/review|try\s+again|please\s+wait|rate\s+limit)"
)

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
    r"(?::(?P<line>\d+)(?:-\d+)?)?"
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
    r"(?::(?P<line>\d+)(?:-\d+)?)?"
    r"\s*[-—–]\s*"
    r"(?P<message>.+)"
)

_SEVERITY_MAP = {
    "CRITICAL": "P0",
    "WARNING": "P1",
    "NIT": "P2",
}

# Markdown table row format from AGENTS.md response template:
# | CRITICAL | src/foo.py | 42 | C1 | message text |
_TABLE_ROW_RE = re.compile(
    r"\|\s*(?P<severity>CRITICAL|WARNING|NIT|P[012])\s*\|"
    r"\s*(?P<file>[^\s|]+\.(?:py|md|yaml|yml|json|toml|cfg|txt|ipynb|sh))\s*\|"
    r"\s*(?P<line>\d*)(?:-\d+)?\s*\|"
    r"\s*(?P<check_id>[A-Z]\d+|—|-)\s*\|"
    r"\s*(?P<message>[^|]+?)\s*\|"
)

# Reversed format: [P1] message text — /absolute/or/relative/path:line[-end]
# Observed from Codex CLI v0.115.0 (e.g., PR #818). The finding message comes
# before the dash separator, and the file path comes after.
_REVERSED_FINDING_RE = re.compile(
    r"[-•*]\s*"  # leading bullet
    r"\[(?P<severity>P[012])\]\s+"
    r"(?P<message>.+?)\s*"
    r"[—–]\s*"  # em/en dash separator (not plain hyphen — too ambiguous)
    r"(?P<file>/[^\s:]+|(?:src|tests|scripts|experiments|notebooks|\.claude)/[^\s:]+)"
    r"(?::(?P<line>\d+)(?:-\d+)?)?"
)

# Prose pattern: file references in natural-language text.
# Matches lines containing a recognizable file path with optional line number,
# used as a last resort when structured formats fail.
# Expanded to handle .sh/.yaml/.yml/.json/.toml/.md/.cfg/.txt extensions.
# Absolute paths are intentionally NOT matched here (risk of false positives
# from system paths in diagnostic context). The reversed-format regex above
# handles absolute paths with [P1] gating.
_PROSE_FILE_REF_RE = re.compile(
    r"(?P<file>(?:src|tests|scripts|experiments|notebooks|\.claude)"
    r"/[^\s:,`\"']+\.(?:py|sh|yaml|yml|json|toml|md|cfg|txt))"
    r"(?::(?P<line>\d+)(?:-\d+)?|(?:\s+line\s+(?P<line2>\d+)))?"
)

# Severity keywords for prose parsing (mapped to severity levels)
_PROSE_SEVERITY_KEYWORDS = {
    "P0": ["critical", "merge conflict", "security", "data corruption"],
    "P1": [
        "bug",
        "unseeded",
        "random.random",
        "falsy",
        "import boundary",
        "determinism",
        "incorrect",
        "wrong",
        "broken",
    ],
    "P2": [
        "style",
        "convention",
        "nit",
        "minor",
        "consider",
        "could",
        "readability",
        "improvement",
    ],
}

# Patterns that indicate a genuinely clean review (no findings expected).
# Each string is one alternative; compiled with | join for readability.
_CLEAN_REVIEW_PATTERN_STRINGS: list[str] = [
    # --- Original patterns ---
    r"no\s+(?:issues?|findings?|problems?|concerns?)(?:\s+found)?",
    r"(?:changes?\s+)?look(?:s)?\s+good",
    r"0\s+findings",
    r"lgtm",
    r"all\s+(?:good|clear|clean)",
    r"ship\s+it",
    r"(?:^|\.\s+)approved(?:\.|\s*$)",
    r"nothing\s+to\s+(?:flag|report|note)",
    r"changes?\s+(?:are\s+)?clean",
    # --- Expanded patterns (PR #799 — Codex uses varied phrasings) ---
    r"no\s+(?:significant|major|critical|blocking)\s+issues?",
    r"no\s+(?:blockers?|violations?)",
    r"everything\s+(?:looks?\s+good|checks?\s+out)",
    r"(?:I\s+)?(?:found|see|find|detect(?:ed)?)\s+no\s+issues?",
    r"(?:I\s+)?(?:don'?t|do\s+not)\s+see\s+(?:any\s+)?issues?",
    r"good\s+to\s+go",
    r"ready\s+to\s+merge",
    r"no\s+(?:action|changes?)\s+(?:needed|required)",
    r"pass(?:es)?\s+all\s+checks",
    r"(?:code|plan|changes?|implementation)\s+(?:is|are)\s+(?:correct|sound|solid)",
    r"(?:looks?|appears?)\s+correct",
    r"nothing\s+(?:stands?\s+out|to\s+(?:add|mention|change))",
    r"no\s+(?:errors?|problems?)\s+detected",
    r"satisfactory",
    r"no\s+(?:items?|things?)\s+to\s+(?:flag|report|address)",
    # --- Empty-diff patterns (stale worktree — Codex sees no changes) ---
    # Exact phrases from observed Codex output on PRs #800, #809, #820:
    r"is\s+empty\s+in\s+this\s+worktree",
    r"no\s+tracked\s+code\s+changes",
    r"no\s+committed\s+changes\s+to\s+review",
    r"no\s+code\s+changes\s+relative\s+to",
    r"no\s+changes\s+to\s+review",
    r"nothing\s+to\s+review",
    # --- Patterns from runtime artifact analysis (parser defang PR) ---
    r"no\s+tracked\s+changes",
    r"does\s+not\s+introduce\s+.{0,60}issue",
    r"no\s+patch\s+to\s+flag",
    r"did\s+not\s+find\s+any\s+(?:discrete|actionable).*bugs?",
    r"no\s+(?:code|functional)\s+changes?",
]

_CLEAN_REVIEW_PATTERNS = re.compile(
    r"(?i)(?:" + "|".join(_CLEAN_REVIEW_PATTERN_STRINGS) + r")"
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
    parse_confidence: str | None = (
        None  # "structured", "clean_signal", "unparseable", "backend_error"
    )

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "findings": [f.to_dict() for f in self.findings],
            "raw_output": self.raw_output,
            "latency_seconds": self.latency_seconds,
            "error": self.error,
            "exit_code": self.exit_code,
            "error_type": self.error_type,
            "parse_confidence": self.parse_confidence,
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

    Handles five output formats (tried in order):
    1. Standard: [P1] file:line — message (C1)
    2. Alternative: [CRITICAL][C1] file:line — message
    3. Markdown table: | CRITICAL | file | line | C1 | message |
    4. Reversed: - [P1] message — /path/to/file:line-range
    5. Prose fallback: natural-language lines containing file references

    Pass 1 (formats 1-3) runs first. Pass 1.5 (format 4, reversed) runs
    only if Pass 1 found nothing, to prevent ambiguity with standard format.
    Pass 2 (format 5, prose) runs only if both Pass 1 and 1.5 found nothing.

    Args:
        raw_output: Raw stdout from Codex CLI.

    Returns:
        List of parsed CodexFinding objects.
    """
    findings: list[CodexFinding] = []
    seen: set[tuple[str, int, str]] = set()

    lines = raw_output.split("\n")

    # Pass 1: structured formats (standard, alt, table)
    for line in lines:
        line = line.strip()
        if not line:
            continue

        finding = (
            _parse_standard_format(line)
            or _parse_alt_format(line)
            or _parse_table_format(line)
        )
        if finding is None:
            continue

        key = (finding.file, finding.line, finding.message)
        if key in seen:
            continue
        seen.add(key)
        findings.append(finding)

    # Pass 1.5: reversed format — only if structured parsing found nothing
    if not findings:
        for line in lines:
            line = line.strip()
            if not line:
                continue

            finding = _parse_reversed_format(line)
            if finding is None:
                continue

            key = (finding.file, finding.line, finding.message)
            if key in seen:
                continue
            seen.add(key)
            findings.append(finding)

    # Pass 2: prose fallback — only if Passes 1 and 1.5 found nothing
    if not findings:
        for line in lines:
            line = line.strip()
            if not line:
                continue

            finding = _parse_prose_finding(line)
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


def _parse_table_format(line: str) -> CodexFinding | None:
    """Parse markdown table row: | SEVERITY | file | line | check | message |."""
    match = _TABLE_ROW_RE.search(line)
    if not match:
        return None

    raw_severity = match.group("severity")
    severity = _SEVERITY_MAP.get(raw_severity, raw_severity)
    file_path = match.group("file")
    line_num = int(match.group("line") or 0)
    message = match.group("message").strip()
    raw_check = match.group("check_id")
    check_id = raw_check if raw_check not in ("—", "-", "") else None

    return CodexFinding(
        severity=severity,
        file=file_path,
        line=line_num,
        category=_categorize_finding(message, check_id),
        check_id=check_id,
        message=message,
    )


def _infer_prose_severity(text: str) -> str:
    """Infer severity from prose context keywords. Defaults to P2."""
    text_lower = text.lower()
    for severity, keywords in _PROSE_SEVERITY_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return severity
    return "P2"


def _strip_to_relative(abs_path: str) -> str:
    """Strip an absolute path to a repo-relative path.

    Uses the current working directory as the repo root. If the path starts
    with the cwd prefix, the prefix is removed. Otherwise returns the path
    unchanged (best-effort).
    """
    cwd = os.getcwd()
    if abs_path.startswith(cwd):
        rel = abs_path[len(cwd) :].lstrip("/")
        return rel if rel else abs_path
    return abs_path


def _parse_reversed_format(line: str) -> CodexFinding | None:
    """Parse reversed format: - [P1] message — /path/to/file:line-range.

    This format is produced by Codex CLI v0.115.0+. The finding message comes
    before the dash separator, and the file path comes after. Line numbers may
    be ranges (e.g., 90-95); only the start line is extracted.
    """
    match = _REVERSED_FINDING_RE.search(line)
    if not match:
        return None

    severity = match.group("severity")
    message = match.group("message").strip()
    file_path = match.group("file")
    line_num = int(match.group("line") or 0)

    # Strip absolute paths to repo-relative
    if file_path.startswith("/"):
        file_path = _strip_to_relative(file_path)

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


def _parse_prose_finding(line: str) -> CodexFinding | None:
    """Extract a finding from prose text containing a file reference.

    Only matches lines with a recognizable src/tests/scripts file path.
    Severity is inferred from surrounding keywords; defaults to P2.
    """
    match = _PROSE_FILE_REF_RE.search(line)
    if not match:
        return None

    file_path = match.group("file")
    line_num = int(match.group("line") or match.group("line2") or 0)

    # Use the full line as the message, trimmed of markdown formatting
    message = re.sub(r"^[\s*\-•]+", "", line).strip()
    message = re.sub(r"[`]", "", message)

    severity = _infer_prose_severity(line)
    check_match = _CHECK_ID_RE.search(line)
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
    3. ``npx @openai/codex`` fallback (downloads if needed)

    Note: The macOS Codex desktop app (``/Applications/Codex.app``) is
    intentionally NOT used as a fallback. Its internal binary launches
    a full Electron GUI rather than running a headless CLI review, causing
    a 300s timeout with no useful output.
    """
    custom_cmd = os.environ.get("CODEX_REVIEW_CMD", "").strip()
    if custom_cmd:
        parts = custom_cmd.split()
        logger.info("Using custom Codex launcher from CODEX_REVIEW_CMD: %s", parts)
        return parts
    if shutil.which("codex"):
        return ["codex"]
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
    from codex_plan_review_adapter import _run_with_pty

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
        returncode, output = _run_with_pty(cmd, timeout=timeout, cwd=cwd)
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

    elapsed = time.monotonic() - start

    if returncode is None:
        logger.warning("Codex CLI timed out after %.1fs", elapsed)
        return CodexReviewResult(
            success=False,
            findings=[],
            raw_output=output,
            latency_seconds=elapsed,
            error=f"Timeout after {timeout}s",
        )

    if returncode != 0:
        # Check for retryable backend interruptions before classifying as error
        if _RETRYABLE_BACKEND_RE.search(output):
            logger.warning(
                "Codex CLI interrupted (exit %d, %.1fs) — treating as advisory",
                returncode,
                elapsed,
            )
            return CodexReviewResult(
                success=True,
                findings=[],
                raw_output=output,
                latency_seconds=elapsed,
                exit_code=returncode,
                parse_confidence="backend_error",
            )

        error_type = _classify_error(output)
        logger.warning(
            "Codex CLI returned exit code %d (%.1fs, %s): %s",
            returncode,
            elapsed,
            error_type,
            output[:200],
        )
        return CodexReviewResult(
            success=False,
            findings=[],
            raw_output=output,
            latency_seconds=elapsed,
            error=f"Exit code {returncode}: {output[:200]}",
            exit_code=returncode,
            error_type=error_type,
        )

    findings = parse_codex_output(output)

    # Determine parse confidence level
    if findings:
        parse_confidence = "structured"
    elif not output.strip():
        parse_confidence = "clean_signal"  # Empty output = nothing to review
    elif _CLEAN_REVIEW_PATTERNS.search(output):
        parse_confidence = "clean_signal"
    else:
        # Output present but no findings parsed and no clean signal.
        # Previously this was success=False (blocking). Now advisory:
        # the raw output is persisted for human inspection.
        parse_confidence = "unparseable"
        logger.warning(
            "Codex CLI returned output (%.1fs, %d chars) but no findings "
            "were parsed and no clean-review signal detected — treating "
            "as advisory (parse_confidence=unparseable)",
            elapsed,
            len(output),
        )

    logger.info(
        "Codex CLI completed (%.1fs): %d findings, parse_confidence=%s",
        elapsed,
        len(findings),
        parse_confidence,
    )
    return CodexReviewResult(
        success=True,
        findings=findings,
        raw_output=output,
        latency_seconds=elapsed,
        exit_code=0,
        parse_confidence=parse_confidence,
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
