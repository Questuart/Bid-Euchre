#!/usr/bin/env python3
"""Regenerate ``knowledge/INDEX.md`` deterministically.

Per Primitive C shaping §4.1.3 (``plans/steward_platform/3_primitive_C/shaping.md``)
and governing plan §5-C. The INDEX is a generated artifact listing every
promoted KB file with its class, size, and a one-line summary.

**Algorithm:**

1. Walk ``knowledge/`` excluding ``_candidates/`` (gitignored) and
   ``_promoted/`` (archive, not live content).
2. For each ``.md`` file at the top level, emit a row with filename,
   last-modified date from git (or mtime if git history absent), heading
   count.
3. For each directory (``adr/``, ``incidents/``), emit a section listing
   entries with one-line summaries (first ``###`` heading or first
   non-blank line of content, truncated to ≤80 chars).
4. Emit a final ``_promoted/`` archive section: last 10 promotion
   entries (by filename sort, most recent first since filenames are
   dated).
5. Write INDEX.md atomically (write to temp, fsync, rename).

**Determinism.** Same input tree → byte-identical output. Unit test
``tests/unit/test_kb_index.py::test_index_regenerates_deterministically``
runs twice and asserts empty diff.

**Exit codes:**

* ``0`` — regeneration succeeded
* ``1`` — I/O error or invocation error
* ``2`` — schema violation detected mid-walk (tracked ``knowledge/*.md``
  file lacks a worked example / required heading)

**Usage:**

.. code-block:: bash

    uv run python scripts/internal/kb_index.py --write       # rewrite knowledge/INDEX.md
    uv run python scripts/internal/kb_index.py --stdout      # print to stdout (no file write)
    uv run python scripts/internal/kb_index.py --check       # exit 2 if INDEX.md is stale
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


TOP_LEVEL_FILES = (
    "NOTES.md",
    "PLAYBOOKS.md",
    "anti_patterns.md",
    "harness_assumptions.md",
    "agent_readability_scorecard.md",
    "external_signal_sources.md",
)
# Files that must carry a worked example at file head per §5-C obligation.
WORKED_EXAMPLE_REQUIRED = (
    "NOTES.md",
    "PLAYBOOKS.md",
    "anti_patterns.md",
    "harness_assumptions.md",
)

SCAN_DIRS = ("adr", "incidents")
ARCHIVE_DIR = "_promoted"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class TopFileRow:
    filename: str
    heading_count: int
    last_modified: str  # YYYY-MM-DD
    present: bool


@dataclass
class DirEntry:
    filename: str
    summary: str


# ---------------------------------------------------------------------------
# Core walkers
# ---------------------------------------------------------------------------


def _git_last_modified(repo_root: Path, relpath: Path) -> str:
    """Return YYYY-MM-DD date from `git log -1`, or mtime fallback.

    Determinism note: we use the *committer date* for the most recent
    commit touching the file. Untracked files fall back to mtime. For
    fully deterministic fixture-based tests, callers provide a tree with
    no git history; we fall back to ``1970-01-01`` in that case.
    """
    abs_path = repo_root / relpath
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "log",
                "-1",
                "--format=%cs",
                "--",
                str(relpath),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        date = result.stdout.strip()
        if date:
            return date
    except (FileNotFoundError, OSError):
        pass
    # Fallback for fixture trees without git history: stable sentinel.
    if not abs_path.exists():
        return "1970-01-01"
    return "1970-01-01"


def _count_headings(text: str) -> int:
    """Count all markdown headings (``#`` through ``######``)."""
    return sum(1 for line in text.splitlines() if re.match(r"^#{1,6}\s+\S", line))


def _first_summary_line(text: str) -> str:
    """Return the first ``### <heading>`` or first non-blank prose line,
    truncated to 80 chars for the INDEX one-liner."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("### "):
            summary = stripped[4:].strip()
            break
        if stripped.startswith("#"):
            # Fall through — skip top-level title, prefer first H3 or
            # first prose paragraph.
            continue
        if stripped.startswith(">"):
            continue
        if stripped.startswith("**") and stripped.endswith("**"):
            # Field label; keep looking for a narrative line.
            continue
        summary = stripped
        break
    else:
        summary = "(empty)"
    if len(summary) > 80:
        summary = summary[:77] + "…"
    return summary


def _has_worked_example(text: str) -> bool:
    """Heuristic: a worked example is any level-3 heading OR a ``##
    Worked example`` / ``## Worked example (canonical)`` section at file
    head."""
    if re.search(r"(?im)^##\s+Worked example\b", text):
        return True
    if re.search(r"(?m)^###\s+\S", text):
        return True
    return False


def scan_top_level(kb_root: Path, repo_root: Path) -> list[TopFileRow]:
    rows: list[TopFileRow] = []
    for name in TOP_LEVEL_FILES:
        path = kb_root / name
        if not path.exists():
            rows.append(
                TopFileRow(
                    filename=name,
                    heading_count=0,
                    last_modified="—",
                    present=False,
                )
            )
            continue
        text = path.read_text(encoding="utf-8")
        if name in WORKED_EXAMPLE_REQUIRED and not _has_worked_example(text):
            raise SchemaViolation(
                f"{path} is missing a worked example (per §5-C schema "
                f"obligation). Add a `## Worked example` section or a "
                f"level-3 heading with a concrete entry."
            )
        rel = path.relative_to(repo_root)
        rows.append(
            TopFileRow(
                filename=name,
                heading_count=_count_headings(text),
                last_modified=_git_last_modified(repo_root, rel),
                present=True,
            )
        )
    return rows


def scan_directory(kb_root: Path, dirname: str) -> list[DirEntry]:
    dirpath = kb_root / dirname
    if not dirpath.exists():
        return []
    entries: list[DirEntry] = []
    for p in sorted(dirpath.rglob("*.md")):
        text = p.read_text(encoding="utf-8")
        summary = _first_summary_line(text)
        rel = p.relative_to(kb_root)
        entries.append(DirEntry(filename=str(rel), summary=summary))
    return entries


def scan_promoted_archive(kb_root: Path) -> list[str]:
    """Return the last-10 promoted-archive filenames (sort descending)."""
    promoted = kb_root / ARCHIVE_DIR
    if not promoted.exists():
        return []
    files = sorted(
        (p.name for p in promoted.rglob("*.md")),
        reverse=True,
    )
    return files[:10]


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


INTERFACE_CONTRACT = """## Archivist C↔D Interface Contract

**D writes to:** `knowledge/_candidates/<YYYY-MM-DD>_<kind>.md`
  where <kind> ∈ {lessons, changelog, gc}

**D does NOT write to:** anything else under `knowledge/`.
  D MUST NOT edit NOTES.md, PLAYBOOKS.md, anti_patterns.md, harness_assumptions.md,
  incidents/*, adr/*, or INDEX.md. These are operator-promoted surfaces.

**C reads from:** `knowledge/_candidates/*.md` (session-local; gitignored)
**C writes to:** `knowledge/NOTES.md` or `knowledge/PLAYBOOKS.md` or
  `knowledge/anti_patterns.md` (appended under operator direction) AND
  `knowledge/_promoted/<YYYY-MM-DD>_<class>_<hash>.md` (archive entry).

**Gate between them:** operator review of candidate files via `/run-archivist`
  skill or direct edit. No automatic promotion. No autonomous state mutation
  (binding constraint from ADR 010 §Decision).

**Event emission on promotion (C-side):**
  - `kb_artifact_promoted` (event_type per Primitive A schema v1.0; fields:
    artifact_class, source_candidate_path, promoted_path, operator_id,
    trace_id, promoted_at)
  - `kb_artifact_unpromoted` — emitted on rollback

**Event emission on candidate generation (D-side):**
  - `archivist_candidate_generated` (fields: candidate_path, candidate_count,
    trigger, archivist_mode, generated_at)

**Failure modes:**
  - D writes outside `_candidates/`: C-side lint flags; archivist refuses to
    run until resolved.
  - C promotes without emitting event: Pattern 8 (Observable-by-default) lint
    flags in post-merge review.
  - Operator promotes a candidate file D hasn't written (fake candidate):
    `kb_artifact_promoted` event has no matching `archivist_candidate_generated`
    upstream event; review-driver precheck V7 flags.
"""


def render_index(
    top_rows: list[TopFileRow],
    adr_entries: list[DirEntry],
    incident_entries: list[DirEntry],
    promoted_archive: list[str],
) -> str:
    parts: list[str] = []
    parts.append("# Knowledge Base INDEX\n")
    parts.append(
        "> Auto-generated by `scripts/internal/kb_index.py`. Do not edit "
        "by hand; run the regenerator after any promotion. See Primitive "
        "C shaping §4.1.3 for the algorithm.\n"
    )
    parts.append(
        "> **Commit policy (ADR 010):** only promoted artifacts live "
        "under `knowledge/`. `_candidates/` is gitignored (session "
        "inflow); `_promoted/` is the tracked archive.\n"
    )
    parts.append("")

    # Top-level files section.
    parts.append("## Top-level files\n")
    parts.append(
        "| File | Status | Headings | Last modified (git) |\n" "|---|---|---|---|"
    )
    for row in top_rows:
        if row.present:
            parts.append(
                f"| [`{row.filename}`]({row.filename}) | tracked | "
                f"{row.heading_count} | {row.last_modified} |"
            )
        else:
            parts.append(f"| `{row.filename}` | MISSING | — | — |")
    parts.append("")

    # ADR directory.
    parts.append("## `adr/` — Architecture Decision Records\n")
    if adr_entries:
        parts.append("| Entry | Summary |\n|---|---|")
        for e in adr_entries:
            parts.append(
                f"| [`{e.filename}`](adr/{e.filename.split('/')[-1] if '/' not in e.filename else e.filename}) | {e.summary} |"
            )
    else:
        parts.append("_(no ADR entries yet)_")
    parts.append("")

    # Incidents directory.
    parts.append("## `incidents/` — per-fingerprint incident records\n")
    if incident_entries:
        parts.append("| Entry | Summary |\n|---|---|")
        for e in incident_entries:
            rel = e.filename.split("/")[-1]
            parts.append(f"| [`{e.filename}`](incidents/{rel}) | {e.summary} |")
    else:
        parts.append("_(no incidents recorded yet)_")
    parts.append("")

    # Promoted archive (last 10).
    parts.append("## `_promoted/` — last 10 promotion archive entries\n")
    if promoted_archive:
        for name in promoted_archive:
            parts.append(f"- [`{name}`](_promoted/{name})")
    else:
        parts.append("_(no promotion archive entries yet)_")
    parts.append("")

    # Interface contract (verbatim — matches archivist.py docstring per §4.3).
    parts.append(INTERFACE_CONTRACT)

    # Trailing newline for POSIX-compliant file end.
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Write / diff
# ---------------------------------------------------------------------------


class SchemaViolation(Exception):
    """Raised when a tracked KB file violates the §5-C schema."""


def atomic_write(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` atomically (temp + fsync + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as tmp:
        tmp.write(content)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def regenerate(repo_root: Path) -> str:
    kb_root = repo_root / "knowledge"
    top_rows = scan_top_level(kb_root, repo_root)
    adr_entries = scan_directory(kb_root, "adr")
    incident_entries = scan_directory(kb_root, "incidents")
    promoted_archive = scan_promoted_archive(kb_root)
    return render_index(top_rows, adr_entries, incident_entries, promoted_archive)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kb_index",
        description=(
            "Regenerate knowledge/INDEX.md deterministically "
            "(Primitive C shaping §4.1.3)."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root (default: inferred from script path)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--write",
        action="store_true",
        help="Overwrite knowledge/INDEX.md with regenerated content.",
    )
    mode.add_argument(
        "--stdout",
        action="store_true",
        help="Print regenerated INDEX to stdout (no file write).",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="Exit 2 if knowledge/INDEX.md is stale (content diff).",
    )
    args = parser.parse_args(argv)
    repo_root: Path = args.repo_root.resolve()

    try:
        content = regenerate(repo_root)
    except SchemaViolation as exc:
        print(f"kb_index: SCHEMA VIOLATION — {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"kb_index: I/O error — {exc}", file=sys.stderr)
        return 1

    index_path = repo_root / "knowledge" / "INDEX.md"

    if args.write:
        atomic_write(index_path, content)
        print(f"kb_index: wrote {index_path}")
        return 0
    if args.check:
        if not index_path.exists():
            print("kb_index: INDEX.md is missing (run --write).", file=sys.stderr)
            return 2
        existing = index_path.read_text(encoding="utf-8")
        if existing != content:
            print(
                "kb_index: INDEX.md is stale (run --write to regenerate).",
                file=sys.stderr,
            )
            return 2
        print("kb_index: INDEX.md is up to date.")
        return 0
    # Default / --stdout.
    sys.stdout.write(content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
