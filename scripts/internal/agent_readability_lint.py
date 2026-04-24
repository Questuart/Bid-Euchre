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
    """Return all Pattern 10 findings across the given plan roots.

    Also runs the events-emission sub-checks (VC4/VC5) introduced in
    Primitive A §8.2 step 9: unknown event_type passed to ``emit()``
    is BLOCK, §9.7 first-class IDs routed through ``extra_fields=`` is
    WARN (Pattern 8 "extra_fields-as-bug-marker" signal).
    """
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

    # Rules VC4/VC5 — events.emit() call-site audit. Scans the repo's Python
    # surfaces for emit() calls and validates them against the Event Schema
    # v1.0 registry.
    findings.extend(_check_emit_call_sites(repo_root))

    return findings


# ---------------------------------------------------------------------------
# Event emission sub-checks (Primitive A §8.2 step 9)
# ---------------------------------------------------------------------------


#: Python source roots scanned for ``emit("<event_type>", ...)`` call-sites.
#: Tests are intentionally excluded — they legitimately construct arbitrary
#: event-type literals for fixtures.
_EMIT_SCAN_ROOTS: tuple[str, ...] = ("src/bid_euchre", "scripts", "experiments")

#: Python source files excluded from emit-call-site scanning because they
#: are the definitions / helpers, not emission call-sites.
_EMIT_SCAN_EXCLUDE: tuple[str, ...] = (
    "src/bid_euchre/ops/events.py",
    "src/bid_euchre/ops/event_schema.py",
    "src/bid_euchre/ops/event_writer.py",
    "src/bid_euchre/ops/event_taxonomy.py",
    "scripts/internal/audit_event_emission.py",
    "scripts/internal/agent_readability_lint.py",
)


#: Matches ``emit("<type>", ...)`` / ``events.emit("<type>", ...)`` /
#: ``v1_emit("<type>", ...)``. Capture group 0 is the event type literal,
#: capture group 1 is the tail of the call (up to a balanced-enough paren).
_EMIT_CALL_RE = re.compile(
    r"""
    (?:\bevents\.emit|\bv1_emit|\bemit)    # callable spellings
    \s*\(\s*
    ["'](?P<event_type>[a-z_][a-z0-9_]*)["']
    (?P<tail>[^)]*)           # remaining kwargs up to closing paren
    \)
    """,
    re.VERBOSE | re.DOTALL,
)


#: Canonical §9.7 first-class IDs. Routing any of these through
#: ``extra_fields=`` is a Pattern 8 bug marker — they must land at the
#: top level of the record per ADR 007.
_FIRST_CLASS_IDS: frozenset[str] = frozenset(
    {
        "project_id",
        "cell_id",
        "session_id",
        "task_id",
        "lane_id",
        "trace_id",
        "incident_fingerprint",
        "prompt_policy_version",
        "schema_version",
    }
)


def _check_emit_call_sites(repo_root: Path) -> list[Finding]:
    """Scan Python sources for emit() call-sites and produce VC4/VC5 findings.

    VC4 (BLOCK): unknown event_type literal passed to emit(). Only literal
    strings are checked — dynamic ``emit(type_var, ...)`` usages are
    out of scope (audit_event_emission.py will catch those through the
    no-emitter-for-class path instead).

    VC5 (WARN): §9.7 first-class IDs routed through ``extra_fields=``.
    These must land at the top level per ADR 007 "extra_fields is a bug
    marker" (Pattern 8).
    """
    findings: list[Finding] = []
    known_types = _load_known_event_types(repo_root)
    if known_types is None:
        # Schema module not importable — skip (not a lint failure).
        return findings
    for source_path in _iter_emit_scan_files(repo_root):
        try:
            text = source_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in _EMIT_CALL_RE.finditer(text):
            event_type = m.group("event_type")
            tail = m.group("tail") or ""
            # Compute line number (1-indexed) for the matched literal.
            line_no = text[: m.start()].count("\n") + 1
            # VC4: unknown event_type.
            if event_type not in known_types:
                findings.append(
                    Finding(
                        severity=Severity.BLOCK,
                        rule_id="VC4",
                        path=source_path,
                        line=line_no,
                        message=(
                            f"emit({event_type!r}) — event_type not registered in "
                            f"EVENT_FIELD_REGISTRY. Either add a spec to "
                            f"event_schema.py or fix the typo."
                        ),
                    )
                )
            # VC5: §9.7 ID routed through extra_fields.
            leaked_ids = _extra_fields_leaked_ids(tail)
            if leaked_ids:
                findings.append(
                    Finding(
                        severity=Severity.WARN,
                        rule_id="VC5",
                        path=source_path,
                        line=line_no,
                        message=(
                            f"emit({event_type!r}) routes §9.7 first-class ID(s) "
                            f"{sorted(leaked_ids)!r} through extra_fields=; these "
                            f"must be top-level kwargs (Pattern 8: "
                            f"extra_fields-is-a-bug-marker)."
                        ),
                    )
                )
    return findings


def _iter_emit_scan_files(repo_root: Path) -> list[Path]:
    """Enumerate Python files to scan for emit() call-sites."""
    paths: list[Path] = []
    excludes = {(repo_root / rel).resolve() for rel in _EMIT_SCAN_EXCLUDE}
    for rel in _EMIT_SCAN_ROOTS:
        root = repo_root / rel
        if not root.exists():
            continue
        for py in root.rglob("*.py"):
            try:
                resolved = py.resolve()
            except OSError:
                continue
            if resolved in excludes:
                continue
            paths.append(py)
    return paths


def _load_known_event_types(repo_root: Path) -> set[str] | None:
    """Load the set of registered event types from event_schema.py.

    Loads the module directly from its file path at
    ``<repo_root>/src/bid_euchre/ops/event_schema.py`` (bypassing
    ``sys.modules`` caching) so lint behaviour is per-repo-root and does
    not leak state between tmp_path-based tests and the live repo.

    Returns None if the schema file is absent (not a lint failure — a
    freshly cloned repo may legitimately lack it until Primitive A lands).
    """
    import importlib.util

    schema_path = repo_root / "src" / "bid_euchre" / "ops" / "event_schema.py"
    if not schema_path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location(
            f"_arl_schema_{abs(hash(str(schema_path)))}", schema_path
        )
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception:
        return None
    registry = getattr(mod, "EVENT_FIELD_REGISTRY", None)
    if not isinstance(registry, dict):
        return None
    return set(registry.keys())


# ``extra_fields={"lane_id": x, ...}`` — pattern for finding §9.7 IDs.
_EXTRA_FIELDS_BLOCK_RE = re.compile(
    r"""extra_fields\s*=\s*(?P<block>\{[^{}]*\})""",
    re.DOTALL,
)

_ID_KEY_RE = re.compile(r"""["'](?P<key>[a-z_][a-z0-9_]*)["']\s*:""")


def _extra_fields_leaked_ids(call_tail: str) -> set[str]:
    """Return the set of §9.7 IDs routed through ``extra_fields=`` literal
    dict, if any. Best-effort string-scan (AST not required for lint)."""
    leaked: set[str] = set()
    for block_m in _EXTRA_FIELDS_BLOCK_RE.finditer(call_tail):
        block = block_m.group("block")
        for key_m in _ID_KEY_RE.finditer(block):
            key = key_m.group("key")
            if key in _FIRST_CLASS_IDS:
                leaked.add(key)
    return leaked


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
# Pattern 9: check load-bearing-ownership (LBO1 / LBO2 / LBO3)
# ---------------------------------------------------------------------------


# High-leverage sections (governing-plan architectural). A reference that
# lives in one of these sections without a matching Work/Readiness bullet
# is a BLOCK-severity finding per §4.5.1 of Primitive C shaping.
_LBO_BLOCK_SECTIONS = ("5", "6.4", "13")


# Patterns that extract script / skill / module references from plan
# prose.  These are deliberately narrow to keep false-positives low.
_PLAN_REFERENCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"`(scripts/internal/[A-Za-z0-9_./\-]+\.py)`"),
    re.compile(r"`(src/bid_euchre/[A-Za-z0-9_./\-]+\.py)`"),
    re.compile(r"`(\.claude/skills/[A-Za-z0-9_./\-]+)`"),
    re.compile(r"`(\.claude/hooks/[A-Za-z0-9_./\-]+\.sh)`"),
    re.compile(r"(?<![/\w])/([a-z][a-z0-9\-]+)\b"),  # /<skill-name>
)


def _collect_plan_references(
    walk: PlanWalk,
    repo_root: Path,
) -> list[tuple[Path, int, str, str, str]]:
    """Walk every tracked plan file and return references to load-bearing
    targets.

    Returns ``[(plan_path, line, section_num, raw_reference, resolved_or_skill_name), ...]``.
    A reference is kept only when it resolves to an actual file under
    ``repo_root`` (to avoid emitting findings against speculative prose)
    OR is a ``/<skill-name>`` token whose skill dir exists.
    """
    refs: list[tuple[Path, int, str, str, str]] = []
    skills_root = repo_root / ".claude" / "skills"
    for path in walk.plans_walked:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        section_num = ""
        for i, line in enumerate(lines):
            m = SECTION_HEADING_RE.match(line)
            if m:
                section_num = m.group("num")
            for pat in _PLAN_REFERENCE_PATTERNS:
                for m2 in pat.finditer(line):
                    raw = m2.group(1)
                    if raw.startswith(("scripts/", "src/", ".claude/")):
                        resolved = repo_root / raw
                        if resolved.exists():
                            refs.append((path, i + 1, section_num, raw, raw))
                    else:
                        # /<skill-name> token — resolve as .claude/skills/<name>/SKILL.md
                        skill_dir = skills_root / raw
                        if skill_dir.is_dir():
                            resolved_path = f".claude/skills/{raw}/SKILL.md"
                            refs.append(
                                (path, i + 1, section_num, f"/{raw}", resolved_path)
                            )
    return refs


def _section_in_block_scope(section_num: str) -> bool:
    if not section_num:
        return False
    return any(
        section_num == top or section_num.startswith(top + ".")
        for top in _LBO_BLOCK_SECTIONS
    )


def _is_archive_reference(path: Path) -> bool:
    name = path.name.lower()
    parts = [p.lower() for p in path.parts]
    if any(p in {"_archive", "archive"} for p in parts):
        return True
    return bool(re.search(r"draft\d+", name))


def check_load_bearing_ownership(roots: list[Path], repo_root: Path) -> list[Finding]:
    """Pattern 9 — verify load-bearing items have named owners.

    Emits:
    * ``LBO1`` (BLOCK) — reference in §5-X / §6.4 / §13 with no matching
      Work/Readiness bullet.
    * ``LBO2`` (WARN)  — reference in any other section with no matching
      Work/Readiness bullet.
    * ``LBO3`` (WARN)  — target is referenced in an archival/draft file
      only (no live-plan enumeration).
    * ``HA1``  (WARN)  — harness-assumption brittleness-signal is not
      machine-observable (fires whenever the walk covers
      ``knowledge/harness_assumptions.md`` OR a plan file embeds a worked
      example with the brittleness-signal field).
    """
    # Include an extra root for the harness_assumptions.md check if it
    # exists — it may live outside the default plans/ walk.
    walk = walk_plans(roots)

    findings: list[Finding] = []
    refs = _collect_plan_references(walk, repo_root)

    # Collect *all* bulleted tokens across the walked plans (not just
    # tokens under a dedicated `### Work` heading). This keeps Pattern 9
    # precision-first: shape docs that enumerate deliverables under
    # `**Files created:**` or `### Scope` style headings satisfy the
    # ownership requirement as long as the target appears in a list item
    # somewhere in a live (non-archive) plan.
    per_file_bullets: dict[Path, list[str]] = _collect_all_bullets(walk.plans_walked)

    # Build the set of resolved targets that are referenced *somewhere* in
    # the live (non-archive) plan set, keyed by resolved path.
    live_refs: set[str] = set()
    archive_refs: set[str] = set()
    for plan_path, _line, _sec, _raw, resolved in refs:
        if _is_archive_reference(plan_path):
            archive_refs.add(resolved)
        else:
            live_refs.add(resolved)

    for plan_path, line, section_num, raw, resolved in refs:
        if _is_archive_reference(plan_path):
            continue  # archival references handled in LBO3 sweep
        if _bullet_exists_for_target(resolved, walk.deliverables):
            continue
        if _any_bullet_mentions_target(resolved, per_file_bullets):
            continue
        if _section_in_block_scope(section_num):
            findings.append(
                Finding(
                    severity=Severity.BLOCK,
                    rule_id="LBO1",
                    path=plan_path,
                    line=line,
                    message=(
                        f"§{section_num or '?'} references {raw!r} with no "
                        f"matching Work/Readiness bullet. Pattern 9: "
                        f"load-bearing items in §5-X / §6.4 / §13 must "
                        f"carry a named owner."
                    ),
                )
            )
        else:
            findings.append(
                Finding(
                    severity=Severity.WARN,
                    rule_id="LBO2",
                    path=plan_path,
                    line=line,
                    message=(
                        f"§{section_num or '?'} references {raw!r} with no "
                        f"matching Work/Readiness bullet. Pattern 9: "
                        f"add a Work bullet or move the reference into "
                        f"prose that cites the owning primitive."
                    ),
                )
            )

    # LBO3 — reference is *only* in archive/draft files. The main walker
    # skips archive dirs, so the archive refs collected above are the few
    # accidentally-included ones. Do a dedicated archive sweep.
    archive_only_refs = _collect_archive_references(roots, repo_root, live_refs)
    for plan_path, line, raw, _resolved in archive_only_refs:
        findings.append(
            Finding(
                severity=Severity.WARN,
                rule_id="LBO3",
                path=plan_path,
                line=line,
                message=(
                    f"{raw!r} is referenced only in archival/draft "
                    f"files. Pattern 9: enumerate it in a live plan "
                    f"or remove the load-bearing weight."
                ),
            )
        )
    _ = archive_refs  # legacy compatibility with main walk

    # HA1 — scan harness_assumptions.md (in knowledge/ tree or anywhere
    # the walk covered) for entries whose brittleness signal lacks a
    # machine-observable token.
    findings.extend(_check_harness_assumptions(repo_root, roots))

    return findings


def _collect_all_bullets(paths: list[Path]) -> dict[Path, list[str]]:
    """Walk each plan file and collect every list-item, stitching
    continuation lines onto the bullet they extend.

    Used by Pattern 9 to accept scope-enumeration bullets (under
    `**Files created:**` / `### Scope` headings) as valid ownership
    signals. Continuation lines are indented text following a bullet
    line; they are collapsed so multi-line bullets count as one unit
    of mention.
    """
    out: dict[Path, list[str]] = {}
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        bullets: list[str] = []
        current: list[str] | None = None
        for line in text.splitlines():
            m = re.match(r"^\s*[-*]\s+(.*\S)", line)
            if m:
                if current is not None:
                    bullets.append(" ".join(current))
                current = [m.group(1)]
                continue
            if current is not None:
                # Continuation: indented, non-empty, not another list
                if line.startswith((" ", "\t")) and line.strip():
                    current.append(line.strip())
                    continue
                # End of bullet.
                bullets.append(" ".join(current))
                current = None
        if current is not None:
            bullets.append(" ".join(current))
        out[path] = bullets
    return out


def _any_bullet_mentions_target(
    resolved: str, per_file_bullets: dict[Path, list[str]]
) -> bool:
    basename = resolved.rsplit("/", 1)[-1]
    for bullets in per_file_bullets.values():
        for text in bullets:
            if resolved in text:
                return True
            if basename and basename in text:
                return True
    return False


def _collect_archive_references(
    roots: list[Path],
    repo_root: Path,
    live_refs: set[str],
) -> list[tuple[Path, int, str, str]]:
    """Scan archive/draft plan files for load-bearing references that do
    not also appear in live (non-archive) plan files.

    The main ``walk_plans()`` filter intentionally skips archive dirs to
    keep Pattern 10 enforcement hermetic. LBO3 requires the opposite — we
    must visit archive/draft files specifically to detect references that
    have drifted out of the live plan set.

    Returns ``[(path, line, raw, resolved), ...]``.
    """
    out: list[tuple[Path, int, str, str]] = []
    seen: set[tuple[str, str]] = set()
    skills_root = repo_root / ".claude" / "skills"
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            if not _is_archive_reference(path):
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for i, line in enumerate(lines):
                for pat in _PLAN_REFERENCE_PATTERNS:
                    for m in pat.finditer(line):
                        raw = m.group(1)
                        resolved: str | None = None
                        if raw.startswith(("scripts/", "src/", ".claude/")):
                            if (repo_root / raw).exists():
                                resolved = raw
                        else:
                            skill_dir = skills_root / raw
                            if skill_dir.is_dir():
                                resolved = f".claude/skills/{raw}/SKILL.md"
                        if resolved is None or resolved in live_refs:
                            continue
                        key = (str(path), resolved)
                        if key in seen:
                            continue
                        seen.add(key)
                        display = (
                            f"/{raw}"
                            if not raw.startswith(("scripts/", "src/", ".claude/"))
                            else raw
                        )
                        out.append((path, i + 1, display, resolved))
    return out


def _bullet_target_keywords(text: str) -> list[str]:
    """Extract backtick-quoted or path-like tokens that could be bullet
    ownership references."""
    out: list[str] = []
    for m in re.finditer(r"`([^`]+)`", text):
        out.append(m.group(1).strip())
    for m in re.finditer(
        r"([A-Za-z_./][A-Za-z0-9_./\-]*\.(?:py|md|sh|json|ya?ml))", text
    ):
        out.append(m.group(1))
    return out


def _bullet_exists_for_target(resolved: str, bullets: list[DeliverableBullet]) -> bool:
    """Does any Work/Readiness bullet mention this resolved target?"""
    basename = resolved.rsplit("/", 1)[-1]
    for b in bullets:
        if resolved in b.bullet_text:
            return True
        if basename and basename in b.bullet_text:
            return True
        # Match skill-name tokens (`/archivist-run` maps to bullet containing `archivist`).
        if resolved.startswith(".claude/skills/") and basename in b.bullet_text:
            return True
    return False


# ---------------------------------------------------------------------------
# HA1 — harness-assumption brittleness-signal machine-observable check
# ---------------------------------------------------------------------------


_HA_SIGNAL_MACHINE_TOKENS = (
    re.compile(r"`[^`]+`"),  # backtick-quoted token (grep pattern / command)
    re.compile(r"\bmake\s+[a-z\-]+\b"),  # make <target>
    re.compile(r"\.github/workflows/[A-Za-z0-9_.\-]+\.ya?ml\b"),
    re.compile(r"\.claude/hooks/[A-Za-z0-9_.\-]+\b"),
)


def _check_harness_assumptions(repo_root: Path, roots: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    candidates: list[Path] = []
    # Always consider knowledge/harness_assumptions.md if it exists.
    ha_path = repo_root / "knowledge" / "harness_assumptions.md"
    if ha_path.exists():
        candidates.append(ha_path)
    # Also consider any file inside walk roots with that basename.
    for root in roots:
        if root.is_dir():
            for p in root.rglob("harness_assumptions.md"):
                if p not in candidates:
                    candidates.append(p)
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        findings.extend(_lint_harness_assumptions_file(path, text))
    return findings


def _lint_harness_assumptions_file(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = text.splitlines()
    i = 0
    current_entry_line = 0
    current_entry_name = ""
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m:
            current_entry_name = m.group(1).strip()
            current_entry_line = i + 1
            # Find the brittleness-signal field within the next ~10 lines.
            signal_text = _find_brittleness_signal(lines, i + 1)
            if signal_text is None:
                # No signal field at all — emit HA1.
                findings.append(
                    Finding(
                        severity=Severity.WARN,
                        rule_id="HA1",
                        path=path,
                        line=current_entry_line,
                        message=(
                            f"Harness-assumption {current_entry_name!r} has no "
                            f"Brittleness signal field. Pattern 9 / §4.1.2: "
                            f"each entry must carry a machine-observable signal."
                        ),
                    )
                )
            elif not _signal_is_machine_observable(signal_text):
                findings.append(
                    Finding(
                        severity=Severity.WARN,
                        rule_id="HA1",
                        path=path,
                        line=current_entry_line,
                        message=(
                            f"Harness-assumption {current_entry_name!r} "
                            f"brittleness signal is not machine-observable "
                            f"(no backtick pattern, `make <target>`, GitHub "
                            f"workflow, or `.claude/hooks/` reference). "
                            f"Pattern 9 / §4.1.2 requires a checkable token."
                        ),
                    )
                )
        i += 1
    return findings


def _find_brittleness_signal(lines: list[str], start: int) -> str | None:
    """Find the `**Brittleness signal:**` field after a `###` heading.

    Searches the entry body (until the next H3 heading or file end); does
    not cap at a fixed line count because longer entries (e.g., those
    with multi-paragraph observations or inline probe logs) legitimately
    place the brittleness signal past the first ~15 lines.
    """
    for i in range(start, len(lines)):
        # Stop at the next H3 or file end.
        if re.match(r"^###\s+", lines[i]):
            return None
        m = re.match(
            r"^\s*\*\*Brittleness signal:?\*\*\s*(.+?)\s*$",
            lines[i],
            re.IGNORECASE,
        )
        if m:
            # Consume continuation text on the next non-empty, non-heading line
            # when the signal wraps, but keep it simple: just return this line's payload.
            return m.group(1)
    return None


def _signal_is_machine_observable(signal: str) -> bool:
    return any(pat.search(signal) for pat in _HA_SIGNAL_MACHINE_TOKENS)


# ---------------------------------------------------------------------------
# Pattern 11: check pattern-11 (P11_1 / P11_2 / P11_3)
# ---------------------------------------------------------------------------


_PACKET_REFERENCE_RE = re.compile(r"Packet\s+(?P<id>[A-Za-z0-9\-_]+)")


def check_pattern_11(roots: list[Path], repo_root: Path) -> list[Finding]:
    """Pattern 11 — shape-then-execute dispatch discipline.

    Emits:
    * ``P11_1`` (BLOCK) — primitive directory under
      ``plans/steward_platform/<N>_primitive_<X>/`` exists but has no
      ``shaping.md`` sibling.
    * ``P11_2`` (WARN)  — stub only (git-log walk deferred until the
      review-driver V-precheck surface; this lint is run-against-existing
      and would false-positive on historical commits).  Kept as a hook for
      future PR-diff-based invocations.
    * ``P11_3`` (WARN)  — a ``shaping.md`` file references a Packet ID
      that does not appear in git log as an implementing PR or commit,
      best-effort via ``git grep``.
    """
    findings: list[Finding] = []
    findings.extend(_check_p11_1(repo_root))
    findings.extend(_check_p11_3(roots, repo_root))
    return findings


def _check_p11_1(repo_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    platform_root = repo_root / "plans" / "steward_platform"
    if not platform_root.exists():
        return findings
    for entry in sorted(platform_root.iterdir()):
        if not entry.is_dir():
            continue
        name = entry.name
        # Match dirs like `3_primitive_C`, `1_primitive_A`, etc.
        if not re.match(r"^\d+_primitive_[A-Z0-9]+$", name):
            continue
        shaping = entry / "shaping.md"
        if not shaping.exists():
            findings.append(
                Finding(
                    severity=Severity.BLOCK,
                    rule_id="P11_1",
                    path=entry,
                    line=1,
                    message=(
                        f"primitive directory {name} has no shaping.md. "
                        f"Pattern 11: shape-then-execute dispatch requires "
                        f"a shaping document before any execution packet."
                    ),
                )
            )
    return findings


def _check_p11_3(roots: list[Path], repo_root: Path) -> list[Finding]:
    """Flag shaping docs whose Packet IDs don't appear referenced.

    Best-effort: we grep the repo for the Packet ID (case-sensitive short
    form, 4+ chars) and emit WARN if zero matches.  False-positives are
    suppressed for Packet IDs whose ID is ambiguous prose (``X``, ``1``).
    """
    import subprocess  # local import to keep the module import-light

    findings: list[Finding] = []
    shaping_files: list[Path] = []
    for root in roots:
        if root.is_dir():
            shaping_files.extend(root.rglob("shaping.md"))
    for path in shaping_files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        packet_ids = {m.group("id") for m in _PACKET_REFERENCE_RE.finditer(text)}
        # Skip tiny tokens that are noise.
        packet_ids = {pid for pid in packet_ids if len(pid) >= 4}
        for pid in sorted(packet_ids):
            try:
                # Look for this packet ID anywhere in the repo outside
                # shaping docs themselves.
                result = subprocess.run(
                    ["git", "grep", "-l", pid],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                continue
            if result.returncode == 0:
                hits = [
                    line.strip()
                    for line in result.stdout.splitlines()
                    if line.strip() and not line.endswith("shaping.md")
                ]
                if hits:
                    continue
            findings.append(
                Finding(
                    severity=Severity.WARN,
                    rule_id="P11_3",
                    path=path,
                    line=1,
                    message=(
                        f"Packet {pid!r} is referenced in shaping doc but "
                        f"has no implementing PR / commit reference in the "
                        f"repo. Pattern 11: shaping docs that never lead to "
                        f"execution drift."
                    ),
                )
            )
    return findings


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

    p11 = check_sub.add_parser(
        "pattern-11",
        help="Pattern 11 — shape-then-execute dispatch discipline",
    )
    p11.add_argument("paths", nargs="*", type=Path, help="Plan paths to walk")

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
    elif args.rule_set == "pattern-11":
        findings = check_pattern_11(paths, repo_root)
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
