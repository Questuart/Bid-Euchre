"""Artifact lifecycle management for Arc D v2 lineage.

Manages run directory status (canonical, superseded, quarantined, etc.),
rerun manifests, supersession linking, and pruning of retired artifacts.

Status taxonomy from the governing plan section 4.5:
  - canonical:   part of official evidence chain
  - exploratory: experimental / not yet promoted
  - superseded:  replaced by a newer run
  - archived:    retained for historical reference, not active
  - quarantined: known-bad, excluded from all analysis
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# From the governing plan section 4.5
VALID_STATUSES = frozenset(
    {"canonical", "exploratory", "superseded", "archived", "quarantined"}
)


@dataclass
class ArtifactStatus:
    """Status marker for a run or artifact bundle.

    Persisted as ``status.json`` in the run directory.
    """

    status: str  # one of VALID_STATUSES
    run_id: str
    timestamp: str
    superseded_by: str | None = None  # run_id of replacement
    supersedes: str | None = None  # run_id this replaces
    quarantine_reason: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            msg = f"Invalid status {self.status!r}; expected one of {sorted(VALID_STATUSES)}"
            raise ValueError(msg)


@dataclass
class RerunManifest:
    """Record of a rerun event linking old and new runs."""

    rerun_id: str
    rung: str
    trigger: str  # "human_review", "canary_check", "upstream_correction", "manual"
    issue: str
    affected_models: list[str] = field(default_factory=list)
    affected_steps: list[str] = field(default_factory=list)
    supersedes_run_id: str = ""
    new_run_id: str = ""
    cross_rung_impact: str = ""
    timestamp: str = ""

    def save(self, path: Path) -> None:
        """Write manifest to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2) + "\n")

    @classmethod
    def load(cls, path: Path) -> RerunManifest:
        """Load manifest from JSON file."""
        return cls(**json.loads(path.read_text()))


# ── Run ID generation ─────────────────────────────────────────────────────


def generate_run_id(rung: str, mode: str, seed: int) -> str:
    """Generate a unique run ID per the naming contract (section 18).

    Format: ``arc_d_v2_<rung>_<mode>_seed<N>_<YYYYMMDDTHHMMSSZ>``
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"arc_d_v2_{rung}_{mode}_seed{seed}_{ts}"


# ── Status markers ────────────────────────────────────────────────────────


def _write_status(run_dir: Path, status: ArtifactStatus) -> None:
    """Write a status.json marker file in the run directory."""
    status_path = run_dir / "status.json"
    status_path.write_text(json.dumps(asdict(status), indent=2) + "\n")


def mark_superseded(run_dir: Path, superseded_by_run_id: str) -> None:
    """Mark a run directory as superseded.

    Writes a status.json marker file in the run directory.
    Does NOT delete the directory -- old artifacts are preserved.
    """
    status = ArtifactStatus(
        status="superseded",
        run_id=run_dir.name,
        timestamp=datetime.now(timezone.utc).isoformat(),
        superseded_by=superseded_by_run_id,
    )
    _write_status(run_dir, status)


def mark_quarantined(run_dir: Path, reason: str) -> None:
    """Mark a run directory as quarantined (known-bad)."""
    status = ArtifactStatus(
        status="quarantined",
        run_id=run_dir.name,
        timestamp=datetime.now(timezone.utc).isoformat(),
        quarantine_reason=reason,
    )
    _write_status(run_dir, status)


def mark_canonical(run_dir: Path) -> None:
    """Mark a run directory as canonical (part of official evidence)."""
    status = ArtifactStatus(
        status="canonical",
        run_id=run_dir.name,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    _write_status(run_dir, status)


# ── Status queries ────────────────────────────────────────────────────────


def get_status(run_dir: Path) -> ArtifactStatus | None:
    """Read the status of a run directory. Returns None if no status marker."""
    status_path = run_dir / "status.json"
    if not status_path.exists():
        return None
    data = json.loads(status_path.read_text())
    return ArtifactStatus(**data)


def is_active(run_dir: Path) -> bool:
    """Check if a run directory is active (canonical or no status marker).

    Runs without a status marker are considered active by default
    (backward compatibility with pre-lifecycle runs).
    """
    status = get_status(run_dir)
    if status is None:
        return True  # No marker = active by default
    return status.status in ("canonical", "exploratory")


def list_runs(rung_dir: Path) -> list[tuple[Path, ArtifactStatus | None]]:
    """List all run directories in a rung with their statuses.

    Returns a sorted list of (path, status) tuples. Directories starting
    with '.' are skipped.
    """
    runs: list[tuple[Path, ArtifactStatus | None]] = []
    if not rung_dir.exists():
        return runs
    for child in sorted(rung_dir.iterdir()):
        if child.is_dir() and not child.name.startswith("."):
            runs.append((child, get_status(child)))
    return runs


# ── Supersession workflow ─────────────────────────────────────────────────


def supersede_run(old_run_dir: Path, new_run_dir: Path) -> RerunManifest:
    """Supersede an old run with a new one.

    Marks the old run as superseded and creates a rerun manifest
    in the new run directory linking back to the old one.
    """
    mark_superseded(old_run_dir, new_run_dir.name)

    manifest = RerunManifest(
        rerun_id=f"rerun_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        rung="",  # caller should set
        trigger="manual",
        issue="superseded by newer run",
        supersedes_run_id=old_run_dir.name,
        new_run_id=new_run_dir.name,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    manifest.save(new_run_dir / "rerun_manifest.json")
    return manifest


# ── Pruning ───────────────────────────────────────────────────────────────


def prune_superseded(rung_dir: Path, *, dry_run: bool = True) -> list[Path]:
    """List (or remove) superseded and quarantined run directories.

    Args:
        rung_dir: Directory containing run subdirectories.
        dry_run: If True, only list what would be removed. If False, delete.

    Returns:
        List of paths that were/would be removed.
    """
    prunable: list[Path] = []
    for run_dir, status in list_runs(rung_dir):
        if status is not None and status.status in ("superseded", "quarantined"):
            prunable.append(run_dir)

    if not dry_run:
        for p in prunable:
            shutil.rmtree(p)

    return prunable
