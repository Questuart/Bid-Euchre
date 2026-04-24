"""Hook inventory contract test — Primitive E Phase 0 Packet E1.

Asserts 1-to-1 correspondence between hook files on disk and rows in the
`Conditional-Hook Migration` § `Disposition Table` of `.claude/hooks/README.md`.

Rationale: the disposition table is the source of truth for every hook's
matcher scope and migration status. A hook file that exists on disk but has
no row is unreviewed; a row that has no file on disk is stale documentation.
Either case is a bug.

Scope — considered "hooks":
- `.claude/hooks/*.sh` and `.claude/hooks/*.py` (direct hook registrations
  and Python helpers invoked by sibling `.sh` wrappers)
- `scripts/internal/hooks/*.sh` (external hook helpers registered in
  `.claude/settings.json`)

Excluded:
- `.claude/hooks/lib/**` — shared shell library code, not itself a hook
- `.claude/hooks/__pycache__/**` — bytecode cache
- `.claude/hooks/README.md` — the doc under test
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
EXTERNAL_HOOKS_DIR = REPO_ROOT / "scripts" / "internal" / "hooks"
README_PATH = HOOKS_DIR / "README.md"

DISPOSITION_HEADER_RE = re.compile(r"^###\s+Disposition\s+Table\s*$", re.MULTILINE)
NEXT_SECTION_RE = re.compile(r"^##?#?\s+\S", re.MULTILINE)
TABLE_ROW_RE = re.compile(r"^\|\s*`([^`]+?)`(?:\s*\([^)]*\))?\s*\|")


def _split_markdown_row(line: str) -> list[str]:
    """Split a markdown table row on `|` while respecting backtick-quoted
    cells (which may themselves contain a literal `|` inside `` `...` ``).

    Returns the non-empty cell strings (i.e., the outer leading/trailing
    `|` are stripped).
    """
    cells: list[str] = []
    buf: list[str] = []
    in_backtick = False
    # Skip the leading `|` if present; the trailing one produces an empty
    # cell which we drop at the end.
    for ch in line:
        if ch == "`":
            in_backtick = not in_backtick
            buf.append(ch)
            continue
        if ch == "|" and not in_backtick:
            cells.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    cells.append("".join(buf).strip())
    # Drop outer empties (leading/trailing `|` sentinels)
    return [c for c in cells if c != ""]


VALID_DISPOSITIONS = {
    "already-narrow",
    "event-scoped",
    "dispatched",
    "retained-universal-justified",
    "migrated-v0.5",
    "deprecated",
    "helper",
}

RETENTION_SENTINEL = "retained-universal-justified"


def _inventory_on_disk() -> set[str]:
    """Return the set of hook filenames (basenames) on disk."""
    names: set[str] = set()
    for path in HOOKS_DIR.glob("*.sh"):
        names.add(path.name)
    for path in HOOKS_DIR.glob("*.py"):
        names.add(path.name)
    for path in EXTERNAL_HOOKS_DIR.glob("*.sh"):
        names.add(path.name)
    return names


def _parse_disposition_table() -> list[dict[str, str]]:
    """Parse the Disposition Table rows from README.md.

    Returns a list of dicts keyed by column: hook, current_matcher,
    proposed_matcher, disposition, rationale.
    """
    text = README_PATH.read_text(encoding="utf-8")
    header_match = DISPOSITION_HEADER_RE.search(text)
    assert header_match, "Disposition Table section missing from README.md"

    body_start = header_match.end()
    # Find the next section (## or ###) after the Disposition Table header
    next_section = NEXT_SECTION_RE.search(text, body_start)
    body_end = next_section.start() if next_section else len(text)
    body = text[body_start:body_end]

    rows: list[dict[str, str]] = []
    for line in body.splitlines():
        if not line.startswith("|"):
            continue
        # Skip header row and separator row
        if "---" in line:
            continue
        if "| Hook " in line and "| Current Matcher " in line:
            continue
        # Parse pipe-delimited row — respect backtick-quoted cells
        cells = _split_markdown_row(line)
        if len(cells) < 5:
            continue
        # Hook cell is backtick-quoted; extract the script name
        hook_cell = cells[0]
        match = TABLE_ROW_RE.match(line)
        if not match:
            continue
        rows.append(
            {
                "hook": match.group(1),
                "current_matcher": cells[1],
                "proposed_matcher": cells[2],
                "disposition": cells[3],
                "rationale": cells[4],
                "_raw_hook_cell": hook_cell,
            }
        )
    return rows


def test_disposition_table_parses_nonempty() -> None:
    """Sanity check: parser extracts at least 30 rows."""
    rows = _parse_disposition_table()
    assert len(rows) >= 30, f"Expected ≥30 disposition rows, got {len(rows)}"


def test_every_hook_on_disk_has_a_disposition_row() -> None:
    """Every hook file in the inventory MUST appear in the disposition table."""
    rows = _parse_disposition_table()
    documented = {row["hook"] for row in rows}
    on_disk = _inventory_on_disk()
    missing = sorted(on_disk - documented)
    assert not missing, (
        "Hook files on disk without a Disposition Table row "
        f"(undocumented hooks, README.md needs update): {missing}"
    )


def test_every_disposition_row_has_a_file_on_disk() -> None:
    """Every row in the disposition table MUST correspond to a real file."""
    rows = _parse_disposition_table()
    on_disk = _inventory_on_disk()
    stale = sorted({row["hook"] for row in rows} - on_disk)
    assert not stale, (
        "Disposition Table rows without a corresponding hook file on disk "
        f"(stale README.md rows): {stale}"
    )


def test_every_disposition_value_is_in_vocabulary() -> None:
    """Every row's Disposition column MUST be one of the legend values."""
    rows = _parse_disposition_table()
    invalid: list[tuple[str, str]] = []
    for row in rows:
        if row["disposition"] not in VALID_DISPOSITIONS:
            invalid.append((row["hook"], row["disposition"]))
    assert not invalid, (
        "Rows with Disposition values outside the legend vocabulary: "
        f"{invalid} (valid: {sorted(VALID_DISPOSITIONS)})"
    )


def test_retained_universal_rows_include_sentinel() -> None:
    """Every retained-universal-justified row MUST end its Rationale with the sentinel."""
    rows = _parse_disposition_table()
    missing_sentinel: list[str] = []
    for row in rows:
        if row["disposition"] != "retained-universal-justified":
            continue
        if RETENTION_SENTINEL not in row["rationale"]:
            missing_sentinel.append(row["hook"])
    assert not missing_sentinel, (
        "Rows classified as retained-universal-justified MUST include the "
        f"sentinel '{RETENTION_SENTINEL}' in Rationale: {missing_sentinel}"
    )
