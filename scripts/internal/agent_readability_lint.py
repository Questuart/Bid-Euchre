#!/usr/bin/env python3
"""Agent-readability lint for steward-platform plan/artifact health.

This is the shared lint harness for draft-8 §10.9 patterns and Primitive
B-exec.α registry rule sets:

* **Pattern 9 — Load-bearing-ownership lint.** Every *load-bearing* item
  (cross-linked, referenced-from-multiple-places, gate-input) must have a
  named owner in its originating primitive.  Rule set: ``check
  load-bearing-ownership`` *(scaffold only in Packet 2b; rule set lands in
  a follow-up).*

* **Pattern 10 — Verification surface per deliverable.** Every plan/sub-plan
  ``§N.M`` Work bullet or Readiness bullet must be backed by a row in its
  plan's ``## Verification Plan`` section OR in the canonical
  ``plans/steward_platform/verification_contract/map.md``.  Rule set:
  ``check verification-contract``.

* **B.3 — Prompt-policy registry structural lint.** Every file under
  ``.claude/rules/prompt_policy/**/*.md`` carries ``## Version``,
  ``## Trigger``, ``## Expected effect``, and ``## Rollback`` sections.
  Version format matches ``^<archetype>-v\\d+\\.\\d+$``. Rule set:
  ``check prompt-policy``.

* **B.6 — Tool risk registry structural lint.** The file
  ``.claude/rules/tool_risk_registry.md`` covers every tool in
  ``.claude/settings.json`` ``permissions.allow``; every row has both
  envelope columns populated with one of
  ``{direct, approve, edit, reject}``. Rule set: ``check tool-risk``.

* **B.11 — Orchestration recipe archive structural lint.** Every file
  under ``knowledge/orchestration_recipes/**/*.md`` (excluding
  ``_archive/``, ``_template.md``, and ``INDEX.md``) carries the six
  required sections (Version, Context, Decision, Observed outcome, Reuse
  guidance, Downstream citations); ``INDEX.md`` references every
  non-archive, non-template recipe. Rule set: ``check recipes``.

**Shared-module dependency (§13.2 risk #2 of verification_contract/shaping.md):**
both rule sets consume the same plan-walker core and the same row-parser
primitives.  Breaking or regressing the plan-walker *silently degrades both
Pattern 9 and Pattern 10 enforcement at once.*  Tests for either rule set
therefore live alongside shared-core tests in
``tests/unit/test_agent_readability_lint.py`` and the plan-walker must be
treated as a single-owner component even though it is exercised by two
distinct rule sets.

Usage
-----
::

    uv run python scripts/internal/agent_readability_lint.py \\
        check verification-contract [PATH ...]

    uv run python scripts/internal/agent_readability_lint.py \\
        check load-bearing-ownership [PATH ...]  # Pattern 9 scaffold

    uv run python scripts/internal/agent_readability_lint.py \\
        check prompt-policy [PATH ...]

    uv run python scripts/internal/agent_readability_lint.py \\
        check tool-risk [PATH ...]

    uv run python scripts/internal/agent_readability_lint.py \\
        check recipes [PATH ...]

If no ``PATH`` is provided, each check defaults to a sensible root:
``check verification-contract`` walks ``plans/``; ``check prompt-policy``
walks ``.claude/rules/prompt_policy/``; ``check tool-risk`` walks
``.claude/rules/tool_risk_registry.md``; ``check recipes`` walks
``knowledge/orchestration_recipes/``.

Exit codes
----------
* ``0`` — lint passes (no findings, or only INFO findings)
* ``1`` — invocation error (unknown sub-command, bad path, malformed CLI)
* ``2`` — lint findings present (BLOCK or WARN severity)

Severity semantics follow ``.claude/rules/deferred/60_review_gate.md``:
BLOCK fails the precheck; WARN is reported but non-fatal under
``--warnings-ok``; INFO is recorded in the report only.

Pattern 10 — see ``plans/steward_platform/governing_plan.md`` §10.9 and
``plans/steward_platform/verification_contract/shaping.md`` §3.2(iii).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# ---------------------------------------------------------------------------
# Severity model (aligned with 60_review_gate.md)
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    BLOCK = "BLOCK"
    WARN = "WARN"
    INFO = "INFO"


@dataclass
class Finding:
    severity: Severity
    rule_id: str
    path: Path
    line: int
    message: str

    def format_line(self) -> str:
        return f"{self.severity.value} [{self.rule_id}] {self.path}:{self.line}: {self.message}"


# ---------------------------------------------------------------------------
# Plan-walker core (shared by Pattern 9 and Pattern 10 rule sets)
# ---------------------------------------------------------------------------

# A §N.M section heading, e.g. `## §5.3`, `### §5.3 Work`, `## 5.3`.  We
# accept both the section-sigil form (§5.3) and the plain-number form
# (5.3 Work) to keep the walker lenient-form per Pattern 10.
SECTION_HEADING_RE = re.compile(
    r"^(?P<hashes>#{1,6})\s+(?:§\s*)?(?P<num>\d+(?:\.\d+)+)\b", re.MULTILINE
)

# A "Work bullet" or "Readiness bullet": a markdown list item under a
# `Work`/`Readiness`/`Deliverables` heading.  We detect the containing
# heading via the walker, then treat every `- ` list item under it as a
# candidate deliverable.
WORK_HEADING_RE = re.compile(
    r"^#{1,6}\s+(?:§\s*\d+(?:\.\d+)+\s+)?(Work|Readiness|Deliverables)\b",
    re.IGNORECASE | re.MULTILINE,
)

# A deliverable row in a `## Verification Plan` table.  Columns:
# Deliverable | Class | Verification surface | Owner | Acceptance.
VERIFICATION_ROW_RE = re.compile(
    r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$"
)

VERIFICATION_HEADING_RE = re.compile(
    r"^#{1,6}\s+Verification\s+Plan\b", re.IGNORECASE | re.MULTILINE
)


@dataclass
class DeliverableBullet:
    """A `Work`/`Readiness` bullet found in a plan §N.M section."""

    path: Path
    section_num: str
    bullet_text: str
    line: int


@dataclass
class VerificationRow:
    """A row under a `## Verification Plan` section."""

    path: Path
    deliverable: str
    class_: str
    surface: str
    owner: str
    acceptance: str
    line: int


@dataclass
class PlanWalk:
    deliverables: list[DeliverableBullet] = field(default_factory=list)
    verification_rows: list[VerificationRow] = field(default_factory=list)
    plans_walked: list[Path] = field(default_factory=list)


def walk_plans(roots: list[Path]) -> PlanWalk:
    """Walk plan-like markdown files rooted at the given paths.

    A "plan-like" file is any ``*.md`` under ``plans/``, ``plans/_templates``,
    ``plans/sessions``, or ``.claude/skills``.  For Packet 2b we scope the
    walker to ``plans/`` because that is where Pattern 10's contract lives;
    skills are sub-walked only when a caller explicitly includes them.
    """
    walk = PlanWalk()
    files: list[Path] = []
    for root in roots:
        if root.is_file() and root.suffix == ".md":
            files.append(root)
            continue
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*.md")):
            # Skip archival drafts — they are historical snapshots, not live
            # plans subject to Pattern 10 enforcement.
            if "_archive" in p.parts or "archive" in p.parts:
                continue
            files.append(p)

    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        walk.plans_walked.append(path)
        _walk_file(path, text, walk)
    return walk


def _walk_file(path: Path, text: str, walk: PlanWalk) -> None:
    lines = text.splitlines()

    # Find all Work/Readiness/Deliverables headings and collect their bullets.
    work_headings = list(WORK_HEADING_RE.finditer(text))
    # Map each work heading to its §N.M number by searching backward for the
    # most recent numbered-section heading.
    for m in work_headings:
        heading_line_idx = text[: m.start()].count("\n")
        section_num = _nearest_section_num(lines, heading_line_idx)
        if section_num is None:
            continue
        # Collect bullets until next heading of equal or higher level.
        heading_level = len(m.group(0).split()[0])
        bullets = _collect_bullets_under_heading(lines, heading_line_idx, heading_level)
        for bullet_line_idx, bullet_text in bullets:
            walk.deliverables.append(
                DeliverableBullet(
                    path=path,
                    section_num=section_num,
                    bullet_text=bullet_text,
                    line=bullet_line_idx + 1,
                )
            )

    # Find the `## Verification Plan` section (0 or 1 per file) and parse
    # its table rows.
    vp_match = VERIFICATION_HEADING_RE.search(text)
    if vp_match is not None:
        vp_line_idx = text[: vp_match.start()].count("\n")
        vp_level = len(vp_match.group(0).split()[0])
        rows = _collect_verification_rows(path, lines, vp_line_idx, vp_level)
        walk.verification_rows.extend(rows)


def _nearest_section_num(lines: list[str], idx: int) -> str | None:
    """Walk backward from `idx` looking for the nearest ``§N.M`` heading."""
    for i in range(idx, -1, -1):
        m = SECTION_HEADING_RE.match(lines[i])
        if m:
            return m.group("num")
    return None


def _collect_bullets_under_heading(
    lines: list[str], heading_idx: int, heading_level: int
) -> list[tuple[int, str]]:
    """Return ``[(line_idx, bullet_text), ...]`` for list items that fall
    under the heading at ``heading_idx`` until the next heading of equal or
    higher level."""
    bullets: list[tuple[int, str]] = []
    i = heading_idx + 1
    while i < len(lines):
        line = lines[i]
        heading_m = re.match(r"^(#{1,6})\s+", line)
        if heading_m and len(heading_m.group(1)) <= heading_level:
            break
        bullet_m = re.match(r"^\s*[-*]\s+(.*\S)", line)
        if bullet_m:
            bullets.append((i, bullet_m.group(1).strip()))
        i += 1
    return bullets


def _collect_verification_rows(
    path: Path, lines: list[str], heading_idx: int, heading_level: int
) -> list[VerificationRow]:
    rows: list[VerificationRow] = []
    i = heading_idx + 1
    # Skip preamble (non-table content) until we hit a table.
    while i < len(lines):
        line = lines[i]
        heading_m = re.match(r"^(#{1,6})\s+", line)
        if heading_m and len(heading_m.group(1)) <= heading_level:
            break
        if line.startswith("|"):
            # Parse this table block.
            while i < len(lines) and lines[i].startswith("|"):
                table_line = lines[i]
                # Skip separator rows and header rows.
                if re.match(r"^\|[\s\-:|]+\|\s*$", table_line):
                    i += 1
                    continue
                m = VERIFICATION_ROW_RE.match(table_line)
                if m:
                    deliverable, class_, surface, owner, acceptance = (
                        g.strip() for g in m.groups()
                    )
                    # Skip obvious header rows.
                    lower = deliverable.lower()
                    if lower in {"deliverable", "deliverable (§n.m)", "item"}:
                        i += 1
                        continue
                    # Skip the illustrative "(row per …)" template placeholder.
                    if deliverable.startswith("(") and deliverable.endswith(")"):
                        i += 1
                        continue
                    rows.append(
                        VerificationRow(
                            path=path,
                            deliverable=deliverable,
                            class_=class_,
                            surface=surface,
                            owner=owner,
                            acceptance=acceptance,
                            line=i + 1,
                        )
                    )
                i += 1
            continue
        i += 1
    return rows


# ---------------------------------------------------------------------------
# Pattern 10: check verification-contract
# ---------------------------------------------------------------------------


# Tokens in the `surface` column that mean "not a real surface yet".
_SURFACE_PLACEHOLDER_TOKENS = ("TBD", "TODO", "FIXME", "XXX")


def _surface_is_placeholder(surface: str) -> bool:
    upper = surface.upper()
    return any(tok in upper for tok in _SURFACE_PLACEHOLDER_TOKENS)


def _surface_is_present(surface: str) -> bool:
    s = surface.strip()
    return bool(s) and s not in {"—", "-"}


def _load_global_map(repo_root: Path) -> set[str]:
    """Load deliverables from the canonical verification-contract map.

    Returns a set of deliverable-strings covered by the global map.  Used
    by ``check verification-contract`` to allow plans to satisfy Pattern 10
    either via their own ``## Verification Plan`` or via a row in the
    global map (per §6.1 of verification_contract/shaping.md worked
    example).
    """
    map_path = (
        repo_root / "plans" / "steward_platform" / "verification_contract" / "map.md"
    )
    if not map_path.exists():
        return set()
    try:
        text = map_path.read_text(encoding="utf-8")
    except OSError:
        return set()
    deliverables: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        m = VERIFICATION_ROW_RE.match(line)
        if not m:
            continue
        deliverable = m.group(1).strip()
        if deliverable.lower() in {"deliverable", "deliverable (§n.m)", "item"}:
            continue
        if re.match(r"^\|[\s\-:|]+\|?$", line):
            continue
        if deliverable.startswith("(") and deliverable.endswith(")"):
            continue
        if not deliverable:
            continue
        deliverables.add(deliverable)
    return deliverables


def check_verification_contract(roots: list[Path], repo_root: Path) -> list[Finding]:
    """Return all Pattern 10 findings across the given plan roots."""
    walk = walk_plans(roots)
    global_map = _load_global_map(repo_root)
    findings: list[Finding] = []

    # Rule VC1 — Verification Plan rows must carry a non-placeholder surface.
    for row in walk.verification_rows:
        if not _surface_is_present(row.surface):
            findings.append(
                Finding(
                    severity=Severity.BLOCK,
                    rule_id="VC1",
                    path=row.path,
                    line=row.line,
                    message=(
                        f"Verification Plan row for {row.deliverable!r} has "
                        f"no surface (column is empty or '—'). Pattern 10 "
                        f"requires a concrete surface."
                    ),
                )
            )
            continue
        if _surface_is_placeholder(row.surface):
            findings.append(
                Finding(
                    severity=Severity.BLOCK,
                    rule_id="VC2",
                    path=row.path,
                    line=row.line,
                    message=(
                        f"Verification Plan row for {row.deliverable!r} "
                        f"carries placeholder surface {row.surface!r}. "
                        f"Pattern 10 requires strict-existence; replace "
                        f"TBD/TODO/FIXME/XXX with a real surface before "
                        f"merge."
                    ),
                )
            )

    # Rule VC3 — Work/Readiness bullets must be covered by a Verification
    # Plan row in the same plan, or by a row in the global map.
    per_file_rows: dict[Path, list[VerificationRow]] = {}
    for row in walk.verification_rows:
        per_file_rows.setdefault(row.path, []).append(row)

    # WARN (not BLOCK) rationale: the walker is intentionally lenient-form
    # and can false-positive on narrative bullets that are not themselves
    # deliverables. Review-driver V1/V6 promote the plan-change cases to
    # BLOCK at PR time (see shaping §3.4); this periodic lint is the
    # run-against-existing surface. Files with a local Verification Plan
    # section opt into covering-via-own-section; files without one rely
    # on the global `verification_contract/map.md` (or have no Work
    # bullets).

    for bullet in walk.deliverables:
        if _bullet_covered(bullet, per_file_rows.get(bullet.path, []), global_map):
            continue
        findings.append(
            Finding(
                severity=Severity.WARN,
                rule_id="VC3",
                path=bullet.path,
                line=bullet.line,
                message=(
                    f"§{bullet.section_num} bullet {_truncate(bullet.bullet_text, 60)!r} "
                    f"is not covered by a Verification Plan row in this file "
                    f"or by a row in plans/steward_platform/verification_contract/map.md. "
                    f"Pattern 10: add a row naming the verification surface."
                ),
            )
        )

    return findings


def _bullet_covered(
    bullet: DeliverableBullet,
    local_rows: list[VerificationRow],
    global_map: set[str],
) -> bool:
    # Heuristic match: a row covers a bullet if the bullet's section
    # number appears in the row's `Deliverable` column OR a token of the
    # bullet text appears in the `Deliverable` column.  This is
    # deliberately lenient-form per Pattern 10.
    section_needle = f"§{bullet.section_num}"
    raw_needle = bullet.section_num
    bullet_tokens = _bullet_keywords(bullet.bullet_text)
    for row in local_rows:
        d = row.deliverable
        if (
            section_needle in d
            or d.startswith(raw_needle)
            or f" {raw_needle}" in f" {d}"
        ):
            return True
        for tok in bullet_tokens:
            if tok and tok in d:
                return True
    for deliverable in global_map:
        if section_needle in deliverable or deliverable.startswith(raw_needle):
            return True
        for tok in bullet_tokens:
            if tok and tok in deliverable:
                return True
    return False


def _bullet_keywords(text: str) -> list[str]:
    """Extract stable keywords from a bullet text for lenient matching.

    We take backtick-quoted code spans and path-like tokens as the stable
    keywords.  Natural-language prose is ignored.
    """
    keywords: list[str] = []
    for m in re.finditer(r"`([^`]+)`", text):
        keywords.append(m.group(1).strip())
    for m in re.finditer(
        r"[A-Za-z_./][A-Za-z0-9_./\-]*\.(py|md|json|yaml|yml|sh)", text
    ):
        keywords.append(m.group(0))
    return keywords


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


# ---------------------------------------------------------------------------
# Pattern 9 scaffold: check load-bearing-ownership
# ---------------------------------------------------------------------------


def check_load_bearing_ownership(roots: list[Path], repo_root: Path) -> list[Finding]:
    """Scaffold for Pattern 9 enforcement.

    The Pattern 9 rule set is enumerated in draft 8 §10.9 and folded into
    this harness per the shared-module decision in §13.2 risk #2 of
    verification_contract/shaping.md.  The concrete rule set lands in a
    follow-up PR; Packet 2b ships the scaffold and ensures the sub-command
    is available so downstream callers have a stable interface.
    """
    # Intentionally no findings in the scaffold version.  Tests assert the
    # sub-command exits 0 over a known-clean tree.
    _ = roots
    _ = repo_root
    return []


# ---------------------------------------------------------------------------
# B.3: check prompt-policy
# ---------------------------------------------------------------------------

_PROMPT_POLICY_REQUIRED_SECTIONS: tuple[str, ...] = (
    "Version",
    "Trigger",
    "Expected effect",
    "Rollback",
)

# Format: `<archetype>-v<MAJOR>.<MINOR>` (e.g., `author-v1.0`). Archetype
# may contain lowercase letters + hyphens (e.g., `brws-author`).
_POLICY_VERSION_RE = re.compile(r"^`([a-z][a-z0-9_-]*)-v(\d+)\.(\d+)`$")

# A ``## Foo`` style top-level section heading.
_H2_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)


def _find_h2_line(text: str, title: str) -> int | None:
    """Return 1-indexed line of the first ``## <title>`` heading, or None."""
    target = title.strip().lower()
    for m in _H2_RE.finditer(text):
        if m.group("title").strip().lower() == target:
            return text[: m.start()].count("\n") + 1
    return None


def _extract_section_body(text: str, title: str) -> str | None:
    """Return the markdown body between ``## <title>`` and the next H2."""
    target = title.strip().lower()
    headings = list(_H2_RE.finditer(text))
    for i, m in enumerate(headings):
        if m.group("title").strip().lower() != target:
            continue
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        return text[start:end]
    return None


def _policy_files_under(root: Path) -> list[Path]:
    """Return every ``.md`` under ``root`` (recursive)."""
    if root.is_file() and root.suffix == ".md":
        return [root]
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.md") if p.is_file())


def check_prompt_policy(roots: list[Path], repo_root: Path) -> list[Finding]:
    """Return B.3 findings: every prompt-policy file has the 4 required
    sections; its ``## Version`` body matches the canonical format.
    """
    findings: list[Finding] = []
    default_root = repo_root / ".claude" / "rules" / "prompt_policy"
    search_roots = roots if roots else [default_root]

    files: list[Path] = []
    for r in search_roots:
        files.extend(_policy_files_under(r))

    if not files:
        # Lint emits a WARN when the scan produces zero files — that is
        # almost always a pointer/typo rather than a clean state.
        findings.append(
            Finding(
                severity=Severity.WARN,
                rule_id="PP0",
                path=default_root,
                line=1,
                message=(
                    "check prompt-policy walked zero files; expected at "
                    "least one .md under .claude/rules/prompt_policy/"
                ),
            )
        )
        return findings

    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            findings.append(
                Finding(
                    severity=Severity.BLOCK,
                    rule_id="PP1",
                    path=path,
                    line=1,
                    message=f"cannot read file: {exc}",
                )
            )
            continue

        # PP2: required sections exist.
        for section in _PROMPT_POLICY_REQUIRED_SECTIONS:
            if _find_h2_line(text, section) is None:
                findings.append(
                    Finding(
                        severity=Severity.BLOCK,
                        rule_id="PP2",
                        path=path,
                        line=1,
                        message=(
                            f"missing required section '## {section}' "
                            f"(B.3 registry schema — shaping §4.2)"
                        ),
                    )
                )

        # PP3: Version body has canonical format on its own line.
        version_body = _extract_section_body(text, "Version")
        if version_body is not None:
            version_line = None
            for raw in version_body.splitlines():
                stripped = raw.strip()
                if not stripped:
                    continue
                version_line = stripped
                break
            if version_line is None:
                findings.append(
                    Finding(
                        severity=Severity.BLOCK,
                        rule_id="PP3",
                        path=path,
                        line=_find_h2_line(text, "Version") or 1,
                        message=(
                            "Version section is empty; expected a single "
                            "line `<archetype>-v<MAJOR>.<MINOR>`"
                        ),
                    )
                )
            elif not _POLICY_VERSION_RE.match(version_line):
                findings.append(
                    Finding(
                        severity=Severity.BLOCK,
                        rule_id="PP3",
                        path=path,
                        line=_find_h2_line(text, "Version") or 1,
                        message=(
                            f"Version line {version_line!r} does not match "
                            f"`<archetype>-v<MAJOR>.<MINOR>` (backticked)"
                        ),
                    )
                )

        # PP4: Trigger / Expected effect / Rollback bodies are non-empty.
        for section in ("Trigger", "Expected effect", "Rollback"):
            body = _extract_section_body(text, section)
            if body is not None and not body.strip():
                findings.append(
                    Finding(
                        severity=Severity.BLOCK,
                        rule_id="PP4",
                        path=path,
                        line=_find_h2_line(text, section) or 1,
                        message=(
                            f"'## {section}' section is empty; B.3 "
                            f"registry requires a concrete body"
                        ),
                    )
                )

    return findings


# ---------------------------------------------------------------------------
# B.6: check tool-risk
# ---------------------------------------------------------------------------

_TOOL_RISK_APPROVAL_CLASSES: frozenset[str] = frozenset(
    {"direct", "approve", "edit", "reject"}
)

# Parse a 4-column registry row:
#   | Tool | Auto-mode envelope | Bypass envelope | Notes |
_TOOL_RISK_ROW_RE = re.compile(
    r"^\|\s*(?P<tool>.+?)\s*\|\s*(?P<auto>.+?)\s*\|\s*(?P<bypass>.+?)\s*\|\s*(?P<notes>.*?)\s*\|\s*$"
)

_ALLOWLIST_ENTRY_RE = re.compile(r'^\s*"([^"]+)"[,\s]*$')


def _load_permissions_allow(settings_path: Path) -> list[str]:
    """Extract the ``permissions.allow`` string array from settings.json
    using a lightweight structural scan (avoids pulling in a JSON parser
    that would error on comments).

    Returns the ordered list of allow entries. Returns an empty list if
    the file does not exist or the ``allow`` array cannot be located.
    """
    try:
        text = settings_path.read_text(encoding="utf-8")
    except OSError:
        return []
    # Locate the start of the "allow": [ ... ] block.
    start = text.find('"allow"')
    if start < 0:
        return []
    bracket = text.find("[", start)
    if bracket < 0:
        return []
    close = text.find("]", bracket)
    if close < 0:
        return []
    body = text[bracket + 1 : close]
    entries: list[str] = []
    for raw in body.splitlines():
        m = _ALLOWLIST_ENTRY_RE.match(raw.rstrip())
        if m:
            entries.append(m.group(1))
    return entries


def _parse_tool_risk_rows(text: str) -> list[tuple[int, str, str, str, str]]:
    """Return ``(line_no, tool, auto_class, bypass_class, notes)`` rows.

    Skips header rows, separator rows, and template placeholder rows
    (`(...)`). Line numbers are 1-indexed.
    """
    rows: list[tuple[int, str, str, str, str]] = []
    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line.startswith("|"):
            continue
        if re.match(r"^\|[\s\-:|]+\|\s*$", line):
            continue
        m = _TOOL_RISK_ROW_RE.match(line)
        if not m:
            continue
        tool = m.group("tool").strip()
        auto = m.group("auto").strip()
        bypass = m.group("bypass").strip()
        notes = m.group("notes").strip()
        low = tool.lower()
        if low in {"tool", "item"}:
            continue
        if tool.startswith("(") and tool.endswith(")"):
            continue
        rows.append((i, tool, auto, bypass, notes))
    return rows


def _approval_class_first_token(cell: str) -> str:
    """Registry cells are of the form ``direct`` or ``approve (classifier
    gates…)``. Return the first lowercase token."""
    match = re.match(r"^([a-z]+)", cell.strip().lower())
    return match.group(1) if match else ""


def check_tool_risk(roots: list[Path], repo_root: Path) -> list[Finding]:
    """Return B.6 findings: registry file exists; every row has both
    envelope columns populated with a valid approval class; every entry
    in ``permissions.allow`` has at least one matching row.
    """
    findings: list[Finding] = []
    default_path = repo_root / ".claude" / "rules" / "tool_risk_registry.md"
    registry_path = roots[0] if roots else default_path
    if registry_path.is_dir():
        registry_path = registry_path / "tool_risk_registry.md"

    if not registry_path.exists():
        findings.append(
            Finding(
                severity=Severity.BLOCK,
                rule_id="TR0",
                path=registry_path,
                line=1,
                message=(
                    "tool_risk_registry.md not found (B.6 — shaping §5.1). "
                    "Register every tool in permissions.allow."
                ),
            )
        )
        return findings

    try:
        text = registry_path.read_text(encoding="utf-8")
    except OSError as exc:
        findings.append(
            Finding(
                severity=Severity.BLOCK,
                rule_id="TR0",
                path=registry_path,
                line=1,
                message=f"cannot read registry: {exc}",
            )
        )
        return findings

    rows = _parse_tool_risk_rows(text)
    if not rows:
        findings.append(
            Finding(
                severity=Severity.BLOCK,
                rule_id="TR1",
                path=registry_path,
                line=1,
                message="registry contains zero rows — expected coverage table",
            )
        )
        return findings

    # TR2: every row has both envelopes populated with a valid class.
    for line_no, tool, auto_cell, bypass_cell, notes in rows:
        for label, cell in (("auto-mode", auto_cell), ("bypass", bypass_cell)):
            if not cell or cell.upper() == "TBD":
                findings.append(
                    Finding(
                        severity=Severity.BLOCK,
                        rule_id="TR2",
                        path=registry_path,
                        line=line_no,
                        message=(
                            f"row {tool!r}: {label} envelope column is empty or TBD"
                        ),
                    )
                )
                continue
            first = _approval_class_first_token(cell)
            if first not in _TOOL_RISK_APPROVAL_CLASSES:
                findings.append(
                    Finding(
                        severity=Severity.BLOCK,
                        rule_id="TR2",
                        path=registry_path,
                        line=line_no,
                        message=(
                            f"row {tool!r}: {label} class {first!r} is not "
                            f"one of {{direct, approve, edit, reject}}"
                        ),
                    )
                )

        # TR3: every reject-under-bypass row has a Notes explanation.
        bypass_first = _approval_class_first_token(bypass_cell)
        if bypass_first == "reject" and not notes:
            findings.append(
                Finding(
                    severity=Severity.WARN,
                    rule_id="TR3",
                    path=registry_path,
                    line=line_no,
                    message=(
                        f"row {tool!r}: reject-under-bypass requires a "
                        f"Notes explanation (destructive/exfil/etc)"
                    ),
                )
            )

    # TR4: every permissions.allow entry has at least one row covering it.
    # Matching is lenient: an entry is covered if its exact string appears
    # in any row's Tool column, OR if a backticked-form of it appears.
    # This lets the registry group related entries (e.g., a single
    # ``Edit(.claude/rules/**)`` row covers both Edit+Write pair entries
    # by explicitly listing both in the Tool cell when needed).
    settings_path = repo_root / ".claude" / "settings.json"
    allow = _load_permissions_allow(settings_path)
    registry_blob = "\n".join(r[1] for r in rows)
    for entry in allow:
        if entry in registry_blob:
            continue
        # Fall back: try the first-prefix match (``Bash(git *)`` inside
        # a cell that lists ``Bash(git *)``). Same test as `in`, so this
        # branch exists for future extension (e.g., regex-based rows).
        findings.append(
            Finding(
                severity=Severity.BLOCK,
                rule_id="TR4",
                path=registry_path,
                line=1,
                message=(
                    f"permissions.allow entry {entry!r} has no registry "
                    f"row (grep cross-check — shaping §5.2 item 3)"
                ),
            )
        )

    return findings


# ---------------------------------------------------------------------------
# B.11: check recipes
# ---------------------------------------------------------------------------

_RECIPE_REQUIRED_SECTIONS: tuple[str, ...] = (
    "Version",
    "Context",
    "Decision",
    "Observed outcome",
    "Reuse guidance",
    "Downstream citations",
)

_RECIPE_VERSION_RE = re.compile(r"^`b11-recipe-[a-z0-9][a-z0-9_-]*-v\d+\.\d+`$")


def _recipe_files_under(root: Path) -> list[Path]:
    """Return non-archive, non-template recipe markdown files."""
    if not root.is_dir():
        return []
    files: list[Path] = []
    for p in sorted(root.rglob("*.md")):
        parts = set(p.parts)
        if "_archive" in parts or "archive" in parts:
            continue
        if p.name == "_template.md":
            continue
        if p.name == "INDEX.md":
            continue
        files.append(p)
    return files


def check_recipes(roots: list[Path], repo_root: Path) -> list[Finding]:
    """Return B.11 findings: every recipe file has six required sections;
    the archive ``INDEX.md`` references every non-archive, non-template
    recipe.
    """
    findings: list[Finding] = []
    default_root = repo_root / "knowledge" / "orchestration_recipes"
    search_root = roots[0] if roots else default_root
    if search_root.is_file():
        search_root = search_root.parent

    if not search_root.exists():
        findings.append(
            Finding(
                severity=Severity.BLOCK,
                rule_id="RC0",
                path=search_root,
                line=1,
                message=(
                    "knowledge/orchestration_recipes/ not found (B.11 — shaping §8.1)"
                ),
            )
        )
        return findings

    index_path = search_root / "INDEX.md"
    if not index_path.exists():
        findings.append(
            Finding(
                severity=Severity.BLOCK,
                rule_id="RC1",
                path=index_path,
                line=1,
                message=(
                    "archive INDEX.md missing (B.11 — shaping §8.5). "
                    "Every non-archive recipe must be indexed."
                ),
            )
        )
        index_text = ""
    else:
        try:
            index_text = index_path.read_text(encoding="utf-8")
        except OSError as exc:
            findings.append(
                Finding(
                    severity=Severity.BLOCK,
                    rule_id="RC1",
                    path=index_path,
                    line=1,
                    message=f"cannot read INDEX.md: {exc}",
                )
            )
            index_text = ""

    recipes = _recipe_files_under(search_root)

    for path in recipes:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            findings.append(
                Finding(
                    severity=Severity.BLOCK,
                    rule_id="RC2",
                    path=path,
                    line=1,
                    message=f"cannot read recipe: {exc}",
                )
            )
            continue

        # RC2: required sections exist.
        for section in _RECIPE_REQUIRED_SECTIONS:
            if _find_h2_line(text, section) is None:
                findings.append(
                    Finding(
                        severity=Severity.BLOCK,
                        rule_id="RC2",
                        path=path,
                        line=1,
                        message=(
                            f"missing required section '## {section}' "
                            f"(B.11 recipe schema — shaping §8.2)"
                        ),
                    )
                )

        # RC3: Version body matches the canonical format.
        version_body = _extract_section_body(text, "Version")
        if version_body is not None:
            version_line = None
            for raw in version_body.splitlines():
                stripped = raw.strip()
                if not stripped:
                    continue
                version_line = stripped
                break
            if version_line is None or not _RECIPE_VERSION_RE.match(version_line):
                findings.append(
                    Finding(
                        severity=Severity.BLOCK,
                        rule_id="RC3",
                        path=path,
                        line=_find_h2_line(text, "Version") or 1,
                        message=(
                            f"Version {version_line!r} does not match "
                            f"`b11-recipe-<slug>-v<MAJOR>.<MINOR>`"
                        ),
                    )
                )

        # RC4: INDEX.md references this recipe (by filename).
        if index_text and path.name not in index_text:
            findings.append(
                Finding(
                    severity=Severity.WARN,
                    rule_id="RC4",
                    path=index_path,
                    line=1,
                    message=(
                        f"recipe {path.name!r} is not referenced in INDEX.md "
                        f"(B.11 — shaping §8.5)"
                    ),
                )
            )

    return findings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_findings(findings: list[Finding], stream) -> None:  # type: ignore[no-untyped-def]
    for f in findings:
        print(f.format_line(), file=stream)


def _exit_code_for_findings(findings: list[Finding], warnings_ok: bool) -> int:
    blocks = [f for f in findings if f.severity == Severity.BLOCK]
    warns = [f for f in findings if f.severity == Severity.WARN]
    if blocks:
        return 2
    if warns and not warnings_ok:
        return 2
    return 0


def _default_roots(repo_root: Path, rule_set: str) -> list[Path]:
    if rule_set == "prompt-policy":
        return [repo_root / ".claude" / "rules" / "prompt_policy"]
    if rule_set == "tool-risk":
        return [repo_root / ".claude" / "rules" / "tool_risk_registry.md"]
    if rule_set == "recipes":
        return [repo_root / "knowledge" / "orchestration_recipes"]
    return [repo_root / "plans"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agent_readability_lint",
        description=(
            "Agent-readability lint for steward-platform plan health "
            "(Pattern 9 + Pattern 10 + B.3/B.6/B.11 registries)."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root (default: inferred from script path)",
    )
    parser.add_argument(
        "--warnings-ok",
        action="store_true",
        help="Exit 0 even if WARN findings are present (BLOCK still exits 2).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Run a named rule set")
    check_sub = check.add_subparsers(dest="rule_set", required=True)

    vc = check_sub.add_parser(
        "verification-contract",
        help="Pattern 10 — verify surface-per-deliverable contract",
    )
    vc.add_argument("paths", nargs="*", type=Path, help="Plan paths to walk")

    lbo = check_sub.add_parser(
        "load-bearing-ownership",
        help="Pattern 9 — verify load-bearing items have named owners",
    )
    lbo.add_argument("paths", nargs="*", type=Path, help="Plan paths to walk")

    pp = check_sub.add_parser(
        "prompt-policy",
        help="B.3 — verify prompt-policy registry schema (4 sections + version format)",
    )
    pp.add_argument("paths", nargs="*", type=Path, help="Policy paths to walk")

    tr = check_sub.add_parser(
        "tool-risk",
        help="B.6 — verify tool-risk registry schema (dual-envelope + allow-list coverage)",
    )
    tr.add_argument(
        "paths", nargs="*", type=Path, help="Registry path (file or containing dir)"
    )

    rc = check_sub.add_parser(
        "recipes",
        help="B.11 — verify orchestration-recipe archive schema (6 sections + INDEX)",
    )
    rc.add_argument("paths", nargs="*", type=Path, help="Archive paths to walk")

    args = parser.parse_args(argv)
    repo_root: Path = args.repo_root.resolve()
    paths: list[Path] = list(args.paths) or _default_roots(repo_root, args.rule_set)

    # Validate paths exist to avoid silent empty walks — but for
    # rule-sets whose defaults may not exist yet (e.g., ``tool-risk``
    # before the registry is authored), let the check produce a
    # BLOCK finding rather than an invocation error so CI surfaces
    # the gap as a lint finding (not a bad-arg).
    strict_missing_paths = args.rule_set in {
        "verification-contract",
        "load-bearing-ownership",
    }
    for p in paths:
        if not p.exists() and strict_missing_paths:
            print(f"ERROR: path not found: {p}", file=sys.stderr)
            return 1

    if args.rule_set == "verification-contract":
        findings = check_verification_contract(paths, repo_root)
    elif args.rule_set == "load-bearing-ownership":
        findings = check_load_bearing_ownership(paths, repo_root)
    elif args.rule_set == "prompt-policy":
        findings = check_prompt_policy(paths, repo_root)
    elif args.rule_set == "tool-risk":
        findings = check_tool_risk(paths, repo_root)
    elif args.rule_set == "recipes":
        findings = check_recipes(paths, repo_root)
    else:  # pragma: no cover - argparse enforces
        print(f"ERROR: unknown rule set: {args.rule_set}", file=sys.stderr)
        return 1

    if findings:
        _print_findings(findings, sys.stdout)
    else:
        print("agent_readability_lint: 0 findings")

    return _exit_code_for_findings(findings, args.warnings_ok)


if __name__ == "__main__":
    sys.exit(main())
