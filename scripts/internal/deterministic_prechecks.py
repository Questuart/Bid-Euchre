"""Deterministic prechecks for code review.

Fast, local checks extracted from /reviewing-changes Phases 0-2.
Both the /reviewing-changes skill AND the autonomous review loop
state machine call this module.

Returns structured findings in the same schema as Codex findings,
enabling uniform treatment downstream.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Finding:
    """A single precheck finding."""

    severity: str  # "P0", "P1", "P2"
    file: str
    line: int
    category: str  # "correctness", "convention", "process"
    check_id: str  # "C1", "C2", "X3", etc.
    message: str
    raw_source: str = "deterministic_precheck"

    def to_dict(self) -> dict:
        return asdict(self)


# Patterns for convention checks (WARN severity in /reviewing-changes)
_CONVENTION_PATTERNS: list[tuple[str, str, str]] = [
    # (regex, check_id, message)
    (r"\bbreakpoint\(\)", "X3", "breakpoint() call in code"),
    (r"==\s*None\b", "X3", "Use 'is None' instead of '== None'"),
    (r"!=\s*None\b", "X3", "Use 'is not None' instead of '!= None'"),
    (r"==\s*True\b", "X3", "Use 'if x:' instead of '== True'"),
    (r"==\s*False\b", "X3", "Use 'if not x:' instead of '== False'"),
    (r'\bprint\(f?"(?:DEBUG|>>>)', "X3", "Debug print statement in code"),
    (r"\btype\(\w+\)\s*==\s*", "X3", "Use isinstance() instead of type() =="),
]

# Merge conflict markers
_MERGE_MARKER_RE = re.compile(r"^(<{7}|>{7}|={7})(\s|$)", re.MULTILINE)

# Import boundary: src/ importing from experiments/ or tests/
_IMPORT_BOUNDARY_RE = re.compile(
    r"^\s*(?:from|import)\s+(?:experiments|tests)\b", re.MULTILINE
)

# X3 check: detects leftover "remove-before-merge" TODO markers
_TODO_REMOVE_RE = re.compile(r"TODO:\s*remove before merge", re.IGNORECASE)

# Large commented-out blocks (>10 consecutive comment lines)
_COMMENT_BLOCK_RE = re.compile(r"((?:^[ \t]*#[^\n]*\n){11,})", re.MULTILINE)

# Falsy numeric guard: x = x or fallback (C2)
_FALSY_GUARD_RE = re.compile(r"\b(\w+)\s*=\s*\1\s+or\s+(?:\d+\.?\d*|default_\w+)")

# --- N1: Missing contract-type facet (notebooks only) ---
# Matches groupby(...) followed by aggregation/plot methods on the same line
_N1_GROUPBY_RE = re.compile(
    r"\.groupby\([^)]*\)\s*(?:\[[^\]]*\])?\s*\." r"(?:mean|sum|plot|bar|box)\b"
)
# Terms that indicate contract-type faceting is present
_N1_EXEMPT_RE = re.compile(r"\bcontract_type\b|\bct\b")

# --- N2: Collapsed matchup table (notebooks only) ---
# Matches .groupby('matchup') or .groupby("matchup") without 'team' in the expression
_N2_COLLAPSED_RE = re.compile(r"""\.groupby\(\s*['"]matchup['"]\s*\)""")

# --- N3: Inference claim without statistical test (notebooks only) ---
_N3_CLAIM_RE = re.compile(
    r"\b(outperform(?:s|ed)?|better\s+than|significant(?:ly)?|superior)\b",
    re.IGNORECASE,
)
_N3_STATS_RE = re.compile(
    r"\b(p_value|p-value|ttest|t_test|f_oneway|bootstrap|confidence.interval|CI)\b",
    re.IGNORECASE,
)

# --- C5: Redundant except catch ---
# Detects `except (Specific, ..., Exception)` where Exception makes the
# specific catches redundant.  Observed in PR #1075 where
# `except (json.JSONDecodeError, Exception)` silently swallowed all errors.
_EXCEPT_TUPLE_RE = re.compile(r"except\s*\(([^)]+)\)")

# --- X2: Undocumented contract change (diff-level) ---
_X2_CONTRACT_PATHS = (
    "src/bid_euchre/core/rules.py",
    "src/bid_euchre/scoring.py",
)
_X2_CONTRACT_PREFIX = "src/bid_euchre/logging/"
_X2_DOC_PREFIX = "docs/01_core/"


def check_file(
    file_path: str,
    content: str,
    *,
    is_library: bool = False,
    mode: str = "standard",
) -> list[Finding]:
    """Run all deterministic checks on a single file's content.

    Args:
        file_path: Relative path to the file being checked.
        content: The file's text content.
        is_library: True if file is under src/ (enables library-only checks).
        mode: Review mode — "standard", "report-audit", or "plan-audit".

    Returns:
        List of Finding objects.
    """
    findings: list[Finding] = []
    lines = content.split("\n")

    # --- P0: Merge conflict markers ---
    for i, line in enumerate(lines, 1):
        if _MERGE_MARKER_RE.match(line):
            findings.append(
                Finding(
                    severity="P0",
                    file=file_path,
                    line=i,
                    category="process",
                    check_id="X3",
                    message="Merge conflict marker — invalid syntax",
                )
            )

    # --- P1: TODO remove before merge ---
    for i, line in enumerate(lines, 1):
        if _TODO_REMOVE_RE.search(line):
            findings.append(
                Finding(
                    severity="P1",
                    file=file_path,
                    line=i,
                    category="process",
                    check_id="X3",
                    message="'TODO-remove-before-merge' marker",
                )
            )

    # --- P1: Large commented-out blocks ---
    for match in _COMMENT_BLOCK_RE.finditer(content):
        block_start = content[: match.start()].count("\n") + 1
        block_lines = match.group().count("\n")
        findings.append(
            Finding(
                severity="P1",
                file=file_path,
                line=block_start,
                category="process",
                check_id="X3",
                message=f"Large commented-out block ({block_lines} lines)",
            )
        )

    # --- Library-only checks (src/) ---
    if is_library:
        # C1: Unseeded randomness
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Skip comments
            if stripped.startswith("#"):
                continue
            if "random.Random()" in line and "seed" not in line.lower():
                findings.append(
                    Finding(
                        severity="P1",
                        file=file_path,
                        line=i,
                        category="correctness",
                        check_id="C1",
                        message="Unseeded random.Random() — non-deterministic",
                    )
                )
            # Global random.* calls (not on a local rng variable)
            if re.search(
                r"\brandom\.(choice|shuffle|randint|random|sample|uniform)\b",
                line,
            ) and not re.search(r"\b(rng|self\.\w*rng)\.", line):
                findings.append(
                    Finding(
                        severity="P1",
                        file=file_path,
                        line=i,
                        category="correctness",
                        check_id="C1",
                        message="Global random.* call — use seeded local RNG",
                    )
                )

        # C2: Falsy numeric guard
        for i, line in enumerate(lines, 1):
            if line.strip().startswith("#"):
                continue
            if _FALSY_GUARD_RE.search(line):
                findings.append(
                    Finding(
                        severity="P1",
                        file=file_path,
                        line=i,
                        category="correctness",
                        check_id="C2",
                        message="Falsy numeric guard — 0.0 is falsy, use 'if x is None'",
                    )
                )

        # Import boundary: src/ must not import from experiments/ or tests/
        for i, line in enumerate(lines, 1):
            if line.strip().startswith("#"):
                continue
            if _IMPORT_BOUNDARY_RE.match(line):
                findings.append(
                    Finding(
                        severity="P1",
                        file=file_path,
                        line=i,
                        category="correctness",
                        check_id="X3",
                        message="Import boundary violation — src/ importing from experiments/ or tests/",
                    )
                )

    # --- Notebook-only checks (N1, N2, N3) ---
    is_notebook = "notebooks/" in file_path

    if is_notebook:
        # N1: Missing contract-type facet in groupby/plot
        for i, line in enumerate(lines, 1):
            if _N1_GROUPBY_RE.search(line):
                # Check ±3 lines for contract_type or ct
                window_start = max(0, i - 1 - 3)  # i is 1-indexed
                window_end = min(len(lines), i - 1 + 4)  # +3 after current
                window = "\n".join(lines[window_start:window_end])
                if not _N1_EXEMPT_RE.search(window):
                    findings.append(
                        Finding(
                            severity="P2",
                            file=file_path,
                            line=i,
                            category="process",
                            check_id="N1",
                            message="Missing contract-type facet in groupby/plot",
                        )
                    )

        # N2: Collapsed matchup table (groupby matchup without team)
        for i, line in enumerate(lines, 1):
            if _N2_COLLAPSED_RE.search(line) and "team" not in line:
                findings.append(
                    Finding(
                        severity="P2",
                        file=file_path,
                        line=i,
                        category="process",
                        check_id="N2",
                        message="Collapsed matchup table — groupby('matchup') without team",
                    )
                )

        # N3: Inference claim without statistical test
        for i, line in enumerate(lines, 1):
            if _N3_CLAIM_RE.search(line):
                # Check ±10 lines for stats patterns
                window_start = max(0, i - 1 - 10)
                window_end = min(len(lines), i - 1 + 11)
                window = "\n".join(lines[window_start:window_end])
                if not _N3_STATS_RE.search(window):
                    findings.append(
                        Finding(
                            severity="P2",
                            file=file_path,
                            line=i,
                            category="process",
                            check_id="N3",
                            message="Inference claim without statistical test nearby",
                        )
                    )

    # --- C5: Redundant except catch (P2 — non-blocking) ---
    # Catches `except (Specific, ..., Exception)` where Exception renders
    # the specific catches redundant.  See PR #1075.
    for i, line in enumerate(lines, 1):
        if line.strip().startswith("#"):
            continue
        match = _EXCEPT_TUPLE_RE.search(line)
        if match:
            types_str = match.group(1)
            if "," in types_str and re.search(r"\bException\b", types_str):
                findings.append(
                    Finding(
                        severity="P2",
                        file=file_path,
                        line=i,
                        category="correctness",
                        check_id="C5",
                        message=(
                            "Redundant except — Exception in tuple makes "
                            "specific catches redundant"
                        ),
                    )
                )

    # --- Convention checks (P2 — non-blocking) ---
    for i, line in enumerate(lines, 1):
        if line.strip().startswith("#"):
            continue
        for pattern, check_id, message in _CONVENTION_PATTERNS:
            if re.search(pattern, line):
                findings.append(
                    Finding(
                        severity="P2",
                        file=file_path,
                        line=i,
                        category="convention",
                        check_id=check_id,
                        message=message,
                    )
                )

    return findings


def check_diff(
    base: str = "origin/main",
    *,
    mode: str = "standard",
    repo_root: Path | None = None,
    changed_files: list[str] | None = None,
) -> list[Finding]:
    """Run deterministic prechecks on all files changed vs base.

    Args:
        base: Git ref to diff against (ignored when *changed_files* is provided).
        mode: Review mode.
        repo_root: Repository root directory (defaults to cwd).
        changed_files: PR-scoped file list.  When provided, skip the local
            ``git diff`` and use this list directly.  This avoids scope leaks
            where the local worktree has drifted from the PR branch.

    Returns:
        List of Finding objects across all changed files.
    """
    if repo_root is None:
        repo_root = Path.cwd()

    # Use PR-scoped file list when available; fall back to local git diff.
    if changed_files is None:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
        if result.returncode != 0:
            return [
                Finding(
                    severity="P0",
                    file="<git>",
                    line=0,
                    category="process",
                    check_id="X3",
                    message=f"git diff failed (rc={result.returncode}): {result.stderr.strip()[:200]}",
                )
            ]

        changed_files = [
            f.strip() for f in result.stdout.strip().split("\n") if f.strip()
        ]
    all_findings: list[Finding] = []

    for file_path in changed_files:
        # Only check Python files
        if not file_path.endswith(".py"):
            continue

        full_path = repo_root / file_path
        if not full_path.exists():
            continue

        content = full_path.read_text()
        is_library = file_path.startswith("src/")

        all_findings.extend(
            check_file(file_path, content, is_library=is_library, mode=mode)
        )

    # X2: Undocumented contract change (diff-level)
    all_findings.extend(_check_undocumented_contract_change(changed_files))

    # T1: Untested behavior change (diff-level)
    all_findings.extend(_check_untested_behavior_change(changed_files))

    # Plan-audit mode: check referenced file paths exist
    if mode == "plan-audit":
        all_findings.extend(_check_plan_paths(changed_files, repo_root))

    return all_findings


def _check_undocumented_contract_change(
    changed_files: list[str],
) -> list[Finding]:
    """X2: Flag changes to core rules/scoring/logging without doc updates."""
    contract_files = [
        f
        for f in changed_files
        if f in _X2_CONTRACT_PATHS or f.startswith(_X2_CONTRACT_PREFIX)
    ]
    if not contract_files:
        return []

    has_doc_update = any(
        f.startswith(_X2_DOC_PREFIX) and f.endswith(".md") for f in changed_files
    )
    if has_doc_update:
        return []

    return [
        Finding(
            severity="P2",
            file=cf,
            line=0,
            category="process",
            check_id="X2",
            message=(
                "Contract file changed without docs/01_core/ update — "
                "add documentation or confirm no contract change"
            ),
        )
        for cf in contract_files
    ]


def _check_untested_behavior_change(
    changed_files: list[str],
) -> list[Finding]:
    """T1: Flag library behavior changes without corresponding test changes.

    If any ``.py`` file under ``src/`` (excluding ``__init__.py``) is changed
    but no ``.py`` file under ``tests/`` is changed, emit a P2 advisory
    finding.  This pattern has been a repeated real miss across fix-batch
    PRs #977, #1000, and #1015 where post-merge reviews added missing tests.
    """
    src_py_files = [
        f
        for f in changed_files
        if f.startswith("src/") and f.endswith(".py") and not f.endswith("__init__.py")
    ]
    if not src_py_files:
        return []

    has_test_changes = any(
        f.startswith("tests/") and f.endswith(".py") for f in changed_files
    )
    if has_test_changes:
        return []

    # Emit one finding pointing at the first changed library file
    return [
        Finding(
            severity="P2",
            file=src_py_files[0],
            line=0,
            category="process",
            check_id="T1",
            message=(
                "Library code changed without test changes — "
                "verify behavior is covered by existing tests"
            ),
        )
    ]


def _check_plan_paths(changed_files: list[str], repo_root: Path) -> list[Finding]:
    """For plan-audit mode: verify that file paths referenced in plan files exist."""
    findings: list[Finding] = []
    for file_path in changed_files:
        if not file_path.endswith(".md"):
            continue
        # Only check files under plans/
        if not file_path.startswith("plans/"):
            continue

        full_path = repo_root / file_path
        if not full_path.exists():
            continue

        content = full_path.read_text()
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            # Look for backtick-quoted paths
            for match in re.finditer(r"`([^`]+\.\w+)`", line):
                ref_path = match.group(1)
                # Skip URLs, globs, and placeholder patterns
                if any(c in ref_path for c in ("://", "*", "{", "}", "<", ">")):
                    continue
                # Skip paths that look like they're being created
                if any(
                    marker in line.lower()
                    for marker in ("create", "new file", "add", "write")
                ):
                    continue
                ref_full = repo_root / ref_path
                if not ref_full.exists() and not ref_path.startswith("data/"):
                    findings.append(
                        Finding(
                            severity="P1",
                            file=file_path,
                            line=i,
                            category="process",
                            check_id="P1",
                            message=f"Referenced path does not exist: {ref_path}",
                        )
                    )

    return findings


def get_blocking_findings(findings: list[Finding]) -> list[Finding]:
    """Filter to only P0/P1 findings (blocking)."""
    from review_common import is_blocking_severity

    return [f for f in findings if is_blocking_severity(f.severity)]
