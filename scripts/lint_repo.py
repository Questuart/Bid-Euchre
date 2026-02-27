#!/usr/bin/env python3
"""
Repo linter: enforce project-specific rules that Ruff can't.

Usage:
  python scripts/lint_repo.py --base origin/main --head HEAD
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

ALLOWED_ARTIFACT_FILENAMES = {".gitkeep"}
FIXTURE_SIZE_LIMIT_BYTES = 102400  # 100KB

# Modules allowed to use global random (bare `random.` calls)
# All other src/ modules should use local RNG instances for determinism
RANDOM_ALLOWED_MODULES = {
    "src/bid_euchre/sim/deals.py",  # Designated RNG module
}

# src/ files with deprecation shims that contain `import argparse` inside
# `if __name__ == "__main__":` blocks — excluded from the no-cli-in-src check.
CLI_SHIM_ALLOWLIST = {
    "src/bid_euchre/reporting/chart_runner.py",
    "src/bid_euchre/models/train_olsa.py",
    "src/bid_euchre/models/train_b0.py",
}


@dataclass(frozen=True)
class Violation:
    rule: str
    path: str
    message: str


def run_git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def ensure_ref_exists(ref: str) -> None:
    try:
        subprocess.check_output(
            ["git", "rev-parse", "--verify", ref], stderr=subprocess.DEVNULL
        )
    except Exception:
        raise SystemExit(
            f"ERROR: git ref '{ref}' not found. "
            f"Run: git fetch origin main (or adjust --base)."
        )


def list_changed_files(base: str, head: str) -> list[str]:
    """
    Return changed files between base..head (added/modified/renamed), excluding deletions.
    """
    out = run_git("diff", "--name-status", f"{base}..{head}")
    files: list[str] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split(maxsplit=2)
        status = parts[0]
        if status.startswith("D"):
            continue
        # Handle rename lines: R100 old new -> take last token (new path)
        path = parts[-1]
        files.append(path)
    return files


def is_under(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix.rstrip("/") + "/")


def check_no_generated_artifacts(changed: list[str]) -> list[Violation]:
    violations: list[Violation] = []
    blocked_prefixes = ["data/runs/", "data/reports/"]
    for p in changed:
        for pref in blocked_prefixes:
            if is_under(p, pref):
                name = Path(p).name
                if name not in ALLOWED_ARTIFACT_FILENAMES:
                    violations.append(
                        Violation(
                            rule="no-generated-artifacts",
                            path=p,
                            message=f"Do not commit generated artifacts under {pref} (except .gitkeep).",
                        )
                    )
    return violations


def _imports_from_tree(tree: ast.AST) -> set[str]:
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                if n.name:
                    mods.add(n.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mods.add(node.module.split(".")[0])
    return mods


def check_src_no_experiments_or_tests_imports(
    changed: list[str], repo_root: Path
) -> list[Violation]:
    violations: list[Violation] = []
    for p in changed:
        if not (p.startswith("src/") and p.endswith(".py")):
            continue

        abs_path = repo_root / p
        if not abs_path.exists():
            # In unusual cases, a rename/move could produce a path not present in workspace.
            continue

        text = abs_path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text, filename=p)
        except SyntaxError as e:
            violations.append(
                Violation(
                    rule="src-import-boundary",
                    path=p,
                    message=f"SyntaxError while parsing imports: {e}",
                )
            )
            continue

        imports = _imports_from_tree(tree)
        bad = sorted(set(imports) & {"experiments", "tests"})
        if bad:
            violations.append(
                Violation(
                    rule="src-import-boundary",
                    path=p,
                    message=f"src/ must not import from {bad}. Move shared code into src/ proper.",
                )
            )
    return violations


def check_no_deprecated_changes(changed: list[str]) -> list[Violation]:
    """
    Block modifications to experiments/_deprecated/, except:
    - README.md updates (for documenting new deprecations)
    - New files being added (quarantining scripts is OK)
    """
    violations: list[Violation] = []
    for p in changed:
        if is_under(p, "experiments/_deprecated/"):
            # Allow README updates (documenting deprecations)
            if p.endswith("README.md"):
                continue

            # Check if this is a new file (added, not modified)
            # Git shows renames as additions, which is what we want
            status = subprocess.run(
                ["git", "diff", "--name-status", "origin/main...HEAD", "--", p],
                capture_output=True,
                text=True,
            ).stdout.strip()

            # Allow additions (A) and renames (R) into _deprecated
            if status.startswith(("A", "R")):
                continue

            # Block modifications (M) to existing deprecated files
            violations.append(
                Violation(
                    rule="no-deprecated-changes",
                    path=p,
                    message="Do not modify existing deprecated files. If quarantining, use git mv (shows as rename).",
                )
            )
    return violations


def check_data_fixtures_allowlist(
    changed: list[str], repo_root: Path
) -> list[Violation]:
    """
    Enforce that only data/fixtures/** and data/.gitkeep may be committed under data/.
    Also enforce 100KB size limit on fixtures.
    """
    violations: list[Violation] = []
    for p in changed:
        if not is_under(p, "data/"):
            continue

        # Check if allowlisted
        is_gitkeep = p == "data/.gitkeep"
        is_fixture = is_under(p, "data/fixtures/")

        if not (is_gitkeep or is_fixture):
            # Block everything else under data/
            violations.append(
                Violation(
                    rule="data-fixtures-allowlist",
                    path=p,
                    message=f"{p} is not allowed (only data/fixtures/** and data/.gitkeep may be committed)",
                )
            )
            continue

        # Check fixture size limit
        if is_fixture:
            abs_path = repo_root / p
            if abs_path.exists():
                size_bytes = abs_path.stat().st_size
                if size_bytes > FIXTURE_SIZE_LIMIT_BYTES:
                    size_kb = (size_bytes + 1023) // 1024  # Round up
                    violations.append(
                        Violation(
                            rule="data-fixtures-allowlist",
                            path=p,
                            message=f"data/fixtures/{Path(p).name} exceeds 100KB limit (size: {size_kb}KB, limit: 100KB)",
                        )
                    )

    return violations


def check_no_new_scripts_in_frozen_folders(changed: list[str]) -> list[Violation]:
    """
    Block new Python scripts in experiments/comparisons/ and experiments/training/.
    These folders are frozen to prevent workflow sprawl.

    Allowlist:
    - experiments/comparisons/run_head_to_head.py (existing wrapper)
    - experiments/training/train_bidder_aware_models.py (existing training script)
    - Any README.md files (documentation)
    - Any __init__.py files (package markers)
    """
    FROZEN_FOLDERS = [
        "experiments/comparisons/",
        "experiments/training/",
    ]

    ALLOWLIST = {
        "experiments/comparisons/run_head_to_head.py",
        "experiments/training/train_bidder_aware_models.py",
    }

    violations: list[Violation] = []
    for p in changed:
        # Check if under frozen folders
        in_frozen_folder = any(is_under(p, folder) for folder in FROZEN_FOLDERS)
        if not in_frozen_folder:
            continue

        # Allow README.md files
        if p.endswith("README.md"):
            continue

        # Allow __init__.py files
        if p.endswith("__init__.py"):
            continue

        # Allow allowlisted scripts
        if p in ALLOWLIST:
            continue

        # Check if this is a new Python file (added or renamed into folder)
        if not p.endswith(".py"):
            continue

        # Check git status to see if this is a new file
        status = subprocess.run(
            ["git", "diff", "--name-status", "origin/main...HEAD", "--", p],
            capture_output=True,
            text=True,
        ).stdout.strip()

        # Block additions (A) and renames (R) into frozen folders
        if status.startswith(("A", "R")):
            folder_name = "comparisons" if "comparisons" in p else "training"
            violations.append(
                Violation(
                    rule="no-frozen-folder-sprawl",
                    path=p,
                    message=f"Do not add new scripts to experiments/{folder_name}/. Use configs + experiments/run_experiment.py (or suites) instead.",
                )
            )

    return violations


def check_no_ds_store_files(changed: list[str]) -> list[Violation]:
    """
    Block any .DS_Store files from being added/modified in the diff.
    .DS_Store files are macOS system files that should not be committed.
    """
    violations: list[Violation] = []
    for p in changed:
        if Path(p).name == ".DS_Store":
            violations.append(
                Violation(
                    rule="no-ds-store",
                    path=p,
                    message=".DS_Store files are forbidden - these are macOS system files that should not be committed.",
                )
            )
    return violations


def check_no_global_random(changed: list[str], repo_root: Path) -> list[Violation]:
    """
    Block bare 'random.' usage in src/ Python files (except designated RNG modules).

    This prevents hidden nondeterminism from creeping into the codebase.
    Code should use local RNG instances (random.Random(seed)) for reproducibility.

    Allowed:
    - Files in RANDOM_ALLOWED_MODULES (e.g., src/bid_euchre/sim/deals.py)
    - Tests (tests/ directory)
    - Experiments (experiments/ directory)
    """
    import re

    # Pattern matches bare `random.` method calls that indicate global RNG usage
    # This catches: random.choice, random.randint, random.shuffle, etc.
    global_random_pattern = re.compile(
        r"\brandom\.(choice|randint|randrange|shuffle|sample|uniform|random|seed"
        r"|getstate|setstate)\b"
    )

    violations: list[Violation] = []
    for p in changed:
        # Only check src/ Python files
        if not (p.startswith("src/") and p.endswith(".py")):
            continue

        # Skip allowed modules
        if p in RANDOM_ALLOWED_MODULES:
            continue

        abs_path = repo_root / p
        if not abs_path.exists():
            continue

        text = abs_path.read_text(encoding="utf-8")

        # Check for global random usage
        matches = global_random_pattern.findall(text)
        if matches:
            unique_methods = sorted(set(matches))
            violations.append(
                Violation(
                    rule="no-global-random",
                    path=p,
                    message=(
                        f"Global random usage detected: random.{{{', '.join(unique_methods)}}}. "
                        "Use a local RNG instance (random.Random(seed)) for determinism."
                    ),
                )
            )

    return violations


def check_empty_test_functions(changed: list[str], repo_root: Path) -> list[Violation]:
    """
    Flag test functions that are literally empty (just pass or docstring).

    Note: This replaces the "tests without asserts" check which had false
    positives for valid tests using pytest.raises context managers.
    """
    violations: list[Violation] = []
    for p in changed:
        # Only check test files
        if not (p.startswith("tests/") and p.endswith(".py")):
            continue

        abs_path = repo_root / p
        if not abs_path.exists():
            continue

        text = abs_path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text, filename=p)
        except SyntaxError:
            # Skip files with syntax errors (will be caught by other tools)
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                # Check if function body is empty (only pass or docstring)
                body_without_docstring = [
                    n
                    for n in node.body
                    if not isinstance(n, ast.Expr)
                    or not isinstance(n.value, ast.Constant)
                    or not isinstance(n.value.value, str)
                ]

                # If only 'pass' statement remains, it's empty
                if len(body_without_docstring) == 1 and isinstance(
                    body_without_docstring[0], ast.Pass
                ):
                    violations.append(
                        Violation(
                            rule="empty-test-function",
                            path=f"{p}:{node.lineno}",
                            message=f"test function '{node.name}' is empty (only 'pass')",
                        )
                    )
                elif len(body_without_docstring) == 0:
                    violations.append(
                        Violation(
                            rule="empty-test-function",
                            path=f"{p}:{node.lineno}",
                            message=f"test function '{node.name}' is empty (only docstring)",
                        )
                    )

    return violations


def check_experiments_without_seed(
    changed: list[str], repo_root: Path
) -> list[Violation]:
    """
    Flag experiment invocations in docs/scripts missing --seed.

    All experiment invocations should either:
    1. Use --seed <int> for reproducibility, or
    2. Use --allow-nondeterministic for exploratory runs
    """
    import re

    violations: list[Violation] = []

    # Pattern matches experiment invocations (including multi-line with backslash continuations)
    experiment_pattern = re.compile(
        r"python experiments/run_experiment\.py(?:[^\n]*\\\n)*[^\n]*"
    )

    # Files to check
    paths_to_check: list[Path] = []
    for p in changed:
        if p.endswith(".md") or (p.startswith("scripts/") and p.endswith(".py")):
            abs_path = repo_root / p
            if abs_path.exists():
                paths_to_check.append(abs_path)

    for abs_path in paths_to_check:
        rel_path = abs_path.relative_to(repo_root)
        text = abs_path.read_text(encoding="utf-8")

        for match in experiment_pattern.finditer(text):
            invocation = match.group(0)

            # Check for --seed or --allow-nondeterministic
            if (
                "--seed" not in invocation
                and "--allow-nondeterministic" not in invocation
            ):
                lineno = text[: match.start()].count("\n") + 1
                violations.append(
                    Violation(
                        rule="experiments-require-seed",
                        path=f"{rel_path}:{lineno}",
                        message="experiment invocation missing --seed or --allow-nondeterministic",
                    )
                )

    return violations


def check_no_sys_path_insert(changed: list[str], repo_root: Path) -> list[Violation]:
    """Block sys.path.insert/append in active Python files.

    Deprecated files under experiments/_deprecated/ are grandfathered.
    """
    violations: list[Violation] = []
    for p in changed:
        if not p.endswith(".py"):
            continue
        if is_under(p, "experiments/_deprecated/"):
            continue
        if is_under(p, "tests/"):
            continue
        if p == "scripts/lint_repo.py":
            continue
        abs_path = repo_root / p
        if not abs_path.exists():
            continue
        text = abs_path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "sys.path.insert" in line or "sys.path.append" in line:
                violations.append(
                    Violation(
                        rule="no-sys-path-mutation",
                        path=f"{p}:{i}",
                        message="sys.path.insert/append is forbidden. Use PYTHONPATH=src or uv run.",
                    )
                )
    return violations


def check_no_cli_in_src(changed: list[str], repo_root: Path) -> list[Violation]:
    """Block module-level ``import argparse`` in src/ Python files.

    CLI entrypoints belong in scripts/, not in library code.  Files in
    CLI_SHIM_ALLOWLIST are expected to contain ``import argparse`` only
    inside their ``if __name__ == "__main__":`` deprecation shim and are
    therefore excluded from this check.

    Uses ast.parse to inspect only *module-level* statements so that
    argparse imports inside ``if __name__`` guards are not flagged.
    """
    violations: list[Violation] = []
    for p in changed:
        if not (p.startswith("src/") and p.endswith(".py")):
            continue
        if p in CLI_SHIM_ALLOWLIST:
            continue

        abs_path = repo_root / p
        if not abs_path.exists():
            continue

        text = abs_path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text, filename=p)
        except SyntaxError:
            continue

        # Only inspect top-level statements (not nested in if/def/class)
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "argparse":
                        violations.append(
                            Violation(
                                rule="no-cli-in-src",
                                path=f"{p}:{node.lineno}",
                                message=(
                                    "Module-level `import argparse` in src/ is forbidden. "
                                    "Move CLI logic to scripts/."
                                ),
                            )
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module == "argparse":
                    violations.append(
                        Violation(
                            rule="no-cli-in-src",
                            path=f"{p}:{node.lineno}",
                            message=(
                                "Module-level `from argparse import ...` in src/ is forbidden. "
                                "Move CLI logic to scripts/."
                            ),
                        )
                    )

    return violations


def check_no_import_experiments_package(
    changed: list[str], repo_root: Path
) -> list[Violation]:
    """Block 'import experiments' or 'from experiments import' outside experiments/.

    The top-level experiments/ directory is a filesystem directory (YAML configs + runner),
    NOT a Python package. Use bid_euchre.experiments for config classes.
    """
    violations: list[Violation] = []
    for p in changed:
        if not p.endswith(".py"):
            continue
        if is_under(p, "experiments/"):
            continue
        abs_path = repo_root / p
        if not abs_path.exists():
            continue
        text = abs_path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text, filename=p)
        except SyntaxError:
            continue
        imports = _imports_from_tree(tree)
        if "experiments" in imports:
            violations.append(
                Violation(
                    rule="no-experiments-package-import",
                    path=p,
                    message=(
                        "'import experiments' is forbidden outside experiments/. "
                        "Use bid_euchre.experiments for config classes."
                    ),
                )
            )
    return violations


# --- Promotion contract lint rules ---

# Promotion registry: files that constitute the canonical results registry.
PROMOTION_REGISTRY_PREFIXES = [
    "docs/04_reports/",
]

# Explicit allowlist for additional registry files outside the prefix dirs.
PROMOTION_REGISTRY_ALLOWLIST: set[str] = set()

GATE_EVIDENCE_PATTERNS = [
    "batch_gate.json",
    "notebook_gate.json",
    "canonical_summary.json",
    "gate_status",
]

CODE_REGISTRY_PATH = "src/bid_euchre/datasets/canonical_runs.py"


def check_registry_requires_gate_reference(
    changed: list[str],
    repo_root: Path,
) -> list[Violation]:
    """If a promotion registry doc changes, require gate evidence reference in content."""
    violations: list[Violation] = []
    for p in changed:
        # Only check .md files
        if not p.endswith(".md"):
            continue
        # Skip README.md (index/navigation only)
        if Path(p).name == "README.md":
            continue
        # Check if under registry prefixes or in allowlist
        in_registry = any(is_under(p, prefix) for prefix in PROMOTION_REGISTRY_PREFIXES)
        if not in_registry and p not in PROMOTION_REGISTRY_ALLOWLIST:
            continue

        abs_path = repo_root / p
        if not abs_path.exists():
            continue

        text = abs_path.read_text(encoding="utf-8")

        # Check if any gate evidence pattern appears in content
        has_gate_ref = any(pattern in text for pattern in GATE_EVIDENCE_PATTERNS)
        if not has_gate_ref:
            violations.append(
                Violation(
                    rule="registry-requires-gate-reference",
                    path=p,
                    message=(
                        "Promotion registry doc must reference gate evidence "
                        f"(one of: {', '.join(GATE_EVIDENCE_PATTERNS)})"
                    ),
                )
            )
    return violations


def check_promotion_report_requires_integrity_review(
    changed: list[str],
    repo_root: Path,
) -> list[Violation]:
    """Promotion report files must have a rung-matched measurement integrity review."""
    violations: list[Violation] = []
    for p in changed:
        if not p.endswith(".md"):
            continue
        name = Path(p).name
        # Scope: only files named <rung>_promotion_report.md under reports dir
        if not name.endswith("_promotion_report.md"):
            continue
        if not any(is_under(p, prefix) for prefix in PROMOTION_REGISTRY_PREFIXES):
            continue

        abs_path = repo_root / p
        if not abs_path.exists():
            continue

        # Extract rung from filename: e.g., "r0_promotion_report.md" -> "r0"
        rung = name.removesuffix("_promotion_report.md")

        # Enforce directory-rung consistency: filename rung must match parent dir
        dir_name = abs_path.parent.name
        if dir_name != rung:
            violations.append(
                Violation(
                    rule="promotion-requires-integrity-review",
                    path=p,
                    message=(
                        f"Promotion report rung '{rung}' does not match "
                        f"directory '{dir_name}'. Convention requires "
                        f"docs/04_reports/{rung}/{name}."
                    ),
                )
            )
            continue

        # Require rung-matched companion: measurement_integrity_<rung>.md
        expected = abs_path.parent / f"measurement_integrity_{rung}.md"
        if not expected.exists():
            violations.append(
                Violation(
                    rule="promotion-requires-integrity-review",
                    path=p,
                    message=(
                        f"Promotion report requires companion file "
                        f"'measurement_integrity_{rung}.md' in the same directory. "
                        f"See docs/02_agent/MEASUREMENT_INTEGRITY_REVIEW.md for template."
                    ),
                )
            )
    return violations


def check_canonical_runs_registry_consistency(
    changed: list[str],
    repo_root: Path,
) -> list[Violation]:
    """If code registry exists AND doc registry changes, require synchronized update."""
    violations: list[Violation] = []

    # Check if code registry exists on disk
    code_registry = repo_root / CODE_REGISTRY_PATH
    if not code_registry.exists():
        # Post-#305 reality: code registry deleted, no-op
        return violations

    # Identify doc registry files in changed set
    doc_registry_changed = [
        p
        for p in changed
        if (
            any(is_under(p, prefix) for prefix in PROMOTION_REGISTRY_PREFIXES)
            or p in PROMOTION_REGISTRY_ALLOWLIST
        )
    ]

    code_registry_changed = CODE_REGISTRY_PATH in changed

    # If doc changed but code not changed → violation
    if doc_registry_changed and not code_registry_changed:
        for p in doc_registry_changed:
            violations.append(
                Violation(
                    rule="canonical-runs-registry-consistency",
                    path=p,
                    message=(
                        f"Doc registry changed but {CODE_REGISTRY_PATH} was not updated. "
                        "Keep code and doc registries in sync."
                    ),
                )
            )

    # If code changed but no doc changed → violation
    if code_registry_changed and not doc_registry_changed:
        violations.append(
            Violation(
                rule="canonical-runs-registry-consistency",
                path=CODE_REGISTRY_PATH,
                message=(
                    "Code registry changed but no doc registry files were updated. "
                    "Keep code and doc registries in sync."
                ),
            )
        )

    return violations


# --- Artifact discovery lint rules ---
#
# This is a supplemental commit-time check. The canonical promotion-path
# enforcement lives in reporting.eligibility.check_artifacts_frozen() which
# uses models.freeze.verify_frozen() at runtime. The lint rule mirrors that
# logic (checks both frozen_at and artifact_sha256) for early feedback.

# Filename substrings that indicate model artifacts (case-insensitive match).
# Used as a path-based pre-filter; schema confirmation via
# _has_model_artifact_schema() prevents false positives on unrelated JSON.
ARTIFACT_NAME_PATTERNS = ["olsa", "b0", "teacher", "hybrid"]

# Infrastructure JSON files that live under data/ but are NOT model artifacts.
FREEZE_EXEMPT_NAMES = {"meta.json", "rollup.json", "canonical_summary.json"}


def _is_model_artifact(path: str) -> bool:
    """Path-based pre-filter: True if *path* is a candidate model artifact.

    Checks: under data/, .json extension, not exempt, filename matches a
    known pattern. Callers should confirm with _has_model_artifact_schema()
    after reading the file content.
    """
    if not is_under(path, "data/"):
        return False
    name = Path(path).name
    if not name.endswith(".json"):
        return False
    if name in FREEZE_EXEMPT_NAMES:
        return False
    name_lower = name.lower()
    return any(pattern in name_lower for pattern in ARTIFACT_NAME_PATTERNS)


def _has_model_artifact_schema(data: dict) -> bool:
    """Schema-based confirmation: True if *data* looks like a model artifact.

    Checks for known model artifact keys produced by the training pipeline:
    - ``artifact_type``: explicitly tags the file as a model artifact
    - ``frozen_at``: freeze field (present even when null in training output)
    - ``models`` + ``metadata``: OLSa artifact structure
    """
    if "artifact_type" in data:
        return True
    if "frozen_at" in data:
        return True
    if "models" in data and "metadata" in data:
        return True
    return False


def check_artifacts_require_freeze(
    changed: list[str],
    repo_root: Path,
) -> list[Violation]:
    """Model artifact JSON must be properly frozen (frozen_at + artifact_sha256).

    Detection uses two-phase filtering: path pre-filter (_is_model_artifact)
    then schema confirmation (_has_model_artifact_schema). This prevents
    false positives on unrelated JSON that happens to match filename patterns.

    Freeze check mirrors models.freeze.verify_frozen(): requires both
    frozen_at and artifact_sha256 to be non-null.
    """
    violations: list[Violation] = []
    for p in changed:
        if not _is_model_artifact(p):
            continue

        abs_path = repo_root / p
        if not abs_path.exists():
            continue

        try:
            metadata = json.loads(abs_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            violations.append(
                Violation(
                    rule="artifact-requires-freeze",
                    path=p,
                    message="Model artifact is not valid JSON.",
                )
            )
            continue

        if not isinstance(metadata, dict):
            violations.append(
                Violation(
                    rule="artifact-requires-freeze",
                    path=p,
                    message=(
                        "Model artifact JSON must be an object (got "
                        f"{type(metadata).__name__})."
                    ),
                )
            )
            continue

        # Schema confirmation: skip files that don't look like model artifacts
        if not _has_model_artifact_schema(metadata):
            continue

        if metadata.get("frozen_at") is None:
            violations.append(
                Violation(
                    rule="artifact-requires-freeze",
                    path=p,
                    message=(
                        "Model artifact must be frozen before commit "
                        "(frozen_at is null). Run freeze_artifact() first."
                    ),
                )
            )
        elif metadata.get("artifact_sha256") is None:
            violations.append(
                Violation(
                    rule="artifact-requires-freeze",
                    path=p,
                    message=(
                        "Model artifact has frozen_at but missing artifact_sha256. "
                        "Run freeze_artifact() to set both fields."
                    ),
                )
            )
    return violations


# --- Gate artifact and split manifest schema lint rules ---

GATE_REQUIRED_FIELDS = {"schema_version", "gate_status", "created_at_utc"}

SEMANTIC_GATE_REQUIRED_FIELDS = {
    "schema_version",
    "gate_status",
    "created_at_utc",
    "active_split",
    "mode",
    "seed",
    "total_hands",
    "total_checks",
    "passed_checks",
    "failed_checks",
    "checks",
}

SEMANTIC_GATE_CHECK_REQUIRED_FIELDS = {
    "check_id",
    "category",
    "status",
    "threshold",
    "observed",
    "detail",
}

SPLIT_MANIFEST_REQUIRED_FIELDS = {
    "schema_version",
    "split_type",
    "split_seed",
    "total_hand_ids",
    "partition_hashes",
}
VALID_SPLIT_TYPES = {"two_way", "three_way"}


def _is_gate_artifact(path: str) -> bool:
    """Return True if *path* looks like a gate artifact JSON under data/."""
    if not is_under(path, "data/"):
        return False
    name = Path(path).name
    return name.endswith(".json") and "gate" in name.lower()


def _is_split_manifest(path: str) -> bool:
    """Return True if *path* looks like a split manifest JSON."""
    name = Path(path).name
    return name.startswith("split_manifest") and name.endswith(".json")


def check_gate_artifacts_schema(
    changed: list[str],
    repo_root: Path,
) -> list[Violation]:
    """Gate artifact JSON files must have required fields and gate_status == PASS."""
    violations: list[Violation] = []
    for p in changed:
        if not _is_gate_artifact(p):
            continue

        abs_path = repo_root / p
        if not abs_path.exists():
            continue

        try:
            data = json.loads(abs_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            violations.append(
                Violation(
                    rule="gate-artifact-schema",
                    path=p,
                    message="Gate artifact is not valid JSON.",
                )
            )
            continue

        if not isinstance(data, dict):
            violations.append(
                Violation(
                    rule="gate-artifact-schema",
                    path=p,
                    message=(
                        "Gate artifact JSON must be an object (got "
                        f"{type(data).__name__})."
                    ),
                )
            )
            continue

        missing = GATE_REQUIRED_FIELDS - set(data.keys())
        if missing:
            violations.append(
                Violation(
                    rule="gate-artifact-schema",
                    path=p,
                    message=f"Gate artifact missing required fields: {sorted(missing)}",
                )
            )
            continue

        if data["gate_status"] != "PASS":
            violations.append(
                Violation(
                    rule="gate-artifact-schema",
                    path=p,
                    message=(
                        f"Gate artifact has gate_status={data['gate_status']!r} "
                        "(must be 'PASS' to commit)."
                    ),
                )
            )
    return violations


def _is_semantic_gate(path: str) -> bool:
    """Return True if path looks like a semantic gate JSON."""
    name = Path(path).name
    return name.startswith("semantic_gate") and name.endswith(".json")


def check_semantic_gate_schema(
    changed: list[str],
    repo_root: Path,
) -> list[Violation]:
    """Semantic gate JSON files must have full required schema fields."""
    violations: list[Violation] = []
    for p in changed:
        if not _is_semantic_gate(p):
            continue

        abs_path = repo_root / p
        if not abs_path.exists():
            continue

        try:
            data = json.loads(abs_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            continue  # Already caught by generic gate rule

        if not isinstance(data, dict):
            continue  # Already caught by generic gate rule

        # Validate top-level fields
        missing = SEMANTIC_GATE_REQUIRED_FIELDS - set(data.keys())
        if missing:
            violations.append(
                Violation(
                    rule="semantic-gate-schema",
                    path=p,
                    message=f"Semantic gate missing required fields: {sorted(missing)}",
                )
            )
            continue

        # Validate each check entry
        checks = data.get("checks", [])
        for i, check in enumerate(checks):
            if not isinstance(check, dict):
                violations.append(
                    Violation(
                        rule="semantic-gate-schema",
                        path=p,
                        message=f"checks[{i}] is not a dict",
                    )
                )
                continue
            cmissing = SEMANTIC_GATE_CHECK_REQUIRED_FIELDS - set(check.keys())
            if cmissing:
                violations.append(
                    Violation(
                        rule="semantic-gate-schema",
                        path=p,
                        message=f"checks[{i}] (check_id={check.get('check_id', '?')}) "
                        f"missing fields: {sorted(cmissing)}",
                    )
                )
    return violations


def check_split_manifest_schema(
    changed: list[str],
    repo_root: Path,
) -> list[Violation]:
    """Split manifest JSON files must have required fields and valid split_type."""
    violations: list[Violation] = []
    for p in changed:
        if not _is_split_manifest(p):
            continue

        abs_path = repo_root / p
        if not abs_path.exists():
            continue

        try:
            data = json.loads(abs_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            violations.append(
                Violation(
                    rule="split-manifest-schema",
                    path=p,
                    message="Split manifest is not valid JSON.",
                )
            )
            continue

        if not isinstance(data, dict):
            violations.append(
                Violation(
                    rule="split-manifest-schema",
                    path=p,
                    message=(
                        "Split manifest JSON must be an object (got "
                        f"{type(data).__name__})."
                    ),
                )
            )
            continue

        missing = SPLIT_MANIFEST_REQUIRED_FIELDS - set(data.keys())
        if missing:
            violations.append(
                Violation(
                    rule="split-manifest-schema",
                    path=p,
                    message=f"Split manifest missing required fields: {sorted(missing)}",
                )
            )
            continue

        if data["split_type"] not in VALID_SPLIT_TYPES:
            violations.append(
                Violation(
                    rule="split-manifest-schema",
                    path=p,
                    message=(
                        f"Split manifest has split_type={data['split_type']!r} "
                        f"(must be one of: {sorted(VALID_SPLIT_TYPES)})."
                    ),
                )
            )
    return violations


# --- Hybrid artifact schema lint rule ---

HYBRID_OLSA_REQUIRED_FIELDS = {
    "artifact_type",
    "payoff_model",
    "residual_variance",
    "risk_lambda",
    "context_features",
}

HYBRID_OLSA_MODEL_REQUIRED_FIELDS = {"weights", "bias", "feature_names"}


def _is_hybrid_artifact(path: str) -> bool:
    """Return True if path looks like a hybrid_olsa_v1 JSON."""
    name = Path(path).name
    return name.endswith(".json") and "hybrid" in name.lower()


def check_hybrid_artifact_schema(
    changed: list[str],
    repo_root: Path,
) -> list[Violation]:
    """Hybrid OLSa artifact JSON files must have required schema fields."""
    violations: list[Violation] = []
    for p in changed:
        if not _is_hybrid_artifact(p):
            continue

        abs_path = repo_root / p
        if not abs_path.exists():
            continue

        try:
            data = json.loads(abs_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            violations.append(
                Violation(
                    rule="hybrid-artifact-schema",
                    path=p,
                    message="Hybrid artifact is not valid JSON.",
                )
            )
            continue

        if not isinstance(data, dict):
            continue

        # Only validate files with artifact_type == hybrid_olsa_v1
        if data.get("artifact_type") != "hybrid_olsa_v1":
            continue

        missing = HYBRID_OLSA_REQUIRED_FIELDS - set(data.keys())
        if missing:
            violations.append(
                Violation(
                    rule="hybrid-artifact-schema",
                    path=p,
                    message=f"Hybrid artifact missing required fields: {sorted(missing)}",
                )
            )
            continue

        # Validate payoff_model entries
        payoff_model = data.get("payoff_model", {})
        if not isinstance(payoff_model, dict) or not payoff_model:
            violations.append(
                Violation(
                    rule="hybrid-artifact-schema",
                    path=p,
                    message="payoff_model must be a non-empty object",
                )
            )
            continue

        for cf, model in payoff_model.items():
            if not isinstance(model, dict):
                violations.append(
                    Violation(
                        rule="hybrid-artifact-schema",
                        path=p,
                        message=f"payoff_model[{cf!r}] must be an object",
                    )
                )
                continue
            mmissing = HYBRID_OLSA_MODEL_REQUIRED_FIELDS - set(model.keys())
            if mmissing:
                violations.append(
                    Violation(
                        rule="hybrid-artifact-schema",
                        path=p,
                        message=f"payoff_model[{cf!r}] missing fields: {sorted(mmissing)}",
                    )
                )

    return violations


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--head", default="HEAD")
    args = ap.parse_args()

    repo_root = Path(run_git("rev-parse", "--show-toplevel"))
    os.chdir(repo_root)

    ensure_ref_exists(args.base)

    changed = list_changed_files(args.base, args.head)

    violations: list[Violation] = []
    violations += check_no_generated_artifacts(changed)
    violations += check_no_deprecated_changes(changed)
    violations += check_src_no_experiments_or_tests_imports(changed, repo_root)
    violations += check_data_fixtures_allowlist(changed, repo_root)
    violations += check_no_new_scripts_in_frozen_folders(changed)
    violations += check_no_ds_store_files(changed)
    violations += check_no_global_random(changed, repo_root)
    violations += check_empty_test_functions(changed, repo_root)
    violations += check_experiments_without_seed(changed, repo_root)
    violations += check_no_sys_path_insert(changed, repo_root)
    violations += check_no_cli_in_src(changed, repo_root)
    violations += check_no_import_experiments_package(changed, repo_root)
    violations += check_registry_requires_gate_reference(changed, repo_root)
    violations += check_promotion_report_requires_integrity_review(changed, repo_root)
    violations += check_canonical_runs_registry_consistency(changed, repo_root)
    violations += check_artifacts_require_freeze(changed, repo_root)
    violations += check_gate_artifacts_schema(changed, repo_root)
    violations += check_semantic_gate_schema(changed, repo_root)
    violations += check_split_manifest_schema(changed, repo_root)
    violations += check_hybrid_artifact_schema(changed, repo_root)

    if violations:
        print("Repo linter failed:\n")
        for v in violations:
            print(f"- [{v.rule}] {v.path}: {v.message}")
        print("\nFix the violations or adjust the change to comply with repo rules.")
        return 1

    print("Repo linter passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
