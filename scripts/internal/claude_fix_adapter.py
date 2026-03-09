"""Claude fix adapter — applies deterministic fixes from Codex findings.

Takes normalized findings from Codex CLI review and applies
auto-fixable patterns. Records what was changed and commits.

Only handles deterministic, pattern-based fixes. Complex fixes
(logic errors, architectural issues) are left for manual intervention
and recorded as "unfixed" in the summary.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger("claude_fix_adapter")

# Max retries for make check
MAX_MAKE_CHECK_RETRIES = 3


@dataclass
class FixAction:
    """Record of a single fix applied (or skipped)."""

    file: str
    line: int
    check_id: str | None
    original: str
    replacement: str | None  # None = not auto-fixable
    status: str  # "fixed", "skipped", "error"
    reason: str | None = None


@dataclass
class FixSummary:
    """Summary of all fix actions in a round."""

    fixes_applied: int = 0
    fixes_skipped: int = 0
    fixes_errored: int = 0
    commit_sha: str | None = None
    actions: list[FixAction] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "fixes_applied": self.fixes_applied,
            "fixes_skipped": self.fixes_skipped,
            "fixes_errored": self.fixes_errored,
            "commit_sha": self.commit_sha,
            "actions": [asdict(a) for a in self.actions],
        }


# Auto-fixable patterns: (regex, replacement_fn, description)
# Each entry: (compiled_regex, replacement_function(match) -> str)
_AUTO_FIXES: list[tuple[re.Pattern, str, str]] = [
    # == None → is None
    (
        re.compile(r"(\S+)\s*==\s*None\b"),
        r"\1 is None",
        "Use 'is None' instead of '== None'",
    ),
    # != None → is not None
    (
        re.compile(r"(\S+)\s*!=\s*None\b"),
        r"\1 is not None",
        "Use 'is not None' instead of '!= None'",
    ),
    # == True → truthiness (only simple cases)
    (
        re.compile(r"if\s+(\w+)\s*==\s*True\b"),
        r"if \1",
        "Use 'if x:' instead of '== True'",
    ),
    # == False → not x (only simple cases)
    (
        re.compile(r"if\s+(\w+)\s*==\s*False\b"),
        r"if not \1",
        "Use 'if not x:' instead of '== False'",
    ),
    # breakpoint() → remove line (handled specially)
]


def _is_auto_fixable(finding_dict: dict) -> bool:
    """Check if a finding can be auto-fixed."""
    msg = finding_dict.get("message", "").lower()
    check_id = finding_dict.get("check_id")

    # Only auto-fix convention patterns, not correctness issues
    if check_id in ("C1", "C2"):
        return False  # Correctness — needs human review

    # Convention checks (X3 convention patterns)
    if "== none" in msg or "!= none" in msg:
        return True
    if "is none" in msg or "is not none" in msg:
        return True
    if "== true" in msg or "== false" in msg:
        return True
    if "breakpoint()" in msg:
        return True

    return False


def apply_fixes(
    findings: list[dict],
    *,
    repo_root: Path | None = None,
) -> FixSummary:
    """Apply auto-fixable patterns from findings.

    Args:
        findings: Normalized finding dicts (from Codex or prechecks).
        repo_root: Repository root directory.

    Returns:
        FixSummary with actions taken.
    """
    if repo_root is None:
        repo_root = Path.cwd()

    summary = FixSummary()

    # Group findings by file for efficient processing
    by_file: dict[str, list[dict]] = {}
    for f in findings:
        # Only attempt P0/P1 blocking findings
        if f.get("severity") not in ("P0", "P1"):
            continue
        by_file.setdefault(f["file"], []).append(f)

    for file_path, file_findings in by_file.items():
        full_path = repo_root / file_path
        if not full_path.exists():
            for f in file_findings:
                action = FixAction(
                    file=file_path,
                    line=f.get("line", 0),
                    check_id=f.get("check_id"),
                    original="",
                    replacement=None,
                    status="error",
                    reason=f"File not found: {file_path}",
                )
                summary.actions.append(action)
                summary.fixes_errored += 1
            continue

        if not _is_auto_fixable(file_findings[0]):
            # Check each finding individually
            for f in file_findings:
                if _is_auto_fixable(f):
                    _apply_single_fix(f, full_path, summary)
                else:
                    action = FixAction(
                        file=file_path,
                        line=f.get("line", 0),
                        check_id=f.get("check_id"),
                        original=f.get("message", ""),
                        replacement=None,
                        status="skipped",
                        reason="Not auto-fixable — needs manual review",
                    )
                    summary.actions.append(action)
                    summary.fixes_skipped += 1
        else:
            for f in file_findings:
                if _is_auto_fixable(f):
                    _apply_single_fix(f, full_path, summary)
                else:
                    action = FixAction(
                        file=file_path,
                        line=f.get("line", 0),
                        check_id=f.get("check_id"),
                        original=f.get("message", ""),
                        replacement=None,
                        status="skipped",
                        reason="Not auto-fixable — needs manual review",
                    )
                    summary.actions.append(action)
                    summary.fixes_skipped += 1

    return summary


def _apply_single_fix(
    finding: dict,
    full_path: Path,
    summary: FixSummary,
) -> None:
    """Apply a single auto-fix to a file."""
    line_num = finding.get("line", 0)
    message = finding.get("message", "").lower()
    file_path = finding.get("file", str(full_path))

    try:
        content = full_path.read_text()
        lines = content.split("\n")

        if line_num < 1 or line_num > len(lines):
            action = FixAction(
                file=file_path,
                line=line_num,
                check_id=finding.get("check_id"),
                original="",
                replacement=None,
                status="error",
                reason=f"Line {line_num} out of range (file has {len(lines)} lines)",
            )
            summary.actions.append(action)
            summary.fixes_errored += 1
            return

        original_line = lines[line_num - 1]
        new_line = original_line

        if "breakpoint()" in message:
            # Remove breakpoint() lines entirely
            if "breakpoint()" in original_line:
                new_line = ""  # Will be removed
                action = FixAction(
                    file=file_path,
                    line=line_num,
                    check_id=finding.get("check_id"),
                    original=original_line.strip(),
                    replacement="<removed>",
                    status="fixed",
                )
                # Remove the line
                lines[line_num - 1] = None  # type: ignore[assignment]
                lines = [ln for ln in lines if ln is not None]
                full_path.write_text("\n".join(lines))
                summary.actions.append(action)
                summary.fixes_applied += 1
                return

        # Apply pattern-based fixes
        for pattern, replacement, _desc in _AUTO_FIXES:
            if pattern.search(original_line):
                new_line = pattern.sub(replacement, original_line)
                break

        if new_line != original_line:
            lines[line_num - 1] = new_line
            full_path.write_text("\n".join(lines))
            action = FixAction(
                file=file_path,
                line=line_num,
                check_id=finding.get("check_id"),
                original=original_line.strip(),
                replacement=new_line.strip(),
                status="fixed",
            )
            summary.actions.append(action)
            summary.fixes_applied += 1
        else:
            action = FixAction(
                file=file_path,
                line=line_num,
                check_id=finding.get("check_id"),
                original=original_line.strip(),
                replacement=None,
                status="skipped",
                reason="Pattern not matched on line",
            )
            summary.actions.append(action)
            summary.fixes_skipped += 1

    except Exception as e:
        action = FixAction(
            file=file_path,
            line=line_num,
            check_id=finding.get("check_id"),
            original="",
            replacement=None,
            status="error",
            reason=str(e),
        )
        summary.actions.append(action)
        summary.fixes_errored += 1


def commit_fixes(
    summary: FixSummary,
    pr_number: int,
    iteration: int,
    *,
    repo_root: Path | None = None,
) -> str | None:
    """Stage and commit applied fixes.

    Args:
        summary: Fix summary with applied actions.
        pr_number: PR number for commit message.
        iteration: Current iteration number.
        repo_root: Repository root directory.

    Returns:
        Commit SHA if changes were committed, None otherwise.
    """
    if summary.fixes_applied == 0:
        logger.info("No fixes applied — nothing to commit")
        return None

    if repo_root is None:
        repo_root = Path.cwd()

    # Stage changed files
    changed_files = {a.file for a in summary.actions if a.status == "fixed"}
    for f in changed_files:
        result = subprocess.run(
            ["git", "add", f],
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
        if result.returncode != 0:
            logger.warning("Failed to stage %s: %s", f, result.stderr)

    # Commit
    msg = (
        f"fix: address {summary.fixes_applied} Codex finding(s) "
        f"(PR #{pr_number}, round {iteration})"
    )
    result = subprocess.run(
        ["git", "commit", "-m", msg],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    if result.returncode != 0:
        logger.warning("Commit failed: %s", result.stderr)
        return None

    # Get commit SHA
    sha_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    sha = sha_result.stdout.strip() if sha_result.returncode == 0 else None
    summary.commit_sha = sha
    logger.info("Committed fixes: %s", sha)
    return sha


def push_fixes(
    branch: str,
    *,
    repo_root: Path | None = None,
) -> bool:
    """Push committed fixes to remote.

    Args:
        branch: Branch name to push.
        repo_root: Repository root directory.

    Returns:
        True if push succeeded, False otherwise.
    """
    if repo_root is None:
        repo_root = Path.cwd()

    result = subprocess.run(
        ["git", "push", "origin", branch],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    if result.returncode != 0:
        logger.warning("Push failed: %s", result.stderr)
        return False
    logger.info("Pushed fixes to origin/%s", branch)
    return True


def run_make_check(*, repo_root: Path | None = None) -> bool:
    """Run make check and return success status.

    Args:
        repo_root: Repository root directory.

    Returns:
        True if make check passes, False otherwise.
    """
    if repo_root is None:
        repo_root = Path.cwd()

    result = subprocess.run(
        ["make", "check-quiet"],
        capture_output=True,
        text=True,
        cwd=repo_root,
        timeout=600,  # 10 minute timeout
    )
    if result.returncode == 0:
        logger.info("make check passed")
        return True
    else:
        logger.warning("make check failed (rc=%d)", result.returncode)
        return False


def save_fix_summary(
    summary: FixSummary,
    pr_number: int,
    iteration: int,
    base_dir: Path | None = None,
) -> Path:
    """Save fix summary to the round directory.

    Args:
        summary: Fix summary to save.
        pr_number: PR number.
        iteration: Current iteration number.
        base_dir: Override for state persistence directory.

    Returns:
        Path to the saved JSON file.
    """
    from review_state import round_dir

    rdir = round_dir(pr_number, iteration, base_dir)
    rdir.mkdir(parents=True, exist_ok=True)

    # Save JSON
    path = rdir / "fix_summary.json"
    with open(path, "w") as f:
        json.dump(summary.to_dict(), f, indent=2)

    # Save human-readable markdown
    md_path = rdir / "claude_fix_summary.md"
    with open(md_path, "w") as f:
        f.write(f"# Fix Summary — Round {iteration}\n\n")
        f.write(f"- Fixes applied: {summary.fixes_applied}\n")
        f.write(f"- Fixes skipped: {summary.fixes_skipped}\n")
        f.write(f"- Fixes errored: {summary.fixes_errored}\n")
        if summary.commit_sha:
            f.write(f"- Commit: {summary.commit_sha}\n")
        f.write("\n## Actions\n\n")
        f.write("| Status | File | Line | Check | Detail |\n")
        f.write("|--------|------|------|-------|--------|\n")
        for a in summary.actions:
            detail = a.reason or f"`{a.original}` → `{a.replacement}`"
            f.write(
                f"| {a.status} | {a.file} | {a.line} | "
                f"{a.check_id or '-'} | {detail} |\n"
            )

    return path
