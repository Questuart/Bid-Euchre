#!/usr/bin/env python3
"""
Repo linter: enforce project-specific rules that Ruff can't.

Usage:
  python scripts/lint_repo.py --base origin/main --head HEAD
"""

from __future__ import annotations

import argparse
import ast
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
        subprocess.check_output(["git", "rev-parse", "--verify", ref], stderr=subprocess.DEVNULL)
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


def check_src_no_experiments_or_tests_imports(changed: list[str], repo_root: Path) -> list[Violation]:
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
                text=True
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


def check_data_fixtures_allowlist(changed: list[str], repo_root: Path) -> list[Violation]:
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
            text=True
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
                    n for n in node.body
                    if not isinstance(n, ast.Expr) or
                       not isinstance(n.value, ast.Constant) or
                       not isinstance(n.value.value, str)
                ]

                # If only 'pass' statement remains, it's empty
                if (len(body_without_docstring) == 1 and
                    isinstance(body_without_docstring[0], ast.Pass)):
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


def check_experiments_without_seed(changed: list[str], repo_root: Path) -> list[Violation]:
    """
    Flag experiment invocations in docs/scripts missing --seed.

    All experiment invocations should either:
    1. Use --seed <int> for reproducibility, or
    2. Use --allow-nondeterministic for exploratory runs
    """
    import re

    violations: list[Violation] = []

    # Pattern matches experiment invocations (including multi-line with backslash continuations)
    experiment_pattern = re.compile(r'python experiments/run_experiment\.py(?:[^\n]*\\\n)*[^\n]*')

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
            if "--seed" not in invocation and "--allow-nondeterministic" not in invocation:
                lineno = text[:match.start()].count('\n') + 1
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
                violations.append(Violation(
                    rule="no-sys-path-mutation",
                    path=f"{p}:{i}",
                    message="sys.path.insert/append is forbidden. Use PYTHONPATH=src or uv run.",
                ))
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


def check_no_import_experiments_package(changed: list[str], repo_root: Path) -> list[Violation]:
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
