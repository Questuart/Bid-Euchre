"""Deterministic prechecks for code review.

Fast, local checks extracted from /reviewing-changes Phases 0-2.
Both the /reviewing-changes skill AND the autonomous review loop
state machine call this module.

Returns structured findings in the same schema as Codex findings,
enabling uniform treatment downstream.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Callable
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

# --- String-literal masking ---
# Replace content inside triple-quoted strings with blank lines so that test
# fixture strings (containing merge markers, TODO, breakpoint, etc.) do not
# trigger false-positive findings.  Line count is preserved for accurate
# line-number reporting.
_TRIPLE_QUOTE_RE = re.compile(r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')')


def _mask_string_literals(content: str) -> str:
    """Replace triple-quoted string interiors with blank lines."""
    return _TRIPLE_QUOTE_RE.sub(lambda m: "\n" * m.group().count("\n"), content)


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
    # Mask triple-quoted string interiors to avoid false positives on test fixtures
    masked = _mask_string_literals(content)
    lines = masked.split("\n")

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
    for match in _COMMENT_BLOCK_RE.finditer(masked):
        block_start = masked[: match.start()].count("\n") + 1
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
    commit_messages: list[str] | None = None,
    pr_body: str | None = None,
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

    # Plan-audit mode: check referenced file paths exist.
    #
    # Exclusion: when the PR diff touches ONLY markdown files under plans/**,
    # skip the path-existence precheck.  Governance plan prose frequently
    # mentions filenames conversationally (e.g. `task_queue.py`, `ops/dashboard.py`
    # in discussion) that the precheck misinterprets as asserted repo-root
    # paths.  On pure governance-plan PRs this pattern produced 20–130
    # false-positive findings with zero actual blockers (see issue #2761).
    # Mixed PRs (plans + code) still run the check — the heuristic is narrow
    # so code-changing diffs never bypass path validation.
    if mode == "plan-audit":
        if _should_run_path_existence_check(changed_files):
            all_findings.extend(_check_plan_paths(changed_files, repo_root))
        else:
            all_findings.append(
                Finding(
                    severity="P2",
                    file="<plan-audit>",
                    line=0,
                    category="process",
                    check_id="PX",
                    message=(
                        "path-existence check skipped: PR touches only "
                        "plans/**/*.md files (per #2761 exclusion — prose "
                        "path references in governance plans are not "
                        "asserted repo-root paths)"
                    ),
                )
            )

    # V1–V6: verification-contract prechecks (Pattern 10, §10.9 governing plan).
    all_findings.extend(
        check_verification_contract(
            changed_files,
            repo_root,
            commit_messages=commit_messages,
            pr_body=pr_body,
        )
    )

    # V7: commit-policy precheck (Primitive C / ADR 010 binding).  Gated
    # behind the ``ENABLE_V7_COMMIT_POLICY`` env flag (default off until
    # Primitive A archivist event emission is live — see
    # plans/steward_platform/3_primitive_C/shaping.md §4.6 + §6.3).
    all_findings.extend(
        check_v7_commit_policy(
            changed_files,
            repo_root,
            pr_body=pr_body,
        )
    )

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


def _should_run_path_existence_check(diff_paths: list[str]) -> bool:
    """Return True when the path-existence precheck should run for *diff_paths*.

    The check is skipped when the PR touches ONLY markdown files under
    ``plans/**``.  Governance plan prose frequently mentions filenames
    conversationally (e.g. ``task_queue.py`` inside a sentence) that the
    precheck misinterprets as asserted repo-root paths.  See issue #2761
    for concrete examples (PR #2749: 21 findings / 0 blockers; PR #2751:
    132 findings / 0 blockers).

    Rationale for the narrow heuristic:
      * Pure governance-plan PRs are entirely under ``plans/**/*.md`` —
        matching this shape means any "referenced path" is prose, not a
        real path claim to audit.
      * Mixed PRs (plans + code) still run the check: a single non-plan
        file or non-markdown file flips the gate back on, so code-changing
        diffs cannot bypass path validation.

    An empty ``diff_paths`` list returns True (the check runs) so we never
    accidentally suppress findings when no diff is available.
    """
    if not diff_paths:
        return True
    all_are_plan_markdown = all(
        p.startswith("plans/") and p.endswith(".md") for p in diff_paths
    )
    return not all_are_plan_markdown


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


_VC_SECTION_DOC = """
V1-V6: Verification-contract prechecks (Pattern 10, §10.9 governing plan,
§3.4 of plans/steward_platform/verification_contract/shaping.md).

Severity maps to the check-ID taxonomy in .claude/rules/deferred/60_review_gate.md:
  V1 (BLOCK), V2 (BLOCK), V3 (BLOCK), V4 (WARN), V5 (INFO), V6 (WARN).

Per §13.2 risk #1 of shaping.md: V3 must gate on the current PR HEAD +
PR diff, not on the local working tree, or it becomes vacuous when
author-lane checkouts drift.  Callers pass ``pr_changed_files`` explicitly
so we do not shell out to ``git`` from inside this module.

Per §13.2 risk #3: the commit-footer lint (V2) accepts a
``Verification:`` footer on ANY commit in the PR range, not only the
introducing commit — authors may backfill the footer as a follow-up
commit within the same PR.
"""

# §3.3 commit-footer trigger paths (see shaping.md §3.3).
_VC_TRIGGER_PREFIXES = (
    "src/",
    "scripts/internal/",
    ".claude/hooks/",
    ".claude/skills/",
    "src/bid_euchre/ops/",
    "plans/_templates/",
    ".claude/rules/prompt_policy/",
)
_VC_TRIGGER_EXACT_PATHS = (".claude/settings.json",)
_VC_ADR_PREFIXES = (
    "knowledge/adr/",
    "plans/steward_platform/adrs/",
)

_VC_FOOTER_RE = re.compile(r"^Verification:\s*(?P<surface>\S.+?)\s*$", re.MULTILINE)

# PR-body "Verification Performed" section. Accept any Markdown heading
# level; the section is satisfied if the body contains the heading and at
# least one non-blank content line following it.
_VC_PR_BODY_HEADING_RE = re.compile(r"(?im)^\s{0,3}#{1,6}\s+Verification\s+Performed\b")

# §N.M section sigil (e.g. `§5.3`, `§10.9`).
_VC_SECTION_SIGIL_RE = re.compile(r"§\s*\d+(?:\.\d+)+")


def _vc_is_trigger_path(path: str) -> bool:
    """Return True if *path* is a §3.3 trigger for verification-contract."""
    if path in _VC_TRIGGER_EXACT_PATHS:
        return True
    for prefix in _VC_TRIGGER_PREFIXES:
        if path.startswith(prefix):
            return True
    for prefix in _VC_ADR_PREFIXES:
        if path.startswith(prefix):
            return True
    # §7: §5 sub-deliverable row in governing_plan*.md
    if path.startswith("plans/steward_platform/") and "governing_plan" in path:
        return True
    # §8: §N.M section add in plans/**/*.md, .claude/skills/**/*.md, knowledge/**/*.md
    if (
        (path.startswith("plans/") and path.endswith(".md"))
        or (path.startswith(".claude/skills/") and path.endswith(".md"))
        or (path.startswith("knowledge/") and path.endswith(".md"))
    ):
        return True
    return False


def _vc_pr_body_has_verification_performed(pr_body: str | None) -> bool:
    if not pr_body:
        return False
    return bool(_VC_PR_BODY_HEADING_RE.search(pr_body))


def _vc_any_commit_has_footer(commit_messages: list[str] | None) -> list[str]:
    """Return the list of surfaces named in ``Verification:`` footers.

    Per §13.2 risk #3, a footer on ANY commit in the PR range satisfies
    the lint.  Returns ``[]`` when none found or no commit messages were
    supplied.
    """
    if not commit_messages:
        return []
    surfaces: list[str] = []
    for msg in commit_messages:
        for m in _VC_FOOTER_RE.finditer(msg):
            surfaces.append(m.group("surface"))
    return surfaces


def _vc_surface_exists(surface: str, repo_root: Path) -> bool:
    """Return True when the named surface resolves to a real path or is a
    well-known non-path surface form.

    Per the §10.9 Pattern 10 table, acceptable surfaces include:
      * relative paths (``tests/unit/test_foo.py``)
      * path::node forms (``tests/unit/test_foo.py::test_bar``)
      * commands (``make check``, ``uv run …``)
      * review-artifact references (``review-log``, ``canary-dashboard``)

    We accept anything that points to an existing file; for non-path
    forms we accept any surface whose first token contains a known
    non-path keyword.  This is deliberately lenient-form per Pattern 10.
    """
    s = surface.strip()
    if not s:
        return False
    # Strip ::node suffix for path-check
    path_part = s.split("::", 1)[0].strip()
    candidate = (repo_root / path_part).resolve()
    if candidate.exists():
        return True
    # Non-path surface classes (lenient-form).
    first_token = s.split()[0].lower() if s.split() else ""
    non_path_keywords = {
        "make",
        "uv",
        "python",
        "pytest",
        "bash",
        "sh",
        "canary-dashboard",
        "review-log",
        "manual-review",
        "operator-review",
        "dashboard",
        "canary",
    }
    return first_token in non_path_keywords


def _vc_map_contains_deliverable(map_path: Path, needle_tokens: list[str]) -> bool:
    """Return True if the verification_contract/map.md contains a row
    whose `Deliverable` column contains any of *needle_tokens*."""
    if not map_path.exists():
        return False
    try:
        text = map_path.read_text(encoding="utf-8")
    except OSError:
        return False
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        # Extract first column
        parts = line.split("|")
        if len(parts) < 3:
            continue
        deliverable = parts[1].strip()
        for needle in needle_tokens:
            if needle and needle in deliverable:
                return True
    return False


def check_verification_contract(
    changed_files: list[str],
    repo_root: Path,
    *,
    commit_messages: list[str] | None = None,
    pr_body: str | None = None,
) -> list[Finding]:
    """V1–V6 verification-contract prechecks (Pattern 10).

    Args:
        changed_files: PR-scoped list of changed file paths.
        repo_root: Repository root for surface-existence resolution.
        commit_messages: Commit messages across the PR range.  When
            ``None``, V2's BLOCK is suppressed (we cannot distinguish
            "no footer" from "commit messages unavailable").
        pr_body: The PR description body.  When ``None``, the PR-body
            fallback for V2/V5 is disabled.

    Returns:
        List of Finding objects.  Severities align with §3.4:
            V1/V2/V3 → P0 (BLOCK), V4/V6 → P2 (WARN), V5 → P2 (INFO-like).
    """
    findings: list[Finding] = []

    # Identify trigger paths in the changed set.
    triggered = [f for f in changed_files if _vc_is_trigger_path(f)]
    if not triggered:
        return findings

    footer_surfaces = _vc_any_commit_has_footer(commit_messages)
    pr_body_has_section = _vc_pr_body_has_verification_performed(pr_body)

    # V2 — new deliverable path triggered and NO commit-footer AND NO PR body
    # section.  We only BLOCK when we actually have commit_messages to look
    # at; otherwise we emit a WARN so the review driver can see the fallback.
    if not footer_surfaces and not pr_body_has_section:
        if commit_messages is not None:
            for t in triggered:
                findings.append(
                    Finding(
                        severity="P0",
                        file=t,
                        line=0,
                        category="process",
                        check_id="V2",
                        message=(
                            "Verification footer missing. This diff "
                            "introduces or modifies a plan deliverable "
                            "(§3.3 of verification_contract/shaping.md). "
                            "Add a 'Verification: <surface>' commit-message "
                            "footer OR a 'Verification Performed' section "
                            "in the PR body naming the surface per Pattern "
                            "10 (§10.9 governing plan)."
                        ),
                    )
                )
        else:
            # Fallback WARN: callers that cannot supply commit_messages
            # (e.g. local dev runs) still see the reminder.
            findings.append(
                Finding(
                    severity="P2",
                    file=triggered[0],
                    line=0,
                    category="process",
                    check_id="V2",
                    message=(
                        "Verification footer or PR-body section not "
                        "supplied to precheck; cannot enforce V2 BLOCK. "
                        "Pass commit_messages/pr_body or run via review_driver."
                    ),
                )
            )

    # V3 — named surface must resolve to a real path (strict-existence).
    # We check both commit-footer surfaces and PR-body-named surfaces.
    candidate_surfaces = list(footer_surfaces)
    if pr_body:
        # Pull "Verification: X" style lines from the PR body too.
        for m in _VC_FOOTER_RE.finditer(pr_body):
            candidate_surfaces.append(m.group("surface"))
    for surface in candidate_surfaces:
        if not _vc_surface_exists(surface, repo_root):
            findings.append(
                Finding(
                    severity="P0",
                    file="<verification-contract>",
                    line=0,
                    category="process",
                    check_id="V3",
                    message=(
                        f"Named verification surface does not exist: "
                        f"{surface!r}. Pattern 10 is strict-existence on "
                        f"surfaces; adjust the surface or land the target "
                        f"first."
                    ),
                )
            )

    # V1 / V6 — plan-change rows + Work-bullet coverage.
    # Detect plan changes (governing_plan.md sub-deliverable row changes and
    # §N.M section adds).  We do a best-effort textual check without git
    # diff: if a plans/*.md file is in changed_files and has no row in the
    # verification_contract/map.md mentioning one of its §N.M section
    # numbers, emit V6 WARN.
    map_path = (
        repo_root / "plans" / "steward_platform" / "verification_contract" / "map.md"
    )
    for path in changed_files:
        if not (path.startswith("plans/") and path.endswith(".md")):
            continue
        if path.endswith("/verification_contract/map.md"):
            continue
        full = repo_root / path
        if not full.exists():
            continue
        try:
            text = full.read_text(encoding="utf-8")
        except OSError:
            continue
        # Collect §N.M sigils present in the file.
        sigils = set(_VC_SECTION_SIGIL_RE.findall(text))
        if not sigils:
            continue
        if _vc_map_contains_deliverable(map_path, list(sigils)):
            continue
        findings.append(
            Finding(
                severity="P2",
                file=path,
                line=0,
                category="process",
                check_id="V6",
                message=(
                    "Plan file changed but verification_contract/map.md "
                    "has no row referencing any of its §N.M sections. "
                    "Pattern 10: backfill a map row naming the verification "
                    "surface for each changed deliverable."
                ),
            )
        )

    # V5 — informational: commit adds new file under trigger paths and has
    # no footer, but PR body has matching section.  (Recorded in report
    # only — we emit a P2 finding with a distinct check_id so downstream
    # can treat it as INFO.)
    if not footer_surfaces and pr_body_has_section and triggered:
        findings.append(
            Finding(
                severity="P2",
                file=triggered[0],
                line=0,
                category="process",
                check_id="V5",
                message=(
                    "Verification surface is in PR body 'Verification "
                    "Performed' section but no commit carries a "
                    "'Verification:' footer. This passes Pattern 10 "
                    "(PR-body fallback) but commit-footer form is preferred."
                ),
            )
        )

    # V4 — deliverable-class vs surface-class mismatch.  The full mapping
    # is the §10.9 Pattern 10 table; Packet 2b lands the most common
    # mismatches as hard rules and defers the long-tail to Pattern-9's
    # load-bearing ownership lint (shared plan-walker, §13.2 risk #2).
    for path in triggered:
        # Rule: new .claude/hooks/** file should cite a rollback test, not
        # just "operator review".  Detect via surface text.
        if path.startswith(".claude/hooks/"):
            for surface in candidate_surfaces:
                s_lower = surface.lower()
                if "operator review" in s_lower and "rollback" not in s_lower:
                    findings.append(
                        Finding(
                            severity="P2",
                            file=path,
                            line=0,
                            category="process",
                            check_id="V4",
                            message=(
                                "Hook file change names 'operator review' "
                                "as verification surface, but hook deliverables "
                                "should include a rollback test per §10.9 "
                                "Pattern 10 deliverable-class table."
                            ),
                        )
                    )

    return findings


_V7_SECTION_DOC = """
V7: Commit-policy precheck (Primitive C / ADR 010 binding).

See ``plans/steward_platform/3_primitive_C/shaping.md`` §4.6:
  PR adds a file under ``knowledge/_promoted/**`` AND no
  ``archivist_candidate_generated`` event exists upstream (via
  event-stream query over last 30 days) matching the promoted
  artifact's class + approximate timestamp -> BLOCK.

Feature-flagged via ``ENABLE_V7_COMMIT_POLICY`` (default off until
Primitive A's archivist event emission is live per §6.3).  When the
flag is unset the check returns ``[]`` unconditionally.

Event-schema integration is injected via the ``event_lookup``
callable so tests can stub it without a live event store.  The
default stub returns ``False`` (no events known) — which is why the
flag MUST default off pre-Primitive-A: every ``_promoted/`` file
would otherwise BLOCK on a missing-event false positive.
"""


V7_ENV_FLAG = "ENABLE_V7_COMMIT_POLICY"
_V7_PROMOTED_PREFIX = "knowledge/_promoted/"

# Manual-promotion sanction sentinel (case-insensitive substring match
# on the PR body).  Tokens below mark a PR as an explicit manual
# override per §4.6 option (b).
_V7_MANUAL_SANCTION_TOKENS = (
    "manual-promotion exception",
    "manual promotion exception",
    "operator-sanctioned promotion",
)


def _v7_flag_enabled() -> bool:
    """Return True when the V7 feature flag is set to "1"."""
    return os.environ.get(V7_ENV_FLAG) == "1"


def _v7_default_event_lookup(path: str) -> bool:
    """Default event lookup stub.

    Returns ``False`` unconditionally.  A real lookup will be wired
    once Primitive A's event schema v1.0 ships an
    ``archivist_candidate_generated`` event stream (§4.6 Rationale,
    §6.3 coordination).  Because this default always returns False,
    the feature flag MUST remain default off until the real lookup is
    wired — otherwise every ``knowledge/_promoted/**`` add would block.
    """
    del path  # reserved: path-indexed event query when Primitive A lands
    return False


def _v7_pr_has_manual_sanction(pr_body: str | None) -> bool:
    if not pr_body:
        return False
    lower = pr_body.lower()
    return any(token in lower for token in _V7_MANUAL_SANCTION_TOKENS)


def check_v7_commit_policy(
    changed_files: list[str],
    repo_root: Path,
    *,
    event_lookup: Callable[[str], bool] | None = None,
    pr_body: str | None = None,
) -> list[Finding]:
    """V7 commit-policy precheck (ADR 010 binding).

    Args:
        changed_files: PR-scoped list of changed file paths.
        repo_root: Repository root (reserved for future use; included
            for signature parity with ``check_verification_contract``).
        event_lookup: Optional callable ``(path) -> bool`` returning
            True when a matching ``archivist_candidate_generated``
            event exists upstream for *path* within the 30-day window.
            Defaults to :func:`_v7_default_event_lookup`.
        pr_body: PR description body.  A body containing an explicit
            manual-promotion sanction marker (see
            ``_V7_MANUAL_SANCTION_TOKENS``) opts out of the V7 BLOCK
            per §4.6 option (b).

    Returns:
        List of Finding objects.  Empty when the feature flag is off,
        when no ``_promoted/`` files are in the diff, or when every
        ``_promoted/`` file resolves to a matching upstream event.

    Severity: V7 emits P0 (BLOCK) per §3.4 taxonomy extension.
    """
    del repo_root  # reserved — keeps signature symmetric with V1–V6
    if not _v7_flag_enabled():
        return []

    promoted = [p for p in changed_files if p.startswith(_V7_PROMOTED_PREFIX)]
    if not promoted:
        return []

    # Manual-promotion sanction (§4.6 option (b)) opts out entirely.
    if _v7_pr_has_manual_sanction(pr_body):
        return []

    lookup = event_lookup or _v7_default_event_lookup
    findings: list[Finding] = []
    for path in promoted:
        if lookup(path):
            continue
        findings.append(
            Finding(
                severity="P0",
                file=path,
                line=0,
                category="process",
                check_id="V7",
                message=(
                    f"Promoted KB artifact {path!r} has no archivist "
                    "candidate upstream (no matching "
                    "`archivist_candidate_generated` event within 30 "
                    "days). Either (a) produce the candidate via "
                    "`/run-archivist`, then promote, OR (b) mark the PR "
                    "as a manual-promotion exception with explicit "
                    "operator sanction in the PR body. See "
                    "plans/steward_platform/3_primitive_C/shaping.md "
                    "§4.6."
                ),
            )
        )
    return findings
