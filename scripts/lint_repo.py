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
import sys
from dataclasses import dataclass
from pathlib import Path


ALLOWED_ARTIFACT_FILENAMES = {".gitkeep"}
FIXTURE_SIZE_LIMIT_BYTES = 102400  # 100KB


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
