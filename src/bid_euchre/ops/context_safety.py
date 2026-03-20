"""Context-safety scanning for promoted operator content.

Gates memory promotion, summary auto-load, and skill promotion by
scanning candidate content for unsafe patterns before they enter
high-autonomy paths.

Every piece of content is classified as:
- **allow** — safe to promote/auto-load
- **warn** — non-blocking concern; content is persisted with a warning tag
- **reject** — blocked; content must not be promoted

Built-in rules detect:
- Secrets / token-like material (API keys, passwords)
- Shell injection patterns (backtick execution, $() subshells)
- Path traversal (../ sequences, absolute paths outside repo)
- Missing provenance (no source_file or added_by)
- Oversized content (exceeding configurable threshold)
- Binary / non-text content (null bytes, non-UTF-8)

Usage::

    from bid_euchre.ops.context_safety import scan_content, scan_memory_entry

    result = scan_content("some text", {"source_file": "CLAUDE.md", "added_by": "ops"})
    if result.outcome == "reject":
        raise ValueError(f"Content blocked: {result.findings}")
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Literal

if TYPE_CHECKING:
    from bid_euchre.ops.memory import MemoryEntry

logger = logging.getLogger("ops.context_safety")

# ── Default thresholds ──────────────────────────────────────────

DEFAULT_MAX_CONTENT_BYTES = 10_240  # 10 KB


# ── Data contracts ──────────────────────────────────────────────


@dataclass
class ScanFinding:
    """A single finding from a context-safety rule."""

    rule_id: str
    severity: Literal["warn", "reject"]
    message: str
    location: str | None = None  # line number, byte offset, or None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "message": self.message,
            "location": self.location,
        }


@dataclass
class ScanResult:
    """Aggregate result of scanning one piece of content."""

    outcome: Literal["allow", "warn", "reject"]
    findings: list[ScanFinding] = field(default_factory=list)
    content_hash: str = ""  # SHA-256 hex digest for audit trail

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "content_hash": self.content_hash,
            "findings": [f.to_dict() for f in self.findings],
        }


# Type alias for rule check functions
RuleCheck = Callable[[str, dict[str, Any]], list[ScanFinding]]


@dataclass
class Rule:
    """A named safety rule."""

    rule_id: str
    description: str
    check: RuleCheck
    severity: Literal["warn", "reject"]


# ── Built-in rules ─────────────────────────────────────────────

# Patterns that look like API keys, tokens, or passwords.
# Intentionally broad — false positives are acceptable for a safety gate.
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "API key prefix",
        re.compile(r"\b(?:sk|pk|api[_-]?key)[_-][A-Za-z0-9_\-]{16,}", re.I),
    ),
    ("Bearer token", re.compile(r"\bBearer\s+[A-Za-z0-9_\-.]{20,}", re.I)),
    ("AWS key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "Generic secret assignment",
        re.compile(
            r"""(?:password|secret|token|api_key|apikey|auth_token|access_token)"""
            r"""\s*[=:]\s*["'][^"']{8,}["']""",
            re.I,
        ),
    ),
    (
        "GitHub token",
        re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}\b"),
    ),
    (
        "Base64-encoded secret block",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----"),
    ),
]


def _check_secrets(content: str, _metadata: dict[str, Any]) -> list[ScanFinding]:
    """Detect secret-like patterns in content."""
    findings: list[ScanFinding] = []
    for label, pattern in _SECRET_PATTERNS:
        for match in pattern.finditer(content):
            # Find approximate line number
            line_no = content[: match.start()].count("\n") + 1
            findings.append(
                ScanFinding(
                    rule_id="secret_pattern",
                    severity="reject",
                    message=f"Potential secret detected ({label})",
                    location=f"line {line_no}",
                )
            )
    return findings


# Shell injection patterns: backtick execution, $() subshells, dangerous commands.
#
# Design notes on false-positive mitigation:
# - Backtick/subshell patterns use \b anchors on both sides of command names
#   to avoid matching words like "push", "stash", "hash", "crash" that end
#   in "sh".  Only whole-word matches of dangerous commands are flagged.
# - Triple-backtick code fences (```...```) are excluded by requiring the
#   backtick pattern to match single backticks only (no ` preceded by ``).
# - The "dangerous pipe" pattern requires the pipe NOT to be at the start of
#   a line (which would indicate a markdown table cell), reducing false
#   positives for content like "| bash | description |".
_SHELL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "Backtick execution",
        # Single-backtick inline code containing a dangerous command.
        # Negative lookbehind (?<!`) excludes triple-backtick fences.
        re.compile(r"(?<!`)`(?!`)[^`]*\b(?:rm|curl|wget|eval)\b[^`]*`"),
    ),
    (
        "Subshell execution",
        re.compile(r"\$\([^)]*\b(?:rm|curl|wget|eval)\b[^)]*\)"),
    ),
    (
        "Dangerous pipe",
        # Pipe to shell — but not at line start (markdown table cells).
        re.compile(r"(?<!^)\|\s*\b(?:sh|bash|zsh|eval)\b", re.M),
    ),
    (
        "Curl-to-shell",
        re.compile(r"curl\s+[^\n]*\|\s*\b(?:sh|bash|sudo)\b", re.I),
    ),
]


def _check_shell_injection(
    content: str, _metadata: dict[str, Any]
) -> list[ScanFinding]:
    """Detect shell injection patterns in content."""
    findings: list[ScanFinding] = []
    for label, pattern in _SHELL_PATTERNS:
        for match in pattern.finditer(content):
            line_no = content[: match.start()].count("\n") + 1
            findings.append(
                ScanFinding(
                    rule_id="shell_injection",
                    severity="reject",
                    message=f"Shell injection pattern detected ({label})",
                    location=f"line {line_no}",
                )
            )
    return findings


# Path traversal: ../ sequences or absolute paths outside repo
_PATH_TRAVERSAL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "Directory traversal",
        re.compile(r"(?:\.\./){2,}"),  # Two or more ../
    ),
    (
        "Sensitive absolute path",
        re.compile(r"(?:/etc/(?:passwd|shadow|hosts)|/root/|/var/log/)"),
    ),
]


def _check_path_traversal(content: str, _metadata: dict[str, Any]) -> list[ScanFinding]:
    """Detect path traversal patterns in content."""
    findings: list[ScanFinding] = []
    for label, pattern in _PATH_TRAVERSAL_PATTERNS:
        for match in pattern.finditer(content):
            line_no = content[: match.start()].count("\n") + 1
            findings.append(
                ScanFinding(
                    rule_id="path_traversal",
                    severity="reject",
                    message=f"Path traversal detected ({label})",
                    location=f"line {line_no}",
                )
            )
    return findings


def _check_missing_provenance(
    _content: str, metadata: dict[str, Any]
) -> list[ScanFinding]:
    """Check that provenance fields are present in metadata."""
    findings: list[ScanFinding] = []
    if not metadata.get("source_file"):
        findings.append(
            ScanFinding(
                rule_id="missing_provenance",
                severity="reject",
                message="Missing required provenance field: source_file",
            )
        )
    if not metadata.get("added_by"):
        findings.append(
            ScanFinding(
                rule_id="missing_provenance",
                severity="reject",
                message="Missing required provenance field: added_by",
            )
        )
    return findings


def _check_oversized(content: str, metadata: dict[str, Any]) -> list[ScanFinding]:
    """Check if content exceeds the size threshold."""
    max_bytes = metadata.get("max_content_bytes", DEFAULT_MAX_CONTENT_BYTES)
    content_bytes = len(content.encode("utf-8", errors="replace"))
    if content_bytes > max_bytes:
        return [
            ScanFinding(
                rule_id="oversized_content",
                severity="warn",
                message=(
                    f"Content is {content_bytes:,} bytes, "
                    f"exceeding threshold of {max_bytes:,} bytes"
                ),
            )
        ]
    return []


def _check_binary(content: str, _metadata: dict[str, Any]) -> list[ScanFinding]:
    """Check for binary / non-text content (null bytes)."""
    if "\x00" in content:
        pos = content.index("\x00")
        return [
            ScanFinding(
                rule_id="binary_content",
                severity="reject",
                message="Binary content detected (null byte found)",
                location=f"byte {pos}",
            )
        ]
    return []


# ── Rule registry ───────────────────────────────────────────────

DEFAULT_RULES: list[Rule] = [
    Rule(
        rule_id="secret_pattern",
        description="Detect API keys, tokens, passwords, and private keys",
        check=_check_secrets,
        severity="reject",
    ),
    Rule(
        rule_id="shell_injection",
        description="Detect shell injection and dangerous execution patterns",
        check=_check_shell_injection,
        severity="reject",
    ),
    Rule(
        rule_id="path_traversal",
        description="Detect path traversal and access to sensitive system paths",
        check=_check_path_traversal,
        severity="reject",
    ),
    Rule(
        rule_id="missing_provenance",
        description="Require source_file and added_by provenance metadata",
        check=_check_missing_provenance,
        severity="reject",
    ),
    Rule(
        rule_id="oversized_content",
        description="Warn when content exceeds size threshold",
        check=_check_oversized,
        severity="warn",
    ),
    Rule(
        rule_id="binary_content",
        description="Reject binary / non-text content",
        check=_check_binary,
        severity="reject",
    ),
]


# ── Scanning ────────────────────────────────────────────────────


def _compute_hash(content: str) -> str:
    """Compute SHA-256 hash of content for audit trail."""
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()


def scan_content(
    content: str,
    metadata: dict[str, Any] | None = None,
    *,
    rules: list[Rule] | None = None,
) -> ScanResult:
    """Scan content for safety issues.

    Args:
        content: The text content to scan.
        metadata: Provenance and configuration metadata. Keys used:
            - ``source_file`` (str): Where this content comes from.
            - ``added_by`` (str): Who/what is promoting this content.
            - ``max_content_bytes`` (int): Override size threshold.
        rules: Custom rule list. Defaults to ``DEFAULT_RULES``.

    Returns:
        ScanResult with outcome (allow/warn/reject), findings, and content hash.
    """
    if metadata is None:
        metadata = {}
    if rules is None:
        rules = DEFAULT_RULES

    content_hash = _compute_hash(content)
    all_findings: list[ScanFinding] = []

    for rule in rules:
        try:
            findings = rule.check(content, metadata)
            all_findings.extend(findings)
        except Exception:
            logger.exception("Rule '%s' raised an exception", rule.rule_id)
            all_findings.append(
                ScanFinding(
                    rule_id=rule.rule_id,
                    severity="reject",
                    message=f"Rule '{rule.rule_id}' failed with an internal error",
                )
            )

    # Determine outcome: reject > warn > allow
    if any(f.severity == "reject" for f in all_findings):
        outcome: Literal["allow", "warn", "reject"] = "reject"
    elif any(f.severity == "warn" for f in all_findings):
        outcome = "warn"
    else:
        outcome = "allow"

    return ScanResult(
        outcome=outcome,
        findings=all_findings,
        content_hash=content_hash,
    )


def scan_memory_entry(entry: MemoryEntry) -> ScanResult:
    """Scan a MemoryEntry for safety issues.

    Extracts the entry's value and provenance metadata for scanning.

    Args:
        entry: A MemoryEntry instance from ``ops.memory``.

    Returns:
        ScanResult with outcome, findings, and content hash.
    """
    metadata = {
        "source_file": entry.source_file,
        "added_by": entry.added_by,
    }
    return scan_content(entry.value, metadata)


# ── Formatting ──────────────────────────────────────────────────


def format_scan_text(result: ScanResult) -> str:
    """Format a scan result as human-readable text."""
    icon = {"allow": "✓", "warn": "⚠", "reject": "✗"}.get(result.outcome, "?")
    lines = [f"{icon} Scan outcome: {result.outcome.upper()}"]

    if result.content_hash:
        lines.append(f"  Content hash: {result.content_hash[:16]}...")

    if not result.findings:
        lines.append("  No findings.")
    else:
        lines.append(f"  Findings ({len(result.findings)}):")
        for f in result.findings:
            loc = f" at {f.location}" if f.location else ""
            lines.append(f"    [{f.severity.upper():6s}] {f.rule_id}: {f.message}{loc}")

    return "\n".join(lines)


def format_scan_json(result: ScanResult) -> dict[str, Any]:
    """Format a scan result as a JSON-serializable dict."""
    return result.to_dict()
