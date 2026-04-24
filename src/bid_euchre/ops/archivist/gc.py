"""GC-mode archivist collector + templater — Phase 0 code-path scaffold.

Per shape §4.2, Phase 0 ships the *code path* only — module, templates,
CLI dispatch, seeded fake-KB fixture tests. No operator-facing activation.
Phase 1 activation (outcome D.1c) is the proving-run workflow gated on
SC #15 (≥3 accepted proposals across ≥2 categories).

Five gc_class values are supported:

- ``stale`` — KB entry not referenced recently
- ``dead-skill`` — skill not invoked since promotion
- ``obsolete-policy`` — superseded prompt-policy version
- ``orphan`` — file whose referenced target is missing
- ``expired`` — KB entry whose evidence link has expired

The input sources (shape §4.2.2) are surfaced through a small
``KBSnapshot`` dataclass so tests can inject deterministic fake-KB state.
Live-source loading is not implemented at Phase 0 — it would rely on
infrastructure not yet in place (Primitive A events for skill invocation
telemetry, B.3 registry for policy supersession). The live-load hooks
are stubbed with clear ``TODO(phase-1)`` markers.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import events as archivist_events
from . import templates as tpl

logger = logging.getLogger("ops.archivist.gc")

# Exit-code sentinels mirror lessons mode.
EXIT_OK = 0
EXIT_EMPTY = 1
EXIT_SOURCE_UNREACHABLE = 2
EXIT_WRITE_FAIL = 3

GC_CLASSES = ("stale", "dead-skill", "obsolete-policy", "orphan", "expired")


@dataclass(frozen=True)
class GCProposal:
    """A single GC proposal in one of the five classes."""

    gc_class: str
    target_paths: tuple[str, ...]
    proposed_action: str
    evidence: str
    rollback: str


@dataclass
class KBSnapshot:
    """Deterministic snapshot of KB state, used by the Phase 0 fake-KB
    fixture path. Each list contains paths relative to the repo root.

    Phase 1 will replace this with live loaders (filesystem walk + PR
    body grep + skill-invocation event stream + B.3 registry index).
    """

    all_files: list[str] = field(default_factory=list)
    references: dict[str, list[str]] = field(default_factory=dict)
    # ``references`` maps file path → list of referencing locations.

    skills: list[str] = field(default_factory=list)
    skill_last_invoked: dict[str, datetime | None] = field(default_factory=dict)
    # ``None`` means "never since promotion".

    prompt_policies: list[str] = field(default_factory=list)
    superseded_policies: dict[str, str] = field(default_factory=dict)
    # mapping: old_version path → new_version path

    orphans: dict[str, str] = field(default_factory=dict)
    # mapping: orphan_path → missing_target

    expired: dict[str, str] = field(default_factory=dict)
    # mapping: kb_entry_path → expired_evidence_link


@dataclass
class GCRunResult:
    """Structured result of a gc-mode run."""

    output_path: Path | None
    proposal_count: int
    exit_code: int
    classes_covered: list[str] = field(default_factory=list)


def run_gc(
    candidates_dir: Path,
    *,
    snapshot: KBSnapshot | None = None,
    dry_run: bool = False,
    when: datetime | None = None,
) -> GCRunResult:
    """Execute one GC-mode archivist run.

    Args:
        candidates_dir: target candidates directory.
        snapshot: deterministic KBSnapshot for the fixture path. If None,
            Phase 0 returns an empty result (live-load is Phase 1).
        dry_run: if True, derive proposals but do not write.
        when: ISO-date override; defaults to now(UTC).
    """
    when = when or datetime.now(timezone.utc).replace(microsecond=0)

    if snapshot is None:
        logger.info(
            "gc mode: no snapshot provided; live-load path is Phase 1 — "
            "returning empty result (no proposals)"
        )
        return GCRunResult(
            output_path=None,
            proposal_count=0,
            exit_code=EXIT_EMPTY,
            classes_covered=[],
        )

    proposals = _derive_proposals(snapshot)

    if not proposals:
        return GCRunResult(
            output_path=None,
            proposal_count=0,
            exit_code=EXIT_EMPTY,
            classes_covered=[],
        )

    grouped: dict[str, list[GCProposal]] = defaultdict(list)
    for p in proposals:
        grouped[p.gc_class].append(p)

    classes_covered = [c for c in GC_CLASSES if c in grouped]

    output_path = _output_path_for_today(candidates_dir, when)

    if dry_run:
        return GCRunResult(
            output_path=output_path,
            proposal_count=len(proposals),
            exit_code=EXIT_OK,
            classes_covered=classes_covered,
        )

    try:
        _write_or_append(
            output_path=output_path,
            grouped=grouped,
            when=when,
            kb_count=len(snapshot.all_files),
        )
    except OSError as exc:
        logger.error("Write failure to %s: %s", output_path, exc)
        return GCRunResult(
            output_path=output_path,
            proposal_count=len(proposals),
            exit_code=EXIT_WRITE_FAIL,
            classes_covered=classes_covered,
        )

    for proposal in proposals:
        try:
            archivist_events.emit_gc_proposed(
                candidate_path=output_path,
                gc_class=proposal.gc_class,
                target_paths=list(proposal.target_paths),
            )
        except Exception as exc:  # pragma: no cover - A schema drift
            logger.warning("Emission failed for gc proposal: %s", exc)

    return GCRunResult(
        output_path=output_path,
        proposal_count=len(proposals),
        exit_code=EXIT_OK,
        classes_covered=classes_covered,
    )


# ----- Derivation -----


def _derive_proposals(snapshot: KBSnapshot) -> list[GCProposal]:
    """Run all five gc_class detectors over the snapshot."""
    out: list[GCProposal] = []
    out.extend(_detect_stale(snapshot))
    out.extend(_detect_dead_skills(snapshot))
    out.extend(_detect_obsolete_policies(snapshot))
    out.extend(_detect_orphans(snapshot))
    out.extend(_detect_expired(snapshot))
    return out


def _detect_stale(snapshot: KBSnapshot) -> list[GCProposal]:
    """Entries in ``all_files`` with zero entries in ``references``
    (i.e., nobody references them) are candidate stale entries."""
    out: list[GCProposal] = []
    for path in snapshot.all_files:
        refs = snapshot.references.get(path, [])
        if len(refs) > 0:
            continue
        out.append(
            GCProposal(
                gc_class="stale",
                target_paths=(path,),
                proposed_action="mark stale",
                evidence=f"No referencing entries found in references map for {path}",
                rollback="git revert the mark-stale commit",
            )
        )
    return out


def _detect_dead_skills(snapshot: KBSnapshot) -> list[GCProposal]:
    """Skills with ``skill_last_invoked == None`` are dead."""
    out: list[GCProposal] = []
    for skill in snapshot.skills:
        last = snapshot.skill_last_invoked.get(skill)
        if last is not None:
            continue
        out.append(
            GCProposal(
                gc_class="dead-skill",
                target_paths=(skill,),
                proposed_action="retire skill",
                evidence="No invocation events since promotion",
                rollback="git revert the retirement commit",
            )
        )
    return out


def _detect_obsolete_policies(snapshot: KBSnapshot) -> list[GCProposal]:
    """Policies in ``superseded_policies`` keys are obsolete — superseded
    by the mapped value's version."""
    out: list[GCProposal] = []
    for old_path, new_path in snapshot.superseded_policies.items():
        out.append(
            GCProposal(
                gc_class="obsolete-policy",
                target_paths=(old_path,),
                proposed_action=f"retire — superseded by {new_path}",
                evidence=f"B.3 registry marks {old_path} as superseded by {new_path}",
                rollback="git revert the retirement commit",
            )
        )
    return out


def _detect_orphans(snapshot: KBSnapshot) -> list[GCProposal]:
    """Entries in ``snapshot.orphans`` are paths whose reference targets
    do not exist."""
    out: list[GCProposal] = []
    for orphan_path, missing_target in snapshot.orphans.items():
        out.append(
            GCProposal(
                gc_class="orphan",
                target_paths=(orphan_path,),
                proposed_action="resolve or delete",
                evidence=f"References missing target `{missing_target}`",
                rollback="git revert the resolution commit",
            )
        )
    return out


def _detect_expired(snapshot: KBSnapshot) -> list[GCProposal]:
    """Entries in ``snapshot.expired`` are KB entries whose evidence link
    is marked expired."""
    out: list[GCProposal] = []
    for entry_path, expired_link in snapshot.expired.items():
        out.append(
            GCProposal(
                gc_class="expired",
                target_paths=(entry_path,),
                proposed_action="refresh evidence or retire entry",
                evidence=f"Expired evidence link: {expired_link}",
                rollback="git revert the refresh/retirement commit",
            )
        )
    return out


# ----- Output -----


def _output_path_for_today(candidates_dir: Path, when: datetime) -> Path:
    """Return ``<candidates_dir>/<YYYY-MM-DD>_gc.md`` for ``when``."""
    date_str = when.strftime("%Y-%m-%d")
    return candidates_dir / f"{date_str}_gc.md"


def _write_or_append(
    *,
    output_path: Path,
    grouped: dict[str, list[GCProposal]],
    when: datetime,
    kb_count: int,
) -> None:
    """Write the GC candidate markdown file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    proposal_count = sum(len(v) for v in grouped.values())

    parts = [
        tpl.GC_HEADER.format(
            date=when.strftime("%Y-%m-%d"),
            run_ts=when.isoformat(),
            kb_count=kb_count,
            proposal_count=proposal_count,
        ),
        tpl.GC_SECTION_1_HEADER,
        _render_section(grouped.get("stale", [])),
        tpl.GC_SECTION_2_HEADER,
        _render_section(grouped.get("dead-skill", [])),
        tpl.GC_SECTION_3_HEADER,
        _render_section(grouped.get("obsolete-policy", [])),
        tpl.GC_SECTION_4_HEADER,
        _render_section(grouped.get("orphan", [])),
        tpl.GC_SECTION_5_HEADER,
        _render_section(grouped.get("expired", [])),
        tpl.GC_FOOTER,
    ]
    body = "".join(parts)

    mode = "a" if output_path.exists() else "w"
    with open(output_path, mode, encoding="utf-8") as fh:
        if mode == "a":
            fh.write("\n---\n\n")
        fh.write(body)


def _render_section(items: list[GCProposal]) -> str:
    if not items:
        return "_No proposals this run._\n\n"
    lines: list[str] = []
    for idx, p in enumerate(items, start=1):
        target_list = ", ".join(f"`{t}`" for t in p.target_paths)
        lines.append(f"### Proposal {idx}\n\n")
        lines.append(f"- **Target paths:** {target_list}\n")
        lines.append(f"- **Proposed action:** {p.proposed_action}\n")
        lines.append(f"- **Evidence:** {p.evidence}\n")
        lines.append(f"- **Rollback:** {p.rollback}\n\n")
    return "".join(lines)


# ----- Fake-KB fixture loader (test helper) -----


def load_fake_kb_snapshot(fixture_dir: Path) -> KBSnapshot:
    """Load a ``KBSnapshot`` from a structured fixture directory.

    The fixture directory layout mirrors the Phase 1 live sources:

    - ``all_files.txt`` — one path per line
    - ``references.txt`` — ``<path>\\t<referencing_location>`` per line
    - ``skills.txt`` — one skill path per line
    - ``skill_invocations.txt`` — ``<path>\\t<last_ts_or_none>`` per line
    - ``superseded_policies.txt`` — ``<old>\\t<new>`` per line
    - ``orphans.txt`` — ``<orphan>\\t<missing_target>`` per line
    - ``expired.txt`` — ``<entry>\\t<link>`` per line

    Any missing file is treated as empty; the fixture is permissive by
    design so tests can assert one gc_class in isolation without having
    to populate all five.
    """
    snapshot = KBSnapshot()

    all_files_path = fixture_dir / "all_files.txt"
    if all_files_path.exists():
        snapshot.all_files = [
            line.strip()
            for line in all_files_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    refs_path = fixture_dir / "references.txt"
    if refs_path.exists():
        for line in refs_path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or "\t" not in line:
                continue
            path, ref = line.split("\t", 1)
            snapshot.references.setdefault(path, []).append(ref)

    skills_path = fixture_dir / "skills.txt"
    if skills_path.exists():
        snapshot.skills = [
            line.strip()
            for line in skills_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    inv_path = fixture_dir / "skill_invocations.txt"
    if inv_path.exists():
        for line in inv_path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or "\t" not in line:
                continue
            skill, ts = line.split("\t", 1)
            ts = ts.strip()
            parsed: datetime | None
            if ts == "" or ts.lower() == "none":
                parsed = None
            else:
                try:
                    parsed = datetime.fromisoformat(ts)
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                except ValueError:
                    parsed = None
            snapshot.skill_last_invoked[skill] = parsed

    sup_path = fixture_dir / "superseded_policies.txt"
    if sup_path.exists():
        for line in sup_path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or "\t" not in line:
                continue
            old, new = line.split("\t", 1)
            snapshot.superseded_policies[old] = new

    orphans_path = fixture_dir / "orphans.txt"
    if orphans_path.exists():
        for line in orphans_path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or "\t" not in line:
                continue
            orph, target = line.split("\t", 1)
            snapshot.orphans[orph] = target

    expired_path = fixture_dir / "expired.txt"
    if expired_path.exists():
        for line in expired_path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or "\t" not in line:
                continue
            entry, link = line.split("\t", 1)
            snapshot.expired[entry] = link

    # Phase-1 hook: populate snapshot.skills from skill_invocations.txt if
    # skills.txt was missing.
    if not snapshot.skills and snapshot.skill_last_invoked:
        snapshot.skills = list(snapshot.skill_last_invoked.keys())

    # `Any` below used only to silence strict type-checkers if extended in future.
    _: Any = snapshot
    return snapshot
