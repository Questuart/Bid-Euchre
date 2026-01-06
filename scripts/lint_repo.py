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
    violations: list[Violation] = []
    for p in changed:
        if is_under(p, "experiments/_deprecated/"):
            violations.append(
                Violation(
                    rule="no-deprecated-changes",
                    path=p,
                    message="Do not modify experiments/_deprecated/. Create new code outside _deprecated instead.",
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
