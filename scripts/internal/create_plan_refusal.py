#!/usr/bin/env python3
"""`/create-plan` refusal-logic evaluator.

Per Primitive C shaping §4.4.1 / §4.4.2
(``plans/steward_platform/3_primitive_C/shaping.md``). The `/create-plan`
skill (SKILL.md) MUST refuse to emit a plan whose ``## Verification
Plan`` section fails any of the four conditions R1-R4 enumerated below.
This module implements the evaluation so both the skill wrapper and
``tests/unit/test_create_plan_refusal.py`` exercise the same algorithm.

**Refusal conditions (ordered by detection per §4.4.1):**

* **R1** — ``## Verification Plan`` section is missing
* **R2** — Section is present but the table is empty (header row only)
* **R3** — Any row contains a placeholder token (``TBD``, ``TODO``,
  ``FIXME``, ``XXX``) in the ``Verification surface`` column
* **R4** — Any Work bullet in the plan body lacks a matching row in
  this plan's Verification Plan table AND lacks coverage in
  ``plans/steward_platform/verification_contract/map.md``

**Refusal message format (§4.4.2, verbatim):**

.. code-block:: text

    /create-plan REFUSED: Pattern 10 (§10.9) requires a complete Verification Plan section.

    Refusal reasons:
      R<N>: <fragment from §4.4.1 table>
      [additional R<N> lines if multiple conditions fire]

    See the worked example in plans/_templates/sub_plan.md §Verification Plan.
    See Pattern 10 table at §10.9 of plans/steward_platform/governing_plan.md for
    deliverable-class → surface-class defaults.

    No plan file was written. Fix the above and re-invoke /create-plan.

**Exit code:** 0 if the plan passes all four checks; 2 if any fires.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT_DEFAULT = Path(__file__).resolve().parents[2]
LINT_SCRIPT = REPO_ROOT_DEFAULT / "scripts" / "internal" / "agent_readability_lint.py"

PLACEHOLDER_TOKENS = ("TBD", "TODO", "FIXME", "XXX")


@dataclass(frozen=True)
class Refusal:
    """One R<N> refusal reason."""

    code: str  # e.g. "R1"
    fragment: str  # fragment from §4.4.1 table


# ---------------------------------------------------------------------------
# R1, R2, R3 — local to the plan file
# ---------------------------------------------------------------------------


_VERIFICATION_HEADING_RE = re.compile(
    r"^#{1,6}\s+Verification\s+Plan\b", re.IGNORECASE | re.MULTILINE
)
_NEXT_HEADING_RE = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)
_TABLE_ROW_RE = re.compile(r"^\|")


def _extract_verification_block(text: str) -> tuple[int, int] | None:
    """Return ``(start_index, end_index)`` of the ``## Verification Plan`` block.

    The block spans from the heading line to the next heading at the
    same-or-higher level (or EOF). Returns ``None`` if the heading is
    not present.
    """
    match = _VERIFICATION_HEADING_RE.search(text)
    if not match:
        return None
    start = match.end()
    # Find the next heading after this one.
    next_match = _NEXT_HEADING_RE.search(text, pos=start)
    end = next_match.start() if next_match else len(text)
    return (start, end)


def _check_r1_r2_r3(text: str) -> list[Refusal]:
    """Evaluate R1 (missing), R2 (empty table), R3 (placeholder tokens)."""
    refusals: list[Refusal] = []
    block = _extract_verification_block(text)
    if block is None:
        refusals.append(Refusal("R1", "Missing `## Verification Plan` section"))
        return refusals

    start, end = block
    body = text[start:end]
    table_lines = [
        line for line in body.splitlines() if _TABLE_ROW_RE.match(line.strip())
    ]
    # A valid table has at least three rows: header, separator, and ≥1 data row.
    data_rows = _extract_data_rows(table_lines)

    if not data_rows:
        refusals.append(
            Refusal(
                "R2",
                "`## Verification Plan` section is empty (header row only)",
            )
        )
        return refusals

    # R3 — placeholder tokens in the Verification surface column (col 3 by
    # convention: Deliverable | Class | Verification surface | Owner |
    # Acceptance). We scan column 3 case-insensitively.
    for row in data_rows:
        cells = _split_row(row)
        if len(cells) < 3:
            continue
        deliverable = cells[0]
        surface = cells[2]
        if _has_placeholder(surface):
            refusals.append(
                Refusal(
                    "R3",
                    f"Row for deliverable `{deliverable}` carries placeholder surface `{surface}`",
                )
            )
    return refusals


def _extract_data_rows(table_lines: list[str]) -> list[str]:
    """Return the non-header, non-separator rows of a markdown pipe table."""
    if len(table_lines) < 2:
        return []
    # The separator row contains only ``|``, ``-``, ``:``, and whitespace.
    sep_re = re.compile(r"^\|[\s\-:|]+\|\s*$")
    data: list[str] = []
    saw_separator = False
    for line in table_lines:
        stripped = line.strip()
        if sep_re.match(stripped):
            saw_separator = True
            continue
        if not saw_separator:
            # Header row(s) before the separator.
            continue
        data.append(stripped)
    return data


def _split_row(row: str) -> list[str]:
    """Split a markdown pipe-table row into its cells (stripped)."""
    # Strip leading/trailing pipes.
    inner = row.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [cell.strip() for cell in inner.split("|")]


def _has_placeholder(text: str) -> bool:
    upper = text.upper()
    return any(token in upper for token in PLACEHOLDER_TOKENS)


# ---------------------------------------------------------------------------
# R4 — cross-referenced with the lint's verification-contract rule
# ---------------------------------------------------------------------------


def _load_lint_module():
    """Import ``agent_readability_lint`` without depending on sys.path tweaks."""
    name = "agent_readability_lint"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, LINT_SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _check_r4(path: Path, repo_root: Path) -> list[Refusal]:
    """Evaluate R4 by delegating to the lint's VC3 rule.

    A VC3 finding indicates a Work bullet with no Verification Plan row
    and no coverage in ``map.md``. Each VC3 finding becomes a separate
    R4 refusal reason so the caller can cite the specific §N.M.
    """
    lint = _load_lint_module()
    findings = lint.check_verification_contract([path], repo_root)
    refusals: list[Refusal] = []
    for f in findings:
        if f.rule_id != "VC3":
            continue
        refusals.append(
            Refusal("R4", f.message or "Work bullet has no Verification Plan row")
        )
    return refusals


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def evaluate_plan(
    path: Path,
    *,
    repo_root: Path | None = None,
) -> list[Refusal]:
    """Evaluate R1-R4 against the plan at ``path``.

    Returns an ordered list of refusals. An empty list means the plan
    passed all four checks.

    Detection order matches §4.4.1. Short-circuit semantics: if R1
    fires, R2/R3/R4 do not run (no table exists to check). If R2 fires,
    R3 does not run. R4 runs regardless of R2/R3 so the caller can see
    Work-bullet gaps even when the table is malformed.
    """
    if not path.exists():
        return [Refusal("R1", f"Plan path not found: {path}")]
    if repo_root is None:
        repo_root = REPO_ROOT_DEFAULT
    text = path.read_text(encoding="utf-8")
    refusals = _check_r1_r2_r3(text)
    if any(r.code == "R1" for r in refusals):
        return refusals
    refusals.extend(_check_r4(path, repo_root))
    return refusals


# ---------------------------------------------------------------------------
# Message formatting + CLI
# ---------------------------------------------------------------------------


REFUSAL_HEADER = "/create-plan REFUSED: Pattern 10 (§10.9) requires a complete Verification Plan section."
REFUSAL_FOOTER = (
    "See the worked example in plans/_templates/sub_plan.md §Verification Plan.\n"
    "See Pattern 10 table at §10.9 of plans/steward_platform/governing_plan.md for\n"
    "deliverable-class → surface-class defaults.\n"
    "\n"
    "No plan file was written. Fix the above and re-invoke /create-plan."
)


def format_refusal_message(refusals: list[Refusal]) -> str:
    """Format refusal reasons per §4.4.2 exact message format."""
    reason_lines = "\n".join(f"  {r.code}: {r.fragment}" for r in refusals)
    return (
        f"{REFUSAL_HEADER}\n"
        "\n"
        "Refusal reasons:\n"
        f"{reason_lines}\n"
        "\n"
        f"{REFUSAL_FOOTER}\n"
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="create_plan_refusal",
        description="Evaluate R1-R4 refusal conditions for /create-plan (Primitive C shaping §4.4).",
    )
    parser.add_argument(
        "path", type=Path, help="Path to the plan markdown file to evaluate."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT_DEFAULT,
        help="Repository root (default: inferred from script path).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    refusals = evaluate_plan(args.path, repo_root=args.repo_root.resolve())
    if not refusals:
        return 0
    sys.stderr.write(format_refusal_message(refusals))
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
